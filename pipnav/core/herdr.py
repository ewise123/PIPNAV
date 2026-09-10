"""Talk to a running herdr server over its unix socket.

herdr owns the agent terminals; PipNav asks it questions. The server hangs up
after every response, so there is no long-lived client to keep alive — each call
opens its own connection. Event subscriptions (phase 5) are the exception and
will need their own reader thread.

Nothing here raises at PipNav: `is_available` and `list_agents` degrade to a
False/empty answer so PipNav stays usable when herdr is not running.
"""

from __future__ import annotations

import json
import os
import re
import socket
import uuid
from dataclasses import dataclass
from pathlib import Path

from pipnav.core.logging import get_logger

CONFIG_DIR = Path.home() / ".config" / "herdr"

# herdr is local; a slow answer means something is wrong, not that we should wait.
DEFAULT_TIMEOUT = 2.0

# herdr's own AgentStatus enum (protocol 22). Anything else is treated as unknown
# so a newer herdr adding a state cannot corrupt the fleet view.
AGENT_STATUSES = ("idle", "working", "blocked", "done", "unknown")

# The one status that means a human is needed.
NEEDS_YOU = "blocked"


class HerdrError(RuntimeError):
    """herdr is unreachable, or answered with an error."""


@dataclass(frozen=True)
class HerdrAgent:
    """A coding agent herdr is currently watching."""

    pane_id: str
    tab_id: str
    workspace_id: str
    harness: str  # "claude" | "codex" | "opencode" | ... ("" if herdr can't tell)
    label: str  # human-facing name, e.g. "Claude Code"
    status: str  # one of AGENT_STATUSES
    cwd: Path | None
    title: str
    session_ref: str  # value to resume with, "" when herdr has not seen one
    session_kind: str  # "id" | "path" | ""
    focused: bool

    @property
    def needs_you(self) -> bool:
        return self.status == NEEDS_YOU


def socket_path() -> Path:
    """Resolve the API socket the way herdr's own client does."""
    explicit = os.environ.get("HERDR_SOCKET_PATH")
    if explicit:
        return Path(explicit)
    session = os.environ.get("HERDR_SESSION")
    if session:
        return CONFIG_DIR / "sessions" / session / "herdr.sock"
    return CONFIG_DIR / "herdr.sock"


def _read_line(sock: socket.socket) -> bytes:
    """Read one newline-terminated response, however it arrives on the wire."""
    chunks: list[bytes] = []
    while True:
        chunk = sock.recv(65536)
        if not chunk:
            break  # server hung up
        chunks.append(chunk)
        if chunk.endswith(b"\n"):
            break
    return b"".join(chunks)


def call(method: str, params: dict | None = None, timeout: float = DEFAULT_TIMEOUT) -> dict:
    """Send one request and return its result payload. Raises HerdrError."""
    request = {
        "id": uuid.uuid4().hex[:12],
        "method": method,
        # params is required by herdr's schema even when empty.
        "params": params or {},
    }
    payload = (json.dumps(request) + "\n").encode("utf-8")

    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            sock.connect(str(socket_path()))
            sock.sendall(payload)
            raw = _read_line(sock)
    except OSError as exc:
        raise HerdrError(f"herdr unreachable ({method}): {exc}") from exc

    if not raw.strip():
        raise HerdrError(f"herdr closed the connection without answering {method}")

    try:
        message = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HerdrError(f"unreadable answer to {method}: {exc}") from exc

    if not isinstance(message, dict):
        raise HerdrError(f"unexpected answer to {method}")

    error = message.get("error")
    if isinstance(error, dict):
        raise HerdrError(
            f"{error.get('code', 'error')}: {error.get('message', 'herdr refused')}"
        )

    result = message.get("result")
    if not isinstance(result, dict):
        raise HerdrError(f"no result in answer to {method}")
    return result


def is_available(timeout: float = DEFAULT_TIMEOUT) -> bool:
    """True when a herdr server is running and speaking a protocol we understand."""
    try:
        return call("ping", timeout=timeout).get("type") == "pong"
    except HerdrError:
        return False


