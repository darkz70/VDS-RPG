"""Хранилище состояния игроков в SQLite (один JSON-документ на игрока)."""
import json
import os
import sqlite3
import threading

_lock = threading.RLock()
_conn = None


def _get_conn(db_path: str) -> sqlite3.Connection:
    global _conn
    with _lock:
        if _conn is None:
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
            _conn = sqlite3.connect(db_path, check_same_thread=False)
            _conn.row_factory = sqlite3.Row
            _conn.execute(
                "CREATE TABLE IF NOT EXISTS players ("
                "  tg_id INTEGER PRIMARY KEY,"
                "  data TEXT NOT NULL"
                ")"
            )
            _conn.execute(
                "CREATE TABLE IF NOT EXISTS kv ("
                "  key TEXT PRIMARY KEY,"
                "  value TEXT NOT NULL"
                ")"
            )
            _conn.execute(
                "CREATE TABLE IF NOT EXISTS promos ("
                "  code TEXT PRIMARY KEY,"
                "  reward TEXT NOT NULL,"
                "  max_uses INTEGER NOT NULL DEFAULT 1,"
                "  redeemed TEXT NOT NULL DEFAULT '[]'"
                ")"
            )
            _conn.commit()
        return _conn


# ------------------------- Глобальные флаги (kv) -------------------------
def get_flag(db_path: str, key: str, default=False):
    conn = _get_conn(db_path)
    with _lock:
        row = conn.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
    if not row:
        return default
    return row["value"] == "1"


def set_flag(db_path: str, key: str, value: bool) -> None:
    conn = _get_conn(db_path)
    with _lock:
        conn.execute(
            "INSERT INTO kv (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, "1" if value else "0"),
        )
        conn.commit()


def name_taken(db_path: str, name: str, exclude_tg_id: int = 0) -> bool:
    """Занят ли никнейм другим игроком (регистронезависимо)."""
    conn = _get_conn(db_path)
    with _lock:
        rows = conn.execute("SELECT tg_id, data FROM players").fetchall()
    n = name.strip().lower()
    for r in rows:
        if r["tg_id"] == exclude_tg_id:
            continue
        d = json.loads(r["data"])
        if str(d.get("name", "")).strip().lower() == n:
            return True
    return False


# ------------------------------ Промокоды ------------------------------
def create_promo(db_path: str, code: str, reward: dict, max_uses: int = 1) -> None:
    conn = _get_conn(db_path)
    with _lock:
        conn.execute(
            "INSERT INTO promos (code, reward, max_uses, redeemed) VALUES (?, ?, ?, '[]') "
            "ON CONFLICT(code) DO UPDATE SET reward=excluded.reward, max_uses=excluded.max_uses, redeemed='[]'",
            (code.strip().upper(), json.dumps(reward, ensure_ascii=False), int(max_uses)),
        )
        conn.commit()


def list_promos(db_path: str) -> list[dict]:
    conn = _get_conn(db_path)
    with _lock:
        rows = conn.execute("SELECT code, reward, max_uses, redeemed FROM promos ORDER BY code").fetchall()
    out = []
    for r in rows:
        redeemed = json.loads(r["redeemed"])
        out.append({
            "code": r["code"], "reward": json.loads(r["reward"]),
            "max_uses": r["max_uses"], "used": len(redeemed),
        })
    return out


def delete_promo(db_path: str, code: str) -> None:
    conn = _get_conn(db_path)
    with _lock:
        conn.execute("DELETE FROM promos WHERE code=?", (code.strip().upper(),))
        conn.commit()


def redeem_promo(db_path: str, code: str, tg_id: int) -> tuple[bool, dict | str]:
    """Использовать промокод. Вернёт (ok, reward|error)."""
    conn = _get_conn(db_path)
    code = code.strip().upper()
    with _lock:
        row = conn.execute(
            "SELECT reward, max_uses, redeemed FROM promos WHERE code=?", (code,)
        ).fetchone()
        if not row:
            return False, "Промокод не найден"
        redeemed = json.loads(row["redeemed"])
        if tg_id in redeemed:
            return False, "Ты уже использовал этот промокод"
        if len(redeemed) >= row["max_uses"]:
            return False, "Промокод уже исчерпан"
        redeemed.append(tg_id)
        conn.execute("UPDATE promos SET redeemed=? WHERE code=?", (json.dumps(redeemed), code))
        conn.commit()
    return True, json.loads(row["reward"])


def get_player(db_path: str, tg_id: int) -> dict | None:
    conn = _get_conn(db_path)
    with _lock:
        row = conn.execute("SELECT data FROM players WHERE tg_id=?", (tg_id,)).fetchone()
    if not row:
        return None
    return json.loads(row["data"])


def save_player(db_path: str, tg_id: int, data: dict) -> None:
    conn = _get_conn(db_path)
    with _lock:
        conn.execute(
            "INSERT INTO players (tg_id, data) VALUES (?, ?) "
            "ON CONFLICT(tg_id) DO UPDATE SET data=excluded.data",
            (tg_id, json.dumps(data, ensure_ascii=False)),
        )
        conn.commit()


def list_players(db_path: str) -> list[dict]:
    """Сводка по всем игрокам (для админ-панели)."""
    conn = _get_conn(db_path)
    with _lock:
        rows = conn.execute("SELECT tg_id, data FROM players ORDER BY tg_id").fetchall()
    out = []
    for r in rows:
        d = json.loads(r["data"])
        out.append({
            "tg_id": r["tg_id"],
            "name": d.get("name"),
            "level": d.get("level"),
            "darkness": d.get("darkness"),
            "egez": d.get("egez"),
            "scrolls": d.get("scrolls"),
            "characters": len(d.get("characters", [])),
            "locations_cleared": len(d.get("progress", {})),
        })
    return out


def delete_player(db_path: str, tg_id: int) -> None:
    conn = _get_conn(db_path)
    with _lock:
        conn.execute("DELETE FROM players WHERE tg_id=?", (tg_id,))
        conn.commit()
