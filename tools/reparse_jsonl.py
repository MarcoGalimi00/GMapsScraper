"""Recompute category, rating and reviews_count of saved rows, without scraping again.

    python -m tools.reparse_jsonl raw/milan_merged.jsonl --out raw/milan_reparsed.jsonl

Works because every row keeps its raw `card_text` (and, in newer files, `rating_label`).
Use it after improving the parser in gmaps_scraper/parsing.py.
"""
import argparse
from pathlib import Path

from gmaps_scraper.parsing import reparse_row
from gmaps_scraper.storage import read_jsonl, write_jsonl


def share(rows: list[dict], field: str) -> str:
    n = sum(1 for r in rows if r.get(field) is not None)
    return f"{field}: {n}/{len(rows)} ({n / len(rows):.0%})" if rows else f"{field}: 0/0"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("file", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    before = read_jsonl(args.file)
    after = [reparse_row(r) for r in before]
    write_jsonl(after, args.out, stamp=False)
    for field in ("category", "rating", "reviews_count"):
        print(f"  before {share(before, field):40}  after {share(after, field)}")
    print(f"{len(after)} rows -> {args.out}")


if __name__ == "__main__":
    main()
