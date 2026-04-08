"""Tests for the project memory layer."""

import json
from pathlib import Path

import pytest

from pipnav.core.memory import (
    ProjectMemory,
    cycle_tag,
    load_memory,
    memory_to_notes,
    save_memory,
    set_note,
    update_memory_field,
)
from pipnav.core.notes import ProjectNotes


@pytest.fixture(autouse=True)
def _use_tmp_dirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Redirect memory and notes paths to temp."""
    import pipnav.core.memory as mem
    import pipnav.core.notes as notes_mod
    import pipnav.core.config as cfg

    monkeypatch.setattr(cfg, "PIPNAV_DIR", tmp_path)
    monkeypatch.setattr(mem, "MEMORY_PATH", tmp_path / "memory.json")
    monkeypatch.setattr(mem, "NOTES_PATH", tmp_path / "notes.json")
    monkeypatch.setattr(notes_mod, "NOTES_PATH", tmp_path / "notes.json")


class TestMemoryPersistence:
    def test_save_and_load_round_trip(self) -> None:
        memory = {
            "/home/user/proj": ProjectMemory(
                tags=("work",),
                note="test note",
                handoff="left off at auth module",
                next_action="finish login flow",
                gotchas=("don't touch config.py",),
                prompts=("review the auth module",),
            )
        }
        save_memory(memory)
        loaded = load_memory()

        assert "/home/user/proj" in loaded
        m = loaded["/home/user/proj"]
        assert m.tags == ("work",)
        assert m.note == "test note"
        assert m.handoff == "left off at auth module"
        assert m.next_action == "finish login flow"
        assert m.gotchas == ("don't touch config.py",)
        assert m.prompts == ("review the auth module",)

    def test_load_empty_when_missing(self) -> None:
        assert load_memory() == {}

    def test_load_handles_corrupt_json(self, tmp_path: Path) -> None:
        import pipnav.core.memory as mem

        mem.MEMORY_PATH.write_text("not json!", encoding="utf-8")
        assert load_memory() == {}

    def test_load_corrupt_memory_falls_back_to_notes(self) -> None:
        import pipnav.core.memory as mem

        mem.MEMORY_PATH.write_text("not json!", encoding="utf-8")
        mem.NOTES_PATH.write_text(
            json.dumps(
                {
                    "/home/user/proj": {
                        "tags": ["work"],
                        "note": "legacy note",
                    }
                }
            ),
            encoding="utf-8",
        )

        loaded = load_memory()

        assert loaded["/home/user/proj"].tags == ("work",)
        assert loaded["/home/user/proj"].note == "legacy note"


class TestMigrationFromNotes:
    def test_auto_migrates_from_notes_json(self, tmp_path: Path) -> None:
        import pipnav.core.memory as mem

        # Write a notes.json file
        notes_data = {
            "/home/user/proj": {
                "tags": ["work"],
                "note": "old note",
            }
        }
        mem.NOTES_PATH.write_text(
            json.dumps(notes_data), encoding="utf-8"
        )

        # Load memory — should migrate
        memory = load_memory()
        assert "/home/user/proj" in memory
        assert memory["/home/user/proj"].tags == ("work",)
        assert memory["/home/user/proj"].note == "old note"
        assert memory["/home/user/proj"].handoff == ""

        # memory.json should now exist
        assert mem.MEMORY_PATH.exists()

    def test_no_migration_if_memory_exists(self, tmp_path: Path) -> None:
        import pipnav.core.memory as mem

        # Write both files
        mem.NOTES_PATH.write_text(
            json.dumps({"/proj": {"tags": ["old"], "note": "old"}}),
            encoding="utf-8",
        )
        save_memory({"/proj": ProjectMemory(tags=("new",), note="new")})

        # Should load from memory.json, not notes.json
        loaded = load_memory()
        assert loaded["/proj"].tags == ("new",)


class TestMemoryOperations:
    def test_update_field(self) -> None:
        memory: dict[str, ProjectMemory] = {}
        memory = update_memory_field("/proj", "handoff", "auth module", memory)
        assert memory["/proj"].handoff == "auth module"
        assert memory["/proj"].last_updated != ""

    def test_update_field_truncates(self) -> None:
        memory: dict[str, ProjectMemory] = {}
        long_text = "x" * 1000
        memory = update_memory_field("/proj", "note", long_text, memory)
        assert len(memory["/proj"].note) == 500

    def test_set_note(self) -> None:
        memory: dict[str, ProjectMemory] = {}
        memory = set_note("/proj", "quick note", memory)
        assert memory["/proj"].note == "quick note"

    def test_set_note_truncates_to_200(self) -> None:
        memory: dict[str, ProjectMemory] = {}
        memory = set_note("/proj", "x" * 300, memory)
        assert len(memory["/proj"].note) == 200

    def test_cycle_tag(self) -> None:
        tags = ("work", "personal", "archived")
        memory: dict[str, ProjectMemory] = {}

        memory = cycle_tag("/proj", tags, memory)
        assert memory["/proj"].tags == ("work",)

        memory = cycle_tag("/proj", tags, memory)
        assert memory["/proj"].tags == ("personal",)

        memory = cycle_tag("/proj", tags, memory)
        assert memory["/proj"].tags == ("archived",)

        memory = cycle_tag("/proj", tags, memory)
        assert memory["/proj"].tags == ()

    def test_cycle_tag_preserves_other_fields(self) -> None:
        memory = {"/proj": ProjectMemory(note="keep this", handoff="and this")}
        memory = cycle_tag("/proj", ("work",), memory)
        assert memory["/proj"].note == "keep this"
        assert memory["/proj"].handoff == "and this"


class TestMemoryToNotes:
    def test_converts_basic_fields(self) -> None:
        mem = ProjectMemory(tags=("work",), note="hello")
        notes = memory_to_notes(mem)
        assert isinstance(notes, ProjectNotes)
        assert notes.tags == ("work",)
        assert notes.note == "hello"

    def test_default_memory_to_default_notes(self) -> None:
        notes = memory_to_notes(ProjectMemory())
        assert notes == ProjectNotes()


class TestFrozen:
    def test_memory_is_frozen(self) -> None:
        mem = ProjectMemory()
        with pytest.raises(AttributeError):
            mem.note = "changed"  # type: ignore[misc]
