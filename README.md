# Black Company

> **Your offshore PM desk that never sleeps, never invoices correctly, and won’t merge your PR without an Owner saying “yes.”**  
> Also: a LangGraph + Telegram bot for pretending you have Product, Eng, and QA on retainer—while stub agents hand you plausible text and your real code stays in *your* repos.

This repo is a **PM-hub workflow demo**: brief → Owner gate → planning loop → delivery stubs → QA → ship check. The fun part is **Telegram**: chat like Slack, run workspace commands, merge `.env` keys from chat, and optionally wire **DeepSeek** so the PM sounds human instead of like a spec template from 2003.

For the original graph sketch, see [`docs/langgraph-team-sketch.md`](docs/langgraph-team-sketch.md).

---

## What you actually get

| Layer | What it does |
|--------|----------------|
| **LangGraph** | Deterministic-ish team graph with interrupts for “Owner kickoff” / “Owner acceptance.” |
| **Telegram bot** | PM voice, `/run` to start a workflow, growth memory, workspace listing, **project run** + **env merge** from chat. |
| **DeepSeek** (optional) | Nicer copy when `DEEPSEEK_API_KEY` is set; disable with `BLACK_COMPANY_DISABLE_DEEPSEEK=1`. |
| **Workspace** | Scan folders under `BLACK_COMPANY_PROJECT_ROOT` so the PM “knows” what repos exist (readme hints, git flag). |

---

## Requirements

- **Python ≥ 3.11**
- **Telegram bot token** from [@BotFather](https://t.me/BotFather)
- Optional: **DeepSeek API key** for LLM-flavored messages  
- Optional: **Docker** if you want it always-on in a container

---

## Quick start (local)

```bash
git clone <this-repo> && cd black-company
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate

pip install -e ".[telegram,llm]"
cp .env.example .env
```

Edit **`.env`**: at minimum set `TELEGRAM_BOT_TOKEN=…`. Optional: `DEEPSEEK_API_KEY`, `TELEGRAM_ALLOWED_USER_IDS` (comma-separated—**use this** so randos don’t drive your bot).

**Machine-only paths** (Windows drive letters, `BLACK_COMPANY_PROJECT_ROOT`, etc.) go in **`.env.local`** (loaded after `.env`, not used by default Docker Compose).

Run from the repo root (so dotenv finds `.env`):

```bash
python -m black_company.integrations.telegram_app
# or, if installed: black-company-telegram
```

Talk to the bot in Telegram. Try `/start`, `/help`, `/projects`.

---

## Docker (recommended for “run forever”)

```bash
cp .env.example .env
# Fill TELEGRAM_BOT_TOKEN (+ TELEGRAM_ALLOWED_USER_IDS strongly recommended)
docker compose up -d --build
docker compose logs -f telegram
```

- **`BLACK_COMPANY_DATA_DIR=/data`** — growth SQLite on a named volume.  
- **`BLACK_COMPANY_PROJECT_ROOT=/projects`** — workspace for cloning/running projects; backed by Docker volume **`black_company_workspace`** (not your host disk unless you change `docker-compose.yml` to bind-mount).

Rebuild after **Dockerfile** or code changes:

```bash
docker compose up -d --build --force-recreate
```

The image includes **Python**, **git**, **Node 20**, and **pnpm** so `/runproj` can drive typical JS/TS projects—add more runtimes in the **Dockerfile** if you need them.

---

## Environment variables (cheat sheet)

| Variable | Role |
|----------|------|
| `TELEGRAM_BOT_TOKEN` | **Required** for the bot. |
| `TELEGRAM_ALLOWED_USER_IDS` | **Strongly recommended**: only these Telegram user IDs can chat (comma-separated). |
| `DEEPSEEK_API_KEY` | Optional LLM for PM/team copy. |
| `BLACK_COMPANY_DISABLE_DEEPSEEK` | `1` = templates only. |
| `BLACK_COMPANY_DEEPSEEK_TELEGRAM_ONLY` | `1` = LLM only on Telegram intro/recap (cheaper). |
| `BLACK_COMPANY_NAME` / `BLURB` / `PROJECTS` | Injected into PM context. |
| `BLACK_COMPANY_PROJECT_ROOT` | Parent folder of project subfolders (Docker: often `/projects`). |
| `BLACK_COMPANY_DATA_DIR` | Growth DB dir (Compose sets `/data` in the container). |

Full commentary: [`.env.example`](.env.example).

---

## Telegram commands (the ones you’ll actually use)

| Command | What it does |
|---------|----------------|
| `/start` | Short help. |
| `/help` | Workflow + workspace notes. |
| `/run` | Start the **LangGraph** PM→Owner→Eng… workflow (stub agents). |
| `/reset` | New thread + clears Owner/setenv pendings; uses session nonce so races don’t resurrect old gates. |
| `/growth` | Recent milestone / memory rows from SQLite. |
| `/projects` | Lists workspace folders (HTML): hints from README/pyproject/package.json where possible. |
| `/setenv ProjectFolder` | Next message = `KEY=value` lines → **merges** into `ProjectFolder/.env`. `/cancelsetenv` aborts. **Secrets in chat are risky—rotate if exposed.** |
| `/runproj` | Lists repos that contain `.black-company-run.toml`, or `/runproj Name` runs the **fixed argv** in that manifest (no arbitrary shell from chat). |
| `/stopproj Name` | SIGTERM for a **background** run started from a manifest with `background = true`. |

Natural language: messages like **“what projects do we have?”** map to the same list as `/projects` (no LLM).

---

## Running a real project from Telegram

1. **Workspace** must point at a folder whose **children** are individual project dirs (`BLACK_COMPANY_PROJECT_ROOT`).  
2. Per project, add **`examples/dot-black-company-run.toml`** as **`.black-company-run.toml`** (command argv, `cwd`, `timeout_sec`, optional `background`).  
3. **`/setenv MyRepo`** then paste env lines if you need a `.env` there.  
4. **`/runproj MyRepo`** executes the manifest.

Tools (**node**, **pnpm**, **python**, …) must exist **in the same environment** as the bot (host PATH or Docker image).  
Clone private repos inside the container with `GITHUB_TOKEN` in `.env` and the `x-access-token` clone URL—see `.env.example`.

---

## Security (read this)

- **`TELEGRAM_ALLOWED_USER_IDS`** — treat unset as **dev only**.  
- **`/setenv`** and **`/runproj`** execute file writes and subprocesses on the host/container.  
- Don’t paste production secrets in Telegram if your chat history or backups are untrusted.

---

## Development

```bash
pip install -e ".[telegram,llm]"
python -m black_company.demo   # non-Telegram demo loop with auto-yes to interrupts
```

---

## License / vibe

Internal workflow toy. Name unrelated to any actual mercenary outfit—any resemblance to your standup is coincidental.

**May your Owner approvals be swift and your README first lines under 420 characters.**
