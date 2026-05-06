"""Shared graph state (aligned with docs/langgraph-team-sketch.md)."""

from __future__ import annotations

from typing import Literal, NotRequired

from typing_extensions import TypedDict


OwnerKickoff = Literal["pending", "approved", "needs_pm_revision"]
OwnerAcceptance = Literal["pending", "ok", "needs_rework"]
UserAgentSpec = Literal["iterating", "satisfied"]
UserAgentShip = Literal["pending", "ok", "concerns"]
QAResult = Literal["pending", "pass", "fail"]
PairTurn = Literal["dev1_drives", "dev2_drives"]


class TeamState(TypedDict, total=False):
    """Single state object for the team graph."""

    status: str
    _next: str

    spec: str
    design: str
    impl: str
    pair_turn: PairTurn
    pair_round: int
    review_feedback: str

    qa_report: str
    qa_result: QAResult

    pm_readiness_summary: str
    user_agent_notes: str
    user_agent_spec: UserAgentSpec
    user_agent_ship: UserAgentShip

    owner_kickoff: OwnerKickoff
    owner_acceptance: OwnerAcceptance
    owner_notes: str
    owner_decision: NotRequired[str]

    planning_iterations: int

    assignee_hints: str
    pm_owner_thread: str
