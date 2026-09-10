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
