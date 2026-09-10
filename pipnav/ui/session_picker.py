"""Session picker modal — choose a session to resume, in any tool."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from textual import on
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from pipnav.core.session_center import format_age
from pipnav.core.sessions_all import AgentSession

TITLE_LIMIT = 60

# Each tool gets its own colour so the list is scannable by tool at a glance.
_HARNESS_COLOURS = {
    "claude": "bold green",
    "codex": "bold cyan",
    "opencode": "bold magenta",
}


class SessionPicker(ModalScreen):
    """Modal listing every resumable session for one project."""

    DEFAULT_CSS = """
    SessionPicker {
        align: center middle;
    }
    SessionPicker #session-container {
        width: 76;
        height: auto;
        max-height: 80%;
        border: solid $primary;
        background: $surface;
        color: $primary;
        padding: 1 2;
    }
    SessionPicker OptionList {
        background-tint: initial;
        height: auto;
        max-height: 22;
    }
    SessionPicker OptionList:focus {
        background-tint: initial;
    }
    """

    BINDINGS = [
        ("escape", "dismiss", "Close"),
    ]

    @dataclass
    class Selected(Message):
        """Fired when a session is chosen."""

        session: AgentSession

    def __init__(
        self, sessions: "tuple[AgentSession, ...]", project_name: str
    ) -> None:
        super().__init__()
        self._sessions = sessions
        self._project_name = project_name

    def session_at(self, index: int) -> AgentSession | None:
        """The session on the given row, or None when the row does not exist."""
        if 0 <= index < len(self._sessions):
            return self._sessions[index]
        return None

    @staticmethod
    def session_row(session: AgentSession) -> tuple[str, str]:
        """Render one session as (label, detail)."""
        title = (session.title or "(no description)").strip() or "(no description)"
        if len(title) > TITLE_LIMIT:
            title = title[: TITLE_LIMIT - 1] + "…"

        colour = _HARNESS_COLOURS.get(session.harness, "bold")
        label = f"[{colour}]{session.label}[/]  {title}"

        elapsed = (datetime.now() - session.last_active).total_seconds()
        age = format_age(max(0, int(elapsed)))
        detail = f"{age} ago"
        if session.cost:
            detail += f"  ·  ${session.cost:.2f}"
        return label, detail

    def compose(self) -> ComposeResult:
        with Vertical(id="session-container"):
            yield Static(
                f"[bold]RESUME IN {self._project_name.upper()}[/]"
                f"  [dim]Enter:resume  Esc:close[/]\n"
            )
            yield OptionList(id="session-options")

    def on_mount(self) -> None:
        option_list = self.query_one("#session-options", OptionList)

        if not self._sessions:
            option_list.add_option(
                Option("  [dim]No resumable sessions in this project[/]", id="__none__")
            )
            option_list.focus()
            return

        for index, session in enumerate(self._sessions):
            label, detail = self.session_row(session)
            option_list.add_option(
                Option(f"  {label}\n  [dim]{detail}[/]", id=str(index))
            )
        # Preselect the newest, so Enter resumes without arrowing down first.
        option_list.highlighted = 0
        option_list.focus()

    @on(OptionList.OptionSelected, "#session-options")
    def _on_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option.id == "__none__":
            return
        if event.option_index is None:
            return
        session = self.session_at(event.option_index)
        if session is None:
            return
        self.dismiss()
        self.post_message(self.Selected(session))

    def action_dismiss(self) -> None:
        self.dismiss()
