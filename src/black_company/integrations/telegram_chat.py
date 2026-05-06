"""Natural-language replies for Telegram (PM voice, no raw JSON)."""

from __future__ import annotations

import json
import re
from typing import Any


_GREET = frozenset({
    "hi",
    "hey",
    "hei",
    "hai",
    "hiya",
    "yo",
    "hello",
    "howdy",
    "hallo",
    "hola",
    "sup",
    "hay",
})
_GREET_TAIL = frozenset({"there", "team", "all", "folks", "everyone"})


def looks_like_greeting_only(text: str) -> bool:
    """Pure hi / hey — do not start LangGraph or treat as a brief."""
    raw = (text or "").strip().lower()
    if not raw or len(raw) > 44:
        return False
    t = re.sub(r"[!?.,]+$", "", raw)
    words = t.split()
    if not words or len(words) > 3:
        return False
    if any(len(w) > 14 for w in words):
        return False
    if len(words) == 1:
        return words[0] in _GREET
    if len(words) == 2:
        a, b = words
        if a in _GREET and b in _GREET:
            return True
        if a in _GREET and b in _GREET_TAIL:
            return True
    if len(words) == 3:
        return words[0] in _GREET and words[1] in _GREET_TAIL and words[2] in _GREET_TAIL
    return False


def casual_greeting_reply() -> str:
    return (
        "Hey — that’s just a wave, so I didn’t open a run. "
        "Send what you actually want scoped when you’re ready. /help"
    )


def casual_greeting_while_owner_waits() -> str:
    return "Hey. Still need your call on the Owner line above when you can."


def truncate(s: str, n: int = 3500) -> str:
    s = s.strip()
    return s if len(s) <= n else s[: n - 20] + "\n…(truncated)"


def pm_intro_after_request(user_message: str) -> str:
    from black_company.company_context import company_context_for_llm

    ctx = company_context_for_llm().strip()
    if len(ctx) > 320:
        ctx = ctx[:317] + "…"
    return f"{ctx}\n\nRoger — running kickoff on my side from what you sent."


def pm_run_complete_message(out: dict[str, Any]) -> str:
    st = out.get("status", "?")
    qa = out.get("qa_result", "?")
    owner_k = out.get("owner_kickoff", "—")
    owner_a = out.get("owner_acceptance", "—")
    lines = [
        "All right — this slice cleared the workflow.",
        f"• Status: {st}",
        f"• QA: {qa}",
        f"• Owner kickoff: {owner_k}",
        f"• Owner acceptance: {owner_a}",
    ]
    summ = (out.get("pm_readiness_summary") or "").strip()
    if summ:
        lines.extend(["", "Last internal readiness note:", truncate(summ, 900)])
    unotes = (out.get("user_agent_notes") or "").strip()
    if unotes:
        lines.extend(["", "Product (ship gate):", truncate(unotes, 400)])
    return "\n".join(lines)


def format_interrupt(interrupts: Any) -> str:
    if not interrupts:
        return "Yes / no (+ notes if useful)."
    seq = interrupts if isinstance(interrupts, (list, tuple)) else (interrupts,)
    if not seq:
        return "Yes / no (+ notes if useful)."
    first = seq[0]
    val = getattr(first, "value", first)
    if isinstance(val, dict):
        phase = val.get("phase", "")
        prompt = val.get("prompt", "")
        if phase == "kickoff":
            spec = val.get("spec", "")
            return truncate(f"{prompt}\n\n{spec}", 3500)
        if phase == "acceptance":
            summ = val.get("summary", "")
            extra = val.get("spec_excerpt", "")
            return truncate(f"{prompt}\n\n{summ}\n\n{extra}", 3500)
        return truncate(json.dumps(val, indent=2, ensure_ascii=False), 3500)
    return truncate(str(val), 3500)


def looks_like_new_brief_while_awaiting_owner(text: str) -> bool:
    """Heuristic: user sent a product pitch while the bot waits for an Owner yes/no."""
    t = text.strip().lower()
    if len(t) < 32:
        return False
    if _looks_like_owner_vote(t):
        return False
    markers = (
        "feature",
        "wallet",
        "project",
        "implement",
        "create ",
        "build ",
        "add a",
        "we need",
        "i want",
        "i wanna",
        "can we",
    )
    if not any(m in t for m in markers):
        return False
    return len(t.split()) >= 4


def _looks_like_owner_vote(t: str) -> bool:
    """Treat as Owner decision — resume graph, not chit-chat."""
    if t in (
        "yes",
        "no",
        "y",
        "n",
        "ok",
        "okay",
        "yep",
        "nope",
        "nah",
        "sure",
        "approve",
        "approved",
        "reject",
        "rejected",
        "👍",
        "👎",
    ):
        return True
    if t.startswith(("yes ", "no ", "y ", "n ", "ok ", "approve", "reject")):
        return True
    if t.startswith(("yes,", "no,", "y,", "n,")):
        return True
    return False


