"""Launch external tools — VS Code and Claude Code via WSL/Windows Terminal."""

import os
import re
import shlex
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from pipnav.core import agents, herdr
from pipnav.core.logging import get_logger


def _is_wsl() -> bool:
    """True when running under Windows Subsystem for Linux."""
    import platform
    return "microsoft" in platform.uname().release.lower()


def _tmux_name(path: Path) -> str:
    """A tmux-safe window/session name derived from the project folder."""
    return re.sub(r"[^A-Za-z0-9_-]", "-", path.name) or "pipnav"


def _launch_preflight(command: str) -> tuple[bool, "str | None", str]:
    """Validate environment and command availability. Returns (ok, wt_path, error)."""
    if _is_wsl():
        wt = shutil.which("wt.exe")
        if not wt:
            return False, None, "'wt.exe' not found \u2014 Windows Terminal required"
    else:
        wt = None
        if not shutil.which("tmux"):
            return False, None, "'tmux' not found \u2014 required to launch sessions on Linux"
    if not shutil.which(command):
        return False, None, f"'{command}' not found on PATH"
    return True, wt, ""


def _build_launch_argv(
    shell_cmd: str,
    path: Path,
    name: str,
    *,
    is_wsl: bool,
    in_tmux: bool,
    wt: "str | None" = None,
    shell: str = "bash",
) -> list[str]:
    """Build the argv that opens shell_cmd in a new session for the current environment.

    WSL            -> new Windows Terminal tab running the command under wsl.exe
    Linux + tmux   -> new tmux window in the current session
    Linux, no tmux -> new detached tmux session (attach with: tmux attach -t <name>)
    """
    if is_wsl:
        return [
            wt, "-w", "0", "new-tab",
            "wsl.exe", "--cd", str(path),
            "--", "bash", "-ic", shell_cmd,
        ]
    if in_tmux:
        return ["tmux", "new-window", "-c", str(path), "-n", name, shell, "-ic", shell_cmd]
    return ["tmux", "new-session", "-d", "-s", name, "-c", str(path), shell, "-ic", shell_cmd]


# Available choices for the custom launch builder
PERMISSION_MODES = ("default", "auto", "plan", "acceptEdits", "dontAsk", "bypassPermissions")
EFFORT_LEVELS = ("low", "medium", "high", "max")
MODEL_ALIASES = ("sonnet", "opus", "haiku")


@dataclass(frozen=True)
class LaunchOptions:
    """Full set of Claude Code launch options."""

    model: str = ""
    permission_mode: str = ""
    worktree: bool = False
    worktree_name: str = ""
    add_dirs: tuple[str, ...] = ()
    effort: str = ""
    allowed_tools: tuple[str, ...] = ()
    disallowed_tools: tuple[str, ...] = ()
    session_name: str = ""
    append_system_prompt: str = ""
    continue_session: bool = False

    def to_flags(self) -> tuple[str, ...]:
        """Convert options to CLI flags."""
        flags: list[str] = []
        if self.model:
            flags.extend(["--model", self.model])
        if self.permission_mode:
            flags.extend(["--permission-mode", self.permission_mode])
        if self.worktree:
            if self.worktree_name:
                flags.extend(["--worktree", self.worktree_name])
            else:
                flags.append("--worktree")
        for d in self.add_dirs:
            flags.extend(["--add-dir", d])
        if self.effort:
            flags.extend(["--effort", self.effort])
        if self.allowed_tools:
            flags.extend(["--allowedTools", ",".join(self.allowed_tools)])
        if self.disallowed_tools:
            flags.extend(["--disallowedTools", ",".join(self.disallowed_tools)])
        if self.session_name:
            flags.extend(["--name", self.session_name])
        if self.append_system_prompt:
            flags.extend(["--append-system-prompt", self.append_system_prompt])
        if self.continue_session:
            flags.append("--continue")
        return tuple(flags)


