"""Claude Code session tracking — read/write ~/.pipnav/sessions.json."""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from pipnav.core.logging import get_logger

SESSIONS_PATH = Path.home() / ".pipnav" / "sessions.json"


@dataclass(frozen=True)
class SessionInfo:
    """Claude Code session state for a project."""

    last_session: datetime
    resumable: bool


def load_sessions() -> dict[str, SessionInfo]:
    """Load sessions from ~/.pipnav/sessions.json."""
    logger = get_logger()

    if not SESSIONS_PATH.exists():
        return {}

    try:
        raw = SESSIONS_PATH.read_text(encoding="utf-8")
        data = json.loads(raw)
        result: dict[str, SessionInfo] = {}
        for key, val in data.items():
            result[key] = SessionInfo(
                last_session=datetime.fromisoformat(val["last_session"]),
                resumable=val.get("resumable", False),
            )
        return result
    except (json.JSONDecodeError, TypeError, KeyError, ValueError) as exc:
        logger.warning("Corrupt sessions file, returning empty: %s", exc)
        return {}


def save_sessions(sessions: dict[str, SessionInfo]) -> None:
    """Write sessions to ~/.pipnav/sessions.json."""
    logger = get_logger()
    SESSIONS_PATH.parent.mkdir(parents=True, exist_ok=True)

    try:
        data = {
            key: {
                "last_session": info.last_session.isoformat(),
                "resumable": info.resumable,
            }
            for key, info in sessions.items()
        }
        SESSIONS_PATH.write_text(
            json.dumps(data, indent=2) + "\n", encoding="utf-8"
        )
    except OSError as exc:
        logger.error("Failed to save sessions: %s", exc)


def record_session(
    project_path: Path, resumable: bool = True
) -> dict[str, SessionInfo]:
    """Record a Claude Code session launch. Returns updated sessions."""
    sessions = load_sessions()
    key = str(project_path)
    new_sessions = {
        **sessions,
        key: SessionInfo(last_session=datetime.now(), resumable=resumable),
    }
    save_sessions(new_sessions)
    return new_sessions
