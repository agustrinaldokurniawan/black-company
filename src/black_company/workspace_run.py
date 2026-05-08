"""Run workspace projects via static TOML manifests only (never arbitrary shell from Telegram)."""

from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from black_company.growth.store import data_dir

MANIFEST_NAME: Final = ".black-company-run.toml"
_MAX_TIMEOUT: Final = 600
_DEFAULT_TIMEOUT: Final = 120
_PID_SUBDIR: Final = "runproj"


def _safe_dir_name(name: str) -> bool:
    if not name or len(name) > 200:
        return False
    if ".." in name or "/" in name or "\\" in name:
        return False
    return bool(re.match(r"^[\w][\w.-]*$", name))


def _workspace_root() -> Path | None:
    raw = os.environ.get("BLACK_COMPANY_PROJECT_ROOT", "").strip()
    if not raw:
        return None
    p = Path(raw).expanduser().resolve()
    return p if p.is_dir() else None


def _project_path(name: str) -> Path | None:
    if not _safe_dir_name(name):
        return None
    root = _workspace_root()
    if root is None:
        return None
    cand = (root / name).resolve()
    if not cand.is_dir():
        return None
    try:
        cand.relative_to(root)
    except ValueError:
        return None
    return cand


def workspace_project_dir(name: str) -> Path | None:
    """Public: resolved project folder under ``BLACK_COMPANY_PROJECT_ROOT``."""
    return _project_path(name)


@dataclass(frozen=True)
class RunManifest:
    command: list[str]
    cwd: Path
    timeout_sec: int
    background: bool


def _parse_manifest(project_dir: Path, data: dict[str, Any]) -> RunManifest:
    cmd = data.get("command")
    if not isinstance(cmd, list) or not cmd:
        raise ValueError("`command` must be a non-empty TOML array of strings, e.g. command = [\"pnpm\", \"run\", \"build\"]")
    command: list[str] = []
    for x in cmd:
        if not isinstance(x, str) or not x.strip():
            raise ValueError("each `command` entry must be a non-empty string")
        command.append(x)
    cwd_rel = data.get("cwd", ".")
    if not isinstance(cwd_rel, str):
        raise ValueError("`cwd` must be a string (path relative to the project folder)")
    proj = project_dir.resolve()
    cwd_path = (proj / cwd_rel).resolve()
    try:
        cwd_path.relative_to(proj)
    except ValueError as e:
        raise ValueError("`cwd` must stay inside the project directory") from e
    if not cwd_path.is_dir():
        raise ValueError(f"`cwd` is not a directory: {cwd_rel}")
    raw_timeout = data.get("timeout_sec", _DEFAULT_TIMEOUT)
    if isinstance(raw_timeout, bool):
        raise ValueError("`timeout_sec` must be an integer")
    if isinstance(raw_timeout, float):
        raw_timeout = int(raw_timeout) if raw_timeout == int(raw_timeout) else _DEFAULT_TIMEOUT
    if type(raw_timeout) is not int:
        raise ValueError("`timeout_sec` must be an integer")
    timeout_sec = max(1, min(int(raw_timeout), _MAX_TIMEOUT))
    bg = data.get("background", False)
    if not isinstance(bg, bool):
        raise ValueError("`background` must be true or false")
    return RunManifest(command=command, cwd=cwd_path, timeout_sec=timeout_sec, background=bg)


def load_manifest(project_dir: Path) -> RunManifest:
    mf = project_dir / MANIFEST_NAME
    if not mf.is_file():
        raise FileNotFoundError(f"Missing {MANIFEST_NAME} in {project_dir.name}/")
    raw = tomllib.loads(mf.read_text(encoding="utf-8", errors="replace"))
    if not isinstance(raw, dict):
        raise ValueError("manifest root must be a table")
    return _parse_manifest(project_dir, raw)


def list_runnable_project_names() -> list[str]:
    root = _workspace_root()
    if root is None:
        return []
    names: list[str] = []
    try:
        for child in sorted(root.iterdir(), key=lambda p: p.name.lower()):
            if child.is_dir() and not child.name.startswith(".") and (child / MANIFEST_NAME).is_file():
                names.append(child.name)
    except OSError:
        return []
    return names


