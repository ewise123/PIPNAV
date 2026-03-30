"""SESSIONS tab — list resumable Claude Code sessions for the selected project."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from textual import on, work
from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from pipnav.core.claude_sessions import ClaudeSession, discover_sessions_for_project
from pipnav.core.utils import time_ago


class SessionsTab(VerticalScroll):
    """Shows Claude Code sessions available to resume."""

    project_path: reactive[Path | None] = reactive(None)

    @dataclass
    class SessionActivated(Message):
        """Fired when Enter is pressed on a session."""

        session_id: str
        project_path: Path

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._sessions: tuple[ClaudeSession, ...] = ()

    def compose(self) -> ComposeResult:
        yield Static(
            "Select a project to view Claude sessions", id="sessions-placeholder"
        )
        yield OptionList(id="session-options")

    def on_mount(self) -> None:
        """Hide the option list until sessions are loaded."""
        self.query_one("#session-options", OptionList).display = False

    def watch_project_path(self, path: Path | None) -> None:
        """Load sessions when project changes."""
        if path is not None:
            self._load_sessions(path)
        else:
            self._sessions = ()
            self._show_placeholder("Select a project to view Claude sessions")

    @work(exclusive=True, thread=True)
    def _load_sessions(self, path: Path) -> None:
        """Discover sessions in background thread."""
        sessions = discover_sessions_for_project(path)
        self.app.call_from_thread(self._update_sessions, sessions)

    def _update_sessions(self, sessions: tuple[ClaudeSession, ...]) -> None:
        """Update the session list."""
        self._sessions = sessions
        option_list = self.query_one("#session-options", OptionList)
        option_list.clear_options()

        if not sessions:
            self._show_placeholder("No Claude sessions found for this project")
            return

        self.query_one("#sessions-placeholder", Static).display = False
        option_list.display = True

        for session in sessions:
            time_str = time_ago(session.timestamp)
            label = (
                f"  {session.first_message}\n"
                f"  [dim]{time_str} \u2014 {session.message_count} messages[/]"
            )
            option_list.add_option(Option(label, id=session.session_id))

    def _show_placeholder(self, text: str) -> None:
        """Show placeholder text and hide the option list."""
        placeholder = self.query_one("#sessions-placeholder", Static)
        placeholder.update(text)
        placeholder.display = True
        self.query_one("#session-options", OptionList).display = False

    @on(OptionList.OptionSelected, "#session-options")
    def _on_session_selected(self, event: OptionList.OptionSelected) -> None:
        """Fire SessionActivated when Enter is pressed on a session."""
        if event.option_index is not None and 0 <= event.option_index < len(self._sessions):
            session = self._sessions[event.option_index]
            self.post_message(
                self.SessionActivated(
                    session_id=session.session_id,
                    project_path=Path(session.project_path),
                )
            )
