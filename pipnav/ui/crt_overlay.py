"""CRT effects — scanline overlay and flicker animation."""

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static


class CRTOverlay(Widget):
    """Simulated CRT scanline overlay.

    When mounted and visible, renders alternating dim lines over the screen
    to simulate a CRT monitor effect.
    """

    DEFAULT_CSS = """
    CRTOverlay {
        layer: overlay;
        dock: top;
        width: 100%;
        height: 100%;
        background: transparent;
        color: #0A0A0A 30%;
    }
    """

    can_focus = False

    def compose(self) -> ComposeResult:
        yield Static("", id="scanlines")

    def on_mount(self) -> None:
        """Generate scanline pattern on mount."""
        self._update_scanlines()

    def on_resize(self, event: object) -> None:
        """Regenerate scanlines when terminal resizes."""
        self._update_scanlines()

    def _update_scanlines(self) -> None:
        """Render scanline pattern matching terminal height."""
        try:
            height = self.size.height
            lines: list[str] = []
            for i in range(height):
                if i % 2 == 0:
                    lines.append("[on #111111]" + " " * 200 + "[/]")
                else:
                    lines.append("")
            self.query_one("#scanlines", Static).update("\n".join(lines))
        except Exception:
            pass
