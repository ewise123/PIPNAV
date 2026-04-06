"""Discover real Claude Code sessions from ~/.claude/ storage."""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from pipnav.core.logging import get_logger

CLAUDE_DIR = Path.home() / ".claude"
PROJECTS_DIR = CLAUDE_DIR / "projects"


@dataclass(frozen=True)
class ClaudeSession:
    """A resumable Claude Code session."""

    session_id: str
    project_path: str
    timestamp: datetime
    last_activity: datetime
    session_name: str
    first_message: str
    message_count: int


def _encode_project_path(path: Path) -> str:
    """Encode a project path the way Claude Code does (slashes to dashes)."""
    return str(path).replace("/", "-")



def discover_sessions_for_project(project_path: Path) -> tuple[ClaudeSession, ...]:
    """Find all Claude Code sessions for a given project path."""
    logger = get_logger()
    encoded = _encode_project_path(project_path)
    sessions_dir = PROJECTS_DIR / encoded

    if not sessions_dir.is_dir():
        return ()

    sessions: list[ClaudeSession] = []

    try:
        for jsonl_file in sessions_dir.glob("*.jsonl"):
            session_id = jsonl_file.stem
            # Skip non-UUID filenames
            if len(session_id) < 30:
                continue

            session = _parse_session_file(jsonl_file, session_id, str(project_path))
            if session is not None:
                sessions.append(session)
    except OSError as exc:
        logger.error("Error scanning sessions for %s: %s", project_path, exc)

    # Sort by last activity so resumed sessions stay at the top.
    sessions.sort(key=lambda s: s.last_activity, reverse=True)
    return tuple(sessions)


def _parse_timestamp(ts: object) -> datetime | None:
    """Parse a timestamp from a JSONL entry, converting UTC to local time."""
    try:
        if isinstance(ts, str):
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            # Convert to local time, then strip timezone for naive comparison
            return dt.astimezone().replace(tzinfo=None)
        if isinstance(ts, (int, float)):
            return datetime.fromtimestamp(ts / 1000)
    except (ValueError, OSError):
        pass
    return None


def _parse_session_file(
    path: Path, session_id: str, project_path: str
) -> ClaudeSession | None:
    """Parse a session JSONL file to extract metadata."""
    logger = get_logger()
    first_message = ""
    session_name = ""
    start_timestamp: datetime | None = None
    last_timestamp: datetime | None = None
    message_count = 0

    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                entry_type = entry.get("type", "")

                # Count user and assistant messages
                if entry_type in ("user", "assistant"):
                    message_count += 1

                # Track timestamps — first and last
                if "timestamp" in entry:
                    parsed = _parse_timestamp(entry["timestamp"])
                    if parsed is not None:
                        if start_timestamp is None:
                            start_timestamp = parsed
                        last_timestamp = parsed

                # Get session name from custom-title (use the latest one)
                if entry_type == "custom-title":
                    title = entry.get("customTitle", "")
                    if title:
                        session_name = title

                # Get first user message as fallback summary
                if (
                    not first_message
                    and entry_type == "user"
                    and "message" in entry
                ):
                    content = entry["message"].get("content", "")
                    if isinstance(content, str):
                        first_message = _clean_message(content)
                    elif isinstance(content, list):
                        for block in content:
                            if isinstance(block, dict) and block.get("type") == "text":
                                first_message = _clean_message(block.get("text", ""))
                                break

    except OSError as exc:
        logger.debug("Error reading session file %s: %s", path, exc)
        return None

    if start_timestamp is None:
        # Fall back to file mtime
        try:
            start_timestamp = datetime.fromtimestamp(path.stat().st_mtime)
        except OSError:
            return None

    if last_timestamp is None:
        last_timestamp = start_timestamp

    return ClaudeSession(
        session_id=session_id,
        project_path=project_path,
        timestamp=start_timestamp,
        last_activity=last_timestamp,
        session_name=session_name,
        first_message=first_message or "(no message)",
        message_count=message_count,
    )


def _clean_message(text: str) -> str:
    """Clean up a user message for display — strip tags and truncate."""
    # Remove XML-like tags
    import re

    cleaned = re.sub(r"<[^>]+>", "", text).strip()
    # Take first line only
    first_line = cleaned.split("\n")[0].strip()
    # Truncate
    if len(first_line) > 80:
        return first_line[:77] + "..."
    return first_line if first_line else "(no message)"
