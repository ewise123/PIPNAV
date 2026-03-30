"""Project detail panel — shows metadata for the selected project."""

from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static

from pipnav.core.git import GitStatus
from pipnav.core.notes import ProjectNotes
from pipnav.core.sessions import SessionInfo
from pipnav.core.utils import read_readme_preview, time_ago


class ProjectDetail(Widget):
    """Detail panel showing metadata for the selected project."""

    project_path: reactive[Path | None] = reactive(None)
    project_name: reactive[str] = reactive("")

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._git_status: GitStatus | None = None
        self._session: SessionInfo | None = None
        self._notes: ProjectNotes = ProjectNotes()
        self._readme: str = ""

    def compose(self) -> ComposeResult:
        yield Static("Select a project", id="detail-content")

    def update_detail(
        self,
        name: str,
        path: Path,
        git_status: GitStatus | None,
        session: SessionInfo | None,
        notes: ProjectNotes,
        readme: str,
    ) -> None:
        """Update all detail fields and re-render."""
        self._git_status = git_status
        self._session = session
        self._notes = notes
        self._readme = readme
        self.project_name = name
        self.project_path = path
        self._render_detail()

    def _render_detail(self) -> None:
        """Render the detail content."""
        lines: list[str] = []
        path = self.project_path
        name = self.project_name

        if path is None:
            self._update_content("Select a project")
            return

        lines.append(f"[bold]NAME:[/]    {name}")
        lines.append(f"[bold]PATH:[/]    {path}")

        gs = self._git_status
        if gs is not None:
            branch_info = gs.branch
            if gs.ahead > 0:
                branch_info += f" (+{gs.ahead} ahead)"
            if gs.behind > 0:
                branch_info += f" (-{gs.behind} behind)"
            lines.append(f"[bold]BRANCH:[/]  {branch_info}")

            status_parts: list[str] = []
            if gs.modified_count > 0:
                status_parts.append(f"{gs.modified_count} modified")
            if gs.staged_count > 0:
                status_parts.append(f"{gs.staged_count} staged")
            if gs.untracked_count > 0:
                status_parts.append(f"{gs.untracked_count} untracked")
            status_text = ", ".join(status_parts) if status_parts else "clean"
            lines.append(f"[bold]STATUS:[/]  {status_text}")
            lines.append(f"[bold]LAST:[/]    {time_ago(gs.last_commit_time)}")
        else:
            lines.append("[bold]GIT:[/]     Not a git repository")

        # Claude Code session
        if self._session is not None and self._session.resumable:
            session_text = f"Session resumable ({time_ago(self._session.last_session)})"
        else:
            session_text = "No session"
        lines.append(f"[bold]CLAUDE:[/]  {session_text}")

        # Tags
        if self._notes.tags:
            lines.append(f"[bold]TAGS:[/]    {', '.join(self._notes.tags)}")

        # README preview
        if self._readme:
            lines.append("")
            lines.append("[bold]README:[/]  " + "─" * 40)
            for readme_line in self._readme.split("\n"):
                lines.append(f"  {readme_line}")

        # Notes
        if self._notes.note:
            lines.append("")
            lines.append(f"[bold]NOTE:[/]    {self._notes.note}")

        self._update_content("\n".join(lines))

    def _update_content(self, text: str) -> None:
        """Update the static content widget."""
        try:
            self.query_one("#detail-content", Static).update(text)
        except Exception:
            pass
