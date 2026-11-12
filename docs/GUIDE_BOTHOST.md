# Гайд: деплой на bothost.ru (BotHost)

Ваш бот на bothost.ru — это слот **BotHost**: он клонит Git-репозиторий, ставит зависимости и запускает процесс, а домен `vdsrpg.bothost.ru` проксируется на HTTP-порт этого процесса. Поэтому проект должен лежать **в корне репозитория** и содержать:

- `bothost.json` — конфиг BotHost: `{"main": "main.py", "python": "3.12"}`. **Без него BotHost думает, что проект на Node.js, и падает на `npm ci`** (именно эти ошибки были в логах).
- `main.py` — точка входа: поднимает Flask на `0.0.0.0:$PORT` (сайт + API + webhook + `/health` в одном процессе).
- `requirements.txt` — зависимости (BotHost выполнит `pip install -r requirements.txt` сам).

## 1. Настройка слота в панели bot-manage.pl (вкладки вашего бота)
- **Репозиторий**: `https://github.com/darkz70/VDS-RPG.git`, ветка `arena/16e85770-vds-rpg` → «Сохранить и пересобрать».
- **Запуск**: язык **Python**, главный файл **main.py** (обязательно явно укажите — иначе автодетект может выбрать `webapp/app.js`). Если есть галочка **«Использовать собственный Dockerfile»** — включите её (в репозитории лежит наш Dockerfile).
- **Домен**: «Использовать домен» включено, свой домен `vdsrpg.bothost.ru` **выключен** (его SSL-сертификат отозван — по нему HTTPS не работает). Используйте авто-домен слота: **`https://bot-vdsrpg-verte82.bothost.tech`**. Укажите **порт** (например, 8000) — BotHost передаст его в переменную `PORT`.
- **Переменные** (вкладка «Переменные», **не создавайте .env на хостинге** — на BotHost читаются только переменные панели):

| Переменная | Значение |
| --- | --- |
| `BOT_TOKEN` | токен от @BotFather (или поле «Токен» — BotHost подставит сам) |
| `PUBLIC_URL` | `https://bot-vdsrpg-verte82.bothost.tech` |
| `WEBAPP_URL` | `https://bot-vdsrpg-verte82.bothost.tech/app/?mode=fullscreen` |
| `SETUP_SECRET` | ваш секрет (сгенерируйте случайный) |
| `ADMIN_IDS` | `5992994003,1787475400` |
| `DB_PATH` | `/app/data/vdsrpg.db` (папка `data/` на BotHost сохраняется между пересборками) |

`PORT` задавать вручную не нужно — BotHost передаёт его автоматически.

## 2. Что происходит при деплое
1. BotHost клонит ветку, читает `bothost.json`, ставит `requirements.txt`.
2. Запускает `python main.py` → приложение слушает `0.0.0.0:$PORT`.
3. `main.py` сам регистрирует webhook `https://bot-vdsrpg-verte82.bothost.tech/webhook` и команды бота (нужен `BOT_TOKEN`).
4. Авто-домен проксируется на порт → мини-апп доступен на `https://bot-vdsrpg-verte82.bothost.tech/app/?mode=fullscreen`.

## 3. Проверка
- В браузере: `https://bot-vdsrpg-verte82.bothost.tech/health` → `{"ok": true, ...}`
- Мини-апп: `https://bot-vdsrpg-verte82.bothost.tech/app/?mode=fullscreen`
- Диагностика webhook: `https://bot-vdsrpg-verte82.bothost.tech/webhookinfo?secret=ВАШ_SETUP_SECRET`
- Ручная перестановка webhook (если нужно): `https://bot-vdsrpg-verte82.bothost.tech/setup?secret=ВАШ_SETUP_SECRET`
- В терминале панели (веб-терминал, файлы в `/app`): `bash /app/check.sh`
- В Telegram: `/start` боту → приветствие с кнопкой 🎮.

## 4. Обновление после пуша в GitHub
BotHost пересобирает бот при пуше в выбранную ветку — просто `git push`. Если домен/порт меняли — нажмите «Сохранить и пересобрать».

## 5. Частые ошибки (из логов)
- `npm error ... package-lock.json` / `npm ci` — BotHost выбрал Node.js: **добавьте `bothost.json` с `"python": "3.12"` и `"main": "main.py"` в корень репозитория** и пересоберите.
- `Cannot find module '/app/index.js'` — нет главного файла: должен быть `main.py` в корне.
- Бот молчит на /start — проверьте `BOT_TOKEN` в переменных панели и `webhookinfo` (webhook должен указывать на `https://bot-vdsrpg-verte82.bothost.tech/webhook`).
- 502/504 после смены домена/порта — нажмите «Сохранить и пересобрать», чтобы прокси и контейнер синхронизировались.
