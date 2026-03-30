"""Tests for session tracking."""

from datetime import datetime
from pathlib import Path

import pytest

from pipnav.core.sessions import (
    SessionInfo,
    load_sessions,
    record_session,
    save_sessions,
)


@pytest.fixture(autouse=True)
def _use_tmp_sessions(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Redirect sessions to a temp directory."""
    import pipnav.core.sessions as mod

    monkeypatch.setattr(mod, "SESSIONS_PATH", tmp_path / "sessions.json")


def test_load_empty() -> None:
    sessions = load_sessions()
    assert sessions == {}


def test_save_and_load_round_trip() -> None:
    now = datetime(2025, 3, 28, 14, 0, 0)
    sessions = {"/tmp/proj": SessionInfo(last_session=now, resumable=True)}
    save_sessions(sessions)
    loaded = load_sessions()
    assert loaded["/tmp/proj"].resumable is True
    assert loaded["/tmp/proj"].last_session == now


def test_record_session() -> None:
    sessions = record_session(Path("/tmp/proj"))
    assert "/tmp/proj" in sessions
    assert sessions["/tmp/proj"].resumable is True
