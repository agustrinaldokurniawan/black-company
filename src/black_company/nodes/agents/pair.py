"""Pair programming stub (single node; split into driver/reviewer nodes later)."""

from __future__ import annotations

from black_company.state import PairTurn, TeamState


def pair_programming(state: TeamState) -> dict:
    rounds = int(state.get("pair_round") or 0) + 1
    turn: PairTurn = "dev2_drives" if state.get("pair_turn") == "dev1_drives" else "dev1_drives"
    return {
        "pair_round": rounds,
        "pair_turn": turn,
        "review_feedback": f"[stub] review after round {rounds}",
        "impl": f"[stub] implementation through pair round {rounds} (turn={turn})",
    }
