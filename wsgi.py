"""WSGI-точка входа для bothost.ru.

На bothost.ru: создайте сайт с конфигурацией «Python WSGI», залейте файлы в
<сайт>/app, укажите этот файл (wsgi.py) как файл запуска. Приложение поднимет:
  /app/    — мини-апп игры
  /webhook — приём обновлений от Telegram
  /api/*   — API игры
"""
from vdsrpg.api import app as application

# Для локального запуска: python wsgi.py
if __name__ == "__main__":
    from vdsrpg import config
    application.run(host="0.0.0.0", port=config.PORT)
