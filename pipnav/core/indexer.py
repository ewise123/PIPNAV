"""Background project indexer — cached project state with incremental updates."""

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from pipnav.core.claude_sessions import discover_sessions_for_project
from pipnav.core.config import PIPNAV_DIR
from pipnav.core.git import GitStatus, get_git_status
from pipnav.core.logging import get_logger
from pipnav.core.projects import ProjectInfo, discover_projects

CACHE_PATH = PIPNAV_DIR / "cache.json"
CACHE_VERSION = 1


@dataclass(frozen=True)
class CachedProjectState:
    """Cached metadata for a single project."""

    project_path: str
    project_name: str
    is_git_repo: bool
    git_status: GitStatus | None
    session_count: int
    last_modified_ts: float | None
    last_indexed: datetime


@dataclass(frozen=True)
class IndexCache:
    """Full index cache with version and freshness tracking."""

    version: int
    projects: tuple[CachedProjectState, ...]
    last_full_scan: datetime


def _git_status_to_dict(gs: GitStatus | None) -> dict | None:
    if gs is None:
        return None
    return asdict(gs)


def _dict_to_git_status(d: dict | None) -> GitStatus | None:
    if d is None:
        return None
    try:
        last_commit = d.get("last_commit_time")
        if isinstance(last_commit, str):
            last_commit = datetime.fromisoformat(last_commit)
        return GitStatus(
            branch=d.get("branch", ""),
            modified_count=d.get("modified_count", 0),
            staged_count=d.get("staged_count", 0),
            untracked_count=d.get("untracked_count", 0),
            ahead=d.get("ahead", 0),
            behind=d.get("behind", 0),
            last_commit_time=last_commit,
            is_dirty=d.get("is_dirty", False),
        )
    except (TypeError, ValueError):
        return None


def _cached_state_to_dict(state: CachedProjectState) -> dict:
    return {
        "project_path": state.project_path,
        "project_name": state.project_name,
        "is_git_repo": state.is_git_repo,
        "git_status": _git_status_to_dict(state.git_status),
        "session_count": state.session_count,
        "last_modified_ts": state.last_modified_ts,
        "last_indexed": state.last_indexed.isoformat(),
    }


def _dict_to_cached_state(d: dict) -> CachedProjectState | None:
    try:
        return CachedProjectState(
            project_path=d["project_path"],
            project_name=d["project_name"],
            is_git_repo=d.get("is_git_repo", False),
            git_status=_dict_to_git_status(d.get("git_status")),
            session_count=d.get("session_count", 0),
            last_modified_ts=d.get("last_modified_ts"),
            last_indexed=datetime.fromisoformat(d["last_indexed"]),
        )
    except (KeyError, TypeError, ValueError):
        return None


def load_cache() -> IndexCache | None:
    """Load cache from disk. Returns None if missing or corrupt."""
    logger = get_logger()
    if not CACHE_PATH.exists():
        return None

    try:
        raw = CACHE_PATH.read_text(encoding="utf-8")
        data = json.loads(raw)

        if data.get("version") != CACHE_VERSION:
            logger.info("Cache version mismatch, discarding")
            return None

        projects: list[CachedProjectState] = []
        for entry in data.get("projects", []):
            state = _dict_to_cached_state(entry)
            if state is not None:
                projects.append(state)

        return IndexCache(
            version=CACHE_VERSION,
            projects=tuple(projects),
            last_full_scan=datetime.fromisoformat(data["last_full_scan"]),
        )
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        logger.warning("Corrupt cache file, discarding: %s", exc)
        return None


