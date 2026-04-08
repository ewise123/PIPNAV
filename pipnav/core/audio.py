"""Audio playback via a native Windows NAudio helper with legacy fallback."""

from __future__ import annotations

import filecmp
import shutil
import subprocess
import time
from pathlib import Path

from pipnav.core.logging import get_logger

SOUNDS_DIR = Path(__file__).parent.parent / "sounds"
VENDOR_DIR = Path(__file__).parent.parent / "vendor" / "naudio"
WIN_SOUNDS_DIR = Path("/mnt/c/Users") / Path.home().name / ".pipnav" / "sounds"
HELPER_SOURCE = SOUNDS_DIR / "player.cs"
LEGACY_PLAYER_SCRIPT = SOUNDS_DIR / "player.ps1"
NAUDIO_DLL = VENDOR_DIR / "NAudio.dll"
HELPER_EXE_NAME = "pipnav-audio-helper.exe"
CSC_CANDIDATES = (
    Path("/mnt/c/Windows/Microsoft.NET/Framework64/v4.0.30319/csc.exe"),
    Path("/mnt/c/Windows/Microsoft.NET/Framework/v4.0.30319/csc.exe"),
)

SOUND_FILES: dict[str, str] = {
    "boot": "UI_PipBoy_BootSequence_A.mp3",
    "tab": "pipboy-select.mp3",
    "navigate": "UI_PipBoy_Favorite_Menu_Dpad_B.mp3",
    "crt_on": "UI_PipBoy_LightOn.mp3",
    "crt_off": "UI_PipBoy_LightOff.mp3",
    "launch": "UI_Pipboy_OK.mp3",
}

_powershell: str | None = None
_csc: str | None = None
_win_sounds_path: str = ""
_win_legacy_player_script: str = ""
_win_audio_helper: str = ""
_audio_backend: str = ""
_last_play_time: float = 0
_muted: bool = False
MIN_SOUND_GAP = 0.15

_audio_process: subprocess.Popen | None = None


def _get_powershell() -> str | None:
    """Find powershell.exe on PATH."""
    global _powershell
    if _powershell is None:
        _powershell = shutil.which("powershell.exe") or ""
    return _powershell if _powershell else None


def _get_csc() -> str | None:
    """Find the Windows C# compiler."""
    global _csc
    if _csc is None:
        for candidate in CSC_CANDIDATES:
            if candidate.exists():
                _csc = str(candidate)
                break
        else:
            _csc = ""
    return _csc if _csc else None


