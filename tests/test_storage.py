from gmaps_scraper.storage import merge_rows


def test_merge_unites_queries_and_keeps_newest():
    a = [{"place_id": "p1", "name": "old", "queries": ["museum"], "last_scraped_at": "2026-11-17T15:00:00+00:00"}]
    b = [{"place_id": "p1", "name": "new", "queries": ["park"], "last_scraped_at": "2026-11-17T20:00:00+00:00"},
         {"place_id": "p2", "name": "x", "queries": ["park"], "last_scraped_at": "2026-11-17T20:00:00+00:00"}]
    merged = {r["place_id"]: r for r in merge_rows([a, b])}
    assert merged["p1"]["name"] == "new"
    assert merged["p1"]["queries"] == ["museum", "park"]
    assert len(merged) == 2
