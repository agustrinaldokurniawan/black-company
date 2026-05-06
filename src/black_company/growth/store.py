"""Append-only growth memory — milestones across runs (SQLite on disk)."""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_lock = threading.Lock()
_INIT = False

_SCHEMA = """
CREATE TABLE IF NOT EXISTS growth_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    source TEXT NOT NULL,
    actor TEXT,
    chat_id TEXT,
    thread_id TEXT,
    kind TEXT NOT NULL,
    detail TEXT
);
CREATE INDEX IF NOT EXISTS idx_growth_created ON growth_events (created_at);
CREATE INDEX IF NOT EXISTS idx_growth_kind ON growth_events (kind);
"""


def data_dir() -> Path:
    raw = os.environ.get("BLACK_COMPANY_DATA_DIR", "").strip()
    base = Path(raw).resolve() if raw else (Path.cwd() / "data").resolve()
    base.mkdir(parents=True, exist_ok=True)
    return base


def db_path() -> Path:
    return data_dir() / "growth.sqlite"


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(_SCHEMA)


def init_db() -> None:
    global _INIT
    with _lock:
        if _INIT:
            return
        conn = sqlite3.connect(db_path(), check_same_thread=False)
        try:
            _ensure_schema(conn)
            conn.commit()
        finally:
            conn.close()
        _INIT = True


def record_event(
    *,
    kind: str,
    source: str,
    detail: dict[str, Any] | None = None,
    actor: str | None = None,
    chat_id: str | None = None,
    thread_id: str | None = None,
) -> None:
    """Record one milestone (thread-safe)."""
    init_db()
    created = datetime.now(timezone.utc).isoformat()
    payload = json.dumps(detail, ensure_ascii=False, default=str) if detail else None
    with _lock:
        conn = sqlite3.connect(db_path(), check_same_thread=False)
        try:
            conn.execute(
                "INSERT INTO growth_events (created_at, source, actor, chat_id, thread_id, kind, detail) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (created, source, actor, chat_id, thread_id, kind, payload),
            )
            conn.commit()
        finally:
            conn.close()


def recent_events(*, limit: int = 15) -> list[dict[str, Any]]:
    init_db()
    with _lock:
        conn = sqlite3.connect(db_path(), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            cur = conn.execute(
                "SELECT id, created_at, source, actor, chat_id, thread_id, kind, detail "
                "FROM growth_events ORDER BY id DESC LIMIT ?",
                (limit,),
            )
            rows = [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()
    for r in rows:
        if r.get("detail"):
            try:
                r["detail"] = json.loads(r["detail"])
            except json.JSONDecodeError:
                pass
    return rows


def recent_lessons(*, limit: int = 20) -> list[dict[str, Any]]:
    init_db()
    with _lock:
        conn = sqlite3.connect(db_path(), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            cur = conn.execute(
                "SELECT id, created_at, source, actor, chat_id, thread_id, kind, detail "
                "FROM growth_events WHERE kind = ? ORDER BY id DESC LIMIT ?",
                ("lesson_learned", limit),
            )
            rows = [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()
    for r in rows:
        if r.get("detail"):
            try:
                r["detail"] = json.loads(r["detail"])
            except json.JSONDecodeError:
                pass
    return rows


def record_lesson(
    *,
    trigger: str,
    source: str = "graph",
    detail: dict[str, Any] | None = None,
    thread_id: str | None = None,
) -> None:
    payload = {"trigger": trigger, **(detail or {})}
    record_event(kind="lesson_learned", source=source, detail=payload, thread_id=thread_id)


def growth_context_for_pm(*, lesson_limit: int = 8, max_chars: int = 3200) -> str:
    """Digest of recent lessons for LLM PM prompts (or readout in graph state)."""
    lessons = recent_lessons(limit=lesson_limit)
    if not lessons:
        return ""
    lines = [
        "Past lessons (QA, Owner rejections, user ship concerns — consider when planning):",
    ]
    for row in reversed(lessons):
        d = row.get("detail") if isinstance(row.get("detail"), dict) else {}
        trig = d.get("trigger", "?")
        ts = str(row.get("created_at", ""))[:10]
        body = {k: v for k, v in d.items() if k != "trigger"}
        snippet = json.dumps(body, ensure_ascii=False, default=str)
        if len(snippet) > 450:
            snippet = snippet[:430] + "…"
        lines.append(f"- [{ts}] {trig}: {snippet}")
    text = "\n".join(lines)
    if len(text) > max_chars:
        return text[: max_chars - 20] + "\n…(truncated)"
    return text


def stats() -> dict[str, Any]:
    init_db()
    with _lock:
        conn = sqlite3.connect(db_path(), check_same_thread=False)
        try:
            total = conn.execute("SELECT COUNT(*) FROM growth_events").fetchone()[0]
            by_kind = dict(
                conn.execute(
                    "SELECT kind, COUNT(*) FROM growth_events GROUP BY kind ORDER BY COUNT(*) DESC"
                ).fetchall()
            )
            row = conn.execute("SELECT MIN(created_at), MAX(created_at) FROM growth_events").fetchone()
        finally:
            conn.close()
    return {
        "total_events": total,
        "by_kind": by_kind,
        "first_milestone_utc": row[0],
        "last_milestone_utc": row[1],
    }


def format_report(*, limit: int = 12) -> str:
    """Human-readable recap for Telegram or CLI."""
    st = stats()
    if st["total_events"] == 0:
        return "No milestones yet. Run /run to start growing."
    lines = [
        f"Growth memory: {st['total_events']} events (since {st['first_milestone_utc'][:10]}).",
        f"Last activity: {st['last_milestone_utc'][:19]}Z.",
        "",
        "By kind:",
    ]
    for k, n in list(st["by_kind"].items())[:8]:
        lines.append(f"  • {k}: {n}")
    lines.append("")
    lines.append("Recent:")
    for ev in reversed(recent_events(limit=limit)):
        ts = ev.get("created_at", "")[:19]
        k = ev.get("kind", "?")
        src = ev.get("source", "")
        lines.append(f"  [{ts}Z] {k} ({src})")
    return "\n".join(lines)
