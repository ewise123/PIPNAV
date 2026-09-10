"""Tests for reading Codex session history.

Codex rollout files are written by another program and reach tens of megabytes,
so this reader only ever touches the first line. Everything here is a trust
boundary: a wrong answer means resuming the wrong session, which is silent.
"""

import json
from datetime import datetime

import pytest

from pipnav.core import codex_sessions


@pytest.fixture
def sessions_dir(tmp_path, monkeypatch):
    root = tmp_path / "sessions"
    root.mkdir()
    monkeypatch.setattr(codex_sessions, "SESSIONS_DIR", root)
    return root


def write_rollout(
    sessions_dir,
    session_id="01a08217-6ebc-7a52-b7af-7d26812465c7",
    cwd="/home/ewise/projects/PIPNAV",
    timestamp="2026-09-08T17:36:08.892Z",
    day="2026/09/08",
    extra_lines=(),
    first_line=None,
):
    day_dir = sessions_dir / day
    day_dir.mkdir(parents=True, exist_ok=True)
    path = day_dir / f"rollout-{timestamp[:10]}-{session_id}.jsonl"

    if first_line is None:
        first_line = json.dumps({
            "timestamp": timestamp,
            "type": "session_meta",
            "payload": {"id": session_id, "cwd": cwd, "timestamp": timestamp},
        })
    path.write_text("\n".join([first_line, *extra_lines]) + "\n", encoding="utf-8")
    return path


def test_reads_id_and_cwd_from_the_first_line(sessions_dir):
    write_rollout(sessions_dir)
    sessions = codex_sessions.discover_sessions()

    assert len(sessions) == 1
    s = sessions[0]
    assert s.session_id == "01a08217-6ebc-7a52-b7af-7d26812465c7"
    assert s.project_path == "/home/ewise/projects/PIPNAV"
    assert s.last_active.year == 2026


def test_never_reads_past_the_first_line(sessions_dir):
    """Later lines are irrelevant, and rollouts get huge. Garbage must not matter."""
    write_rollout(sessions_dir, extra_lines=["{ this is not json", "\x00\x00binary"])
    assert len(codex_sessions.discover_sessions()) == 1


def test_ignores_a_file_whose_first_line_is_not_session_meta(sessions_dir):
    write_rollout(
        sessions_dir,
        first_line=json.dumps({"type": "event_msg", "payload": {}}),
    )
    assert codex_sessions.discover_sessions() == ()


def test_ignores_malformed_json(sessions_dir):
    write_rollout(sessions_dir, first_line="{not json at all")
    assert codex_sessions.discover_sessions() == ()


def test_ignores_an_empty_file(sessions_dir):
    day = sessions_dir / "2026" / "09" / "08"
    day.mkdir(parents=True)
    (day / "rollout-2026-09-08-abc.jsonl").write_text("", encoding="utf-8")
    assert codex_sessions.discover_sessions() == ()


def test_ignores_a_session_with_no_id(sessions_dir):
    write_rollout(
        sessions_dir,
        first_line=json.dumps({
            "type": "session_meta",
            "payload": {"cwd": "/x", "timestamp": "2026-09-08T17:36:08.892Z"},
        }),
    )
    assert codex_sessions.discover_sessions() == ()


def test_keeps_a_session_with_no_cwd_but_marks_it_unknown(sessions_dir):
    """Resuming still works without a cwd; it just cannot be matched to a project."""
    write_rollout(
        sessions_dir,
        first_line=json.dumps({
            "type": "session_meta",
            "payload": {"id": "abc-123", "timestamp": "2026-09-08T17:36:08.892Z"},
        }),
    )
    sessions = codex_sessions.discover_sessions()
    assert len(sessions) == 1
    assert sessions[0].project_path == ""


def test_falls_back_to_file_mtime_when_the_timestamp_is_unusable(sessions_dir):
    write_rollout(
        sessions_dir,
        first_line=json.dumps({
            "type": "session_meta",
            "payload": {"id": "abc-123", "cwd": "/x", "timestamp": "not a date"},
        }),
    )
    sessions = codex_sessions.discover_sessions()
    assert len(sessions) == 1
    assert isinstance(sessions[0].last_active, datetime)


def test_missing_sessions_directory_is_not_an_error(tmp_path, monkeypatch):
    monkeypatch.setattr(codex_sessions, "SESSIONS_DIR", tmp_path / "absent")
    assert codex_sessions.discover_sessions() == ()


def test_newest_first(sessions_dir):
    write_rollout(sessions_dir, session_id="old", timestamp="2026-09-01T10:00:00.000Z",
                  day="2026/09/01")
    write_rollout(sessions_dir, session_id="new", timestamp="2026-09-08T10:00:00.000Z",
                  day="2026/09/08")
    assert [s.session_id for s in codex_sessions.discover_sessions()] == ["new", "old"]


def test_filters_to_one_project(sessions_dir):
    write_rollout(sessions_dir, session_id="here", cwd="/home/ewise/projects/PIPNAV",
                  day="2026/09/08")
    write_rollout(sessions_dir, session_id="elsewhere", cwd="/tmp",
                  timestamp="2026-09-07T10:00:00.000Z", day="2026/09/07")

    from pathlib import Path
    got = codex_sessions.discover_sessions_for_project(
        Path("/home/ewise/projects/PIPNAV")
    )
    assert [s.session_id for s in got] == ["here"]


def test_project_filter_ignores_a_trailing_slash(sessions_dir):
    write_rollout(sessions_dir, cwd="/home/ewise/projects/PIPNAV/")
    from pathlib import Path
    got = codex_sessions.discover_sessions_for_project(
        Path("/home/ewise/projects/PIPNAV")
    )
    assert len(got) == 1