def server_version(timeout: float = DEFAULT_TIMEOUT) -> str:
    """The running server's version, or "" when herdr is not up."""
    try:
        return str(call("ping", timeout=timeout).get("version") or "")
    except HerdrError:
        return ""


def _agent_from_info(info: dict) -> HerdrAgent | None:
    """Map one herdr AgentInfo record. Returns None if it is not usable."""
    pane_id = info.get("pane_id")
    if not isinstance(pane_id, str) or not pane_id:
        return None

    status = info.get("agent_status")
    if status not in AGENT_STATUSES:
        status = "unknown"

    harness = info.get("agent") or ""
    cwd = info.get("cwd") or info.get("foreground_cwd")

    session = info.get("agent_session")
    if not isinstance(session, dict):
        session = {}

    return HerdrAgent(
        pane_id=pane_id,
        tab_id=info.get("tab_id") or "",
        workspace_id=info.get("workspace_id") or "",
        harness=harness,
        label=info.get("display_agent") or harness,
        status=status,
        cwd=Path(cwd) if cwd else None,
        # ponytail: activity text is only as good as what the agent writes to its
        # terminal title; a plain shell pane reported as an agent shows its prompt.
        # Verify against a real Claude/Codex pane in phase 1 before adding cleverness.
        title=info.get("title") or info.get("terminal_title_stripped") or "",
        session_ref=str(session.get("value") or ""),
        session_kind=str(session.get("kind") or ""),
        focused=bool(info.get("focused")),
    )


def list_agents(timeout: float = DEFAULT_TIMEOUT) -> tuple[HerdrAgent, ...]:
    """Every agent herdr is watching. Empty when herdr is not running."""
    logger = get_logger()
    try:
        result = call("agent.list", timeout=timeout)
    except HerdrError as exc:
        logger.debug("herdr agent.list failed: %s", exc)
        return ()

    raw = result.get("agents")
    if not isinstance(raw, list):
        logger.debug("herdr returned a non-list agent payload")
        return ()

    agents = [
        agent
        for entry in raw
        if isinstance(entry, dict) and (agent := _agent_from_info(entry)) is not None
    ]
    # Whoever needs you comes first; herdr's own order otherwise.
    agents.sort(key=lambda a: 0 if a.needs_you else 1)
    return tuple(agents)


def focus_agent(pane_id: str, timeout: float = DEFAULT_TIMEOUT) -> bool:
    """Bring an agent's pane to the front in herdr. False when it didn't work."""
    try:
        # agent.* methods address by "target" (pane id or agent name). Only
        # agent.start takes a "pane_id" — do not copy that shape here.
        call("agent.focus", {"target": pane_id}, timeout=timeout)
        return True
    except HerdrError as exc:
        get_logger().debug("herdr agent.focus failed: %s", exc)
        return False


# --- launching -------------------------------------------------------------
#
# Placement rules, decided 2026-09-10:
#   one workspace per project, labelled with the project folder name;
#   a second agent in that project gets its own TAB, not a split.

# agent.start waits for the agent to come up, so it needs more room than a query.
LAUNCH_TIMEOUT = 45.0


def find_workspace(label: str, timeout: float = DEFAULT_TIMEOUT) -> str | None:
    """The id of the workspace with this label, or None."""
    try:
        result = call("workspace.list", timeout=timeout)
    except HerdrError as exc:
        get_logger().debug("herdr workspace.list failed: %s", exc)
        return None

    workspaces = result.get("workspaces")
    if not isinstance(workspaces, list):
        return None
    for workspace in workspaces:
        if isinstance(workspace, dict) and workspace.get("label") == label:
            workspace_id = workspace.get("workspace_id")
            if isinstance(workspace_id, str) and workspace_id:
                return workspace_id
    return None


def _root_pane_id(result: dict) -> str:
    """The pane a workspace.create or tab.create just handed us."""
    root = result.get("root_pane")
    if isinstance(root, dict):
        pane_id = root.get("pane_id")
        if isinstance(pane_id, str) and pane_id:
            return pane_id
    return ""


