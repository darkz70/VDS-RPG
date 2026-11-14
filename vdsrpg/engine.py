"""Игровой движок VDS RPG : Между Мирами."""
import random
import time
import uuid

from . import data as D


# ---------------------------------------------------------------------------
# Создание игрока
# ---------------------------------------------------------------------------
def new_player(tg_id: int, name: str) -> dict:
    return {
        "tg_id": tg_id,
        "name": name or "Безымянная Тень",
        "registered": False,    # ник выбирается один раз при первом заходе (в мини-аппе)
        "level": 1,
        "exp": 0,
        "hp": 21,               # 20 + 1 за уровень
        "max_hp": 21,
        "pet": {"name": "Теневой щенок", "bonus_hp": 5},
        "chances": dict(D.BASE_CHANCES),
        "pending_points": 0,    # очки повышения шансов за уровни
        "darkness": D.START_DARKNESS,
        "egez": D.START_EGEZ,   # валюта открытия колод
        "gacha_free_claimed": False,  # одна бесплатная крутка навсегда
        "scrolls": 0,
        "team": [],             # id персонажей в команде
        "characters": [],       # список персонажей игрока
        "items": [],            # инвентарь
        "progress": {},         # "ch:loc" -> кол-во зачисток
        "boss_scroll_claimed": [],  # "ch:loc" боссов, с которых уже получен свиток (единоразово)
        "material_cd": {},      # "ch:loc" -> timestamp последнего дропа
        "buffs": [],            # активные зелья {effect..., battles_left}
        "brews": [],            # варки {id, potion_id, ready_at}
        "potions": {},          # сваренные зелья {potion_id: count}
        "materials": {m: 0 for m in D.MATERIALS},
        "created_at": int(time.time()),
    }


def add_character(player: dict, key: str, level: int = 1) -> dict:
    base = D.CHAR_BY_KEY[key]
    char = {
        "id": uuid.uuid4().hex[:12],
        "key": key,
        "name": base["name"],
        "rarity": base["rarity"],
        "affinities": [base["aff"]],
        "dmg_type": base["dmg_type"],
        "level": level,
        "evo": 0,
        "gear": {slot: None for slot in D.GEAR_SLOTS},
        "artifacts": [None, None, None],
        "bonus": [None] * 10,
    }
    player["characters"].append(char)
    if not player["team"]:
        player["team"].append(char["id"])
    return char


# ---------------------------------------------------------------------------
# Характеристики
# ---------------------------------------------------------------------------
def player_max_hp(player: dict) -> int:
    return 20 + player["level"] + player.get("pet", {}).get("bonus_hp", 0)


def team_size(player: dict) -> int:
    n = 1
    if player["level"] >= 3:
        n += 1
    if player["level"] >= 5:
        n += 1
    return n


def bonus_slots(char: dict) -> int:
    """10 бонусных слотов + 1 за каждый уровень персонажа."""
    return 10 + char["level"]


def char_base(char: dict) -> dict:
    return D.CHAR_BY_KEY[char["key"]]


def char_stats(char: dict, player: dict | None = None) -> dict:
    """Итоговые характеристики персонажа: база +10% за уровень +15% за эволюцию + снаряжение."""
    b = char_base(char)
    lvl_mult = 1 + 0.10 * (char["level"] - 1)     # каждый уровень +10% от начальных
    evo_mult = 1 + 0.15 * char["evo"]             # каждая эволюция +15% от начальных
    mult = lvl_mult * evo_mult
    stats = {
        "hp": int(b["hp"] * mult),
        "str": b["str"] * mult,
        "will": b["will"] * mult,
        "agi": b["agi"] * mult,
        "def": b["def"] * mult,
    }
    weapon_dmg = 0.0
    armor_def = 0.0
    for slot in ("armor", "off_armor", "gloves", "amulet", "weapon", "off_weapon"):
        item = char["gear"].get(slot)
        if item:
            stats["hp"] += item.get("hp", 0)
            stats["str"] += item.get("str", 0)
            stats["will"] += item.get("will", 0)
            stats["agi"] += item.get("agi", 0)
            stats["def"] += item.get("def", 0)
            if slot == "weapon":
                weapon_dmg += item.get("dmg", 0)
            if slot == "armor":
                armor_def += item.get("def", 0)
    for item in char["artifacts"]:
        if item:
            stats["hp"] += item.get("hp", 0)
            stats["str"] += item.get("str", 0)
            stats["will"] += item.get("will", 0)
            stats["agi"] += item.get("agi", 0)
            stats["def"] += item.get("def", 0)
    for item in char["bonus"]:
        if item:
            stats["hp"] += item.get("hp", 0)
            stats["str"] += item.get("str", 0)
            stats["will"] += item.get("will", 0)
            stats["agi"] += item.get("agi", 0)
            stats["def"] += item.get("def", 0)
    # Доп. броня: 50% защиты брони +0.1 за каждую эволюцию (на 5-й — 100%),
    # -20% ловкости на 0 эволюции, +4% за каждую эволюцию (на 5-й — 0%)
    off_armor = char["gear"].get("off_armor")
    if off_armor:
        eff = 0.5 + 0.1 * char["evo"]
        stats["def"] += armor_def * eff
        stats["agi"] *= (1 - 0.20 + 0.04 * char["evo"])
    # Доп. оружие: 50% урона оружия +0.1 за эволюцию (на 5-й — 100%)
    off_weapon = char["gear"].get("off_weapon")
    if off_weapon:
        weapon_dmg += weapon_dmg * (0.5 + 0.1 * char["evo"])
    stats["weapon_dmg"] = weapon_dmg
    return stats


