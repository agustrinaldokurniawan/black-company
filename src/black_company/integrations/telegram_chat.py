"""Natural-language replies for Telegram (PM voice, no raw JSON)."""

from __future__ import annotations

import json
from typing import Any


def truncate(s: str, n: int = 3500) -> str:
    s = s.strip()
    return s if len(s) <= n else s[: n - 20] + "\n…(truncated)"


def pm_intro_after_request(user_message: str) -> str:
    excerpt = truncate(user_message, 600)
    return (
        "Hey — I’m on it.\n\n"
        f"I’ve pulled this into our working brief:\n“{excerpt}”\n\n"
        "I’m taking it through Product planning next; you’ll see Owner kickoff when the brief is tight enough."
    )


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
        return "Reply with whatever you’d say in a real meeting (yes / no / notes)."
    seq = interrupts if isinstance(interrupts, (list, tuple)) else (interrupts,)
    if not seq:
        return "Reply with whatever you’d say in a real meeting (yes / no / notes)."
    first = seq[0]
    val = getattr(first, "value", first)
    if isinstance(val, dict):
        phase = val.get("phase", "")
        prompt = val.get("prompt", "")
        if phase == "kickoff":
            spec = val.get("spec", "")
            return truncate(
                f"{prompt}\n\n--- Brief we’re asking you to approve ---\n{spec}",
                3500,
            )
        if phase == "acceptance":
            summ = val.get("summary", "")
            extra = val.get("spec_excerpt", "")
            return truncate(
                f"{prompt}\n\n--- Readiness ---\n{summ}\n\n--- Spec (excerpt) ---\n{extra}",
                3500,
            )
        return truncate(json.dumps(val, indent=2, ensure_ascii=False), 3500)
    return truncate(str(val), 3500)


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
