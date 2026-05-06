"""Designer agent stub."""

from __future__ import annotations

from black_company.llm.deepseek_copy import try_design_handoff
from black_company.state import TeamState
from black_company.voice import designer_handoff


def designer(state: TeamState) -> dict:
    text = try_design_handoff(state) or designer_handoff(state)
    return {"design": text}
