"""Flask-приложение: webhook Telegram-бота + REST API мини-аппа + статика."""
import os
import re
import time

from flask import Flask, jsonify, request, send_from_directory, redirect

from . import config, engine, tgapi
from .bot import handle_update
from .security import parse_user
from .store import (
    get_player, save_player, list_players, delete_player,
    get_flag, set_flag, name_taken,
    create_promo, list_promos, delete_promo, redeem_promo,
)
from . import data as D

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEBAPP_DIR = os.path.join(BASE_DIR, "webapp")

app = Flask(__name__, static_folder=None)


# ---------------------------------------------------------------------------
# Статика мини-аппа
# ---------------------------------------------------------------------------
@app.get("/")
def index():
    # Отдаём мини-апп напрямую (без redirect — в WebView Telegram redirect иногда не срабатывает)
    return send_from_directory(WEBAPP_DIR, "index.html")


@app.get("/app/")
def webapp_index():
    return send_from_directory(WEBAPP_DIR, "index.html")


@app.get("/app/<path:path>")
def webapp_static(path):
    return send_from_directory(WEBAPP_DIR, path)


# ---------------------------------------------------------------------------
# Webhook Telegram
# ---------------------------------------------------------------------------
@app.post("/webhook")
def webhook():
    try:
        update = request.get_json(force=True, silent=True) or {}
        app.logger.info("update: %s", str(update)[:500])
        handle_update(update)
    except Exception as e:  # не роняем webhook
        app.logger.exception("webhook error: %s", e)
    return jsonify({"ok": True})


@app.get("/webhookinfo")
def webhook_info():
    """Диагностика webhook: GET /webhookinfo?secret=<SETUP_SECRET>
    Покажет, зарегистрирован ли webhook и последнюю ошибку от Telegram."""
    if request.args.get("secret") != config.SETUP_SECRET:
        return jsonify({"ok": False, "error": "bad secret"}), 403
    try:
        info = tgapi.get_webhook_info(config.BOT_TOKEN)
    except tgapi.TgApiError as e:
        return jsonify({"ok": False, "error": str(e)}), 502
    return jsonify({"ok": True, "webhook": info})


@app.get("/setup")
def setup():
    """Установить webhook и команды бота. Вызвать один раз после деплоя:
    GET /setup?secret=<SETUP_SECRET>
    """
    if request.args.get("secret") != config.SETUP_SECRET:
        return jsonify({"ok": False, "error": "bad secret"}), 403
    from . import tgapi
    url = config.PUBLIC_URL + "/webhook"
    tgapi.set_webhook(config.BOT_TOKEN, url)
    tgapi.set_my_commands(config.BOT_TOKEN, [
        {"command": "start", "description": "Начать игру 🎮"},
        {"command": "profile", "description": "Мой профиль"},
        {"command": "admin", "description": "Админ-панель 🛠"},
        {"command": "help", "description": "Помощь"},
    ])
    me = tgapi.get_me(config.BOT_TOKEN)
    return jsonify({"ok": True, "webhook": url, "bot": me.get("username")})


# ---------------------------------------------------------------------------
# Авторизация мини-аппа
# ---------------------------------------------------------------------------
def _auth_player():
    """Вернуть (player, error_response)."""
    body = request.get_json(force=True, silent=True) or {}
    init_data = body.get("initData", "")
    user = parse_user(init_data, config.BOT_TOKEN, allow_unsafe=config.ALLOW_UNSAFE_INIT)
    if not user:
        return None, (jsonify({"ok": False, "error": "auth failed"}), 401)
    tg_id = int(user["id"])
    name = user.get("first_name") or user.get("username") or "Тень"
    player = get_player(config.DB_PATH, tg_id)
    if player is None:
        player = engine.new_player(tg_id, name)
        engine.add_character(player, D.START_CHARACTER)
        save_player(config.DB_PATH, tg_id, player)
    return player, None


