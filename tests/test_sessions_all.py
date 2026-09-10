"""Tests for merging session history across all three coding tools.

The merge decides what `r` resumes, so getting it wrong resumes the wrong
session in the wrong tool — silent, and annoying to diagnose after the fact.
"""

from datetime import datetime
from pathlib import Path

import pytest

from pipnav.core import sessions_all
from pipnav.core.claude_sessions import ClaudeSession
from pipnav.core.codex_sessions import CodexSession
from pipnav.core.opencode_sessions import OpenCodeSession

PROJECT = Path("/home/ewise/projects/PIPNAV")


def _claude(session_id, when, name="Fix the fleet view"):
    return ClaudeSession(
        session_id=session_id, project_path=str(PROJECT), timestamp=when,
        last_activity=when, session_name=name, first_message="hello",
        message_count=12,
    )


def _codex(session_id, when):
    return CodexSession(
        session_id=session_id, project_path=str(PROJECT), title="PIPNAV",
        last_active=when,
    )


def _opencode(session_id, when, cost=0.0):
    return OpenCodeSession(
        session_id=session_id, project_path=str(PROJECT), title="Wire up export",
        last_active=when, cost=cost,
    )


@pytest.fixture
def stub(monkeypatch):
    """Stub all three readers. Returns a setter."""
    def set_sources(claude=(), codex=(), opencode=()):
        monkeypatch.setattr(
            sessions_all.claude_sessions, "discover_sessions_for_project",
            lambda _p: tuple(claude),
        )
        monkeypatch.setattr(
            sessions_all.codex_sessions, "discover_sessions_for_project",
            lambda _p: tuple(codex),
        )
        monkeypatch.setattr(
            sessions_all.opencode_sessions, "discover_sessions_for_project",
            lambda _p: tuple(opencode),
        )
    return set_sources


def test_merges_all_three_tools(stub):
    when = datetime(2026, 9, 8, 12, 0)
    stub(claude=[_claude("c1", when)], codex=[_codex("x1", when)],
         opencode=[_opencode("o1", when)])

    got = sessions_all.sessions_for_project(PROJECT)
    assert sorted(s.harness for s in got) == ["claude", "codex", "opencode"]


def test_newest_first_across_tools(stub):
    stub(
        claude=[_claude("c_old", datetime(2026, 9, 1, 9, 0))],
        codex=[_codex("x_newest", datetime(2026, 9, 9, 9, 0))],
        opencode=[_opencode("o_mid", datetime(2026, 9, 5, 9, 0))],
    )
    got = sessions_all.sessions_for_project(PROJECT)
    assert [s.session_id for s in got] == ["x_newest", "o_mid", "c_old"]


def test_carries_the_resume_command_for_each_tool(stub):
    when = datetime(2026, 9, 8, 12, 0)
    stub(claude=[_claude("c1", when)], codex=[_codex("x1", when)],
         opencode=[_opencode("o1", when)])

    by_harness = {s.harness: s for s in sessions_all.sessions_for_project(PROJECT)}
    assert by_harness["claude"].resume_argv() == ("--resume", "c1")
    assert by_harness["codex"].resume_argv() == ("resume", "x1")
    assert by_harness["opencode"].resume_argv() == ("-s", "o1")


def test_prefers_a_claude_session_name_over_its_first_message(stub):
    when = datetime(2026, 9, 8, 12, 0)
    stub(claude=[_claude("c1", when, name="Named session")])
    assert sessions_all.sessions_for_project(PROJECT)[0].title == "Named session"


def test_falls_back_to_the_first_message_when_unnamed(stub):
    when = datetime(2026, 9, 8, 12, 0)
    stub(claude=[_claude("c1", when, name="")])
    assert sessions_all.sessions_for_project(PROJECT)[0].title == "hello"


def test_carries_opencode_cost(stub):
    when = datetime(2026, 9, 8, 12, 0)
    stub(opencode=[_opencode("o1", when, cost=0.42)])
    assert sessions_all.sessions_for_project(PROJECT)[0].cost == 0.42


def test_no_sessions_anywhere_is_empty_not_an_error(stub):
    stub()
    assert sessions_all.sessions_for_project(PROJECT) == ()


