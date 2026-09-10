"""The coding harnesses PipNav can launch.

One entry per tool. Adding a fourth is a data change, not a code change.

Flags are deliberately literal per tool rather than abstracted behind a shared
"permission mode" idea — the three tools spell approvals differently enough that
any common vocabulary would be a lie.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Harness:
    """A coding agent PipNav knows how to start."""

    key: str  # short id, and the agent kind herdr recognises
    label: str  # human-facing name
    binary: str  # what to look for on PATH
    launch_flags: tuple[str, ...] = ()  # applied unless the caller overrides
    resume_flags: tuple[str, ...] = ()  # "{session}" is substituted
    keybinding: str = ""  # the PipNav key that launches it

    @property
    def herdr_kind(self) -> str:
        """The `kind` herdr's agent.start expects. Same string as our key."""
        return self.key

    def available(self) -> bool:
        """True when this tool is installed."""
        return shutil.which(self.binary) is not None

    def launch_argv(self, extra_flags: "tuple[str, ...]" = ()) -> tuple[str, ...]:
        """Flags for a fresh session. The binary itself is not included —
        herdr's agent.start takes the kind and the args separately."""
        extra = tuple(extra_flags)
        # Anything the caller names wins, so asking for plan mode does not also
        # get the auto default.
        keep: list[str] = []
        skip_value = False
        for item in self.launch_flags:
            if skip_value:
                skip_value = False
                continue
            if item.startswith("-") and item in extra:
                # Drop this default, and its value if it takes one.
                skip_value = True
                continue
            keep.append(item)
        return tuple(keep) + extra

    def resume_argv(self, session_id: str) -> tuple[str, ...]:
        """Args that reopen an existing session.

        Launch defaults are deliberately not applied: the session already has
        its own settings, and re-asserting a permission mode would change them.
        """
        if not session_id:
            raise ValueError(f"{self.label}: cannot resume without a session id")
        if not self.resume_flags:
            raise ValueError(f"{self.label}: resume is not supported")
        return tuple(
            part.replace("{session}", session_id) for part in self.resume_flags
        )


# Verified against these tools on 2026-09-10. herdr recognises all three keys
# as agent kinds.
#
# Only Claude carries a permission default, and only because that is PipNav's
# existing behaviour. Codex's --dangerously-bypass-approvals-and-sandbox and
# OpenCode's --auto are both flagged as dangerous by their own help text, so
# PipNav does not opt anyone into them; those tools start with their own
# defaults and the user can pass flags explicitly.
HARNESSES: tuple[Harness, ...] = (
    Harness(
        key="claude",
        label="Claude Code",
        binary="claude",
        launch_flags=("--permission-mode", "auto"),
        resume_flags=("--resume", "{session}"),
        keybinding="c",
    ),
    Harness(
        key="codex",
        label="Codex",
        binary="codex",
        resume_flags=("resume", "{session}"),  # a subcommand, not a flag
        keybinding="x",
    ),
    Harness(
        key="opencode",
        label="OpenCode",
        binary="opencode",
        resume_flags=("-s", "{session}"),
        keybinding="o",
    ),
)


def get(key: str) -> Harness | None:
    """The harness with this key, or None."""
    for harness in HARNESSES:
        if harness.key == key:
            return harness
    return None


def installed() -> tuple[Harness, ...]:
    """Only the harnesses actually present on this machine."""
    return tuple(harness for harness in HARNESSES if harness.available())
