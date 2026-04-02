"""Tests for workspace profiles and launch recipes."""

import json
from pathlib import Path

import pytest

from pipnav.core.profiles import (
    BUILTIN_RECIPES,
    DEFAULT_PROFILE,
    LaunchRecipe,
    WorkspaceProfile,
    filter_projects_by_profile,
    get_available_recipes,
    get_effective_roots,
    get_profile_by_name,
    load_profiles,
    save_profiles,
)


@pytest.fixture(autouse=True)
def _use_tmp_profiles(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Redirect profiles to a temp directory."""
    import pipnav.core.profiles as prof
    import pipnav.core.config as cfg

    monkeypatch.setattr(cfg, "PIPNAV_DIR", tmp_path)
    monkeypatch.setattr(prof, "PIPNAV_DIR", tmp_path)
    monkeypatch.setattr(prof, "PROFILES_PATH", tmp_path / "profiles.json")


def _make_profile(**overrides: object) -> WorkspaceProfile:
    defaults = {"name": "test"}
    defaults.update(overrides)
    return WorkspaceProfile(**defaults)


def _make_recipe(**overrides: object) -> LaunchRecipe:
    defaults = {"name": "Test Recipe", "action": "launch"}
    defaults.update(overrides)
    return LaunchRecipe(**defaults)


class TestProfilePersistence:
    def test_save_and_load_round_trip(self) -> None:
        profiles = (
            _make_profile(name="work", roots=("~/work",)),
            _make_profile(name="personal", roots=("~/personal",)),
        )
        save_profiles(profiles)
        loaded = load_profiles()

        assert len(loaded) == 2
        assert loaded[0].name == "work"
        assert loaded[0].roots == ("~/work",)
        assert loaded[1].name == "personal"

    def test_load_empty_when_missing(self) -> None:
        assert load_profiles() == ()

    def test_load_handles_corrupt_json(self, tmp_path: Path) -> None:
        import pipnav.core.profiles as prof

        prof.PROFILES_PATH.write_text("not json!", encoding="utf-8")
        assert load_profiles() == ()

    def test_recipes_survive_round_trip(self) -> None:
        recipe = _make_recipe(
            name="Review",
            description="Start a review",
            action="launch",
            claude_flags=("--model", "opus"),
            permission_mode="plan",
        )
        profile = _make_profile(name="dev", recipes=(recipe,))
        save_profiles((profile,))
        loaded = load_profiles()

        assert len(loaded[0].recipes) == 1
        r = loaded[0].recipes[0]
        assert r.name == "Review"
        assert r.claude_flags == ("--model", "opus")
        assert r.permission_mode == "plan"

    def test_profile_with_filters(self) -> None:
        profile = _make_profile(
            name="focused",
            tags_filter=("work",),
            hidden_projects=("old-project",),
        )
        save_profiles((profile,))
        loaded = load_profiles()

        assert loaded[0].tags_filter == ("work",)
        assert loaded[0].hidden_projects == ("old-project",)


class TestProfileLookup:
    def test_get_by_name(self) -> None:
        profiles = (
            _make_profile(name="alpha"),
            _make_profile(name="beta"),
        )
        assert get_profile_by_name(profiles, "beta").name == "beta"

    def test_get_by_name_case_insensitive(self) -> None:
        profiles = (_make_profile(name="Work"),)
        assert get_profile_by_name(profiles, "work").name == "Work"

    def test_get_by_name_not_found(self) -> None:
        profiles = (_make_profile(name="alpha"),)
        assert get_profile_by_name(profiles, "gamma") is None


class TestEffectiveRoots:
    def test_uses_profile_roots_when_set(self) -> None:
        profile = _make_profile(roots=("~/custom",))
        result = get_effective_roots(profile, ("~/projects",))
        assert result == ("~/custom",)

    def test_falls_back_to_config_roots(self) -> None:
        profile = _make_profile(roots=())
        result = get_effective_roots(profile, ("~/projects",))
        assert result == ("~/projects",)


class TestAvailableRecipes:
    def test_builtins_always_available(self) -> None:
        profile = _make_profile()
        recipes = get_available_recipes(profile)
        names = {r.name for r in recipes}
        assert "Launch" in names
        assert "Resume Latest" in names

    def test_profile_recipes_come_first(self) -> None:
        custom = _make_recipe(name="Custom Action")
        profile = _make_profile(recipes=(custom,))
        recipes = get_available_recipes(profile)
        assert recipes[0].name == "Custom Action"

    def test_profile_recipe_overrides_builtin_by_name(self) -> None:
        custom_launch = _make_recipe(
            name="Launch",
            description="Custom launch",
            permission_mode="plan",
        )
        profile = _make_profile(recipes=(custom_launch,))
        recipes = get_available_recipes(profile)
        launch_recipes = [r for r in recipes if r.name == "Launch"]
        assert len(launch_recipes) == 1
        assert launch_recipes[0].permission_mode == "plan"


class TestFilterProjects:
    def test_no_filter(self) -> None:
        profile = _make_profile()
        paths = ("/home/user/a", "/home/user/b")
        assert filter_projects_by_profile(paths, profile) == paths

    def test_hides_projects(self) -> None:
        profile = _make_profile(hidden_projects=("old",))
        paths = ("/home/user/old", "/home/user/new")
        result = filter_projects_by_profile(paths, profile)
        assert result == ("/home/user/new",)


class TestLaunchRecipe:
    def test_display_label_launch(self) -> None:
        r = _make_recipe(name="Go", action="launch")
        assert "[>] Go" in r.display_label

    def test_display_label_resume(self) -> None:
        r = _make_recipe(name="Resume", action="resume_latest")
        assert "[R] Resume" in r.display_label

    def test_frozen(self) -> None:
        r = _make_recipe()
        with pytest.raises(AttributeError):
            r.name = "changed"  # type: ignore[misc]


class TestDefaultProfile:
    def test_default_has_empty_roots(self) -> None:
        assert DEFAULT_PROFILE.roots == ()

    def test_default_name(self) -> None:
        assert DEFAULT_PROFILE.name == "default"
