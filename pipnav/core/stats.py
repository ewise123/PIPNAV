"""Aggregate stats — compute summary metrics across all projects."""

from pathlib import Path

from pipnav.core.claude_sessions import discover_sessions_for_project
from pipnav.core.git import GitStatus


def compute_aggregate_stats(
    git_statuses: dict[str, GitStatus | None],
) -> dict[str, int]:
    """Compute summary stats for the status bar."""
    total = len(git_statuses)
    clean = sum(
        1 for gs in git_statuses.values()
        if gs is not None and not gs.is_dirty
    )

    # Count projects that have at least one Claude session
    projects_with_sessions = 0
    for path_str in git_statuses:
        sessions = discover_sessions_for_project(Path(path_str))
        if sessions:
            projects_with_sessions += 1

    return {
        "total": total,
        "clean": clean,
        "projects_with_sessions": projects_with_sessions,
    }


def make_bar(current: int, total: int, width: int = 10) -> str:
    """Render a block-character progress bar."""
    if total == 0:
        return "░" * width
    filled = round((current / total) * width)
    filled = min(filled, width)
    return "█" * filled + "░" * (width - filled)
