from pathlib import Path

import pytest

from gmaps_scraper.config import ConfigError, load_config

ROOT = Path(__file__).resolve().parent.parent


def test_repository_config_loads():
    cfg = load_config(ROOT / "config.toml")
    assert "milan" in cfg.cities
    assert cfg.settings.page_pause_s == (3.0, 7.0)
    assert len(cfg.categories) == 11


def test_resolve_categories():
    cfg = load_config(ROOT / "config.toml")
    assert cfg.resolve_categories(["museum", "@green", "museum"]) == ["museum", "park", "garden"]
    assert cfg.resolve_categories(["all"]) == list(cfg.categories)
    with pytest.raises(ConfigError):
        cfg.resolve_categories(["pizza"])
    with pytest.raises(ConfigError):
        cfg.resolve_categories(["@nope"])


def test_invalid_bbox(tmp_path):
    bad = tmp_path / "c.toml"
    bad.write_text('[categories]\nmuseum = "museum"\n[cities.x]\nbbox = { south = 46, west = 9, north = 45, east = 10 }\n')
    with pytest.raises(ConfigError):
        load_config(bad)


def test_unknown_setting(tmp_path):
    bad = tmp_path / "c.toml"
    bad.write_text('[settings]\nzom = 15\n[categories]\nmuseum = "museum"\n')
    with pytest.raises(ConfigError):
        load_config(bad)
