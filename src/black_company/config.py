"""Tunable workflow limits (stubs + simulation). Replace with real policy later."""

from __future__ import annotations

from typing import Final

from black_company.voice import default_project_brief

MAX_PLANNING_LOOPS: Final = 2
MAX_PAIR_ROUNDS: Final = 2

DEFAULT_STUB_SPEC: Final = default_project_brief()
