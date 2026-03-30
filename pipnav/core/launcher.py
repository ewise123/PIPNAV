"""Launch external tools — VS Code and Claude Code via WSL/Windows Terminal."""

import shlex
import shutil
import subprocess
from pathlib import Path

from pipnav.core.logging import get_logger


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

        if session_id:
            quoted_sid = shlex.quote(session_id)
            shell_cmd = (
                f"cd {quoted_path} && {quoted_cmd}"
                f" --resume {quoted_sid} --permission-mode auto"
            )
        elif resume:
            shell_cmd = f"cd {quoted_path} && {quoted_cmd} --resume"
        else:
            shell_cmd = (
                f"cd {quoted_path} && {quoted_cmd} --permission-mode auto"
            )

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
