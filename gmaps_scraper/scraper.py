"""Orchestration: grid x categories, de-duplication, checkpoints."""
from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .browser import BlockedError, build_url, scrape_search
from .config import Settings
from .geometry import BBox, auto_step_km, order_center_first
from .parsing import parse_card
from .storage import run_paths, write_jsonl

log = logging.getLogger("gmaps")


@dataclass(frozen=True)
class RunPlan:
    """Everything one run needs, decided before the browser opens."""
    city_code: str
    bbox: BBox
    categories: dict[str, str]          # key -> search text, in the order they will run
    cells: list[tuple[float, float]]
    step_km: float
    step_is_manual: bool

    @property
    def total_searches(self) -> int:
        return len(self.cells) * len(self.categories)


def plan_run(city_code: str, bbox: BBox, categories: dict[str, str], settings: Settings,
             step_km: float | None = None, max_cells: int | None = None,
             center_first: bool = False) -> RunPlan:
    step = step_km or auto_step_km(bbox.mid_lat, settings.zoom, settings.viewport,
                                   settings.side_panel_px, settings.overlap)
    cells = bbox.grid_centers(step)
    if center_first:
        cells = order_center_first(cells, bbox)
    return RunPlan(city_code, bbox, categories, cells[:max_cells], step, step_km is not None)


def run(plan: RunPlan, settings: Settings, headless: bool) -> tuple[list[dict], Path]:
    """Run every (category, cell) search and return (places, final file path).

    Places are kept in a dict keyed by place_id: the same place found by ten
    cells or three categories is stored once, and its `queries` list grows.
    """
    from playwright.sync_api import sync_playwright

    started = datetime.now(timezone.utc)
    final_path, partial_path = run_paths(settings.output_dir, plan.city_code, started)
    rows: dict[str, dict] = {}
    done = 0
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless)
        context = browser.new_context(locale="en-US", viewport=settings.viewport)
        page = context.new_page()
        try:
            for key, text in plan.categories.items():
                for lat, lng in plan.cells:
                    cards = scrape_search(page, build_url(text, lat, lng, settings.zoom), settings)
                    new = 0
                    for card in cards:
                        row = parse_card(card, plan.city_code, key, plan.bbox)
                        if row is None:
                            continue
                        existing = rows.get(row["place_id"])
                        if existing is None:
                            rows[row["place_id"]] = row
                            new += 1
                        elif key not in existing["queries"]:
                            existing["queries"].append(key)
                    done += 1
                    log.info("[%d/%d] %-20s @%.4f,%.4f  cards=%d  new=%d  total=%d",
                             done, plan.total_searches, key, lat, lng, len(cards), new, len(rows))
                    if done % settings.checkpoint_every == 0:
                        write_jsonl(list(rows.values()), partial_path)
                    time.sleep(random.uniform(*settings.page_pause_s))
        except (BlockedError, KeyboardInterrupt) as exc:
            # Anti-robot page or Ctrl+C: keep what was collected so far.
            log.error("Interrupted (%s). Keeping the %d places collected so far.", exc or "Ctrl+C", len(rows))
        finally:
            browser.close()
    return list(rows.values()), final_path
