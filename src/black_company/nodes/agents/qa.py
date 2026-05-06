"""QA agent stub."""

from __future__ import annotations

from black_company.config import MAX_PAIR_ROUNDS
from black_company.llm.deepseek_copy import try_qa_report
from black_company.state import TeamState
from black_company.voice import qa_gate_report


def qa(state: TeamState) -> dict:
    rounds = int(state.get("pair_round") or 0)
    ok = rounds >= MAX_PAIR_ROUNDS
    report = try_qa_report(rounds, passing=ok, state=state) or qa_gate_report(rounds, passing=ok)
    return {
        "qa_report": report,
        "qa_result": "pass" if ok else "fail",
    }
