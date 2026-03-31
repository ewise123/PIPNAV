"""Aggregate stats — compute summary metrics across all projects."""

from datetime import datetime

from pipnav.core.git import GitStatus
from pipnav.core.sessions import SessionInfo


def compute_aggregate_stats(
    git_statuses: dict[str, GitStatus | None],
    sessions: dict[str, SessionInfo],
) -> dict[str, int]:
    """Compute summary stats for the status bar."""
    total = len(git_statuses)
    clean = sum(
        1 for gs in git_statuses.values()
        if gs is not None and not gs.is_dirty
    )
    active_sessions = sum(
        1 for s in sessions.values() if s.resumable
    )
    total_commits = 0
    for gs in git_statuses.values():
        if gs is not None and gs.last_commit_time is not None:
            # Count ahead as a proxy for recent activity
            total_commits += gs.ahead

    return {
        "total": total,
        "clean": clean,
        "sessions": active_sessions,
    }


def make_bar(current: int, total: int, width: int = 10) -> str:
    """Render a block-character progress bar."""
    if total == 0:
        return "░" * width
    filled = round((current / total) * width)
    filled = min(filled, width)
    return "█" * filled + "░" * (width - filled)
