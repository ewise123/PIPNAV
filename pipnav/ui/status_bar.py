"""Pip-Boy status bar — replaces default Footer with live gauges."""

from __future__ import annotations

from datetime import datetime

from textual.app import ComposeResult
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static

from pipnav.core.stats import make_bar


class StatusBar(Widget):
    """Pip-Boy style status bar with HP, AP, and timestamp gauges."""

    DEFAULT_CSS = """
    StatusBar {
        dock: bottom;
        height: 1;
        background: $surface;
        color: $primary;
        border-top: solid $secondary;
        padding: 0 1;
    }
    """

    total_projects: reactive[int] = reactive(0)
    clean_projects: reactive[int] = reactive(0)
    active_sessions: reactive[int] = reactive(0)

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._timer: object | None = None

    def compose(self) -> ComposeResult:
        yield Static(self._render(), id="status-content")

    def on_mount(self) -> None:
        """Start clock update timer."""
        self._timer = self.set_interval(30, self._tick)

    def _tick(self) -> None:
        """Update the clock."""
        self._refresh_display()

    def watch_total_projects(self, value: int) -> None:
        self._refresh_display()

    def watch_clean_projects(self, value: int) -> None:
        self._refresh_display()

    def watch_active_sessions(self, value: int) -> None:
        self._refresh_display()

    def update_stats(
        self, total: int, clean: int, sessions: int
    ) -> None:
        """Update all stats at once."""
        self.total_projects = total
        self.clean_projects = clean
        self.active_sessions = sessions

    def _render(self) -> str:
        """Render the status bar content."""
        hp_bar = make_bar(self.clean_projects, self.total_projects, 8)
        hp_text = f"{self.clean_projects}/{self.total_projects}"

        ap_bar = make_bar(self.active_sessions, max(self.active_sessions, 4), 4)
        ap_text = str(self.active_sessions)

        now = datetime.now().strftime("%m.%d.%Y %H:%M")

        return (
            f" HP:{hp_bar} {hp_text} clean"
            f"  │  AP:{ap_bar} {ap_text} sessions"
            f"  │  {now}"
        )

    def _refresh_display(self) -> None:
        """Re-render the status bar."""
        try:
            self.query_one("#status-content", Static).update(self._render())
        except Exception:
            pass
