# How it works: from the command to a clean row

Read the code in the order Python runs it, not top to bottom. Each step states
the general rule first, then an **example on Milan** with real numbers.

```
1 Prepare ─► 2 Browser ─► [ 3 URL ─► 4 Read page ─► 5 Parse ─► 6 De-duplicate ─► 7 Log/checkpoint ] ─► 8 Save
                              └──────────────── repeated for every category × cell ─────────────┘
```

## 1. Prepare (`cli.py`, `config.py`, `scraper.plan_run`)

`main()` parses the options, `load_config()` reads `config.toml` and validates it
(unknown keys, south > north, unknown categories all fail before any browser
opens). `resolve_categories()` turns `museum @green all` into a list of keys.
`plan_run()` computes the step, the grid and the number of searches.

**Example on Milan** — `--city milan --categories all`: 49 cells × 11 categories = 539 searches.

### The automatic step (`geometry.auto_step_km`)

1. Metres per pixel = `156543.03 × cos(lat) / 2^zoom`.
2. Visible map = `(window width − side panel) × m/px` by `window height × m/px`.
3. Step = `overlap × short side`.

`overlap` is how far the centre moves from one cell to the next, as a fraction
of the visible short side. With 1.0 neighbouring cells just touch, and any error
in the estimate leaves a gap; with 0.85 they share 15%.

**Example on Milan** (lat 45.465, zoom 15, 1280×900 window): 3.35 m/px, visible
area 2.92 × 3.02 km, step = 0.85 × 2.92 = **2.48 km**. Two neighbouring cells
share 2.92 − 2.48 = 0.45 km. Overlap 1.0 would give 36 cells, 0.7 would give 81.

| City | Latitude | Automatic step |
|---|---|---|
| Singapore | 1.29 | 3.54 km |
| Rome | 41.89 | 2.64 km |
| Milan | 45.465 | 2.48 km |
| Stockholm | 59.33 | 1.81 km |

### The grid (`BBox.grid_centers`)

`dlat = step / 111`, `dlng = step / (111 × cos(mid lat))`. The first centre sits
half a step inside the south-west corner; two `while` loops add rows and columns
while the centre stays inside the rectangle (+ half a step).

**Example on Milan**: the rectangle is 0.15° × 111 = 16.7 km tall and
0.22° × 111 × cos(45.465°) = 17.1 km wide. 16.7 / 2.48 ≈ 6.7 and
17.1 / 2.48 ≈ 6.9 → 7 rows × 7 columns = **49 cells**, from (45.40117, 9.07593)
to (45.53523, 9.26707). With `--center-first` the first cell becomes (45.4682, 9.1715).

## 2. Open the browser (`scraper.run`)

One Chromium, one context (`locale="en-US"`, fixed viewport), one page, reused
for every search. The window is visible unless `--headless` is passed: headless
pages omit review counts (section 5).

## 3. Build the URL (`browser.build_url`)

`https://www.google.com/maps/search/<text>/@<lat>,<lng>,<zoom>z?hl=en` — the text
comes from `[categories]`, the point from the grid. `hl=en` keeps the page in
English so the parser always sees the same words.

**Example on Milan**: `…/maps/search/art+gallery/@45.4642,9.19,15z?hl=en`.

## 4. Read the page (`browser.scrape_search`)

1. `page.goto(url, wait_until="domcontentloaded")`.
2. `handle_consent`: on `consent.google.com`, click "Reject all".
3. `check_blocked`: on `/sorry/`, raise `BlockedError` — the run stops and saves; no bypass.
4. Wait for `div[role="feed"]`; if it never appears (zero or one result) return `[]`.
5. `scroll_to_end`: scroll the feed until "You've reached the end of the list",
   or the card count stops growing `stall_limit` times, or `max_scrolls` is reached.
6. `EXTRACT_JS` runs inside the page and returns, per card: `name`, `href`,
   `sponsored`, `rating_label` (aria-label of the stars), `image_src`, `card_text`.

**Example on Milan**: lists hold 16–111 cards for `tourist_attraction`, but stop
at 120–122 for dense categories such as `park` — the per-search cap.

## 5. Parse (`parsing.parse_card`)

A raw card (example built in the same shape as real cards):

