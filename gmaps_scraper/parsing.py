"""From a raw card (what the browser read) to a clean row.

Pure Python, no browser: every function here can be tested offline on a card
written by hand (see tests/test_parsing.py) and re-run on old JSONL files
(see tools/reparse_jsonl.py), because the raw `card_text` is always saved.
"""
from __future__ import annotations

import logging
import re

from .geometry import BBox

log = logging.getLogger("gmaps")

# The link of every card already holds the most valuable data:
#   .../maps/place/<name>/data=...!1s0x47..:0x1b..!8m2!3d45.4718!4d9.1881...!19sChIJ...
#   !1s  = Maps internal id    !3d / !4d = latitude / longitude    !19s = place_id
PLACE_ID_RE = re.compile(r"!19s([\w-]+)")
FEATURE_ID_RE = re.compile(r"!1s(0x[0-9a-f]+:0x[0-9a-f]+)")
LAT_RE = re.compile(r"!3d(-?\d+(?:\.\d+)?)")
LNG_RE = re.compile(r"!4d(-?\d+(?:\.\d+)?)")
IMAGE_HOST_RE = re.compile(r"^https://lh\d\.googleusercontent\.com/")

# The rating line inside card_text. Two shapes are seen, both followed by a star icon
# (a private-use character such as , i.e. not a letter or digit):
#   "4.6(3,578)"   -> rating 4.6, 3578 reviews
#   "4.7"          -> rating only (e.g. when the page is rendered headless)
# Places without reviews show "No reviews" instead.
RATING_LINE_RE = re.compile(r"^(\d[.,]\d)(?:\s*\(([\d,.]+)\))?\W*$|^No reviews", re.IGNORECASE)

# Opening-hours lines: "Open 24 hours", "Closed · Opens 10 AM", "Closes soon"...
# Careful: "Open air museum" is a category, not opening hours.
HOURS_LINE_RE = re.compile(
    r"^(Open|Closed)(\s*·|\s+24 hours|\s*$)|^(Closes|Opens|Temporarily closed|Permanently closed)",
    re.IGNORECASE,
)

# The `aria-label` of the stars element. Two shapes:
#   "4.6 stars 86,636 Reviews"   (visible window)
#   "4.6 stars"                  (headless, almost always: no review count)
# (?: ... )? makes the review block optional; group 2 is then None.
RATING_LABEL_RE = re.compile(r"(\d[.,]\d)\s+stars?(?:\s+([\d,]+)\s+Reviews?)?", re.IGNORECASE)


def parse_rating(rating_label: str | None, card_text: str | None) -> tuple[float | None, int | None]:
    """Return (rating, reviews_count); either can be None.

    Sources, in order of preference:
      1. rating_label  -> the aria-label of the stars, e.g. "4.6 stars 86,636 Reviews"
      2. card_text     -> the visible rating line, e.g. "4.6(3,578)" or "4.7"
    The review count is an int without thousands separators (86636), or None when absent.
    """
    # 1. aria-label of the stars: "4.6 stars 86,636 Reviews" or "4.6 stars"
    m = RATING_LABEL_RE.search(rating_label or "")
    # 2. fallback: the rating line inside card_text: "4.6(3,578)" or "4.6"
    if m is None:
        for line in (card_text or "").split("\n"):
            m = RATING_LINE_RE.match(line.strip())
            if m and m.group(1):          # group(1) is None on the "No reviews" line
                break
            m = None
    if m is None:
        return None, None
    rating = float(m.group(1).replace(",", "."))
    reviews = int(m.group(2).replace(",", "").replace(".", "")) if m.group(2) else None
    return rating, reviews


def extract_category(card_text: str) -> str | None:
    """Google's category ("Art museum") is the part before the first '·' on the
    first line that has one, skipping the name, the rating line and opening hours.
    Example card_text lines:
        Pinacoteca di Brera                 <- name (first line, skipped)
        4.7                                 <- rating line, skipped
        Tourist attraction · · Via Brera, 28   <- category = "Tourist attraction"
        Open · Closes 7:15 PM               <- hours, skipped
    """
    lines = [ln.strip() for ln in card_text.split("\n") if ln.strip()]
    for line in lines[1:]:
        if RATING_LINE_RE.match(line) or HOURS_LINE_RE.match(line):
            continue
        if "·" in line:
            return line.split("·")[0].strip() or None
    return None


def parse_card(card: dict, city_code: str, query_key: str, bbox: BBox) -> dict | None:
    """Turn ONE raw card into a row, or None when it must be dropped.

    `card` comes from EXTRACT_JS (browser.py) and has the keys:
    name, href, sponsored, rating_label, image_src, card_text.
    """
    href = card.get("href") or ""                 # regexes need a string, never None
    place_id = PLACE_ID_RE.search(href)
    lat, lng = LAT_RE.search(href), LNG_RE.search(href)

    if card.get("sponsored"):
        return None       # ads can be off-topic or out of area; good places show up anyway
    if not (place_id and lat and lng):
        log.warning("Card without place_id/coordinates, skipped: %s", card.get("name"))
        return None
    lat_f, lng_f = float(lat.group(1)), float(lng.group(1))
    if not bbox.contains(lat_f, lng_f):
        return None       # Maps also returns places outside the searched area

    card_text = card.get("card_text") or ""
    rating, reviews = parse_rating(card.get("rating_label"), card_text)
    feature = FEATURE_ID_RE.search(href)
    src = card.get("image_src") or ""
    return {
        "place_id": place_id.group(1),
        "name": card.get("name"),
        "city_code": city_code,
        "queries": [query_key],
        "category": extract_category(card_text),
        "rating": rating,
        "reviews_count": reviews,
        "lat": lat_f,
        "lng": lng_f,
        "maps_url": href.split("?")[0],               # drop session parameters
        "feature_id": feature.group(1) if feature else None,
        "image_url": src if IMAGE_HOST_RE.match(src) else None,   # drop data:image placeholders
        "rating_label": card.get("rating_label"),     # raw, so ratings can be re-parsed later
        "card_text": card.get("card_text"),           # raw, so everything can be re-parsed later
    }


def reparse_row(row: dict) -> dict:
    """Recompute the derived fields of an already saved row from its raw fields.
    Used by tools/reparse_jsonl.py: no browser, no new scraping."""
    card_text = row.get("card_text") or ""
    rating, reviews = parse_rating(row.get("rating_label"), card_text)
    return {**row, "category": extract_category(card_text), "rating": rating, "reviews_count": reviews}
