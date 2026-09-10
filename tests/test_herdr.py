"""Tests for the herdr socket client.

herdr is an outside program writing data we parse, so this is a trust boundary:
every failure mode gets a test. The real server closes the connection after each
response, so the fake server here does the same.
"""

import json
import socket
import threading
from pathlib import Path

import pytest

from pipnav.core import herdr


# --- fake server -------------------------------------------------------------


class FakeHerdr:
    """A one-shot-per-connection unix socket server, like the real thing."""

    def __init__(self, path: Path, responses):
        """responses: list of raw bytes to write, one per connection."""
        self.path = path
        self.responses = list(responses)
        self.requests: list[str] = []
        self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._sock.bind(str(path))
        self._sock.listen(8)
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def _serve(self):
        while True:
            try:
                conn, _ = self._sock.accept()
            except OSError:
                return
            try:
                data = b""
                while not data.endswith(b"\n"):
                    chunk = conn.recv(4096)
                    if not chunk:
                        break
                    data += chunk
                self.requests.append(data.decode("utf-8").strip())
                if self.responses:
                    conn.sendall(self.responses.pop(0))
            except OSError:
                pass
            finally:
                conn.close()  # the real server hangs up after every response

    def close(self):
        self._sock.close()


def _ok(result: dict) -> bytes:
    return (json.dumps({"id": "x", "result": result}) + "\n").encode()


def _err(code: str, message: str) -> bytes:
    return (
        json.dumps({"id": "x", "error": {"code": code, "message": message}}) + "\n"
    ).encode()


@pytest.fixture
def fake(tmp_path, monkeypatch):
    """Point the client at a fake server. Yields a factory."""
    made: list[FakeHerdr] = []

    def make(*responses):
        # Short path: unix sockets die past ~108 bytes and tmp_path is long.
        sock_path = Path("/tmp") / f"pipnav-t{len(made)}-{id(made)}.sock"
        sock_path.unlink(missing_ok=True)
        server = FakeHerdr(sock_path, responses)
        made.append(server)
        monkeypatch.setenv("HERDR_SOCKET_PATH", str(sock_path))
        return server

    yield make
    for server in made:
        server.close()
        server.path.unlink(missing_ok=True)


AGENT_INFO = {
    "pane_id": "w1:p2",
    "tab_id": "w1:t1",
    "workspace_id": "w1",
    "agent": "claude",
    "display_agent": "Claude Code",
    "agent_status": "blocked",
    "cwd": "/home/ewise/projects/PIPNAV",
    "title": "approve migration?",
    "focused": False,
    "agent_session": {
        "source": "screen",
        "agent": "claude",
        "kind": "id",
        "value": "abc-123",
    },
}


# --- socket_path -------------------------------------------------------------


def test_socket_path_prefers_explicit_env(monkeypatch):
    monkeypatch.setenv("HERDR_SOCKET_PATH", "/run/custom.sock")
    monkeypatch.setenv("HERDR_SESSION", "work")
    assert herdr.socket_path() == Path("/run/custom.sock")


def test_socket_path_uses_named_session(monkeypatch):
    monkeypatch.delenv("HERDR_SOCKET_PATH", raising=False)
    monkeypatch.setenv("HERDR_SESSION", "work")
    assert herdr.socket_path() == (
        Path.home() / ".config" / "herdr" / "sessions" / "work" / "herdr.sock"
    )


def test_socket_path_falls_back_to_default(monkeypatch):
    monkeypatch.delenv("HERDR_SOCKET_PATH", raising=False)
    monkeypatch.delenv("HERDR_SESSION", raising=False)
    assert herdr.socket_path() == Path.home() / ".config" / "herdr" / "herdr.sock"


# --- call --------------------------------------------------------------------


def test_call_sends_newline_delimited_json_with_params(fake):
    server = fake(_ok({"type": "pong", "version": "0.9.0", "protocol": 22}))
    herdr.call("ping")
    sent = json.loads(server.requests[0])
    # params is REQUIRED by herdr's schema even when empty — omitting it is rejected.
    assert sent["params"] == {}
    assert sent["method"] == "ping"
    assert sent["id"]


