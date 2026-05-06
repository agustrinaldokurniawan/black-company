"""Run stub workflow end-to-end (no LLM, no Owner interrupt)."""

from __future__ import annotations

import json

from black_company.graph import build_graph


def main() -> None:
    app = build_graph()
    thread = {"configurable": {"thread_id": "demo-1"}}
    out = app.invoke({}, thread)
    # Print stable subset for quick sanity check
    preview = {k: out[k] for k in sorted(out) if not k.startswith("_") and k != "messages"}
    print(json.dumps(preview, indent=2, default=str))


if __name__ == "__main__":
    main()