# herdr enforces this on agent names: lowercase, digits, - and _, 1-32 chars,
# must start with a letter. Anything else is rejected as invalid_agent_name.
AGENT_NAME_MAX = 32
_NAME_STRIP = re.compile(r"[^a-z0-9_-]+")


def agent_name(kind: str, label: str, pane_id: str = "") -> str:
    """A herdr-legal agent name identifying which project this agent serves.

    `pane_id` qualifies the name when the plain one is already taken — two
    agents of the same kind in the same project.
    """
    def slug(text: str) -> str:
        return _NAME_STRIP.sub("-", text.lower()).strip("-")

    kind_slug = slug(kind) or "agent"
    if not kind_slug[0].isalpha():
        kind_slug = f"a{kind_slug}"

    suffix = slug(pane_id)
    # The uniquifier must survive truncation, so reserve its room up front.
    budget = AGENT_NAME_MAX - (len(suffix) + 1 if suffix else 0)
    name = f"{kind_slug}-{slug(label)}".strip("-")[:budget].strip("-")
    return f"{name}-{suffix}" if suffix else name


def _start_agent(pane_id: str, kind: str, name: str, args, timeout: float) -> dict:
    """agent.start, addressed by pane_id — every other agent.* uses target."""
    return call(
        "agent.start",
        {"pane_id": pane_id, "kind": kind, "name": name, "args": list(args)},
        timeout=timeout,
    )


def open_agent(
    project_path: Path,
    kind: str,
    args: "tuple[str, ...]" = (),
    timeout: float = LAUNCH_TIMEOUT,
) -> tuple[bool, str]:
    """Start `kind` in a herdr pane for this project.

    Returns (ok, error). Never raises — the caller falls back to its own
    launcher when this reports False.
    """
    logger = get_logger()
    label = project_path.name
    cwd = str(project_path)

    created_workspace_id = ""
    created_tab_id = ""

    try:
        workspace_id = find_workspace(label)
        if workspace_id:
            # Project already open: give this agent its own tab.
            placed = call(
                "tab.create",
                {"workspace_id": workspace_id, "cwd": cwd, "label": kind, "focus": True},
            )
            created_tab_id = (placed.get("tab") or {}).get("tab_id") or ""
        else:
            placed = call(
                "workspace.create", {"label": label, "cwd": cwd, "focus": True}
            )
            created_workspace_id = (
                (placed.get("workspace") or {}).get("workspace_id") or ""
            )

        pane_id = _root_pane_id(placed)
        if not pane_id:
            _undo_placement(created_workspace_id, created_tab_id)
            return False, "herdr gave no pane to start the agent in"

        # herdr requires agent names to be unique across the whole session, so
        # the name carries the project; the pane-qualified retry covers two
        # agents of the same kind in one project.
        try:
            started = _start_agent(
                pane_id, kind, agent_name(kind, label), args, timeout
            )
        except HerdrError as exc:
            if "agent_name_taken" not in str(exc):
                raise
            started = _start_agent(
                pane_id, kind, agent_name(kind, label, pane_id), args, timeout
            )
    except HerdrError as exc:
        logger.warning("herdr launch of %s in %s failed: %s", kind, cwd, exc)
        _undo_placement(created_workspace_id, created_tab_id)
        return False, str(exc)

    logger.info("herdr started %s: %s", kind, started.get("argv"))
    return True, ""


def _undo_placement(workspace_id: str, tab_id: str) -> None:
    """Remove the pane we made for an agent that never started.

    Close only what we created: the tab when the project was already open, the
    whole workspace when we opened it. Otherwise a failed launch leaves an empty
    workspace sitting in the user's herdr window.
    """
    try:
        if workspace_id:
            call("workspace.close", {"workspace_id": workspace_id})
        elif tab_id:
            call("tab.close", {"tab_id": tab_id})
    except HerdrError as exc:
        get_logger().debug("herdr cleanup after failed launch: %s", exc)