def _save(player):
    save_player(config.DB_PATH, player["tg_id"], player)


def api_ok(payload=None):
    out = {"ok": True}
    if payload:
        out.update(payload)
    return jsonify(out)


def maintenance_on() -> bool:
    return get_flag(config.DB_PATH, "maintenance", False)


def _maintenance_err(player=None):
    """Если включён техперерыв — вернуть ответ-ошибку для игровых действий.
    Админы (ADMIN_IDS) проходят всегда — чтобы могли тестить и искать баги."""
    if player and player["tg_id"] in config.ADMIN_IDS:
        return None
    if maintenance_on():
        return jsonify({"ok": False, "error": "🔧 ТЕХ ПЕРЕРЫВ — игра временно недоступна. Загляните позже!", "maintenance": True})
    return None


# ---------------------------------------------------------------------------
# API игры
# ---------------------------------------------------------------------------
@app.post("/api/auth")
def api_auth():
    player, err = _auth_player()
    if err:
        return err
    _save(player)
    return api_ok({"state": engine.public_state(player), "admin": player["tg_id"] in config.ADMIN_IDS,
                   "maintenance": maintenance_on()})


@app.post("/api/state")
def api_state():
    player, err = _auth_player()
    if err:
        return err
    return api_ok({"state": engine.public_state(player), "admin": player["tg_id"] in config.ADMIN_IDS,
                   "maintenance": maintenance_on()})


NAME_RE = re.compile(r"^[\w\- ]{3,16}$", re.UNICODE)


@app.post("/api/register")
def api_register():
    """Первый заход: выбрать никнейм раз и навсегда (уникальный)."""
    player, err = _auth_player()
    if err:
        return err
    if player.get("registered", True):
        return jsonify({"ok": False, "error": "Имя уже выбрано и не может быть изменено"}), 400
    body = request.get_json(force=True, silent=True) or {}
    name = str(body.get("name", "")).strip()
    if not NAME_RE.match(name):
        return jsonify({"ok": False, "error": "Ник: 3–16 символов (буквы, цифры, '-', '_', пробел)"}), 400
    if name_taken(config.DB_PATH, name, exclude_tg_id=player["tg_id"]):
        return jsonify({"ok": False, "error": "Этот ник уже занят — выбери другой"}), 409
    player["name"] = name
    player["registered"] = True
    _save(player)
    return api_ok({"name": name, "state": engine.public_state(player)})


@app.post("/api/promo")
def api_promo():
    """Использовать промокод."""
    player, err = _auth_player()
    if err:
        return err
    body = request.get_json(force=True, silent=True) or {}
    code = str(body.get("code", "")).strip()
    if not code:
        return jsonify({"ok": False, "error": "Введите промокод"}), 400
    ok, res = redeem_promo(config.DB_PATH, code, player["tg_id"])
    if not ok:
        return jsonify({"ok": False, "error": res}), 400
    reward = res
    player["darkness"] += int(reward.get("darkness", 0))
    player["egez"] += int(reward.get("egez", 0))
    player["scrolls"] += int(reward.get("scrolls", 0))
    if reward.get("character"):
        engine.add_character(player, str(reward["character"]))
    _save(player)
    return api_ok({"reward": reward, "state": engine.public_state(player)})


# ---------------------------------------------------------------------------
# Админ-панель (только для ID из ADMIN_IDS; проверка — по валидированному initData)
# ---------------------------------------------------------------------------
def _auth_admin():
    player, err = _auth_player()
    if err:
        return None, err
    if player["tg_id"] not in config.ADMIN_IDS:
        return None, (jsonify({"ok": False, "error": "⛔ нет доступа"}), 403)
    return player, None


@app.post("/api/admin/players")
def admin_players():
    _, err = _auth_admin()
    if err:
        return err
    players = list_players(config.DB_PATH)
    return api_ok({"players": players, "total": len(players), "admin_ids": sorted(config.ADMIN_IDS),
                   "maintenance": maintenance_on(), "promos": list_promos(config.DB_PATH)})