def test_one_broken_reader_does_not_lose_the_others(stub, monkeypatch):
    """A reader blowing up must not hide the tools that are working."""
    when = datetime(2026, 9, 8, 12, 0)
    stub(claude=[_claude("c1", when)])

    def boom(_path):
        raise RuntimeError("codex store unreadable")

    monkeypatch.setattr(
        sessions_all.codex_sessions, "discover_sessions_for_project", boom
    )
    got = sessions_all.sessions_for_project(PROJECT)
    assert [s.session_id for s in got] == ["c1"]


# --- latest_for_project: what `r` actually resumes ---------------------------


def test_latest_picks_the_newest_regardless_of_tool(stub):
    stub(
        claude=[_claude("c1", datetime(2026, 9, 1, 9, 0))],
        opencode=[_opencode("o1", datetime(2026, 9, 9, 9, 0))],
    )
    latest = sessions_all.latest_for_project(PROJECT)
    assert latest.session_id == "o1"
    assert latest.harness == "opencode"


def test_latest_is_none_when_there_is_nothing(stub):
    stub()
    assert sessions_all.latest_for_project(PROJECT) is None


# --- live matching -----------------------------------------------------------
#
# herdr records a session reference for agents it recognises. Matching on it is
# how a row gets marked LIVE. When herdr reports no reference we mark nothing —
# a false LIVE badge is worse than no badge.


def test_live_keys_pairs_harness_with_session_id(monkeypatch):
    from pipnav.core.herdr import HerdrAgent

    monkeypatch.setattr(
        sessions_all.herdr, "list_agents",
        lambda: (
            HerdrAgent("w1:p1", "w1:t1", "w1", "claude", "Claude Code", "working",
                       PROJECT, "", "c1", "id", False),
            HerdrAgent("w2:p1", "w2:t1", "w2", "codex", "Codex", "blocked",
                       PROJECT, "", "x1", "id", False),
        ),
    )
    assert sessions_all.live_keys() == frozenset(
        {("claude", "c1"), ("codex", "x1")}
    )


def test_live_keys_ignores_an_agent_with_no_session_reference(monkeypatch):
    """herdr has not seen a session id yet — claiming LIVE would be a guess."""
    from pipnav.core.herdr import HerdrAgent

    monkeypatch.setattr(
        sessions_all.herdr, "list_agents",
        lambda: (
            HerdrAgent("w1:p1", "w1:t1", "w1", "claude", "Claude Code", "working",
                       PROJECT, "", "", "", False),
        ),
    )
    assert sessions_all.live_keys() == frozenset()


def test_live_keys_ignores_a_path_style_reference(monkeypatch):
    """Only id-kind references match a session id."""
    from pipnav.core.herdr import HerdrAgent

    monkeypatch.setattr(
        sessions_all.herdr, "list_agents",
        lambda: (
            HerdrAgent("w1:p1", "w1:t1", "w1", "claude", "Claude Code", "working",
                       PROJECT, "", "/some/path", "path", False),
        ),
    )
    assert sessions_all.live_keys() == frozenset()


def test_live_keys_empty_when_herdr_is_not_running(monkeypatch):
    monkeypatch.setattr(sessions_all.herdr, "list_agents", lambda: ())
    assert sessions_all.live_keys() == frozenset()


def test_live_keys_survives_herdr_blowing_up(monkeypatch):
    def boom():
        raise RuntimeError("socket gone")

    monkeypatch.setattr(sessions_all.herdr, "list_agents", boom)
    assert sessions_all.live_keys() == frozenset()


# --- across projects ---------------------------------------------------------


def test_sessions_for_projects_merges_and_orders(stub):
    other = Path("/home/ewise/projects/scratch")

    def per_project(path):
        if path == PROJECT:
            return (_claude("c_pipnav", datetime(2026, 9, 8, 9, 0)),)
        return (_claude("c_scratch", datetime(2026, 9, 9, 9, 0)),)

    import pipnav.core.claude_sessions as cs
    import pipnav.core.codex_sessions as cx
    import pipnav.core.opencode_sessions as oc
    stub()  # zero everything first
    for mod in (cx, oc):
        setattr(mod, "discover_sessions_for_project", lambda _p: ())
    cs.discover_sessions_for_project = per_project

    got = sessions_all.sessions_for_projects((PROJECT, other))
    assert [s.session_id for s in got] == ["c_scratch", "c_pipnav"]
