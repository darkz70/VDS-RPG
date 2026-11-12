"""Минимальный клиент Telegram Bot API на stdlib (urllib) — без внешних зависимостей."""
import json
import urllib.request

API_BASE = "https://api.telegram.org"


class TgApiError(Exception):
    pass


def call(token: str, method: str, **params):
    url = f"{API_BASE}/bot{token}/{method}"
    data = json.dumps(params).encode("utf-8") if params else None
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        raise TgApiError(f"Telegram API error on {method}: {e}")
    if not body.get("ok"):
        raise TgApiError(f"Telegram API error on {method}: {body}")
    return body.get("result")


def send_message(token, chat_id, text, parse_mode="HTML", reply_markup=None, disable_web_page_preview=True):
    params = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode,
              "disable_web_page_preview": disable_web_page_preview}
    if reply_markup:
        params["reply_markup"] = reply_markup
    return call(token, "sendMessage", **params)


def answer_callback(token, callback_query_id, text=None, show_alert=False):
    params = {"callback_query_id": callback_query_id, "show_alert": show_alert}
    if text:
        params["text"] = text
    return call(token, "answerCallbackQuery", **params)


def set_webhook(token, url, drop_pending=True):
    return call(token, "setWebhook", url=url, drop_pending_updates=drop_pending)


def get_webhook_info(token):
    return call(token, "getWebhookInfo")


def delete_webhook(token):
    return call(token, "deleteWebhook")


def get_me(token):
    return call(token, "getMe")


def set_my_commands(token, commands):
    return call(token, "setMyCommands", commands=commands)


def set_chat_menu_button(token, chat_id=None, text="🎮 Открыть игру", webapp_url=None):
    params = {"text": text, "menu_button": {"type": "web_app", "text": text, "web_app": {"url": webapp_url}}}
    if chat_id:
        params["chat_id"] = chat_id
    return call(token, "setChatMenuButton", **params)
