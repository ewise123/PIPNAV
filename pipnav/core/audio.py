"""Audio playback — play Pip-Boy sound effects via PowerShell MediaPlayer."""

import os
import shutil
import subprocess
import threading
import time
from pathlib import Path

from pipnav.core.logging import get_logger

SOUNDS_DIR = Path(__file__).parent.parent / "sounds"
# Copy sounds to Windows-accessible path (UNC paths don't work for audio)
WIN_SOUNDS_DIR = Path("/mnt/c/Users") / Path.home().name / ".pipnav" / "sounds"

# Map sound names to files — add more as needed
SOUND_FILES: dict[str, str] = {
    "select": "pipboy-select.mp3",
}

_powershell: str | None = None
_win_sounds_path: str = ""
_last_play_time: float = 0
MIN_SOUND_GAP = 0.15


def _get_powershell() -> str | None:
    """Find powershell.exe on PATH."""
    global _powershell
    if _powershell is None:
        _powershell = shutil.which("powershell.exe") or ""
    return _powershell if _powershell else None


def init_audio() -> None:
    """Copy sound files to Windows-accessible path and cache locations."""
    global _win_sounds_path
    logger = get_logger()

    _get_powershell()

    # Create Windows-side sounds directory
    WIN_SOUNDS_DIR.mkdir(parents=True, exist_ok=True)

    # Copy all sound files to Windows path
    for filename in SOUND_FILES.values():
        src = SOUNDS_DIR / filename
        dst = WIN_SOUNDS_DIR / filename
        if src.exists() and (not dst.exists() or src.stat().st_size != dst.stat().st_size):
            try:
                shutil.copy2(src, dst)
                logger.debug("Copied sound: %s -> %s", src, dst)
            except OSError as exc:
                logger.debug("Failed to copy sound %s: %s", filename, exc)

    # Get the Windows path for the sounds directory
    try:
        result = subprocess.run(
            ["wslpath", "-w", str(WIN_SOUNDS_DIR)],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            _win_sounds_path = result.stdout.strip()
    except Exception:
        pass


def play_sound(name: str) -> None:
    """Play a named sound effect. Non-blocking, fire-and-forget, debounced."""
    global _last_play_time
    logger = get_logger()

    now = time.monotonic()
    if now - _last_play_time < MIN_SOUND_GAP:
        return
    _last_play_time = now

    filename = SOUND_FILES.get(name)
    if not filename or not _win_sounds_path:
        return

    ps = _get_powershell()
    if not ps:
        return

    win_file = f"{_win_sounds_path}\\{filename}"

    def _play() -> None:
        try:
            # Use -WindowStyle Hidden to prevent PowerShell window flash
            # Redirect stdout/stderr to NUL on the Windows side (not Python side,
            # which kills audio handles)
            cmd = (
                'Add-Type -AssemblyName presentationCore;'
                ' $p = New-Object System.Windows.Media.MediaPlayer;'
                f' $p.Open([Uri]"{win_file}");'
                ' $p.Play();'
                ' Start-Sleep -Milliseconds 3000'
            )
            subprocess.run(
                [ps, "-WindowStyle", "Hidden", "-NoProfile", "-c", cmd],
                stdout=open(os.devnull, "w"),
                stderr=open(os.devnull, "w"),
                stdin=subprocess.DEVNULL,
                timeout=5,
            )
        except Exception as exc:
            logger.debug("Failed to play sound %s: %s", name, exc)

    threading.Thread(target=_play, daemon=True).start()
