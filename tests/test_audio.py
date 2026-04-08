"""Tests for audio helper lifecycle."""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest

import pipnav.core.audio as audio
from pipnav.main import PipNavApp


@pytest.fixture(autouse=True)
def _reset_audio_state(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reset mutable module state between tests."""
    monkeypatch.setattr(audio, "_powershell", "powershell.exe")
    monkeypatch.setattr(audio, "_csc", "/mnt/c/Windows/Microsoft.NET/Framework64/v4.0.30319/csc.exe")
    monkeypatch.setattr(audio, "_win_sounds_path", r"C:\Users\ewise\.pipnav\sounds")
    monkeypatch.setattr(
        audio,
        "_win_legacy_player_script",
        r"C:\Users\ewise\.pipnav\sounds\player.ps1",
    )
    monkeypatch.setattr(
        audio,
        "_win_audio_helper",
        r"C:\Users\ewise\.pipnav\sounds\pipnav-audio-helper.exe",
    )
    monkeypatch.setattr(audio, "_audio_backend", "")
    monkeypatch.setattr(audio, "_last_play_time", 0.0)
    monkeypatch.setattr(audio, "_muted", False)
    monkeypatch.setattr(audio, "_audio_process", None)


def _make_process() -> MagicMock:
    """Build a mock process with a writable stdin."""
    proc = MagicMock()
    proc.stdin = MagicMock()
    proc.poll.return_value = None
    return proc


def test_shutdown_audio_graceful() -> None:
    proc = _make_process()
    audio._audio_process = proc

    audio.shutdown_audio()

    proc.stdin.write.assert_called_once_with("quit\n")
    proc.stdin.flush.assert_called_once()
    proc.stdin.close.assert_called_once()
    proc.wait.assert_called_once_with(timeout=0.5)
    proc.terminate.assert_not_called()
    proc.kill.assert_not_called()
    assert audio._audio_process is None


def test_shutdown_audio_forces_termination(monkeypatch: pytest.MonkeyPatch) -> None:
    proc = _make_process()
    proc.wait.side_effect = [
        subprocess.TimeoutExpired("pipnav-audio-helper.exe", 0.5),
        subprocess.TimeoutExpired("pipnav-audio-helper.exe", 0.5),
        None,
    ]
    cleanup = MagicMock()
    monkeypatch.setattr(audio, "_cleanup_stale_helpers", cleanup)
    audio._audio_process = proc
    audio._audio_backend = "helper"

    audio.shutdown_audio()

    proc.terminate.assert_called_once_with()
    cleanup.assert_called_once_with(audio._win_audio_helper)
    proc.kill.assert_called_once_with()
    assert proc.wait.call_count == 3
    assert audio._audio_process is None


def test_play_sound_noop_when_muted(monkeypatch: pytest.MonkeyPatch) -> None:
    audio._muted = True
    start_player = MagicMock()
    monkeypatch.setattr(audio, "_start_player", start_player)

    audio.play_sound("tab")

    start_player.assert_not_called()


def test_play_sound_restarts_dead_helper(monkeypatch: pytest.MonkeyPatch) -> None:
    dead_proc = _make_process()
    dead_proc.poll.return_value = 1
    live_proc = _make_process()
    start_player = MagicMock(return_value=live_proc)
    monkeypatch.setattr(audio, "_start_player", start_player)
    monkeypatch.setattr(audio.time, "monotonic", lambda: 10.0)
    audio._audio_process = dead_proc

    audio.play_sound("tab")

    start_player.assert_called_once_with()
    live_proc.stdin.write.assert_called_once_with("tab\n")
    live_proc.stdin.flush.assert_called_once()


def test_init_audio_starts_player(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    proc = _make_process()
    monkeypatch.setattr(audio, "WIN_SOUNDS_DIR", tmp_path / "sounds")
    monkeypatch.setattr(audio, "SOUNDS_DIR", tmp_path / "src_sounds")
    monkeypatch.setattr(audio, "SOUND_FILES", {})
    monkeypatch.setattr(audio, "_to_windows_path", MagicMock(return_value=audio._win_sounds_path))
    monkeypatch.setattr(
        audio,
        "_sync_legacy_player_script",
        MagicMock(return_value=audio._win_legacy_player_script),
    )
    monkeypatch.setattr(audio, "_cleanup_stale_players", MagicMock())
    monkeypatch.setattr(audio, "_build_helper_if_needed", MagicMock(return_value=audio._win_audio_helper))
    monkeypatch.setattr(audio, "_cleanup_stale_helpers", MagicMock())
    monkeypatch.setattr(audio, "_start_player", MagicMock(return_value=proc))
    monkeypatch.setattr(audio, "get_logger", MagicMock())

    audio.init_audio()

    audio._start_player.assert_called_once_with()
    audio._cleanup_stale_players.assert_called_once_with(audio._win_legacy_player_script)
    audio._cleanup_stale_helpers.assert_called_once_with(audio._win_audio_helper)
    assert audio._audio_process is proc


def test_build_helper_invokes_csc_when_exe_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    helper_source = tmp_path / "player.cs"
    helper_source.write_text("// helper")
    naudio_dll = tmp_path / "NAudio.dll"
    naudio_dll.write_bytes(b"dll")
    win_dir = tmp_path / "windows"
    win_dir.mkdir()
    logger = MagicMock()
    run = MagicMock(return_value=subprocess.CompletedProcess(["csc"], 0, "", ""))

    monkeypatch.setattr(audio, "HELPER_SOURCE", helper_source)
    monkeypatch.setattr(audio, "NAUDIO_DLL", naudio_dll)
    monkeypatch.setattr(audio, "WIN_SOUNDS_DIR", win_dir)
    monkeypatch.setattr(audio, "_to_windows_path", lambda path: f"WIN::{path.name}")
    monkeypatch.setattr(audio.subprocess, "run", run)

    win_helper = audio._build_helper_if_needed(logger)

    assert win_helper == "WIN::pipnav-audio-helper.exe"
    assert (win_dir / "player.cs").exists()
    assert (win_dir / "NAudio.dll").exists()
    assert run.call_args.args[0] == [
        audio._csc,
        "/nologo",
        "/optimize+",
        "/target:exe",
        "/out:WIN::pipnav-audio-helper.exe",
        "/reference:WIN::NAudio.dll",
        "WIN::player.cs",
    ]


def test_start_player_cleans_stale_helpers_before_spawning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[object] = []
    proc = _make_process()

    def _cleanup(win_helper: str) -> None:
        calls.append(("cleanup", win_helper))

    def _spawn(args, **kwargs) -> MagicMock:
        calls.append(("popen", args))
        return proc

    monkeypatch.setattr(audio, "_cleanup_stale_helpers", _cleanup)
    monkeypatch.setattr(audio.subprocess, "Popen", _spawn)

    started = audio._start_player()

    assert started is proc
    assert calls[0] == ("cleanup", audio._win_audio_helper)
    assert calls[1][0] == "popen"
    assert calls[1][1][0] == str(audio.WIN_SOUNDS_DIR / audio.HELPER_EXE_NAME)
    assert (
        "boot=C:\\Users\\ewise\\.pipnav\\sounds\\UI_PipBoy_BootSequence_A.mp3"
        in calls[1][1]
    )


def test_start_player_falls_back_to_legacy_when_helper_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[object] = []
    proc = _make_process()

    monkeypatch.setattr(audio, "_win_audio_helper", "")
    monkeypatch.setattr(audio, "_build_helper_if_needed", lambda logger: "")
    monkeypatch.setattr(audio, "_cleanup_stale_players", lambda script: calls.append(("cleanup", script)))
    monkeypatch.setattr(audio, "get_logger", MagicMock())

    def _spawn(args, **kwargs) -> MagicMock:
        calls.append(("popen", args))
        return proc

    monkeypatch.setattr(audio.subprocess, "Popen", _spawn)

    started = audio._start_player()

    assert started is proc
    assert audio._audio_backend == "legacy"
    assert calls[0] == ("cleanup", audio._win_legacy_player_script)
    assert calls[1] == (
        "popen",
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            audio._win_legacy_player_script,
        ],
    )


def test_app_on_unmount_shuts_down_audio() -> None:
    app = PipNavApp()

    with patch("pipnav.main.shutdown_audio") as shutdown_audio:
        app.on_unmount()

    shutdown_audio.assert_called_once_with()
