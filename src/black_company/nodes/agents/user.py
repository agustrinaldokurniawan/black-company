"""User agent (planning + ship check)."""

from __future__ import annotations

import os

from black_company.config import MAX_PLANNING_LOOPS
from black_company.growth.store import record_lesson
from black_company.state import TeamState

SHIP_STUB_ENV = "BLACK_COMPANY_USER_SHIP_STUB"


def user_planning(state: TeamState) -> dict:
    n = int(state.get("planning_iterations") or 0) + 1
    satisfied = n >= MAX_PLANNING_LOOPS
    return {
        "planning_iterations": n,
        "user_agent_spec": "satisfied" if satisfied else "iterating",
        "user_agent_notes": f"[stub user agent] planning pass {n}",
    }


def user_ship(state: TeamState) -> dict:
    mode = os.environ.get(SHIP_STUB_ENV, "ok").strip().lower()
    if mode == "concerns":
        ship = "concerns"
        notes = "[stub user agent] ship check: concerns (BLACK_COMPANY_USER_SHIP_STUB=concerns)"
    else:
        ship = "ok"
        notes = "[stub user agent] ship check ok vs pm_readiness_summary"
    # Replace stub branch above with LLM parsing; keep this block for any "concerns" outcome.
    if ship == "concerns":
        record_lesson(
            trigger="user_ship_concerns",
            detail={
                "pm_readiness_summary": (state.get("pm_readiness_summary") or "")[:1200],
                "user_agent_notes": notes,
            },
        )
    return {"user_agent_ship": ship, "user_agent_notes": notes}