@app.post("/api/admin/player")
def admin_player():
    _, err = _auth_admin()
    if err:
        return err
    body = request.get_json(force=True, silent=True) or {}
    target = get_player(config.DB_PATH, int(body.get("tg_id", 0)))
    if not target:
        return jsonify({"ok": False, "error": "Игрок не найден"}), 404
    return api_ok({"state": engine.public_state(target)})


@app.post("/api/admin/give")
def admin_give():
    _, err = _auth_admin()
    if err:
        return err
    body = request.get_json(force=True, silent=True) or {}
    target = get_player(config.DB_PATH, int(body.get("tg_id", 0)))
    if not target:
        return jsonify({"ok": False, "error": "Игрок не найден"}), 404
    for field in ("darkness", "egez", "scrolls"):
        val = int(body.get(field, 0) or 0)
        if val:
            target[field] = target.get(field, 0) + val
    exp = int(body.get("exp", 0) or 0)
    if exp:
        target["exp"] += exp
        while target["exp"] >= D.exp_needed(target["level"]) and target["level"] < 100:
            target["exp"] -= D.exp_needed(target["level"])
            target["level"] += 1
            target["pending_points"] += 1
            target["max_hp"] = engine.player_max_hp(target)
            target["hp"] = target["max_hp"]
    if body.get("character"):
        engine.add_character(target, str(body["character"]))
    save_player(config.DB_PATH, target["tg_id"], target)
    return api_ok({"state": engine.public_state(target)})


@app.post("/api/admin/reset")
def admin_reset():
    _, err = _auth_admin()
    if err:
        return err
    body = request.get_json(force=True, silent=True) or {}
    tg_id = int(body.get("tg_id", 0))
    delete_player(config.DB_PATH, tg_id)
    return api_ok({"reset": tg_id})


@app.post("/api/admin/broadcast")
def admin_broadcast():
    _, err = _auth_admin()
    if err:
        return err
    body = request.get_json(force=True, silent=True) or {}
    text = str(body.get("text", "")).strip()
    if not text:
        return jsonify({"ok": False, "error": "Пустое сообщение"}), 400
    if not config.BOT_TOKEN:
        return jsonify({"ok": False, "error": "BOT_TOKEN не задан"}), 400
    sent, failed = 0, 0
    for p in list_players(config.DB_PATH):
        try:
            tgapi.send_message(config.BOT_TOKEN, p["tg_id"], f"📢 <b>VDS RPG</b>: {text}")
            sent += 1
        except tgapi.TgApiError:
            failed += 1
    return api_ok({"sent": sent, "failed": failed})


@app.post("/api/admin/maintenance")
def admin_maintenance():
    """Включить/выключить техперерыв (кнопка админа)."""
    _, err = _auth_admin()
    if err:
        return err
    body = request.get_json(force=True, silent=True) or {}
    on = bool(body.get("on", False))
    set_flag(config.DB_PATH, "maintenance", on)
    return api_ok({"maintenance": on})


@app.post("/api/admin/promo/create")
def admin_promo_create():
    _, err = _auth_admin()
    if err:
        return err
    body = request.get_json(force=True, silent=True) or {}
    code = str(body.get("code", "")).strip().upper()
    if not code:
        return jsonify({"ok": False, "error": "Нужен код"}), 400
    reward = {
        "darkness": int(body.get("darkness", 0) or 0),
        "egez": int(body.get("egez", 0) or 0),
        "scrolls": int(body.get("scrolls", 0) or 0),
        "character": str(body.get("character", "")).strip() or None,
    }
    max_uses = int(body.get("max_uses", 1) or 1)
    create_promo(config.DB_PATH, code, reward, max_uses)
    return api_ok({"code": code, "reward": reward, "max_uses": max_uses})


