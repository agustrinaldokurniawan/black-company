"""PM phases: User ship check + Owner acceptance."""

from __future__ import annotations

from black_company.constants import NEXT_END, NodeId, Status
from black_company.nodes.pm.types import PhaseHandler
from black_company.state import TeamState


def handle_pm_user_ship_check(state: TeamState) -> dict:
    if state.get("user_agent_ship") == "concerns":
        return {"status": Status.BUILDING, "_next": NodeId.PAIR_PROGRAMMING}
    if state.get("user_agent_ship") == "ok":
        return {
            "status": Status.AWAITING_OWNER_ACCEPTANCE,
            "owner_acceptance": "pending",
            "_next": NodeId.OWNER_ACCEPT,
        }
    return {"_next": NodeId.USER_SHIP}


def handle_awaiting_owner_acceptance(state: TeamState) -> dict:
    if state.get("owner_acceptance") == "ok":
        return {"status": Status.DONE, "_next": NEXT_END}
    if state.get("owner_acceptance") == "needs_rework":
        return {"status": Status.DESIGNING, "_next": NodeId.DESIGNER}
    return {"_next": NodeId.OWNER_ACCEPT}


def handle_done(_state: TeamState) -> dict:
    return {"status": Status.DONE, "_next": NEXT_END}


HANDLERS: dict[str, PhaseHandler] = {
    Status.PM_USER_SHIP_CHECK: handle_pm_user_ship_check,
    Status.AWAITING_OWNER_ACCEPTANCE: handle_awaiting_owner_acceptance,
    Status.DONE: handle_done,
}
