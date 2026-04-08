"""Tests for the polling-based file watcher."""

import time
from pathlib import Path
from typing import Callable

import pytest

from pipnav.core.watcher import FileWatcher, _get_watched_paths, _snapshot_mtimes


def _wait_for(
    predicate: Callable[[], bool],
    timeout: float = 3.0,
    interval: float = 0.05,
) -> None:
    """Poll until predicate returns True or timeout expires."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(interval)
    # Final check — let the assertion in the caller fail with context
    return


@pytest.fixture(autouse=True)
def _use_tmp_dirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Redirect watched dirs to temp."""
    import pipnav.core.watcher as w

    monkeypatch.setattr(w, "CLAUDE_PROJECTS_DIR", tmp_path / "claude" / "projects")
    monkeypatch.setattr(w, "PIPNAV_STATE_DIR", tmp_path / "pipnav")


class TestSnapshotMtimes:
    def test_snapshot_file(self, tmp_path: Path) -> None:
        f = tmp_path / "test.json"
        f.write_text("{}")
        result = _snapshot_mtimes((f,))
        assert str(f) in result

    def test_snapshot_dir(self, tmp_path: Path) -> None:
        result = _snapshot_mtimes((tmp_path,))
        assert str(tmp_path) in result

    def test_snapshot_nonexistent(self, tmp_path: Path) -> None:
        missing = tmp_path / "missing"
        result = _snapshot_mtimes((missing,))
        assert len(result) == 0

    def test_snapshot_multiple(self, tmp_path: Path) -> None:
        f1 = tmp_path / "a.json"
        f2 = tmp_path / "b.json"
        f1.write_text("{}")
        f2.write_text("{}")
        result = _snapshot_mtimes((f1, f2))
        assert len(result) == 2


class TestGetWatchedPaths:
    def test_watches_root_dir(self, tmp_path: Path) -> None:
        paths = _get_watched_paths((str(tmp_path),))
        assert tmp_path in paths

    def test_watches_project_subdirs(self, tmp_path: Path) -> None:
        project = tmp_path / "myproject"
        project.mkdir()
        paths = _get_watched_paths((str(tmp_path),))
        assert project in paths

    def test_watches_git_dirs(self, tmp_path: Path) -> None:
        project = tmp_path / "myproject"
        git_dir = project / ".git"
        git_dir.mkdir(parents=True)
        (git_dir / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
        paths = _get_watched_paths((str(tmp_path),))
        assert git_dir in paths
        assert git_dir / "HEAD" in paths

    def test_watches_claude_project_dirs_and_session_files(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import pipnav.core.watcher as w

        claude_root = tmp_path / "claude" / "projects"
        session_dir = claude_root / "-home-user-projects-demo"
        session_file = session_dir / "abc123.jsonl"
        session_dir.mkdir(parents=True)
        session_file.write_text("{}\n", encoding="utf-8")
        monkeypatch.setattr(w, "CLAUDE_PROJECTS_DIR", claude_root)

        paths = _get_watched_paths((str(tmp_path),))

        assert claude_root in paths
        assert session_dir in paths
        assert session_file in paths

    def test_skips_hidden_dirs(self, tmp_path: Path) -> None:
        hidden = tmp_path / ".hidden"
        hidden.mkdir()
        paths = _get_watched_paths((str(tmp_path),))
        assert hidden not in paths

    def test_nonexistent_root(self) -> None:
        paths = _get_watched_paths(("/nonexistent/root",))
        # Should not crash, just skip
        assert len(paths) == 0

    def test_watches_memory_state_file(self, tmp_path: Path) -> None:
        state_dir = tmp_path / "pipnav"
        state_dir.mkdir(parents=True)
        memory_file = state_dir / "memory.json"
        memory_file.write_text("{}", encoding="utf-8")

        paths = _get_watched_paths((str(tmp_path),))

        assert memory_file in paths


class TestFileWatcher:
    def test_start_and_stop(self, tmp_path: Path) -> None:
        watcher = FileWatcher(
            roots=(str(tmp_path),),
            interval_seconds=1,
        )
        watcher.start()
        assert watcher._thread is not None
        assert watcher._thread.is_alive()

        watcher.stop()
        assert watcher._thread is None

    def test_detects_new_file(self, tmp_path: Path) -> None:
        changes_detected: list[bool] = []

        def on_change() -> None:
            changes_detected.append(True)

        watcher = FileWatcher(
            roots=(str(tmp_path),),
            interval_seconds=1,
            on_change=on_change,
        )
        watcher.start()

        # Create a new project dir
        new_project = tmp_path / "new-project"
        new_project.mkdir()

        _wait_for(lambda: len(changes_detected) > 0)
        watcher.stop()

        assert len(changes_detected) > 0

    def test_detects_claude_session_file_append(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import pipnav.core.watcher as w

        claude_root = tmp_path / "claude" / "projects"
        session_dir = claude_root / "-home-user-projects-demo"
        session_file = session_dir / "abc123.jsonl"
        session_dir.mkdir(parents=True)
        session_file.write_text("{}\n", encoding="utf-8")
        monkeypatch.setattr(w, "CLAUDE_PROJECTS_DIR", claude_root)

        changes_detected: list[bool] = []

        def on_change() -> None:
            changes_detected.append(True)

        watcher = FileWatcher(
            roots=(str(tmp_path),),
            interval_seconds=1,
            on_change=on_change,
        )
        watcher.start()
        # Wait for initial snapshot to settle
        _wait_for(lambda: False, timeout=0.5)

        # Append to session file (simulates new message)
        with session_file.open("a", encoding="utf-8") as f:
            f.write("{\"type\":\"assistant\"}\n")

        _wait_for(lambda: len(changes_detected) > 0)
        watcher.stop()

        assert len(changes_detected) > 0

    def test_no_callback_when_no_changes(self, tmp_path: Path) -> None:
        changes_detected: list[bool] = []

        def on_change() -> None:
            changes_detected.append(True)

        watcher = FileWatcher(
            roots=(str(tmp_path),),
            interval_seconds=1,
            on_change=on_change,
        )
        watcher.start()
        _wait_for(lambda: False, timeout=2.5)
        watcher.stop()

        # No changes should have been detected
        assert len(changes_detected) == 0

    def test_roots_property(self, tmp_path: Path) -> None:
        watcher = FileWatcher(roots=(str(tmp_path),), interval_seconds=1)
        assert watcher.roots == (str(tmp_path),)

        new_root = str(tmp_path / "other")
        watcher.roots = (new_root,)
        assert watcher.roots == (new_root,)

    def test_double_start_is_safe(self, tmp_path: Path) -> None:
        watcher = FileWatcher(roots=(str(tmp_path),), interval_seconds=1)
        watcher.start()
        watcher.start()  # Should not create second thread
        watcher.stop()

    def test_last_change_initially_none(self, tmp_path: Path) -> None:
        watcher = FileWatcher(roots=(str(tmp_path),), interval_seconds=1)
        assert watcher.last_change is None