def _pid_file(name: str) -> Path:
    d = data_dir() / _PID_SUBDIR
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{name}.json"


def _run_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("GIT_TERMINAL_PROMPT", "0")
    env.setdefault("CI", "1")
    return env


def run_project_foreground(project_name: str) -> tuple[int, str]:
    """Run with subprocess.run; return (exit_code, combined log). exit -1 = launch error."""
    pd = _project_path(project_name)
    if pd is None:
        return -1, "Invalid project name or BLACK_COMPANY_PROJECT_ROOT not set."
    try:
        m = load_manifest(pd)
    except (OSError, ValueError, tomllib.TOMLDecodeError) as e:
        return -1, str(e)
    if m.background:
        ok, msg = start_project_background(project_name)
        return (0 if ok else -1), msg
    try:
        proc = subprocess.run(
            m.command,
            cwd=m.cwd,
            capture_output=True,
            text=True,
            timeout=m.timeout_sec,
            env=_run_env(),
        )
        out = (proc.stdout or "") + (("\n" + proc.stderr) if proc.stderr else "")
        if not out.strip():
            out = f"(no output, exit {proc.returncode})"
        return proc.returncode, out
    except subprocess.TimeoutExpired as e:
        tail = ""
        if e.stdout:
            tail += str(e.stdout)
        if e.stderr:
            tail += "\n" + str(e.stderr)
        return -2, f"Timed out after {m.timeout_sec}s.\n{tail}"[:8000]
    except FileNotFoundError as e:
        return -1, f"Executable not found (is PATH correct inside Docker/local?): {e}"
    except Exception as e:
        return -1, f"{type(e).__name__}: {e}"


def start_project_background(project_name: str) -> tuple[bool, str]:
    pd = _project_path(project_name)
    if pd is None:
        return False, "Invalid project name or BLACK_COMPANY_PROJECT_ROOT not set."
    try:
        m = load_manifest(pd)
    except (OSError, ValueError, tomllib.TOMLDecodeError) as e:
        return False, str(e)
    if not m.background:
        return False, "Manifest has `background = false` — use /runproj without stopping; it runs until timeout."
    # Already running?
    pf = _pid_file(project_name)
    if pf.is_file():
        try:
            meta = json.loads(pf.read_text(encoding="utf-8"))
            pid = int(meta.get("pid", 0))
            if pid > 0 and _pid_alive(pid):
                return False, f"Already running (PID {pid}). /stopproj {project_name} first."
        except (json.JSONDecodeError, OSError, ValueError):
            pass
    try:
        popen_kw: dict[str, Any] = {
            "cwd": m.cwd,
            "env": _run_env(),
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
        }
        if os.name == "posix":
            popen_kw["start_new_session"] = True
        proc = subprocess.Popen(m.command, **popen_kw)
    except FileNotFoundError as e:
        return False, f"Executable not found: {e}"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"
    meta = {"pid": proc.pid, "project": project_name}
    pf.write_text(json.dumps(meta), encoding="utf-8")
    return True, f"Started in background (PID {proc.pid}). Logs not captured. /stopproj {project_name} to stop."


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def stop_project_background(project_name: str) -> str:
    if not _safe_dir_name(project_name):
        return "Invalid project name."
    pf = _pid_file(project_name)
    if not pf.is_file():
        return f"No recorded background run for `{project_name}`."
    try:
        meta = json.loads(pf.read_text(encoding="utf-8"))
        pid = int(meta.get("pid", 0))
    except (OSError, json.JSONDecodeError, ValueError):
        pf.unlink(missing_ok=True)
        return "Stale pid file removed."
    if pid <= 0 or not _pid_alive(pid):
        pf.unlink(missing_ok=True)
        return f"Process {pid} not running; cleared record."
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError as e:
        return f"Could not signal PID {pid}: {e}"
    pf.unlink(missing_ok=True)
    return f"Sent SIGTERM to PID {pid} (`{project_name}`). Child processes may still be running."