def looks_like_meta_chat_while_awaiting_owner(text: str) -> bool:
    """Side chatter during Owner interrupt — do not pass as Command(resume=…).

    Any message with ``?`` is treated as a question (safer than resuming blindly). Other phrases are
    typical confusion / clarification without a vote.
    """
    t = text.strip().lower()
    if not t or _looks_like_owner_vote(t):
        return False
    if "?" in t:
        return True
    fragments = (
        "what is this",
        "what's this",
        "whats this",
        "going on",
        "dont understand",
        "don't understand",
        "confused",
        "explain",
        "help me",
        "no brain",
        "have no brain",
    )
    return any(f in t for f in fragments)


def looks_like_idle_workflow_brief(text: str) -> bool:
    """If True, message should start the LangGraph team loop. If False, use idle PM chat instead."""
    t = (text or "").strip()
    if not t:
        return False
    low = t.lower()
    words = t.split()
    n = len(words)
    if low.startswith(("new project:", "new project :")):
        return True
    if len(t) >= 200:
        return True
    if n >= 26:
        return True
    if low.startswith("add ") and n >= 3:
        return True
    if low.startswith("fix ") and n >= 2:
        return True
    if low.startswith(("build ", "create ", "implement ")) and n >= 3:
        return True
    signals = (
        "implement",
        "ship by",
        "ship this",
        " launch",
        "launch ",
        "user story",
        "acceptance crit",
        "we need to",
        "please add",
        "add a ",
        "add the ",
        "add support",
        "build a ",
        "build the ",
        "create a ",
        "create the ",
        "new feature",
        "feature:",
        "bug:",
        " fix the",
        "fix:",
        "integrate ",
        "endpoint ",
        "migration",
        "deadline",
        " sprint",
        "milestone",
        "can we add",
        "can we ship",
        "can we build",
        "i want a ",
        "i want the ",
        "i need ",
        "rollout",
        "roll out",
    )
    if any(s in low for s in signals):
        return True
    if n >= 10 and any(s in low for s in ("requirements", "specification", "acceptance", "proposal for")):
        return True
    return False


def idle_pm_chat_fallback() -> str:
    """Template when DeepSeek is off — still offer context + how to start a run."""
    from black_company.company_context import company_context_for_llm

    ctx = company_context_for_llm().strip()
    return (
        f"{ctx}\n\n"
        "I’m in **chat mode** here (no LLM). For a full PM→Owner→Eng run, send a concrete brief, "
        "prefix **New project:** …, or use **/run**. Other: **growth**, **/reset**, **/help**."
    )


def owner_gate_sidebar_fallback(_user_message: str, _spec: str, status: str | None) -> str:
    """Compact PM line when LLM is off / failed."""
    from black_company.company_context import company_context_for_llm

    ctx = company_context_for_llm().replace("\n", " ").strip()
    if len(ctx) > 200:
        ctx = ctx[:197] + "…"
    if status == "awaiting_owner_acceptance":
        return f"Still on the ship call above — {ctx}"
    return f"Still on kickoff above — {ctx}"


def help_text() -> str:
    return (
        "**How this chat maps to the workflow**\n"
        "• **Hi / hey** — quick wave, no workflow.\n"
        "• Most other lines → **PM chat** (planning, context, how this works) without starting a run.\n"
        "• A **concrete brief**, **/run**, or **New project:** … → PM+Owner+Eng workflow on this thread.\n"
        "• When you see an **Owner** question, the next line is read as **yes / no + notes** "
        "(chit-chat is treated separately when we can tell).\n"
        "• **/reset** — new LangGraph thread; describe what to build next.\n"
        "• **New project:** … — explicit new brief.\n"
        "• **growth** / **milestones** — what the team stored from past runs.\n\n"
        "**Org copy for the PM** — set in `.env`:\n"
        "`BLACK_COMPANY_NAME`, `BLACK_COMPANY_BLURB`, `BLACK_COMPANY_PROJECTS`"
    )


def is_growth_lookup(text: str) -> bool:
    t = text.strip().lower()
    if not t:
        return False
    if t in {
        "growth",
        "milestones",
        "memory",
        "stats",
        "what did we learn",
        "learnings",
    }:
        return True
    if t.startswith("show growth") or t.startswith("show milestones"):
        return True
    return False


def strip_new_project_prefix(text: str) -> str:
    """If user uses `New project: ...`, return the body as the spec."""
    t = text.strip()
    low = t.lower()
    for prefix in ("new project:", "new project :"):
        if low.startswith(prefix):
            return t[len(prefix) :].strip()
    return t