def test_call_returns_result_payload(fake):
    fake(_ok({"type": "agent_list", "agents": []}))
    assert herdr.call("agent.list") == {"type": "agent_list", "agents": []}


def test_call_raises_on_error_response(fake):
    fake(_err("not_found", "pane not found"))
    with pytest.raises(herdr.HerdrError, match="pane not found"):
        herdr.call("pane.get", {"pane_id": "nope"})


def test_call_raises_when_socket_missing(monkeypatch, tmp_path):
    monkeypatch.setenv("HERDR_SOCKET_PATH", str(tmp_path / "absent.sock"))
    with pytest.raises(herdr.HerdrError):
        herdr.call("ping")


def test_call_raises_on_hangup_without_response(fake):
    fake()  # accepts the connection, then closes with nothing written
    with pytest.raises(herdr.HerdrError):
        herdr.call("ping")


def test_call_raises_on_malformed_json(fake):
    fake(b"{not json at all\n")
    with pytest.raises(herdr.HerdrError):
        herdr.call("ping")


def test_call_raises_on_response_missing_result(fake):
    fake((json.dumps({"id": "x"}) + "\n").encode())
    with pytest.raises(herdr.HerdrError):
        herdr.call("ping")


def test_call_survives_response_split_across_packets(fake, monkeypatch):
    """A response arriving in fragments must still be read as one line."""
    payload = _ok({"type": "pong", "version": "0.9.0", "protocol": 22})
    fake(payload[:12], payload[12:])  # unused second entry; see below

    # Rebuild a server that dribbles the payload out in two writes.
    class Dribble(FakeHerdr):
        def _serve(self):
            conn, _ = self._sock.accept()
            data = b""
            while not data.endswith(b"\n"):
                chunk = conn.recv(4096)
                if not chunk:
                    break
                data += chunk
            self.requests.append(data.decode().strip())
            conn.sendall(payload[:12])
            conn.sendall(payload[12:])
            conn.close()

    path = Path("/tmp") / f"pipnav-dribble-{id(payload)}.sock"
    path.unlink(missing_ok=True)
    server = Dribble(path, [])
    monkeypatch.setenv("HERDR_SOCKET_PATH", str(path))
    try:
        assert herdr.call("ping")["type"] == "pong"
    finally:
        server.close()
        path.unlink(missing_ok=True)


# --- is_available ------------------------------------------------------------


def test_is_available_true_on_pong(fake):
    fake(_ok({"type": "pong", "version": "0.9.0", "protocol": 22}))
    assert herdr.is_available() is True


def test_is_available_false_when_down(monkeypatch, tmp_path):
    monkeypatch.setenv("HERDR_SOCKET_PATH", str(tmp_path / "absent.sock"))
    assert herdr.is_available() is False


def test_is_available_false_on_garbage(fake):
    fake(b"garbage\n")
    assert herdr.is_available() is False


# --- list_agents -------------------------------------------------------------


def test_list_agents_maps_agent_info(fake):
    fake(_ok({"type": "agent_list", "agents": [AGENT_INFO]}))
    agents = herdr.list_agents()

    assert len(agents) == 1
    agent = agents[0]
    assert agent.pane_id == "w1:p2"
    assert agent.workspace_id == "w1"
    assert agent.harness == "claude"
    assert agent.status == "blocked"
    assert agent.cwd == Path("/home/ewise/projects/PIPNAV")
    assert agent.title == "approve migration?"
    assert agent.session_ref == "abc-123"
    assert agent.session_kind == "id"
    assert agent.focused is False


def test_list_agents_returns_empty_when_herdr_down(monkeypatch, tmp_path):
    """PipNav must stay usable when herdr is not running."""
    monkeypatch.setenv("HERDR_SOCKET_PATH", str(tmp_path / "absent.sock"))
    assert herdr.list_agents() == ()


