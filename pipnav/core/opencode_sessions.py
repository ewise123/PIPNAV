"""Discover resumable OpenCode sessions from its SQLite database.

OpenCode's own process writes this database while we read it, so every access is
read-only and every failure degrades to an empty list rather than raising:
the file may be absent, locked mid-write, or a different shape after an update.

Two details that are easy to get silently wrong:
  * `time_updated` is epoch MILLISECONDS, not seconds.
  * The table carries child sessions (an agent's own internal work) and
    archived ones. Neither belongs in a list of things you can pick back up.

Resume with: opencode -s <session_id>
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from pipnav.core.logging import get_logger

DB_PATH = Path.home() / ".local" / "share" / "opencode" / "opencode.db"

# Short, because the database may be locked by OpenCode writing to it.
TIMEOUT_SECONDS = 1.0

_QUERY = """
SELECT id, directory, title, time_updated, cost
FROM session
WHERE parent_id IS NULL
  AND time_archived IS NULL
ORDER BY time_updated DESC
"""


@dataclass(frozen=True)
class OpenCodeSession:
    """A resumable OpenCode session."""

    session_id: str
    project_path: str
    title: str
    last_active: datetime
    cost: float = 0.0


def _rows() -> tuple[sqlite3.Row, ...]:
    """Every top-level, unarchived session row. Empty on any problem."""
    logger = get_logger()
    if not DB_PATH.is_file():
        return ()

    try:
        # uri=True so mode=ro is honoured — never write a database we don't own.
        connection = sqlite3.connect(
            f"file:{DB_PATH}?mode=ro", uri=True, timeout=TIMEOUT_SECONDS
        )
    except sqlite3.Error as exc:
        logger.debug("Cannot open opencode database: %s", exc)
        return ()

    try:
        connection.row_factory = sqlite3.Row
        return tuple(connection.execute(_QUERY))
    except sqlite3.Error as exc:
        # Locked, corrupt, or a schema we no longer recognise.
        logger.debug("Cannot read opencode sessions: %s", exc)
        return ()
    finally:
        connection.close()


def _session_from_row(row: sqlite3.Row) -> OpenCodeSession | None:
    """Map one row. Returns None if it is not usable."""
    session_id = row["id"]
    if not isinstance(session_id, str) or not session_id:
        return None

    try:
        last_active = datetime.fromtimestamp(row["time_updated"] / 1000)
    except (TypeError, ValueError, OSError, OverflowError):
        return None

    directory = row["directory"] if isinstance(row["directory"], str) else ""
    title = (row["title"] or "").strip()

    try:
        cost = float(row["cost"] or 0.0)
    except (TypeError, ValueError):
        cost = 0.0

    return OpenCodeSession(
        session_id=session_id,
        project_path=directory,
        title=title or (Path(directory).name if directory else "(untitled)"),
        last_active=last_active,
        cost=cost,
    )


def discover_sessions() -> tuple[OpenCodeSession, ...]:
    """Every resumable OpenCode session, newest first."""
    sessions = [
        session
        for row in _rows()
        if (session := _session_from_row(row)) is not None
    ]
    return tuple(sessions)


def discover_sessions_for_project(project_path: Path) -> tuple[OpenCodeSession, ...]:
    """Resumable OpenCode sessions that ran in this directory, newest first."""
    wanted = str(project_path).rstrip("/")
    return tuple(
        session
        for session in discover_sessions()
        if session.project_path.rstrip("/") == wanted
    )
