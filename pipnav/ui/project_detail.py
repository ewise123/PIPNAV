"""Project detail panel — shows metadata for the selected project."""

from __future__ import annotations

from pathlib import Path

from textual import work
from textual.app import ComposeResult
from textual.color import Color
from textual.containers import VerticalScroll
from textual.reactive import reactive
from textual.widgets import Sparkline, Static

from pipnav.core.git import GitStatus, get_commit_frequency
from pipnav.core.memory import ProjectMemory
from pipnav.core.notes import ProjectNotes
from pipnav.core.sessions import SessionInfo
from pipnav.core.utils import time_ago


class ProjectDetail(VerticalScroll):
    """Detail panel showing metadata for the selected project."""

    project_path: reactive[Path | None] = reactive(None)
    project_name: reactive[str] = reactive("")

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._git_status: GitStatus | None = None
        self._session: SessionInfo | None = None
        self._notes: ProjectNotes = ProjectNotes()
        self._memory: ProjectMemory | None = None
        self._readme: str = ""

    def compose(self) -> ComposeResult:
        yield Static("Select a project", id="detail-content")
        yield Static("[bold]ACTIVITY:[/] (30 days)", id="sparkline-label")
        yield Sparkline([], id="detail-sparkline")

    def on_mount(self) -> None:
        """Hide sparkline initially."""
        self.query_one("#sparkline-label", Static).display = False
        self.query_one("#detail-sparkline", Sparkline).display = False

    def update_detail(
        self,
        name: str,
        path: Path,
        git_status: GitStatus | None,
        session: SessionInfo | None,
        notes: ProjectNotes,
        readme: str,
        memory: ProjectMemory | None = None,
    ) -> None:
        """Update all detail fields and re-render."""
        self._git_status = git_status
        self._session = session
        self._notes = notes
        self._memory = memory
        self._readme = readme
        self.project_name = name
        self.project_path = path
        self._render_detail()

        # Load sparkline data in background
        if git_status is not None:
            self._load_sparkline(path)
        else:
            self.query_one("#sparkline-label", Static).display = False
            self.query_one("#detail-sparkline", Sparkline).display = False

    @work(exclusive=True, thread=True)
    def _load_sparkline(self, path: Path) -> None:
        """Fetch commit frequency in background."""
        data = get_commit_frequency(path, days=30)
        self.app.call_from_thread(self._update_sparkline, data)

    def _update_sparkline(self, data: tuple[float, ...]) -> None:
        """Update the sparkline widget with commit data."""
        sparkline = self.query_one("#detail-sparkline", Sparkline)
        label = self.query_one("#sparkline-label", Static)
        if data and any(d > 0 for d in data):
            sparkline.data = list(data)
            sparkline.display = True
            label.display = True
        else:
            sparkline.display = False
            label.display = False

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

        if self._session is not None and self._session.resumable:
            session_text = f"Session resumable ({time_ago(self._session.last_session)})"
        else:
            session_text = "No session"
        lines.append(f"[bold]CLAUDE:[/]  {session_text}")

        if self._notes.tags:
            lines.append(f"[bold]TAGS:[/]    {', '.join(self._notes.tags)}")

        # Show memory fields prominently after tags
        mem = self._memory
        if mem is not None and any((mem.handoff, mem.next_action, mem.gotchas, mem.prompts)):
            lines.append("")
            lines.append("[bold]── MEMORY ──[/]")
            if mem.handoff:
                lines.append(f"[bold yellow]HANDOFF:[/] {mem.handoff}")
            if mem.next_action:
                lines.append(f"[bold yellow]NEXT:[/]    {mem.next_action}")
            if mem.gotchas:
                lines.append(f"[bold]GOTCHAS:[/] {'; '.join(mem.gotchas)}")
            if mem.prompts:
                lines.append(f"[bold]PROMPTS:[/] {'; '.join(mem.prompts)}")

        if self._notes.note:
            lines.append("")
            lines.append(f"[bold]NOTE:[/]    {self._notes.note}")

        if self._readme:
            lines.append("")
            lines.append("[bold]README:[/]  " + "─" * 40)
            for readme_line in self._readme.split("\n"):
                lines.append(f"  {readme_line}")

        self._update_content("\n".join(lines))

    def _update_content(self, text: str) -> None:
        """Update the static content widget."""
        try:
            self.query_one("#detail-content", Static).update(text)
        except Exception:
            pass
