# black-company Telegram bot (long-polling; no inbound port required for Telegram).
FROM python:3.11-slim

# System: git (clone into /projects) + Node 20 + pnpm so `/runproj` can run JS/TS stacks inside the same container.
# Remove the Node block if you only run Python projects from `/runproj`.
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates curl gnupg \
    && mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key \
        | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x nodistro main" \
        > /etc/apt/sources.list.d/nodesource.list \
    && apt-get update && apt-get install -y --no-install-recommends nodejs \
    && corepack enable && corepack prepare pnpm@9.15.0 --activate \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml ./
COPY docs ./docs/
COPY src ./src

RUN pip install --no-cache-dir ".[telegram,llm]"

ENV PYTHONUNBUFFERED=1

CMD ["black-company-telegram"]
