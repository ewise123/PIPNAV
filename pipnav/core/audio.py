"""Audio playback — play Pip-Boy sound effects via a persistent PowerShell player."""

import os
import shutil
import subprocess
import time
from pathlib import Path

from pipnav.core.logging import get_logger

SOUNDS_DIR = Path(__file__).parent.parent / "sounds"
WIN_SOUNDS_DIR = Path("/mnt/c/Users") / Path.home().name / ".pipnav" / "sounds"
PLAYER_SCRIPT = SOUNDS_DIR / "player.ps1"

SOUND_FILES: dict[str, str] = {
    "boot": "UI_PipBoy_BootSequence_A.mp3",
    "tab": "pipboy-select.mp3",
    "navigate": "UI_PipBoy_Favorite_Menu_Dpad_B.mp3",
    "crt_on": "UI_PipBoy_LightOn.mp3",
    "crt_off": "UI_PipBoy_LightOff.mp3",
    "launch": "UI_Pipboy_OK.mp3",
}

_powershell: str | None = None
_win_sounds_path: str = ""
_last_play_time: float = 0
MIN_SOUND_GAP = 0.15

# Persistent PowerShell player process
_ps_process: subprocess.Popen | None = None


def _get_powershell() -> str | None:
    """Find powershell.exe on PATH."""
    global _powershell
    if _powershell is None:
        _powershell = shutil.which("powershell.exe") or ""
    return _powershell if _powershell else None


def _start_player() -> subprocess.Popen | None:
    """Start the persistent PowerShell player script."""
    ps = _get_powershell()
    if not ps:
        return None

    # Copy player script to Windows side
    dst = WIN_SOUNDS_DIR / "player.ps1"
    try:
        shutil.copy2(PLAYER_SCRIPT, dst)
    except OSError:
        return None

    try:
        win_script = subprocess.run(
            ["wslpath", "-w", str(dst)],
            capture_output=True, text=True, timeout=5,
        ).stdout.strip()

        proc = subprocess.Popen(
            [ps, "-NoProfile", "-ExecutionPolicy", "Bypass",
             "-File", win_script],
            stdin=subprocess.PIPE,
            stdout=open(os.devnull, "w"),
            stderr=open(os.devnull, "w"),
            text=True,
        )
        return proc
    except Exception:
        return None


def init_audio() -> None:
    """Copy sound files to Windows path and start persistent player."""
    global _win_sounds_path, _ps_process
    logger = get_logger()

    _get_powershell()
    WIN_SOUNDS_DIR.mkdir(parents=True, exist_ok=True)

    for filename in SOUND_FILES.values():
        src = SOUNDS_DIR / filename
        dst = WIN_SOUNDS_DIR / filename
        if src.exists() and (not dst.exists() or src.stat().st_size != dst.stat().st_size):
            try:
                shutil.copy2(src, dst)
            except OSError as exc:
                logger.debug("Failed to copy sound %s: %s", filename, exc)

    try:
        result = subprocess.run(
            ["wslpath", "-w", str(WIN_SOUNDS_DIR)],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            _win_sounds_path = result.stdout.strip()
    except Exception:
        pass

    _ps_process = _start_player()
    # Wait for PowerShell to load the assembly and be ready
    if _ps_process is not None:
        time.sleep(1.0)


def play_sound(name: str) -> None:
    """Play a named sound effect. Non-blocking, low-latency, debounced."""
    global _last_play_time, _ps_process

    now = time.monotonic()
    if now - _last_play_time < MIN_SOUND_GAP:
        return
    _last_play_time = now

    filename = SOUND_FILES.get(name)
    if not filename or not _win_sounds_path:
        return

    if _ps_process is None or _ps_process.poll() is not None:
        _ps_process = _start_player()

    if _ps_process is None or _ps_process.stdin is None:
        return

    win_file = f"{_win_sounds_path}\\{filename}"

    try:
        _ps_process.stdin.write(win_file + "\n")
        _ps_process.stdin.flush()
    except Exception:
        _ps_process = None