@app.post("/api/admin/promo/delete")
def admin_promo_delete():
    _, err = _auth_admin()
    if err:
        return err
    body = request.get_json(force=True, silent=True) or {}
    delete_promo(config.DB_PATH, str(body.get("code", "")))
    return api_ok({"deleted": str(body.get("code", "")).upper()})


@app.post("/api/player/rename")
def api_rename():
    player, err = _auth_player()
    if err:
        return err
    if player.get("registered", True):
        return jsonify({"ok": False, "error": "Имя выбрано при первом заходе и не меняется"}), 400
    body = request.get_json(force=True, silent=True) or {}
    name = str(body.get("name", "")).strip()[:24]
    if not name:
        return jsonify({"ok": False, "error": "Имя не может быть пустым"}), 400
    player["name"] = name
    _save(player)
    return api_ok({"name": name})


@app.post("/api/player/allocate")
def api_allocate():
    player, err = _auth_player()
    if err:
        return err
    m = _maintenance_err(player)
    if m:
        return m
    body = request.get_json(force=True, silent=True) or {}
    res = engine.allocate_point(player, body.get("chance", ""))
    if res.get("ok"):
        _save(player)
    return jsonify(res)


@app.post("/api/player/pet")
def api_pet():
    player, err = _auth_player()
    if err:
        return err
    m = _maintenance_err(player)
    if m:
        return m
    body = request.get_json(force=True, silent=True) or {}
    name = str(body.get("name", "")).strip()[:24] or player["pet"]["name"]
    player["pet"]["name"] = name
    player["max_hp"] = engine.player_max_hp(player)
    player["hp"] = min(player["hp"], player["max_hp"])
    _save(player)
    return api_ok({"pet": player["pet"], "max_hp": player["max_hp"]})


@app.post("/api/campaign")
def api_campaign():
    player, err = _auth_player()
    if err:
        return err
    chapters = []
    for ch in range(1, D.MAX_CHAPTERS + 1):
        locs = []
        for loc in D.gen_locations(ch):
            key = f"{ch}:{loc['n']}"
            clears = player["progress"].get(key, 0)
            locs.append({
                "n": loc["n"], "mobs": loc["mobs"], "theme": loc["theme"]["name"],
                "theme_id": loc["theme"]["id"], "theme_desc": loc["theme"]["desc"], "darkness": loc["darkness"],
                "is_boss": loc["is_boss"], "materials": loc["materials"],
                "clears": clears,
                # Локации внутри главы проходятся по порядку
                "locked": loc["n"] > 1 and player["progress"].get(f"{ch}:{loc['n'] - 1}", 0) == 0,
            })
        # Глава открыта, если пройден босс (локация 35) предыдущей главы
        unlocked = ch == 1 or player["progress"].get(f"{ch - 1}:{D.LOCS_PER_CHAPTER}", 0) > 0
        chapters.append({"chapter": ch, "name": D.CHAPTER_NAMES.get(ch, f"Глава {ch}"),
                         "mult": D.chapter_mult(ch), "locations": locs, "unlocked": unlocked})
    return api_ok({"chapters": chapters, "max_chapter": D.MAX_CHAPTERS})


@app.post("/api/battle")
def api_battle():
    player, err = _auth_player()
    if err:
        return err
    m = _maintenance_err(player)
    if m:
        return m
    body = request.get_json(force=True, silent=True) or {}
    chapter = int(body.get("chapter", 1))
    loc = int(body.get("loc", 1))
    # Главы проходятся по очереди: нужен босс предыдущей главы (lock'и — для всех)
    if chapter > 1 and player["progress"].get(f"{chapter - 1}:{D.LOCS_PER_CHAPTER}", 0) == 0:
        return jsonify({"ok": False, "error": f"Глава {chapter} закрыта — сначала пройдите босса главы {chapter - 1} (локация {D.LOCS_PER_CHAPTER})"})
    if loc > 1 and player["progress"].get(f"{chapter}:{loc - 1}", 0) == 0:
        return jsonify({"ok": False, "error": f"Локация {loc} закрыта — сначала пройдите локацию {loc - 1}"})
    res = engine.battle(player, chapter, loc)
    if res.get("ok"):
        _save(player)
    return jsonify(res)


