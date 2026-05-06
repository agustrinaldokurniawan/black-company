"""PM phases: Owner approves brief first, then spec refinement (Product↔PM), then build."""

from __future__ import annotations

from black_company.config import DEFAULT_STUB_SPEC
from black_company.constants import NodeId, Status
from black_company.nodes.pm.types import PhaseHandler
from black_company.state import TeamState


def handle_init(state: TeamState) -> dict:
    return {
        "spec": state.get("spec") or DEFAULT_STUB_SPEC,
        "status": Status.AWAITING_OWNER_KICKOFF,
        "owner_kickoff": "pending",
        "planning_iterations": 0,
        "_next": NodeId.OWNER_KICKOFF,
    }


def handle_pm_user_loop(state: TeamState) -> dict:
    if state.get("user_agent_spec") != "satisfied":
        return {"_next": NodeId.USER_PLANNING}
    # Owner already approved the initial brief before planning; after Product↔PM loop, start build.
    if state.get("owner_kickoff") == "approved":
        return {"status": Status.DESIGNING, "_next": NodeId.DESIGNER}
    # Owner asked for revision: planning is done again → now they must re-approve before eng.
    return {
        "status": Status.AWAITING_OWNER_KICKOFF,
        "owner_kickoff": "pending",
        "_next": NodeId.OWNER_KICKOFF,
    }


def handle_awaiting_owner_kickoff(state: TeamState) -> dict:
    ok = state.get("owner_kickoff")
    if ok == "needs_pm_revision":
        return {
            "status": Status.PM_USER_LOOP,
            "user_agent_spec": "iterating",
            "planning_iterations": 0,
            "owner_kickoff": "pending",
            "_next": NodeId.USER_PLANNING,
        }
    if ok != "approved":
        return {"_next": NodeId.OWNER_KICKOFF}
    return {
        "status": Status.PM_USER_LOOP,
        "user_agent_spec": "iterating",
        "_next": NodeId.USER_PLANNING,
    }


HANDLERS: dict[str, PhaseHandler] = {
    Status.INIT: handle_init,
    Status.PM_USER_LOOP: handle_pm_user_loop,
    Status.AWAITING_OWNER_KICKOFF: handle_awaiting_owner_kickoff,
}
