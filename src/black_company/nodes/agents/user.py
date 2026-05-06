"""User agent (planning + ship check)."""

from __future__ import annotations

import os

from black_company.config import MAX_PLANNING_LOOPS
from black_company.growth.store import record_lesson
from black_company.llm.deepseek_copy import try_user_planning_notes, try_user_ship_notes
from black_company.state import TeamState
from black_company.voice import (
    user_planning_notes,
    user_ship_concerns_notes,
    user_ship_ok_notes,
)

SHIP_STUB_ENV = "BLACK_COMPANY_USER_SHIP_STUB"


def user_planning(state: TeamState) -> dict:
    n = int(state.get("planning_iterations") or 0) + 1
    satisfied = n >= MAX_PLANNING_LOOPS
    notes = try_user_planning_notes(n, satisfied, state) or user_planning_notes(n, satisfied)
    return {
        "planning_iterations": n,
        "user_agent_spec": "satisfied" if satisfied else "iterating",
        "user_agent_notes": notes,
    }


def user_ship(state: TeamState) -> dict:
    mode = os.environ.get(SHIP_STUB_ENV, "ok").strip().lower()
    if mode == "concerns":
        ship = "concerns"
        notes = try_user_ship_notes("concerns", state) or user_ship_concerns_notes()
    else:
        ship = "ok"
        notes = try_user_ship_notes("ok", state) or user_ship_ok_notes()
    # When wiring a real agent, set ship/notes from the model; keep record_lesson on concerns.
    if ship == "concerns":
        record_lesson(
            trigger="user_ship_concerns",
            detail={
                "pm_readiness_summary": (state.get("pm_readiness_summary") or "")[:1200],
                "user_agent_notes": notes,
            },
        )
    return {"user_agent_ship": ship, "user_agent_notes": notes}
