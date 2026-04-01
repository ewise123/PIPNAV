"""Polling-based file watcher — detects changes in project dirs and Claude state."""

from __future__ import annotations

import threading
from datetime import datetime
from pathlib import Path
from typing import Callable

from pipnav.core.logging import get_logger

# Directories and files that signal state changes
CLAUDE_PROJECTS_DIR = Path.home() / ".claude" / "projects"
PIPNAV_STATE_DIR = Path.home() / ".pipnav"


def _snapshot_mtimes(paths: tuple[Path, ...]) -> dict[str, float]:
    """Take a snapshot of modification times for the given paths."""
    result: dict[str, float] = {}
    for path in paths:
        try:
            if path.is_file():
                result[str(path)] = path.stat().st_mtime
            elif path.is_dir():
                result[str(path)] = path.stat().st_mtime
        except OSError:
            pass
    return result


def _get_watched_paths(roots: tuple[str, ...]) -> tuple[Path, ...]:
    """Collect all paths we want to watch for changes."""
    paths: list[Path] = []

    # Watch root directories themselves (new projects added)
    for root_str in roots:
        root = Path(root_str).expanduser().resolve()
        if root.is_dir():
            paths.append(root)
            # Watch each project dir for git changes
            try:
                for entry in root.iterdir():
                    if entry.is_dir() and not entry.name.startswith("."):
                        paths.append(entry)
                        # Watch .git dir if it exists (branch changes, commits)
                        git_dir = entry / ".git"
                        if git_dir.is_dir():
                            paths.append(git_dir)
            except OSError:
                pass

    # Watch Claude projects dir for new sessions
    if CLAUDE_PROJECTS_DIR.is_dir():
        paths.append(CLAUDE_PROJECTS_DIR)

    # Watch PipNav state files
    for state_file in ("sessions.json", "notes.json", "config.json"):
        sf = PIPNAV_STATE_DIR / state_file
        if sf.exists():
            paths.append(sf)

    return tuple(paths)


class FileWatcher:
    """Polls filesystem for changes and calls back when detected.

    Designed to run on a background thread. The callback is invoked
    on the watcher thread — use call_from_thread to post to the UI.
    """

    def __init__(
        self,
        roots: tuple[str, ...],
        interval_seconds: int = 10,
        on_change: Callable[[], None] | None = None,
    ) -> None:
        self._roots = roots
        self._interval = interval_seconds
        self._on_change = on_change
        self._last_snapshot: dict[str, float] = {}
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_change: datetime | None = None

    @property
    def roots(self) -> tuple[str, ...]:
        return self._roots

    @roots.setter
    def roots(self, value: tuple[str, ...]) -> None:
        self._roots = value
        # Reset snapshot so next poll detects everything as new
        self._last_snapshot = {}

    @property
    def last_change(self) -> datetime | None:
        return self._last_change

    def start(self) -> None:
        """Start the watcher thread."""
        if self._thread is not None and self._thread.is_alive():
            return

        self._stop_event.clear()
        # Take initial snapshot
        watched = _get_watched_paths(self._roots)
        self._last_snapshot = _snapshot_mtimes(watched)

        self._thread = threading.Thread(
            target=self._poll_loop,
            daemon=True,
            name="pipnav-watcher",
        )
        self._thread.start()

    def stop(self) -> None:
        """Stop the watcher thread."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None

    def _poll_loop(self) -> None:
        """Main polling loop — runs on background thread."""
        logger = get_logger()

        while not self._stop_event.is_set():
            self._stop_event.wait(timeout=self._interval)
            if self._stop_event.is_set():
                break

            try:
                watched = _get_watched_paths(self._roots)
                current = _snapshot_mtimes(watched)

                if self._has_changes(current):
                    self._last_snapshot = current
                    self._last_change = datetime.now()
                    logger.debug("Watcher detected changes")
                    if self._on_change is not None:
                        self._on_change()
                else:
                    self._last_snapshot = current
            except Exception as exc:
                logger.debug("Watcher poll error: %s", exc)

    def _has_changes(self, current: dict[str, float]) -> bool:
        """Compare current snapshot against last snapshot."""
        # New or removed paths
        if set(current.keys()) != set(self._last_snapshot.keys()):
            return True

        # Changed mtimes
        for path, mtime in current.items():
            if self._last_snapshot.get(path) != mtime:
                return True

        return False
