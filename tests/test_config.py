"""Tests for config read/write."""

import json
from pathlib import Path

import pytest

from pipnav.core.config import (
    PipNavConfig,
    _config_to_dict,
    _dict_to_config,
    load_config,
    save_config,
    update_config,
)


@pytest.fixture(autouse=True)
def _use_tmp_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Redirect config to a temp directory."""
    import pipnav.core.config as cfg

    monkeypatch.setattr(cfg, "PIPNAV_DIR", tmp_path)
    monkeypatch.setattr(cfg, "CONFIG_PATH", tmp_path / "config.json")


def test_default_config() -> None:
    config = PipNavConfig()
    assert config.project_roots == ("~/projects",)
    assert config.crt_effects is False
    assert config.stale_threshold_days == 30


def test_config_is_frozen() -> None:
    config = PipNavConfig()
    with pytest.raises(AttributeError):
        config.crt_effects = True  # type: ignore[misc]


def test_round_trip() -> None:
    config = PipNavConfig(
        project_roots=("~/a", "~/b"),
        crt_effects=True,
        tags=("foo", "bar"),
    )
    save_config(config)
    loaded = load_config()
    assert loaded.project_roots == ("~/a", "~/b")
    assert loaded.crt_effects is True
    assert loaded.tags == ("foo", "bar")


def test_load_creates_defaults_when_missing() -> None:
    config = load_config()
    assert config == PipNavConfig()


def test_load_handles_corrupt_json(tmp_path: Path) -> None:
    import pipnav.core.config as cfg

    cfg.CONFIG_PATH.write_text("not json!", encoding="utf-8")
    config = load_config()
    assert config == PipNavConfig()


def test_dict_to_config_fills_defaults() -> None:
    config = _dict_to_config({"crt_effects": True})
    assert config.crt_effects is True
    assert config.project_roots == ("~/projects",)


def test_update_config() -> None:
    config = PipNavConfig()
    updated = update_config(config, crt_effects=True)
    assert updated.crt_effects is True
    assert config.crt_effects is False  # Original unchanged
