"""From a city rectangle to a grid of search centres.

One Maps search only shows a small area, so a city is covered by many searches
around different points. Two facts drive every formula here:

* one degree of latitude is always ~111 km;
* one degree of longitude is 111 km x cos(latitude): meridians get closer
  away from the equator.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

KM_PER_DEG_LAT = 111.0


@dataclass(frozen=True)
class BBox:
    """Geographic rectangle in decimal degrees.
    Rectangles crossing the antimeridian (180 degrees) are not supported."""

    south: float
    west: float
    north: float
    east: float

    @property
    def mid_lat(self) -> float:
        return (self.south + self.north) / 2

    def contains(self, lat: float, lng: float) -> bool:
        return self.south <= lat <= self.north and self.west <= lng <= self.east

    def grid_centers(self, step_km: float) -> list[tuple[float, float]]:
        """Centres of a regular grid covering the rectangle, south-west first.

        The first centre sits HALF a step inside the rectangle, so every cell
        covers half a step on each side of its centre. Rows and columns are added
        while the centre is still inside the rectangle (plus half a step).
        Example: Milan (16.7 x 17.1 km) with a 2.48 km step -> 7 x 7 = 49 centres.
        """
        dlat = step_km / KM_PER_DEG_LAT
        dlng = step_km / (KM_PER_DEG_LAT * math.cos(math.radians(self.mid_lat)))
        centers = []
        lat = self.south + dlat / 2
        while lat < self.north + dlat / 2:
            lng = self.west + dlng / 2
            while lng < self.east + dlng / 2:
                centers.append((round(lat, 5), round(lng, 5)))
                lng += dlng
            lat += dlat
        return centers


def bbox_around(lat: float, lng: float, radius_km: float) -> BBox:
    """Square of +/- radius_km around a point. The longitude span is wider than the
    latitude span, because one degree of longitude is 111 km x cos(latitude)."""
    dlat = radius_km / KM_PER_DEG_LAT
    dlng = radius_km / (KM_PER_DEG_LAT * math.cos(math.radians(lat)))
    return BBox(round(lat - dlat, 4), round(lng - dlng, 4), round(lat + dlat, 4), round(lng + dlng, 4))


def meters_per_pixel(lat: float, zoom: int) -> float:
    """Standard web-map formula: size of one screen pixel on the ground."""
    return 156543.03 * math.cos(math.radians(lat)) / 2**zoom


def auto_step_km(lat: float, zoom: int, viewport: dict, side_panel_px: int, overlap: float) -> float:
    """Grid step derived from what one search can actually see.

    Visible map = window minus the results panel on the left. The step is a
    fraction (`overlap`) of the SHORT side: with 0.85 two neighbouring cells
    share 15% of their area, a safety margin against gaps.
    """
    m_px = meters_per_pixel(lat, zoom)
    visible_w_km = (viewport["width"] - side_panel_px) * m_px / 1000
    visible_h_km = viewport["height"] * m_px / 1000
    return round(overlap * min(visible_w_km, visible_h_km), 2)


def order_center_first(cells: list[tuple[float, float]], bbox: BBox) -> list[tuple[float, float]]:
    """Sort cells by distance from the rectangle centre (Pythagoras in km).
    Useful for short tests (--max-cells): the centre is more interesting than a corner."""
    c_lat, c_lng = bbox.mid_lat, (bbox.west + bbox.east) / 2
    km_lng = KM_PER_DEG_LAT * math.cos(math.radians(c_lat))
    return sorted(cells, key=lambda c: math.hypot((c[0] - c_lat) * KM_PER_DEG_LAT, (c[1] - c_lng) * km_lng))
