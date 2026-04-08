"""Profile editor modal — create or edit a workspace profile."""

from __future__ import annotations

from dataclasses import dataclass

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.events import Key
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Static

from pipnav.core.profiles import WorkspaceProfile

COLOR_SCHEME_OPTIONS: list[tuple[str, str]] = [
    ("(inherit)", ""),
    ("green", "green"),
    ("amber", "amber"),
    ("blue", "blue"),
    ("white", "white"),
]

# IDs of focusable fields in tab order
_FIELD_IDS = (
    "#profile-name-input",
    "#profile-roots-input",
    "#profile-hidden-input",
    "#profile-color-select",
    "#profile-recipe-input",
    "#profile-save-btn",
    "#profile-cancel-btn",
)


def parse_comma_list(value: str) -> tuple[str, ...]:
    """Split a comma-separated string into a tuple of stripped, non-empty items."""
    return tuple(item.strip() for item in value.split(",") if item.strip())


def format_comma_list(items: tuple[str, ...]) -> str:
    """Join a tuple into a comma-separated string."""
    return ", ".join(items)


class ProfileEditor(ModalScreen):
    """Modal for creating or editing a workspace profile.

    Navigation: Up/Down or j/k move between fields.
    Space or Enter interact with the focused field.
    """

    DEFAULT_CSS = """
    ProfileEditor {
        align: center middle;
    }
    ProfileEditor #profile-editor-container {
        width: 64;
        height: auto;
        max-height: 85%;
        border: solid $primary;
        background: $surface;
        color: $primary;
        padding: 1 2;
    }
    ProfileEditor .field-row {
        height: 3;
        margin-bottom: 0;
    }
    ProfileEditor .field-label {
        width: 20;
        height: 3;
        content-align: left middle;
    }
    ProfileEditor Select {
        width: 36;
    }
    ProfileEditor Input {
        width: 36;
    }
    ProfileEditor .button-row {
        height: 3;
        margin-top: 1;
        align: center middle;
    }
    ProfileEditor Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
    ]

    @dataclass
    class Saved(Message):
        """Fired when a profile is saved."""

        profile: WorkspaceProfile

    def __init__(self, profile: WorkspaceProfile | None = None) -> None:
        super().__init__()
        self._profile = profile

    def compose(self) -> ComposeResult:
        editing = self._profile is not None
        title = "EDIT PROFILE" if editing else "NEW PROFILE"

        with Vertical(id="profile-editor-container"):
            yield Static(
                f"[bold]{title}[/]\n"
                f"[dim]j/k:navigate  Enter/Space:select  Esc:cancel[/]\n"
            )

            with Horizontal(classes="field-row"):
                yield Label("Name", classes="field-label")
                yield Input(
                    value=self._profile.name if editing else "",
                    placeholder="profile name",
                    id="profile-name-input",
                )

            with Horizontal(classes="field-row"):
                yield Label("Roots", classes="field-label")
                yield Input(
                    value=format_comma_list(self._profile.roots) if editing else "",
                    placeholder="~/projects, ~/work",
                    id="profile-roots-input",
                )

            with Horizontal(classes="field-row"):
                yield Label("Hidden Projects", classes="field-label")
                yield Input(
                    value=format_comma_list(self._profile.hidden_projects) if editing else "",
                    placeholder="old-proj, archive",
                    id="profile-hidden-input",
                )

            with Horizontal(classes="field-row"):
                yield Label("Color Scheme", classes="field-label")
                yield Select(
                    COLOR_SCHEME_OPTIONS,
                    value=self._profile.color_scheme if editing else "",
                    id="profile-color-select",
                )

            with Horizontal(classes="field-row"):
                yield Label("Default Recipe", classes="field-label")
                yield Input(
                    value=self._profile.default_recipe if editing else "",
                    placeholder="recipe name",
                    id="profile-recipe-input",
                )

            with Horizontal(classes="button-row"):
                yield Button("Save", variant="primary", id="profile-save-btn")
                yield Button("Cancel", variant="error", id="profile-cancel-btn")

    def on_mount(self) -> None:
        """Focus the first field."""
        from textual.css.query import NoMatches

        try:
            self.query_one(_FIELD_IDS[0]).focus()
        except NoMatches:
            pass

    def on_key(self, event: Key) -> None:
        """Intercept arrow keys for field navigation.

        Up/Down move between fields. j/k are passed through to Input
        widgets for typing.
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
        idx = self._current_field_index()
        next_idx = (idx + 1) % len(_FIELD_IDS) if idx >= 0 else 0
        try:
            self.query_one(_FIELD_IDS[next_idx]).focus()
        except Exception:
            pass

    def _focus_prev(self) -> None:
        idx = self._current_field_index()
        prev_idx = (idx - 1) % len(_FIELD_IDS) if idx >= 0 else len(_FIELD_IDS) - 1
        try:
            self.query_one(_FIELD_IDS[prev_idx]).focus()
        except Exception:
            pass

    def _build_profile(self) -> tuple[WorkspaceProfile | None, str]:
        """Build a WorkspaceProfile from form state. Returns (profile, error)."""
        name = self.query_one("#profile-name-input", Input).value.strip()
        if not name:
            return None, "name"

        roots_raw = self.query_one("#profile-roots-input", Input).value
        hidden_raw = self.query_one("#profile-hidden-input", Input).value
        color_sel = self.query_one("#profile-color-select", Select)
        recipe_input = self.query_one("#profile-recipe-input", Input)

        roots = parse_comma_list(roots_raw)
        hidden = parse_comma_list(hidden_raw)
        color = str(color_sel.value) if color_sel.value != Select.BLANK else ""
        default_recipe = recipe_input.value.strip()

        # Preserve existing recipes and tags_filter when editing
        existing_recipes: tuple = ()
        existing_tags: tuple = ()
        if self._profile is not None:
            existing_recipes = self._profile.recipes
            existing_tags = self._profile.tags_filter

        profile = WorkspaceProfile(
            name=name,
            roots=roots,
            tags_filter=existing_tags,
            hidden_projects=hidden,
            color_scheme=color,
            default_recipe=default_recipe,
            recipes=existing_recipes,
        )
        return profile, ""

    @on(Button.Pressed, "#profile-save-btn")
    def _on_save(self, event: Button.Pressed) -> None:
        profile, error = self._build_profile()
        if error == "name":
            self.notify("Name is required", severity="warning")
            return
        if profile is None:
            return
        self.dismiss()
        self.post_message(self.Saved(profile))

    @on(Button.Pressed, "#profile-cancel-btn")
    def _on_cancel(self, event: Button.Pressed) -> None:
        self.dismiss()

    def action_cancel(self) -> None:
        self.dismiss()
