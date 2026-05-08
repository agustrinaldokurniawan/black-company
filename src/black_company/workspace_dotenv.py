"""Merge KEY=value pairs from chat into a workspace project's `.env` file."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Final

from html import escape

from black_company.workspace_run import workspace_project_dir

_MAX_KEYS: Final = 120
_MAX_VAL_LEN: Final = 16_384
_MAX_FILE: Final = 512_000
_KEY_RE: Final = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class DotenvParseError(ValueError):
    pass


def parse_kv_lines(text: str, *, strict: bool = True) -> dict[str, str]:
    """Parse ``KEY=value`` lines. With ``strict=False``, skips lines without ``=`` (legacy ``.env``)."""
    out: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.lower().startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            if strict:
                raise DotenvParseError(f"Line is not KEY=value: {raw_line[:80]!r}")
            continue
        key, _, rest = line.partition("=")
        key = key.strip()
        val = rest.strip()
        if not _KEY_RE.match(key):
            raise DotenvParseError(f"Invalid key name: {key!r}")
        if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
            val = val[1:-1]
        if "\n" in val or "\r" in val:
            raise DotenvParseError(f"Value for {key} must be a single line")
        if len(val) > _MAX_VAL_LEN:
            raise DotenvParseError(f"Value for {key} exceeds {_MAX_VAL_LEN} chars")
        out[key] = val
    return out


def _escape_dotenv_value(val: str) -> str:
    if "\n" in val or "\r" in val:
        raise DotenvParseError("newlines in values are not allowed")
    if val == "":
        return '""'
    if re.search(r'[\s#"\'\\]', val) or val.startswith("="):
        esc = val.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{esc}"'
    return val


def _load_env_file(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    try:
        data = path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        raise DotenvParseError(f"Cannot read .env: {e}") from e
    if len(data) > _MAX_FILE:
        raise DotenvParseError(f".env file is larger than {_MAX_FILE} bytes — edit on disk.")
    return parse_kv_lines(data, strict=False)


def merge_write_project_env(project_name: str, chat_body: str) -> tuple[bool, str]:
    """
    Parse ``chat_body`` as KEY=value lines and merge into ``project/.env`` (updates win).
    Returns (success, message for user).
    """
    pd = workspace_project_dir(project_name)
    if pd is None:
        return False, "Invalid project name, folder missing, or BLACK_COMPANY_PROJECT_ROOT not set."
    try:
        updates = parse_kv_lines(chat_body, strict=True)
    except DotenvParseError as e:
        return False, str(e)
    if not updates:
        return False, "No keys parsed. Send lines like:\n<code>DATABASE_URL=postgres://...</code>\n<code>API_KEY=abc</code>"
    if len(updates) > _MAX_KEYS:
        return False, f"Too many keys (max {_MAX_KEYS})."

    env_path = pd / ".env"
    try:
        existing = _load_env_file(env_path)
    except DotenvParseError as e:
        return False, str(e)

    merged = {**existing, **updates}
    lines_out = [f"{k}={_escape_dotenv_value(v)}" for k, v in sorted(merged.items())]
    body = "\n".join(lines_out) + "\n"
    if len(body) > _MAX_FILE:
        return False, f"Resulting .env would be too large (max {_MAX_FILE} bytes)."

    tmp = env_path.with_suffix(".env.tmp")
    try:
        tmp.write_text(body, encoding="utf-8", newline="\n")
        os.replace(tmp, env_path)
    except OSError as e:
        tmp.unlink(missing_ok=True)
        return False, f"Could not write .env: {e}"

    n_new = len(set(updates) - set(existing))
    n_upd = len(set(updates) & set(existing))
    return True, (
        f"Updated <code>{escape(str(env_path))}</code>\n"
        f"• {len(updates)} key(s) from this message — "
        f"{n_new} new, {n_upd} overwritten.\n\n"
        "<i>Telegram is not a secret store — rotate keys if this chat could be seen.</i>"
    )
