"""Tests for the background project indexer."""

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from pipnav.core.git import GitStatus
from pipnav.core.indexer import (
    CACHE_VERSION,
    CachedProjectState,
    IndexCache,
    ProjectIndexer,
    load_cache,
    save_cache,
)


@pytest.fixture(autouse=True)
def _use_tmp_dirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Redirect cache and project dirs to temp."""
    import pipnav.core.indexer as idx
    import pipnav.core.config as cfg

    monkeypatch.setattr(cfg, "PIPNAV_DIR", tmp_path)
    monkeypatch.setattr(idx, "CACHE_PATH", tmp_path / "cache.json")


def _make_git_status(**overrides: object) -> GitStatus:
    defaults = {
        "branch": "main",
        "modified_count": 0,
        "staged_count": 0,
        "untracked_count": 0,
        "ahead": 0,
        "behind": 0,
        "last_commit_time": datetime(2026, 1, 15, 10, 30),
        "is_dirty": False,
    }
    defaults.update(overrides)
    return GitStatus(**defaults)


def _make_cached_state(
    path: str = "/home/user/projects/test",
    name: str = "test",
    **overrides: object,
) -> CachedProjectState:
    defaults = {
        "project_path": path,
        "project_name": name,
        "is_git_repo": True,
        "git_status": _make_git_status(),
        "session_count": 2,
        "last_modified_ts": 1700000000.0,
        "last_indexed": datetime(2026, 3, 31, 12, 0),
    }
    defaults.update(overrides)
    return CachedProjectState(**defaults)


def _make_cache(**overrides: object) -> IndexCache:
    defaults = {
        "version": CACHE_VERSION,
        "roots": (str(Path("~/projects").expanduser().resolve()),),
        "projects": (_make_cached_state(),),
        "last_full_scan": datetime(2026, 3, 31, 12, 0),
    }
    defaults.update(overrides)
    return IndexCache(**defaults)


class TestCacheSerialization:
    def test_save_and_load_round_trip(self) -> None:
        cache = _make_cache()
        save_cache(cache)
        loaded = load_cache()

        assert loaded is not None
        assert loaded.version == CACHE_VERSION
        assert len(loaded.projects) == 1
        assert loaded.projects[0].project_path == "/home/user/projects/test"
        assert loaded.projects[0].project_name == "test"
        assert loaded.projects[0].session_count == 2

    def test_git_status_survives_round_trip(self) -> None:
        gs = _make_git_status(branch="feature", modified_count=3, is_dirty=True)
        cache = _make_cache(
            projects=(_make_cached_state(git_status=gs),),
        )
        save_cache(cache)
        loaded = load_cache()

        assert loaded is not None
        loaded_gs = loaded.projects[0].git_status
        assert loaded_gs is not None
        assert loaded_gs.branch == "feature"
        assert loaded_gs.modified_count == 3
        assert loaded_gs.is_dirty is True

    def test_none_git_status_round_trip(self) -> None:
        cache = _make_cache(
            projects=(_make_cached_state(git_status=None, is_git_repo=False),),
        )
        save_cache(cache)
        loaded = load_cache()

        assert loaded is not None
        assert loaded.projects[0].git_status is None

    def test_load_returns_none_when_missing(self) -> None:
        assert load_cache() is None

    def test_load_returns_none_for_corrupt_json(self, tmp_path: Path) -> None:
        import pipnav.core.indexer as idx

        idx.CACHE_PATH.write_text("not json!", encoding="utf-8")
        assert load_cache() is None

    def test_load_returns_none_for_version_mismatch(self) -> None:
        import pipnav.core.indexer as idx

        data = {"version": 999, "projects": [], "last_full_scan": "2026-01-01T00:00:00"}
        idx.CACHE_PATH.write_text(json.dumps(data), encoding="utf-8")
        assert load_cache() is None

    def test_multiple_projects(self) -> None:
        states = (
            _make_cached_state("/home/user/projects/a", "a"),
            _make_cached_state("/home/user/projects/b", "b", session_count=5),
        )
        cache = _make_cache(projects=states)
        save_cache(cache)
        loaded = load_cache()

        assert loaded is not None
        assert len(loaded.projects) == 2
        assert loaded.projects[1].session_count == 5


class TestProjectIndexer:
    def test_warm_start_with_no_cache(self) -> None:
        indexer = ProjectIndexer(roots=("~/nonexistent",), ttl_seconds=60)
        result = indexer.warm_start()
        assert result is None

    def test_warm_start_loads_existing_cache(self) -> None:
        cache = _make_cache()
        save_cache(cache)

        indexer = ProjectIndexer(roots=("~/projects",), ttl_seconds=60)
        result = indexer.warm_start()

        assert result is not None
        assert len(result.projects) == 1

    def test_warm_start_ignores_cache_for_other_roots(self) -> None:
        cache = _make_cache(roots=(str(Path("/tmp/other").resolve()),))
        save_cache(cache)

        indexer = ProjectIndexer(roots=("~/projects",), ttl_seconds=60)
        result = indexer.warm_start()

        assert result is None
        assert indexer.cache is None

    def test_get_git_statuses_empty_when_no_cache(self) -> None:
        indexer = ProjectIndexer(roots=("~/projects",), ttl_seconds=60)
        assert indexer.get_git_statuses() == {}

    def test_get_git_statuses_from_cache(self) -> None:
        gs = _make_git_status(branch="develop")
        cache = _make_cache(
            projects=(_make_cached_state(git_status=gs),),
        )
        save_cache(cache)

        indexer = ProjectIndexer(roots=("~/projects",), ttl_seconds=60)
        indexer.warm_start()

        statuses = indexer.get_git_statuses()
        assert "/home/user/projects/test" in statuses
        assert statuses["/home/user/projects/test"].branch == "develop"

    def test_get_projects_from_cache(self) -> None:
        cache = _make_cache()
        save_cache(cache)

        indexer = ProjectIndexer(roots=("~/projects",), ttl_seconds=60)
        indexer.warm_start()

        projects = indexer.get_projects()
        assert len(projects) == 1
        assert projects[0].name == "test"
        assert projects[0].path == Path("/home/user/projects/test")

    def test_get_session_counts(self) -> None:
        cache = _make_cache(
            projects=(
                _make_cached_state("/a", "a", session_count=3),
                _make_cached_state("/b", "b", session_count=0),
            ),
        )
        save_cache(cache)

        indexer = ProjectIndexer(roots=("~/projects",), ttl_seconds=60)
        indexer.warm_start()

        counts = indexer.get_session_counts()
        assert counts["/a"] == 3
        assert counts["/b"] == 0

    def test_invalidate_clears_cache(self) -> None:
        cache = _make_cache()
        save_cache(cache)

        indexer = ProjectIndexer(roots=("~/projects",), ttl_seconds=60)
        indexer.warm_start()
        assert indexer.cache is not None

        indexer.invalidate()
        assert indexer.cache is None

    def test_last_scan_time_set_after_warm_start(self) -> None:
        cache = _make_cache()
        save_cache(cache)

        indexer = ProjectIndexer(roots=("~/projects",), ttl_seconds=60)
        indexer.warm_start()

        # warm_start sets last_refreshed from cache timestamp
        assert indexer.last_scan_time() is not None

    def test_last_scan_time_none_when_no_cache(self) -> None:
        indexer = ProjectIndexer(roots=("~/projects",), ttl_seconds=60)
        assert indexer.last_scan_time() is None

    def test_roots_property(self) -> None:
        indexer = ProjectIndexer(roots=("~/a",), ttl_seconds=60)
        assert indexer.roots == ("~/a",)
        indexer.roots = ("~/b",)
        assert indexer.roots == ("~/b",)
