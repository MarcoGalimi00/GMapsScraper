"""Add a city to config.toml (or update it), centred on a point.

    python -m tools.add_city turin "Turin, Italy" --email you@example.com
    python -m tools.add_city venice "Venice, Italy" --radius-km 5 --email you@example.com
    python -m tools.add_city las_vegas "Las Vegas, USA" --center 36.12 -115.17      # no lookup
    python -m tools.add_city milan "Milan, Italy" --radius-km 6 --replace --email ...  # overwrite
    python -m tools.add_city turin "Turin, Italy" --email ... --dry-run              # print, write nothing

The centre comes from Nominatim, OpenStreetMap's free geocoder. Its usage policy
(https://operations.osmfoundation.org/policies/nominatim/) asks for at most one
request per second and a User-Agent that identifies you: hence --email.

The block written to config.toml is:

    [cities.turin]
    name = "Turin, Italy"
    center = [45.0677, 7.6825]
    radius_km = 8

and the scraper turns it into the square of +/- radius_km around the centre.
The geocoder's point is the administrative centre, not always the tourist one:
check it on a map and, if needed, edit `center` by hand or pass --center.
"""
import argparse
import re
from pathlib import Path

from gmaps_scraper.config import load_config
from gmaps_scraper.geometry import auto_step_km, bbox_around

URL = "https://nominatim.openstreetmap.org/search"


def city_block(code: str, name: str, lat: float, lng: float, radius_km: float, note: str = "") -> str:
    """The TOML text of one [cities.<code>] table."""
    comment = f"   # {note}" if note else ""
    return (f"[cities.{code}]\n"
            f'name = "{name}"\n'
            f"center = [{lat:.4f}, {lng:.4f}]{comment}\n"
            f"radius_km = {radius_km:g}\n")


def upsert_city_block(text: str, code: str, block: str, replace: bool = False) -> str:
    """Return `text` with `block` appended, or swapped in place of an existing
    [cities.<code>] table when replace=True. Everything else, comments included,
    is left exactly as it was."""
    header = re.compile(rf"^\[cities\.{re.escape(code)}\][ \t]*$", re.MULTILINE)
    found = header.search(text)
    if found is None:
        return text.rstrip("\n") + "\n\n" + block
    if not replace:
        raise ValueError(f"[cities.{code}] already exists: use --replace to overwrite it")
    nxt = re.compile(r"^\[", re.MULTILINE).search(text, found.end())   # next table, or end of file
    end = nxt.start() if nxt else len(text)
    tail = text[end:]
    return text[:found.start()] + block + ("\n" + tail if tail else "")


def geocode(query: str, email: str) -> tuple[float, float, str]:
    import requests

    r = requests.get(URL, params={"q": query, "format": "jsonv2", "limit": 1},
                     headers={"User-Agent": f"GMapsScraper/0.2 ({email})"}, timeout=30)
    r.raise_for_status()
    results = r.json()
    if not results:
        raise SystemExit(f"Nominatim found nothing for '{query}'")
    return float(results[0]["lat"]), float(results[0]["lon"]), results[0]["display_name"]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("code", help="short code used with --city, e.g. turin")
    ap.add_argument("query", help='city name with the country, e.g. "Turin, Italy"')
    ap.add_argument("--radius-km", type=float, default=8.0, help="half side of the square (default 8)")
    ap.add_argument("--center", nargs=2, type=float, metavar=("LAT", "LNG"), help="skip the lookup, use this centre")
    ap.add_argument("--email", help="your contact, required by Nominatim's policy when looking up")
    ap.add_argument("--config", type=Path, default=Path("config.toml"))
    ap.add_argument("--replace", action="store_true", help="overwrite the city if it is already in the config")
    ap.add_argument("--dry-run", action="store_true", help="print the block, do not write the config")
    args = ap.parse_args()

    if not re.fullmatch(r"[a-z0-9_]+", args.code):
        ap.error("code: lowercase letters, digits and _ only (e.g. new_york)")
    if args.center:
        lat, lng = args.center
        found = "manual centre"
    else:
        if not args.email:
            ap.error("--email is required for a Nominatim lookup (or pass --center)")
        lat, lng, found = geocode(args.query, args.email)

    block = city_block(args.code, args.query, lat, lng, args.radius_km)
    box = bbox_around(lat, lng, args.radius_km)
    cfg = load_config(args.config)
    s = cfg.settings
    cells = len(box.grid_centers(auto_step_km(box.mid_lat, s.zoom, s.viewport, s.side_panel_px, s.overlap)))
    print(f"# {found}\n# {cells} cells at the automatic step\n{block}")
    if args.dry_run:
        return
    text = args.config.read_text(encoding="utf-8")
    try:
        new_text = upsert_city_block(text, args.code, block, args.replace)
    except ValueError as exc:
        ap.error(str(exc))
    args.config.write_text(new_text, encoding="utf-8")
    load_config(args.config)                        # fail loudly if the result is not valid
    print(f"written to {args.config}. Try: python -m gmaps_scraper --city {args.code} --categories tourist_attraction --dry-run")


if __name__ == "__main__":
    main()
