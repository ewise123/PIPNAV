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
        self._last_scan: datetime | None = None
        self._profile_name: str = ""

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

    def update_freshness(self, last_scan: datetime | None) -> None:
        """Update the freshness indicator."""
        self._last_scan = last_scan
        self._refresh_display()

    def update_profile(self, name: str) -> None:
        """Update the active profile display."""
        self._profile_name = name
        self._refresh_display()

    def _refresh_display(self) -> None:
        """Re-render the status bar, adapting to terminal width."""
        hp_bar = make_bar(self.clean_projects, self.total_projects, 8)
        hp_text = f"{self.clean_projects}/{self.total_projects}"

        ap_bar = make_bar(
            self.projects_with_sessions,
            max(self.total_projects, 1),
            6,
        )
        ap_text = f"{self.projects_with_sessions}/{self.total_projects}"

        now = datetime.now().strftime("%m.%d.%Y %H:%M")

        # Width-aware: hide segments at narrow widths
        width = self.size.width
        # Guard: before layout, width is 0 — default to full display
        if width == 0:
            width = 200

        freshness = self._format_freshness()
        show_profile = width >= 80 and self._profile_name
        show_freshness = width >= 100

        profile = f"  │  [{self._profile_name}]" if show_profile else ""
        freshness_segment = f"  │  {freshness}" if show_freshness else ""

        self.update(
            f" HP:{hp_bar} {hp_text} clean"
            f"  │  AP:{ap_bar} {ap_text} w/ claude"
            f"{profile}"
            f"{freshness_segment}"
            f"  │  {now}"
        )

    def _format_freshness(self) -> str:
        """Format the freshness indicator."""
        if self._last_scan is None:
            return "scanning..."

        delta = (datetime.now() - self._last_scan).total_seconds()
        if delta < 5:
            return "live"
        elif delta < 60:
            return f"updated {int(delta)}s ago"
        elif delta < 3600:
            minutes = int(delta / 60)
            return f"updated {minutes}m ago"
        else:
            return "stale"
