"""Load and validate config.toml.

The rest of the package never reads the TOML file directly: it receives a
`Config` object. This keeps one place that knows the file layout and turns
mistakes (a missing key, a south bigger than north) into clear errors before
the browser is ever opened.
"""
from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from .geometry import BBox, bbox_around


class ConfigError(ValueError):
    """The configuration file is missing something or contains an invalid value."""


@dataclass(frozen=True)
class Settings:
    zoom: int = 15
    overlap: float = 0.85
    side_panel_px: int = 408
    viewport: dict = field(default_factory=lambda: {"width": 1280, "height": 900})
    max_scrolls: int = 40
    stall_limit: int = 4
    scroll_pause_s: float = 1.5
    page_pause_s: tuple[float, float] = (3.0, 7.0)
    feed_timeout_ms: int = 15_000
    checkpoint_every: int = 10
    output_dir: Path = Path("raw")


@dataclass(frozen=True)
class City:
    code: str
    name: str
    bbox: BBox
    center: tuple[float, float] | None = None   # set when the city is written as center + radius_km
    radius_km: float | None = None


@dataclass(frozen=True)
class Config:
    settings: Settings
    categories: dict[str, str]           # key -> text typed in the Maps search box
    groups: dict[str, list[str]]         # group name -> list of category keys
    cities: dict[str, City]

    def resolve_categories(self, requested: list[str]) -> list[str]:
        """Turn what the user typed after --categories into a list of category keys.

        Accepted tokens: a category key ("museum"), a group ("@sights") or "all".
        Order is kept and duplicates are removed.
        """
        keys: list[str] = []
        for token in requested:
            if token == "all":
                keys.extend(self.categories)
            elif token.startswith("@"):
                group = token[1:]
                if group not in self.groups:
                    raise ConfigError(f"unknown category group '{group}'. Known: {', '.join(sorted(self.groups)) or 'none'}")
                keys.extend(self.groups[group])
            elif token in self.categories:
                keys.append(token)
            else:
                raise ConfigError(f"unknown category '{token}'. Known: {', '.join(sorted(self.categories))}")
        return list(dict.fromkeys(keys))     # dict keeps insertion order: cheap de-duplication


def _city(code: str, raw: dict) -> City:
    """A city is written either as an explicit `bbox`, or as `center` + `radius_km`
    (the square of +/- radius_km around the centre). An explicit bbox wins."""
    name = str(raw.get("name", code))
    if "bbox" in raw:
        return City(code, name, _bbox(code, raw["bbox"]))
    if "center" in raw and "radius_km" in raw:
        try:
            lat, lng = (float(x) for x in raw["center"])
            radius = float(raw["radius_km"])
        except (TypeError, ValueError) as exc:
            raise ConfigError(f"city '{code}': center must be [lat, lng] and radius_km a number") from exc
        if not (-90 < lat < 90 and -180 <= lng <= 180 and radius > 0):
            raise ConfigError(f"city '{code}': center or radius_km out of range")
        return City(code, name, bbox_around(lat, lng, radius), (lat, lng), radius)
    raise ConfigError(f"city '{code}': give either bbox or center + radius_km")


def _bbox(code: str, raw: dict) -> BBox:
    try:
        box = BBox(float(raw["south"]), float(raw["west"]), float(raw["north"]), float(raw["east"]))
    except (KeyError, TypeError) as exc:
        raise ConfigError(f"city '{code}': bbox needs south, west, north, east") from exc
    if not (box.south < box.north and box.west < box.east):
        raise ConfigError(f"city '{code}': expected south < north and west < east, got {box}")
    return box


def load_config(path: Path) -> Config:
    if not path.exists():
        raise ConfigError(f"config file not found: {path}")
    with path.open("rb") as f:                       # tomllib wants a binary file
        data = tomllib.load(f)

    raw_settings = dict(data.get("settings", {}))
    if "page_pause_s" in raw_settings:
        raw_settings["page_pause_s"] = tuple(raw_settings["page_pause_s"])
    if "output_dir" in raw_settings:
        raw_settings["output_dir"] = Path(raw_settings["output_dir"])
    try:
        settings = Settings(**raw_settings)
    except TypeError as exc:                          # an unknown key in [settings]
        raise ConfigError(f"[settings]: {exc}") from exc

    categories = {str(k): str(v) for k, v in data.get("categories", {}).items()}
    if not categories:
        raise ConfigError("[categories] is empty: add at least one category")

    groups = {str(k): list(v) for k, v in data.get("category_groups", {}).items()}
    for name, members in groups.items():
        unknown = [m for m in members if m not in categories]
        if unknown:
            raise ConfigError(f"group '{name}' uses unknown categories: {', '.join(unknown)}")

    cities = {code: _city(code, raw) for code, raw in data.get("cities", {}).items()}
    return Config(settings=settings, categories=categories, groups=groups, cities=cities)
