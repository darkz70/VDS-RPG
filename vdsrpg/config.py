import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_dotenv(path: str) -> None:
    """Простая загрузка .env файла (без внешних зависимостей).

    Реальные переменные окружения имеют приоритет над файлом.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key:
                    os.environ.setdefault(key, value)
    except FileNotFoundError:
        pass


_load_dotenv(os.path.join(BASE_DIR, ".env"))

# Telegram bot token, полученный у @BotFather
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

# Публичный URL сайта на bothost.ru, например https://vds-rpg.bothost.ru
PUBLIC_URL = os.environ.get("PUBLIC_URL", "http://localhost:8000").rstrip("/")

# URL мини-аппа, показывается в кнопке бота.
# mode=fullscreen — клиент Telegram открывает мини-апп сразу на весь экран (Bot API 8.0+)
def _with_fullscreen_mode(url: str) -> str:
    if "mode=" in url:
        return url
    return url + ("&" if "?" in url else "?") + "mode=fullscreen"

WEBAPP_URL = _with_fullscreen_mode(os.environ.get("WEBAPP_URL", PUBLIC_URL + "/app/"))

# База данных SQLite
DB_PATH = os.environ.get("DB_PATH", os.path.join(BASE_DIR, "data", "vdsrpg.db"))

# Dev-режим: пропускает HMAC-проверку initData (только для локального теста!)
ALLOW_UNSAFE_INIT = os.environ.get("ALLOW_UNSAFE_INIT", "0") == "1"

# Порт для локального запуска
PORT = int(os.environ.get("PORT", "8000"))

# Секрет для ручного вызова /setup (установка webhook)
SETUP_SECRET = os.environ.get("SETUP_SECRET", "change-me")

# Telegram ID администраторов/разработчиков (через запятую) — получают доступ
# к админ-панели в мини-аппе и команде /admin в боте
ADMIN_IDS = {int(x) for x in os.environ.get("ADMIN_IDS", "5992994003,1787475400").split(",") if x.strip().isdigit()}
