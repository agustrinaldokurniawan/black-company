# black-company Telegram bot (long-polling; no inbound port required for Telegram).
FROM python:3.11-slim

# `git` is not in slim — needed if you clone into `/projects` inside the container.
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml ./
COPY docs ./docs/
COPY src ./src

RUN pip install --no-cache-dir ".[telegram,llm]"

ENV PYTHONUNBUFFERED=1

CMD ["black-company-telegram"]
