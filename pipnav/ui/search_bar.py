"""Search bar — inline fuzzy search input."""

from __future__ import annotations

from dataclasses import dataclass

from textual.app import ComposeResult
from textual.events import Key
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Input


class SearchInput(Input):
    """Input that emits a dismiss message on Escape."""

    DEFAULT_CSS = """
    SearchInput {
        background-tint: initial;
    }
    SearchInput:focus {
        background-tint: initial;
    }
    """

    class Dismissed(Message):
        """Fired when Escape is pressed."""

    def on_key(self, event: Key) -> None:
        """Intercept Escape before Input consumes it."""
        if event.key == "escape":
            event.stop()
            event.prevent_default()
            self.post_message(self.Dismissed())


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
        yield SearchInput(placeholder="Search projects...", id="search-input")

    def watch_is_searching(self, value: bool) -> None:
        """Show/hide and focus the search bar."""
        self.display = value
        if value:
            inp = self.query_one("#search-input", SearchInput)
            inp.value = ""
            inp.focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        """Forward query changes."""
        self.post_message(self.QueryChanged(query=event.value))

    def on_search_input_dismissed(self, event: SearchInput.Dismissed) -> None:
        """Close search when Escape is pressed in the input."""
        self.is_searching = False
        self.post_message(self.SearchClosed())
