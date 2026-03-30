"""Help overlay — keybinding reference modal."""

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static

HELP_TEXT = """\
[bold]PIPNAV — KEYBINDING REFERENCE[/]

[bold]Navigation[/]
  ↑/↓ or j/k      Navigate project list
  Tab              Cycle tabs (STAT / FILES / LOG)
  1 / 2 / 3       Jump to STAT / FILES / LOG tab

[bold]Actions[/]
  Enter            Open project in VS Code
  c                Launch Claude Code (auto-mode)
  r                Resume Claude Code session
  f                Open project folder in VS Code

[bold]Project[/]
  t                Cycle tag on selected project
  n                Edit note for selected project
  /                Fuzzy search projects
  F5               Refresh all project metadata

[bold]Display[/]
  ~ or `           Toggle CRT effects
  ?                Show this help
  q or Esc         Quit

[dim]Press Esc or ? to close[/]\
"""


class HelpScreen(ModalScreen):
    """Modal keybinding help overlay."""

    DEFAULT_CSS = """
    HelpScreen {
        align: center middle;
    }
    HelpScreen #help-container {
        width: 56;
        height: auto;
        max-height: 80%;
        border: solid #FFB000;
        background: #0A0A0A;
        color: #FFB000;
        padding: 1 2;
    }
    """

    BINDINGS = [
        ("escape", "dismiss", "Close"),
        ("question_mark", "dismiss", "Close"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="help-container"):
            yield Static(HELP_TEXT)

    def action_dismiss(self) -> None:
        """Close the help overlay."""
        self.app.pop_screen()
