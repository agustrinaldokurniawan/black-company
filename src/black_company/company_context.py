"""Org / product background for LLM prompts and Telegram (from env)."""

from __future__ import annotations

import os

from black_company.workspace_projects import workspace_block_for_llm


def company_context_for_llm() -> str:
    """Short block injected into PM prompts; empty env → sensible default."""
    lines: list[str] = []
    ws = workspace_block_for_llm().strip()
    if ws:
        lines.append(ws)
    name = os.environ.get("BLACK_COMPANY_NAME", "").strip()
    blurb = os.environ.get("BLACK_COMPANY_BLURB", "").strip()
    projects = os.environ.get("BLACK_COMPANY_PROJECTS", "").strip()
    if name:
        lines.append(name)
    if blurb:
        lines.append(blurb)
    if projects:
        lines.append(f"Additional tracks (env): {projects}")
    if not lines:
        return (
            "We’re the internal PM-hub / LangGraph crew shipping workflow demos "
            "(set BLACK_COMPANY_PROJECT_ROOT to point at a folder of existing repos, plus optional "
            "BLACK_COMPANY_NAME, BLACK_COMPANY_BLURB, BLACK_COMPANY_PROJECTS in .env to personalize)."
        )
    return "\n".join(lines)
