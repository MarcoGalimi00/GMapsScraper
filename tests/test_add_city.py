import pytest

from gmaps_scraper.geometry import bbox_around
from tools.add_city import city_block, upsert_city_block

CONFIG = """[categories]
museum = "museum"

# Cities
[cities.milan]
name = "Milan, Italy"
bbox = { south = 45.39, west = 9.06, north = 45.54, east = 9.28 }

[cities.turin]
name = "Turin, Italy"
center = [45.0, 7.6]
radius_km = 8
"""


def test_bbox_around_is_wider_in_longitude():
    box = bbox_around(45.0, 7.6, 8)
    assert (box.south, box.north) == (44.9279, 45.0721)       # 8 / 111 = 0.0721 degrees
    assert box.east - box.west > box.north - box.south         # cos(45) < 1


def test_new_city_is_appended_and_rest_untouched():
    out = upsert_city_block(CONFIG, "venice", city_block("venice", "Venice, Italy", 45.4372, 12.3346, 5))
    assert out.startswith(CONFIG.rstrip("\n"))
    assert out.endswith('[cities.venice]\nname = "Venice, Italy"\ncenter = [45.4372, 12.3346]\nradius_km = 5\n')


def test_existing_city_is_refused_without_replace():
    with pytest.raises(ValueError):
        upsert_city_block(CONFIG, "turin", city_block("turin", "Turin, Italy", 45.07, 7.68, 6))


def test_replace_swaps_only_that_city():
    out = upsert_city_block(CONFIG, "milan", city_block("milan", "Milan, Italy", 45.46, 9.19, 6), replace=True)
    assert "bbox = { south = 45.39" not in out
    assert "center = [45.4600, 9.1900]" in out
    assert "# Cities" in out and "[cities.turin]" in out and out.count("[cities.") == 2
