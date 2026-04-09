"""SESSION CENTER tab — cross-project Claude session dashboard."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from textual import on, work
from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.message import Message
from textual.widgets import DataTable, Static

from pipnav.core.projects import ProjectInfo
from pipnav.core.session_center import (
    STATUS_BADGES,
    EnrichedSession,
    discover_all_sessions,
    filter_sessions,
    format_age,
    sort_sessions,
)


class SessionCenterTable(DataTable):
    """DataTable with no background tint on focus."""

    DEFAULT_CSS = """
    SessionCenterTable {
        background-tint: initial;
    }
    SessionCenterTable:focus {
        background-tint: initial;
    }
    """


FILTER_CYCLE = ("all", "active", "resumable", "idle", "stale")
SORT_CYCLE = ("timestamp", "project", "messages", "status")


class SessionCenterTab(VerticalScroll):
    """Cross-project Claude session dashboard."""

    @dataclass
    class SessionActivated(Message):
        """Fired when Enter is pressed on a session row."""

        session_id: str
        project_path: Path

    @dataclass
    class ProjectJump(Message):
        """Fired when user wants to jump to a session's project."""

        project_path: Path

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._all_sessions: tuple[EnrichedSession, ...] = ()
        self._visible_sessions: tuple[EnrichedSession, ...] = ()
        self._current_filter: str = "all"
        self._current_sort: str = "timestamp"
        self._loading: bool = False
        self._project_filter: Path | None = None

    def compose(self) -> ComposeResult:
        yield Static(self._render_filter_bar(), id="session-filter-bar")
        yield SessionCenterTable(id="session-center-table")
        yield Static("Loading sessions...", id="session-center-placeholder")

    def on_mount(self) -> None:
        """Set up the table columns."""
        table = self.query_one("#session-center-table", SessionCenterTable)
        table.cursor_type = "row"
        table.zebra_stripes = False
        table.add_columns("STS", "PROJECT", "BRANCH", "SESSION", "MSG", "AGE")
        table.display = False

    def load_sessions(
        self,
        projects: tuple[ProjectInfo, ...],
        background: bool = False,
    ) -> None:
        """Trigger background session discovery for all projects."""
        self._loading = True
        if not background or not self._all_sessions:
            self._show_placeholder("Scanning sessions...")
        self._discover_sessions(projects)

    @work(exclusive=True, thread=True)
    def _discover_sessions(self, projects: tuple[ProjectInfo, ...]) -> None:
        """Discover all sessions in background."""
        sessions = discover_all_sessions(projects)
        self.app.call_from_thread(self._update_sessions, sessions)

    def _update_sessions(self, sessions: tuple[EnrichedSession, ...]) -> None:
        """Update session data and rebuild the table."""
        self._all_sessions = sessions
        self._loading = False
        self._apply_filter_and_sort()

    def set_project_filter(self, path: Path | None) -> None:
        """Scope the view to sessions belonging to a specific project."""
        self._project_filter = path
        self._apply_filter_and_sort()

    def clear_project_filter(self) -> None:
        """Remove the project-scope filter and show all projects."""
        self.set_project_filter(None)

    def _apply_filter_and_sort(self) -> None:
        """Apply current filter and sort, then rebuild the table."""
        filtered = filter_sessions(self._all_sessions, self._current_filter)
        if self._project_filter is not None:
            project_str = str(self._project_filter)
            filtered = tuple(
                s for s in filtered if s.project_path == project_str
            )
        sorted_sessions = sort_sessions(filtered, self._current_sort)
        self._visible_sessions = sorted_sessions
        self._rebuild_table()

    def _rebuild_table(self) -> None:
        """Rebuild the DataTable rows, preserving cursor position."""
        table = self.query_one("#session-center-table", SessionCenterTable)
        prev_row = table.cursor_row
        prev_session = self.get_selected_session()
        table.clear()

        # Always update filter bar, even when no rows to display
        self.query_one("#session-filter-bar", Static).update(
            self._render_filter_bar()
        )

        if not self._visible_sessions:
            if self._all_sessions:
                self._show_placeholder(
                    f"No {self._current_filter} sessions found"
                )
            else:
                self._show_placeholder("No Claude sessions found across projects")
            return

        self.query_one("#session-center-placeholder", Static).display = False
        table.display = True

        for session in self._visible_sessions:
            badge = STATUS_BADGES.get(session.status, session.status)
            prompt = session.last_prompt
            if len(prompt) > 50:
                prompt = prompt[:47] + "..."
            age = format_age(session.age_seconds)
            msg_count = str(session.message_count)

            table.add_row(
                badge,
                session.project_name,
                session.branch,
                prompt,
                msg_count,
                age,
            )

        # Restore cursor position
        if prev_session is not None:
            for row_idx, session in enumerate(self._visible_sessions):
                if session.session_id == prev_session.session_id:
                    table.move_cursor(row=row_idx)
                    break
            else:
                if prev_row is not None and prev_row < len(self._visible_sessions):
                    table.move_cursor(row=prev_row)
        elif prev_row is not None and prev_row < len(self._visible_sessions):
            table.move_cursor(row=prev_row)


    def _show_placeholder(self, text: str) -> None:
        """Show placeholder text and hide the table."""
        placeholder = self.query_one("#session-center-placeholder", Static)
        placeholder.update(text)
        placeholder.display = True
        self.query_one("#session-center-table", SessionCenterTable).display = False

    def _render_filter_bar(self) -> str:
        """Render the filter/sort indicator bar."""
        # Count by status (respecting project filter for accurate counts)
        base = self._all_sessions
        if self._project_filter is not None:
            project_str = str(self._project_filter)
            base = tuple(s for s in base if s.project_path == project_str)

        counts: dict[str, int] = {"all": len(base)}
        for s in base:
            counts[s.status] = counts.get(s.status, 0) + 1

        parts: list[str] = []
        for f in FILTER_CYCLE:
            count = counts.get(f, 0)
            label = f"{f.upper()}({count})"
            if f == self._current_filter:
                parts.append(f"[reverse bold] {label} [/]")
            else:
                parts.append(f"[dim] {label} [/]")

        sort_label = f"sort:{self._current_sort}"
        project_label = ""
        hint = "[dim]f:filter  o:sort  Enter:resume[/]"
        if self._project_filter is not None:
            project_name = self._project_filter.name
            project_label = f"  │  viewing: {project_name}"
            hint = "[dim]f:all projects  o:sort  Enter:resume[/]"

        return f"  {'  '.join(parts)}  │  {sort_label}{project_label}  │  {hint}"

    def cycle_filter(self) -> None:
        """Cycle to next filter."""
        try:
            idx = FILTER_CYCLE.index(self._current_filter)
            self._current_filter = FILTER_CYCLE[(idx + 1) % len(FILTER_CYCLE)]
        except ValueError:
            self._current_filter = "all"
        self._apply_filter_and_sort()

    def cycle_sort(self) -> None:
        """Cycle to next sort mode."""
        try:
            idx = SORT_CYCLE.index(self._current_sort)
            self._current_sort = SORT_CYCLE[(idx + 1) % len(SORT_CYCLE)]
        except ValueError:
            self._current_sort = "timestamp"
        self._apply_filter_and_sort()

    @on(DataTable.RowSelected, "#session-center-table")
    def _on_row_selected(self, event: DataTable.RowSelected) -> None:
        """Resume the selected session."""
        if event.cursor_row is not None and 0 <= event.cursor_row < len(self._visible_sessions):
            session = self._visible_sessions[event.cursor_row]
            self.post_message(
                self.SessionActivated(
                    session_id=session.session_id,
                    project_path=Path(session.project_path),
                )
            )

    def get_selected_session(self) -> EnrichedSession | None:
        """Return the currently highlighted session, if any."""
        table = self.query_one("#session-center-table", SessionCenterTable)
        row = table.cursor_row
        if row is not None and 0 <= row < len(self._visible_sessions):
            return self._visible_sessions[row]
        return None

    @property
    def session_count(self) -> int:
        return len(self._all_sessions)
