"""Tests for git integration."""

import subprocess
from pathlib import Path

import pytest

from pipnav.core.git import compute_badge, get_git_log, get_git_status


@pytest.fixture()
def git_repo(tmp_path: Path) -> Path:
    """Create a temporary git repo with one commit."""
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    subprocess.run(["git", "init"], cwd=repo_path, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=repo_path,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=repo_path,
        capture_output=True,
    )
    (repo_path / "file.txt").write_text("hello")
    subprocess.run(["git", "add", "."], cwd=repo_path, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=repo_path,
        capture_output=True,
    )
    return repo_path


def test_get_git_status_basic(git_repo: Path) -> None:
    status = get_git_status(git_repo)
    assert status is not None
    assert status.branch == "main" or status.branch == "master"
    assert status.modified_count == 0
    assert status.is_dirty is False


def test_get_git_status_dirty(git_repo: Path) -> None:
    (git_repo / "file.txt").write_text("changed")
    status = get_git_status(git_repo)
    assert status is not None
    assert status.modified_count >= 1
    assert status.is_dirty is True


def test_get_git_status_untracked(git_repo: Path) -> None:
    (git_repo / "new.txt").write_text("new file")
    status = get_git_status(git_repo)
    assert status is not None
    assert status.untracked_count >= 1


def test_get_git_status_not_a_repo(tmp_path: Path) -> None:
    status = get_git_status(tmp_path)
    assert status is None


def test_get_git_log(git_repo: Path) -> None:
    entries = get_git_log(git_repo)
    assert len(entries) >= 1
    assert entries[0].message == "Initial commit"


def test_get_git_log_not_a_repo(tmp_path: Path) -> None:
    entries = get_git_log(tmp_path)
    assert entries == ()


def test_compute_badge_no_git() -> None:
    assert compute_badge(None, False, False) == "[?]"


def test_compute_badge_session() -> None:
    from pipnav.core.git import GitStatus

    gs = GitStatus("main", 0, 0, 0, 0, 0, None, False)
    assert compute_badge(gs, True, False) == "[S]"


def test_compute_badge_unpushed() -> None:
    from pipnav.core.git import GitStatus

    gs = GitStatus("main", 0, 0, 0, 3, 0, None, False)
    assert compute_badge(gs, False, False) == "[!U]"


def test_compute_badge_dirty() -> None:
    from pipnav.core.git import GitStatus

    gs = GitStatus("main", 2, 0, 0, 0, 0, None, True)
    assert compute_badge(gs, False, False) == "[!M]"


def test_compute_badge_stale() -> None:
    from pipnav.core.git import GitStatus

    gs = GitStatus("main", 0, 0, 0, 0, 0, None, False)
    assert compute_badge(gs, False, True) == "[~]"


def test_compute_badge_clean() -> None:
    from pipnav.core.git import GitStatus

    gs = GitStatus("main", 0, 0, 0, 0, 0, None, False)
    assert compute_badge(gs, False, False) == "[✓]"


def test_compute_badge_multiple() -> None:
    from pipnav.core.git import GitStatus

    gs = GitStatus("main", 2, 0, 0, 3, 0, None, True)
    assert compute_badge(gs, True, False) == "[S][!U][!M]"
