"""Project discovery — scan root directories for project subdirectories."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from pipnav.core.logging import get_logger


@dataclass(frozen=True)
class ProjectInfo:
    """Metadata about a discovered project directory."""

    name: str
    path: Path
    is_git_repo: bool
    last_modified: datetime | None


def discover_projects(roots: tuple[str, ...]) -> tuple[ProjectInfo, ...]:
    """Scan each root for immediate subdirectories. Skip hidden dirs."""
    logger = get_logger()
    projects: list[ProjectInfo] = []

    for root_str in roots:
        root = Path(root_str).expanduser().resolve()
        if not root.is_dir():
            logger.warning("Project root does not exist: %s", root)
            continue

        try:
            for entry in sorted(root.iterdir(), key=lambda p: p.name.lower()):
                if not entry.is_dir():
                    continue
                if entry.name.startswith("."):
                    continue

                is_git = (entry / ".git").is_dir()
                try:
                    mtime = datetime.fromtimestamp(entry.stat().st_mtime)
                except OSError:
                    mtime = None

                projects.append(
                    ProjectInfo(
                        name=entry.name,
                        path=entry,
                        is_git_repo=is_git,
                        last_modified=mtime,
                    )
                )
        except OSError as exc:
            logger.error("Error scanning root %s: %s", root, exc)

    return tuple(projects)


def is_stale(project: ProjectInfo, threshold_days: int) -> bool:
    """Check if a project hasn't been modified within the threshold."""
    if project.last_modified is None:
        return True
    delta = datetime.now() - project.last_modified
    return delta.days > threshold_days
