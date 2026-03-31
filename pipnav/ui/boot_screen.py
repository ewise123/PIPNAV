"""Boot screen — VAULT-TEC INDUSTRIES terminal boot animation."""

import random

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static

BOOT_STAGES = (
    # (text, delay_seconds)
    ("", 0.15),
    ("VAULT-TEC INDUSTRIES (TM)", 0.08),
    ("ROBCO UNIFIED OPERATING SYSTEM V.85", 0.08),
    ("COPYRIGHT 2075-2077 ROBCO INDUSTRIES", 0.08),
    ("", 0.15),
    ("INITIALIZING SYSTEM...", 0.3),
    ("", 0.1),
    ("MEMORY TEST:  ", 0.05),  # Will be replaced with counting
    ("64K RAM SYSTEM  [OK]", 0.1),
    ("HOLOTAPE DRIVE  [OK]", 0.1),
    ("RADIO MODULE    [OK]", 0.1),
    ("V.A.T.S. CORE   [OK]", 0.1),
    ("", 0.15),
    ("LOADING PIPNAV NAVIGATION SYSTEM...", 0.2),
    ("", 0.1),
    (">>> AUTHENTICATING USER...", 0.25),
    (">>> ACCESS GRANTED", 0.15),
    ("", 0.1),
    ("WELCOME, VAULT DWELLER", 0.3),
    ("", 0.2),
)

HEX_CHARS = "0123456789ABCDEF"


def _random_hex_line() -> str:
    """Generate a fake hex dump line."""
    addr = random.randint(0x1000, 0xFFFF)
    values = " ".join(
        f"{random.randint(0, 255):02X}" for _ in range(8)
    )
    return f"0x{addr:04X}  {values}"


class BootScreen(Screen):
    """Animated boot sequence — skippable with any key."""

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
        self._stage_index = 0
        self._timer_handle: object | None = None
        self._current_text = ""
        self._mem_count = 0

    def compose(self) -> ComposeResult:
        yield Static("", id="boot-text")

    def on_mount(self) -> None:
        """Start the boot animation."""
        self._advance_stage()

    def _advance_stage(self) -> None:
        """Process the next boot stage."""
        if self._stage_index >= len(BOOT_STAGES):
            self.set_timer(0.3, self._finish)
            return

        text, delay = BOOT_STAGES[self._stage_index]

        # Special handling for memory test line
        if text == "MEMORY TEST:  ":
            self._current_text += "\n" + text
            self._mem_count = 0
            self._timer_handle = self.set_interval(0.02, self._count_memory)
            return

        self._current_text += "\n" + text
        self._update_display()
        self._stage_index += 1
        self._timer_handle = self.set_timer(delay, self._advance_stage)

    def _count_memory(self) -> None:
        """Animate the memory test counter."""
        self._mem_count += 4
        if self._mem_count >= 64:
            if self._timer_handle is not None:
                self._timer_handle.stop()  # type: ignore[union-attr]
            # Replace the memory test line with the final count
            lines = self._current_text.split("\n")
            lines[-1] = "MEMORY TEST:  64K OK"
            self._current_text = "\n".join(lines)
            self._update_display()
            self._stage_index += 1
            self._timer_handle = self.set_timer(0.15, self._advance_stage)
        else:
            lines = self._current_text.split("\n")
            lines[-1] = f"MEMORY TEST:  {self._mem_count}K"
            self._current_text = "\n".join(lines)
            self._update_display()

    def _update_display(self) -> None:
        """Update the boot text widget."""
        try:
            self.query_one("#boot-text", Static).update(self._current_text)
        except Exception:
            pass

    def _finish(self) -> None:
        """Dismiss the boot screen."""
        if self._timer_handle is not None:
            try:
                self._timer_handle.stop()  # type: ignore[union-attr]
            except Exception:
                pass
        if self.is_current:
            self.dismiss()

    def on_key(self, event: object) -> None:
        """Skip boot animation on any key press."""
        if self._timer_handle is not None:
            try:
                self._timer_handle.stop()  # type: ignore[union-attr]
            except Exception:
                pass
        self._finish()
