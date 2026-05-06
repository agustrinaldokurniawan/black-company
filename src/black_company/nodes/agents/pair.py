"""Pair programming stub (single node; split into driver/reviewer nodes later)."""

from __future__ import annotations

from black_company.state import PairTurn, TeamState
from black_company.voice import pair_session_update


def pair_programming(state: TeamState) -> dict:
    drove: PairTurn = state.get("pair_turn") or "dev1_drives"
    rounds = int(state.get("pair_round") or 0) + 1
    turn: PairTurn = "dev2_drives" if drove == "dev1_drives" else "dev1_drives"
    review_feedback, impl = pair_session_update(rounds, drove)
    return {
        "pair_round": rounds,
        "pair_turn": turn,
        "review_feedback": review_feedback,
        "impl": impl,
    }
