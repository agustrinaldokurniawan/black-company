"""Specialist node callables — registry drives `graph/builder.py` (DRY wiring)."""

from __future__ import annotations

from typing import Callable, Final

from black_company.constants import NodeId
from black_company.nodes.agents import designer, owner, pair, qa, user
from black_company.state import TeamState

BLACK_TEAM_NODE = Callable[[TeamState], dict]

SPECIALIST_FUNCS: Final[dict[str, BLACK_TEAM_NODE]] = {
    NodeId.USER_PLANNING: user.user_planning,
    NodeId.OWNER_KICKOFF: owner.owner_kickoff,
    NodeId.DESIGNER: designer.designer,
    NodeId.PAIR_PROGRAMMING: pair.pair_programming,
    NodeId.QA: qa.qa,
    NodeId.USER_SHIP: user.user_ship,
    NodeId.OWNER_ACCEPT: owner.owner_accept,
}

__all__ = ["BLACK_TEAM_NODE", "SPECIALIST_FUNCS"]
