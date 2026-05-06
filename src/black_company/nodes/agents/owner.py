"""Owner human-in-the-loop stubs (replace with interrupt + resume)."""

from __future__ import annotations

from black_company.state import TeamState


def owner_kickoff(_state: TeamState) -> dict:
    return {
        "owner_kickoff": "approved",
        "owner_notes": "[stub] Owner approved kickoff via PM.",
    }


def owner_accept(_state: TeamState) -> dict:
    return {
        "owner_acceptance": "ok",
        "owner_notes": "[stub] Owner accepted delivery via PM.",
    }
