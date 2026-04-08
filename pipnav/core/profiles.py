"""Workspace profiles and launch recipes — named modes with custom roots/filters/recipes."""

import json
from dataclasses import asdict, dataclass, replace
from pathlib import Path

from pipnav.core.config import PIPNAV_DIR
from pipnav.core.logging import get_logger

PROFILES_PATH = PIPNAV_DIR / "profiles.json"


@dataclass(frozen=True)
class LaunchRecipe:
    """A named Claude launch configuration."""

    name: str
    description: str = ""
    action: str = "launch"  # "launch" | "resume_latest" | "resume_pick"
    claude_flags: tuple[str, ...] = ()
    permission_mode: str = ""

    @property
    def display_label(self) -> str:
        icon = {
            "launch": ">",
            "resume_latest": "R",
            "resume_pick": "?",
            "remote_control": "~",
        }
        return f"[{icon.get(self.action, '>')}] {self.name}"


@dataclass(frozen=True)
class WorkspaceProfile:
    """A named workspace mode with roots, filters, theme, and recipes."""

    name: str
    roots: tuple[str, ...] = ()
    tags_filter: tuple[str, ...] = ()
    hidden_projects: tuple[str, ...] = ()
    color_scheme: str = ""
    default_recipe: str = ""
    recipes: tuple[LaunchRecipe, ...] = ()


# --- Built-in profiles ---

DEFAULT_PROFILE = WorkspaceProfile(
    name="default",
    roots=(),  # empty means use config.project_roots
)

BUILTIN_RECIPES: tuple[LaunchRecipe, ...] = (
    LaunchRecipe(
        name="Launch",
        description="Start new Claude session",
        action="launch",
        permission_mode="auto",
    ),
    LaunchRecipe(
        name="Resume Latest",
        description="Resume most recent session",
        action="resume_latest",
    ),
    LaunchRecipe(
        name="Resume Pick",
        description="Pick a session to resume",
        action="resume_pick",
    ),
    LaunchRecipe(
        name="Remote Control",
        description="Start remote control server (claude.ai/code)",
        action="remote_control",
    ),
    LaunchRecipe(
        name="Remote Interactive",
        description="Launch interactive session with remote access",
        action="launch",
        claude_flags=("--remote-control",),
        permission_mode="auto",
    ),
)


# --- Serialization ---

def _recipe_to_dict(recipe: LaunchRecipe) -> dict:
    d = asdict(recipe)
    d["claude_flags"] = list(recipe.claude_flags)
    return d


def _dict_to_recipe(data: dict) -> LaunchRecipe:
    return LaunchRecipe(
        name=data.get("name", "Untitled"),
        description=data.get("description", ""),
        action=data.get("action", "launch"),
        claude_flags=tuple(data.get("claude_flags", ())),
        permission_mode=data.get("permission_mode", ""),
    )


def _profile_to_dict(profile: WorkspaceProfile) -> dict:
    return {
        "name": profile.name,
        "roots": list(profile.roots),
        "tags_filter": list(profile.tags_filter),
        "hidden_projects": list(profile.hidden_projects),
        "color_scheme": profile.color_scheme,
        "default_recipe": profile.default_recipe,
        "recipes": [_recipe_to_dict(r) for r in profile.recipes],
    }


def _dict_to_profile(data: dict) -> WorkspaceProfile:
    return WorkspaceProfile(
        name=data.get("name", "Untitled"),
        roots=tuple(data.get("roots", ())),
        tags_filter=tuple(data.get("tags_filter", ())),
        hidden_projects=tuple(data.get("hidden_projects", ())),
        color_scheme=data.get("color_scheme", ""),
        default_recipe=data.get("default_recipe", ""),
        recipes=tuple(
            _dict_to_recipe(r) for r in data.get("recipes", ())
        ),
    )


# --- Persistence ---

def load_profiles() -> tuple[WorkspaceProfile, ...]:
    """Load profiles from ~/.pipnav/profiles.json."""
    logger = get_logger()

    if not PROFILES_PATH.exists():
        return ()

    try:
        raw = PROFILES_PATH.read_text(encoding="utf-8")
        data = json.loads(raw)
        profiles = tuple(_dict_to_profile(p) for p in data.get("profiles", ()))
        return profiles
    except (json.JSONDecodeError, TypeError, KeyError) as exc:
        logger.warning("Corrupt profiles file: %s", exc)
        return ()


def save_profiles(profiles: tuple[WorkspaceProfile, ...]) -> None:
    """Write profiles to ~/.pipnav/profiles.json."""
    logger = get_logger()
    PIPNAV_DIR.mkdir(parents=True, exist_ok=True)

    try:
        data = {"profiles": [_profile_to_dict(p) for p in profiles]}
        PROFILES_PATH.write_text(
            json.dumps(data, indent=2) + "\n", encoding="utf-8"
        )
    except OSError as exc:
        logger.error("Failed to save profiles: %s", exc)


def get_profile_by_name(
    profiles: tuple[WorkspaceProfile, ...],
    name: str,
) -> WorkspaceProfile | None:
    """Find a profile by name (case-insensitive)."""
    for p in profiles:
        if p.name.lower() == name.lower():
            return p
    return None


def get_effective_roots(
    profile: WorkspaceProfile,
    config_roots: tuple[str, ...],
) -> tuple[str, ...]:
    """Get the roots to use — profile roots if set, otherwise config roots."""
    return profile.roots if profile.roots else config_roots


def get_available_recipes(
    profile: WorkspaceProfile,
) -> tuple[LaunchRecipe, ...]:
    """Get recipes available for a profile — profile-specific + builtins."""
    # Profile recipes first, then builtins (skip duplicates by name)
    seen: set[str] = set()
    result: list[LaunchRecipe] = []

    for recipe in profile.recipes:
        if recipe.name.lower() not in seen:
            seen.add(recipe.name.lower())
            result.append(recipe)

    for recipe in BUILTIN_RECIPES:
        if recipe.name.lower() not in seen:
            seen.add(recipe.name.lower())
            result.append(recipe)

    return tuple(result)


def filter_projects_by_profile(
    project_paths: tuple[str, ...],
    profile: WorkspaceProfile,
) -> tuple[str, ...]:
    """Filter project paths based on profile's hidden_projects list."""
    if not profile.hidden_projects:
        return project_paths

    hidden = frozenset(profile.hidden_projects)
    return tuple(p for p in project_paths if Path(p).name not in hidden)
