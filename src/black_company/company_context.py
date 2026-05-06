"""Org / product background for LLM prompts and Telegram (from env)."""

from __future__ import annotations

import os


def company_context_for_llm() -> str:
    """Short block injected into PM prompts; empty env → sensible default."""
    name = os.environ.get("BLACK_COMPANY_NAME", "").strip()
    blurb = os.environ.get("BLACK_COMPANY_BLURB", "").strip()
    projects = os.environ.get("BLACK_COMPANY_PROJECTS", "").strip()
    lines: list[str] = []
    if name:
        lines.append(name)
    if blurb:
        lines.append(blurb)
    if projects:
        lines.append(f"Active work: {projects}")
    if not lines:
        return (
            "We’re the internal PM-hub / LangGraph crew shipping workflow demos "
            "(set BLACK_COMPANY_NAME, BLACK_COMPANY_BLURB, BLACK_COMPANY_PROJECTS in .env to personalize)."
        )
    return "\n".join(lines)
