"""Owner human-in-the-loop (LangGraph interrupt — resume via Telegram, CLI, etc.)."""

from __future__ import annotations

from typing import Any

from langgraph.types import interrupt

from black_company.growth.store import record_lesson
from black_company.state import TeamState


def _norm_reply(reply: Any) -> str:
    if isinstance(reply, dict):
        return str(reply.get("text", reply.get("message", reply)))
    return str(reply).strip()


def _is_yes(reply: Any) -> bool:
    s = _norm_reply(reply).lower()
    return s.startswith("y") or s in ("approve", "approved", "ok", "yes", "1", "👍")


def _is_no(reply: Any) -> bool:
    s = _norm_reply(reply).lower()
    return s in ("n", "no", "nope", "reject", "rejected", "0", "👎") or s.startswith(
        ("no ", "no,", "nope ")
    )


def owner_kickoff(state: TeamState) -> dict:
    spec = state.get("spec") or ""
    reply = interrupt(
        {
            "phase": "kickoff",
            "prompt": "Owner — Kickoff: approve this brief before we run Product planning and hand off to Engineering. Reply yes, or no with what to change.",
            "spec": spec,
        }
    )
    if _is_yes(reply):
        return {"owner_kickoff": "approved", "owner_notes": _norm_reply(reply)}
    record_lesson(
        trigger="owner_kickoff_reject",
        detail={"notes": _norm_reply(reply)[:2000], "spec_excerpt": spec[:600]},
    )
    return {"owner_kickoff": "needs_pm_revision", "owner_notes": _norm_reply(reply)}


def owner_accept(state: TeamState) -> dict:
    reply = interrupt(
        {
            "phase": "acceptance",
            "prompt": "Owner — Delivery review: accept this increment for release? Reply yes, or no with rework notes.",
            "summary": state.get("pm_readiness_summary") or "",
            "spec_excerpt": (state.get("spec") or "")[:800],
        }
    )
    if _is_yes(reply):
        return {"owner_acceptance": "ok", "owner_notes": _norm_reply(reply)}
    if _is_no(reply):
        record_lesson(
            trigger="owner_delivery_reject",
            detail={
                "notes": _norm_reply(reply)[:2000],
                "readiness": (state.get("pm_readiness_summary") or "")[:1200],
            },
        )
        return {"owner_acceptance": "needs_rework", "owner_notes": _norm_reply(reply)}
    # unclear — treat as rework
    record_lesson(
        trigger="owner_delivery_reject",
        detail={"notes": _norm_reply(reply)[:2000], "unclear_reply": True},
    )
    return {"owner_acceptance": "needs_rework", "owner_notes": _norm_reply(reply)}
