"""Telegram bot: PM chat by default; concrete briefs (or /run) start the team graph.

Loads `.env` from the current working directory when `python-dotenv` is installed (included in the `telegram` extra).

Optional DeepSeek for natural PM + team copy (requires ``pip install -e ".[telegram,llm]"`` and ``DEEPSEEK_API_KEY``).
Set ``BLACK_COMPANY_DISABLE_DEEPSEEK=1`` to force template fallbacks.
Set ``BLACK_COMPANY_DEEPSEEK_TELEGRAM_ONLY=1`` to call DeepSeek only for Telegram intro/recap (not every graph node).

Env:
  TELEGRAM_BOT_TOKEN       — required (from @BotFather)
  TELEGRAM_ALLOWED_USER_IDS — optional comma-separated Telegram user ids; if empty, any user (dev only)
  BLACK_COMPANY_DATA_DIR   — optional; default `./data` — growth memory SQLite + metadata
  BLACK_COMPANY_NAME       — optional; org line for PM copy (Telegram + LLM prompts)
  BLACK_COMPANY_BLURB      — optional; one line what the company does
  BLACK_COMPANY_PROJECTS   — optional; active tracks / products (short)

Chat: **PM chat** by default (planning, context, how this works). A **concrete brief**, **/run**, or
**New project** … (`:` optional) starts the team graph (typing indicator, one reply with Owner gate or recap). **Hi / hey**
stays a lightweight wave. **growth** / **milestones** for memory stats. Slash: /start /reset /growth /run /help.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import uuid
from typing import Any

from langgraph.types import Command

try:
    from telegram import Update
    from telegram.constants import ChatAction
    from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
except ImportError as e:
    raise ImportError(
        "Telegram deps missing. Install: pip install 'black-company[telegram]'"
    ) from e

from black_company.graph import build_graph
from black_company.growth import format_report, record_event
from black_company.integrations.telegram_chat import (
    casual_greeting_reply,
    casual_greeting_while_owner_waits,
    format_interrupt,
    help_text,
    idle_pm_chat_fallback,
    is_growth_lookup,
    looks_like_greeting_only,
    looks_like_idle_workflow_brief,
    looks_like_kickoff_brief_reaffirmation,
    looks_like_meta_chat_while_awaiting_owner,
    looks_like_new_brief_while_awaiting_owner,
    owner_gate_sidebar_fallback,
    pm_intro_after_request,
    pm_run_complete_message,
    strip_new_project_prefix,
    truncate,
)

logger = logging.getLogger(__name__)


async def _send_typing(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    if chat:
        await context.bot.send_chat_action(chat_id=chat.id, action=ChatAction.TYPING)


async def _run_with_typing_pulse(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    coro: Any,
) -> Any:
    """Keep Telegram 'typing…' alive during long sync work (invoke pulses ~4s)."""
    stop = asyncio.Event()

    async def _pulse() -> None:
        while not stop.is_set():
            await _send_typing(update, context)
            try:
                await asyncio.wait_for(stop.wait(), timeout=4.0)
            except asyncio.TimeoutError:
                continue

    pulse = asyncio.create_task(_pulse())
    try:
        return await coro
    finally:
        stop.set()
        pulse.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await pulse


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


async def _resolve_pm_intro(text: str | None) -> str | None:
    if not text:
        return None
    from black_company.llm.deepseek_copy import try_telegram_pm_intro

    llm = await asyncio.to_thread(try_telegram_pm_intro, text)
    return llm or pm_intro_after_request(text)


async def _resolve_pm_recap(out: dict[str, Any]) -> str:
    from black_company.llm.deepseek_copy import try_telegram_run_recap

    llm = await asyncio.to_thread(try_telegram_run_recap, out)
    return llm or pm_run_complete_message(out)


async def _invoke(graph: Any, inp: dict[str, Any] | Command, config: dict[str, Any]) -> dict[str, Any]:
    return await asyncio.to_thread(graph.invoke, inp, config)


async def _graph_state_values(graph: Any, config: dict[str, Any]) -> dict[str, Any]:
    """Read merged LangGraph state for UX copy (e.g. explain Owner gate)."""

    def _get() -> dict[str, Any]:
        try:
            snap = graph.get_state(config)
            v = getattr(snap, "values", None) if snap is not None else None
            if isinstance(v, dict):
                return dict(v)
        except Exception as e:
            logger.debug("graph.get_state failed: %s", e)
        return {}

    return await asyncio.to_thread(_get)


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
    context.chat_data.pop("last_interrupt_phase", None)


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
        context.chat_data["last_interrupt_phase"] = _intr_phase(intr)
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
            body = f"{pm_preamble}\n\n{body}"
        await update.effective_message.reply_text(truncate(body, 4000))
        return

    context.chat_data["awaiting_resume"] = False
    context.chat_data["run_finished"] = True
    context.chat_data.pop("last_interrupt_phase", None)
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
    body = await _resolve_pm_recap(out)
    if pm_preamble:
        body = f"{pm_preamble}\n\n{body}"
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
    out = await _run_with_typing_pulse(
        update,
        context,
        _invoke(graph, inp, config),
    )
    await _send_typing(update, context)
    preamble = await _resolve_pm_intro(intro_from_user_text) if intro_from_user_text else None
    await _emit_invoke_result(update, context, out, pm_preamble=preamble)


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user and not _allowed_user(update.effective_user.id):
        await update.effective_message.reply_text("Not authorized.")
        return
    await update.effective_message.reply_text(
        "PM hub — talk like Slack; org blurb comes from `.env` (`BLACK_COMPANY_*`).\n\n"
        "/help — flow + Owner pauses\n"
        "/reset — new run"
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user and not _allowed_user(update.effective_user.id):
        await update.effective_message.reply_text("Not authorized.")
        return
    await update.effective_message.reply_text(truncate(help_text(), 4000))


async def reset_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not _allowed_user(update.effective_user.id):
        await update.effective_message.reply_text("Not authorized.")
        return
    chat = update.effective_chat.id
    old_tid = context.chat_data.get("thread_id")
    context.chat_data["thread_id"] = f"tg-{chat}-{uuid.uuid4().hex[:10]}"
    context.chat_data["awaiting_resume"] = False
    context.chat_data["run_finished"] = True
    context.chat_data.pop("last_interrupt_phase", None)
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
            if "thread_id" not in context.chat_data:
                await update.effective_message.reply_text(
                    "No active session — just describe what you want to ship."
                )
                return
            tid = context.chat_data["thread_id"]
            config = {"configurable": {"thread_id": tid}}
            graph = context.application.bot_data["graph"]

            if looks_like_greeting_only(text):
                await update.effective_message.reply_text(truncate(casual_greeting_while_owner_waits(), 4000))
                return

            phase = context.chat_data.get("last_interrupt_phase")
            if phase == "kickoff":
                values_k = await _graph_state_values(graph, config)
                spec_stored = str(values_k.get("spec") or "")
                if looks_like_kickoff_brief_reaffirmation(text, spec_stored):
                    await update.effective_message.reply_text(
                        truncate("Got it — same brief counts as **yes**. Continuing…", 4000)
                    )
                    text = "yes"
            elif phase == "acceptance":
                values_a = await _graph_state_values(graph, config)
                spec_acc = str(values_a.get("spec") or "")
                if looks_like_kickoff_brief_reaffirmation(text, spec_acc):
                    await update.effective_message.reply_text(
                        truncate("Understood — re-sending the spec counts as **yes** for release.", 4000)
                    )
                    text = "yes"

            if looks_like_meta_chat_while_awaiting_owner(text):
                values = await _graph_state_values(graph, config)
                from black_company.llm.deepseek_copy import try_telegram_owner_gate_sidebar

                spec = str(values.get("spec") or "")
                st = str(values.get("status") or "")
                impl_ex = str(values.get("impl") or "")
                llm = await asyncio.to_thread(try_telegram_owner_gate_sidebar, text, spec, st, impl_ex)
                msg = llm or owner_gate_sidebar_fallback(text, spec, st, impl_ex)
                await update.effective_message.reply_text(truncate(msg, 4000))
                return

            if looks_like_new_brief_while_awaiting_owner(text):
                await update.effective_message.reply_text(
                    truncate(
                        "Still on the Owner line above — that pitch would count as your answer. "
                        "**/reset** if you meant a new thread."
                    )
                )
                return

            context.chat_data["awaiting_resume"] = False

            record_event(
                kind="owner_resume",
                source="telegram",
                actor=_actor(update),
                chat_id=str(update.effective_chat.id),
                thread_id=tid,
                detail={"text_preview": text[:300]},
            )
            out = await _run_with_typing_pulse(
                update,
                context,
                _invoke(graph, Command(resume=text), config),
            )
            await _emit_invoke_result(update, context, out, pm_preamble=None)
            return

        if not context.chat_data.get("run_finished", True):
            logger.warning("telegram: recovering session (run_finished=false, not awaiting resume)")
            context.chat_data["run_finished"] = True

        if looks_like_greeting_only(text):
            await update.effective_message.reply_text(truncate(casual_greeting_reply(), 4000))
            return

        if looks_like_idle_workflow_brief(text):
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
            return

        from black_company.llm.deepseek_copy import try_telegram_idle_pm_chat

        llm = await asyncio.to_thread(try_telegram_idle_pm_chat, text)
        msg = llm or idle_pm_chat_fallback()
        await update.effective_message.reply_text(truncate(msg, 4000))


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
    application.add_handler(CommandHandler("help", help_cmd))
    application.add_handler(CommandHandler("run", run_cmd))
    application.add_handler(CommandHandler("reset", reset_cmd))
    application.add_handler(CommandHandler("growth", growth_cmd))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    if not os.environ.get("TELEGRAM_ALLOWED_USER_IDS", "").strip():
        logger.warning("TELEGRAM_ALLOWED_USER_IDS unset — any Telegram user can use this bot.")

    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
