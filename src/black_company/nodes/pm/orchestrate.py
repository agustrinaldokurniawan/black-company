"""PM hub: dispatch by `status` to small phase handlers (easy to add/remove phases)."""

from __future__ import annotations

from black_company.constants import NEXT_END, Status
from black_company.nodes.pm.phases import ALL_HANDLERS
from black_company.state import TeamState


def pm_orchestrate(state: TeamState) -> dict:
    st = state.get("status", Status.INIT)
    handler = ALL_HANDLERS.get(st)
    if handler is not None:
        return handler(state)
    return {"status": Status.DONE, "_next": NEXT_END}
