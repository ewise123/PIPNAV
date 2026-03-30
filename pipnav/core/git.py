"""Git integration — extract branch, status, ahead/behind, log from repos."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from pipnav.core.logging import get_logger


@dataclass(frozen=True)
class GitStatus:
    """Git working tree status for a project."""

    branch: str
    modified_count: int
    staged_count: int
    untracked_count: int
    ahead: int
    behind: int
    last_commit_time: datetime | None
    is_dirty: bool


@dataclass(frozen=True)
class GitLogEntry:
    """A single git log entry."""

    sha_short: str
    message: str
    author: str
    timestamp: datetime


def get_git_status(path: Path) -> GitStatus | None:
    """Return git status for path, or None if not a git repo. Never raises."""
    logger = get_logger()
    try:
        from git import InvalidGitRepositoryError, Repo

        repo = Repo(path)
    except Exception as exc:
        logger.debug("Not a git repo or git error at %s: %s", path, exc)
        return None

    try:
        # Branch name
        try:
            branch = repo.active_branch.name
        except TypeError:
            branch = "HEAD detached"

        # Working tree changes
        try:
            modified_count = len(repo.index.diff(None))
        except Exception:
            modified_count = 0

        # Staged changes
        try:
            staged_count = len(repo.index.diff("HEAD"))
        except Exception:
            staged_count = 0

        # Untracked files
        try:
            untracked_count = len(repo.untracked_files)
        except Exception:
            untracked_count = 0

        # Ahead/behind
        ahead, behind = 0, 0
        try:
            tracking = repo.active_branch.tracking_branch()
            if tracking is not None:
                rev_list = repo.git.rev_list(
                    "--left-right", "--count", f"{tracking}...HEAD"
                )
                parts = rev_list.strip().split("\t")
                if len(parts) == 2:
                    behind, ahead = int(parts[0]), int(parts[1])
        except Exception:
            pass

        # Last commit time
        last_commit_time = None
        try:
            last_commit_time = repo.head.commit.committed_datetime.replace(
                tzinfo=None
            )
        except Exception:
            pass

        is_dirty = repo.is_dirty(untracked_files=True)

        return GitStatus(
            branch=branch,
            modified_count=modified_count,
            staged_count=staged_count,
            untracked_count=untracked_count,
            ahead=ahead,
            behind=behind,
            last_commit_time=last_commit_time,
            is_dirty=is_dirty,
        )
    except Exception as exc:
        logger.error("Error getting git status for %s: %s", path, exc)
        return None


def get_git_log(path: Path, max_entries: int = 20) -> tuple[GitLogEntry, ...]:
    """Return recent git log entries. Never raises."""
    logger = get_logger()
    try:
        from git import Repo

        repo = Repo(path)
        entries: list[GitLogEntry] = []

        for commit in repo.iter_commits(max_count=max_entries):
            entries.append(
                GitLogEntry(
                    sha_short=commit.hexsha[:7],
                    message=commit.message.strip().split("\n")[0],
                    author=str(commit.author),
                    timestamp=commit.committed_datetime.replace(tzinfo=None),
                )
            )

        return tuple(entries)
    except Exception as exc:
        logger.debug("Error getting git log for %s: %s", path, exc)
        return ()


def compute_badge(
    git_status: GitStatus | None,
    has_session: bool,
    is_stale: bool,
) -> str:
    """Return the highest-priority status badge. Priority: S > !U > !M > ~ > check > ?"""
    if git_status is None:
        return "[? ]"
    if has_session:
        return "[S ]"
    if git_status.ahead > 0:
        return "[!U]"
    if git_status.is_dirty:
        return "[!M]"
    if is_stale:
        return "[~ ]"
    return "[✓ ]"