def test_list_agents_tolerates_missing_optional_fields(fake):
    bare = {"pane_id": "w1:p1", "tab_id": "w1:t1", "workspace_id": "w1"}
    fake(_ok({"type": "agent_list", "agents": [bare]}))
    agent = herdr.list_agents()[0]

    assert agent.harness == ""
    assert agent.status == "unknown"
    assert agent.cwd is None
    assert agent.session_ref == ""


def test_list_agents_maps_unrecognised_status_to_unknown(fake):
    """A future herdr version adding a status must not corrupt the fleet view."""
    rogue = {**AGENT_INFO, "agent_status": "compacting"}
    fake(_ok({"type": "agent_list", "agents": [rogue]}))
    assert herdr.list_agents()[0].status == "unknown"


def test_list_agents_skips_entries_without_a_pane_id(fake):
    fake(_ok({"type": "agent_list", "agents": [{"agent": "claude"}, AGENT_INFO]}))
    agents = herdr.list_agents()
    assert [a.pane_id for a in agents] == ["w1:p2"]


def test_list_agents_ignores_non_list_payload(fake):
    fake(_ok({"type": "agent_list", "agents": "nope"}))
    assert herdr.list_agents() == ()


def test_list_agents_prefers_display_agent_for_label(fake):
    fake(_ok({"type": "agent_list", "agents": [AGENT_INFO]}))
    assert herdr.list_agents()[0].label == "Claude Code"


def test_list_agents_label_falls_back_to_harness(fake):
    no_display = {k: v for k, v in AGENT_INFO.items() if k != "display_agent"}
    fake(_ok({"type": "agent_list", "agents": [no_display]}))
    assert herdr.list_agents()[0].label == "claude"


# --- focus_agent -------------------------------------------------------------


def test_focus_agent_addresses_the_agent_by_target(fake):
    """agent.* methods take `target`, not `pane_id` — only agent.start differs."""
    server = fake(_ok({"type": "agent_info", "agent": AGENT_INFO}))
    assert herdr.focus_agent("w1:p2") is True

    sent = json.loads(server.requests[0])
    assert sent["method"] == "agent.focus"
    assert sent["params"] == {"target": "w1:p2"}


def test_focus_agent_false_when_herdr_refuses(fake):
    fake(_err("not_found", "no such agent"))
    assert herdr.focus_agent("w9:p9") is False


def test_focus_agent_false_when_herdr_down(monkeypatch, tmp_path):
    monkeypatch.setenv("HERDR_SOCKET_PATH", str(tmp_path / "absent.sock"))
    assert herdr.focus_agent("w1:p2") is False


# --- find_workspace ----------------------------------------------------------


WORKSPACES = {
    "type": "workspace_list",
    "workspaces": [
        {"workspace_id": "w1", "label": "scratch"},
        {"workspace_id": "w2", "label": "PIPNAV"},
    ],
}


def test_find_workspace_matches_by_label(fake):
    fake(_ok(WORKSPACES))
    assert herdr.find_workspace("PIPNAV") == "w2"


def test_find_workspace_none_when_no_match(fake):
    fake(_ok(WORKSPACES))
    assert herdr.find_workspace("cleanroom") is None


def test_find_workspace_none_when_herdr_down(monkeypatch, tmp_path):
    monkeypatch.setenv("HERDR_SOCKET_PATH", str(tmp_path / "absent.sock"))
    assert herdr.find_workspace("PIPNAV") is None


# --- open_agent --------------------------------------------------------------
#
# Placement is the thing worth testing: one workspace per project, and a NEW TAB
# for a second agent in a project that already has one. Getting this wrong puts
# an agent somewhere the user isn't looking, with no error to show for it.


def _workspace_created(workspace_id="w3", pane_id="w3:p1"):
    return _ok({
        "type": "workspace_created",
        "workspace": {"workspace_id": workspace_id, "label": "cleanroom"},
        "tab": {"tab_id": f"{workspace_id}:t1"},
        "root_pane": {"pane_id": pane_id},
    })


