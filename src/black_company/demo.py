"""Run workflow end-to-end; auto-resume Owner interrupts (for non-interactive demo)."""

from __future__ import annotations

import json

from langgraph.types import Command

from black_company.graph import build_graph


def main() -> None:
    app = build_graph()
    thread = {"configurable": {"thread_id": "demo-1"}}
    inp: dict | Command = {}
    while True:
        out = app.invoke(inp, thread)
        if out.get("__interrupt__"):
            inp = Command(resume="yes")
            continue
        break
    preview = {k: out[k] for k in sorted(out) if not str(k).startswith("_") and k != "messages"}
    print(json.dumps(preview, indent=2, default=str))


if __name__ == "__main__":
    main()
