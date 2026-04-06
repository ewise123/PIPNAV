"""Recipe editor modal — create or edit a saved launch recipe."""

from __future__ import annotations

from dataclasses import dataclass

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Static

from pipnav.core.launcher import (
    EFFORT_LEVELS,
    MODEL_ALIASES,
    PERMISSION_MODES,
    LaunchOptions,
)
from pipnav.core.profiles import LaunchRecipe


RECIPE_ACTIONS = (
    ("Launch new session", "launch"),
    ("Resume latest session", "resume_latest"),
    ("Pick session to resume", "resume_pick"),
)


class RecipeEditor(ModalScreen):
    """Modal for creating or editing a launch recipe."""

    DEFAULT_CSS = """
    RecipeEditor {
        align: center middle;
    }
    RecipeEditor #editor-container {
        width: 64;
        height: auto;
        max-height: 85%;
        border: solid $primary;
        background: $surface;
        color: $primary;
        padding: 1 2;
    }
    RecipeEditor .field-row {
        height: 3;
        margin-bottom: 0;
    }
    RecipeEditor .field-label {
        width: 20;
        height: 3;
        content-align: left middle;
    }
    RecipeEditor Select {
        width: 36;
    }
    RecipeEditor Input {
        width: 36;
    }
    RecipeEditor .button-row {
        height: 3;
        margin-top: 1;
        align: center middle;
    }
    RecipeEditor Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
    ]

    @dataclass
    class Saved(Message):
        """Fired when a recipe is saved."""

        recipe: LaunchRecipe

    def __init__(self, recipe: LaunchRecipe | None = None) -> None:
        super().__init__()
        self._recipe = recipe

    def compose(self) -> ComposeResult:
        editing = self._recipe is not None
        title = "EDIT RECIPE" if editing else "NEW RECIPE"

        action_options = list(RECIPE_ACTIONS)
        perm_options = [("(default)", "")] + [(p, p) for p in PERMISSION_MODES]

        with Vertical(id="editor-container"):
            yield Static(f"[bold]{title}[/]\n")

            with Horizontal(classes="field-row"):
                yield Label("Name", classes="field-label")
                yield Input(
                    value=self._recipe.name if editing else "",
                    placeholder="recipe name",
                    id="name-input",
                )

            with Horizontal(classes="field-row"):
                yield Label("Description", classes="field-label")
                yield Input(
                    value=self._recipe.description if editing else "",
                    placeholder="what this recipe does",
                    id="desc-input",
                )

            with Horizontal(classes="field-row"):
                yield Label("Action", classes="field-label")
                yield Select(
                    action_options,
                    value=self._recipe.action if editing else "launch",
                    id="action-select",
                )

            with Horizontal(classes="field-row"):
                yield Label("Permission Mode", classes="field-label")
                yield Select(
                    perm_options,
                    value=self._recipe.permission_mode if editing else "",
                    id="perm-select",
                )

            with Horizontal(classes="field-row"):
                yield Label("Extra Flags", classes="field-label")
                yield Input(
                    value=" ".join(self._recipe.claude_flags) if editing else "",
                    placeholder="e.g. --model opus --effort max",
                    id="flags-input",
                )

            with Horizontal(classes="button-row"):
                yield Button("Save", variant="primary", id="save-btn")
                yield Button("Cancel", variant="error", id="cancel-btn")

    def _build_recipe(self) -> LaunchRecipe | None:
        """Build a LaunchRecipe from form state."""
        name = self.query_one("#name-input", Input).value.strip()
        if not name:
            return None

        desc = self.query_one("#desc-input", Input).value.strip()
        action_sel = self.query_one("#action-select", Select)
        perm_sel = self.query_one("#perm-select", Select)
        flags_input = self.query_one("#flags-input", Input)

        action = str(action_sel.value) if action_sel.value != Select.BLANK else "launch"
        perm = str(perm_sel.value) if perm_sel.value != Select.BLANK else ""

        flags = tuple(
            f.strip() for f in flags_input.value.split() if f.strip()
        )

        return LaunchRecipe(
            name=name,
            description=desc,
            action=action,
            claude_flags=flags,
            permission_mode=perm,
        )

    @on(Button.Pressed, "#save-btn")
    def _on_save(self, event: Button.Pressed) -> None:
        recipe = self._build_recipe()
        if recipe is None:
            self.notify("Name is required", severity="warning")
            return
        self.dismiss()
        self.post_message(self.Saved(recipe))

    @on(Button.Pressed, "#cancel-btn")
    def _on_cancel(self, event: Button.Pressed) -> None:
        self.dismiss()

    def action_cancel(self) -> None:
        self.dismiss()


def launch_options_to_recipe(
    options: LaunchOptions, name: str = "Custom"
) -> LaunchRecipe:
    """Convert a LaunchOptions into a saveable LaunchRecipe."""
    return LaunchRecipe(
        name=name,
        description="Saved from custom launch",
        action="launch",
        claude_flags=options.to_flags(),
        permission_mode=options.permission_mode,
    )