def _tab_created(pane_id="w2:p7"):
    return _ok({
        "type": "tab_created",
        "tab": {"tab_id": "w2:t2", "workspace_id": "w2"},
        "root_pane": {"pane_id": pane_id},
    })


def _agent_started(pane_id="w3:p1"):
    return _ok({
        "type": "agent_started",
        "agent": {**AGENT_INFO, "pane_id": pane_id},
        "argv": ["claude", "--permission-mode", "auto"],
    })


def test_open_agent_creates_workspace_for_a_new_project(fake):
    server = fake(
        _ok(WORKSPACES),                 # workspace.list — no "cleanroom"
        _workspace_created(),            # workspace.create
        _agent_started(),                # agent.start
    )
    ok, err = herdr.open_agent(
        Path("/home/ewise/projects/cleanroom"), "claude",
        ("--permission-mode", "auto"),
    )
    assert (ok, err) == (True, "")

    methods = [json.loads(r)["method"] for r in server.requests]
    assert methods == ["workspace.list", "workspace.create", "agent.start"]

    create = json.loads(server.requests[1])["params"]
    assert create["label"] == "cleanroom"
    assert create["cwd"] == "/home/ewise/projects/cleanroom"


def test_open_agent_opens_a_new_tab_in_an_existing_project(fake):
    """A second agent in the same project gets its own tab, not a split."""
    server = fake(
        _ok(WORKSPACES),        # workspace.list — "PIPNAV" already exists
        _tab_created(),         # tab.create
        _agent_started("w2:p7"),
    )
    ok, err = herdr.open_agent(Path("/home/ewise/projects/PIPNAV"), "codex")
    assert (ok, err) == (True, "")

    methods = [json.loads(r)["method"] for r in server.requests]
    assert methods == ["workspace.list", "tab.create", "agent.start"]

    tab = json.loads(server.requests[1])["params"]
    assert tab["workspace_id"] == "w2"
    assert tab["cwd"] == "/home/ewise/projects/PIPNAV"


def test_open_agent_starts_the_right_kind_with_our_flags(fake):
    server = fake(_ok(WORKSPACES), _workspace_created(), _agent_started())
    herdr.open_agent(
        Path("/home/ewise/projects/cleanroom"), "claude",
        ("--model", "opus", "--permission-mode", "auto"),
    )
    start = json.loads(server.requests[2])["params"]

    # agent.start is the one agent.* method addressed by pane_id, not target.
    assert start["pane_id"] == "w3:p1"
    assert start["kind"] == "claude"
    assert start["args"] == ["--model", "opus", "--permission-mode", "auto"]


def test_open_agent_fails_cleanly_when_herdr_down(monkeypatch, tmp_path):
    monkeypatch.setenv("HERDR_SOCKET_PATH", str(tmp_path / "absent.sock"))
    ok, err = herdr.open_agent(Path("/tmp/x"), "claude")
    assert ok is False
    assert err


def test_open_agent_fails_when_the_agent_will_not_start(fake):
    fake(_ok(WORKSPACES), _workspace_created(), _err("spawn_failed", "claude not found"))
    ok, err = herdr.open_agent(Path("/home/ewise/projects/cleanroom"), "claude")
    assert ok is False
    assert "claude not found" in err


def test_open_agent_fails_when_no_pane_comes_back(fake):
    """Never call agent.start without a pane to start it in."""
    fake(_ok(WORKSPACES), _ok({"type": "workspace_created", "workspace": {}}))
    ok, err = herdr.open_agent(Path("/home/ewise/projects/cleanroom"), "claude")
    assert ok is False
    assert err


# --- open_agent: naming and cleanup -----------------------------------------
#
# Found by running it for real: herdr requires agent names to be unique across
# the whole session, so a fixed name ("claude") allows exactly one Claude to
# exist anywhere — which defeats the point of a multi-project fleet.


