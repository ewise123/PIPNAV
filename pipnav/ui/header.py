"""PipNav header — ASCII logo and tab indicators."""

from textual.app import ComposeResult
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


class PipNavHeader(Widget):
    """Header with ASCII logo and tab bar."""

    active_tab: reactive[str] = reactive("STAT")

    def compose(self) -> ComposeResult:
        yield Static(LOGO, id="logo")
        yield Static(self._render_tabs(), id="tab-bar")

    def watch_active_tab(self, tab: str) -> None:
        """Update tab bar when active tab changes."""
        try:
            tab_bar = self.query_one("#tab-bar", Static)
            tab_bar.update(self._render_tabs())
        except Exception:
            pass

    def _render_tabs(self) -> str:
        """Render tab indicators with active tab highlighted."""
        parts: list[str] = []
        for name in TAB_NAMES:
            if name == self.active_tab:
                parts.append(f"[reverse bold] {name} [/]")
            else:
                parts.append(f"[dim] {name} [/]")
        return "  ".join(parts)
