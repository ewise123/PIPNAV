"""Tests for launcher."""

from pathlib import Path
from unittest.mock import patch

from pipnav.core.launcher import launch_claude, launch_vscode


def test_launch_vscode_missing_command() -> None:
    ok, err = launch_vscode(Path("/tmp"), command="nonexistent-editor-xyz")
    assert ok is False
    assert "not found" in err


def test_launch_claude_missing_wt() -> None:
    with patch("pipnav.core.launcher.shutil.which", return_value=None):
        ok, err = launch_claude(Path("/tmp"))
    assert ok is False
    assert "wt.exe" in err


@patch("pipnav.core.launcher.shutil.which", return_value="/usr/bin/code")
@patch("pipnav.core.launcher.subprocess.Popen")
def test_launch_vscode_success(mock_popen, mock_which) -> None:
    ok, err = launch_vscode(Path("/tmp/proj"))
    assert ok is True
    assert err == ""
    mock_popen.assert_called_once()


@patch("pipnav.core.launcher.subprocess.Popen")
def test_launch_claude_new_tab(mock_popen) -> None:
    def _which(cmd: str) -> str | None:
        return "/usr/bin/" + cmd.replace(".exe", "")

    with patch("pipnav.core.launcher.shutil.which", side_effect=_which):
        ok, err = launch_claude(Path("/tmp/proj"))
    assert ok is True
    assert err == ""
    mock_popen.assert_called_once()
    call_args = mock_popen.call_args[0][0]
    assert "new-tab" in call_args


@patch("pipnav.core.launcher.subprocess.Popen")
def test_launch_claude_resume(mock_popen) -> None:
    def _which(cmd: str) -> str | None:
        return "/usr/bin/" + cmd.replace(".exe", "")

    with patch("pipnav.core.launcher.shutil.which", side_effect=_which):
        ok, err = launch_claude(Path("/tmp/proj"), resume=True)
    assert ok is True
    call_args = mock_popen.call_args[0][0]
    assert "--resume" in " ".join(call_args)