def launch_vscode(
    path: Path, command: str = "code", file_path: Path | None = None
) -> tuple[bool, str]:
    """Launch VS Code at path. Returns (success, error_message)."""
    logger = get_logger()

    if not shutil.which(command):
        return False, f"'{command}' not found on PATH"

    try:
        target = str(file_path) if file_path else str(path)
        subprocess.Popen(
            [command, target],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        logger.info("Launched VS Code: %s %s", command, target)
        return True, ""
    except OSError as exc:
        logger.error("Failed to launch VS Code: %s", exc)
        return False, str(exc)


def launch_agent(
    path: Path,
    harness: "agents.Harness",
    extra_flags: Sequence[str] = (),
    session_id: str | None = None,
) -> tuple[bool, str]:
    """Start or resume any supported coding tool in a project.

    herdr is the runtime when it is running: the tool opens in a herdr tab for
    this project. The terminal path is the fallback for when herdr is not
    running, never a retry after herdr refuses — that would launch twice.
    """
    logger = get_logger()

    if not shutil.which(harness.binary):
        return False, f"'{harness.binary}' not found on PATH"

    if session_id:
        argv = harness.resume_argv(session_id)
    else:
        argv = harness.launch_argv(tuple(extra_flags))

    if herdr.is_available():
        return herdr.open_agent(path, harness.herdr_kind, argv)

    ok, wt, err = _launch_preflight(harness.binary)
    if not ok:
        return False, err

    try:
        quoted = " ".join(shlex.quote(part) for part in argv)
        suffix = f" {quoted}" if quoted else ""
        shell_cmd = (
            f"cd {shlex.quote(str(path))} && "
            f"{shlex.quote(harness.binary)}{suffix}"
        )
        args = _build_launch_argv(
            shell_cmd, path, _tmux_name(path),
            is_wsl=_is_wsl(), in_tmux=bool(os.environ.get("TMUX")),
            wt=wt, shell=os.environ.get("SHELL") or "bash",
        )
        subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        logger.info("Launched %s in new tab: %s", harness.label, shell_cmd)
        return True, ""
    except OSError as exc:
        logger.error("Failed to launch %s: %s", harness.label, exc)
        return False, str(exc)


def _claude_flags(
    resume: bool,
    session_id: str | None,
    extra_flags: Sequence[str],
) -> list[str]:
    """The flags a Claude launch gets, shared by the herdr and terminal routes."""
    flags = list(extra_flags)
    has_permission_mode = "--permission-mode" in flags

    if session_id:
        flags.extend(["--resume", session_id])
    elif resume:
        flags.append("--resume")

    if not (resume and not session_id) and not has_permission_mode:
        flags.extend(["--permission-mode", "auto"])
    return flags


def launch_claude(
    path: Path,
    command: str = "claude",
    resume: bool = False,
    session_id: str | None = None,
    extra_flags: Sequence[str] = (),
) -> tuple[bool, str]:
    """Launch Claude Code.

    herdr is the runtime when it is running: the agent opens in a herdr pane for
    this project. The Windows Terminal / tmux path is the fallback for when herdr
    is not running — it is never used as a retry after herdr refuses, which would
    launch the same agent twice.
    """
    logger = get_logger()

    if not shutil.which(command):
        return False, f"'{command}' not found on PATH"

    flags = _claude_flags(resume, session_id, extra_flags)

    if herdr.is_available():
        return herdr.open_agent(path, "claude", tuple(flags))

    ok, wt, err = _launch_preflight(command)
    if not ok:
        return False, err

    try:
        quoted_path = shlex.quote(str(path))
        quoted_cmd = shlex.quote(command)

        quoted_flags = " ".join(shlex.quote(flag) for flag in flags)
        flags_suffix = f" {quoted_flags}" if quoted_flags else ""
        shell_cmd = f"cd {quoted_path} && {quoted_cmd}{flags_suffix}"

        args = _build_launch_argv(
            shell_cmd, path, _tmux_name(path),
            is_wsl=_is_wsl(), in_tmux=bool(os.environ.get("TMUX")),
            wt=wt, shell=os.environ.get("SHELL") or "bash",
        )
        subprocess.Popen(
            args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        logger.info("Launched Claude Code in new tab: %s", shell_cmd)
        return True, ""
    except OSError as exc:
        logger.error("Failed to launch Claude Code: %s", exc)
        return False, str(exc)


# Available spawn modes for remote control
REMOTE_SPAWN_MODES = ("same-dir", "worktree", "session")


def launch_remote_control(
    path: Path,
    command: str = "claude",
    spawn_mode: str = "same-dir",
    permission_mode: str = "auto",
    session_name: str = "",
    capacity: int | None = None,
    extra_flags: Sequence[str] = (),
) -> tuple[bool, str]:
    """Launch Claude remote-control server in a new session (WT tab on WSL, tmux window on Linux)."""
    logger = get_logger()

    ok, wt, err = _launch_preflight(command)
    if not ok:
        return False, err

    try:
        quoted_path = shlex.quote(str(path))
        quoted_cmd = shlex.quote(command)

        flags = ["remote-control"]
        user_flags = list(extra_flags)

        if "--spawn" not in user_flags:
            flags.extend(["--spawn", spawn_mode])
        if permission_mode and "--permission-mode" not in user_flags:
            flags.extend(["--permission-mode", permission_mode])
        if session_name and "--name" not in user_flags:
            flags.extend(["--name", session_name])
        if capacity is not None and "--capacity" not in user_flags:
            flags.extend(["--capacity", str(capacity)])
        flags.extend(user_flags)

        quoted_flags = " ".join(shlex.quote(f) for f in flags)
        shell_cmd = f"cd {quoted_path} && {quoted_cmd} {quoted_flags}"

        args = _build_launch_argv(
            shell_cmd, path, _tmux_name(path),
            is_wsl=_is_wsl(), in_tmux=bool(os.environ.get("TMUX")),
            wt=wt, shell=os.environ.get("SHELL") or "bash",
        )
        subprocess.Popen(
            args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        logger.info("Launched remote control in new tab: %s", shell_cmd)
        return True, ""
    except OSError as exc:
        logger.error("Failed to launch remote control: %s", exc)
        return False, str(exc)
