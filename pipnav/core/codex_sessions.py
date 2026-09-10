"""Discover resumable Codex sessions from ~/.codex/sessions.

Codex writes one JSONL rollout per session into a dated tree, and the first line
is a `session_meta` record carrying the session id and the directory it ran in.
Rollouts reach tens of megabytes, so this reader opens each file and reads
exactly one line — never the whole thing.

Resume with: codex resume <session_id>
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from pipnav.core.logging import get_logger

SESSIONS_DIR = Path.home() / ".codex" / "sessions"


@dataclass(frozen=True)
class CodexSession:
    """A resumable Codex session."""

    session_id: str
    project_path: str  # "" when the rollout did not record a cwd
    title: str
    last_active: datetime


def _parse_timestamp(value: object) -> datetime | None:
    """Parse Codex's ISO timestamp, converted to naive local time."""
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone().replace(tzinfo=None)


def _read_meta(path: Path) -> CodexSession | None:
    """Read one rollout's first line. Returns None if it is not usable."""
    logger = get_logger()
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            first_line = handle.readline()
    except OSError as exc:
        logger.debug("Cannot read codex rollout %s: %s", path, exc)
        return None

    if not first_line.strip():
        return None

    try:
        entry = json.loads(first_line)
    except json.JSONDecodeError:
        logger.debug("Codex rollout %s does not start with JSON", path)
        return None

    if not isinstance(entry, dict) or entry.get("type") != "session_meta":
        return None

    payload = entry.get("payload")
    if not isinstance(payload, dict):
        return None

    session_id = payload.get("id")
    if not isinstance(session_id, str) or not session_id:
        return None

    last_active = _parse_timestamp(payload.get("timestamp")) or _parse_timestamp(
        entry.get("timestamp")
    )
    if last_active is None:
        try:
            last_active = datetime.fromtimestamp(path.stat().st_mtime)
        except OSError:
            return None

    cwd = payload.get("cwd")
    project_path = cwd if isinstance(cwd, str) else ""

    return CodexSession(
        session_id=session_id,
        project_path=project_path,
        # Codex records no title. The folder name is the most useful label we
        # have without reading the whole rollout.
        title=Path(project_path).name if project_path else "(no directory)",
        last_active=last_active,
    )


def discover_sessions() -> tuple[CodexSession, ...]:
    """Every resumable Codex session, newest first."""
    if not SESSIONS_DIR.is_dir():
        return ()

    sessions: list[CodexSession] = []
    try:
        for path in SESSIONS_DIR.rglob("rollout-*.jsonl"):
            session = _read_meta(path)
            if session is not None:
                sessions.append(session)
    except OSError as exc:
        get_logger().debug("Error scanning codex sessions: %s", exc)

    sessions.sort(key=lambda s: s.last_active, reverse=True)
    return tuple(sessions)


def discover_sessions_for_project(project_path: Path) -> tuple[CodexSession, ...]:
    """Resumable Codex sessions that ran in this directory, newest first."""
    wanted = str(project_path).rstrip("/")
    return tuple(
        session
        for session in discover_sessions()
        if session.project_path.rstrip("/") == wanted
    )
