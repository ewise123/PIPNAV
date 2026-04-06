"""Custom launch builder modal — configure Claude launch options live."""

from __future__ import annotations

from dataclasses import dataclass

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.events import Key
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Static, Switch

from pipnav.core.launcher import (
    EFFORT_LEVELS,
    MODEL_ALIASES,
    PERMISSION_MODES,
    LaunchOptions,
)

# IDs of focusable fields in tab order
_FIELD_IDS = (
    "#model-select",
    "#perm-select",
    "#effort-select",
    "#name-input",
    "#dirs-input",
    "#worktree-switch",
    "#prompt-input",
    "#launch-btn",
    "#save-btn",
    "#cancel-btn",
)


class LaunchBuilder(ModalScreen):
    """Modal for building a custom Claude Code launch configuration.

    Navigation: Up/Down or j/k move between fields.
    Space or Enter interact with the focused field (open dropdown, toggle switch, press button).
    """

    DEFAULT_CSS = """
    LaunchBuilder {
        align: center middle;
    }
    LaunchBuilder #builder-container {
        width: 64;
        height: auto;
        max-height: 85%;
        border: solid $primary;
        background: $surface;
        color: $primary;
        padding: 1 2;
    }
    LaunchBuilder .field-row {
        height: 3;
        margin-bottom: 0;
    }
    LaunchBuilder .field-label {
        width: 20;
        height: 3;
        content-align: left middle;
    }
    LaunchBuilder Select {
        width: 36;
    }
    LaunchBuilder Input {
        width: 36;
    }
    LaunchBuilder Switch {
        height: 3;
    }
    LaunchBuilder .button-row {
        height: 3;
        margin-top: 1;
        align: center middle;
    }
    LaunchBuilder Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
    ]

    @dataclass
    class Launched(Message):
        """Fired when the user confirms launch."""

        options: LaunchOptions
        save_as_recipe: bool

    def __init__(self, project_name: str = "") -> None:
        super().__init__()
        self._project_name = project_name

    def compose(self) -> ComposeResult:
        model_options = [("(default)", "")] + [(m, m) for m in MODEL_ALIASES]
        perm_options = [("(default)", "")] + [(p, p) for p in PERMISSION_MODES]
        effort_options = [("(default)", "")] + [(e, e) for e in EFFORT_LEVELS]

        with Vertical(id="builder-container"):
            yield Static(
                f"[bold]CUSTOM LAUNCH[/]  {self._project_name}\n"
                f"[dim]j/k:navigate  Enter/Space:select  Esc:cancel[/]\n"
            )

            with Horizontal(classes="field-row"):
                yield Label("Model", classes="field-label")
                yield Select(model_options, value="", id="model-select")

            with Horizontal(classes="field-row"):
                yield Label("Permission Mode", classes="field-label")
                yield Select(perm_options, value="", id="perm-select")

            with Horizontal(classes="field-row"):
                yield Label("Effort", classes="field-label")
                yield Select(effort_options, value="", id="effort-select")

            with Horizontal(classes="field-row"):
                yield Label("Session Name", classes="field-label")
                yield Input(placeholder="optional", id="name-input")

            with Horizontal(classes="field-row"):
                yield Label("Add Dirs", classes="field-label")
                yield Input(
                    placeholder="comma-separated paths",
                    id="dirs-input",
                )

            with Horizontal(classes="field-row"):
                yield Label("Worktree", classes="field-label")
                yield Switch(value=False, id="worktree-switch")

            with Horizontal(classes="field-row"):
                yield Label("System Prompt", classes="field-label")
                yield Input(
                    placeholder="appended to default prompt",
                    id="prompt-input",
                )

            with Horizontal(classes="button-row"):
                yield Button("Launch", variant="primary", id="launch-btn")
                yield Button(
                    "Launch & Save Recipe",
                    variant="default",
                    id="save-btn",
                )
                yield Button("Cancel", variant="error", id="cancel-btn")

    def on_mount(self) -> None:
        """Focus the first field."""
        from textual.css.query import NoMatches

        try:
            self.query_one(_FIELD_IDS[0]).focus()
        except NoMatches:
            pass

    def on_key(self, event: Key) -> None:
        """Intercept arrow keys for field navigation.

        Up/Down move between fields (except in Input widgets where they
        move the cursor). j/k are passed through to Input widgets for typing.
        """
        focused = self.focused

        # Let Input widgets handle all keys normally for typing
        if isinstance(focused, Input):
            return

        if event.key in ("down", "j"):
            event.stop()
            event.prevent_default()
            self._focus_next()
        elif event.key in ("up", "k"):
            event.stop()
            event.prevent_default()
            self._focus_prev()

    def _current_field_index(self) -> int:
        """Find the index of the currently focused field."""
        focused = self.focused
        if focused is None:
            return -1
        for i, fid in enumerate(_FIELD_IDS):
            try:
                if self.query_one(fid) is focused:
                    return i
            except Exception:
                pass
        return -1

    def _focus_next(self) -> None:
        """Move focus to the next field."""
        idx = self._current_field_index()
        next_idx = (idx + 1) % len(_FIELD_IDS) if idx >= 0 else 0
        try:
            self.query_one(_FIELD_IDS[next_idx]).focus()
        except Exception:
            pass

    def _focus_prev(self) -> None:
        """Move focus to the previous field."""
        idx = self._current_field_index()
        prev_idx = (idx - 1) % len(_FIELD_IDS) if idx >= 0 else len(_FIELD_IDS) - 1
        try:
            self.query_one(_FIELD_IDS[prev_idx]).focus()
        except Exception:
            pass

    def _build_options(self) -> LaunchOptions:
        """Build LaunchOptions from current form state."""
        model_sel = self.query_one("#model-select", Select)
        perm_sel = self.query_one("#perm-select", Select)
        effort_sel = self.query_one("#effort-select", Select)
        name_input = self.query_one("#name-input", Input)
        dirs_input = self.query_one("#dirs-input", Input)
        worktree_sw = self.query_one("#worktree-switch", Switch)
        prompt_input = self.query_one("#prompt-input", Input)

        model = str(model_sel.value) if model_sel.value != Select.BLANK else ""
        perm = str(perm_sel.value) if perm_sel.value != Select.BLANK else ""
        effort = str(effort_sel.value) if effort_sel.value != Select.BLANK else ""

        add_dirs = tuple(
            d.strip() for d in dirs_input.value.split(",") if d.strip()
        )

        return LaunchOptions(
            model=model,
            permission_mode=perm,
            worktree=worktree_sw.value,
            add_dirs=add_dirs,
            effort=effort,
            session_name=name_input.value.strip(),
            append_system_prompt=prompt_input.value.strip(),
        )

    @on(Button.Pressed, "#launch-btn")
    def _on_launch(self, event: Button.Pressed) -> None:
        self.dismiss()
        self.post_message(self.Launched(self._build_options(), save_as_recipe=False))

    @on(Button.Pressed, "#save-btn")
    def _on_save_launch(self, event: Button.Pressed) -> None:
        self.dismiss()
        self.post_message(self.Launched(self._build_options(), save_as_recipe=True))

    @on(Button.Pressed, "#cancel-btn")
    def _on_cancel(self, event: Button.Pressed) -> None:
        self.dismiss()

    def action_cancel(self) -> None:
        self.dismiss()
