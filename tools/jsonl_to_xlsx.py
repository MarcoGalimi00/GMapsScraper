"""Turn a JSONL file of the scraper into an Excel workbook to browse and filter.

    python -m tools.jsonl_to_xlsx                         # newest file in raw/
    python -m tools.jsonl_to_xlsx raw/milan_merged.jsonl --out milan.xlsx

Sheets: "Places" (one row per place, sorted by reviews_count) and "Summary"
(counts per Google category and per search category).
"""
import argparse
import collections
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from gmaps_scraper.storage import read_jsonl

# (JSON key, column title, width in characters)
COLUMNS = [
    ("name", "Name", 38),
    ("category", "Google category", 22),
    ("queries", "Found by", 26),
    ("rating", "Rating", 7),
    ("reviews_count", "Reviews", 10),
    ("lat", "Lat", 11),
    ("lng", "Lng", 11),
    ("maps_url", "Maps", 9),
    ("image_url", "Image", 9),
    ("city_code", "City", 9),
    ("place_id", "place_id", 30),
    ("feature_id", "feature_id", 28),
    ("last_scraped_at", "Scraped at", 20),
    ("card_text", "Card text", 50),
]
LINK_COLUMNS = {"maps_url", "image_url"}


def cell_value(row: dict, key: str):
    v = row.get(key)                              # .get: older files may miss a column
    if isinstance(v, list):
        return ", ".join(str(x) for x in v)       # ["museum", "park"] -> "museum, park"
    if key == "card_text" and v:
        return v.replace("\n", " | ")[:300]       # Excel dislikes long multi-line text
    return v


def write_places(ws, rows: list[dict]) -> None:
    header_fill = PatternFill("solid", start_color="DDEBF7")
    ws.append([title for _, title, _ in COLUMNS])
    for c in ws[1]:
        c.font, c.fill, c.alignment = Font(bold=True), header_fill, Alignment(vertical="center")
    for r in sorted(rows, key=lambda r: r.get("reviews_count") or -1, reverse=True):   # most reviewed first
        ws.append([cell_value(r, key) for key, _, _ in COLUMNS])
    for i, (key, _, width) in enumerate(COLUMNS, start=1):
        ws.column_dimensions[get_column_letter(i)].width = width
        if key in LINK_COLUMNS:
            for n in range(2, ws.max_row + 1):
                c = ws.cell(row=n, column=i)
                if c.value:
                    c.hyperlink, c.value = c.value, "open"
                    c.font = Font(color="0563C1", underline="single")
    ws.freeze_panes = "B2"
    ws.auto_filter.ref = ws.dimensions


def write_summary(ws, rows: list[dict]) -> None:
    def block(title, counts, top_row, col):
        ws.cell(row=top_row, column=col, value=title).font = Font(bold=True)
        for n, (key, count) in enumerate(counts.most_common(), start=1):
            ws.cell(row=top_row + n, column=col, value=key if key is not None else "(empty)")
            ws.cell(row=top_row + n, column=col + 1, value=count)

    stats = [("Places", len(rows)),
             ("With rating", sum(1 for r in rows if r.get("rating") is not None)),
             ("With review count", sum(1 for r in rows if r.get("reviews_count") is not None)),
             ("With Google category", sum(1 for r in rows if r.get("category"))),
             ("With image", sum(1 for r in rows if r.get("image_url")))]
    for i, (label, value) in enumerate(stats, start=1):
        ws.cell(row=i, column=1, value=label).font = Font(bold=True)
        ws.cell(row=i, column=2, value=value)
    block("Google category", collections.Counter(r.get("category") for r in rows), 8, 1)
    block("Found by (our search)", collections.Counter(q for r in rows for q in (r.get("queries") or [])), 8, 4)
    ws.column_dimensions["A"].width = 34
    ws.column_dimensions["D"].width = 24


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("jsonl", nargs="?", type=Path, help="JSONL file (default: newest in raw/)")
    ap.add_argument("--out", type=Path, help=".xlsx path (default: next to the JSONL)")
    args = ap.parse_args()

    if args.jsonl is None:
        found = sorted(Path("raw").glob("*.jsonl"), key=lambda p: p.stat().st_mtime)
        if not found:
            ap.error("no file in raw/: run the scraper first or pass a file")
        args.jsonl = found[-1]                     # newest by modification time, not by name
    rows = read_jsonl(args.jsonl)
    if not rows:
        ap.error(f"{args.jsonl} is empty")

    wb = Workbook()
    wb.active.title = "Places"
    write_places(wb.active, rows)
    write_summary(wb.create_sheet("Summary"), rows)
    out = args.out or args.jsonl.with_suffix(".xlsx")
    wb.save(out)
    print(f"{len(rows)} places -> {out}")


if __name__ == "__main__":
    main()
