from gmaps_scraper.geometry import BBox, auto_step_km, order_center_first

MILAN = BBox(45.39, 9.06, 45.54, 9.28)
VIEWPORT = {"width": 1280, "height": 900}


def test_milan_automatic_step():
    assert auto_step_km(MILAN.mid_lat, 15, VIEWPORT, 408, 0.85) == 2.48


def test_milan_grid_is_7_by_7():
    cells = MILAN.grid_centers(2.48)
    assert len(cells) == 49
    assert cells[0] == (45.40117, 9.07593)     # half a step inside the south-west corner
    assert cells[-1] == (45.53523, 9.26707)


def test_step_changes_cell_count():
    assert len(MILAN.grid_centers(2.92)) == 36   # overlap 1.0
    assert len(MILAN.grid_centers(2.04)) == 81   # overlap 0.7


def test_higher_zoom_halves_the_step():
    assert auto_step_km(MILAN.mid_lat, 16, VIEWPORT, 408, 0.85) == 1.24


def test_center_first():
    first = order_center_first(MILAN.grid_centers(2.48), MILAN)[0]
    assert first == (45.4682, 9.1715)


def test_contains():
    assert MILAN.contains(45.4642, 9.19)
    assert not MILAN.contains(41.9, 12.5)
