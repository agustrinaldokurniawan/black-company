"""Telegram bot: Owner talks to PM only; graph pauses on Owner interrupt (resume = chat messages).

Loads `.env` from the current working directory when `python-dotenv` is installed (included in the `telegram` extra).

Env:
  TELEGRAM_BOT_TOKEN       — required (from @BotFather)
  TELEGRAM_ALLOWED_USER_IDS — optional comma-separated Telegram user ids; if empty, any user (dev only)

Commands: /start /run /reset — text replies resume an interrupt.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from typing import Any

from langgraph.types import Command

try:
    from telegram import Update
    from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
except ImportError as e:
    raise ImportError(
        "Telegram deps missing. Install: pip install 'black-company[telegram]'"
    ) from e

from black_company.graph import build_graph

logger = logging.getLogger(__name__)


def _allowed_user(user_id: int) -> bool:
    raw = os.environ.get("TELEGRAM_ALLOWED_USER_IDS", "").strip()
    if not raw:
        return True
    allowed: set[int] = set()
    for part in raw.split(","):
        part = part.strip()
        if part.isdigit():
            allowed.add(int(part))
    return user_id in allowed


def _truncate(s: str, n: int = 3500) -> str:
    s = s.strip()
    return s if len(s) <= n else s[: n - 20] + "\n…(truncated)"


def _format_interrupt(interrupts: Any) -> str:
    if not interrupts:
        return "Reply with text to continue."
    seq = interrupts if isinstance(interrupts, (list, tuple)) else (interrupts,)
    if not seq:
        return "Reply with text to continue."
    first = seq[0]
    val = getattr(first, "value", first)
    if isinstance(val, dict):
        phase = val.get("phase", "")
        prompt = val.get("prompt", "")
        if phase == "kickoff":
            spec = val.get("spec", "")
            return _truncate(f"{prompt}\n\n--- Spec ---\n{spec}")
        if phase == "acceptance":
            summ = val.get("summary", "")
            extra = val.get("spec_excerpt", "")
            return _truncate(f"{prompt}\n\n--- Readiness ---\n{summ}\n\n--- Spec (excerpt) ---\n{extra}")
        return _truncate(json.dumps(val, indent=2, ensure_ascii=False))
    return _truncate(str(val))


def _preview_state(out: dict[str, Any]) -> str:
    pub = {k: out[k] for k in sorted(out) if not str(k).startswith("_") and k != "messages"}
    return _truncate(json.dumps(pub, indent=2, default=str))


async def _invoke(graph: Any, inp: dict[str, Any] | Command, config: dict[str, Any]) -> dict[str, Any]:
    return await asyncio.to_thread(graph.invoke, inp, config)


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user and not _allowed_user(update.effective_user.id):
        await update.effective_message.reply_text("Not authorized.")
        return
    await update.effective_message.reply_text(
        "black-company: PM-hub workflow.\n"
        "/run — start (or continue after /reset)\n"
        "/reset — new LangGraph thread for this chat\n\n"
        "When the bot asks a question, reply with a normal message (yes / no / notes)."
    )


async def reset_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user and not _allowed_user(update.effective_user.id):
        await update.effective_message.reply_text("Not authorized.")
        return
    chat = update.effective_chat.id
    context.chat_data["thread_id"] = f"tg-{chat}-{uuid.uuid4().hex[:10]}"
    context.chat_data["awaiting_resume"] = False
    await update.effective_message.reply_text("New session for this chat. Use /run.")


async def run_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not _allowed_user(update.effective_user.id):
        await update.effective_message.reply_text("Not authorized.")
        return
    chat = update.effective_chat.id
    if "thread_id" not in context.chat_data:
        context.chat_data["thread_id"] = f"tg-{chat}-{uuid.uuid4().hex[:10]}"
    tid = context.chat_data["thread_id"]
    config = {"configurable": {"thread_id": tid}}
    graph = context.application.bot_data["graph"]

    context.chat_data["awaiting_resume"] = False
    await update.effective_message.reply_text("Running…")
    out = await _invoke(graph, {}, config)
    intr = out.get("__interrupt__")
    if intr:
        context.chat_data["awaiting_resume"] = True
        await update.effective_message.reply_text(_format_interrupt(intr))
        return
    await update.effective_message.reply_text("Done:\n" + _preview_state(out))


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not _allowed_user(update.effective_user.id):
        return
    if not context.chat_data.get("awaiting_resume"):
        return
    text = (update.message and update.message.text) or ""
    context.chat_data["awaiting_resume"] = False

    if "thread_id" not in context.chat_data:
        await update.effective_message.reply_text("Use /run first.")
        return
    tid = context.chat_data["thread_id"]
    config = {"configurable": {"thread_id": tid}}
    graph = context.application.bot_data["graph"]

    out = await _invoke(graph, Command(resume=text), config)
    intr = out.get("__interrupt__")
    if intr:
        context.chat_data["awaiting_resume"] = True
        await update.effective_message.reply_text(_format_interrupt(intr))
        return
    await update.effective_message.reply_text("Done:\n" + _preview_state(out))


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv()


def main() -> None:
    _load_dotenv()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise SystemExit("Set TELEGRAM_BOT_TOKEN (and optionally TELEGRAM_ALLOWED_USER_IDS).")

    graph = build_graph(with_checkpointer=True)
    application = Application.builder().token(token).build()
    application.bot_data["graph"] = graph

    application.add_handler(CommandHandler("start", start_cmd))
    application.add_handler(CommandHandler("run", run_cmd))
    application.add_handler(CommandHandler("reset", reset_cmd))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    if not os.environ.get("TELEGRAM_ALLOWED_USER_IDS", "").strip():
        logger.warning("TELEGRAM_ALLOWED_USER_IDS unset — any Telegram user can use this bot.")

    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
