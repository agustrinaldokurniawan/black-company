"""User agent (planning + ship check)."""

from __future__ import annotations

from black_company.config import MAX_PLANNING_LOOPS
from black_company.state import TeamState


def user_planning(state: TeamState) -> dict:
    n = int(state.get("planning_iterations") or 0) + 1
    satisfied = n >= MAX_PLANNING_LOOPS
    return {
        "planning_iterations": n,
        "user_agent_spec": "satisfied" if satisfied else "iterating",
        "user_agent_notes": f"[stub user agent] planning pass {n}",
    }


def user_ship(_state: TeamState) -> dict:
    return {
        "user_agent_ship": "ok",
        "user_agent_notes": "[stub user agent] ship check ok vs pm_readiness_summary",
    }
