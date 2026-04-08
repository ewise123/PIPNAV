"""Help overlay — keybinding reference modal."""

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Static

HELP_TEXT = """\
[bold]PIPNAV — KEYBINDING REFERENCE[/]

[bold]Navigation[/]
  ↑/↓ or j/k      Navigate project list
  l (right)        Focus right panel
  h (left)         Focus back to project list
  Enter            Drill into folder / activate
  Backspace        Go back to parent
  Esc              Go back / close / quit
  Tab              Cycle tabs
  1-5              STAT / FILES / LOG / CONSOLE / INV

[bold]Actions[/]
  v                Open project in VS Code
  c                Launch Claude Code
  r                Resume Claude Code session
  a                Launch recipe picker

[bold]Project[/]
  t                Cycle tag on selected project
  n                Edit project memory
  N                Quick inline note
  /                Fuzzy search projects
  .                Refresh all project metadata

[bold]Console[/]
  f                Cycle filter
  o                Cycle sort mode

[bold]Workspace[/]
  w                Switch workspace profile
  p                Cycle color scheme (green/amber/blue/white)
  ~ or `           Toggle sound effects
  ?                Show this help
  q or Esc         Quit

[dim]↑/↓ to scroll · Esc or ? to close[/]\
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
        border: solid $primary;
        background: $surface;
        color: $primary;
        padding: 1 2;
    }
    """

    BINDINGS = [
        ("escape", "dismiss", "Close"),
        ("question_mark", "dismiss", "Close"),
    ]

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="help-container"):
            yield Static(HELP_TEXT)

    def action_dismiss(self) -> None:
        """Close the help overlay."""
        self.dismiss()
