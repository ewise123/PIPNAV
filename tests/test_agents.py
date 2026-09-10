"""Tests for the coding-harness registry.

Argv construction is the trust boundary here: a dropped or duplicated flag
launches an agent in the wrong permission mode with no visible symptom, so every
harness gets its flags asserted explicitly.
"""

import pytest

from pipnav.core import agents


def test_registry_has_the_three_supported_harnesses():
    assert [h.key for h in agents.HARNESSES] == ["claude", "codex", "opencode"]


def test_get_returns_the_harness():
    assert agents.get("codex").label == "Codex"


def test_get_unknown_returns_none():
    assert agents.get("aider") is None


def test_keys_double_as_herdr_agent_kinds():
    """herdr recognises these exact strings; they must not drift."""
    for harness in agents.HARNESSES:
        assert harness.herdr_kind == harness.key


# --- launch argv -------------------------------------------------------------


def test_claude_keeps_pipnavs_existing_auto_default():
    assert agents.get("claude").launch_flags == ("--permission-mode", "auto")


@pytest.mark.parametrize("key", ["codex", "opencode"])
def test_codex_and_opencode_launch_with_their_own_safe_defaults(key):
    """Both tools' auto-approve flags are labelled dangerous by their own help.

    PipNav must not opt a user into skipping approvals on their behalf.
    """
    harness = agents.get(key)
    assert harness.launch_flags == ()

    flags = harness.launch_argv()
    for dangerous in (
        "--dangerously-bypass-approvals-and-sandbox",
        "--auto",
        "--full-auto",
    ):
        assert dangerous not in flags


def test_launch_argv_is_just_flags_not_the_binary():
    """herdr's agent.start takes args separately from the kind."""
    assert agents.get("claude").launch_argv() == ("--permission-mode", "auto")


def test_launch_argv_appends_extra_flags():
    argv = agents.get("claude").launch_argv(("--model", "opus"))
    assert argv == ("--permission-mode", "auto", "--model", "opus")


def test_launch_argv_lets_the_caller_override_a_default():
    """A user asking for plan mode must not also get the auto default."""
    argv = agents.get("claude").launch_argv(("--permission-mode", "plan"))
    assert argv.count("--permission-mode") == 1
    assert "plan" in argv
    assert "auto" not in argv


def test_launch_argv_override_works_for_a_flag_with_no_value():
    harness = agents.Harness(
        key="x", label="X", binary="x", launch_flags=("--quiet",)
    )
    assert harness.launch_argv(("--quiet",)) == ("--quiet",)


# --- resume argv -------------------------------------------------------------
#
# Each tool spells resume differently: a flag, a subcommand, a short option.


def test_claude_resume_uses_a_flag():
    assert agents.get("claude").resume_argv("abc-123") == ("--resume", "abc-123")


def test_codex_resume_uses_a_subcommand():
    assert agents.get("codex").resume_argv("abc-123") == ("resume", "abc-123")


def test_opencode_resume_uses_a_short_option():
    assert agents.get("opencode").resume_argv("abc-123") == ("-s", "abc-123")


def test_resume_argv_refuses_an_empty_session_id():
    """Resuming with no id would silently start a fresh session instead."""
    with pytest.raises(ValueError):
        agents.get("claude").resume_argv("")


def test_resume_argv_keeps_launch_defaults_out_of_the_way():
    """Resuming must not re-apply a permission default the session already has."""
    assert "--permission-mode" not in agents.get("claude").resume_argv("abc")
