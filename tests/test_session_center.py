"""Tests for the session control center."""

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from pipnav.core.claude_sessions import ClaudeSession
from pipnav.core.session_center import (
    ACTIVE_THRESHOLD_SECONDS,
    IDLE_MESSAGE_THRESHOLD,
    STALE_THRESHOLD_SECONDS,
    EnrichedSession,
    classify_session_status,
    enrich_session,
    filter_sessions,
    format_age,
    sort_sessions,
)


def _make_claude_session(**overrides: object) -> ClaudeSession:
    defaults = {
        "session_id": "abc123",
        "project_path": "/home/user/projects/test",
        "timestamp": datetime.now(),
        "first_message": "Fix the login bug",
        "message_count": 10,
    }
    defaults.update(overrides)
    return ClaudeSession(**defaults)


def _make_enriched(**overrides: object) -> EnrichedSession:
    defaults = {
        "session_id": "abc123",
        "project_path": "/home/user/projects/test",
        "project_name": "test",
        "branch": "main",
        "status": "resumable",
        "last_prompt": "Fix the login bug",
        "message_count": 10,
        "age_seconds": 3600,
        "timestamp": datetime.now() - timedelta(hours=1),
    }
    defaults.update(overrides)
    return EnrichedSession(**defaults)


class TestClassifySessionStatus:
    def test_active_when_recent(self) -> None:
        session = _make_claude_session(message_count=5)
        assert classify_session_status(session, age_seconds=300) == "active"

    def test_active_at_boundary(self) -> None:
        session = _make_claude_session(message_count=5)
        assert classify_session_status(
            session, age_seconds=ACTIVE_THRESHOLD_SECONDS - 1
        ) == "active"

    def test_stale_when_old(self) -> None:
        session = _make_claude_session(message_count=5)
        assert classify_session_status(
            session, age_seconds=STALE_THRESHOLD_SECONDS + 1
        ) == "stale"

    def test_idle_with_few_messages(self) -> None:
        session = _make_claude_session(
            message_count=IDLE_MESSAGE_THRESHOLD - 1
        )
        age = ACTIVE_THRESHOLD_SECONDS + 100
        assert classify_session_status(session, age_seconds=age) == "idle"

    def test_resumable_default(self) -> None:
        session = _make_claude_session(message_count=10)
        age = ACTIVE_THRESHOLD_SECONDS + 100
        assert classify_session_status(session, age_seconds=age) == "resumable"


class TestEnrichSession:
    def test_enriches_with_project_context(self) -> None:
        session = _make_claude_session(
            timestamp=datetime.now() - timedelta(minutes=5)
        )
        enriched = enrich_session(session, "my-project", "feat/login")

        assert enriched.project_name == "my-project"
        assert enriched.branch == "feat/login"
        assert enriched.session_id == session.session_id
        assert enriched.status == "active"
        assert enriched.age_seconds >= 0

    def test_preserves_message_data(self) -> None:
        session = _make_claude_session(
            first_message="Add tests", message_count=25
        )
        enriched = enrich_session(session, "proj", "main")

        assert enriched.last_prompt == "Add tests"
        assert enriched.message_count == 25


class TestFilterSessions:
    def test_all_returns_everything(self) -> None:
        sessions = (
            _make_enriched(status="active"),
            _make_enriched(status="resumable"),
            _make_enriched(status="stale"),
        )
        assert len(filter_sessions(sessions, "all")) == 3

    def test_filter_by_status(self) -> None:
        sessions = (
            _make_enriched(session_id="1", status="active"),
            _make_enriched(session_id="2", status="resumable"),
            _make_enriched(session_id="3", status="active"),
        )
        result = filter_sessions(sessions, "active")
        assert len(result) == 2
        assert all(s.status == "active" for s in result)

    def test_filter_no_matches(self) -> None:
        sessions = (_make_enriched(status="active"),)
        assert len(filter_sessions(sessions, "stale")) == 0

    def test_filter_empty_input(self) -> None:
        assert filter_sessions((), "active") == ()


class TestSortSessions:
    def test_sort_by_timestamp_default(self) -> None:
        now = datetime.now()
        sessions = (
            _make_enriched(session_id="old", timestamp=now - timedelta(hours=5)),
            _make_enriched(session_id="new", timestamp=now - timedelta(hours=1)),
            _make_enriched(session_id="mid", timestamp=now - timedelta(hours=3)),
        )
        result = sort_sessions(sessions, "timestamp")
        assert result[0].session_id == "new"
        assert result[2].session_id == "old"

    def test_sort_by_project(self) -> None:
        sessions = (
            _make_enriched(session_id="z", project_name="zebra"),
            _make_enriched(session_id="a", project_name="alpha"),
        )
        result = sort_sessions(sessions, "project")
        assert result[0].project_name == "alpha"

    def test_sort_by_messages(self) -> None:
        sessions = (
            _make_enriched(session_id="few", message_count=2),
            _make_enriched(session_id="many", message_count=100),
        )
        result = sort_sessions(sessions, "messages")
        assert result[0].message_count == 100

    def test_sort_by_status(self) -> None:
        sessions = (
            _make_enriched(session_id="s", status="stale"),
            _make_enriched(session_id="a", status="active"),
            _make_enriched(session_id="r", status="resumable"),
        )
        result = sort_sessions(sessions, "status")
        assert result[0].status == "active"
        assert result[1].status == "resumable"
        assert result[2].status == "stale"


class TestFormatAge:
    def test_seconds(self) -> None:
        assert format_age(30) == "30s"

    def test_minutes(self) -> None:
        assert format_age(300) == "5m"

    def test_hours(self) -> None:
        assert format_age(7200) == "2h"

    def test_days(self) -> None:
        assert format_age(172800) == "2d"

    def test_zero(self) -> None:
        assert format_age(0) == "0s"