def _battle_lock_check(player, chapter, loc):
    """Те же lock'и прогрессии, что в /api/battle — для всех игроков."""
    if chapter > 1 and player["progress"].get(f"{chapter - 1}:{D.LOCS_PER_CHAPTER}", 0) == 0:
        return jsonify({"ok": False, "error": f"Глава {chapter} закрыта — сначала пройдите босса главы {chapter - 1} (локация {D.LOCS_PER_CHAPTER})"})
    if loc > 1 and player["progress"].get(f"{chapter}:{loc - 1}", 0) == 0:
        return jsonify({"ok": False, "error": f"Локация {loc} закрыта — сначала пройдите локацию {loc - 1}"})
    return None


@app.post("/api/battle/start")
def api_battle_start():
    """Начать ПОШАГОВЫЙ бой (реальная боёвка, не заглушка)."""
    player, err = _auth_player()
    if err:
        return err
    m = _maintenance_err(player)
    if m:
        return m
    body = request.get_json(force=True, silent=True) or {}
    chapter = int(body.get("chapter", 1))
    loc = int(body.get("loc", 1))
    lock = _battle_lock_check(player, chapter, loc)
    if lock:
        return lock
    r = engine.start_battle(player, chapter, loc)
    if not r.get("ok"):
        return jsonify(r), 400
    _save(player)
    return api_ok({"battle": r["battle"], "state": engine.public_state(player)})


@app.post("/api/battle/turn")
def api_battle_turn():
    """Сделать один ход в пошаговом бою: actions = [{char_id, type: attack|defend, target: enemy_idx}]."""
    player, err = _auth_player()
    if err:
        return err
    m = _maintenance_err(player)
    if m:
        return m
    body = request.get_json(force=True, silent=True) or {}
    r = engine.battle_turn(player, body.get("actions") or [])
    if r.get("ok"):
        _save(player)
    else:
        return jsonify(r), 400
    out = {"ok": True, "battle": r["battle"]}
    if r["battle"]["over"]:
        out["rewards"] = r.get("rewards")
        out["levelups"] = r.get("levelups", [])
        out["state"] = engine.public_state(player)
    return jsonify(out)


@app.post("/api/character/upgrade")
def api_upgrade():
    player, err = _auth_player()
    if err:
        return err
    m = _maintenance_err(player)
    if m:
        return m
    body = request.get_json(force=True, silent=True) or {}
    res = engine.upgrade_character(player, body.get("char_id", ""))
    if res.get("ok"):
        _save(player)
    return jsonify(res)


@app.post("/api/character/evolve")
def api_evolve():
    player, err = _auth_player()
    if err:
        return err
    m = _maintenance_err(player)
    if m:
        return m
    body = request.get_json(force=True, silent=True) or {}
    res = engine.evolve_character(player, body.get("char_id", ""), body.get("bonus_aff"))
    if res.get("ok"):
        _save(player)
    return jsonify(res)


@app.post("/api/character/team")
def api_team():
    player, err = _auth_player()
    if err:
        return err
    m = _maintenance_err(player)
    if m:
        return m
    body = request.get_json(force=True, silent=True) or {}
    res = engine.set_team(player, body.get("char_ids", []))
    if res.get("ok"):
        _save(player)
    return jsonify(res)


@app.post("/api/equip")
def api_equip():
    player, err = _auth_player()
    if err:
        return err
    m = _maintenance_err(player)
    if m:
        return m
    body = request.get_json(force=True, silent=True) or {}
    res = engine.equip(player, body.get("char_id", ""), body.get("item_id", ""))
    if res.get("ok"):
        _save(player)
    return jsonify(res)


