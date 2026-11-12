#!/usr/bin/env bash
# Диагностика деплоя VDS RPG на bothost.ru.
# В веб-терминале bothost.ru (terminal.html) файлы сайта лежат в /app:
#   cd /app && bash check.sh
# Скрипт сам переходит в свою директорию, так что можно запустить и так:
#   bash /app/check.sh
cd "$(dirname "$0")"
PASS=0; FAIL=0
ok()   { echo "PASS - $1"; PASS=$((PASS+1)); }
bad()  { echo "FAIL - $1"; FAIL=$((FAIL+1)); }

echo "== VDS RPG : Между Мирами — проверка =="

# 1. Файлы на месте
for f in wsgi.py requirements.txt vdsrpg/api.py vdsrpg/bot.py vdsrpg/engine.py vdsrpg/data.py vdsrpg/config.py vdsrpg/security.py vdsrpg/store.py vdsrpg/tgapi.py webapp/index.html webapp/app.js webapp/style.css; do
  [ -f "$f" ] && ok "файл $f" || bad "нет файла $f"
done

# 2. Синтаксис Python
if python3 -m py_compile vdsrpg/*.py wsgi.py run_local.py 2>/dev/null; then ok "синтаксис Python"; else bad "синтаксис Python"; fi

# 3. Синтаксис JS (только проверка, НЕ запуск — window есть только в браузере)
if command -v node >/dev/null 2>&1; then
  node --check webapp/app.js 2>/dev/null && ok "синтаксис app.js" || bad "синтаксис app.js"
else
  echo "SKIP - node не найден, синтаксис app.js не проверен"
fi

# 4. Зависимости
python3 -c "import flask" 2>/dev/null && ok "flask установлен" || bad "flask НЕ установлен (pip install -r requirements.txt)"

# 5. .env и переменные
if [ -f .env ]; then ok ".env найден"; else echo "SKIP - .env не найден (можно задать переменные в панели сайта)"; fi
grep -q "^BOT_TOKEN=" .env 2>/dev/null && ok "BOT_TOKEN задан в .env" || echo "SKIP - BOT_TOKEN не найден в .env (проверьте панель/переменные окружения)"

# 6. Ответ сайта по health (пробуем публичный URL и localhost)
DOMAIN=$(grep -m1 "^PUBLIC_URL=" .env 2>/dev/null | cut -d= -f2- | tr -d '"' | sed 's:/$::')
for url in "${DOMAIN:-}" "http://localhost" "http://127.0.0.1"; do
  [ -z "$url" ] && continue
  body=$(curl -s -m 8 "$url/health" 2>/dev/null)
  if echo "$body" | grep -q '"ok": *true'; then ok "health отвечает: $url/health"; break; fi
done
[ -z "${body:-}" ] || echo "$body" | grep -q '"ok": *true' || bad "health не ответил (сайт не запущен? проверьте файл запуска wsgi.py в панели)"

# 7. Мини-апп отдаётся
if [ -n "${DOMAIN:-}" ]; then
  code=$(curl -s -o /dev/null -w "%{http_code}" -m 8 "$DOMAIN/app/" 2>/dev/null)
  [ "$code" = "200" ] && ok "мини-апп /app/ отвечает 200" || bad "мини-апп /app/ вернул $code"
fi

echo "== Итог: PASS=$PASS FAIL=$FAIL =="
[ "$FAIL" = "0" ]
