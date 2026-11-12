"""Логика Telegram-бота (webhook-режим, подходит для shared-хостинга вроде bothost.ru)."""
import logging

from . import config, tgapi
from .store import get_player, save_player
from . import engine

logger = logging.getLogger("vdsrpg.bot")

WELCOME = (
    "🌑 <b>VDS RPG : Между Мирами</b> 🌑\n\n"
    "Мы — существа Тени. У нас нет формы, но мы подражаем другим... и их силе.\n\n"
    "Нажми кнопку ниже и открой мини-апп, чтобы отправиться в приключение: "
    "сражайся на 35 локациях каждой главы, собирай команду теней, вари зелья и открывай колоды.\n\n"
    "📱 Игра рассчитана на <b>горизонтальный экран</b> — мини-апп сама попросит повернуть устройство.\n\n"
    "Команды бота:\n"
    "/start — приветствие и кнопка игры\n"
    "/profile — краткий профиль игрока\n"
    "/admin — админ-панель (только для администраторов)\n"
    "/help — помощь"
)


def webapp_button():
    return {
        "inline_keyboard": [[
            {"text": "🎮 Открыть VDS RPG", "web_app": {"url": config.WEBAPP_URL}}
        ]]
    }


def handle_update(update: dict) -> None:
    token = config.BOT_TOKEN
    if not token:
        logger.warning("BOT_TOKEN не задан — обновление от Telegram игнорируется: %s", str(update)[:200])
        return
    message = update.get("message") or update.get("edited_message")
    callback = update.get("callback_query")
    if callback:
        try:
            tgapi.answer_callback(token, callback["id"])
        except tgapi.TgApiError:
            pass
        return
    if not message:
        return
    chat_id = message["chat"]["id"]
    user = message.get("from", {})
    tg_id = user.get("id", chat_id)
    text = (message.get("text") or "").strip()
    name = user.get("first_name") or user.get("username") or "Тень"

    if text.startswith("/start"):
        tgapi.send_message(token, chat_id, WELCOME, reply_markup=webapp_button())
        p = get_player(config.DB_PATH, tg_id)
        if p is None:
            p = engine.new_player(tg_id, name)
            engine.add_character(p, "shadow_seeker")
            save_player(config.DB_PATH, tg_id, p)
        try:
            tgapi.set_chat_menu_button(token, chat_id=chat_id, text="🎮 Играть", webapp_url=config.WEBAPP_URL)
        except tgapi.TgApiError:
            pass
    elif text.startswith("/profile"):
        p = get_player(config.DB_PATH, tg_id)
        if p is None:
            tgapi.send_message(token, chat_id, "Ты ещё не начал игру. Нажми /start и открой мини-апп 🎮")
            return
        st = engine.public_state(p)
        txt = (
            f"👤 <b>{st['name']}</b>\n"
            f"⭐ Уровень: {st['level']} ({st['exp']}/{st['exp_needed']} опыта)\n"
            f"❤️ HP: {st['hp']}/{st['max_hp']}\n"
            f"🌑 Тьма: {st['darkness']:,}\n"
            f"🃏 Э Gez: {st['egez']}\n"
            f"📜 Свитков: {st['scrolls']}\n"
            f"🎯 Команда: {len(st['team'])}/{st['team_size']}\n"
            f"⚡ Шансы: crit {st['chances']['crit']:.1f}% | уклон {st['chances']['dodge']:.1f}% | "
            f"комбо {st['chances']['combo']:.1f}% | эге {st['chances']['suppression']:.1f}%"
        )
        tgapi.send_message(token, chat_id, txt, reply_markup=webapp_button())
    elif text.startswith("/admin"):
        if tg_id not in config.ADMIN_IDS:
            tgapi.send_message(token, chat_id, "⛔ Эта команда только для администраторов.")
            return
        tgapi.send_message(
            token, chat_id,
            "🛠 <b>Админ-панель</b> открывается в мини-аппе: вкладка «🛠 Админка» (видна только тебе).\n"
            "Там: список игроков, выдача ресурсов, просмотр профиля, рассылка сообщений.",
            reply_markup=webapp_button())
    elif text.startswith("/help"):
        tgapi.send_message(token, chat_id, WELCOME, reply_markup=webapp_button())
    else:
        tgapi.send_message(token, chat_id, "Используй /start, чтобы открыть игру 🎮",
                           reply_markup=webapp_button())
