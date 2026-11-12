"""Точка входа для BotHost (bothost.ru).

BotHost клонит репозиторий, читает bothost.json (main: main.py, python 3.12),
выполняет `pip install -r requirements.txt` и запускает `python main.py`.
Приложение обязано слушать HTTP на 0.0.0.0:$PORT — домен бота (vdsrpg.bothost.ru)
проксируется на этот порт, а /health используется для проверки живости.

Эндпоинты одного процесса:
  /app/    — мини-апп
  /api/*   — API игры
  /webhook — приём обновлений Telegram
  /health  — health-check для BotHost
  /setup, /webhookinfo — ручная настройка/диагностика (?secret=SETUP_SECRET)
"""
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from vdsrpg import config
from vdsrpg.api import app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("vdsrpg.main")


def maybe_setup_webhook() -> None:
    """Автоматически регистрирует webhook и команды бота при старте,
    если заданы BOT_TOKEN и PUBLIC_URL (на bothost это переменные панели)."""
    if not (config.BOT_TOKEN and config.PUBLIC_URL):
        logger.info("BOT_TOKEN/PUBLIC_URL не заданы — webhook настраивается вручную через /setup")
        return
    from vdsrpg import tgapi
    url = config.PUBLIC_URL.rstrip("/") + "/webhook"
    try:
        tgapi.set_webhook(config.BOT_TOKEN, url)
        tgapi.set_my_commands(config.BOT_TOKEN, [
            {"command": "start", "description": "Начать игру 🎮"},
            {"command": "profile", "description": "Мой профиль"},
            {"command": "admin", "description": "Админ-панель 🛠"},
            {"command": "help", "description": "Помощь"},
        ])
        logger.info("Webhook установлен: %s", url)
    except Exception as e:
        logger.warning("Автоустановка webhook не удалась (повторите через /setup): %s", e)


if __name__ == "__main__":
    maybe_setup_webhook()
    port = int(os.environ.get("PORT", str(config.PORT)))
    logger.info("VDS RPG : Между Мирами слушает 0.0.0.0:%s", port)
    app.run(host="0.0.0.0", port=port)
