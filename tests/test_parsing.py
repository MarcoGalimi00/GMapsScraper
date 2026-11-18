"""Parser tests: no browser, no network. Run with `pytest`."""
from gmaps_scraper.geometry import BBox
from gmaps_scraper.parsing import extract_category, parse_card, parse_rating, reparse_row

MILAN = BBox(45.39, 9.06, 45.54, 9.28)
STAR = ""   # the star icon Maps puts after the rating

BRERA_TEXT = ("Pinacoteca di Brera\nPinacoteca di Brera\n4.7" + STAR +
              "\nTourist attraction ·  · Via Brera, 28\nArt museum specialising in Italian art\nOpen · Closes 7:15 PM")
EUSTORGIO_TEXT = ("Basilica di Sant'Eustorgio\nBasilica di Sant'Eustorgio\n4.6(3,578)" + STAR +
                  "\nTourist attraction ·  · Piazza Sant'Eustorgio, 1")


# --- parse_rating ------------------------------------------------------------------

def test_parse_rating_label_with_reviews():
    assert parse_rating("4.6 stars 86,636 Reviews", None) == (4.6, 86636)


def test_parse_rating_label_without_reviews():       # headless browser
    assert parse_rating("4.6 stars", None) == (4.6, None)


def test_parse_rating_single_review():
    assert parse_rating("5.0 stars 1 Review", None) == (5.0, 1)


def test_parse_rating_falls_back_to_card_text_with_reviews():
    assert parse_rating(None, EUSTORGIO_TEXT) == (4.6, 3578)


def test_parse_rating_falls_back_to_card_text_rating_only():
    assert parse_rating(None, BRERA_TEXT) == (4.7, None)


def test_parse_rating_label_wins_over_card_text():
    assert parse_rating("4.7 stars 35,872 Reviews", BRERA_TEXT) == (4.7, 35872)


def test_parse_rating_nothing():
    assert parse_rating(None, "Some place\nSome place\nNo reviews\n20121 Milano MI") == (None, None)
    assert parse_rating(None, None) == (None, None)
    assert parse_rating("", "") == (None, None)


# --- extract_category ----------------------------------------------------------------

def test_category_after_rating_only_line():
    assert extract_category(BRERA_TEXT) == "Tourist attraction"


def test_category_after_rating_with_reviews():
    assert extract_category(EUSTORGIO_TEXT) == "Tourist attraction"


def test_category_without_rating():
    text = "MAUA\nMAUA\nNo reviews\nOpen air museum · Via Antonio Tantardini, 22\nOpen 24 hours"
    assert extract_category(text) == "Open air museum"     # not mistaken for opening hours


def test_category_absent():
    assert extract_category("Palazzo\nPalazzo\nNo reviews\n20123 Milano MI") is None


# --- parse_card ----------------------------------------------------------------------

def card(**overrides):
    base = {
        "name": "Pinacoteca di Brera",
        "href": "https://www.google.com/maps/place/Pinacoteca+di+Brera/data=!4m7!3m6"
                "!1s0x4786c6a0e3e0f6b5:0x1a2b3c4d5e6f7a8b!8m2!3d45.4718!4d9.1881!19sChIJexample?authuser=0",
        "sponsored": False,
        "rating_label": "4.7 stars 35,872 Reviews",
        "image_src": "https://lh3.googleusercontent.com/p/AF1Qip=w122-h92-k-no",
        "card_text": BRERA_TEXT,
    }
    return {**base, **overrides}


def test_parse_card_full_row():
    row = parse_card(card(), "milan", "museum", MILAN)
    assert row["place_id"] == "ChIJexample"
    assert (row["lat"], row["lng"]) == (45.4718, 9.1881)
    assert row["feature_id"] == "0x4786c6a0e3e0f6b5:0x1a2b3c4d5e6f7a8b"
    assert row["maps_url"].endswith("!19sChIJexample")          # session parameters dropped
    assert row["queries"] == ["museum"]
    assert row["category"] == "Tourist attraction"
    assert (row["rating"], row["reviews_count"]) == (4.7, 35872)


def test_parse_card_drops_sponsored_incomplete_and_outside():
    assert parse_card(card(sponsored=True), "milan", "museum", MILAN) is None
    assert parse_card(card(href=None), "milan", "museum", MILAN) is None
    rome = card(href="https://www.google.com/maps/place/X/data=!3d41.9!4d12.5!19sChIJrome")
    assert parse_card(rome, "milan", "museum", MILAN) is None


def test_parse_card_ignores_placeholder_images():
    assert parse_card(card(image_src="data:image/gif;base64,AAA"), "milan", "m", MILAN)["image_url"] is None


def test_reparse_row_uses_card_text_when_label_missing():
    old = {"place_id": "x", "card_text": EUSTORGIO_TEXT, "category": None, "rating": None, "reviews_count": None}
    new = reparse_row(old)
    assert (new["category"], new["rating"], new["reviews_count"]) == ("Tourist attraction", 4.6, 3578)
