"""Profile switcher modal — select a workspace profile."""

from __future__ import annotations

from dataclasses import dataclass

from textual import on
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from pipnav.core.profiles import WorkspaceProfile

# Special option IDs for edit/new actions
_EDIT_OPTION_ID = "__edit_profile__"
_NEW_OPTION_ID = "__new_profile__"


class ProfileSwitcher(ModalScreen):
    """Modal for selecting a workspace profile."""

    DEFAULT_CSS = """
    ProfileSwitcher {
        align: center middle;
    }
    ProfileSwitcher #profile-container {
        width: 50;
        height: auto;
        max-height: 70%;
        border: solid $primary;
        background: $surface;
        color: $primary;
        padding: 1 2;
    }
    ProfileSwitcher OptionList {
        background-tint: initial;
        height: auto;
        max-height: 20;
    }
    ProfileSwitcher OptionList:focus {
        background-tint: initial;
    }
    """

    BINDINGS = [
        ("escape", "dismiss", "Close"),
    ]

    @dataclass
    class Selected(Message):
        """Fired when a profile is selected."""

        profile: WorkspaceProfile

    @dataclass
    class EditRequested(Message):
        """Fired when user wants to edit the active profile."""

        profile: WorkspaceProfile

    @dataclass
    class NewRequested(Message):
        """Fired when user wants to create a new profile."""

    def __init__(
        self,
        profiles: tuple[WorkspaceProfile, ...],
        active_name: str = "",
    ) -> None:
        super().__init__()
        self._profiles = profiles
        self._active_name = active_name

    def compose(self) -> ComposeResult:
        with Vertical(id="profile-container"):
            yield Static("[bold]WORKSPACE PROFILES[/]\n")
            yield OptionList(id="profile-options")

    def on_mount(self) -> None:
        option_list = self.query_one("#profile-options", OptionList)
        for profile in self._profiles:
            marker = " *" if profile.name == self._active_name else ""
            roots_hint = ", ".join(profile.roots) if profile.roots else "(config roots)"
            label = (
                f"  {profile.name}{marker}\n"
                f"  [dim]{roots_hint}[/]"
            )
            option_list.add_option(Option(label, id=profile.name))

        if not self._profiles:
            option_list.add_option(Option("  [dim]No profiles configured[/]"))

        # Add visual separator and edit/new options
        option_list.add_option(Option("  [dim]────────────────────[/]", id="__sep__"))
        edit_label = f"  Edit {self._active_name}" if self._active_name else "  Edit profile"
        option_list.add_option(Option(edit_label, id=_EDIT_OPTION_ID))
        option_list.add_option(Option("  New Profile...", id=_NEW_OPTION_ID))

        option_list.focus()

    @on(OptionList.OptionSelected, "#profile-options")
    def _on_selected(self, event: OptionList.OptionSelected) -> None:
        option = event.option
        if option.id == "__sep__":
            return
        if option.id == _EDIT_OPTION_ID:
            # Find the active profile to edit
            active = next(
                (p for p in self._profiles if p.name == self._active_name),
                None,
            )
            if active is not None:
                self.dismiss()
                self.post_message(self.EditRequested(active))
        elif option.id == _NEW_OPTION_ID:
            self.dismiss()
            self.post_message(self.NewRequested())
        elif event.option_index is not None and 0 <= event.option_index < len(self._profiles):
            self.dismiss()
            self.post_message(self.Selected(self._profiles[event.option_index]))

    def action_dismiss(self) -> None:
        self.dismiss()
