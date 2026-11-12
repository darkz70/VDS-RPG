# VDS RPG : Между Мирами 🌑

Telegram-бот + мини-апп (Mini App) с RPG-игрой. Хостится на [bothost.ru](https://bothost.ru) как обычное Python WSGI-приложение. Мини-апп **принудительно запрашивает горизонтальный экран** через `requestFullscreen()` + `lockOrientation()` (нативный экран Telegram «Rotate your device horizontally»), с фолбэк-оверлеем для клиентов без поддержки lock.

**Лор:** мы — существа Тени, раса без формы, которая подражает другим и их способностям.

## Что внутри
- `vdsrpg/` — бэкенд: бот (webhook), REST API игры, игровой движок, SQLite-хранилище
  - 40 особенностей урона в 4 циклах + мета-цикл, подавление ×1.25 (×1.5 на 5-й эволюции)
  - Система игрока: уровень/опыт (30/100/500/675, далее ×1.1265 до 25 ур., ×1.04 до 50, ×1.015 после), HP = 20 + уровень, 4 шанса (крит/уклон/комбо/эге-подавление, с 4-го раунда, после срабатывания ÷2), валюты Тьма и Э Gez, питомец
  - 12 глав × 35 локаций, боссы, особенности карты, материалы на локациях 12/15/30 (кд 30 мин), свитки с боссов глав 4/8/12
  - Персонажи 1–7★: уровни 1–20 (+10% за уровень), вехи 5/10/15/17/18/19/20, режим последнего шанса, эволюции 0–5 (+15% за эволюцию)
  - 8 типов слотов снаряжения (в т.ч. доп. броня/оружие от эволюции), защита падает на урон÷10
  - Зельеварение: 5 редкостей (10 мин … 5 ч); колоды (гача) за Э Gez
- `webapp/` — мини-апп (telegram-web-app.js): принудительный landscape, карта, бой с логом раундов, профиль, персонажи, колоды, зелья
- `docs/` — `GUIDE_BOTFATHER.md` (бот + мини-апп + landscape), `GUIDE_BOTHOST.md` (деплой на bothost.ru)
- **Админ-панель для разработчиков**: Telegram ID задаются в `ADMIN_IDS` (`.env`, по умолчанию `5992994003,1787475400`). Админы получают команду `/admin` в боте и вкладку «🛠 Админка» в мини-аппе (список игроков, выдача Тьмы/Э Gez/свитков/опыта, просмотр профиля, сброс игрока, рассылка сообщений всем). Доступ проверяется на сервере по валидированному initData — ручки `/api/admin/*` отвечают 403 не-админам.
- `tests/smoke_test.py` — 50+ проверок механик и API

## Быстрый старт локально
```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env   # для локального теста включите ALLOW_UNSAFE_INIT=1
.venv/bin/python run_local.py    # http://localhost:8000/app/
.venv/bin/python tests/smoke_test.py
```

## Деплой на bothost.ru (BotHost)
Проект лежит в корне репозитория и деплоится как слот BotHost: `bothost.json` (`main.py`, Python 3.12) + `requirements.txt` + `Dockerfile`; `main.py` поднимает Flask на `0.0.0.0:$PORT` (мини-апп `/app/`, API `/api/*`, webhook `/webhook`, `/health`). Авто-домен слота `https://bot-vdsrpg-verte82.bothost.tech` проксируется на этот порт (свой домен `vdsrpg.bothost.ru` — только с валидным SSL). Переменные (`BOT_TOKEN`, `PUBLIC_URL=https://bot-vdsrpg-verte82.bothost.tech`, `WEBAPP_URL=.../app/?mode=fullscreen`, `SETUP_SECRET`, `ADMIN_IDS`, `DB_PATH=/app/data/vdsrpg.db`) задаются во вкладке «Переменные» панели — **не через .env на хостинге**. Webhook регистрируется автоматически при старте. Подробно: `docs/GUIDE_BOTHOST.md`; создание бота и мини-аппа: `docs/GUIDE_BOTFATHER.md`.

## API мини-аппа
Все POST-ручки принимают `{"initData": "...", ...}` и валидируют подпись Telegram:
`/api/auth`, `/api/state`, `/api/campaign`, `/api/battle`, `/api/player/rename`, `/api/player/allocate`, `/api/player/pet`, `/api/character/upgrade|evolve|team`, `/api/equip`, `/api/unequip`, `/api/loot`, `/api/gacha/open`, `/api/brewing`, `/api/brew/start|claim`, `/api/potion/use`.

## Фоны глав
Каждая глава имеет свой фон: положите картинку в `webapp/img/ch<N>.png (или ch<N>.jpg)` (N = номер главы, 1..12), например `ch1.png`. Если картинки нет — покажется фирменный градиент с оттенком этой главы. Размер — по ширине экрана, обрезка `cover` (ориентир ~1280×720).
