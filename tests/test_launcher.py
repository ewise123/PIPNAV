"""Tests for launcher."""

from pathlib import Path
from unittest.mock import patch

from pipnav.core.launcher import (
    LaunchOptions,
    launch_claude,
    launch_remote_control,
    launch_vscode,
)


def test_launch_vscode_missing_command() -> None:
    ok, err = launch_vscode(Path("/tmp"), command="nonexistent-editor-xyz")
    assert ok is False
    assert "not found" in err


def test_launch_claude_missing_wt() -> None:
    with patch("pipnav.core.launcher._is_wsl", return_value=True), \
         patch("pipnav.core.launcher.shutil.which", return_value=None):
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

    with patch("pipnav.core.launcher._is_wsl", return_value=True), \
         patch("pipnav.core.launcher.shutil.which", side_effect=_which):
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


@patch("pipnav.core.launcher.subprocess.Popen")
def test_launch_claude_forwards_extra_flags(mock_popen) -> None:
    def _which(cmd: str) -> str | None:
        return "/usr/bin/" + cmd.replace(".exe", "")

    with patch("pipnav.core.launcher.shutil.which", side_effect=_which):
        ok, err = launch_claude(
            Path("/tmp/proj"),
            extra_flags=("--model", "opus", "--permission-mode", "plan"),
        )

    assert ok is True
    assert err == ""

    shell_cmd = mock_popen.call_args[0][0][-1]
    assert "--model opus" in shell_cmd
    assert "--permission-mode plan" in shell_cmd
    assert "--permission-mode auto" not in shell_cmd


@patch("pipnav.core.launcher.subprocess.Popen")
def test_launch_remote_control(mock_popen) -> None:
    def _which(cmd: str) -> str | None:
        return "/usr/bin/" + cmd.replace(".exe", "")

    with patch("pipnav.core.launcher.shutil.which", side_effect=_which):
        ok, err = launch_remote_control(
            Path("/tmp/proj"),
            spawn_mode="worktree",
            permission_mode="plan",
            session_name="my-project",
        )

    assert ok is True
    assert err == ""

    shell_cmd = mock_popen.call_args[0][0][-1]
    assert "remote-control" in shell_cmd
    assert "--spawn worktree" in shell_cmd
    assert "--permission-mode plan" in shell_cmd
    assert "--name my-project" in shell_cmd


@patch("pipnav.core.launcher.subprocess.Popen")
def test_launch_remote_control_defaults(mock_popen) -> None:
    def _which(cmd: str) -> str | None:
        return "/usr/bin/" + cmd.replace(".exe", "")

    with patch("pipnav.core.launcher.shutil.which", side_effect=_which):
        ok, err = launch_remote_control(Path("/tmp/proj"))

    assert ok is True
    shell_cmd = mock_popen.call_args[0][0][-1]
    assert "--spawn same-dir" in shell_cmd
    assert "--permission-mode auto" in shell_cmd


@patch("pipnav.core.launcher.subprocess.Popen")
def test_launch_remote_control_forwards_extra_flags(mock_popen) -> None:
    def _which(cmd: str) -> str | None:
        return "/usr/bin/" + cmd.replace(".exe", "")

    with patch("pipnav.core.launcher.shutil.which", side_effect=_which):
        ok, err = launch_remote_control(
            Path("/tmp/proj"),
            session_name="default-name",
            permission_mode="plan",
            extra_flags=("--spawn", "worktree", "--name", "custom-name", "--capacity", "8"),
        )

    assert ok is True
    assert err == ""

    shell_cmd = mock_popen.call_args[0][0][-1]
    assert "--spawn worktree" in shell_cmd
    assert "--name custom-name" in shell_cmd
    assert "--capacity 8" in shell_cmd
    assert "--permission-mode plan" in shell_cmd
    assert "--spawn same-dir" not in shell_cmd
    assert "--name default-name" not in shell_cmd


def test_launch_remote_control_missing_wt() -> None:
    with patch("pipnav.core.launcher._is_wsl", return_value=True), \
         patch("pipnav.core.launcher.shutil.which", return_value=None):
        ok, err = launch_remote_control(Path("/tmp"))
    assert ok is False
    assert "wt.exe" in err


