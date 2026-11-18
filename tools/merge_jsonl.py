"""Merge several JSONL files of the scraper into one, one row per place_id.

    python -m tools.merge_jsonl raw/milan_*.jsonl --out raw/milan_merged.jsonl

Typical use: a test run, a partial file and a full run of the same city.
`queries` lists are united; the other fields come from the most recent row.
"""
import argparse
from pathlib import Path

from gmaps_scraper.storage import merge_rows, read_jsonl, write_jsonl


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("files", nargs="+", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    batches = [read_jsonl(f) for f in args.files]
    for f, rows in zip(args.files, batches):
        print(f"  {f}: {len(rows)} rows")
    merged = merge_rows(batches)
    write_jsonl(merged, args.out, stamp=False)        # keep each row's own last_scraped_at
    print(f"{len(merged)} unique places -> {args.out}")


if __name__ == "__main__":
    main()
