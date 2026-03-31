"""Audio playback — play Pip-Boy sound effects via a persistent PowerShell process."""

import os
import shutil
import subprocess
import threading
import time
from pathlib import Path

from pipnav.core.logging import get_logger

SOUNDS_DIR = Path(__file__).parent.parent / "sounds"
WIN_SOUNDS_DIR = Path("/mnt/c/Users") / Path.home().name / ".pipnav" / "sounds"

SOUND_FILES: dict[str, str] = {
    "select": "pipboy-select.mp3",
}

_powershell: str | None = None
_win_sounds_path: str = ""
_last_play_time: float = 0
MIN_SOUND_GAP = 0.15

# Persistent PowerShell process for low-latency playback
_ps_process: subprocess.Popen | None = None
_ps_lock = threading.Lock()


def _get_powershell() -> str | None:
    """Find powershell.exe on PATH."""
    global _powershell
    if _powershell is None:
        _powershell = shutil.which("powershell.exe") or ""
    return _powershell if _powershell else None


def _start_ps_process() -> subprocess.Popen | None:
    """Start a persistent PowerShell process that listens for commands on stdin."""
    ps = _get_powershell()
    if not ps:
        return None
    try:
        proc = subprocess.Popen(
            [ps, "-NoProfile", "-WindowStyle", "Hidden", "-Command", "-"],
            stdin=subprocess.PIPE,
            stdout=open(os.devnull, "w"),
            stderr=open(os.devnull, "w"),
            text=True,
        )
        # Preload the assembly once
        if proc.stdin:
            proc.stdin.write("Add-Type -AssemblyName presentationCore\n")
            proc.stdin.flush()
        return proc
    except Exception:
        return None


def init_audio() -> None:
    """Copy sound files to Windows path and start persistent PowerShell."""
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
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            _win_sounds_path = result.stdout.strip()
    except Exception:
        pass

    _ps_process = _start_ps_process()


def play_sound(name: str) -> None:
    """Play a named sound effect. Non-blocking, low-latency, debounced."""
    global _last_play_time, _ps_process
    logger = get_logger()

    now = time.monotonic()
    if now - _last_play_time < MIN_SOUND_GAP:
        return
    _last_play_time = now

    filename = SOUND_FILES.get(name)
    if not filename or not _win_sounds_path:
        return

    win_file = f"{_win_sounds_path}\\{filename}"

    def _play() -> None:
        global _ps_process
        with _ps_lock:
            # Restart if process died
            if _ps_process is None or _ps_process.poll() is not None:
                _ps_process = _start_ps_process()

            if _ps_process is None or _ps_process.stdin is None:
                return

            try:
                cmd = (
                    f'$p = New-Object System.Windows.Media.MediaPlayer;'
                    f' $p.Open([Uri]"{win_file}");'
                    f' $p.Play();'
                    f' Start-Sleep -Milliseconds 3000\n'
                )
                _ps_process.stdin.write(cmd)
                _ps_process.stdin.flush()
            except Exception as exc:
                logger.debug("Failed to play sound %s: %s", name, exc)
                _ps_process = None

    threading.Thread(target=_play, daemon=True).start()
