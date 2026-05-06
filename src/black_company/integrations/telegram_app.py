"""Telegram bot: chat like the team — plain messages start work; Owner answers in thread.

Loads `.env` from the current working directory when `python-dotenv` is installed (included in the `telegram` extra).

Env:
  TELEGRAM_BOT_TOKEN       — required (from @BotFather)
  TELEGRAM_ALLOWED_USER_IDS — optional comma-separated Telegram user ids; if empty, any user (dev only)
  BLACK_COMPANY_DATA_DIR   — optional; default `./data` — growth memory SQLite + metadata

Chat: send what you’d say to a PM (“hey, can we add a wallet to this project?”). The bot replies in-character,
then runs the graph until it needs Owner input — reply with normal text (yes / no / notes). Optional:
type **growth** or **milestones** for memory stats. Slash commands are optional (/start /reset /growth /run).
"""

from __future__ import annotations

import asyncio
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
from black_company.growth import format_report, record_event
from black_company.integrations.telegram_chat import (
    format_interrupt,
    is_growth_lookup,
    pm_intro_after_request,
    pm_run_complete_message,
    strip_new_project_prefix,
    truncate,
)

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


def _intr_phase(intr: Any) -> str | None:
    if not intr:
        return None
    seq = intr if isinstance(intr, (list, tuple)) else (intr,)
    if not seq:
        return None
    first = seq[0]
    val = getattr(first, "value", first)
    if isinstance(val, dict):
        p = val.get("phase")
        return str(p) if p is not None else None
    return None


def _actor(update: Update) -> str | None:
    u = update.effective_user
    return str(u.id) if u else None


async def _invoke(graph: Any, inp: dict[str, Any] | Command, config: dict[str, Any]) -> dict[str, Any]:
    return await asyncio.to_thread(graph.invoke, inp, config)


def _invoke_lock(context: ContextTypes.DEFAULT_TYPE) -> asyncio.Lock:
    lock = context.chat_data.get("_invoke_lock")
    if lock is None:
        lock = asyncio.Lock()
        context.chat_data["_invoke_lock"] = lock
    return lock


