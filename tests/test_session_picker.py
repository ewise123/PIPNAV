"""Tests for the resumable-session picker.

Layout and key wiring are not tested — those you catch by looking at the screen.
What is tested is the mapping from a chosen row back to a session: pick the
wrong one and PipNav silently reopens something you did not ask for.
"""

from datetime import datetime, timedelta

from pipnav.core.sessions_all import AgentSession
from pipnav.ui.session_picker import SessionPicker

NOW = datetime.now()


def _session(harness, session_id, title="Wire up the export", minutes=5, cost=0.0):
    return AgentSession(
        harness=harness,
        session_id=session_id,
        project_path="/home/ewise/projects/PIPNAV",
        title=title,
        last_active=NOW - timedelta(minutes=minutes),
        cost=cost,
    )


SESSIONS = (
    _session("claude", "c1", "Fix the fleet view", minutes=4),
    _session("codex", "x1", "Approve the migration", minutes=40),
    _session("opencode", "o1", "Refactor the indexer", minutes=200, cost=0.42),
)


def test_maps_each_row_back_to_its_session():
    picker = SessionPicker(SESSIONS, "PIPNAV")
    assert [picker.session_at(i).session_id for i in range(3)] == ["c1", "x1", "o1"]


def test_out_of_range_row_is_none_not_a_crash():
    picker = SessionPicker(SESSIONS, "PIPNAV")
    assert picker.session_at(3) is None
    assert picker.session_at(-1) is None


def test_empty_list_maps_to_nothing():
    picker = SessionPicker((), "PIPNAV")
    assert picker.session_at(0) is None


# --- row content -------------------------------------------------------------


def test_row_names_the_tool():
    label, _ = SessionPicker.session_row(_session("opencode", "o1"))
    assert "OpenCode" in label


def test_row_shows_the_title():
    label, _ = SessionPicker.session_row(_session("claude", "c1", "Fix the fleet view"))
    assert "Fix the fleet view" in label


def test_row_shows_how_long_ago():
    _, detail = SessionPicker.session_row(_session("claude", "c1", minutes=40))
    assert "40m" in detail


def test_row_shows_cost_only_when_there_is_one():
    _, with_cost = SessionPicker.session_row(_session("opencode", "o1", cost=0.42))
    _, free = SessionPicker.session_row(_session("claude", "c1", cost=0.0))
    assert "0.42" in with_cost
    assert "$" not in free


def test_row_survives_an_empty_title():
    label, _ = SessionPicker.session_row(_session("codex", "x1", title=""))
    assert label.strip()


def test_row_truncates_a_very_long_title():
    long_title = "x" * 300
    label, _ = SessionPicker.session_row(_session("claude", "c1", title=long_title))
    assert len(label) < 200


def test_selecting_a_row_carries_that_session_not_the_newest():
    """The regression that matters: row 3 must resume session 3."""
    picker = SessionPicker(SESSIONS, "PIPNAV")
    chosen = picker.session_at(2)
    assert chosen.harness == "opencode"
    assert chosen.resume_argv() == ("-s", "o1")


def test_a_single_session_still_maps():
    picker = SessionPicker((SESSIONS[1],), "PIPNAV")
    assert picker.session_at(0).session_id == "x1"
    assert picker.session_at(1) is None
