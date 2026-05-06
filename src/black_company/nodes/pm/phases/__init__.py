"""Aggregate PM phase handler maps."""

from __future__ import annotations

from black_company.nodes.pm.phases import delivery, planning, ship

ALL_HANDLERS = {**planning.HANDLERS, **delivery.HANDLERS, **ship.HANDLERS}
