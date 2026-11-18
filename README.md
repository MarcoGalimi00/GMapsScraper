# GMapsScraper

Collect places of interest from Google Maps, one city and a chosen set of
categories at a time, and save them to an **Excel workbook**: one row per place,
keyed by Google's `place_id`, with rating and review count so places can be
ranked by popularity.

The scraper writes a JSONL file (one JSON object per line); the converter
`tools/jsonl_to_xlsx.py` turns it into the Excel file, which is the final output.

Cities and categories live in [`config.toml`](config.toml); you pick them at launch:

```bash
python -m gmaps_scraper --city milan --categories tourist_attraction museum
```

> **Before you use it.** Automated access to Google Maps may conflict with
> Google's Terms of Service. This project is for personal study: it searches at
> a human pace, never tries to bypass Google's anti-robot checks (it stops
> when one appears) and does not rotate IPs or disguise the browser. For
> production use, consider the official Google Places API.

## How it works, in one picture

```
config.toml ──► city rectangle ──► grid of search centres (e.g. Milan: 7 x 7 = 49)
                                          │
                     for each category × centre:  open Maps search ─► scroll the list ─► read cards
                                          │
                     parse each card ─► drop ads / out-of-area ─► de-duplicate by place_id
                                          │
                                raw/<city>_<YYYYmmdd_HHMM>.jsonl
                                          │
                     python -m tools.jsonl_to_xlsx ─► raw/<city>_<YYYYmmdd_HHMM>.xlsx   (final output)
```

Full walkthrough, from launch to clean row: [docs/how-it-works.md](docs/how-it-works.md).

## Install

Requires Python 3.11+.

```bash
git clone https://github.com/MarcoGalimi00/GMapsScraper.git && cd GMapsScraper
python3 -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

Development (tests): `pip install -r requirements-dev.txt`, then `pytest`.

## Run

A run has two steps: scrape, then convert to Excel.

```bash
python -m gmaps_scraper --city milan --categories tourist_attraction    # 1. scrape -> raw/milan_<time>.jsonl
python -m tools.jsonl_to_xlsx                                            # 2. newest JSONL -> raw/milan_<time>.xlsx
```

More ways to launch the scraper:

```bash
python -m gmaps_scraper --list                                   # cities, categories, groups in the config
python -m gmaps_scraper --city milan --categories tourist_attraction --max-cells 2 --center-first   # 2-search smoke test
python -m gmaps_scraper --city milan --categories @sights        # a group from the config
python -m gmaps_scraper --city milan --categories all            # every category
python -m gmaps_scraper --city milan --categories museum --dry-run   # show the plan, open nothing
python -m gmaps_scraper --city turin --bbox 45.00 7.60 45.14 7.75 --categories museum   # a city not in the config
```

| Option | Meaning |
|---|---|
| `--city CODE` | city from `[cities.CODE]` in the config (or any code together with `--bbox`) |
| `--categories …` | category keys, `@group` names, or `all` |
| `--bbox S W N E` | rectangle to use instead of the config's |
| `--headless` | hide the browser window — **review counts will be mostly missing** (see below) |
| `--max-cells N` | use only the first N grid cells (tests) |
| `--center-first` | start from the cells nearest to the centre |
| `--step-km K` | manual grid step instead of the automatic one |
| `--output-dir DIR` | where to write the JSONL (default `raw/`) |
| `--config FILE` | another configuration file |
| `--dry-run` | print the plan and exit |

### Visible window vs headless

The browser window is **visible by default**. In headless mode Google Maps
almost always labels the stars as `4.6 stars` instead of `4.6 stars 86,636 Reviews`,
so the review count — the popularity signal — is missing for most places
(11% had it in the headless Milan run). Ratings, categories and
everything else are still collected. On a Mac, keep the machine awake during
long runs:

```bash
caffeinate -i python -m gmaps_scraper --city milan --categories all
```

### How long does it take?

About 20–35 seconds per search (longer when the list is long). Number of
searches = cells × categories. Milan (49 cells): one category ≈ 20 minutes,
all 11 ≈ 4 h 20 min.

## Configure

```toml
[settings]            # zoom, window size, pauses, checkpoint frequency, output dir
zoom = 15
overlap = 0.85
...

