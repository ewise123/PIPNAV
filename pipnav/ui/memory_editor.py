"""Memory editor modal — edit structured project memory fields."""

from __future__ import annotations

from dataclasses import dataclass

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.css.query import NoMatches
from textual.events import Key
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static, TextArea

from pipnav.core.memory import ProjectMemory

_FIELD_IDS = (
    "#note-field",
    "#handoff-field",
    "#next-action-field",
    "#gotchas-field",
    "#prompts-field",
    "#save-btn",
    "#cancel-btn",
)


class MemoryEditor(ModalScreen):
    """Modal for editing structured project memory."""

    DEFAULT_CSS = """
    MemoryEditor {
        align: center middle;
    }
    MemoryEditor #memory-container {
        width: 70;
        height: auto;
        max-height: 85%;
        border: solid $primary;
        background: $surface;
        color: $primary;
        padding: 1 2;
    }
    MemoryEditor .field-row {
        height: 3;
        margin-bottom: 0;
    }
    MemoryEditor .field-label {
        width: 16;
        height: 3;
        content-align: left middle;
    }
    MemoryEditor Input {
        width: 50;
    }
    MemoryEditor .multi-field {
        height: 4;
    }
    MemoryEditor .multi-label {
        width: 16;
        height: 4;
        content-align: left top;
    }
    MemoryEditor Input.multi-input {
        width: 50;
    }
    MemoryEditor .button-row {
        height: 3;
        margin-top: 1;
        align: center middle;
    }
    MemoryEditor Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
    ]

    @dataclass
    class Saved(Message):
        """Fired when memory is saved."""

        memory: ProjectMemory

    def __init__(self, memory: ProjectMemory, project_name: str = "") -> None:
        super().__init__()
        self._memory = memory
        self._project_name = project_name

    def compose(self) -> ComposeResult:
        with Vertical(id="memory-container"):
            yield Static(
                f"[bold]PROJECT MEMORY[/]  {self._project_name}\n"
                f"[dim]Tab:next field  Esc:cancel[/]\n"
            )

            with Horizontal(classes="field-row"):
                yield Label("Note", classes="field-label")
                yield Input(
                    value=self._memory.note,
                    placeholder="Quick note (200 chars)",
                    id="note-field",
                )

            with Horizontal(classes="field-row"):
                yield Label("Handoff", classes="field-label")
                yield Input(
                    value=self._memory.handoff,
                    placeholder="Context for the next session",
                    id="handoff-field",
                )

            with Horizontal(classes="field-row"):
                yield Label("Next Action", classes="field-label")
                yield Input(
                    value=self._memory.next_action,
                    placeholder="What to do next",
                    id="next-action-field",
                )

            with Horizontal(classes="multi-field"):
                yield Label("Gotchas", classes="multi-label")
                yield Input(
                    value="; ".join(self._memory.gotchas),
                    placeholder="Semicolon-separated warnings",
                    id="gotchas-field",
                )

            with Horizontal(classes="multi-field"):
                yield Label("Prompts", classes="multi-label")
                yield Input(
                    value="; ".join(self._memory.prompts),
                    placeholder="Semicolon-separated favorite prompts",
                    id="prompts-field",
                )

            with Horizontal(classes="button-row"):
                yield Button("Save", variant="primary", id="save-btn")
                yield Button("Cancel", variant="error", id="cancel-btn")

    def on_mount(self) -> None:
        try:
            self.query_one(_FIELD_IDS[0]).focus()
        except NoMatches:
            pass

    def _build_memory(self) -> ProjectMemory:
        """Build ProjectMemory from form state."""
        note = self.query_one("#note-field", Input).value.strip()
        handoff = self.query_one("#handoff-field", Input).value.strip()
        next_action = self.query_one("#next-action-field", Input).value.strip()
        gotchas_raw = self.query_one("#gotchas-field", Input).value.strip()
        prompts_raw = self.query_one("#prompts-field", Input).value.strip()

        gotchas = tuple(g.strip() for g in gotchas_raw.split(";") if g.strip())
        prompts = tuple(p.strip() for p in prompts_raw.split(";") if p.strip())

        from datetime import datetime

        return ProjectMemory(
            tags=self._memory.tags,
            note=note[:200],
            handoff=handoff[:500],
            next_action=next_action[:500],
            gotchas=gotchas,
            prompts=prompts,
            last_updated=datetime.now().isoformat(),
        )

    @on(Button.Pressed, "#save-btn")
    def _on_save(self, event: Button.Pressed) -> None:
        self.dismiss()
        self.post_message(self.Saved(self._build_memory()))

    @on(Button.Pressed, "#cancel-btn")
    def _on_cancel(self, event: Button.Pressed) -> None:
        self.dismiss()

    def action_cancel(self) -> None:
        self.dismiss()
