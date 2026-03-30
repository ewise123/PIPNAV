"""Tests for tags and notes."""

from pathlib import Path

import pytest

from pipnav.core.notes import (
    MAX_NOTE_LENGTH,
    ProjectNotes,
    cycle_tag,
    load_notes,
    save_notes,
    set_note,
)


@pytest.fixture(autouse=True)
def _use_tmp_notes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Redirect notes to a temp directory."""
    import pipnav.core.notes as mod

    monkeypatch.setattr(mod, "NOTES_PATH", tmp_path / "notes.json")


def test_load_empty() -> None:
    notes = load_notes()
    assert notes == {}


def test_save_and_load_round_trip() -> None:
    notes = {"/tmp/proj": ProjectNotes(tags=("work",), note="hello")}
    save_notes(notes)
    loaded = load_notes()
    assert loaded["/tmp/proj"].tags == ("work",)
    assert loaded["/tmp/proj"].note == "hello"


def test_cycle_tag_from_none() -> None:
    available = ("work", "personal", "archived")
    notes = cycle_tag("/tmp/proj", available, {})
    assert notes["/tmp/proj"].tags == ("work",)


def test_cycle_tag_advances() -> None:
    available = ("work", "personal", "archived")
    notes = {"/tmp/proj": ProjectNotes(tags=("work",))}
    notes = cycle_tag("/tmp/proj", available, notes)
    assert notes["/tmp/proj"].tags == ("personal",)


def test_cycle_tag_wraps_to_empty() -> None:
    available = ("work", "personal")
    notes = {"/tmp/proj": ProjectNotes(tags=("personal",))}
    notes = cycle_tag("/tmp/proj", available, notes)
    assert notes["/tmp/proj"].tags == ()


def test_set_note() -> None:
    notes = set_note("/tmp/proj", "my note", {})
    assert notes["/tmp/proj"].note == "my note"


def test_set_note_truncates() -> None:
    long_note = "x" * 500
    notes = set_note("/tmp/proj", long_note, {})
    assert len(notes["/tmp/proj"].note) == MAX_NOTE_LENGTH