def _to_windows_path(path: Path) -> str:
    """Convert a WSL path to a Windows path."""
    try:
        result = subprocess.run(
            ["wslpath", "-w", str(path)],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception:
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def _quote_powershell(value: str) -> str:
    """Escape a string for use inside a single-quoted PowerShell string."""
    return value.replace("'", "''")


def _copy_if_needed(src: Path, dst: Path, logger) -> bool:
    """Copy a file when missing or changed."""
    if not src.exists():
        logger.debug("Missing audio asset %s", src)
        return False

    try:
        src_stat = src.stat()
        dst_stat = dst.stat() if dst.exists() else None
        needs_copy = (
            dst_stat is None
            or src_stat.st_size != dst_stat.st_size
            or not filecmp.cmp(src, dst, shallow=False)
        )
        if needs_copy:
            shutil.copy2(src, dst)
    except OSError as exc:
        logger.debug("Failed to copy %s: %s", src.name, exc)
        return False

    return True


def _sync_legacy_player_script(logger) -> str:
    """Copy the legacy PowerShell player script for cleanup-only support."""
    dst = WIN_SOUNDS_DIR / LEGACY_PLAYER_SCRIPT.name
    if not _copy_if_needed(LEGACY_PLAYER_SCRIPT, dst, logger):
        return ""
    return _to_windows_path(dst)


def _helper_paths() -> tuple[Path, Path, Path]:
    """Return the Windows-local helper source, DLL, and EXE paths."""
    return (
        WIN_SOUNDS_DIR / HELPER_SOURCE.name,
        WIN_SOUNDS_DIR / NAUDIO_DLL.name,
        WIN_SOUNDS_DIR / HELPER_EXE_NAME,
    )


def _build_helper_if_needed(logger) -> str:
    """Copy and build the Windows audio helper, returning its Windows path."""
    source_dst, dll_dst, exe_dst = _helper_paths()

    if not _copy_if_needed(HELPER_SOURCE, source_dst, logger):
        return ""
    if not _copy_if_needed(NAUDIO_DLL, dll_dst, logger):
        return ""

    needs_rebuild = (
        not exe_dst.exists()
        or source_dst.stat().st_mtime_ns > exe_dst.stat().st_mtime_ns
        or dll_dst.stat().st_mtime_ns > exe_dst.stat().st_mtime_ns
    )
    if not needs_rebuild:
        return _to_windows_path(exe_dst)

    csc = _get_csc()
    if not csc:
        logger.debug("Windows C# compiler not found")
        return ""

    win_source = _to_windows_path(source_dst)
    win_dll = _to_windows_path(dll_dst)
    win_exe = _to_windows_path(exe_dst)
    if not win_source or not win_dll or not win_exe:
        logger.debug("Failed to resolve Windows helper paths")
        return ""

    try:
        result = subprocess.run(
            [
                csc,
                "/nologo",
                "/optimize+",
                "/target:exe",
                f"/out:{win_exe}",
                f"/reference:{win_dll}",
                win_source,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except Exception as exc:
        logger.debug("Failed to compile audio helper: %s", exc)
        return ""

    if result.returncode != 0:
        logger.debug(
            "Audio helper build failed (code %s): %s %s",
            result.returncode,
            result.stdout.strip(),
            result.stderr.strip(),
        )
        return ""

    return win_exe


def _cleanup_stale_players(win_script: str) -> None:
    """Stop any legacy PowerShell helpers for the current script path."""
    ps = _get_powershell()
    if not ps or not win_script:
        return

    quoted_script = _quote_powershell(win_script)
    command = (
        f"$script = '{quoted_script}'; "
        "Get-CimInstance Win32_Process | "
        "Where-Object { "
        "$_.Name -eq 'powershell.exe' -and "
        "$_.CommandLine -like \"*$script*\" "
        "} | "
        "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
    )
    try:
        subprocess.run(
            [ps, "-NoProfile", "-Command", command],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=5,
        )
    except Exception:
        return


def _cleanup_stale_helpers(win_helper: str) -> None:
    """Stop any stale native helper processes for the current exe path."""
    ps = _get_powershell()
    if not ps or not win_helper:
        return

    quoted_helper = _quote_powershell(win_helper)
    command = (
        f"$helper = '{quoted_helper}'; "
        "Get-CimInstance Win32_Process | "
        "Where-Object { $_.ExecutablePath -eq $helper } | "
        "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
    )
    try:
        subprocess.run(
            [ps, "-NoProfile", "-Command", command],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=5,
        )
    except Exception:
        return


def _helper_command() -> list[str]:
    """Build the native helper launch command."""
    helper_path = WIN_SOUNDS_DIR / HELPER_EXE_NAME
    return [
        str(helper_path),
        *[
            f"{name}={_win_sounds_path}\\{filename}"
            for name, filename in SOUND_FILES.items()
        ],
    ]


def _legacy_command() -> list[str]:
    """Build the legacy PowerShell player launch command."""
    ps = _get_powershell()
    if not ps or not _win_legacy_player_script:
        return []
    return [
        ps,
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        _win_legacy_player_script,
    ]


def _start_player() -> subprocess.Popen | None:
    """Start the persistent audio player, preferring the native helper."""
    global _audio_backend, _audio_process, _win_audio_helper

    if _audio_process is not None and _audio_process.poll() is None:
        return _audio_process

    logger = get_logger()
    _audio_backend = ""

    if not _win_audio_helper:
        _win_audio_helper = _build_helper_if_needed(logger)

    if _win_audio_helper:
        _cleanup_stale_helpers(_win_audio_helper)
        try:
            proc = subprocess.Popen(
                _helper_command(),
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
            )
            _audio_backend = "helper"
            _audio_process = proc
            return _audio_process
        except Exception as exc:
            logger.debug("Failed to start audio helper: %s", exc)

    command = _legacy_command()
    if not command:
        return None

    logger.debug("Falling back to legacy PowerShell audio player")
    _cleanup_stale_players(_win_legacy_player_script)
    try:
        proc = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        _audio_backend = "legacy"
        _audio_process = proc
        return _audio_process
    except Exception as exc:
        logger.debug("Failed to start legacy audio player: %s", exc)
        return None


def init_audio() -> None:
    """Copy sound files to Windows path and start the persistent helper."""
    global _audio_backend, _audio_process, _win_audio_helper, _win_legacy_player_script, _win_sounds_path
    logger = get_logger()
    _audio_backend = ""

    WIN_SOUNDS_DIR.mkdir(parents=True, exist_ok=True)

    for filename in dict.fromkeys(SOUND_FILES.values()):
        _copy_if_needed(SOUNDS_DIR / filename, WIN_SOUNDS_DIR / filename, logger)

    _win_sounds_path = _to_windows_path(WIN_SOUNDS_DIR)
    _win_legacy_player_script = _sync_legacy_player_script(logger)
    if _win_legacy_player_script:
        _cleanup_stale_players(_win_legacy_player_script)

    _win_audio_helper = _build_helper_if_needed(logger)
    if _win_audio_helper:
        _cleanup_stale_helpers(_win_audio_helper)

    _audio_process = _start_player()


def shutdown_audio() -> None:
    """Shut down the persistent helper if it is running."""
    global _audio_backend, _audio_process

    proc = _audio_process
    _audio_process = None
    backend = _audio_backend
    _audio_backend = ""

    if proc is None:
        return

    if proc.stdin is not None:
        try:
            proc.stdin.write("quit\n")
            proc.stdin.flush()
        except Exception:
            pass
        try:
            proc.stdin.close()
        except Exception:
            pass

    try:
        proc.wait(timeout=0.5)
        return
    except Exception:
        pass

    try:
        proc.terminate()
    except Exception:
        pass

    try:
        proc.wait(timeout=0.5)
        return
    except Exception:
        pass

    if backend == "helper" and _win_audio_helper:
        _cleanup_stale_helpers(_win_audio_helper)
    elif backend == "legacy" and _win_legacy_player_script:
        _cleanup_stale_players(_win_legacy_player_script)

    try:
        proc.kill()
    except Exception:
        pass

    try:
        proc.wait(timeout=0.5)
    except Exception:
        pass


def play_sound(name: str) -> None:
    """Play a named sound effect. Non-blocking, low-latency, debounced."""
    global _audio_process, _last_play_time

    if _muted:
        return

    now = time.monotonic()
    if now - _last_play_time < MIN_SOUND_GAP:
        return
    _last_play_time = now

    if name not in SOUND_FILES or not _win_sounds_path:
        return

    if _audio_process is None or _audio_process.poll() is not None:
        _audio_process = _start_player()

    if _audio_process is None or _audio_process.stdin is None:
        return

    try:
        if _audio_backend == "legacy":
            _audio_process.stdin.write(
                f"{_win_sounds_path}\\{SOUND_FILES[name]}\n"
            )
        else:
            _audio_process.stdin.write(name + "\n")
        _audio_process.stdin.flush()
    except Exception:
        shutdown_audio()
