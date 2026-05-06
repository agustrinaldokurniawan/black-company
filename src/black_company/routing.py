"""Conditional routing from the PM hub node."""

from __future__ import annotations

from langgraph.graph import END

from black_company.constants import NEXT_END, SPECIALIST_NODES
from black_company.state import TeamState


def route_from_pm(state: TeamState) -> str:
    nxt = state.get("_next", NEXT_END)
    if nxt == NEXT_END:
        return END
    if nxt not in SPECIALIST_NODES:
        return END
    return nxt
