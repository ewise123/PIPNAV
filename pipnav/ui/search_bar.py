"""Search bar — inline fuzzy search input."""

from __future__ import annotations

from dataclasses import dataclass

from textual.app import ComposeResult
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Input


class SearchBar(Widget):
    """Inline search input triggered by /."""

    is_searching: reactive[bool] = reactive(False)

    @dataclass
    class QueryChanged(Message):
        """Fired when the search query changes."""

        query: str

    @dataclass
    class SearchClosed(Message):
        """Fired when search is dismissed."""

    def compose(self) -> ComposeResult:
        yield Input(placeholder="Search projects...", id="search-input")

    def watch_is_searching(self, value: bool) -> None:
        """Show/hide and focus the search bar."""
        self.display = value
        if value:
            inp = self.query_one("#search-input", Input)
            inp.value = ""
            inp.focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        """Forward query changes."""
        self.post_message(self.QueryChanged(query=event.value))

    def on_key(self, event: object) -> None:
        """Close search on Escape."""
        # Textual Key event has a .key attribute
        if hasattr(event, "key") and event.key == "escape":  # type: ignore[union-attr]
            self.is_searching = False
            self.post_message(self.SearchClosed())