def test_open_agent_names_the_agent_per_project(fake):
    server = fake(_ok(WORKSPACES), _workspace_created(), _agent_started())
    herdr.open_agent(Path("/home/ewise/projects/cleanroom"), "claude")
    start = json.loads(server.requests[2])["params"]
    assert start["name"] == "claude-cleanroom"


def test_open_agent_retries_with_a_unique_name_when_taken(fake):
    server = fake(
        _ok(WORKSPACES),
        _workspace_created(),
        _err("agent_name_taken", "agent name claude-cleanroom is already used"),
        _agent_started(),
    )
    ok, err = herdr.open_agent(Path("/home/ewise/projects/cleanroom"), "claude")
    assert (ok, err) == (True, "")

    methods = [json.loads(r)["method"] for r in server.requests]
    assert methods.count("agent.start") == 2

    first = json.loads(server.requests[2])["params"]["name"]
    second = json.loads(server.requests[3])["params"]["name"]
    assert first == "claude-cleanroom"
    assert second != first
    assert "w3-p1" in second  # pane id, sanitised, makes it unique


def test_open_agent_closes_the_workspace_it_created_when_the_agent_fails(fake):
    """A failed launch must not leave a stray empty workspace in herdr."""
    server = fake(
        _ok(WORKSPACES),
        _workspace_created(),
        _err("spawn_failed", "claude not found"),
        _err("spawn_failed", "claude not found"),  # the name retry
        _ok({"type": "workspace_closed"}),
    )
    ok, _ = herdr.open_agent(Path("/home/ewise/projects/cleanroom"), "claude")
    assert ok is False

    methods = [json.loads(r)["method"] for r in server.requests]
    assert methods[-1] == "workspace.close"
    assert json.loads(server.requests[-1])["params"] == {"workspace_id": "w3"}


def test_open_agent_closes_only_the_tab_it_created_in_an_existing_workspace(fake):
    """Reusing a project's workspace means cleaning up the tab, never the workspace."""
    server = fake(
        _ok(WORKSPACES),
        _tab_created(),
        _err("spawn_failed", "codex not found"),
        _err("spawn_failed", "codex not found"),
        _ok({"type": "tab_closed"}),
    )
    ok, _ = herdr.open_agent(Path("/home/ewise/projects/PIPNAV"), "codex")
    assert ok is False

    methods = [json.loads(r)["method"] for r in server.requests]
    assert methods[-1] == "tab.close"
    assert "workspace.close" not in methods
    assert json.loads(server.requests[-1])["params"] == {"tab_id": "w2:t2"}


# --- agent names -------------------------------------------------------------
#
# herdr enforces ^[a-z][a-z0-9_-]{0,31}$ on agent names. Found by launching for
# real: "claude@PIPNAV" is rejected for both the "@" and the capitals.

NAME_OK = __import__("re").compile(r"^[a-z][a-z0-9_-]{0,31}$")


def test_agent_name_is_lowercase_and_hyphenated():
    assert herdr.agent_name("claude", "PIPNAV") == "claude-pipnav"


def test_agent_name_strips_characters_herdr_rejects():
    name = herdr.agent_name("claude", "my project (v2)!")
    assert NAME_OK.match(name), name


def test_agent_name_respects_the_32_character_cap():
    name = herdr.agent_name("opencode", "a-very-long-project-name-indeed-yes-truly")
    assert len(name) <= 32
    assert NAME_OK.match(name), name


def test_agent_name_qualified_by_pane_stays_valid():
    name = herdr.agent_name("claude", "PIPNAV", pane_id="w4:p12")
    assert NAME_OK.match(name), name
    assert "w4-p12" in name


def test_agent_name_qualified_by_pane_respects_the_cap():
    name = herdr.agent_name("opencode", "a-very-long-project-name-indeed", pane_id="w4:p12")
    assert len(name) <= 32
    assert NAME_OK.match(name), name
    assert name.endswith("w4-p12")  # the uniquifier must survive truncation


def test_agent_name_always_starts_with_a_letter():
    assert NAME_OK.match(herdr.agent_name("claude", "123-numeric-start"))
