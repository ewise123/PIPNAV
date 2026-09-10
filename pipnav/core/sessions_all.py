"""One resumable-session list across every coding tool PipNav supports.

Each tool stores its history somewhere different and spells resume differently.
This flattens all of that into one type, newest first, so the caller never has
to know which tool a session came from — only that it can be reopened.

A reader that fails is skipped rather than fatal: if Codex's store is
unreadable, you should still see your Claude and OpenCode sessions.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from pipnav.core import agents, claude_sessions, codex_sessions, opencode_sessions
from pipnav.core.logging import get_logger


@dataclass(frozen=True)
class AgentSession:
    """A session you can pick back up, whichever tool made it."""

    harness: str  # "claude" | "codex" | "opencode"
    session_id: str
    project_path: str
    title: str
    last_active: datetime
    cost: float = 0.0

    @property
    def label(self) -> str:
        """The tool's human-facing name."""
        harness = agents.get(self.harness)
        return harness.label if harness else self.harness

    def resume_argv(self) -> tuple[str, ...]:
        """The args that reopen this session in its own tool."""
        harness = agents.get(self.harness)
        if harness is None:
            raise ValueError(f"unknown tool: {self.harness}")
        return harness.resume_argv(self.session_id)


def _from_claude(session: claude_sessions.ClaudeSession) -> AgentSession:
    return AgentSession(
        harness="claude",
        session_id=session.session_id,
        project_path=session.project_path,
        title=session.session_name or session.first_message,
        last_active=session.last_activity,
    )


def _from_codex(session: codex_sessions.CodexSession) -> AgentSession:
    return AgentSession(
        harness="codex",
        session_id=session.session_id,
        project_path=session.project_path,
        title=session.title,
        last_active=session.last_active,
    )


def _from_opencode(session: opencode_sessions.OpenCodeSession) -> AgentSession:
    return AgentSession(
        harness="opencode",
        session_id=session.session_id,
        project_path=session.project_path,
        title=session.title,
        last_active=session.last_active,
        cost=session.cost,
    )


# Each entry: the module to ask, and how to convert what it returns.
_SOURCES = (
    (claude_sessions, _from_claude),
    (codex_sessions, _from_codex),
    (opencode_sessions, _from_opencode),
)


def sessions_for_project(project_path: Path) -> tuple[AgentSession, ...]:
    """Every resumable session for this project, across all tools, newest first."""
    logger = get_logger()
    merged: list[AgentSession] = []

    for module, convert in _SOURCES:
        try:
            found = module.discover_sessions_for_project(project_path)
        except Exception as exc:
            # One tool's store being unreadable must not hide the others.
            logger.debug(
                "Session discovery failed for %s: %s", module.__name__, exc
            )
            continue
        merged.extend(convert(session) for session in found)

    merged.sort(key=lambda s: s.last_active, reverse=True)
    return tuple(merged)


def latest_for_project(project_path: Path) -> AgentSession | None:
    """The most recent session for this project in any tool, or None."""
    sessions = sessions_for_project(project_path)
    return sessions[0] if sessions else None
