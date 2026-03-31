"""Idle screen — PLEASE STAND BY test pattern after inactivity."""

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static

# Braille-character test pattern (crosshair, concentric circles, tick marks)
# Generated with drawille, hand-tuned for terminal display
STANDBY_ART = """\


                    ⣀⣀⣀⣀⣄⣀⣀⣀⡀
               ⢀⣀⣤⠤⠶⠒⠛⠛⠉⠉⠉⠉⠩⠭⡯⠭⠉⠉⠉⠉⠙⠛⠓⠲⠦⢤⣄⣀
           ⣀⣤⢶⣿⣯⣥        ⢀⣀⣀⣀⣇⣀⣀⣀        ⢠⣭⣿⣷⢦⣄⡀
        ⢀⣤⠞⠋ ⠸⠿⠿⠿ ⢀⣠⡤⠶⠚⠛⠉⠉⠉⠉⠉⡏⠉⠉⠉⠉⠙⠛⠲⠦⣤⣀ ⠸⠿⠿⠿ ⠈⠛⢦⣄
       ⣴⠟⠁     ⢀⣴⠞⠋⠁      ⢀⣈⣉⣏⣉⣀       ⠉⠛⢶⣄      ⠙⢷⡄
      ⣼⠏ ⡀    ⣰⡟⠁  ⡀  ⢀⣴⡶⠛⠉⠙⠛⡟⠛⠉⠙⠳⣶⣄   ⡀  ⠙⣷⡀    ⡀⠈⢿⡄
     ⠤⣿⠤⠤⡧⠤⠤⠤⠤⣿⠤⠤⠤⠤⡧⠤⠤⣿⠥⡧⠤⠤⠤⣶⣷⡦⠤⠤⠤⡧⢽⡧⠤⠤⡧⠤⠤⠤⢼⡧⠤⠤⠤⠤⡧⠤⢼⡧⠄
      ⢿⡄ ⠃    ⢻⣆   ⠃  ⠙⢷⣧⣀ ⢀⣀⣇⣀ ⢀⣠⣷⠟⠁  ⠃  ⢀⣾⠃    ⠃ ⣼⠇
      ⠈⢿⣄      ⠙⢷⣄⡀      ⠉⠙⠛⠛⡟⠛⠛⠉⠁      ⣀⣴⠟⠁     ⢀⣼⠏
        ⠙⠷⣄⡀ ⢠⣤⣤⣤⠈⠙⠳⠦⣤⣄⣀   ⠈⠉⡏⠉   ⢀⣀⣠⡤⠶⠛⠉⢠⣤⣤⣤  ⣀⡴⠟⠁
          ⠈⠛⠶⣼⣿⡿⠿     ⠈⠉⠉⠙⠛⠛⠛⡟⠛⠛⠛⠉⠉⠉     ⠸⠿⣿⣿⡴⠞⠋
              ⠉⠙⠓⠶⠦⣤⣀⣀⣀    ⠠⠤⡧⠤    ⢀⣀⣀⣠⡤⠴⠖⠛⠉⠁
                     ⠉⠉⠉⠉⠛⠛⠛⠛⠟⠛⠛⠛⠋⠉⠉⠉⠁


               ╔══════════════════════════════════╗
               ║     P L E A S E   S T A N D   B Y     ║
               ╚══════════════════════════════════╝

                      ╔══════════════════╗
                      ║  VAULT-TEC CORP. ║
                      ╚══════════════════╝

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
