"""Tests for Claude session discovery ordering."""

import json
from pathlib import Path

import pytest

from pipnav.core.claude_sessions import discover_sessions_for_project


@pytest.fixture(autouse=True)
def _use_tmp_projects_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Redirect Claude session storage to a temp directory."""
    import pipnav.core.claude_sessions as claude_sessions

    monkeypatch.setattr(claude_sessions, "PROJECTS_DIR", tmp_path)


def test_discover_sessions_sorts_by_last_activity(tmp_path: Path) -> None:
    project_path = Path("/home/user/projects/demo")
    sessions_dir = tmp_path / "-home-user-projects-demo"
    sessions_dir.mkdir(parents=True)

    older_started_recently_active = sessions_dir / (
        "11111111-1111-1111-1111-111111111111.jsonl"
    )
    older_started_recently_active.write_text(
        "\n".join(
            (
                json.dumps(
                    {
                        "type": "user",
                        "timestamp": "2026-03-01T10:00:00Z",
                        "message": {"content": "older start"},
                    }
                ),
                json.dumps(
                    {
                        "type": "assistant",
                        "timestamp": "2026-04-01T10:00:00Z",
                    }
                ),
            )
        )
        + "\n",
        encoding="utf-8",
    )

    newer_started_stale = sessions_dir / (
        "22222222-2222-2222-2222-222222222222.jsonl"
    )
    newer_started_stale.write_text(
        "\n".join(
            (
                json.dumps(
                    {
                        "type": "user",
                        "timestamp": "2026-03-15T10:00:00Z",
                        "message": {"content": "newer start"},
                    }
                ),
                json.dumps(
                    {
                        "type": "assistant",
                        "timestamp": "2026-03-20T10:00:00Z",
                    }
                ),
            )
        )
        + "\n",
        encoding="utf-8",
    )

    sessions = discover_sessions_for_project(project_path)

    assert [session.session_id for session in sessions] == [
        "11111111-1111-1111-1111-111111111111",
        "22222222-2222-2222-2222-222222222222",
    ]