def _prepare_thread_for_new_workflow(context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> None:
    """Fresh LangGraph thread after a completed slice, or first message in a chat."""
    if context.chat_data.get("run_finished", True):
        context.chat_data["thread_id"] = f"tg-{chat_id}-{uuid.uuid4().hex[:10]}"
    context.chat_data["run_finished"] = False
    context.chat_data["awaiting_resume"] = False


async def _emit_invoke_result(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    out: dict[str, Any],
    *,
    pm_preamble: str | None,
) -> None:
    intr = out.get("__interrupt__")
    chat = update.effective_chat.id
    tid = context.chat_data["thread_id"]

    if intr:
        context.chat_data["awaiting_resume"] = True
        context.chat_data["run_finished"] = False
        record_event(
            kind="owner_interrupt",
            source="telegram",
            actor=_actor(update),
            chat_id=str(chat),
            thread_id=tid,
            detail={"phase": _intr_phase(intr)},
        )
        body = format_interrupt(intr)
        if pm_preamble:
            body = f"{pm_preamble}\n\n— — —\n\n{body}"
        await update.effective_message.reply_text(truncate(body, 4000))
        return

    context.chat_data["awaiting_resume"] = False
    context.chat_data["run_finished"] = True
    record_event(
        kind="run_completed",
        source="telegram",
        actor=_actor(update),
        chat_id=str(chat),
        thread_id=tid,
        detail={
            "status": out.get("status"),
            "qa_result": out.get("qa_result"),
            "pair_round": out.get("pair_round"),
        },
    )
    body = pm_run_complete_message(out)
    if pm_preamble:
        body = f"{pm_preamble}\n\n— — —\n\n{body}"
    await update.effective_message.reply_text(truncate(body, 4000))


async def _start_workflow(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    spec: str | None,
    intro_from_user_text: str | None,
) -> None:
    chat = update.effective_chat.id
    _prepare_thread_for_new_workflow(context, chat)
    tid = context.chat_data["thread_id"]
    config = {"configurable": {"thread_id": tid}}
    graph = context.application.bot_data["graph"]

    inp: dict[str, Any] = {"spec": spec} if spec else {}
    record_event(
        kind="run_started",
        source="telegram",
        actor=_actor(update),
        chat_id=str(chat),
        thread_id=tid,
        detail={"from_chat": bool(intro_from_user_text)},
    )
    await update.effective_message.reply_text("On it — running the team on this now.")
    out = await _invoke(graph, inp, config)
    preamble = pm_intro_after_request(intro_from_user_text) if intro_from_user_text else None
    await _emit_invoke_result(update, context, out, pm_preamble=preamble)


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user and not _allowed_user(update.effective_user.id):
        await update.effective_message.reply_text("Not authorized.")
        return
    await update.effective_message.reply_text(
        "I’m your PM hub — talk like we’re already in Slack.\n\n"
        "• Send what you need, e.g. “can we add a wallet feature to this project?”\n"
        "• When I pause for **Owner** review, reply in plain English (yes / no / notes).\n"
        "• Say **growth** or **milestones** to see what the team remembered from past runs.\n"
        "• **New project:** … starts a fresh thread with that brief (optional prefix).\n\n"
        "Optional commands: /reset (clear session), /run (demo default brief), /growth."
    )


async def reset_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not _allowed_user(update.effective_user.id):
        await update.effective_message.reply_text("Not authorized.")
        return
    chat = update.effective_chat.id
    old_tid = context.chat_data.get("thread_id")
    context.chat_data["thread_id"] = f"tg-{chat}-{uuid.uuid4().hex[:10]}"
    context.chat_data["awaiting_resume"] = False
    context.chat_data["run_finished"] = True
    record_event(
        kind="session_reset",
        source="telegram",
        actor=_actor(update),
        chat_id=str(chat),
        thread_id=context.chat_data["thread_id"],
        detail={"previous_thread_id": old_tid},
    )
    await update.effective_message.reply_text(
        "Session cleared. Tell me what you want to build — same as messaging a real PM."
    )


async def growth_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not _allowed_user(update.effective_user.id):
        await update.effective_message.reply_text("Not authorized.")
        return
    await update.effective_message.reply_text(truncate(format_report(limit=15), 4000))


async def run_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not _allowed_user(update.effective_user.id):
        await update.effective_message.reply_text("Not authorized.")
        return
    async with _invoke_lock(context):
        await _start_workflow(update, context, spec=None, intro_from_user_text=None)


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not _allowed_user(update.effective_user.id):
        return
    text = (update.message and update.message.text) or ""
    if not text.strip():
        return

    async with _invoke_lock(context):
        if is_growth_lookup(text):
            await update.effective_message.reply_text(truncate(format_report(limit=15), 4000))
            return

        if context.chat_data.get("awaiting_resume"):
            context.chat_data["awaiting_resume"] = False
            if "thread_id" not in context.chat_data:
                await update.effective_message.reply_text(
                    "No active session — just describe what you want to ship."
                )
                return
            tid = context.chat_data["thread_id"]
            config = {"configurable": {"thread_id": tid}}
            graph = context.application.bot_data["graph"]
            chat = update.effective_chat.id

            record_event(
                kind="owner_resume",
                source="telegram",
                actor=_actor(update),
                chat_id=str(chat),
                thread_id=tid,
                detail={"text_preview": text[:300]},
            )
            out = await _invoke(graph, Command(resume=text), config)
            await _emit_invoke_result(update, context, out, pm_preamble=None)
            return

        if not context.chat_data.get("run_finished", True):
            logger.warning("telegram: recovering session (run_finished=false, not awaiting resume)")
            context.chat_data["run_finished"] = True

        body = strip_new_project_prefix(text).strip()
        if not body:
            await update.effective_message.reply_text("Tell me what you’d like the team to work on.")
            return

        await _start_workflow(
            update,
            context,
            spec=body,
            intro_from_user_text=body,
        )


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
    application.add_handler(CommandHandler("growth", growth_cmd))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    if not os.environ.get("TELEGRAM_ALLOWED_USER_IDS", "").strip():
        logger.warning("TELEGRAM_ALLOWED_USER_IDS unset — any Telegram user can use this bot.")

    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
