"""Boot screen — VAULT-TEC INDUSTRIES terminal boot with typewriter effect."""

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static

from pipnav.core.audio import play_sound

BOOT_LINES = (
    "",
    "VAULT-TEC INDUSTRIES (TM)",
    "ROBCO UNIFIED OPERATING SYSTEM V.85",
    "COPYRIGHT 2075-2077 ROBCO INDUSTRIES",
    "",
    "INITIALIZING SYSTEM...",
    "",
    "64K RAM SYSTEM  [OK]",
    "HOLOTAPE DRIVE  [OK]",
    "RADIO MODULE    [OK]",
    "V.A.T.S. CORE   [OK]",
    "",
    "LOADING PIPNAV NAVIGATION SYSTEM...",
    "",
    ">>> AUTHENTICATING USER...",
    ">>> ACCESS GRANTED",
    "",
    "WELCOME, VAULT DWELLER",
)

# Chars per second for typewriter effect
CHARS_PER_SECOND = 60
CHAR_INTERVAL = 1.0 / CHARS_PER_SECOND
# Pause after each line completes (seconds)
LINE_PAUSE = 0.08
# Longer pause after blank lines
BLANK_PAUSE = 0.15


class BootScreen(Screen):
    """Animated boot sequence with typewriter effect — skippable with any key."""

    DEFAULT_CSS = """
    BootScreen {
        background: $surface;
        color: $primary;
    }
    BootScreen #boot-text {
        padding: 2 4;
        text-style: bold;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._line_index = 0
        self._char_index = 0
        self._completed_text = ""
        self._current_line = ""
        self._timer_handle: object | None = None
        self._skipped = False

    def compose(self) -> ComposeResult:
        yield Static("", id="boot-text")

    def on_mount(self) -> None:
        """Start the typewriter animation and play boot sound."""
        play_sound("boot")
        self._start_next_line()

    def _start_next_line(self) -> None:
        """Begin typing the next line."""
        if self._skipped:
            return
        if self._line_index >= len(BOOT_LINES):
            self.set_timer(0.3, self._finish)
            return

        self._current_line = BOOT_LINES[self._line_index]
        self._char_index = 0

        if not self._current_line:
            # Blank line — just append and pause
            self._completed_text += "\n"
            self._update_display()
            self._line_index += 1
            self._timer_handle = self.set_timer(
                BLANK_PAUSE, self._start_next_line
            )
        else:
            # Start typing characters
            self._timer_handle = self.set_interval(
                CHAR_INTERVAL, self._type_char
            )

    def _type_char(self) -> None:
        """Type the next character of the current line."""
        if self._skipped:
            return
        if self._char_index >= len(self._current_line):
            # Line complete
            if self._timer_handle is not None:
                self._timer_handle.stop()  # type: ignore[union-attr]
            self._completed_text += "\n" + self._current_line
            self._update_display()
            self._line_index += 1
            self._timer_handle = self.set_timer(
                LINE_PAUSE, self._start_next_line
            )
            return

        self._char_index += 1
        # Show completed lines + partially typed current line
        partial = self._current_line[: self._char_index]
        display = self._completed_text + "\n" + partial + "█"
        self._update_display(display)

    def _update_display(self, text: str | None = None) -> None:
        """Update the boot text widget."""
        try:
            content = text if text is not None else self._completed_text
            self.query_one("#boot-text", Static).update(content)
        except Exception:
            pass

    def _finish(self) -> None:
        """Dismiss the boot screen."""
        self._stop_timer()
        if self.is_current:
            self.dismiss()

    def _stop_timer(self) -> None:
        """Stop any running timer."""
        if self._timer_handle is not None:
            try:
                self._timer_handle.stop()  # type: ignore[union-attr]
            except Exception:
                pass
            self._timer_handle = None

    def on_key(self, event: object) -> None:
        """Skip boot animation on any key press."""
        self._skipped = True
        self._stop_timer()
        self._finish()
