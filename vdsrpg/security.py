"""Проверка подлинности initData от Telegram Mini App.

Алгоритм по документации Telegram:
  secret_key = HMAC_SHA256(key=b"WebAppData", msg=bot_token)
  hash       = HMAC_SHA256(key=secret_key, msg=data_check_string)
где data_check_string — все пары key=value (кроме hash), отсортированные по ключу,
соединённые через '\n'.
"""
import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl


def validate_init_data(init_data: str, bot_token: str, max_age: int = 86400) -> dict | None:
    """Возвращает dict с полями initData (user и т.д.), если подпись верна, иначе None."""
    if not init_data or not bot_token:
        return None
    try:
        pairs = parse_qsl(init_data, keep_blank_values=True)
    except Exception:
        return None
    data = dict(pairs)
    received_hash = data.pop("hash", None)
    if not received_hash:
        return None
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    calc = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calc, received_hash):
        return None
    auth_date = int(data.get("auth_date", 0))
    if max_age and auth_date and time.time() - auth_date > max_age:
        return None
    user = data.get("user")
    if user:
        try:
            data["user"] = json.loads(user)
        except Exception:
            return None
    return data


def parse_user(init_data: str, bot_token: str, allow_unsafe: bool = False) -> dict | None:
    """Вернуть объект user из initData. В dev-режиме — синтетический пользователь."""
    if allow_unsafe:
        try:
            data = dict(parse_qsl(init_data, keep_blank_values=True))
        except Exception:
            data = {}
        user = data.get("user")
        if user:
            try:
                return json.loads(user)
            except Exception:
                pass
        fake_id = int(data.get("tg_id", "1"))
        return {"id": fake_id, "first_name": data.get("first_name", "Тень"), "username": ""}
    parsed = validate_init_data(init_data, bot_token)
    if not parsed:
        return None
    return parsed.get("user")