[categories]          # our key = text typed in the Maps search box (English)
museum = "museum"
street_art = "street art"            # add any search you like

[category_groups]     # use as --categories @sights
sights = ["tourist_attraction", "museum", "art_gallery"]

[cities.milan]
name = "Milan, Italy"
bbox = { south = 45.39, west = 9.06, north = 45.54, east = 9.28 }
```

To add a city, generate its block:

```bash
python -m tools.find_city_bbox turin "Turin, Italy" --email you@example.com --radius-km 6
```

## Output

The final output is the Excel workbook made by `tools.jsonl_to_xlsx`:

- sheet **Places**: one row per place, most reviewed first, with filters and clickable Maps links;
- sheet **Summary**: how many places have a rating, a review count, a category, an image; counts per Google category and per search category.

Its columns come from the intermediate JSONL file: one JSON object per line in `raw/<city>_<YYYYmmdd_HHMM>.jsonl` (UTC time). While
running, `raw/<…>_partial.jsonl` is rewritten every `checkpoint_every` searches.

| Field | Example | Notes |
|---|---|---|
| `place_id` | `ChIJWUblrUjBhkcRtpP5ICHdu7g` | primary key |
| `name` | `Parco Sempione` | |
| `city_code` | `milan` | |
| `queries` | `["tourist_attraction", "park"]` | our categories that found it |
| `category` | `Tourist attraction` | Google's label, may be `null` |
| `rating` | `4.6` | may be `null` |
| `reviews_count` | `86636` | mostly `null` when scraped headless |
| `lat`, `lng` | `45.4721`, `9.1772` | |
| `maps_url` | `https://www.google.com/maps/place/…` | without session parameters |
| `feature_id` | `0x4786c148…:0xb8bbdd…` | Maps internal id |
| `image_url` | `https://lh3.googleusercontent.com/…` | thumbnail link only |
| `rating_label`, `card_text` | raw texts | kept so rows can be re-parsed |
| `last_scraped_at` | `2026-11-17T20:57:38+00:00` | |

## Tools

All run from the repository root:

| Command | What it does |
|---|---|
| `python -m tools.merge_jsonl raw/milan_*.jsonl --out raw/milan_merged.jsonl` | merge runs, one row per place |
| `python -m tools.reparse_jsonl FILE --out FILE2` | recompute category/rating/reviews from the raw texts, no scraping |
| `python -m tools.jsonl_to_xlsx [FILE]` | **final step**: Excel workbook, most reviewed first, plus a summary sheet (default: newest file in `raw/`) |
| `python -m tools.find_city_bbox CODE "City, Country" --email …` | `[cities.CODE]` block for the config |

## Project layout

```
gmaps_scraper/
  cli.py        command line, reads the config, prints the plan
  config.py     loads and validates config.toml
  geometry.py   rectangle -> grid of search centres, automatic step
  browser.py    Maps URL, cookies, anti-robot stop, scrolling, reading cards
  parsing.py    raw card -> clean row (pure Python, tested offline)
  scraper.py    category x cell loop, de-duplication, checkpoints
  storage.py    JSONL read/write/merge
tools/          merge, re-parse, Excel export, city rectangle
tests/          pytest, no browser or network needed
docs/           how-it-works.md, roadmap.md
config.toml     cities, categories, settings
```

## Known limits

- Maps lists stop at about **120 results per search**: in dense categories
  (parks, churches) a cell can hold more. See [docs/roadmap.md](docs/roadmap.md).
- `side_panel_px` and `overlap` are estimates, not measurements.
- Not resumable: a stopped run restarts from zero (the partial file keeps what was found).
- The page structure can change: if every search returns zero cards, check the selectors in `browser.py`.

## License

No license has been chosen yet: all rights reserved by the author.
