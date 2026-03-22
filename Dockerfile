FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY crunchyroll_bot.py .

ENV BOT_TOKEN=""

CMD ["python3", "crunchyroll_bot.py"]
