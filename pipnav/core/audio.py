"""Audio playback — play Pip-Boy sound effects via PowerShell MediaPlayer."""

import shutil
import subprocess
import time
from pathlib import Path

from pipnav.core.logging import get_logger

SOUNDS_DIR = Path(__file__).parent.parent / "sounds"

# Map sound names to files — add more as needed
SOUND_FILES: dict[str, str] = {
    "select": "pipboy-select.mp3",
}

# Cache of WSL -> Windows path conversions
_win_paths: dict[str, str] = {}
_powershell: str | None = None
_last_play_time: float = 0
# Minimum gap between sounds in seconds (prevents spam on rapid scrolling)
MIN_SOUND_GAP = 0.15


def _get_powershell() -> str | None:
    """Find powershell.exe on PATH."""
    global _powershell
    if _powershell is None:
        _powershell = shutil.which("powershell.exe") or ""
    return _powershell if _powershell else None


def _get_win_path(posix_path: Path) -> str | None:
    """Convert a WSL path to a Windows path. Cached."""
    key = str(posix_path)
    if key not in _win_paths:
        try:
            result = subprocess.run(
                ["wslpath", "-w", key],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                _win_paths[key] = result.stdout.strip()
            else:
                return None
        except Exception:
            return None
    return _win_paths.get(key)


def init_audio() -> None:
    """Pre-cache Windows paths for all sound files at startup."""
    for filename in SOUND_FILES.values():
        sound_path = SOUNDS_DIR / filename
        if sound_path.exists():
            _get_win_path(sound_path)
    # Also cache powershell location
    _get_powershell()


def play_sound(name: str) -> None:
    """Play a named sound effect. Non-blocking, fire-and-forget, debounced."""
    global _last_play_time
    logger = get_logger()

    # Debounce — skip if too soon after last sound
    now = time.monotonic()
    if now - _last_play_time < MIN_SOUND_GAP:
        return
    _last_play_time = now

    filename = SOUND_FILES.get(name)
    if not filename:
        return

    sound_path = SOUNDS_DIR / filename
    if not sound_path.exists():
        logger.debug("Sound file not found: %s", sound_path)
        return

    ps = _get_powershell()
    if not ps:
        return

    win_path = _get_win_path(sound_path)
    if not win_path:
        return

    try:
        cmd = (
            "Add-Type -AssemblyName presentationCore;"
            " $p = New-Object System.Windows.Media.MediaPlayer;"
            f" $p.Open([Uri]'{win_path}');"
            " $p.Play();"
            " Start-Sleep -Milliseconds 500"
        )
        subprocess.Popen(
            [ps, "-c", cmd],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as exc:
        logger.debug("Failed to play sound %s: %s", name, exc)
