"""LOG tab — git log for the selected project."""

from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static
from textual import work

from pipnav.core.git import GitLogEntry, get_git_log
from pipnav.core.utils import time_ago


class LogTab(Widget):
    """Git log display for the selected project."""

    project_path: reactive[Path | None] = reactive(None)

    def compose(self) -> ComposeResult:
        yield Static("Select a project to view git log", id="log-content")

    def watch_project_path(self, path: Path | None) -> None:
        """Load git log when project changes."""
        if path is not None:
            self._load_log(path)

    @work(exclusive=True, thread=True)
    def _load_log(self, path: Path) -> None:
        """Fetch git log in background thread."""
        entries = get_git_log(path, max_entries=20)
        rendered = self._render_log(entries)
        self.app.call_from_thread(self._update_content, rendered)

    def _render_log(self, entries: tuple[GitLogEntry, ...]) -> str:
        """Format git log entries for display."""
        if not entries:
            return "No git history available"

        lines: list[str] = []
        for entry in entries:
            lines.append(
                f"[bold]{entry.sha_short}[/]  {entry.message}"
            )
            lines.append(
                f"  [dim]{entry.author} \u2014 {time_ago(entry.timestamp)}[/]"
            )
            lines.append("")

        return "\n".join(lines)

    def _update_content(self, text: str) -> None:
        """Update the log display."""
        try:
            self.query_one("#log-content", Static).update(text)
        except Exception:
            pass
