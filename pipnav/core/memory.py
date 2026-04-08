"""Project memory — structured per-project knowledge in ~/.pipnav/memory.json.

Extends the simple tags+note model with handoff summaries, gotchas,
next actions, and preferred prompts. Backward-compatible with notes.json
via automatic migration.
"""

import json
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path

from pipnav.core.logging import get_logger
from pipnav.core.notes import NOTES_PATH, ProjectNotes, load_notes

MEMORY_PATH = Path.home() / ".pipnav" / "memory.json"

MAX_FIELD_LENGTH = 500


@dataclass(frozen=True)
class ProjectMemory:
    """Structured memory for a project."""

    tags: tuple[str, ...] = ()
    note: str = ""
    handoff: str = ""
    next_action: str = ""
    gotchas: tuple[str, ...] = ()
    prompts: tuple[str, ...] = ()
    last_updated: str = ""  # ISO format string, empty if never updated


def _memory_to_dict(mem: ProjectMemory) -> dict:
    return {
        "tags": list(mem.tags),
        "note": mem.note,
        "handoff": mem.handoff,
        "next_action": mem.next_action,
        "gotchas": list(mem.gotchas),
        "prompts": list(mem.prompts),
        "last_updated": mem.last_updated,
    }


def _dict_to_memory(data: dict) -> ProjectMemory:
    return ProjectMemory(
        tags=tuple(data.get("tags", ())),
        note=data.get("note", ""),
        handoff=data.get("handoff", ""),
        next_action=data.get("next_action", ""),
        gotchas=tuple(data.get("gotchas", ())),
        prompts=tuple(data.get("prompts", ())),
        last_updated=data.get("last_updated", ""),
    )


def _migrate_from_notes(notes: dict[str, ProjectNotes]) -> dict[str, ProjectMemory]:
    """Convert old notes.json entries to ProjectMemory."""
    return {
        key: ProjectMemory(tags=n.tags, note=n.note)
        for key, n in notes.items()
    }


def load_memory() -> dict[str, ProjectMemory]:
    """Load memory from ~/.pipnav/memory.json. Migrates from notes.json if needed."""
    logger = get_logger()

    if MEMORY_PATH.exists():
        try:
            raw = MEMORY_PATH.read_text(encoding="utf-8")
            data = json.loads(raw)
            return {key: _dict_to_memory(val) for key, val in data.items()}
        except (json.JSONDecodeError, TypeError, KeyError) as exc:
            logger.warning("Corrupt memory file, returning empty: %s", exc)
            return {}

    # Auto-migrate from notes.json if it exists
    if NOTES_PATH.exists():
        logger.info("Migrating notes.json to memory.json")
        notes = load_notes()
        memory = _migrate_from_notes(notes)
        save_memory(memory)
        return memory

    return {}


def save_memory(memory: dict[str, ProjectMemory]) -> None:
    """Write memory to ~/.pipnav/memory.json."""
    logger = get_logger()
    MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)

    try:
        data = {key: _memory_to_dict(mem) for key, mem in memory.items()}
        MEMORY_PATH.write_text(
            json.dumps(data, indent=2) + "\n", encoding="utf-8"
        )
    except OSError as exc:
        logger.error("Failed to save memory: %s", exc)


def memory_to_notes(mem: ProjectMemory) -> ProjectNotes:
    """Convert a ProjectMemory to ProjectNotes for backward compatibility."""
    return ProjectNotes(tags=mem.tags, note=mem.note)


def update_memory_field(
    project_key: str,
    field: str,
    value: str | tuple[str, ...],
    memory: dict[str, ProjectMemory],
) -> dict[str, ProjectMemory]:
    """Update a single field on a project's memory. Returns updated dict."""
    current = memory.get(project_key, ProjectMemory())

    if isinstance(value, str):
        value = value[:MAX_FIELD_LENGTH]

    updated = replace(
        current,
        **{field: value, "last_updated": datetime.now().isoformat()},
    )
    new_memory = {**memory, project_key: updated}
    save_memory(new_memory)
    return new_memory


def cycle_tag(
    project_key: str,
    available_tags: tuple[str, ...],
    memory: dict[str, ProjectMemory],
) -> dict[str, ProjectMemory]:
    """Cycle tag on a project. Returns updated memory dict."""
    current = memory.get(project_key, ProjectMemory())
    current_tags = current.tags

    if not current_tags:
        new_tags = (available_tags[0],) if available_tags else ()
    else:
        last_tag = current_tags[-1]
        try:
            idx = available_tags.index(last_tag)
            next_idx = idx + 1
            new_tags = () if next_idx >= len(available_tags) else (available_tags[next_idx],)
        except ValueError:
            new_tags = (available_tags[0],) if available_tags else ()

    updated = replace(current, tags=new_tags)
    new_memory = {**memory, project_key: updated}
    save_memory(new_memory)
    return new_memory


def set_note(
    project_key: str,
    text: str,
    memory: dict[str, ProjectMemory],
) -> dict[str, ProjectMemory]:
    """Set the quick note field. Returns updated memory dict."""
    return update_memory_field(project_key, "note", text[:200], memory)
