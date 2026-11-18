"""Everything that touches the web page: URL, cookies, block detection,
infinite scroll and reading the cards."""
from __future__ import annotations

import logging
from urllib.parse import quote_plus

from .config import Settings

log = logging.getLogger("gmaps")

# Maps is always opened in English (hl=en): the texts the parser recognises
# ("stars", "Reviews", "No reviews", end-of-list message) are then always the same.
LANGUAGE = "en"

# Hooks in the page. Semantic attributes (role, aria-label) instead of generated
# CSS classes such as "Nv2PK", which Google changes often.
FEED = 'div[role="feed"]'
CONSENT_REJECT = 'button[aria-label="Reject all"]'
END_OF_LIST_JS = "/reached the end of the list/i"

# Runs INSIDE the page and reads every card at once: one round trip instead of hundreds.
EXTRACT_JS = """
() => [...document.querySelectorAll('div[role="feed"] div[role="article"]')].map(card => {
    const link = card.querySelector('a[href*="/maps/place/"]');
    const stars = card.querySelector('span[role="img"][aria-label*="star"]');
    const img = card.querySelector('img');
    return {
        name: link ? link.getAttribute('aria-label') : null,
        href: link ? link.href : null,
        sponsored: !!card.querySelector('[aria-label="Sponsored"]'),
        rating_label: stars ? stars.getAttribute('aria-label') : null,
        image_src: img ? img.src : null,
        card_text: card.innerText,
    };
})
"""


class BlockedError(RuntimeError):
    """Google showed its anti-robot check (/sorry/). We stop, we never try to bypass it."""


def build_url(query: str, lat: float, lng: float, zoom: int) -> str:
    """Same URL you see in the address bar when searching on Maps:
    /maps/search/<text>/@<lat>,<lng>,<zoom>z  -> search <text> around that point."""
    return f"https://www.google.com/maps/search/{quote_plus(query)}/@{lat},{lng},{zoom}z?hl={LANGUAGE}"


def handle_consent(page) -> None:
    """In Europe the first visit is redirected to the cookie page: reject the optional ones."""
    if "consent.google.com" in page.url:
        log.info("Cookie page: rejecting non-essential cookies")
        page.click(CONSENT_REJECT)
        page.wait_for_url("**/maps/**", timeout=30_000)


def check_blocked(page) -> None:
    if "/sorry/" in page.url:
        raise BlockedError("Google asked for an anti-robot check: stopping. "
                           "Retry later with longer pauses and fewer searches.")


def scroll_to_end(page, settings: Settings) -> None:
    """The list loads in blocks only when you reach its bottom. Scroll until the
    end-of-list message shows up, or the card count stops growing `stall_limit` times."""
    feed = page.locator(FEED)
    last_count, stalls = -1, 0
    for _ in range(settings.max_scrolls):
        feed.evaluate("el => el.scrollTo(0, el.scrollHeight)")
        page.wait_for_timeout(settings.scroll_pause_s * 1000)
        state = feed.evaluate(
            "el => ({n: el.querySelectorAll('div[role=\"article\"]').length,"
            f" end: {END_OF_LIST_JS}.test(el.innerText)}})"
        )
        if state["end"]:
            return
        stalls = stalls + 1 if state["n"] == last_count else 0   # any growth resets the counter
        if stalls >= settings.stall_limit:
            return
        last_count = state["n"]


def scrape_search(page, url: str, settings: Settings) -> list[dict]:
    """One complete search: open, check cookies and blocks, wait, scroll, read."""
    from playwright.sync_api import TimeoutError as PlaywrightTimeout

    page.goto(url, wait_until="domcontentloaded")
    handle_consent(page)
    check_blocked(page)
    try:
        page.wait_for_selector(FEED, timeout=settings.feed_timeout_ms)
    except PlaywrightTimeout:
        # No list: zero results, or a single result opened directly as a place page.
        return []
    scroll_to_end(page, settings)
    return page.evaluate(EXTRACT_JS)
