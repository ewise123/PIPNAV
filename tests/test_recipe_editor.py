"""Tests for recipe editor flag round-tripping."""

from pipnav.core.launcher import LaunchOptions
from pipnav.ui.recipe_editor import (
    _format_flag_string,
    _split_flag_string,
    launch_options_to_recipe,
)


def test_split_flag_string_preserves_quoted_values() -> None:
    flags = _split_flag_string(
        '--append-system-prompt "Review auth flow" --add-dir "/tmp/my docs"'
    )

    assert flags == (
        "--append-system-prompt",
        "Review auth flow",
        "--add-dir",
        "/tmp/my docs",
    )


def test_format_flag_string_quotes_values_with_spaces() -> None:
    text = _format_flag_string(
        ("--append-system-prompt", "Review auth flow", "--add-dir", "/tmp/my docs")
    )

    assert text == "--append-system-prompt 'Review auth flow' --add-dir '/tmp/my docs'"


def test_launch_options_to_recipe_keeps_permission_mode_separate() -> None:
    recipe = launch_options_to_recipe(
        LaunchOptions(
            model="opus",
            permission_mode="plan",
            append_system_prompt="Review auth flow",
        )
    )

    assert recipe.permission_mode == "plan"
    assert recipe.claude_flags == (
        "--model",
        "opus",
        "--append-system-prompt",
        "Review auth flow",
    )
