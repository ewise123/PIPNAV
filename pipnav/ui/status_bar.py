"""Pip-Boy status bar — replaces default Footer with live gauges."""

from __future__ import annotations

from datetime import datetime

from textual.reactive import reactive
from textual.widgets import Static

from pipnav.core.stats import make_bar


class StatusBar(Static):
    """Pip-Boy style status bar with HP and AP gauges."""

    DEFAULT_CSS = """
    StatusBar {
        dock: bottom;
        height: 2;
        background: $surface;
        color: $primary;
        border-top: solid $secondary;
    }
    """

    total_projects: reactive[int] = reactive(0)
    clean_projects: reactive[int] = reactive(0)
    projects_with_sessions: reactive[int] = reactive(0)

    def __init__(self, **kwargs: object) -> None:
        super().__init__("", **kwargs)
        self._timer: object | None = None

    def on_mount(self) -> None:
        """Start clock update timer."""
        self._timer = self.set_interval(30, self._tick)
        self._refresh_display()

    def _tick(self) -> None:
        """Update the clock."""
        self._refresh_display()

    def watch_total_projects(self, value: int) -> None:
        self._refresh_display()

    def watch_clean_projects(self, value: int) -> None:
        self._refresh_display()

    def watch_projects_with_sessions(self, value: int) -> None:
        self._refresh_display()

    def update_stats(self, total: int, clean: int, with_sessions: int) -> None:
        """Update all stats at once."""
        self.total_projects = total
        self.clean_projects = clean
        self.projects_with_sessions = with_sessions

    def _refresh_display(self) -> None:
        """Re-render the status bar."""
        hp_bar = make_bar(self.clean_projects, self.total_projects, 8)
        hp_text = f"{self.clean_projects}/{self.total_projects}"

        ap_bar = make_bar(
            self.projects_with_sessions,
            max(self.total_projects, 1),
            6,
        )
        ap_text = f"{self.projects_with_sessions}/{self.total_projects}"

        now = datetime.now().strftime("%m.%d.%Y %H:%M")

        self.update(
            f" HP:{hp_bar} {hp_text} clean"
            f"  │  AP:{ap_bar} {ap_text} w/ claude"
            f"  │  {now}"
        )