class TestLaunchOptions:
    def test_empty_options_produce_no_flags(self) -> None:
        opts = LaunchOptions()
        assert opts.to_flags() == ()

    def test_model_flag(self) -> None:
        opts = LaunchOptions(model="opus")
        assert opts.to_flags() == ("--model", "opus")

    def test_permission_mode_flag(self) -> None:
        opts = LaunchOptions(permission_mode="plan")
        assert opts.to_flags() == ("--permission-mode", "plan")

    def test_worktree_flag(self) -> None:
        opts = LaunchOptions(worktree=True)
        assert opts.to_flags() == ("--worktree",)

    def test_worktree_with_name(self) -> None:
        opts = LaunchOptions(worktree=True, worktree_name="feat-x")
        assert opts.to_flags() == ("--worktree", "feat-x")

    def test_add_dirs(self) -> None:
        opts = LaunchOptions(add_dirs=("~/docs", "~/lib"))
        flags = opts.to_flags()
        assert ("--add-dir", "~/docs", "--add-dir", "~/lib") == flags

    def test_effort_flag(self) -> None:
        opts = LaunchOptions(effort="max")
        assert opts.to_flags() == ("--effort", "max")

    def test_allowed_tools(self) -> None:
        opts = LaunchOptions(allowed_tools=("Bash", "Edit"))
        assert opts.to_flags() == ("--allowedTools", "Bash,Edit")

    def test_disallowed_tools(self) -> None:
        opts = LaunchOptions(disallowed_tools=("Write",))
        assert opts.to_flags() == ("--disallowedTools", "Write")

    def test_session_name(self) -> None:
        opts = LaunchOptions(session_name="my-review")
        assert opts.to_flags() == ("--name", "my-review")

    def test_continue_flag(self) -> None:
        opts = LaunchOptions(continue_session=True)
        assert opts.to_flags() == ("--continue",)

    def test_combined_options(self) -> None:
        opts = LaunchOptions(
            model="sonnet",
            permission_mode="auto",
            effort="high",
            session_name="sprint",
        )
        flags = opts.to_flags()
        assert "--model" in flags
        assert "--permission-mode" in flags
        assert "--effort" in flags
        assert "--name" in flags

    def test_frozen(self) -> None:
        import pytest

        opts = LaunchOptions()
        with pytest.raises(AttributeError):
            opts.model = "changed"  # type: ignore[misc]


# --- Native Linux (tmux) launch path -------------------------------------------------

from pipnav.core import launcher as _ln


def test_build_launch_argv_wsl_uses_windows_terminal() -> None:
    argv = _ln._build_launch_argv(
        "cd /p && claude", Path("/p"), "proj",
        is_wsl=True, in_tmux=False, wt="/usr/bin/wt.exe", shell="/bin/bash",
    )
    assert argv[0] == "/usr/bin/wt.exe"
    assert "new-tab" in argv
    assert argv[-1] == "cd /p && claude"


def test_build_launch_argv_linux_in_tmux_opens_new_window() -> None:
    argv = _ln._build_launch_argv(
        "cd /p && claude", Path("/p"), "proj",
        is_wsl=False, in_tmux=True, shell="/usr/bin/zsh",
    )
    assert argv[:2] == ["tmux", "new-window"]
    assert "-n" in argv and "proj" in argv
    assert "-c" in argv and "/p" in argv
    assert "new-session" not in argv
    assert argv[-1] == "cd /p && claude"


def test_build_launch_argv_linux_no_tmux_creates_detached_session() -> None:
    argv = _ln._build_launch_argv(
        "cd /p && claude", Path("/p"), "proj",
        is_wsl=False, in_tmux=False, shell="/usr/bin/zsh",
    )
    assert argv[:2] == ["tmux", "new-session"]
    assert "-d" in argv and "-s" in argv
    assert argv[-1] == "cd /p && claude"


def test_tmux_name_sanitizes_unsafe_chars() -> None:
    assert _ln._tmux_name(Path("/home/x/my.proj:v2")) == "my-proj-v2"


@patch("pipnav.core.launcher.subprocess.Popen")
def test_launch_claude_linux_uses_tmux(mock_popen) -> None:
    def _which(cmd: str) -> str | None:
        return "/usr/bin/" + cmd.replace(".exe", "")
    with patch("pipnav.core.launcher._is_wsl", return_value=False), \
         patch("pipnav.core.launcher.shutil.which", side_effect=_which), \
         patch.dict("os.environ", {"TMUX": "/tmp/tmux-1000/default,1,0"}, clear=False):
        ok, err = launch_claude(Path("/tmp/proj"))
    assert ok is True and err == ""
    argv = mock_popen.call_args[0][0]
    assert argv[:2] == ["tmux", "new-window"]
    assert argv[-1].startswith("cd ") and "claude" in argv[-1]


@patch("pipnav.core.launcher.subprocess.Popen")
def test_launch_claude_linux_missing_tmux(mock_popen) -> None:
    def _which(cmd: str) -> str | None:
        return None if cmd == "tmux" else "/usr/bin/" + cmd
    with patch("pipnav.core.launcher._is_wsl", return_value=False), \
         patch("pipnav.core.launcher.shutil.which", side_effect=_which):
        ok, err = launch_claude(Path("/tmp/proj"))
    assert ok is False
    assert "tmux" in err
    mock_popen.assert_not_called()


@patch("pipnav.core.launcher.subprocess.Popen")
def test_launch_remote_control_linux_uses_tmux(mock_popen) -> None:
    def _which(cmd: str) -> str | None:
        return "/usr/bin/" + cmd.replace(".exe", "")
    with patch("pipnav.core.launcher._is_wsl", return_value=False), \
         patch("pipnav.core.launcher.shutil.which", side_effect=_which), \
         patch.dict("os.environ", {"TMUX": "/tmp/tmux-1000/default,1,0"}, clear=False):
        ok, err = launch_remote_control(Path("/tmp/proj"), session_name="rc")
    assert ok is True and err == ""
    argv = mock_popen.call_args[0][0]
    assert argv[:2] == ["tmux", "new-window"]
    assert "remote-control" in argv[-1]
