"""PM phases: design → pair → QA."""

from __future__ import annotations

from black_company.constants import NodeId, Status
from black_company.nodes.pm.types import PhaseHandler
from black_company.state import TeamState


def handle_designing(state: TeamState) -> dict:
    if not state.get("design"):
        return {"_next": NodeId.DESIGNER}
    return {"status": Status.BUILDING, "_next": NodeId.PAIR_PROGRAMMING}


def handle_building(state: TeamState) -> dict:
    if state.get("qa_result") == "fail":
        return {"_next": NodeId.PAIR_PROGRAMMING, "qa_result": "pending"}
    if not state.get("impl"):
        return {"_next": NodeId.PAIR_PROGRAMMING}
    return {"status": Status.QA_PENDING, "qa_result": "pending", "_next": NodeId.QA}


def handle_qa_pending(state: TeamState) -> dict:
    if state.get("qa_result") == "fail":
        return {
            "status": Status.BUILDING,
            "assignee_hints": "fix from QA",
            "qa_result": "pending",
            "_next": NodeId.PAIR_PROGRAMMING,
        }
    if state.get("qa_result") == "pass":
        return {
            "pm_readiness_summary": "[stub] QA pass; scope matches spec.",
            "status": Status.PM_USER_SHIP_CHECK,
            "user_agent_ship": "pending",
            "assignee_hints": "",
            "_next": NodeId.USER_SHIP,
        }
    return {"_next": NodeId.QA}


HANDLERS: dict[str, PhaseHandler] = {
    Status.DESIGNING: handle_designing,
    Status.BUILDING: handle_building,
    Status.QA_PENDING: handle_qa_pending,
}