def save_cache(cache: IndexCache) -> None:
    """Write cache to disk."""
    logger = get_logger()
    PIPNAV_DIR.mkdir(parents=True, exist_ok=True)

    try:
        data = {
            "version": cache.version,
            "projects": [_cached_state_to_dict(p) for p in cache.projects],
            "last_full_scan": cache.last_full_scan.isoformat(),
        }
        CACHE_PATH.write_text(
            json.dumps(data, indent=2, default=str) + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        logger.error("Failed to save cache: %s", exc)


def _index_project(project: ProjectInfo) -> CachedProjectState:
    """Index a single project — fetch git status and session count."""
    git_status = get_git_status(project.path) if project.is_git_repo else None
    sessions = discover_sessions_for_project(project.path)
    mtime_ts = project.last_modified.timestamp() if project.last_modified else None

    return CachedProjectState(
        project_path=str(project.path),
        project_name=project.name,
        is_git_repo=project.is_git_repo,
        git_status=git_status,
        session_count=len(sessions),
        last_modified_ts=mtime_ts,
        last_indexed=datetime.now(),
    )


def full_scan(roots: tuple[str, ...]) -> IndexCache:
    """Perform a full scan of all projects. Expensive but complete."""
    projects = discover_projects(roots)
    states = tuple(_index_project(p) for p in projects)

    return IndexCache(
        version=CACHE_VERSION,
        projects=states,
        last_full_scan=datetime.now(),
    )


def incremental_update(
    cache: IndexCache,
    roots: tuple[str, ...],
    ttl_seconds: int = 60,
) -> IndexCache:
    """Re-index only stale projects. Projects whose directory mtime changed
    or whose cache entry is older than ttl_seconds get refreshed."""
    now = datetime.now()
    projects = discover_projects(roots)

    # Build lookup from cached data
    cached_by_path: dict[str, CachedProjectState] = {
        s.project_path: s for s in cache.projects
    }

    updated: list[CachedProjectState] = []
    for project in projects:
        key = str(project.path)
        cached = cached_by_path.get(key)

        needs_refresh = False
        if cached is None:
            needs_refresh = True
        else:
            # Check if directory mtime changed
            current_mtime = (
                project.last_modified.timestamp()
                if project.last_modified
                else None
            )
            if current_mtime != cached.last_modified_ts:
                needs_refresh = True
            # Check TTL
            age = (now - cached.last_indexed).total_seconds()
            if age > ttl_seconds:
                needs_refresh = True

        if needs_refresh:
            updated.append(_index_project(project))
        else:
            updated.append(cached)

    return IndexCache(
        version=CACHE_VERSION,
        projects=tuple(updated),
        last_full_scan=cache.last_full_scan,
    )


class ProjectIndexer:
    """Manages the project index cache with warm-start and incremental updates.

    This class is NOT thread-safe — call its methods from a single thread
    (typically a Textual @work thread) and pass results back via call_from_thread.
    """

    def __init__(self, roots: tuple[str, ...], ttl_seconds: int = 60) -> None:
        self._roots = roots
        self._ttl_seconds = ttl_seconds
        self._cache: IndexCache | None = None

    @property
    def cache(self) -> IndexCache | None:
        return self._cache

    @property
    def roots(self) -> tuple[str, ...]:
        return self._roots

    @roots.setter
    def roots(self, value: tuple[str, ...]) -> None:
        self._roots = value

    def warm_start(self) -> IndexCache | None:
        """Try to load cache from disk for instant startup."""
        self._cache = load_cache()
        return self._cache

    def refresh(self, force_full: bool = False) -> IndexCache:
        """Refresh the index. Uses incremental update if cache exists."""
        if self._cache is not None and not force_full:
            self._cache = incremental_update(
                self._cache, self._roots, self._ttl_seconds
            )
        else:
            self._cache = full_scan(self._roots)

        save_cache(self._cache)
        return self._cache

    def invalidate(self) -> None:
        """Force next refresh to be a full scan."""
        self._cache = None

    def get_git_statuses(self) -> dict[str, GitStatus | None]:
        """Extract git statuses from cache as a dict keyed by project path."""
        if self._cache is None:
            return {}
        return {
            s.project_path: s.git_status for s in self._cache.projects
        }

    def get_projects(self) -> tuple[ProjectInfo, ...]:
        """Extract ProjectInfo from cache."""
        if self._cache is None:
            return ()
        return tuple(
            ProjectInfo(
                name=s.project_name,
                path=Path(s.project_path),
                is_git_repo=s.is_git_repo,
                last_modified=(
                    datetime.fromtimestamp(s.last_modified_ts)
                    if s.last_modified_ts is not None
                    else None
                ),
            )
            for s in self._cache.projects
        )

    def get_session_counts(self) -> dict[str, int]:
        """Extract session counts from cache as a dict keyed by project path."""
        if self._cache is None:
            return {}
        return {
            s.project_path: s.session_count for s in self._cache.projects
        }

    def last_scan_time(self) -> datetime | None:
        """Return when the last full scan happened."""
        if self._cache is None:
            return None
        return self._cache.last_full_scan
