"""Смоук-тест движка и API: python tests/smoke_test.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("ALLOW_UNSAFE_INIT", "1")
os.environ.setdefault("DB_PATH", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "test.db"))
if os.path.exists(os.environ["DB_PATH"]):
    os.remove(os.environ["DB_PATH"])

from vdsrpg import engine, data as D
from vdsrpg.api import app

fails = []


def check(name, cond):
    print(("PASS" if cond else "FAIL"), "-", name)
    if not cond:
        fails.append(name)


# --- affinity cycles ---
check("Огонь подавляет Лёд", D.suppresses("Огонь", "Лёд"))
check("Земля подавляет Огонь (последний подавляет первый)", D.suppresses("Земля", "Огонь"))
check("Лёд подавляет Воду (внутри цикла)", D.suppresses("Лёд", "Вода"))
check("Лёд подавляет Свет (мета: цикл1>цикл4)", D.suppresses("Лёд", "Свет"))
check("Лёд НЕ подавляет Порядок", not D.suppresses("Лёд", "Порядок"))
check("Лёд НЕ подавляет Жизнь", not D.suppresses("Лёд", "Жизнь"))
check("40 особенностей", sum(len(v) for v in D.AFF_CYCLES.values()) == 40)

# --- exp curve ---
check("exp: ур1=30", D.exp_needed(1) == 30)
check("exp: ур2=100", D.exp_needed(2) == 100)
check("exp: ур3=500", D.exp_needed(3) == 500)
check("exp: ур4=675", D.exp_needed(4) == 675)
check("exp: ур5 ~ 675*1.1265", abs(D.exp_needed(5) - 675 * 1.1265) < 1)
check("множитель главы 1 = 1", D.chapter_mult(1) == 1)
check("множитель главы 9 = 54", D.chapter_mult(9) == 54)

# --- locations ---
locs1 = D.gen_locations(1)
check("35 локаций в главе", len(locs1) == 35)
check("лок 1-5: 5 слабых", all(l["mobs"] == ["weak"] * 5 for l in locs1[:5]))
check("лок 6-10: 6 слабых + 2 средних", all(l["mobs"] == ["weak"] * 6 + ["medium"] * 2 for l in locs1[5:10]))
check("лок 11 — босс", locs1[10]["mobs"] == ["boss"])
check("в главе 1 три босса (11, 23, 35)", [l["n"] for l in locs1 if l["is_boss"]] == [11, 23, 35])
check("тьма лок1 = 26 213 875", locs1[0]["darkness"] == 26_213_875)
check("тьма лок19 = 83 267 603", locs1[18]["darkness"] == 83_267_603)
locs2 = D.gen_locations(2)
check("глава 2: первая половина — 3 сильных", locs2[0]["mobs"] == ["strong"] * 3)
check("глава 2: вторая половина — 5 сильных", locs2[20]["mobs"] == ["strong"] * 5)

# --- player & battle ---
p = engine.new_player(1, "Тестер")
engine.add_character(p, "shadow_seeker")
check("HP игрока 1 ур = 20+1 (+5 от питомца)", engine.player_max_hp(p) == 20 + 1 + 5)
check("команда 1 человек на 1 ур.", engine.team_size(p) == 1)
p["level"] = 5
check("команда 3 человека на 5 ур.", engine.team_size(p) == 3)

p = engine.new_player(1, "Тестер")
engine.add_character(p, "shadow_seeker")
p["darkness"] = 10**12
r = engine.battle(p, 1, 1)
check("бой на лок 1 проходит", r["ok"] and r["win"])
check("есть награды", r["rewards"] and r["rewards"]["exp"] > 0 and r["rewards"]["darkness"] > 0)
r2 = engine.battle(p, 1, 1)
check("первое перерождение даёт половину опыта", abs(r2["rewards"]["exp"] - r["rewards"]["exp"] / 2) <= 1)
r3 = engine.battle(p, 1, 1)
check("дальнейшие перерождения не дают опыта", r3["rewards"]["exp"] == 0)

# боссовая локация (персонажа предварительно усиливаем)
bc = p["characters"][0]
bc["level"] = 12
p["level"] = 12
rb = engine.battle(p, 1, 11)
check("бой с боссом", rb["ok"] and rb["win"] and rb["rewards"]["exp"] >= 500)

# материалы на лок 12 с кд
p2 = engine.new_player(2, "Зельевар")
c2 = engine.add_character(p2, "shadow_seeker")
c2["level"] = 12
p2["level"] = 12
p2["team"] = [c2["id"]]
p2["darkness"] = 10**12
rm = engine.battle(p2, 1, 12)
check("материал падает с локации 12", sum(rm["rewards"]["materials"].values()) == 1)
rm2 = engine.battle(p2, 1, 12)
check("кд 30 минут на материалы", sum(rm2["rewards"]["materials"].values()) == 0)

# --- leveling & chances ---
p3 = engine.new_player(3, "Ап")
engine.add_character(p3, "shadow_seeker")
p3["exp"] = D.exp_needed(1)
engine.battle(p3, 1, 1)
check("levelup сработал", p3["level"] >= 2 and p3["pending_points"] >= 1)
ok = engine.allocate_point(p3, "crit")
check("+0.1% к crit", ok["ok"] and abs(p3["chances"]["crit"] - (D.BASE_CHANCES["crit"] + 0.1)) < 1e-9)

# --- character upgrade & scrolls ---
p4 = engine.new_player(4, "Прокачка")
c = engine.add_character(p4, "light_shadow")  # 7★
p4["darkness"] = 10**9
p4["level"] = 40
ok, _ = engine.can_upgrade(p4, c)
check("прокачка 1→2 доступна", ok)
r = engine.upgrade_character(p4, c["id"])
check("уровень персонажа вырос", r["ok"] and c["level"] == 2)
c["level"] = 4
p4["scrolls"] = 0
ok, err = engine.can_upgrade(p4, c)
check("4→5 требует свиток", not ok and "свиток" in err.lower())
p4["scrolls"] = 1
c["level"] = 14
ok, err = engine.can_upgrade(p4, c)
check("14→15 при 40 ур. игрока и свитке — доступно", ok)
p4["level"] = 10
ok, err = engine.can_upgrade(p4, c)
check("14→15 при 10 ур. игрока запрещено (нужен 22)", not ok and "22" in err)

# --- evolution ---
c["level"] = 20
r = engine.evolve_character(p4, c["id"])
check("эволюция 0→1", r["ok"] and c["evo"] == 1)
for _ in range(4):
    engine.evolve_character(p4, c["id"])
check("эволюция до 5 с доп. особенностями", c["evo"] == 5 and len(c["affinities"]) == 3)
check("подавление на 5-й эволюции = 1.5", abs(engine.suppress_mult("Огонь", "Лёд", 5) - 1.5) < 1e-9)

# --- gacha ---
p5 = engine.new_player(5, "Гача")
p5["egez"] = 1000
r = engine.open_pack(p5)
check("колода открывается", r["ok"])

# --- brewing ---
p6 = engine.new_player(6, "Алхимик")
engine.add_character(p6, "shadow_seeker")
p6["materials"] = {m: 10 for m in D.MATERIALS}
r = engine.start_brew(p6, "minor_elixir")
check("варка началась", r["ok"])
p6["brews"][-1]["ready_at"] = 0
r = engine.claim_brew(p6, p6["brews"][0]["id"] if p6["brews"] else "x")
p6["potions"]["minor_elixir"] = 1
p6["hp"] = 1
r = engine.use_potion(p6, "minor_elixir")
check("зелье лечит игрока", r["ok"] and p6["hp"] > 1)

# --- gear equip ---
p7 = engine.new_player(7, "Лутер")
c7 = engine.add_character(p7, "flame_echo")
engine.add_loot(p7, 5)
item = p7["items"][0]
r = engine.equip(p7, c7["id"], item["id"])
check("экипировка работает", r["ok"] and len(p7["items"]) == 4)

# --- API через тестовый клиент ---
app.config["TESTING"] = True
client = app.test_client()
init = "tg_id=42&first_name=API"
rv = client.post("/api/auth", json={"initData": init})
check("API auth (unsafe dev mode)", rv.get_json()["ok"])
rv = client.post("/api/battle", json={"initData": init, "chapter": 1, "loc": 1})
j = rv.get_json()
check("API бой", j["ok"] and j["win"])
rv = client.post("/api/campaign", json={"initData": init})
check("API campaign: 9 глав", len(rv.get_json()["chapters"]) == 9)
chapters = rv.get_json()["chapters"]
check("API campaign: открыта только глава 1", chapters[0]["unlocked"] and not any(c["unlocked"] for c in chapters[1:]))
rv = client.post("/api/battle", json={"initData": init, "chapter": 2, "loc": 1})
check("API: бой в закрытой главе 2 отклонён", rv.get_json()["ok"] is False)
lock_init = "tg_id=43&first_name=Lock"
rv = client.post("/api/campaign", json={"initData": lock_init})
locs1 = rv.get_json()["chapters"][0]["locations"]
check("API campaign: лок 1 открыт, лок 2 закрыт", locs1[0]["locked"] is False and locs1[1]["locked"] is True)
rv = client.post("/api/battle", json={"initData": lock_init, "chapter": 1, "loc": 2})
check("API: бой на закрытой локации 2 отклонён", rv.get_json()["ok"] is False)
rv = client.post("/api/gacha/open", json={"initData": init})
check("API gaча (есть 300 Э Gez на старте)", rv.get_json()["ok"])
rv = client.get("/health")
check("health", rv.get_json()["ok"])
rv = client.get("/app/")
check("мини-апп отдаёт index.html", rv.status_code == 200 and b"telegram-web-app.js" in rv.data)
rv = client.get("/app/app.js")
check("в app.js есть requestFullscreen + lockOrientation",
      rv.status_code == 200 and b"requestFullscreen" in rv.data and b"lockOrientation" in rv.data)
rv = client.get("/app/style.css")
check("в style.css есть landscape-медиазапрос", rv.status_code == 200 and b"orientation: landscape" in rv.data)

# --- админ-панель ---
admin_init = "tg_id=5992994003&first_name=Admin"
rv = client.post("/api/auth", json={"initData": admin_init})
check("админ (5992994003) получен флаг admin", rv.get_json().get("admin") is True)
rv = client.post("/api/auth", json={"initData": init})
check("обычный игрок (42) — не админ", rv.get_json().get("admin") is False)
rv = client.post("/api/admin/players", json={"initData": init})
check("не-админу /api/admin/players запрещён (403)", rv.status_code == 403)
rv = client.post("/api/admin/players", json={"initData": admin_init})
j = rv.get_json()
check("админ видит список игроков", j["ok"] and j["total"] >= 2 and 5992994003 in j["admin_ids"])
rv = client.post("/api/admin/give", json={"initData": admin_init, "tg_id": 42, "darkness": 1000, "egez": 50, "scrolls": 2, "exp": 30})
check("админ выдаёт ресурсы", rv.get_json()["ok"] and rv.get_json()["state"]["darkness"] >= 1000)
rv = client.post("/api/admin/player", json={"initData": admin_init, "tg_id": 42})
check("админ смотрит профиль игрока", rv.get_json()["ok"] and rv.get_json()["state"]["level"] >= 2)
rv = client.post("/api/admin/reset", json={"initData": admin_init, "tg_id": 42})
check("админ сбрасывает игрока", rv.get_json()["ok"])
rv = client.post("/api/admin/broadcast", json={"initData": admin_init, "text": ""})
check("пустая рассылка отклонена", rv.status_code == 400)
rv = client.post("/api/admin/broadcast", json={"initData": init, "text": "test"})
check("не-админу рассылка запрещена (403)", rv.status_code == 403)

# --- регистрация ника, промокоды, техперерыв ---
reg_init = "tg_id=77&first_name=Новичок"
rv = client.post("/api/auth", json={"initData": reg_init})
check("новый игрок не зарегистрирован", rv.get_json()["state"]["registered"] is False)
rv = client.post("/api/register", json={"initData": reg_init, "name": "Теневой"})
check("регистрация ника", rv.get_json()["ok"] and rv.get_json()["name"] == "Теневой")
rv = client.post("/api/register", json={"initData": reg_init, "name": "Другой"})
check("повторная смена ника запрещена", rv.status_code == 400)
rv = client.post("/api/register", json={"initData": init, "name": "Теневой"})
check("чужой ник занят (409)", rv.status_code == 409)
rv = client.post("/api/player/rename", json={"initData": reg_init, "name": "X"})
check("rename после регистрации запрещён", rv.status_code == 400)

rv = client.post("/api/admin/promo/create", json={"initData": admin_init, "code": "start2026", "egez": 500, "darkness": 1000, "max_uses": 5})
check("админ создаёт промокод", rv.get_json()["ok"] and rv.get_json()["code"] == "START2026")
rv = client.post("/api/promo", json={"initData": reg_init, "code": "start2026"})
check("промокод активируется", rv.get_json()["ok"] and rv.get_json()["reward"]["egez"] == 500)
rv = client.post("/api/promo", json={"initData": reg_init, "code": "START2026"})
check("повторный промокод отклонён", rv.status_code == 400)
rv = client.post("/api/promo", json={"initData": reg_init, "code": "нет такого"})
check("несуществующий промокод отклонён", rv.status_code == 400)

rv = client.post("/api/admin/maintenance", json={"initData": admin_init, "on": True})
check("админ включает техперерыв", rv.get_json()["maintenance"] is True)
rv = client.post("/api/auth", json={"initData": reg_init})
check("auth сообщает о техперерыве", rv.get_json()["maintenance"] is True)
rv = client.post("/api/battle", json={"initData": reg_init, "chapter": 1, "loc": 1})
check("бой во время техперерыва заблокирован", rv.get_json()["ok"] is False and rv.get_json().get("maintenance") is True)
# админу во время техперерыва можно (тестить/искать баги), и lock'и глав ему не мешают
adm_b = client.post("/api/battle", json={"initData": admin_init, "chapter": 3, "loc": 35})
check("админ во время техперерыва может биться на любой локации", adm_b.get_json()["ok"] is True)
rv = client.post("/api/admin/maintenance", json={"initData": admin_init, "on": False})
check("админ выключает техперерыв", rv.get_json()["maintenance"] is False)
rv = client.post("/api/admin/give", json={"initData": admin_init, "tg_id": 77, "character": "crimson_echo"})
check("админ выдаёт персонажа", rv.get_json()["ok"] and any(c["key"] == "crimson_echo" for c in rv.get_json()["state"]["characters"]))

# Свиток прокачки: с любого босса падает всегда, но единоразово (проверяем на уровне движка)
bp = engine.new_player(424242, "Босс-Тестер")
bp["level"] = 60; bp["max_hp"] = engine.player_max_hp(bp); bp["hp"] = bp["max_hp"]
for ck in [c["key"] for c in D.CHARACTERS][:4]:
    bp["team"].append(engine.add_character(bp, ck, 60)["id"])
b1 = engine.battle(bp, 1, 11)
check("первый бой с боссом 1:11 — победа и свиток падает", b1["win"] and b1["rewards"]["scroll"] is True)
b2 = engine.battle(bp, 1, 11)
check("повторный бой с тем же боссом — свиток НЕ падает", b2["win"] and b2["rewards"]["scroll"] is False)
b3 = engine.battle(bp, 1, 23)
check("другой босс 1:23 — свиток снова падает", b3["win"] and b3["rewards"]["scroll"] is True)

print()
if fails:
    print("FAILED:", fails)
    sys.exit(1)
print("ALL TESTS PASSED ✅")

# --- Пошаговая боёвка ---
sb = engine.start_battle(bp, 2, 1)
check("start_battle создаёт сессию", sb["ok"] and sb["battle"]["round"] == 1)
turns = 0
while bp.get("battle_session") and turns < 45:
    acts = [{"char_id": f["char_id"], "type": "attack", "target": bp["battle_session"]["enemies"][0]["idx"]}
            for f in bp["battle_session"]["fighters"] if f["hp"] > 0]
    rr = engine.battle_turn(bp, acts)
    turns += 1
check("пошаговый бой завершился победой", rr["ok"] and rr["battle"]["over"] and rr["battle"]["win"])
check("за победу выданы награды", rr.get("rewards") is not None and rr["rewards"]["exp"] > 0)
check("сессия очищена после боя", bp.get("battle_session") is None)
