"""PipNav header — ASCII logo and clickable tab indicators."""

from dataclasses import dataclass

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static

LOGO = """\
██████╗ ██╗██████╗ ███╗   ██╗ █████╗ ██╗   ██╗
██╔══██╗██║██╔══██╗████╗  ██║██╔══██╗██║   ██║
██████╔╝██║██████╔╝██╔██╗ ██║███████║██║   ██║
██╔═══╝ ██║██╔═══╝ ██║╚██╗██║██╔══██║╚██╗ ██╔╝
██║     ██║██║     ██║ ╚████║██║  ██║ ╚████╔╝
╚═╝     ╚═╝╚═╝     ╚═╝  ╚═══╝╚═╝  ╚═╝  ╚═══╝\
"""

TAB_NAMES = ("STAT", "FILES", "LOG", "CONSOLE", "INV")


class TabButton(Static):
    """One tab name. Clicking it switches tabs.

    A plain Static has no click handling, so the old single-string tab bar
    looked like a row of buttons and did nothing when clicked.
    """

    def __init__(self, tab_name: str) -> None:
        super().__init__(f" {tab_name} ", classes="tab-button")
        self.tab_name = tab_name

    def on_click(self) -> None:
        self.post_message(PipNavHeader.TabClicked(self.tab_name))


class PipNavHeader(Widget):
    """Header with ASCII logo and tab bar."""

    active_tab: reactive[str] = reactive("STAT")

    @dataclass
    class TabClicked(Message):
        """Fired when a tab name is clicked."""

        tab_name: str

    def compose(self) -> ComposeResult:
        yield Static(LOGO, id="logo")
        with Horizontal(id="tab-bar"):
            for name in TAB_NAMES:
                yield TabButton(name)

    def watch_active_tab(self, tab: str) -> None:
        """Highlight whichever tab is showing."""
        try:
            for button in self.query(TabButton):
                button.set_class(button.tab_name == tab, "-active")
        except Exception:
            pass

    def on_mount(self) -> None:
        self.watch_active_tab(self.active_tab)
