"""Tests for project discovery."""

from pathlib import Path

import pytest

from pipnav.core.projects import discover_projects, is_stale


@pytest.fixture()
def project_tree(tmp_path: Path) -> Path:
    """Create a mock project directory tree."""
    (tmp_path / "alpha").mkdir()
    (tmp_path / "beta").mkdir()
    (tmp_path / "beta" / ".git").mkdir()
    (tmp_path / ".hidden").mkdir()
    (tmp_path / "file.txt").touch()
    return tmp_path


def test_discover_finds_subdirs(project_tree: Path) -> None:
    projects = discover_projects((str(project_tree),))
    names = [p.name for p in projects]
    assert "alpha" in names
    assert "beta" in names


def test_discover_skips_hidden(project_tree: Path) -> None:
    projects = discover_projects((str(project_tree),))
    names = [p.name for p in projects]
    assert ".hidden" not in names


def test_discover_skips_files(project_tree: Path) -> None:
    projects = discover_projects((str(project_tree),))
    names = [p.name for p in projects]
    assert "file.txt" not in names


def test_discover_detects_git(project_tree: Path) -> None:
    projects = discover_projects((str(project_tree),))
    by_name = {p.name: p for p in projects}
    assert by_name["beta"].is_git_repo is True
    assert by_name["alpha"].is_git_repo is False


def test_discover_handles_missing_root() -> None:
    projects = discover_projects(("/nonexistent/path",))
    assert projects == ()


def test_discover_sorted_by_name(project_tree: Path) -> None:
    projects = discover_projects((str(project_tree),))
    names = [p.name for p in projects]
    assert names == sorted(names, key=str.lower)


def test_is_stale() -> None:
    from datetime import datetime, timedelta

    from pipnav.core.projects import ProjectInfo

    recent = ProjectInfo(
        name="recent",
        path=Path("/tmp/recent"),
        is_git_repo=False,
        last_modified=datetime.now() - timedelta(days=5),
    )
    assert is_stale(recent, 30) is False

    old = ProjectInfo(
        name="old",
        path=Path("/tmp/old"),
        is_git_repo=False,
        last_modified=datetime.now() - timedelta(days=60),
    )
    assert is_stale(old, 30) is True
