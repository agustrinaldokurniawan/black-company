"""Discover existing repos under ``BLACK_COMPANY_PROJECT_ROOT`` for PM / LLM context."""

from __future__ import annotations

import html
import json
import os
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Final

_MAX_PROJECTS: Final = 48
_HINT_LEN: Final = 140
# Telegram /projects list: longer excerpt than LLM context above.
_TELEGRAM_HINT_MAX: Final = 420
_TELEGRAM_HTML_MAX: Final = 4050


def _plain_hint_for_display(s: str) -> str:
    """README often uses **foo**; Telegram HTML uses <b> instead."""
    t = re.sub(r"\*\*([^*]+)\*\*", r"\1", s)
    t = re.sub(r"`([^`]+)`", r"\1", t)
    t = re.sub(r"\*+", "", t)
    return t.strip()


@dataclass(frozen=True)
class WorkspaceProject:
    name: str
    has_git: bool
    hint: str


def workspace_root_from_env() -> Path | None:
    raw = os.environ.get("BLACK_COMPANY_PROJECT_ROOT", "").strip()
    if not raw:
        return None
    p = Path(raw).expanduser().resolve()
    if not p.is_dir():
        return None
    return p


def _first_readme_line(project: Path, *, max_chars: int = _HINT_LEN) -> str:
    for fname in ("README.md", "README.MD", "readme.md", "README"):
        rp = project / fname
        if not rp.is_file():
            continue
        try:
            text = rp.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line in text.splitlines():
            s = line.strip()
            if s and not s.startswith(("#", "<!--", "---", "=")):
                s = re.sub(r"^#+\s*", "", s)
                return s[:max_chars] + ("…" if len(s) > max_chars else "")
    return ""


def _pyproject_name(project: Path, *, max_chars: int = _HINT_LEN) -> str:
    pp = project / "pyproject.toml"
    if not pp.is_file():
        return ""
    try:
        data = tomllib.loads(pp.read_text(encoding="utf-8", errors="replace"))
    except (OSError, UnicodeError, ValueError):
        return ""
    proj = data.get("project")
    if isinstance(proj, dict):
        n = proj.get("name")
        if isinstance(n, str) and n.strip():
            return n.strip()[:max_chars]
    return ""


def _package_json_name(project: Path, *, max_chars: int = _HINT_LEN) -> str:
    pj = project / "package.json"
    if not pj.is_file():
        return ""
    try:
        data = json.loads(pj.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return ""
    n = data.get("name")
    return str(n).strip()[:max_chars] if isinstance(n, str) and str(n).strip() else ""


def _hint_for_project(project: Path, *, max_readme_chars: int = _HINT_LEN) -> str:
    h = _first_readme_line(project, max_chars=max_readme_chars)
    if h:
        return h
    h = _pyproject_name(project, max_chars=max_readme_chars)
    if h:
        return h
    return _package_json_name(project, max_chars=max_readme_chars)


def scan_workspace_projects(
    *, max_projects: int = _MAX_PROJECTS, hint_max_chars: int = _HINT_LEN
) -> list[WorkspaceProject]:
    root = workspace_root_from_env()
    if root is None:
        return []
    out: list[WorkspaceProject] = []
    try:
        kids = [p for p in root.iterdir() if p.is_dir() and not p.name.startswith(".")]
    except OSError:
        return []
    kids.sort(key=lambda p: p.name.lower())
    for child in kids:
        if len(out) >= max_projects:
            break
        has_git = (child / ".git").exists()
        hint = _hint_for_project(child, max_readme_chars=hint_max_chars)
        out.append(WorkspaceProject(name=child.name, has_git=has_git, hint=hint))
    return out


def workspace_block_for_llm() -> str:
    root = workspace_root_from_env()
    if root is None:
        return ""
    projects = scan_workspace_projects()
    root_display = str(root)
    if not projects:
        return (
            f"Workspace folder (BLACK_COMPANY_PROJECT_ROOT): {root_display}\n"
            "No immediate subfolders found — add project directories here so the PM can see them."
        )
    lines = [
        f"Workspace folder (BLACK_COMPANY_PROJECT_ROOT): {root_display}",
        "Existing project folders (read these first when prioritizing work):",
    ]
    for p in projects:
        git = " git" if p.has_git else ""
        if p.hint:
            lines.append(f"• {p.name}{git} — {p.hint}")
        else:
            lines.append(f"• {p.name}{git}")
    return "\n".join(lines)


def _projects_list_html(root_s: str, projects: list[WorkspaceProject]) -> str:
    lines: list[str] = [f"<b>Workspace:</b> <code>{root_s}</code>", ""]
    if not projects:
        lines.append("<i>No immediate subfolders — clone or add repos under this path.</i>")
        return "\n".join(lines)
    lines.append("<b>Projects on disk:</b>")
    for p in projects:
        git = " <i>(git)</i>" if p.has_git else ""
        name_e = html.escape(p.name)
        if p.hint:
            plain = _plain_hint_for_display(p.hint)
            hint_e = html.escape(plain)
            lines.append(f"• <b>{name_e}</b>{git} — {hint_e}")
        else:
            lines.append(f"• <b>{name_e}</b>{git}")
    return "\n".join(lines)


def format_projects_command_message() -> str:
    """HTML for Telegram (use with ``parse_mode=ParseMode.HTML``)."""
    root = workspace_root_from_env()
    if root is None:
        return (
            "No workspace root set. Define <b>BLACK_COMPANY_PROJECT_ROOT</b> in <code>.env</code> "
            "(local path or e.g. <code>/projects</code> in Docker with a volume mount)."
        )
    root_s = html.escape(str(root))
    for cap in (_TELEGRAM_HINT_MAX, 300, 200, 140, 100):
        projects = scan_workspace_projects(hint_max_chars=cap)
        body = _projects_list_html(root_s, projects)
        if len(body) <= _TELEGRAM_HTML_MAX:
            return body
    # Still long: drop hints, then fewer rows
    projects = scan_workspace_projects(hint_max_chars=100)
    slim = [WorkspaceProject(name=p.name, has_git=p.has_git, hint="") for p in projects]
    body = _projects_list_html(root_s, slim)
    if len(body) <= _TELEGRAM_HTML_MAX:
        return body
    while len(slim) > 1:
        slim = slim[:-1]
        body = _projects_list_html(root_s, slim)
        if len(body) <= _TELEGRAM_HTML_MAX:
            note = "\n\n<i>…and more projects not shown.</i>"
            combo = body + note
            if len(combo) <= _TELEGRAM_HTML_MAX:
                return combo
            return body
    return body[: _TELEGRAM_HTML_MAX - 1] + "…"
