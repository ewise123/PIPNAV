"""Idle screen — PLEASE STAND BY test pattern after inactivity."""

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static

STANDBY_ART = """\




              ╔══════════════════════════════════════╗
              ║                                      ║
              ║                                      ║
              ║         P L E A S E                   ║
              ║                                      ║
              ║       S T A N D   B Y                 ║
              ║                                      ║
              ║                                      ║
              ║      ╔════════════════════╗           ║
              ║      ║  VAULT-TEC CORP.   ║           ║
              ║      ╚════════════════════╝           ║
              ║                                      ║
              ╚══════════════════════════════════════╝



"""


class IdleScreen(Screen):
    """Displayed after period of inactivity. Dismiss on any key."""

    DEFAULT_CSS = """
    IdleScreen {
        background: #0D2B0D;
        color: #8EFE55;
        align: center middle;
    }
    IdleScreen #standby-text {
        text-align: center;
        text-style: bold;
        width: auto;
        height: auto;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static(STANDBY_ART, id="standby-text")

    def on_key(self, event: object) -> None:
        """Dismiss on any key press."""
        self.dismiss()
