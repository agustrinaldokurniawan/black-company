"""QA agent stub."""

from __future__ import annotations

from black_company.config import MAX_PAIR_ROUNDS
from black_company.state import TeamState


def qa(state: TeamState) -> dict:
    rounds = int(state.get("pair_round") or 0)
    ok = rounds >= MAX_PAIR_ROUNDS
    return {
        "qa_report": "[stub] Automated checks run.",
        "qa_result": "pass" if ok else "fail",
    }
