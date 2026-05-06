"""Shared PM phase handler type."""

from __future__ import annotations

from typing import Any, Callable

from black_company.state import TeamState

PhaseHandler = Callable[[TeamState], dict[str, Any]]

__all__ = ["PhaseHandler"]
