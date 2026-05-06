"""Pair programming stub (single node; split into driver/reviewer nodes later)."""

from __future__ import annotations

from black_company.llm.deepseek_copy import try_pair_impl, try_pair_review
from black_company.state import PairTurn, TeamState
from black_company.voice import pair_session_update


def pair_programming(state: TeamState) -> dict:
    drove: PairTurn = state.get("pair_turn") or "dev1_drives"
    rounds = int(state.get("pair_round") or 0) + 1
    turn: PairTurn = "dev2_drives" if drove == "dev1_drives" else "dev1_drives"
    r_llm = try_pair_review(rounds, drove, state)
    i_llm = try_pair_impl(rounds, drove, state)
    if r_llm and i_llm:
        review_feedback, impl = r_llm, i_llm
    else:
        review_feedback, impl = pair_session_update(rounds, drove)
    return {
        "pair_round": rounds,
        "pair_turn": turn,
        "review_feedback": review_feedback,
        "impl": impl,
    }
