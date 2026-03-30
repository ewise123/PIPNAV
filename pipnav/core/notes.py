"""Tags and notes — per-project metadata in ~/.pipnav/notes.json."""

import json
from dataclasses import dataclass
from pathlib import Path

from pipnav.core.logging import get_logger

NOTES_PATH = Path.home() / ".pipnav" / "notes.json"

MAX_NOTE_LENGTH = 200


@dataclass(frozen=True)
class ProjectNotes:
    """Tags and notes for a project."""

    tags: tuple[str, ...] = ()
    note: str = ""


def load_notes() -> dict[str, ProjectNotes]:
    """Load notes from ~/.pipnav/notes.json."""
    logger = get_logger()

    if not NOTES_PATH.exists():
        return {}

    try:
        raw = NOTES_PATH.read_text(encoding="utf-8")
        data = json.loads(raw)
        result: dict[str, ProjectNotes] = {}
        for key, val in data.items():
            result[key] = ProjectNotes(
                tags=tuple(val.get("tags", ())),
                note=val.get("note", ""),
            )
        return result
    except (json.JSONDecodeError, TypeError, KeyError) as exc:
        logger.warning("Corrupt notes file, returning empty: %s", exc)
        return {}


def save_notes(notes: dict[str, ProjectNotes]) -> None:
    """Write notes to ~/.pipnav/notes.json."""
    logger = get_logger()
    NOTES_PATH.parent.mkdir(parents=True, exist_ok=True)

    try:
        data = {
            key: {"tags": list(info.tags), "note": info.note}
            for key, info in notes.items()
        }
        NOTES_PATH.write_text(
            json.dumps(data, indent=2) + "\n", encoding="utf-8"
        )
    except OSError as exc:
        logger.error("Failed to save notes: %s", exc)


def cycle_tag(
    project_key: str, available_tags: tuple[str, ...], notes: dict[str, ProjectNotes]
) -> dict[str, ProjectNotes]:
    """Add next tag or clear all tags if at end of cycle. Returns updated notes."""
    current = notes.get(project_key, ProjectNotes())
    current_tags = current.tags

    if not current_tags:
        # No tags — assign the first available tag
        new_tags = (available_tags[0],) if available_tags else ()
    else:
        # Find current tag's position and cycle to next
        last_tag = current_tags[-1]
        try:
            idx = available_tags.index(last_tag)
            next_idx = idx + 1
            if next_idx >= len(available_tags):
                new_tags = ()  # Cycle back to no tags
            else:
                new_tags = (available_tags[next_idx],)
        except ValueError:
            new_tags = (available_tags[0],) if available_tags else ()

    updated = ProjectNotes(tags=new_tags, note=current.note)
    new_notes = {**notes, project_key: updated}
    save_notes(new_notes)
    return new_notes


def set_note(
    project_key: str, text: str, notes: dict[str, ProjectNotes]
) -> dict[str, ProjectNotes]:
    """Set note text (truncated to MAX_NOTE_LENGTH). Returns updated notes."""
    current = notes.get(project_key, ProjectNotes())
    truncated = text[:MAX_NOTE_LENGTH]
    updated = ProjectNotes(tags=current.tags, note=truncated)
    new_notes = {**notes, project_key: updated}
    save_notes(new_notes)
    return new_notes