```python
{"name": "Pinacoteca di Brera",
 "href": "https://www.google.com/maps/place/Pinacoteca+di+Brera/data=…!1s0x4786…:0x1a2b…!8m2!3d45.4718!4d9.1881!19sChIJexample?authuser=0",
 "sponsored": False,
 "rating_label": "4.7 stars 35,872 Reviews",
 "card_text": "Pinacoteca di Brera\nPinacoteca di Brera\n4.7\nTourist attraction · · Via Brera, 28\nOpen · Closes 7:15 PM"}
```

| Field | Source | Rule |
|---|---|---|
| `place_id` | `href` | after `!19s` |
| `lat`, `lng` | `href` | after `!3d` / `!4d` |
| `feature_id` | `href` | after `!1s` |
| `rating`, `reviews_count` | `rating_label`, else `card_text` | `parse_rating` |
| `category` | `card_text` | `extract_category` |
| `maps_url` | `href` | text before `?` |
| `image_url` | `image_src` | only `lh*.googleusercontent.com` links |

Cards are dropped when sponsored, without `place_id`/coordinates (logged), or outside the rectangle.

### Rating and reviews (`parse_rating`)

Two sources, in order:

1. `rating_label`: `4.6 stars 86,636 Reviews` (visible window) or, almost always, `4.6 stars` (headless).
2. `card_text`, the visible rating line: `4.6(3,578)` or `4.6`, followed by a star icon.

The review count only exists when the page shows it, so `reviews_count` is
mostly `None` for headless runs (11% of places had it in the headless Milan run).

### Category (`extract_category`)

The first line containing `·`, skipping the name, the rating line ("4.7",
"4.6(3,578)", "No reviews") and opening hours ("Open 24 hours", "Closed · Opens 10 AM").
"Open air museum" is a category, not hours. Places whose card has no such line
get `None`.

**Example on Milan**: on 4,639 places, 82% get a category and 70% a rating from
the saved card texts.

## 6. De-duplicate (`scraper.run`)

`rows` is a dict keyed by `place_id`. A new place is inserted (`new += 1`); a known
place found by another category only gets that category appended to `queries`.

| Event | `queries` |
|---|---|
| first seen by `museum`, cell 1 | `["museum"]` |
| `museum` again, cell 5 | `["museum"]` |
| `art_gallery`, cell 9 | `["museum", "art_gallery"]` |

## 7. Log, checkpoint, pause

Every search logs one line:

```
[2/539] tourist_attraction   @45.4012,9.1078  cards=56  new=6  total=56
```

Every `checkpoint_every` searches the whole of `rows` is rewritten to
`<city>_<time>_partial.jsonl`; then a random pause in `page_pause_s`.

## 8. Save, then convert to Excel

When the loop ends — or on Ctrl+C, or on `/sorry/` — the browser closes and
`write_jsonl` writes `<city>_<time>.jsonl`, stamping `last_scraped_at`. Any other
exception leaves only the last partial file.

Then the converter turns the JSONL into the final Excel workbook:

```bash
python -m tools.jsonl_to_xlsx raw/milan_20261117_2057.jsonl   # -> raw/milan_20261117_2057.xlsx
```

Sheet "Places" has one row per place, most reviewed first; sheet "Summary" counts
ratings, review counts, categories and images.

**Example on Milan** (17 Nov 2026, all 11 categories): 539 searches in 4 h 19 min
(~29 s each), 4,631 places, no anti-robot check.

## Function index

| Function | Module | Called by | Returns |
|---|---|---|---|
| `main` | cli | `python -m gmaps_scraper` | exit code |
| `load_config` | config | `main` | `Config` |
| `Config.resolve_categories` | config | `main` | category keys |
| `plan_run` | scraper | `main` | `RunPlan` |
| `auto_step_km` | geometry | `plan_run` | step in km |
| `BBox.grid_centers` | geometry | `plan_run` | list of (lat, lng) |
| `order_center_first` | geometry | `plan_run` | sorted cells |
| `run` | scraper | `main` | (rows, path) |
| `build_url` | browser | `run` | URL |
| `scrape_search` | browser | `run` | raw cards |
| `handle_consent`, `check_blocked`, `scroll_to_end` | browser | `scrape_search` | — |
| `parse_card` | parsing | `run` | row or `None` |
| `parse_rating`, `extract_category` | parsing | `parse_card`, `reparse_row` | values |
| `write_jsonl`, `read_jsonl`, `merge_rows` | storage | `main`, `run`, tools | — |
