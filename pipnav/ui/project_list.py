"""Project list — scrollable, selectable list with status badges."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from textual import on
from textual.app import ComposeResult
from textual.events import Key
from textual.message import Message
from textual.widget import Widget
from textual.widgets import OptionList
from textual.widgets.option_list import Option


@dataclass(frozen=True)
class ProjectEntry:
    """A project with its display badge."""

    name: str
    path: Path
    badge: str


class ProjectOptionList(OptionList):
    """OptionList where click highlights only; Enter fires OptionSelected."""

    DEFAULT_CSS = """
    ProjectOptionList {
        background-tint: initial;
    }
    ProjectOptionList:focus {
        background-tint: initial;
    }
    """

    _enter_pressed: bool = False

    def on_key(self, event: Key) -> None:
        """Track that Enter was pressed so action_select knows to fire."""
        if event.key == "enter":
            self._enter_pressed = True

    def action_select(self) -> None:
        """Only fire OptionSelected when triggered by Enter, not click."""
        if self._enter_pressed:
            self._enter_pressed = False
            super().action_select()
        # On click: do nothing extra — the highlight already changed via _on_click


class ProjectList(Widget):
    """Scrollable project list with keyboard navigation."""

    can_focus = False  # Let the inner OptionList handle focus

    @dataclass
    class Selected(Message):
        """Fired when a project highlight changes."""

        path: Path
        name: str

    @dataclass
    class Activated(Message):
        """Fired when Enter is pressed on a project."""

        path: Path
        name: str

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._entries: tuple[ProjectEntry, ...] = ()

    def compose(self) -> ComposeResult:
        yield ProjectOptionList(id="project-options")

    def set_projects(self, entries: tuple[ProjectEntry, ...]) -> None:
        """Update the project list with new entries."""
        self._entries = entries
        option_list = self.query_one("#project-options", ProjectOptionList)
        option_list.clear_options()
        for entry in entries:
            label = f"  {entry.name:<26} {entry.badge}"
            option_list.add_option(Option(label, id=str(entry.path)))

        # Select first item if available
        if entries:
            option_list.highlighted = 0
            self._fire_selected(0)

    @on(OptionList.OptionHighlighted, "#project-options")
    def _on_highlight(self, event: OptionList.OptionHighlighted) -> None:
        """Fire Selected message when highlight changes."""
        if event.option_index is not None:
            self._fire_selected(event.option_index)

    @on(OptionList.OptionSelected, "#project-options")
    def _on_selected(self, event: OptionList.OptionSelected) -> None:
        """Fire Activated message when Enter is pressed."""
        if event.option_index is not None and 0 <= event.option_index < len(self._entries):
            entry = self._entries[event.option_index]
            self.post_message(self.Activated(path=entry.path, name=entry.name))

    def _fire_selected(self, index: int) -> None:
        """Post a Selected message for the given index."""
        if 0 <= index < len(self._entries):
            entry = self._entries[index]
            self.post_message(self.Selected(path=entry.path, name=entry.name))

    def focus_list(self) -> None:
        """Focus the inner option list."""
        try:
            self.query_one("#project-options", ProjectOptionList).focus()
        except Exception:
            pass

    @property
    def highlighted_index(self) -> int | None:
        """Return the currently highlighted index."""
        try:
            return self.query_one("#project-options", ProjectOptionList).highlighted
        except Exception:
            return None

    @property
    def selected_entry(self) -> ProjectEntry | None:
        """Return the currently highlighted project entry."""
        idx = self.highlighted_index
        if idx is not None and 0 <= idx < len(self._entries):
            return self._entries[idx]
        return None
