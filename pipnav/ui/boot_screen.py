"""Boot screen — ROBCO INDUSTRIES terminal animation."""

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static

BOOT_LINES = (
    "",
    "ROBCO INDUSTRIES (TM) TERMLINK PROTOCOL",
    "ENTER PASSWORD NOW",
    "",
    ">>> AUTHENTICATING...",
    ">>> ACCESS GRANTED",
    "",
    "LOADING PIPNAV v1.0...",
    "",
)


class BootScreen(Screen):
    """Animated boot sequence screen — skippable with any key."""

    DEFAULT_CSS = """
    BootScreen {
        background: #0A0A0A;
        color: #FFB000;
    }
    BootScreen #boot-text {
        padding: 2 4;
        text-style: bold;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._line_index = 0
        self._timer_handle: object | None = None

    def compose(self) -> ComposeResult:
        yield Static("", id="boot-text")

    def on_mount(self) -> None:
        """Start the typewriter animation."""
        self._timer_handle = self.set_interval(0.25, self._type_line)

    def _type_line(self) -> None:
        """Add the next line of boot text."""
        if self._line_index >= len(BOOT_LINES):
            self.set_timer(0.5, self._finish)
            if self._timer_handle is not None:
                self._timer_handle.stop()  # type: ignore[union-attr]
            return

        widget = self.query_one("#boot-text", Static)
        current = str(widget.renderable) if widget.renderable else ""
        line = BOOT_LINES[self._line_index]
        widget.update(current + "\n" + line)
        self._line_index += 1

    def _finish(self) -> None:
        """Dismiss the boot screen."""
        if self.is_current:
            self.app.pop_screen()

    def on_key(self, event: object) -> None:
        """Skip boot animation on any key press."""
        if self._timer_handle is not None:
            self._timer_handle.stop()  # type: ignore[union-attr]
        self._finish()
