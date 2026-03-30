"""Tests for fuzzy search."""

from pathlib import Path

from pipnav.core.projects import ProjectInfo
from pipnav.core.search import filter_projects, fuzzy_match


def test_fuzzy_match_exact() -> None:
    matched, score = fuzzy_match("foo", "foo")
    assert matched is True
    assert score > 0


def test_fuzzy_match_subsequence() -> None:
    matched, score = fuzzy_match("mca", "my-cool-app")
    assert matched is True


def test_fuzzy_match_no_match() -> None:
    matched, score = fuzzy_match("xyz", "abc")
    assert matched is False
    assert score == 0


def test_fuzzy_match_empty_query() -> None:
    matched, score = fuzzy_match("", "anything")
    assert matched is True
    assert score == 0


def test_fuzzy_match_case_insensitive() -> None:
    matched, _ = fuzzy_match("FOO", "foo-bar")
    assert matched is True


def _make_project(name: str) -> ProjectInfo:
    return ProjectInfo(name=name, path=Path(f"/tmp/{name}"), is_git_repo=False, last_modified=None)


def test_filter_projects() -> None:
    projects = (
        _make_project("my-cool-app"),
        _make_project("portfolio"),
        _make_project("api-service"),
    )
    result = filter_projects("api", projects)
    assert len(result) == 1
    assert result[0].name == "api-service"


def test_filter_projects_empty_query() -> None:
    projects = (_make_project("a"), _make_project("b"))
    result = filter_projects("", projects)
    assert len(result) == 2
