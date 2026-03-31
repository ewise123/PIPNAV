"""Idle screen — PLEASE STAND BY test pattern after inactivity."""

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static

# Hand-crafted ASCII test pattern inspired by Fallout's "Please Stand By"
# Uses box-drawing, circles approximated with Unicode, and geometric shapes
STANDBY_ART = """\


                    ╔══════════════════════════════════════════════╗
                    ║          .  .       |       .  .             ║
                    ║      .              |              .         ║
                    ║    .       ╱‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾╲       .       ║
                    ║   .      ╱    .     |     .    ╲      .      ║
                    ║         ╱          ╔╗          ╲             ║
                    ║  .     │      .────╫╫────.      │     .     ║
                    ║  ──────┼───────────╫╫───────────┼──────     ║
                    ║  .     │      .────╫╫────.      │     .     ║
                    ║         ╲          ╚╝          ╱             ║
                    ║   .      ╲    .     |     .    ╱      .      ║
                    ║    .       ╲_______________╱       .       ║
                    ║      .              |              .         ║
                    ║          .  .       |       .  .             ║
                    ║                                              ║
                    ║        ╔══════════════════════════╗          ║
                    ║        ║   PLEASE   STAND   BY    ║          ║
                    ║        ╚══════════════════════════╝          ║
                    ║                                              ║
                    ║           ╔════════════════════╗             ║
                    ║           ║  VAULT-TEC  CORP.  ║             ║
                    ║           ╚════════════════════╝             ║
                    ╚══════════════════════════════════════════════╝

"""


class IdleScreen(Screen):
    """Displayed after period of inactivity. Dismiss on any key or click."""

    DEFAULT_CSS = """
    IdleScreen {
        background: $surface;
        color: $primary;
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

    def on_click(self, event: object) -> None:
        """Dismiss on click."""
        self.dismiss()
