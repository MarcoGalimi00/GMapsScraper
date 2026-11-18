"""Command line: choose the city and the categories at launch time.

Examples:
    python -m gmaps_scraper --list
    python -m gmaps_scraper --city milan --categories tourist_attraction
    python -m gmaps_scraper --city milan --categories @sights park
    python -m gmaps_scraper --city milan --categories all --headless
    python -m gmaps_scraper --city turin --bbox 45.00 7.60 45.14 7.75 --categories museum
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .config import Config, ConfigError, load_config
from .geometry import BBox
from .scraper import plan_run, run
from .storage import write_jsonl

log = logging.getLogger("gmaps")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m gmaps_scraper",
                                description="Google Maps places of interest -> JSONL, one city at a time.")
    p.add_argument("--config", type=Path, default=Path("config.toml"), help="configuration file (default: config.toml)")
    p.add_argument("--list", action="store_true", help="show cities, categories and groups in the config, then exit")
    p.add_argument("--city", help="city code from the config (or a new code together with --bbox)")
    p.add_argument("--bbox", nargs=4, type=float, metavar=("SOUTH", "WEST", "NORTH", "EAST"),
                   help="use this rectangle instead of the one in the config")
    p.add_argument("--categories", nargs="+", metavar="CAT",
                   help="category keys, @group names or 'all'")
    p.add_argument("--headless", action="store_true",
                   help="hide the browser window (WARNING: Maps then omits most review counts)")
    p.add_argument("--max-cells", type=int, help="use only the first N grid cells (for tests)")
    p.add_argument("--center-first", action="store_true", help="start from the cells nearest to the centre")
    p.add_argument("--step-km", type=float, help="manual grid step in km (default: automatic)")
    p.add_argument("--output-dir", type=Path, help="override settings.output_dir")
    p.add_argument("--dry-run", action="store_true", help="print the plan without opening the browser")
    return p


def print_catalogue(cfg: Config) -> None:
    print("Cities:")
    for code, city in sorted(cfg.cities.items()):
        b = city.bbox
        print(f"  {code:15} {city.name}  [{b.south}, {b.west}, {b.north}, {b.east}]")
    print("Categories:")
    for key, text in cfg.categories.items():
        print(f"  {key:22} searches \"{text}\"")
    if cfg.groups:
        print("Groups:")
        for name, members in cfg.groups.items():
            print(f"  @{name:21} {', '.join(members)}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    try:
        cfg = load_config(args.config)
        if args.list:
            print_catalogue(cfg)
            return 0
        if not args.city or not args.categories:
            parser.error("--city and --categories are required (see --list)")
        if args.bbox:
            bbox = BBox(*args.bbox)
            if not (bbox.south < bbox.north and bbox.west < bbox.east):
                parser.error("--bbox order is SOUTH WEST NORTH EAST (south < north, west < east)")
        elif args.city in cfg.cities:
            bbox = cfg.cities[args.city].bbox
        else:
            parser.error(f"unknown city '{args.city}': add it to {args.config} or pass --bbox")
        keys = cfg.resolve_categories(args.categories)
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    settings = cfg.settings
    if args.output_dir:
        from dataclasses import replace
        settings = replace(settings, output_dir=args.output_dir)

    plan = plan_run(args.city, bbox, {k: cfg.categories[k] for k in keys}, settings,
                    step_km=args.step_km, max_cells=args.max_cells, center_first=args.center_first)
    log.info("%s: step %.2f km (%s), %d cells x %d categories = %d searches",
             plan.city_code, plan.step_km, "manual" if plan.step_is_manual else "automatic",
             len(plan.cells), len(plan.categories), plan.total_searches)
    if args.headless:
        log.warning("Headless mode: Google Maps hides most review counts from headless browsers, "
                    "so reviews_count will be mostly empty. Ratings and everything else are still collected.")
    if args.dry_run:
        return 0

    rows, path = run(plan, settings, headless=args.headless)
    if not rows:
        log.warning("No places collected: nothing to save.")
        return 1
    write_jsonl(rows, path)
    log.info("Saved %d places to %s", len(rows), path)
    return 0
