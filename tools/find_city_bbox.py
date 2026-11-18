"""Print a [cities.<code>] block for config.toml, centred on a city.

    python -m tools.find_city_bbox turin "Turin, Italy" --email you@example.com
    python -m tools.find_city_bbox venice "Venice, Italy" --radius-km 5 --email you@example.com
    python -m tools.find_city_bbox las_vegas "Las Vegas, USA" --center 36.12 -115.17   # no lookup

The centre comes from Nominatim, OpenStreetMap's free geocoder. Its usage policy
(https://operations.osmfoundation.org/policies/nominatim/) asks for at most one
request per second and a User-Agent that identifies you: hence --email.
The rectangle is +/- radius km around the centre. Check it on a map: the
geocoder's point is the administrative centre, which is not always the tourist one.
"""
import argparse
import math

KM_PER_DEG = 111.0
URL = "https://nominatim.openstreetmap.org/search"


def bbox_around(lat: float, lng: float, radius_km: float) -> tuple[float, float, float, float]:
    """(south, west, north, east) of a square of +/- radius_km around a point.
    The longitude span is wider than the latitude span: 1 degree of longitude is
    111 km x cos(latitude)."""
    dlat = radius_km / KM_PER_DEG
    dlng = radius_km / (KM_PER_DEG * math.cos(math.radians(lat)))
    return round(lat - dlat, 4), round(lng - dlng, 4), round(lat + dlat, 4), round(lng + dlng, 4)


def geocode(query: str, email: str) -> tuple[float, float, str]:
    import requests

    r = requests.get(URL, params={"q": query, "format": "jsonv2", "limit": 1},
                     headers={"User-Agent": f"gmaps-places-scraper/0.2 ({email})"}, timeout=30)
    r.raise_for_status()
    results = r.json()
    if not results:
        raise SystemExit(f"Nominatim found nothing for '{query}'")
    return float(results[0]["lat"]), float(results[0]["lon"]), results[0]["display_name"]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("code", help="short code used with --city, e.g. turin")
    ap.add_argument("query", help='text to geocode, with the country, e.g. "Turin, Italy"')
    ap.add_argument("--radius-km", type=float, default=8.0, help="half side of the square (default 8)")
    ap.add_argument("--center", nargs=2, type=float, metavar=("LAT", "LNG"), help="skip the lookup, use this centre")
    ap.add_argument("--email", help="your contact, required by Nominatim's policy when looking up")
    args = ap.parse_args()

    if args.center:
        lat, lng, label = *args.center, "manual centre"
    else:
        if not args.email:
            ap.error("--email is required for a Nominatim lookup (or pass --center)")
        lat, lng, label = geocode(args.query, args.email)
    s, w, n, e = bbox_around(lat, lng, args.radius_km)
    print(f"# {label}  (centre {lat:.4f}, {lng:.4f}, +/- {args.radius_km:g} km)")
    print(f"[cities.{args.code}]")
    print(f'name = "{args.query}"')
    print(f"bbox = {{ south = {s}, west = {w}, north = {n}, east = {e} }}")


if __name__ == "__main__":
    main()
