"""Designer agent stub."""

from __future__ import annotations

from black_company.state import TeamState
from black_company.voice import designer_handoff


def designer(state: TeamState) -> dict:
    return {"design": designer_handoff(state)}