def char_damage(char: dict, stats: dict) -> float:
    if char["dmg_type"] == "phys":
        return stats["str"] * 2 + stats["weapon_dmg"]
    return stats["will"] * 2 + stats["weapon_dmg"]


def suppress_mult(attacker_aff: str, defender_aff: str, attacker_evo: int) -> float:
    """Множитель подавления с учётом эволюции атакующего."""
    if not D.suppresses(attacker_aff, defender_aff):
        return 1.0
    return min(D.MAX_SUPPRESS_MULT, D.BASE_SUPPRESS_MULT + D.EVO_SUPPRESS_STEP * attacker_evo)


# ---------------------------------------------------------------------------
# Бой
# ---------------------------------------------------------------------------
def _roll(chance: float) -> bool:
    return random.random() * 100 < chance


def battle(player: dict, chapter: int, loc_n: int) -> dict:
    locs = D.gen_locations(chapter)
    if not (1 <= chapter <= D.MAX_CHAPTERS) or not (1 <= loc_n <= D.LOCS_PER_CHAPTER):
        return {"ok": False, "error": "Локация не найдена"}
    loc = locs[loc_n - 1]

    size = team_size(player)
    team_ids = player["team"][:size]
    if not team_ids:
        return {"ok": False, "error": "В команде нет персонажей"}
    chars = {c["id"]: c for c in player["characters"]}

    # Баффы от зелий
    exp_buff = sum(b.get("exp_buff", 0) for b in player["buffs"])
    dark_buff = sum(b.get("darkness_buff", 0) for b in player["buffs"])
    chance_buff = sum(b.get("chances_buff", 0) for b in player["buffs"])

    chances = {k: v + chance_buff for k, v in player["chances"].items()}
    fx = loc["theme"]["fx"]
    chances["crit"] += fx.get("crit_add", 0)
    chances["dodge"] *= fx.get("dodge_mult", 1)
    chances["combo"] *= fx.get("combo_mult", 1)

    fighters = []
    for cid in team_ids:
        c = chars[cid]
        st = char_stats(c, player)
        fighters.append({
            "kind": "player", "ref": c, "name": c["name"], "stats": st,
            "hp": st["hp"], "max_hp": st["hp"], "def": st["def"],
            "affs": list(c["affinities"]), "dmg_type": c["dmg_type"],
            "level": c["level"], "evo": c["evo"], "last_stand": 0, "ls_rounds": 0,
        })
    enemies = []
    for i, m in enumerate(loc["mobs"]):
        s = D.mob_stats(m, chapter)
        enemies.append({
            "kind": "enemy", "name": D.mob_name(loc["theme"]["id"], m, i, len(loc["mobs"])), "mtype": m,
            "hp": s["hp"], "max_hp": s["hp"], "def": s["def"], "dmg": s["dmg"],
            "affs": [s["aff"]], "exp": s["exp"],
        })

    log = []
    round_no = 1
    MAX_ROUNDS = 40

    def alive(lst):
        return [x for x in lst if x["hp"] > 0]

    def deal_damage(att, target, mult, log, round_no, tag=""):
        aff = random.choice(att["affs"])
        base = att.get("dmg", None)
        if base is None:
            base = char_damage(att["ref"], att["stats"])
        dmg = base * mult
        dmg *= random.uniform(0.9, 1.1)
        # Подавление особенности урона
        sm = suppress_mult(aff, target["affs"][0], att.get("evo", 0))
        ege = False
        if round_no >= D.CHANCES_FROM_ROUND and att["kind"] == "player" and _roll(chances["suppression"]):
            sm = max(sm, min(D.MAX_SUPPRESS_MULT, D.BASE_SUPPRESS_MULT + D.EVO_SUPPRESS_STEP * att.get("evo", 0)))
            chances["suppression"] /= 2
            ege = True
        dmg *= sm
        # Усиление/ослабление особенности от карты
        weak = fx.get("aff_weak", {}).get(aff)
        strong = fx.get("aff_strong", {}).get(aff)
        if weak:
            dmg *= weak
        if strong:
            dmg *= strong
        raw = int(round(dmg))
        mitigated = max(1, raw - int(target["def"]))
        target["def"] = max(0, target["def"] - raw // 10)  # защита падает: урон/10
        target["hp"] -= mitigated
        log.append(f"Р{round_no}: {att['name']} ({aff}) → {target['name']}: урон {mitigated} (HP: {max(0, target['hp'])})"
                   + (f" 🧿 ПОДАВЛЕНИЕ ×{sm:.2f}" if sm > 1 else "")
                   + (" [ЭГЕ]" if ege else "")
                   + (f" {tag}" if tag else ""))
        return mitigated

    while alive(enemies) and alive(fighters) and round_no <= MAX_ROUNDS:
        log.append(f"— Раунд {round_no} —")
        for f in alive(fighters):
            if not alive(enemies):
                break
            target = random.choice(alive(enemies))
            mult = 1.0
            tag = ""
            # Режим последнего шанса
            if f["level"] >= 18 and f["last_stand"] == 0 and f["hp"] <= f["max_hp"] * 0.3:
                f["last_stand"] = f["hp"]
                f["ls_rounds"] = 3
                f["hp"] += f["max_hp"]  # +100% временных HP
                log.append(f"⚡ {f['name']} активирует РЕЖИМ ПОСЛЕДНЕГО ШАНСА!")
            if f["ls_rounds"] > 0:
                mult *= 1.5
                f["ls_rounds"] -= 1
                if f["ls_rounds"] == 0 and f["last_stand"]:
                    f["hp"] = max(1, int(f["last_stand"] * 0.10))  # после режима — 10% от HP до активации
                    f["last_stand"] = -1
                    log.append(f"💀 {f['name']}: режим окончен, HP = 10% от прежнего")
            # Активная способность I (10 ур.): тяжёлый удар ×2 каждый 4-й раунд
            if f["level"] >= 10 and round_no % 4 == 0:
                mult *= 2
                tag = "⚒ Тяжёлый удар ×2"
            # Активная способность II (15 ур.): удар по всем врагам каждый 5-й раунд
            if f["level"] >= 15 and round_no % 5 == 0:
                for e in alive(enemies):
                    deal_damage(f, e, 0.8, log, round_no, "🌪 Мультиудар")
                continue
            # Крит
            if round_no >= D.CHANCES_FROM_ROUND and _roll(chances["crit"]):
                mult *= 1.5
                chances["crit"] /= 2
                tag += " 💥 КРИТ ×1.5"
            deal_damage(f, target, mult, log, round_no, tag)
            # Комбо — второй удар по той же цели
            if target["hp"] > 0 and round_no >= D.CHANCES_FROM_ROUND and _roll(chances["combo"]):
                chances["combo"] /= 2
                deal_damage(f, target, 1.0, log, round_no, "🔥 КОМБО")
        for e in alive(enemies):
            if not alive(fighters):
                break
            target = random.choice(alive(fighters))
            if round_no >= D.CHANCES_FROM_ROUND and _roll(chances["dodge"]):
                chances["dodge"] /= 2
                log.append(f"Р{round_no}: 💨 {target['name']} уклонился от атаки {e['name']}!")
                continue
            deal_damage(e, target, 1.0, log, round_no)
        round_no += 1

    win = bool(alive(fighters)) and not alive(enemies)
    result = {"ok": True, "win": win, "rounds": round_no - 1, "log": log,
              "chapter": chapter, "loc": loc_n, "theme": loc["theme"]["name"],
              "theme_desc": loc["theme"]["desc"],
              "enemies": [{"name": e["name"], "mtype": e["mtype"]} for e in enemies],
              "rewards": None, "levelups": []}
    if not win:
        return result

    # --- Награды ---
    key = f"{chapter}:{loc_n}"
    clears = player["progress"].get(key, 0)
    replay = 1.0 if clears == 0 else (0.5 if clears == 1 else 0.0)  # первое перерождение — половина, далее 0
    player["progress"][key] = clears + 1

    base_exp = sum(e["exp"] for e in enemies)
    exp_gain = int(base_exp * D.chapter_mult(chapter) * replay * (1 + exp_buff))
    darkness = int(loc["darkness"] * (1 + dark_buff))
    if replay < 1:
        darkness = int(darkness * (0.5 if clears == 1 else 0.25))

    rewards = {"exp": exp_gain, "darkness": darkness, "materials": {}, "scroll": False, "egez": 0}

    # Материалы с локаций 12, 15, 30 (кд 30 минут)
    if loc_n in D.MATERIAL_LOCS:
        last = player["material_cd"].get(key, 0)
        if time.time() - last >= D.MATERIAL_COOLDOWN_SEC:
            mat = random.choice(D.MATERIALS)
            player["materials"][mat] += 1
            player["material_cd"][key] = time.time()
            rewards["materials"][mat] = 1

    # Свиток прокачки: с ЛЮБОГО босса (11/23/35 любой главы) падает всегда, но единоразово (первая победа)
    if loc["is_boss"]:
        ck = f"{chapter}:{loc_n}"
        claimed = player.setdefault("boss_scroll_claimed", [])
        if ck not in claimed:
            claimed.append(ck)
            player["scrolls"] += 1
            rewards["scroll"] = True
        rewards["egez"] = 50
        player["egez"] += 50

    player["darkness"] += darkness
    player["exp"] += exp_gain

    # Повышение уровня игрока
    while player["exp"] >= D.exp_needed(player["level"]) and player["level"] < 100:
        player["exp"] -= D.exp_needed(player["level"])
        player["level"] += 1
        player["pending_points"] += 1
        player["max_hp"] = player_max_hp(player)
        player["hp"] = player["max_hp"]
        result["levelups"].append(player["level"])

    # Истратить баффы боёв
    for b in player["buffs"]:
        b["battles_left"] -= 1
    player["buffs"] = [b for b in player["buffs"] if b["battles_left"] > 0]

    result["rewards"] = rewards
    return result


# ---------------------------------------------------------------------------
# Прокачка персонажа
# ---------------------------------------------------------------------------
def upgrade_cost(char: dict, to_level: int) -> int:
    base = 200 if char["rarity"] <= 4 else 500
    cost = base
    for _ in range(2, to_level + 1):
        cost = cost * 2 + base
    return cost


def can_upgrade(player: dict, char: dict) -> tuple[bool, str]:
    if char["level"] >= 20:
        return False, "Достигнут максимальный уровень (20). Доступна эволюция."
    to = char["level"] + 1
    cost = upgrade_cost(char, to)
    if player["darkness"] < cost:
        return False, f"Не хватает Тьмы: нужно {cost:,}"
    if char["level"] in D.SCROLL_LEVELS and player["scrolls"] < 1:
        return False, f"Нужен свиток прокачки ({D.SCROLL_LEVELS[char['level']]})"
    req = D.PLAYER_LEVEL_REQ.get(char["level"])
    if req and player["level"] < req:
        return False, f"Нужен {req} уровень игрока"
    return True, ""


def upgrade_character(player: dict, char_id: str) -> dict:
    char = next((c for c in player["characters"] if c["id"] == char_id), None)
    if not char:
        return {"ok": False, "error": "Персонаж не найден"}
    ok, err = can_upgrade(player, char)
    if not ok:
        return {"ok": False, "error": err}
    to = char["level"] + 1
    cost = upgrade_cost(char, to)
    player["darkness"] -= cost
    if char["level"] in D.SCROLL_LEVELS:
        player["scrolls"] -= 1
    char["level"] = to
    # Больше бонусных слотов за уровень
    while len(char["bonus"]) < bonus_slots(char):
        char["bonus"].append(None)
    return {"ok": True, "level": char["level"], "darkness": player["darkness"]}


def evolve_character(player: dict, char_id: str, bonus_aff: str | None = None) -> dict:
    char = next((c for c in player["characters"] if c["id"] == char_id), None)
    if not char:
        return {"ok": False, "error": "Персонаж не найден"}
    if char["level"] < 20:
        return {"ok": False, "error": "Эволюция доступна с 20 уровня"}
    if char["evo"] >= 5:
        return {"ok": False, "error": "Достигнута максимальная эволюция (5)"}
    cost = 5000 * (char["evo"] + 1) * char["rarity"]
    if player["darkness"] < cost:
        return {"ok": False, "error": f"Не хватает Тьмы: нужно {cost:,}"}
    # На 3-й и 5-й эволюции можно выбрать доп. особенность
    if char["evo"] + 1 in (3, 5):
        if bonus_aff and bonus_aff not in char["affinities"]:
            aff = bonus_aff
        else:
            aff = random.choice([a for c in D.AFF_CYCLES.values() for a in c if a not in char["affinities"]])
        char["affinities"].append(aff)
    player["darkness"] -= cost
    char["evo"] += 1
    return {"ok": True, "evo": char["evo"], "affinities": char["affinities"], "darkness": player["darkness"]}


# ---------------------------------------------------------------------------
# Колоды (гача)
# ---------------------------------------------------------------------------
def open_pack(player: dict, free: bool = False) -> dict:
    if free:
        if player.get("gacha_free_claimed"):
            return {"ok": False, "error": "Бесплатная колода уже использована"}
        player["gacha_free_claimed"] = True
    else:
        if player["egez"] < D.PACK_COST:
            return {"ok": False, "error": f"Не хватает Э Gez: нужно {D.PACK_COST}"}
        player["egez"] -= D.PACK_COST
    # Взвешенный выбор среди существующих персонажей по весу их редкости
    weights = [D.RARITY_WEIGHTS.get(c["rarity"], 1) for c in D.CHARACTERS]
    pick = random.choices(D.CHARACTERS, weights=weights, k=1)[0]
    rarity = pick["rarity"]
    existing = next((c for c in player["characters"] if c["key"] == pick["key"]), None)
    if existing:
        gain = D.DUPLICATE_EGEZ[rarity]
        player["egez"] += gain
        return {"ok": True, "duplicate": True, "name": pick["name"], "rarity": rarity, "egez_gain": gain}
    char = add_character(player, pick["key"])
    return {"ok": True, "duplicate": False, "character": public_character(char), "rarity": rarity}


# ---------------------------------------------------------------------------
# Зельеварение
# ---------------------------------------------------------------------------
def start_brew(player: dict, potion_id: str) -> dict:
    p = D.POTION_BY_ID.get(potion_id)
    if not p:
        return {"ok": False, "error": "Зелье не найдено"}
    for mat, cnt in p["materials"].items():
        if player["materials"].get(mat, 0) < cnt:
            return {"ok": False, "error": f"Не хватает материала: {mat} ({cnt} шт.)"}
    for mat, cnt in p["materials"].items():
        player["materials"][mat] -= cnt
    brew = {"id": uuid.uuid4().hex[:10], "potion_id": potion_id, "ready_at": time.time() + p["minutes"] * 60}
    player["brews"].append(brew)
    return {"ok": True, "brew": brew, "minutes": p["minutes"]}


def claim_brew(player: dict, brew_id: str) -> dict:
    brew = next((b for b in player["brews"] if b["id"] == brew_id), None)
    if not brew:
        return {"ok": False, "error": "Варка не найдена"}
    if time.time() < brew["ready_at"]:
        return {"ok": False, "error": "Зелье ещё не готово", "ready_in": int(brew["ready_at"] - time.time())}
    player["brews"].remove(brew)
    player["potions"][brew["potion_id"]] = player["potions"].get(brew["potion_id"], 0) + 1
    return {"ok": True, "potion_id": brew["potion_id"]}


def use_potion(player: dict, potion_id: str) -> dict:
    p = D.POTION_BY_ID.get(potion_id)
    if not p or player["potions"].get(potion_id, 0) <= 0:
        return {"ok": False, "error": "Зелья нет в инвентаре"}
    player["potions"][potion_id] -= 1
    eff = p["effect"]
    if "heal_player" in eff:
        player["max_hp"] = player_max_hp(player)
        player["hp"] = min(player["max_hp"], player["hp"] + int(player["max_hp"] * eff["heal_player"]))
    if "battles" in eff:
        player["buffs"].append({**eff, "battles_left": eff["battles"], "potion": p["name"]})
    return {"ok": True, "effect": eff, "hp": player["hp"]}


# ---------------------------------------------------------------------------
# Прочее
# ---------------------------------------------------------------------------
def allocate_point(player: dict, chance: str) -> dict:
    if chance not in D.BASE_CHANCES:
        return {"ok": False, "error": "Неизвестный шанс"}
    if player["pending_points"] <= 0:
        return {"ok": False, "error": "Нет очков повышения (получаются за каждый уровень)"}
    player["pending_points"] -= 1
    player["chances"][chance] += D.CHANCE_LEVEL_STEP
    return {"ok": True, "chances": player["chances"], "pending_points": player["pending_points"]}


def gen_item(player: dict, slot: str, rarity: int | None = None) -> dict:
    rarity = rarity or random.choices([1, 2, 3, 4, 5], weights=[40, 28, 18, 10, 4])[0]
    item = {"id": uuid.uuid4().hex[:10], "slot": slot, "rarity": rarity, "name": f"{D.SLOT_NAMES[slot]} ★{rarity}"}
    points = rarity * 3
    stats = ["hp", "str", "will", "agi", "def", "dmg"]
    for _ in range(points):
        s = random.choice(stats)
        item[s] = item.get(s, 0) + random.randint(1, 2 + rarity)
    if slot == "weapon":
        item["dmg"] = item.get("dmg", 0) + rarity * 4
    if slot == "armor":
        item["def"] = item.get("def", 0) + rarity * 3
    return item


def add_loot(player: dict, count: int = 1):
    for _ in range(count):
        slot = random.choice(D.GEAR_SLOTS)
        player["items"].append(gen_item(player, slot))


def equip(player: dict, char_id: str, item_id: str) -> dict:
    char = next((c for c in player["characters"] if c["id"] == char_id), None)
    item = next((i for i in player["items"] if i["id"] == item_id), None)
    if not char or not item:
        return {"ok": False, "error": "Персонаж или предмет не найдены"}
    slot = item["slot"]
    if slot == "artifact":
        free = next((i for i, v in enumerate(char["artifacts"]) if v is None), None)
        if free is None:
            return {"ok": False, "error": "Нет свободных слотов артефактов"}
        player["items"].remove(item)
        char["artifacts"][free] = item
    elif slot == "bonus":
        if len(char["bonus"]) < bonus_slots(char):
            char["bonus"].extend([None] * (bonus_slots(char) - len(char["bonus"])))
        free = next((i for i, v in enumerate(char["bonus"]) if v is None), None)
        if free is None:
            return {"ok": False, "error": "Нет свободных бонусных слотов"}
        player["items"].remove(item)
        char["bonus"][free] = item
    else:
        old = char["gear"].get(slot)
        if old:
            player["items"].append(old)
        player["items"].remove(item)
        char["gear"][slot] = item
    return {"ok": True}


def unequip(player: dict, char_id: str, slot: str, index: int | None = None) -> dict:
    char = next((c for c in player["characters"] if c["id"] == char_id), None)
    if not char:
        return {"ok": False, "error": "Персонаж не найден"}
    if slot == "artifact":
        item = char["artifacts"][index]
        char["artifacts"][index] = None
    elif slot == "bonus":
        item = char["bonus"][index]
        char["bonus"][index] = None
    else:
        item = char["gear"].get(slot)
        char["gear"][slot] = None
    if item:
        player["items"].append(item)
    return {"ok": True}


def set_team(player: dict, char_ids: list[str]) -> dict:
    ids = [c["id"] for c in player["characters"]]
    team = [i for i in char_ids if i in ids][:team_size(player)]
    if not team:
        return {"ok": False, "error": "Команда не может быть пустой"}
    player["team"] = team
    return {"ok": True, "team": team}


# ---------------------------------------------------------------------------
# Публичное представление
# ---------------------------------------------------------------------------
def public_character(char: dict, player: dict | None = None) -> dict:
    st = char_stats(char, player)
    return {
        "id": char["id"], "key": char["key"], "name": char["name"],
        "face": char.get("face") or D.CHAR_BY_KEY.get(char["key"], {}).get("face", "🦸"),
        "rarity": char["rarity"], "level": char["level"], "evo": char["evo"],
        "affinities": char["affinities"], "dmg_type": char["dmg_type"],
        "stats": {k: round(v, 2) if isinstance(v, float) else v for k, v in st.items()},
        "milestones": {lvl: txt for lvl, txt in D.MILESTONES.items() if char["level"] >= lvl},
        "gear": char["gear"], "artifacts": char["artifacts"], "bonus": char["bonus"],
    }


def public_state(player: dict) -> dict:
    return {
        "name": player["name"], "registered": player.get("registered", True),
        "level": player["level"], "exp": player["exp"],
        "exp_needed": D.exp_needed(player["level"]),
        "hp": player["hp"], "max_hp": player_max_hp(player),
        "pet": player["pet"], "chances": player["chances"], "pending_points": player["pending_points"],
        "darkness": player["darkness"], "egez": player["egez"], "scrolls": player["scrolls"],
        "team_size": team_size(player), "team": player["team"],
        "characters": [public_character(c, player) for c in player["characters"]],
        "items": player["items"], "progress": player["progress"],
        "materials": player["materials"], "potions": player["potions"],
        "brews": player["brews"], "buffs": player["buffs"],
        "material_cd": player["material_cd"],
        "gacha_free_used": bool(player.get("gacha_free_claimed")),
    }


# ---------------------------------------------------------------------------
# Интерактивная (пошаговая) боёвка: сессия хранится в player["battle_session"]
# ---------------------------------------------------------------------------

def _battle_setup(player, chapter, loc_n):
    """Общая инициализация боя (как в battle): возвращает (loc, fighters, enemies) или (None, error)."""
    locs = D.gen_locations(chapter)
    if not (1 <= chapter <= D.MAX_CHAPTERS) or not (1 <= loc_n <= D.LOCS_PER_CHAPTER):
        return None, "Локация не найдена"
    loc = locs[loc_n - 1]
    size = team_size(player)
    team_ids = player["team"][:size]
    if not team_ids:
        return None, "В команде нет персонажей"
    chars = {c["id"]: c for c in player["characters"]}
    fighters = []
    for cid in team_ids:
        c = chars[cid]
        st = char_stats(c, player)
        fighters.append({
            "kind": "player", "ref": c, "char_id": cid, "name": c["name"], "stats": st,
            "hp": st["hp"], "max_hp": st["hp"], "def": st["def"],
            "affs": list(c["affinities"]), "dmg_type": c["dmg_type"],
            "level": c["level"], "evo": c["evo"], "defending": False,
        })
    enemies = []
    for i, m in enumerate(loc["mobs"]):
        s = D.mob_stats(m, chapter)
        enemies.append({
            "kind": "enemy", "idx": i, "name": D.mob_name(loc["theme"]["id"], m, i, len(loc["mobs"])), "mtype": m,
            "hp": s["hp"], "max_hp": s["hp"], "def": s["def"], "dmg": s["dmg"],
            "affs": [s["aff"]], "exp": s["exp"],
        })
    return (loc, fighters, enemies), None


def _sess_public(sess):
    return {
        "chapter": sess["chapter"], "loc": sess["loc"], "round": sess["round"],
        "theme": sess["theme"], "log": sess["log"][-30:],
        "fighters": [{"char_id": f["char_id"], "name": f["name"], "hp": max(0, f["hp"]), "max_hp": f["max_hp"], "level": f["level"], "defending": f["defending"]} for f in sess["fighters"]],
        "enemies": [{"idx": e["idx"], "name": e["name"], "mtype": e["mtype"], "hp": max(0, e["hp"]), "max_hp": e["max_hp"]} for e in sess["enemies"]],
        "over": sess["over"], "win": sess.get("win"),
    }


def start_battle(player: dict, chapter: int, loc_n: int) -> dict:
    """Начать пошаговый бой. Сессия сохраняется в player["battle_session"]."""
    packed, err = _battle_setup(player, chapter, loc_n)
    if err:
        return {"ok": False, "error": err}
    loc, fighters, enemies = packed
    exp_buff = sum(b.get("exp_buff", 0) for b in player["buffs"])
    dark_buff = sum(b.get("darkness_buff", 0) for b in player["buffs"])
    chance_buff = sum(b.get("chances_buff", 0) for b in player["buffs"])
    chances = {k: v + chance_buff for k, v in player["chances"].items()}
    fx = loc["theme"]["fx"]
    chances["crit"] += fx.get("crit_add", 0)
    chances["dodge"] *= fx.get("dodge_mult", 1)
    chances["combo"] *= fx.get("combo_mult", 1)
    sess = {
        "chapter": chapter, "loc": loc_n, "theme": loc["theme"]["name"],
        "fighters": fighters, "enemies": enemies, "chances": chances,
        "round": 1, "log": [f"⚔️ Бой начался: {loc['theme']['name']} — локация {loc_n}"],
        "over": False, "win": None, "exp_buff": exp_buff, "dark_buff": dark_buff,
    }
    player["battle_session"] = sess
    return {"ok": True, "battle": _sess_public(sess)}


def _sess_damage(sess, att, target, mult, tag=""):
    aff = random.choice(att["affs"])
    base = att.get("dmg")
    if base is None:
        base = char_damage(att["ref"], att["stats"])
    dmg = base * mult * random.uniform(0.9, 1.1)
    sm = suppress_mult(aff, target["affs"][0], att.get("evo", 0))
    fx = D.gen_locations(sess["chapter"])[sess["loc"] - 1]["theme"]["fx"]
    weak = fx.get("aff_weak", {}).get(aff)
    strong = fx.get("aff_strong", {}).get(aff)
    if weak:
        dmg *= weak
    if strong:
        dmg *= strong
    raw = int(round(dmg * sm))
    mitigated = max(1, raw - int(target["def"]))
    if target.get("defending"):
        mitigated = max(1, mitigated // 2)
        tag += " 🛡"
    target["def"] = max(0, target["def"] - raw // 10)
    target["hp"] -= mitigated
    sess["log"].append(f"Р{sess['round']}: {att['name']} ({aff}) → {target['name']}: урон {mitigated} (HP: {max(0, target['hp'])})" + (f" {tag}" if tag else ""))
    return mitigated


def battle_turn(player: dict, actions: list) -> dict:
    """Один ход пошагового боя. actions: [{char_id, type: attack|defend, target: enemy_idx}]."""
    sess = player.get("battle_session")
    if not sess or sess["over"]:
        return {"ok": False, "error": "Нет активного боя"}
    acts = {a.get("char_id"): a for a in (actions or [])}
    alive_f = [f for f in sess["fighters"] if f["hp"] > 0]
    alive_e = [e for e in sess["enemies"] if e["hp"] > 0]
    sess["log"].append(f"— Раунд {sess['round']} —")
    # Ход игрока
    for f in alive_f:
        if not any(e["hp"] > 0 for e in sess["enemies"]):
            break
        f["defending"] = False
        a = acts.get(f["char_id"], {"type": "attack"})
        if a.get("type") == "defend":
            f["defending"] = True
            sess["log"].append(f"Р{sess['round']}: 🛡 {f['name']} в защите")
            continue
        tgt = None
        for e in sess["enemies"]:
            if e["idx"] == a.get("target") and e["hp"] > 0:
                tgt = e
                break
        if tgt is None:
            tgt = random.choice([e for e in sess["enemies"] if e["hp"] > 0])
        mult = 1.0
        tag = ""
        if sess["round"] >= D.CHANCES_FROM_ROUND and _roll(sess["chances"]["crit"]):
            mult *= 1.5; sess["chances"]["crit"] /= 2; tag += " 💥 КРИТ ×1.5"
        if f["level"] >= 10 and sess["round"] % 4 == 0:
            mult *= 2; tag += " ⚒ Тяжёлый удар ×2"
        _sess_damage(sess, f, tgt, mult, tag)
        if tgt["hp"] > 0 and sess["round"] >= D.CHANCES_FROM_ROUND and _roll(sess["chances"]["combo"]):
            sess["chances"]["combo"] /= 2
            _sess_damage(sess, f, tgt, 1.0, "🔥 КОМБО")
    # Ход врагов
    for e in [e for e in sess["enemies"] if e["hp"] > 0]:
        if not any(f["hp"] > 0 for f in sess["fighters"]):
            break
        tgt = random.choice([f for f in sess["fighters"] if f["hp"] > 0])
        if sess["round"] >= D.CHANCES_FROM_ROUND and _roll(sess["chances"]["dodge"]):
            sess["chances"]["dodge"] /= 2
            sess["log"].append(f"Р{sess['round']}: 💨 {tgt['name']} уклонился от атаки {e['name']}!")
            continue
        _sess_damage(sess, e, tgt, 1.0)
    sess["round"] += 1

    alive_f = [f for f in sess["fighters"] if f["hp"] > 0]
    alive_e = [e for e in sess["enemies"] if e["hp"] > 0]
    if not alive_e or not alive_f or sess["round"] > 41:
        sess["over"] = True
        sess["win"] = bool(alive_f) and not alive_e
        if sess["win"]:
            _apply_battle_win(player, sess)
    out = {"ok": True, "battle": _sess_public(sess)}
    if sess["over"]:
        out["rewards"] = sess.get("rewards")
        out["levelups"] = sess.get("levelups", [])
        player["battle_session"] = None
    return out


def _apply_battle_win(player: dict, sess: dict):
    """Награды за победу в пошаговом бою (зеркало логики battle())."""
    chapter, loc_n = sess["chapter"], sess["loc"]
    loc = D.gen_locations(chapter)[loc_n - 1]
    key = f"{chapter}:{loc_n}"
    clears = player["progress"].get(key, 0)
    replay = 1.0 if clears == 0 else (0.5 if clears == 1 else 0.0)
    player["progress"][key] = clears + 1
    base_exp = sum(e["exp"] for e in sess["enemies"])
    exp_gain = int(base_exp * D.chapter_mult(chapter) * replay * (1 + sess["exp_buff"]))
    darkness = int(loc["darkness"] * (1 + sess["dark_buff"]))
    if replay < 1:
        darkness = int(darkness * (0.5 if clears == 1 else 0.25))
    rewards = {"exp": exp_gain, "darkness": darkness, "materials": {}, "scroll": False, "egez": 0}
    if loc_n in D.MATERIAL_LOCS:
        last = player["material_cd"].get(key, 0)
        if time.time() - last >= D.MATERIAL_COOLDOWN_SEC:
            mat = random.choice(D.MATERIALS)
            player["materials"][mat] += 1
            player["material_cd"][key] = time.time()
            rewards["materials"][mat] = 1
    if loc["is_boss"]:
        ck = key
        claimed = player.setdefault("boss_scroll_claimed", [])
        if ck not in claimed:
            claimed.append(ck)
            player["scrolls"] += 1
            rewards["scroll"] = True
        rewards["egez"] = 50
        player["egez"] += 50
    player["darkness"] += darkness
    player["exp"] += exp_gain
    levelups = []
    while player["exp"] >= D.exp_needed(player["level"]) and player["level"] < 100:
        player["exp"] -= D.exp_needed(player["level"])
        player["level"] += 1
        player["pending_points"] += 1
        player["max_hp"] = player_max_hp(player)
        player["hp"] = player["max_hp"]
        levelups.append(player["level"])
    for b in player["buffs"]:
        b["battles_left"] -= 1
    player["buffs"] = [b for b in player["buffs"] if b["battles_left"] > 0]
    sess["rewards"] = rewards
    sess["levelups"] = levelups
