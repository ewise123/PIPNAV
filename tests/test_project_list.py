"""Targeted tests for project list refresh behavior."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

from pipnav.ui.project_list import ProjectEntry, ProjectList


class _FakeProjectOptionList:
    def __init__(self) -> None:
        self.highlighted: int | None = None
        self.options: list[object] = []

    def clear_options(self) -> None:
        self.options.clear()
        self.highlighted = None

    def add_option(self, option: object) -> None:
        self.options.append(option)

    @contextmanager
    def prevent(self, *_message_types: object):
        yield


def test_set_projects_preserves_selected_path_without_user_navigation(
    monkeypatch,
) -> None:
    project_list = ProjectList()
    option_list = _FakeProjectOptionList()
    old_entries = (
        ProjectEntry("alpha", Path("/tmp/alpha"), "[ ]"),
        ProjectEntry("beta", Path("/tmp/beta"), "[ ]"),
    )
    new_entries = (
        ProjectEntry("alpha", Path("/tmp/alpha"), "[ ]"),
        ProjectEntry("beta", Path("/tmp/beta"), "[!]"),
        ProjectEntry("gamma", Path("/tmp/gamma"), "[ ]"),
    )
    calls: list[tuple[int, bool]] = []

    project_list._entries = old_entries
    option_list.highlighted = 1

    monkeypatch.setattr(project_list, "query_one", lambda *args, **kwargs: option_list)
    monkeypatch.setattr(
        project_list,
        "_fire_selected",
        lambda index, user_initiated=True: calls.append((index, user_initiated)),
    )

    project_list.set_projects(new_entries)

    assert option_list.highlighted == 1
    assert len(option_list.options) == 3
    assert calls == [(1, False)]


def test_set_projects_falls_back_to_previous_index_when_path_disappears(
    monkeypatch,
) -> None:
    project_list = ProjectList()
    option_list = _FakeProjectOptionList()
    old_entries = (
        ProjectEntry("alpha", Path("/tmp/alpha"), "[ ]"),
        ProjectEntry("beta", Path("/tmp/beta"), "[ ]"),
        ProjectEntry("gamma", Path("/tmp/gamma"), "[ ]"),
    )
    new_entries = (
        ProjectEntry("alpha", Path("/tmp/alpha"), "[ ]"),
        ProjectEntry("delta", Path("/tmp/delta"), "[ ]"),
        ProjectEntry("epsilon", Path("/tmp/epsilon"), "[ ]"),
    )
    calls: list[tuple[int, bool]] = []

    project_list._entries = old_entries
    option_list.highlighted = 2

    monkeypatch.setattr(project_list, "query_one", lambda *args, **kwargs: option_list)
    monkeypatch.setattr(
        project_list,
        "_fire_selected",
        lambda index, user_initiated=True: calls.append((index, user_initiated)),
    )

    project_list.set_projects(new_entries)

    assert option_list.highlighted == 2
    assert calls == [(2, False)]


def test_set_projects_defaults_to_first_entry_without_prior_selection(
    monkeypatch,
) -> None:
    project_list = ProjectList()
    option_list = _FakeProjectOptionList()
    entries = (
        ProjectEntry("alpha", Path("/tmp/alpha"), "[ ]"),
        ProjectEntry("beta", Path("/tmp/beta"), "[ ]"),
    )
    calls: list[tuple[int, bool]] = []

    monkeypatch.setattr(project_list, "query_one", lambda *args, **kwargs: option_list)
    monkeypatch.setattr(
        project_list,
        "_fire_selected",
        lambda index, user_initiated=True: calls.append((index, user_initiated)),
    )

    project_list.set_projects(entries)

    assert option_list.highlighted == 0
    assert calls == [(0, False)]
