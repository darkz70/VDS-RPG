# Собственный Dockerfile для bothost.ru BotHost.
# В панели bot-manage.pl включите «Использовать собственный Dockerfile» —
# тогда BotHost не будет угадывать рантайм (иначе собирает Node.js и падает).
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1
# Порт реально берётся из переменной PORT, которую задаёт BotHost
EXPOSE 3000

CMD ["python", "main.py"]
