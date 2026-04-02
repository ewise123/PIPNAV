"""Configuration management — read/write ~/.pipnav/config.json."""

import json
from dataclasses import asdict, dataclass, replace
from pathlib import Path

from pipnav.core.logging import get_logger

PIPNAV_DIR = Path.home() / ".pipnav"
CONFIG_PATH = PIPNAV_DIR / "config.json"


@dataclass(frozen=True)
class PipNavConfig:
    """Immutable application configuration."""

    project_roots: tuple[str, ...] = ("~/projects",)
    crt_effects: bool = False
    tags: tuple[str, ...] = ("work", "personal", "archived", "active")
    stale_threshold_days: int = 30
    vscode_command: str = "code"
    claude_command: str = "claude"
    color_scheme: str = "green"
    active_profile: str = ""
    cache_ttl_seconds: int = 60
    poll_interval_seconds: int = 10


def _ensure_pipnav_dir() -> Path:
    """Create ~/.pipnav/ if it doesn't exist. Return the path."""
    PIPNAV_DIR.mkdir(parents=True, exist_ok=True)
    return PIPNAV_DIR


def _config_to_dict(config: PipNavConfig) -> dict:
    """Convert config to a JSON-serializable dict."""
    d = asdict(config)
    # Convert tuples to lists for JSON
    d["project_roots"] = list(config.project_roots)
    d["tags"] = list(config.tags)
    # Exclude internal/transient fields from JSON
    return d


def _dict_to_config(data: dict) -> PipNavConfig:
    """Convert a dict from JSON to a PipNavConfig, filling in defaults."""
    defaults = PipNavConfig()
    return PipNavConfig(
        project_roots=tuple(data.get("project_roots", defaults.project_roots)),
        crt_effects=data.get("crt_effects", defaults.crt_effects),
        tags=tuple(data.get("tags", defaults.tags)),
        stale_threshold_days=data.get(
            "stale_threshold_days", defaults.stale_threshold_days
        ),
        vscode_command=data.get("vscode_command", defaults.vscode_command),
        claude_command=data.get("claude_command", defaults.claude_command),
        color_scheme=data.get("color_scheme", defaults.color_scheme),
        active_profile=data.get("active_profile", defaults.active_profile),
        cache_ttl_seconds=data.get("cache_ttl_seconds", defaults.cache_ttl_seconds),
        poll_interval_seconds=data.get(
            "poll_interval_seconds", defaults.poll_interval_seconds
        ),
    )


def load_config() -> PipNavConfig:
    """Load config from ~/.pipnav/config.json, creating defaults if missing."""
    logger = get_logger()
    _ensure_pipnav_dir()

    if not CONFIG_PATH.exists():
        logger.info("No config found, creating defaults at %s", CONFIG_PATH)
        config = PipNavConfig()
        save_config(config)
        return config

    try:
        raw = CONFIG_PATH.read_text(encoding="utf-8")
        data = json.loads(raw)
        return _dict_to_config(data)
    except (json.JSONDecodeError, TypeError, KeyError) as exc:
        logger.warning("Corrupt config file, using defaults: %s", exc)
        return PipNavConfig()


def save_config(config: PipNavConfig) -> None:
    """Write config to ~/.pipnav/config.json."""
    logger = get_logger()
    _ensure_pipnav_dir()

    try:
        data = _config_to_dict(config)
        CONFIG_PATH.write_text(
            json.dumps(data, indent=2) + "\n", encoding="utf-8"
        )
    except OSError as exc:
        logger.error("Failed to save config: %s", exc)


def update_config(config: PipNavConfig, **changes: object) -> PipNavConfig:
    """Return a new config with the given fields replaced, and save it."""
    new_config = replace(config, **changes)
    save_config(new_config)
    return new_config
