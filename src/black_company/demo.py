"""Run workflow end-to-end; auto-resume Owner interrupts (for non-interactive demo)."""

from __future__ import annotations

import json

from langgraph.types import Command

from black_company.graph import build_graph
from black_company.growth import record_event


def main() -> None:
    record_event(kind="run_started", source="demo", detail={"mode": "auto_approve"})
    app = build_graph()
    thread = {"configurable": {"thread_id": "demo-1"}}
    inp: dict | Command = {}
    while True:
        out = app.invoke(inp, thread)
        if out.get("__interrupt__"):
            record_event(
                kind="owner_interrupt",
                source="demo",
                thread_id="demo-1",
                detail={"auto": True},
            )
            inp = Command(resume="yes")
            continue
        break
    record_event(
        kind="run_completed",
        source="demo",
        thread_id="demo-1",
        detail={
            "status": out.get("status"),
            "qa_result": out.get("qa_result"),
            "pair_round": out.get("pair_round"),
        },
    )
    preview = {k: out[k] for k in sorted(out) if not str(k).startswith("_") and k != "messages"}
    print(json.dumps(preview, indent=2, default=str))


if __name__ == "__main__":
    main()