@app.post("/api/unequip")
def api_unequip():
    player, err = _auth_player()
    if err:
        return err
    m = _maintenance_err(player)
    if m:
        return m
    body = request.get_json(force=True, silent=True) or {}
    res = engine.unequip(player, body.get("char_id", ""), body.get("slot", ""), body.get("index"))
    if res.get("ok"):
        _save(player)
    return jsonify(res)


@app.post("/api/loot")
def api_loot():
    """Выдать лут (например, награду вне боя)."""
    player, err = _auth_player()
    if err:
        return err
    m = _maintenance_err(player)
    if m:
        return m
    engine.add_loot(player, 1)
    _save(player)
    return api_ok({"items": player["items"]})


@app.post("/api/gacha/open")
def api_gacha():
    player, err = _auth_player()
    if err:
        return err
    m = _maintenance_err(player)
    if m:
        return m
    body = request.get_json(force=True, silent=True) or {}
    if body.get("dry"):
        return api_ok({"cost": D.PACK_COST})
    times = min(int(body.get("times", 1) or 1), 10)
    free = bool(body.get("free"))
    all_res, chars, last_err = [], [], None
    for i in range(times):
        is_free = free and i == 0
        r = engine.open_pack(player, free=is_free)
        if not r.get("ok"):
            last_err = r.get("error")
            if i == 0:
                return jsonify(r), 400
            break
        all_res.append(r)
        if r.get("character"):
            chars.append(r["character"])
    if all_res:
        _save(player)
    if times > 1:
        return api_ok({"characters": chars, "count": len(all_res), "last_error": last_err,
                       "state": engine.public_state(player)})
    return jsonify(all_res[0] if all_res else {"ok": False, "error": last_err or "Не хватает Э Gez"}), (200 if all_res else 400)


@app.post("/api/brewing")
def api_brewing():
    player, err = _auth_player()
    if err:
        return err
    return api_ok({
        "potions": D.POTIONS,
        "brews": player["brews"],
        "potions_ready": player["potions"],
        "materials": player["materials"],
        "now": int(time.time()),
    })


@app.post("/api/brew/start")
def api_brew_start():
    player, err = _auth_player()
    if err:
        return err
    m = _maintenance_err(player)
    if m:
        return m
    body = request.get_json(force=True, silent=True) or {}
    res = engine.start_brew(player, body.get("potion_id", ""))
    if res.get("ok"):
        _save(player)
    return jsonify(res)


@app.post("/api/brew/claim")
def api_brew_claim():
    player, err = _auth_player()
    if err:
        return err
    m = _maintenance_err(player)
    if m:
        return m
    body = request.get_json(force=True, silent=True) or {}
    res = engine.claim_brew(player, body.get("brew_id", ""))
    if res.get("ok"):
        _save(player)
    return jsonify(res)


@app.post("/api/potion/use")
def api_potion_use():
    player, err = _auth_player()
    if err:
        return err
    m = _maintenance_err(player)
    if m:
        return m
    body = request.get_json(force=True, silent=True) or {}
    res = engine.use_potion(player, body.get("potion_id", ""))
    if res.get("ok"):
        _save(player)
    return jsonify(res)


@app.get("/api/meta")
def api_meta():
    """Константы игры для фронтенда (без авторизации)."""
    return jsonify({
        "ok": True,
        "aff_cycles": D.AFF_CYCLES, "cycle_names": D.CYCLE_NAMES, "meta_cycle": D.META_CYCLE,
        "characters": D.CHARACTERS, "milestones": D.MILESTONES, "slot_names": D.SLOT_NAMES,
        "chances": D.BASE_CHANCES, "chance_names": D.CHANCE_NAMES,
        "pack_cost": D.PACK_COST, "materials": D.MATERIALS,
        "chances_from_round": D.CHANCES_FROM_ROUND,
    })


@app.get("/health")
def health():
    return jsonify({"ok": True, "service": "VDS RPG : Между Мирами"})
