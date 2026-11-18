"""JSONL files: one JSON object per line, one line per place."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_jsonl(rows: list[dict], path: Path, stamp: bool = True) -> None:
    """Write (overwrite) `rows`. With stamp=True every row gets `last_scraped_at` = now (UTC)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            out = {**row, "last_scraped_at": now} if stamp else row
            f.write(json.dumps(out, ensure_ascii=False) + "\n")


def run_paths(output_dir: Path, city_code: str, started: datetime) -> tuple[Path, Path]:
    """File names of one run: <city>_<YYYYmmdd_HHMM>.jsonl and the same with _partial.
    The time is UTC, so names sort the same way on every machine."""
    base = f"{city_code}_{started:%Y%m%d_%H%M}"
    return output_dir / f"{base}.jsonl", output_dir / f"{base}_partial.jsonl"


def merge_rows(batches: list[list[dict]]) -> list[dict]:
    """Merge rows from several runs into one row per place_id.

    The `queries` lists are united; every other field comes from the row with the
    most recent `last_scraped_at` (ISO strings compare correctly as text).
    """
    merged: dict[str, dict] = {}
    for rows in batches:
        for row in rows:
            old = merged.get(row["place_id"])
            if old is None:
                merged[row["place_id"]] = {**row, "queries": list(row.get("queries") or [])}
                continue
            queries = list(dict.fromkeys((old.get("queries") or []) + (row.get("queries") or [])))
            newest = row if (row.get("last_scraped_at") or "") >= (old.get("last_scraped_at") or "") else old
            merged[row["place_id"]] = {**newest, "queries": queries}
    return list(merged.values())
