"""Tests for profile editor data parsing logic."""

from pipnav.core.profiles import WorkspaceProfile
from pipnav.ui.profile_editor import (
    format_comma_list,
    parse_comma_list,
)


class TestParseCommaList:
    def test_basic_split(self) -> None:
        result = parse_comma_list("~/projects, ~/work")
        assert result == ("~/projects", "~/work")

    def test_strips_whitespace(self) -> None:
        result = parse_comma_list("  foo ,  bar  , baz  ")
        assert result == ("foo", "bar", "baz")

    def test_empty_string(self) -> None:
        result = parse_comma_list("")
        assert result == ()

    def test_single_item(self) -> None:
        result = parse_comma_list("~/projects")
        assert result == ("~/projects",)

    def test_skips_empty_segments(self) -> None:
        result = parse_comma_list("a,,b, ,c")
        assert result == ("a", "b", "c")

    def test_trailing_comma(self) -> None:
        result = parse_comma_list("~/projects,")
        assert result == ("~/projects",)


class TestFormatCommaList:
    def test_basic_format(self) -> None:
        result = format_comma_list(("~/projects", "~/work"))
        assert result == "~/projects, ~/work"

    def test_empty_tuple(self) -> None:
        result = format_comma_list(())
        assert result == ""

    def test_single_item(self) -> None:
        result = format_comma_list(("~/projects",))
        assert result == "~/projects"


class TestBuildProfileFromInputs:
    """Test building a WorkspaceProfile from parsed form inputs."""

    def test_build_new_profile(self) -> None:
        roots = parse_comma_list("~/projects, ~/work")
        hidden = parse_comma_list("old-proj, archive")
        profile = WorkspaceProfile(
            name="dev",
            roots=roots,
            hidden_projects=hidden,
            color_scheme="amber",
            default_recipe="Launch",
        )
        assert profile.name == "dev"
        assert profile.roots == ("~/projects", "~/work")
        assert profile.hidden_projects == ("old-proj", "archive")
        assert profile.color_scheme == "amber"
        assert profile.default_recipe == "Launch"

    def test_build_profile_empty_optional_fields(self) -> None:
        roots = parse_comma_list("")
        hidden = parse_comma_list("")
        profile = WorkspaceProfile(
            name="minimal",
            roots=roots,
            hidden_projects=hidden,
            color_scheme="",
            default_recipe="",
        )
        assert profile.name == "minimal"
        assert profile.roots == ()
        assert profile.hidden_projects == ()
        assert profile.color_scheme == ""
        assert profile.default_recipe == ""

    def test_color_scheme_inherit(self) -> None:
        """Empty string means inherit from config."""
        profile = WorkspaceProfile(name="test", color_scheme="")
        assert profile.color_scheme == ""

    def test_valid_color_schemes(self) -> None:
        for scheme in ("green", "amber", "blue", "white"):
            profile = WorkspaceProfile(name="test", color_scheme=scheme)
            assert profile.color_scheme == scheme

    def test_preserves_existing_recipes(self) -> None:
        """Editing a profile should preserve its existing recipes."""
        from pipnav.core.profiles import LaunchRecipe

        existing_recipe = LaunchRecipe(name="Custom", action="launch")
        profile = WorkspaceProfile(
            name="dev",
            roots=parse_comma_list("~/new-root"),
            recipes=(existing_recipe,),
        )
        assert len(profile.recipes) == 1
        assert profile.recipes[0].name == "Custom"

    def test_round_trip_comma_list(self) -> None:
        """Parsing formatted output should yield the original tuple."""
        original = ("~/projects", "~/work", "~/personal")
        formatted = format_comma_list(original)
        parsed = parse_comma_list(formatted)
        assert parsed == original
