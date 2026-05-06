# black-company Telegram bot (long-polling; no inbound port required for Telegram).
FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml ./
COPY docs ./docs/
COPY src ./src

RUN pip install --no-cache-dir ".[telegram,llm]"

ENV PYTHONUNBUFFERED=1

CMD ["black-company-telegram"]
