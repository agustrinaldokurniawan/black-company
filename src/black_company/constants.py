"""Single source of truth for workflow strings (status + graph node ids)."""

from __future__ import annotations

from typing import Final


class Status:
    INIT: Final = "init"
    PM_USER_LOOP: Final = "pm_user_loop"
    AWAITING_OWNER_KICKOFF: Final = "awaiting_owner_kickoff"
    DESIGNING: Final = "designing"
    BUILDING: Final = "building"
    QA_PENDING: Final = "qa_pending"
    PM_USER_SHIP_CHECK: Final = "pm_user_ship_check"
    AWAITING_OWNER_ACCEPTANCE: Final = "awaiting_owner_acceptance"
    DONE: Final = "done"


class NodeId:
    PM: Final = "pm"
    USER_PLANNING: Final = "user_planning"
    OWNER_KICKOFF: Final = "owner_kickoff"
    DESIGNER: Final = "designer"
    PAIR_PROGRAMMING: Final = "pair_programming"
    QA: Final = "qa"
    USER_SHIP: Final = "user_ship"
    OWNER_ACCEPT: Final = "owner_accept"


NEXT_END: Final = "__end__"

# PM routes to these nodes (hub-and-spoke). Keep in lockstep with NodeId specialists.
SPECIALIST_NODES: tuple[str, ...] = (
    NodeId.USER_PLANNING,
    NodeId.OWNER_KICKOFF,
    NodeId.DESIGNER,
    NodeId.PAIR_PROGRAMMING,
    NodeId.QA,
    NodeId.USER_SHIP,
    NodeId.OWNER_ACCEPT,
)
