"""Session Control Center — cross-project Claude session aggregation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from pipnav.core.claude_sessions import (
    ClaudeSession,
    discover_sessions_for_project,
)
from pipnav.core.git import get_git_status
from pipnav.core.logging import get_logger
from pipnav.core.projects import ProjectInfo


@dataclass(frozen=True)
class EnrichedSession:
    """A Claude session enriched with project context and status classification."""

    session_id: str
    project_path: str
    project_name: str
    branch: str
    status: str  # "active" | "resumable" | "idle" | "stale"
    last_prompt: str
    message_count: int
    age_seconds: int
    timestamp: datetime


# Sessions with activity within this window are considered "active"
ACTIVE_THRESHOLD_SECONDS = 3600  # 1 hour
# Sessions older than this are "stale"
STALE_THRESHOLD_SECONDS = 86400 * 7  # 7 days
# Sessions with very few messages are "idle"
IDLE_MESSAGE_THRESHOLD = 2


def classify_session_status(
    session: ClaudeSession,
    age_seconds: int,
) -> str:
    """Classify a session's status based on age and message count.

    Returns one of: "active", "resumable", "idle", "stale"
    """
    if age_seconds < ACTIVE_THRESHOLD_SECONDS:
        return "active"
    if age_seconds > STALE_THRESHOLD_SECONDS:
        return "stale"
    if session.message_count < IDLE_MESSAGE_THRESHOLD:
        return "idle"
    return "resumable"


def enrich_session(
    session: ClaudeSession,
    project_name: str,
    branch: str,
) -> EnrichedSession:
    """Enrich a raw ClaudeSession with project context and status."""
    now = datetime.now()
    age = int((now - session.timestamp).total_seconds())
    status = classify_session_status(session, age)

    return EnrichedSession(
        session_id=session.session_id,
        project_path=session.project_path,
        project_name=project_name,
        branch=branch,
        status=status,
        last_prompt=session.first_message,
        message_count=session.message_count,
        age_seconds=age,
        timestamp=session.timestamp,
    )


def discover_all_sessions(
    projects: tuple[ProjectInfo, ...],
) -> tuple[EnrichedSession, ...]:
    """Discover and enrich all Claude sessions across all projects.

    This is expensive — call from a background worker thread.
    """
    logger = get_logger()
    enriched: list[EnrichedSession] = []

    for project in projects:
        try:
            raw_sessions = discover_sessions_for_project(project.path)

            # Get branch once per project
            branch = "—"
            if project.is_git_repo:
                gs = get_git_status(project.path)
                if gs is not None:
                    branch = gs.branch

            for session in raw_sessions:
                enriched.append(
                    enrich_session(session, project.name, branch)
                )
        except Exception as exc:
            logger.debug(
                "Error discovering sessions for %s: %s", project.path, exc
            )

    # Sort by timestamp, newest first
    enriched.sort(key=lambda s: s.timestamp, reverse=True)
    return tuple(enriched)


def discover_sessions_from_cache(
    projects: tuple[ProjectInfo, ...],
    git_statuses: dict[str, str | None],
) -> tuple[EnrichedSession, ...]:
    """Discover sessions using pre-fetched git branch data from the indexer.

    This avoids redundant git calls when the indexer already has branch info.
    """
    logger = get_logger()
    enriched: list[EnrichedSession] = []

    for project in projects:
        try:
            raw_sessions = discover_sessions_for_project(project.path)
            branch = git_statuses.get(str(project.path), "—") or "—"

            for session in raw_sessions:
                enriched.append(
                    enrich_session(session, project.name, branch)
                )
        except Exception as exc:
            logger.debug(
                "Error discovering sessions for %s: %s", project.path, exc
            )

    enriched.sort(key=lambda s: s.timestamp, reverse=True)
    return tuple(enriched)


def filter_sessions(
    sessions: tuple[EnrichedSession, ...],
    status_filter: str = "all",
) -> tuple[EnrichedSession, ...]:
    """Filter sessions by status. 'all' returns everything."""
    if status_filter == "all":
        return sessions
    return tuple(s for s in sessions if s.status == status_filter)


def sort_sessions(
    sessions: tuple[EnrichedSession, ...],
    sort_by: str = "timestamp",
) -> tuple[EnrichedSession, ...]:
    """Sort sessions by a given key."""
    if sort_by == "project":
        return tuple(sorted(sessions, key=lambda s: s.project_name.lower()))
    if sort_by == "messages":
        return tuple(sorted(sessions, key=lambda s: s.message_count, reverse=True))
    if sort_by == "status":
        order = {"active": 0, "resumable": 1, "idle": 2, "stale": 3}
        return tuple(sorted(sessions, key=lambda s: order.get(s.status, 9)))
    # Default: timestamp (newest first)
    return tuple(sorted(sessions, key=lambda s: s.timestamp, reverse=True))


STATUS_BADGES: dict[str, str] = {
    "active": "[bold green]ACT[/]",
    "resumable": "[bold yellow]RES[/]",
    "idle": "[dim]IDL[/]",
    "stale": "[dim red]OLD[/]",
}


def format_age(seconds: int) -> str:
    """Format age in human-readable form."""
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m"
    if seconds < 86400:
        return f"{seconds // 3600}h"
    days = seconds // 86400
    return f"{days}d"
