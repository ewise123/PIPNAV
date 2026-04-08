"""Launch external tools — VS Code and Claude Code via WSL/Windows Terminal."""

import shlex
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from pipnav.core.logging import get_logger


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


def launch_claude(
    path: Path,
    command: str = "claude",
    resume: bool = False,
    session_id: str | None = None,
    extra_flags: Sequence[str] = (),
) -> tuple[bool, str]:
    """Launch Claude Code in a new Windows Terminal tab. Returns (success, error_message)."""
    logger = get_logger()

    wt = shutil.which("wt.exe")
    if not wt:
        return False, "'wt.exe' not found — Windows Terminal required"

    if not shutil.which(command):
        return False, f"'{command}' not found on PATH"

    try:
        quoted_path = shlex.quote(str(path))
        quoted_cmd = shlex.quote(command)
        flags = list(extra_flags)
        has_permission_mode = "--permission-mode" in flags

        if session_id:
            flags.extend(["--resume", session_id])
            if not has_permission_mode:
                flags.extend(["--permission-mode", "auto"])
        elif resume:
            flags.append("--resume")
        else:
            if not has_permission_mode:
                flags.extend(["--permission-mode", "auto"])

        quoted_flags = " ".join(shlex.quote(flag) for flag in flags)
        flags_suffix = f" {quoted_flags}" if quoted_flags else ""
        shell_cmd = f"cd {quoted_path} && {quoted_cmd}{flags_suffix}"

        args = [
            wt, "-w", "0", "new-tab",
            "wsl.exe", "--cd", str(path),
            "--", "bash", "-ic", shell_cmd,
        ]
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
) -> tuple[bool, str]:
    """Launch Claude remote-control server in a new Windows Terminal tab."""
    logger = get_logger()

    wt = shutil.which("wt.exe")
    if not wt:
        return False, "'wt.exe' not found — Windows Terminal required"

    if not shutil.which(command):
        return False, f"'{command}' not found on PATH"

    try:
        quoted_path = shlex.quote(str(path))
        quoted_cmd = shlex.quote(command)

        flags = ["remote-control", "--spawn", spawn_mode]
        if permission_mode:
            flags.extend(["--permission-mode", permission_mode])
        if session_name:
            flags.extend(["--name", session_name])
        if capacity is not None:
            flags.extend(["--capacity", str(capacity)])

        quoted_flags = " ".join(shlex.quote(f) for f in flags)
        shell_cmd = f"cd {quoted_path} && {quoted_cmd} {quoted_flags}"

        args = [
            wt, "-w", "0", "new-tab",
            "wsl.exe", "--cd", str(path),
            "--", "bash", "-ic", shell_cmd,
        ]
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
