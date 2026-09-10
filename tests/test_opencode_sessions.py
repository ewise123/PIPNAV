"""Tests for reading OpenCode session history.

OpenCode keeps a live SQLite database that its own process writes while we read.
Two silent-failure risks drive these tests: `time_updated` is epoch
MILLISECONDS (treating it as seconds puts every session in 1975 and misorders
the list), and the table carries child and archived sessions we must not offer.
"""

import sqlite3
from datetime import datetime
from pathlib import Path

import pytest

from pipnav.core import opencode_sessions

# The subset of OpenCode's schema this reader depends on.
SCHEMA = """
CREATE TABLE project (
  id text PRIMARY KEY, worktree text NOT NULL, name text,
  time_created integer NOT NULL, time_updated integer NOT NULL,
  sandboxes text NOT NULL
);
CREATE TABLE session (
  id text PRIMARY KEY, project_id text NOT NULL, workspace_id text,
  parent_id text, slug text NOT NULL, directory text NOT NULL, path text,
  title text NOT NULL, version text NOT NULL, cost real DEFAULT 0 NOT NULL,
  tokens_input integer DEFAULT 0 NOT NULL,
  tokens_output integer DEFAULT 0 NOT NULL,
  time_created integer NOT NULL, time_updated integer NOT NULL,
  time_archived integer
);
"""

# 2026-09-04 15:09:20.685 local, in milliseconds — a real value from the DB.
MS_2026_09_04 = 1788548960685


@pytest.fixture
def db(tmp_path, monkeypatch):
    path = tmp_path / "opencode.db"
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    conn.execute(
        "insert into project values ('p1','/home/ewise/projects/PIPNAV','PIPNAV',0,0,'[]')"
    )
    conn.commit()
    monkeypatch.setattr(opencode_sessions, "DB_PATH", path)

    def add(
        session_id, directory="/home/ewise/projects/PIPNAV", title="Wire up export",
        time_updated=MS_2026_09_04, parent_id=None, time_archived=None, cost=0.0,
    ):
        conn.execute(
            "insert into session (id,project_id,parent_id,slug,directory,title,"
            "version,cost,time_created,time_updated,time_archived) "
            "values (?,?,?,?,?,?,?,?,?,?,?)",
            (session_id, "p1", parent_id, session_id, directory, title,
             "0.1.0", cost, time_updated, time_updated, time_archived),
        )
        conn.commit()

    yield add
    conn.close()


PROJECT = Path("/home/ewise/projects/PIPNAV")


def test_reads_a_session(db):
    db("ses_abc")
    got = opencode_sessions.discover_sessions_for_project(PROJECT)

    assert len(got) == 1
    assert got[0].session_id == "ses_abc"
    assert got[0].title == "Wire up export"
    assert got[0].project_path == "/home/ewise/projects/PIPNAV"


def test_treats_time_updated_as_milliseconds(db):
    """Seconds would land in 1975 and silently misorder everything."""
    db("ses_abc", time_updated=MS_2026_09_04)
    got = opencode_sessions.discover_sessions_for_project(PROJECT)

    assert got[0].last_active.year == 2026
    assert got[0].last_active.month == 9


def test_newest_first(db):
    db("older", time_updated=MS_2026_09_04)
    db("newer", time_updated=MS_2026_09_04 + 86_400_000)
    got = opencode_sessions.discover_sessions_for_project(PROJECT)
    assert [s.session_id for s in got] == ["newer", "older"]


def test_excludes_archived_sessions(db):
    db("live")
    db("archived", time_archived=MS_2026_09_04)
    got = opencode_sessions.discover_sessions_for_project(PROJECT)
    assert [s.session_id for s in got] == ["live"]


def test_excludes_child_sessions(db):
    """Child sessions are an agent's own internal work, not yours to resume."""
    db("parent")
    db("child", parent_id="parent")
    got = opencode_sessions.discover_sessions_for_project(PROJECT)
    assert [s.session_id for s in got] == ["parent"]


def test_filters_by_directory(db):
    db("here")
    db("elsewhere", directory="/tmp/somewhere")
    got = opencode_sessions.discover_sessions_for_project(PROJECT)
    assert [s.session_id for s in got] == ["here"]


def test_directory_filter_ignores_a_trailing_slash(db):
    db("here", directory="/home/ewise/projects/PIPNAV/")
    assert len(opencode_sessions.discover_sessions_for_project(PROJECT)) == 1


def test_falls_back_when_the_title_is_empty(db):
    db("ses_abc", title="")
    assert opencode_sessions.discover_sessions_for_project(PROJECT)[0].title


def test_carries_cost_when_present(db):
    db("ses_abc", cost=0.42)
    assert opencode_sessions.discover_sessions_for_project(PROJECT)[0].cost == 0.42


# --- the database is not ours; it may be absent, locked, or a different shape ---


def test_missing_database_is_not_an_error(tmp_path, monkeypatch):
    monkeypatch.setattr(opencode_sessions, "DB_PATH", tmp_path / "absent.db")
    assert opencode_sessions.discover_sessions_for_project(PROJECT) == ()


def test_a_file_that_is_not_a_database_is_not_an_error(tmp_path, monkeypatch):
    bad = tmp_path / "opencode.db"
    bad.write_text("this is not sqlite", encoding="utf-8")
    monkeypatch.setattr(opencode_sessions, "DB_PATH", bad)
    assert opencode_sessions.discover_sessions_for_project(PROJECT) == ()


def test_schema_drift_is_not_an_error(tmp_path, monkeypatch):
    """A future OpenCode renaming a column must degrade, not crash PipNav."""
    path = tmp_path / "opencode.db"
    conn = sqlite3.connect(path)
    conn.executescript("CREATE TABLE session (id text PRIMARY KEY, whatever text);")
    conn.commit()
    conn.close()
    monkeypatch.setattr(opencode_sessions, "DB_PATH", path)
    assert opencode_sessions.discover_sessions_for_project(PROJECT) == ()


def test_opens_the_database_read_only(db, monkeypatch):
    """We must never write to a database another process owns."""
    opened: list[str] = []
    real_connect = sqlite3.connect

    def spy(target, *args, **kwargs):
        opened.append(str(target))
        return real_connect(target, *args, **kwargs)

    monkeypatch.setattr(opencode_sessions.sqlite3, "connect", spy)
    db("ses_abc")
    opencode_sessions.discover_sessions_for_project(PROJECT)

    assert opened, "expected a connection"
    assert "mode=ro" in opened[0]


def test_bad_rows_are_skipped_not_fatal(db):
    """SQLite is loosely typed, so a column can hold something unexpected."""
    db("good")
    db("bad", time_updated="not a number")
    got = opencode_sessions.discover_sessions_for_project(PROJECT)
    ids = [s.session_id for s in got]
    assert "good" in ids
    assert "bad" not in ids
