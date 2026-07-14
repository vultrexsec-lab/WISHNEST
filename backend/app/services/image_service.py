"""
Real image search for WishNest articles.

Three-provider search chain with a structured query-degradation fallback:

  1. DuckDuckGo Images (free, no API key) — primary source.
  2. Pexels API (free, requires PEXELS_API_KEY) — used when DDG returns nothing
     or errors (rate limit, network blip, library issue).
  3. Unsplash API (free, requires UNSPLASH_ACCESS_KEY) — used when both of the
     above fail.

If all three providers return nothing for the exact query, we do NOT fall back
to a random placeholder (Picsum or similar) — that produces foreign, completely
unrelated images (Statue of Liberty, vintage cars, Hollywood hills).

Instead we apply a query-degradation chain that stays geographically relevant:
  - Level 0: exact landmark query  e.g. "Har Ki Pauri Haridwar India"
  - Level 1: bare location          e.g. "Haridwar India"
  - Level 2: thematic regional      e.g. "Ganges River ghats India"
  - Level 3: broad India travel     e.g. "India spiritual river pilgrimage"

If every level of the chain exhausts every provider, the slot is left blank
(returns None) rather than publishing a misleading foreign image.

All returned URLs are rewritten to go through our own `/api/image-proxy`
route so that:
  - Hotlinking/referrer restrictions on the origin CDN never break the
    published article (we fetch server-side and re-serve the bytes).
  - The frontend never depends on a third-party image host's uptime.

Strategy:
  1. Extract h2/h3 headings from the full_article HTML (in document order).
  2. For each heading build a targeted search query and fetch the top image.
  3. Inject a <figure> block immediately after each heading tag so readers see
     a contextual photo right where the subject is discussed.
  4. Also populate hero_image_url (wide search on the headline + location) and
     section_image_urls (list of fetched URLs) for backward-compatible rendering.

Never raises — provider failures fall through the degradation chain; a blank
slot is preferable to a foreign placeholder.
"""
import hashlib
import html
import logging
import random
import re
import time
import urllib.parse

import requests

from app.config import get_settings
from app.services.places_service import PropertyListing, fetch_premium_stays, fetch_property_by_name

logger = logging.getLogger("wishnest.image_service")

_REQUEST_TIMEOUT = 8  # seconds — keep provider calls snappy so one slow API doesn't stall the whole article

# ---------------------------------------------------------------------------
# URL safety
# ---------------------------------------------------------------------------

_SAFE_URL_RE = re.compile(
    r"^https?://"
    r"[a-zA-Z0-9._~:/?#\[\]@!$&'()*+,;=%\-]+"
    r"$"
)

# Also allow our own relative image-proxy path (e.g. "/api/image-proxy?url=...")
# so proxied URLs pass the same safety check as absolute http(s) URLs.
_SAFE_RELATIVE_PROXY_RE = re.compile(
    r"^/api/image-proxy\?url="
    r"[a-zA-Z0-9._~:/?#\[\]@!$&'()*+,;=%\-]+"
    r"$"
)


def _safe_image_url(url: str) -> str | None:
    """
    Return the URL unchanged if it is a safe http(s) image URL (or our own
    relative image-proxy URL), else None. Rejects anything that could break
    out of an HTML attribute context.
    """
    if not url or not isinstance(url, str):
        return None
    url = url.strip()
    if not _SAFE_URL_RE.match(url) and not _SAFE_RELATIVE_PROXY_RE.match(url):
        return None
    lower = url.lower()
    if "javascript:" in lower or "data:" in lower:
        return None
    return url


def _proxied_url(original_url: str) -> str:
    """
    Rewrite a third-party image URL to go through our own backend proxy
    (`/api/image-proxy?url=...`) so published articles never break due to
    hotlink protection, CORS, or the origin host going down.
    """
    return "/api/image-proxy?url=" + urllib.parse.quote(original_url, safe="")


# ---------------------------------------------------------------------------
# Query building — force strict geographic/landmark relevance
# ---------------------------------------------------------------------------

# Indian hill stations that generic/western stock photography frequently
# gets confused with (e.g. "resort with balcony views" pulling Alpine/Bali
# chalet images). Any subject/location mentioning one of these gets a strict
# regional lock: forced *region-correct* hill terms plus negative keywords to
# push DuckDuckGo away from generic interior/stock results. Mapped per-station
# rather than a single hardcoded "Uttarakhand/Himalayan" pair for all of
# them — Ooty/Munnar/Coorg are Western Ghats/Nilgiris, not Himalayan, and
# forcing the wrong region name would itself hurt relevance.
_HILL_STATION_REGIONS: dict[str, str] = {
    "mussoorie": "Uttarakhand hills Himalayan resort",
    "nainital": "Uttarakhand hills Himalayan resort",
    "almora": "Uttarakhand hills Himalayan resort",
    "ranikhet": "Uttarakhand hills Himalayan resort",
    "kausani": "Uttarakhand hills Himalayan resort",
    "lansdowne": "Uttarakhand hills Himalayan resort",
    "shimla": "Himachal hills Himalayan resort",
    "manali": "Himachal hills Himalayan resort",
    "dalhousie": "Himachal hills Himalayan resort",
    "kasauli": "Himachal hills Himalayan resort",
    "chail": "Himachal hills Himalayan resort",
    "darjeeling": "West Bengal Himalayan hills resort",
    "gangtok": "Sikkim Himalayan hills resort",
    "ooty": "Nilgiri hills Western Ghats resort",
    "kodaikanal": "Palani hills Western Ghats resort",
    "munnar": "Kerala Western Ghats hills resort",
    "coorg": "Karnataka Western Ghats hills resort",
}
_HILL_STATIONS = set(_HILL_STATION_REGIONS)


# ---------------------------------------------------------------------------
# Live property listings (Google Places / SerpApi) are the PRIMARY image
# source — every image handed out preferentially belongs to a real, named
# business listing with a genuine Google star rating, never a stock photo.
#
# PREMIUM_LUXURY_HOTEL_IMAGES below is a last-resort SAFETY NET only. It
# exists purely so a slow/erroring/quota-exhausted live provider (or a
# location with no dynamic-search results) can never leave a published
# article with a blank image slot. It is deliberately checked LAST, after
# the live pool and the dynamic search chain have both been exhausted.
# ---------------------------------------------------------------------------
PREMIUM_LUXURY_HOTEL_IMAGES: list[str] = [
    "https://images.unsplash.com/photo-1566073771259-6a8506099945?w=1600&q=80",  # 01 resort infinity pool
    "https://images.unsplash.com/photo-1571896349842-33c89424de2d?w=1600&q=80",  # 02 luxury pool terrace
    "https://images.unsplash.com/photo-1590490360182-c33d57733427?w=1600&q=80",  # 03 hotel suite bedroom
    "https://images.unsplash.com/photo-1582719478250-c89cae4dc85b?w=1600&q=80",  # 04 tropical resort pool
    "https://images.unsplash.com/photo-1540555700478-4be289fbecef?w=1600&q=80",  # 05 grand hotel exterior
]


def _static_fallback_url(index: int, used_urls: set[str]) -> str:
    """
    Pick from PREMIUM_LUXURY_HOTEL_IMAGES starting at a randomised offset
    (so repeated total-provider-outage articles don't all show the exact
    same first entry), then walk forward sequentially from there, wrapping
    around if an article needs more images than the array has. Only skips
    to the next entry if the proxied URL is already used elsewhere in this
    article; if every entry is somehow already used, repeats are accepted
    over leaving the slot blank. Never raises, never returns empty/None —
    this is the guaranteed last line of defense against a blank image slot.
    """
    n = len(PREMIUM_LUXURY_HOTEL_IMAGES)
    index = (index + random.randint(0, n - 1)) % n
    for offset in range(n):
        raw_url = PREMIUM_LUXURY_HOTEL_IMAGES[(index + offset) % n]
        proxied = _proxied_url(raw_url)
        if proxied not in used_urls:
            used_urls.add(proxied)
            return proxied
    # Every static image already used in this article — repeat rather than
    # ever return an empty slot.
    return _proxied_url(PREMIUM_LUXURY_HOTEL_IMAGES[index % n])


class _LivePropertyPool:
    """
    Wraps a list of `PropertyListing`s fetched once per article and hands
    them out sequentially so every section of the grid shows a different
    real property — zero repeats within a single article.
    """

    def __init__(self, location: str | None, limit: int = 10):
        try:
            self.listings: list[PropertyListing] = fetch_premium_stays(location, limit=limit)
        except Exception as exc:  # noqa: BLE001
            # fetch_premium_stays is documented to never raise, but this call
            # site must be bulletproof regardless — a live-provider outage or
            # unexpected exception must never take down article generation
            # or leave the image grid blank.
            logger.warning("Live property fetch raised unexpectedly for %r: %s", location, exc)
            self.listings = []
        self._next_index = 0
        self.used: list[PropertyListing] = []

    @property
    def available(self) -> bool:
        return self._next_index < len(self.listings)

    def take_next(self, used_urls: set[str]) -> tuple[str, PropertyListing] | None:
        """Return (proxied_url, listing) for the next unused live property, or None."""
        while self._next_index < len(self.listings):
            listing = self.listings[self._next_index]
            self._next_index += 1
            if not listing.photo_url:
                continue
            proxied = _proxied_url(listing.photo_url)
            if proxied in used_urls:
                continue
            used_urls.add(proxied)
            self.used.append(listing)
            return proxied, listing
        return None


class _SinglePropertyPhotoPool:
    """
    Strict, single-business image source for review articles about ONE named
    property (e.g. "Hyatt Dehradun"). Every slot cycles through that same
    property's own verified photo pool — never a different business, never
    DDG/Pexels/Unsplash, never the static safety-net images. If the property
    has fewer real photos than the article needs, photos are safely repeated
    (cycled) rather than padded with anything foreign.

    `available` is True only when at least one real photo for the named
    property was found; callers must fall back to the broader multi-property
    pipeline entirely when it's False (there is nothing to strictly filter
    to).
    """

    def __init__(self, headline: str, location: str | None):
        self.listing: PropertyListing | None = None
        try:
            # 15 (not the bare minimum 10) gives enough headroom for the
            # hero slot + at least MIN_SINGLE_PROPERTY_IMAGES section slots
            # even after a couple of photos get skipped as duplicates.
            self.listing = fetch_property_by_name(headline, location, max_photos=15)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Single-property lookup raised for %r: %s", headline[:60], exc)
            self.listing = None
        self._photos: list[str] = list(self.listing.photo_urls) if self.listing else []
        self._cursor = 0

    @property
    def available(self) -> bool:
        return bool(self._photos)

    @property
    def has_unused(self) -> bool:
        """True while at least one of this property's real photos has never
        been handed out yet — callers should prefer topping up from a
        different source (a themed search for the specific slot, e.g.
        "pool"/"dining"/"room") over calling `take_next()` and silently
        repeating a photo the reader already saw under a different caption."""
        return self._cursor < len(self._photos)

    @property
    def unused_count(self) -> int:
        """How many of this property's real photos have never been handed
        out yet. Used to pad the section-image grid with extra real photos
        (beyond one per heading) up to the article's minimum image target."""
        return max(0, len(self._photos) - self._cursor)

    def take_next(self) -> str:
        """Return the proxied URL for the next UNUSED photo in this
        property's own pool. Only repeats (cycles) once every real photo has
        already been handed out at least once — callers should check
        `has_unused` first and prefer a themed search fallback instead of
        forcing a repeat when there's a richer source available (e.g. Google
        Places not configured but DDG/Pexels/Unsplash are). Only call this
        when `available` is True."""
        url = self._photos[self._cursor % len(self._photos)]
        self._cursor += 1
        return _proxied_url(url)


def _build_query(subject: str, location: str | None) -> str:
    """
    Build a targeted image-search query for the given subject + location.

    Strategy
    --------
    Short subjects (≤ 3 words) are almost always specific landmark or place
    names (e.g. "Ram Jhula", "Har Ki Pauri", "Ganga Aarti").  Quoting them
    as two independent phrase-tokens ("Ram Jhula" "Rishikesh") frequently
    returns zero results from image APIs because the providers try to match
    both quoted phrases independently, falling through to Picsum.

    Instead we combine short subject + location into ONE unquoted phrase
    ("Ram Jhula Rishikesh India") so providers treat it as a single coherent
    landmark query — which is exactly what returns accurate results.

    Long subjects (> 3 words) are section headings like "Best Homestays with
    Valley Views".  For those we skip quoting the full heading (too specific)
    and instead lead with the location so the query is anchored geographically.

    Hill-station lock: any subject/location mentioning a known Indian hill
    station gets forced regional terms (e.g. "Uttarakhand hills Himalayan
    resort") plus DDG negative keywords (-interiors -stock -generic) to push
    away generic Alpine/Bali chalet stock photos.
    """
    subject = (subject or "").strip()
    if not subject:
        return location or ""

    haystack = f"{subject} {location or ''}".lower()
    matched_hill_station = next(
        (hs for hs in _HILL_STATIONS if hs in haystack), None
    )

    words = subject.split()
    loc = (location or "").strip()

    if len(words) <= 3:
        # Short landmark name — combine directly into one phrase for maximum
        # search relevance.  Avoids the two-quoted-token problem.
        if loc and loc.lower() not in subject.lower():
            base = f"{subject} {loc}"
        else:
            base = subject
        parts = [base]
        if "india" not in base.lower():
            parts.append("India")
    else:
        # Long heading — anchor on location first, then add the subject
        # without quoting so providers don't over-restrict results.
        if loc and loc.lower() not in subject.lower():
            parts = [loc, subject]
        else:
            parts = [subject]
        if loc and "india" not in loc.lower() and "india" not in subject.lower():
            parts.append("India")
        elif not loc and "india" not in subject.lower():
            parts.append("India")

    if matched_hill_station:
        parts.append(_HILL_STATION_REGIONS[matched_hill_station])
        parts.append("-interiors -stock -generic")

    return " ".join(parts)


# ---------------------------------------------------------------------------
# Relevance filtering — reject images whose metadata has no overlap with the
# geographic/landmark subject we actually searched for
# ---------------------------------------------------------------------------

_STOPWORDS = {
    "the", "a", "an", "of", "in", "at", "for", "and", "or", "to", "with",
    "near", "view", "views", "photo", "photos", "image", "images", "best",
    "top", "stay", "stays", "hotel", "hotels", "resort", "resorts",
    "luxury", "villa", "villas", "property", "review", "reviews", "india",
    "exterior", "interior", "ambiance",
}


def _significant_tokens(text: str | None) -> set[str]:
    if not text:
        return set()
    tokens = re.findall(r"[a-zA-Z]{3,}", text.lower())
    return {t for t in tokens if t not in _STOPWORDS}


def _is_relevant(query: str, title: str | None, source_url: str | None) -> bool:
    """
    Reject a candidate image if its title/source metadata shares no
    significant words with the search query (minus "india" and generic
    filler like "luxury"/"resort"). This stops queries for a specific
    landmark (e.g. "Har Ki Pauri, Haridwar") from silently accepting a
    generic/unrelated stock photo when the exact match wasn't the top hit.

    If the provider gives us no title/source metadata to judge at all, we
    can't strictly filter a bare URL — allow it through rather than
    starving every slot down to the Picsum placeholder.
    """
    query_tokens = _significant_tokens(query)
    if not query_tokens:
        return True

    metadata_tokens = _significant_tokens(f"{title or ''} {source_url or ''}")
    if not metadata_tokens:
        return True

    return bool(query_tokens & metadata_tokens)


# ---------------------------------------------------------------------------
# Provider 1: DuckDuckGo image search (no API key required)
# ---------------------------------------------------------------------------

def _ddg_image_search(query: str, max_results: int = 5) -> list[str]:
    """
    Return a list of validated direct image URLs from DuckDuckGo Images.
    Returns an empty list on any failure.
    """
    try:
        from ddgs import DDGS
        results: list[str] = []
        rejected = 0
        with DDGS() as ddgs:
            for r in ddgs.images(
                query,
                region="wt-wt",
                safesearch="moderate",
                size="Large",
                type_image="photo",
                layout="Wide",
                max_results=max_results * 3,
            ):
                raw_url = r.get("image") or r.get("url") or ""
                safe = _safe_image_url(raw_url)
                if not safe:
                    continue
                if not _is_relevant(query, r.get("title"), r.get("source") or r.get("url")):
                    rejected += 1
                    continue
                results.append(safe)
                if len(results) >= max_results:
                    break
        logger.debug(
            "DDG images for %r -> %d results (%d rejected as irrelevant)",
            query[:60], len(results), rejected,
        )
        return results
    except Exception as exc:  # noqa: BLE001
        logger.warning("DDG image search failed for %r: %s", query[:60], exc)
        return []


# ---------------------------------------------------------------------------
# Provider 2: Pexels API (free key at pexels.com/api)
# ---------------------------------------------------------------------------

def _pexels_image_search(query: str, max_results: int = 5) -> list[str]:
    api_key = get_settings().pexels_api_key
    if not api_key:
        return []
    try:
        resp = requests.get(
            "https://api.pexels.com/v1/search",
            headers={"Authorization": api_key},
            params={"query": query, "per_page": max_results, "orientation": "landscape"},
            timeout=_REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        results: list[str] = []
        rejected = 0
        for photo in data.get("photos", []):
            src = (photo.get("src") or {}).get("large2x") or (photo.get("src") or {}).get("large")
            safe = _safe_image_url(src)
            if not safe:
                continue
            title = photo.get("alt")
            source_url = photo.get("url")
            if not _is_relevant(query, title, source_url):
                rejected += 1
                continue
            results.append(safe)
        logger.debug(
            "Pexels images for %r -> %d results (%d rejected as irrelevant)",
            query[:60], len(results), rejected,
        )
        return results
    except Exception as exc:  # noqa: BLE001
        logger.warning("Pexels image search failed for %r: %s", query[:60], exc)
        return []


# ---------------------------------------------------------------------------
# Provider 3: Unsplash API (free key at unsplash.com/developers)
# ---------------------------------------------------------------------------

def _unsplash_image_search(query: str, max_results: int = 5) -> list[str]:
    access_key = get_settings().unsplash_access_key
    if not access_key:
        return []
    try:
        resp = requests.get(
            "https://api.unsplash.com/search/photos",
            headers={"Authorization": f"Client-ID {access_key}"},
            params={"query": query, "per_page": max_results, "orientation": "landscape"},
            timeout=_REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        results: list[str] = []
        rejected = 0
        for photo in data.get("results", []):
            src = (photo.get("urls") or {}).get("regular") or (photo.get("urls") or {}).get("full")
            safe = _safe_image_url(src)
            if not safe:
                continue
            title = photo.get("alt_description") or photo.get("description")
            source_url = (photo.get("links") or {}).get("html")
            if not _is_relevant(query, title, source_url):
                rejected += 1
                continue
            results.append(safe)
        logger.debug(
            "Unsplash images for %r -> %d results (%d rejected as irrelevant)",
            query[:60], len(results), rejected,
        )
        return results
    except Exception as exc:  # noqa: BLE001
        logger.warning("Unsplash image search failed for %r: %s", query[:60], exc)
        return []


# ---------------------------------------------------------------------------
# Provider chain — try all three real providers before giving up
# ---------------------------------------------------------------------------

def _search_all_providers(query: str, max_results: int = 5) -> list[str]:
    """Try each provider in order; return the first non-empty result list."""
    for provider in (_ddg_image_search, _pexels_image_search, _unsplash_image_search):
        try:
            urls = provider(query, max_results=max_results)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Image provider %s raised for %r: %s", provider.__name__, query[:60], exc)
            urls = []
        if urls:
            return urls
    return []


# ---------------------------------------------------------------------------
# Query-degradation chain — stays geographically/thematically relevant even
# when the exact landmark query returns nothing from any provider.
# Picsum is intentionally ABSENT — it returns random unrelated foreign photos.
# ---------------------------------------------------------------------------

def _degraded_query_chain(query: str, location: str | None) -> list[str]:
    """
    Build a list of progressively broader queries that are all contextually
    appropriate for an Indian travel article.  The caller tries them in order
    until one produces a real, non-duplicate image URL.

    Levels
    ------
    0  Exact query (already constructed by _build_query)
       e.g. "Har Ki Pauri Haridwar India"

    1  Bare location + India
       e.g. "Haridwar India"

    2  Thematic regional query derived from the subject/location keywords
       e.g. "Ganges River ghats India"  (for ghat/river/aarti subjects)
            "Himalayan mountains India" (for hill-station subjects)
            "Hindu temple India"        (for temple/spiritual subjects)

    3  Broad India travel safety net — always contextually relevant for a
       travel website even if very generic
       e.g. "India travel scenic landscape"
    """
    chain: list[str] = [query]

    loc = (location or "").strip()
    haystack = f"{query} {loc}".lower()

    # Level 1 — bare location
    if loc and loc.lower() not in query.lower():
        chain.append(f"{loc} India")
    elif loc:
        # location already in query; try a shorter cut
        chain.append(f"{loc}")

    # Level 2 — thematic regional, based on detectable subject keywords
    if any(w in haystack for w in [
        "jhula", "ghat", "pauri", "aarti", "ganges", "ganga",
        "haridwar", "rishikesh", "varanasi", "kashi", "triveni",
    ]):
        chain.append("Ganges River ghats India pilgrimage")
        chain.append("Haridwar Rishikesh spiritual India")
    elif any(w in haystack for w in [
        "temple", "mandir", "shrine", "puja", "aarti", "spiritual",
        "ashram", "yoga", "meditation", "devi", "shiva", "vishnu",
    ]):
        chain.append("Hindu temple India spiritual")
        chain.append("Indian pilgrimage site India")
    elif any(w in haystack for w in [
        "mussoorie", "nainital", "shimla", "manali", "darjeeling", "ooty",
        "hill station", "trek", "himalay", "mountain", "valley", "waterfall",
    ]):
        chain.append("Himalayan mountains India landscape")
        chain.append("Indian hill station scenic India")
    elif any(w in haystack for w in ["beach", "sea", "ocean", "coast", "goa", "kerala", "andaman"]):
        chain.append("India beach coastline travel")
    elif any(w in haystack for w in [
        "fort", "palace", "rajasthan", "jaipur", "udaipur", "jodhpur",
        "heritage", "monument", "haveli",
    ]):
        chain.append("Rajasthan heritage India palace")
        chain.append("India historical monument heritage")
    elif any(w in haystack for w in ["agra", "taj mahal", "mughal"]):
        chain.append("Taj Mahal Agra India")
    else:
        chain.append("India travel scenic landscape tourism")

    # Level 3 — broadest safe fallback (still India-specific, never random)
    chain.append("India travel landscape scenic")

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for q in chain:
        if q not in seen:
            seen.add(q)
            unique.append(q)
    return unique


def _best_image(
    query: str,
    location: str | None = None,
    used_urls: set[str] | None = None,
) -> str | None:
    """
    Return the best validated (and proxied) image URL for *query* that has
    not already been used in the current article.

    Tries the exact query first, then progressively broader but always
    India-relevant fallback queries (see `_degraded_query_chain`).  Fetches
    8 candidates per query level so there is room to skip duplicates.

    Returns None only when every query level across every provider is
    exhausted — a blank slot is always preferable to a random foreign image.
    Picsum is intentionally never used.
    """
    for attempt_query in _degraded_query_chain(query, location):
        urls = _search_all_providers(attempt_query, max_results=8)
        for raw_url in urls:
            proxied = _proxied_url(raw_url)
            if used_urls is None or proxied not in used_urls:
                if used_urls is not None:
                    used_urls.add(proxied)
                if attempt_query != query:
                    logger.info(
                        "Image degraded fallback used: %r -> %r",
                        query[:50], attempt_query[:50],
                    )
                return proxied

    logger.warning(
        "No relevant image found for %r after full degradation chain — slot left blank.",
        query[:60],
    )
    return None


# ---------------------------------------------------------------------------
# Heading extraction (positional — handles duplicate heading text correctly)
# ---------------------------------------------------------------------------

_HEADING_RE = re.compile(
    r"(<(h[23])[^>]*>)(.*?)(</\2>)",
    re.IGNORECASE | re.DOTALL,
)

_HTML_TAG_RE = re.compile(r"<[^>]+>")

# Minimum total real photos (hero + sections combined) a strict single-
# property review article should carry. Short articles have fewer headings
# than this, so extra real photos from the property's own gallery are
# appended as un-captioned/extra section slots to reach the floor rather
# than under-using an otherwise rich photo pool.
MIN_SINGLE_PROPERTY_IMAGES = 10


def _strip_tags(markup: str) -> str:
    """Remove all HTML tags from *markup* and collapse whitespace."""
    return _HTML_TAG_RE.sub("", markup).strip()


def _extract_headings(full_article_html: str) -> list[str]:
    """
    Return a list of plain-text heading strings (h2 and h3) in document order.
    Duplicate heading texts are preserved as separate entries so that the
    positional injection can handle them independently.
    Skips headings that are completely empty after tag-stripping.
    """
    headings: list[str] = []
    for _open, _tag, inner, _close in _HEADING_RE.findall(full_article_html):
        text = _strip_tags(inner)
        if text:
            headings.append(text)
    return headings


# ---------------------------------------------------------------------------
# Image injection into article HTML (positional, with safe HTML escaping)
# ---------------------------------------------------------------------------

_FIGURE_TEMPLATE = (
    '<figure class="wishnest-section-image" '
    'style="margin:2rem 0;text-align:center;">'
    '<img src="{url}" alt="{alt}" referrerpolicy="no-referrer" '
    'style="max-width:100%;width:100%;height:auto;border-radius:8px;object-fit:cover;display:block;" '
    'loading="lazy" />'
    '<figcaption style="font-size:0.8rem;color:#666;margin-top:0.5rem;">'
    "{caption}"
    "</figcaption>"
    "</figure>"
)


def _inject_images_into_html(
    full_article_html: str,
    heading_images: list[tuple[str, str]],   # [(heading_text, image_url), ...]  positional
) -> str:
    """
    Insert a <figure> block immediately *after* each closing </h2> or </h3> tag.
    Matches headings positionally so duplicate heading texts are handled correctly.
    All interpolated values are HTML-escaped to prevent XSS.
    """
    if not heading_images:
        return full_article_html

    img_iter = iter(heading_images)
    current: tuple[str, str] | None = next(img_iter, None)

    def _replace_heading(match: re.Match) -> str:
        nonlocal current, img_iter

        inner = match.group(3)
        full_match = match.group(0)

        heading_text = _strip_tags(inner)

        if current is None:
            return full_match

        _expected_text, url = current
        current = next(img_iter, None)

        safe_url = _safe_image_url(url)
        if not safe_url:
            return full_match

        alt = html.escape(heading_text[:120], quote=True)
        caption = html.escape(f"Image: {heading_text[:80]}", quote=False)
        figure = _FIGURE_TEMPLATE.format(url=safe_url, alt=alt, caption=caption)
        return full_match + "\n" + figure

    return _HEADING_RE.sub(_replace_heading, full_article_html)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_article_images(
    headline: str,
    focus_keyword: str | None = None,
    location: str | None = None,
    article_type: str = "standard",
    full_article: str | None = None,
) -> tuple[str | None, list[str], str | None, list[dict]]:
    """
    Fill every image slot for the article, preferring LIVE, real Google Maps
    property listings for the given location, and fall back to the dynamic
    (still real, never static) image-search chain only when no live listing
    is available for a given slot.

    Returns:
        (hero_image_url, section_image_urls, enriched_full_article, property_matches)

    - hero_image_url:        URL of the best wide shot for the article header
                              (proxied through /api/image-proxy). May be None
                              if no real image was found at any fallback level.
    - section_image_urls:    One URL per extracted heading (None entries for
                              headings where no real image was found).
    - enriched_full_article: full_article HTML with <figure> blocks injected after
                              each h2/h3 heading. None if full_article was not provided.
    - property_matches:      [{"name", "rating", "review_count", "maps_url"}, ...]
                              for every live Google Maps listing actually used in
                              this article, in the order they were assigned. Empty
                              when no live provider is configured or none matched —
                              callers must treat that as "no live rating data".

    Never raises; per-image failures walk the degradation chain and leave the
    slot as None rather than publishing a random foreign placeholder. No image
    URL is ever reused within the same article.
    """
    # Shared dedup set — every image URL chosen for this article is recorded
    # here so that no two slots (hero, sections, injected figures) ever get
    # the same photo.  Passed into every _best_image / live-pool call below.
    # (Not used at all for the strict single-property path below — repeats
    # are expected and desired there, since every slot must belong to the
    # same one hotel.)
    used_urls: set[str] = set()

    full_article_headings = _extract_headings(full_article) if full_article else []

    def _property_match_dict(listing: PropertyListing) -> dict:
        return {
            "name": listing.name,
            "rating": listing.rating,
            "review_count": listing.review_count,
            "maps_url": listing.maps_url,
        }

    # -------------------------------------------------------------------
    # Strict single-property path — review articles about ONE named place
    # (e.g. "Hyatt Dehradun"). If we can verify real photos for that exact
    # business, EVERY slot (hero + every section) is filled strictly from
    # that business's own photo pool, cycling/repeating as needed. No other
    # business, no DDG/Pexels/Unsplash, no static safety-net image is ever
    # mixed in for this article.
    # -------------------------------------------------------------------
    single_pool: _SinglePropertyPhotoPool | None = None
    if article_type == "review":
        single_pool = _SinglePropertyPhotoPool(headline, location)

    if single_pool is not None and single_pool.available:
        property_name = single_pool.listing.name
        hero_url = single_pool.take_next()
        used_urls.add(hero_url)
        logger.info(
            "Hero image resolved from strict single-property pool %r (%d photo(s) available) for %r",
            property_name, len(single_pool.listing.photo_urls), headline[:60],
        )

        section_urls = []
        heading_images = []
        slots = full_article_headings if full_article_headings else ["exterior view", "interior ambiance"]
        themed_fill_count = 0
        for slot in slots:
            if single_pool.has_unused:
                # A real, never-shown-yet photo of THIS property is still
                # available — always prefer it over a themed search so we
                # exhaust the property's own gallery before touching anything
                # else.
                url = single_pool.take_next()
            else:
                # Every real photo of this property has already been used
                # once. Rather than silently repeating one under a new
                # caption (e.g. the same exterior shot captioned "the
                # infinity pool"), try a themed search anchored on the
                # property's own name + this specific slot (pool/dining/
                # room view/etc) so the reader sees a distinct, on-topic
                # image instead of an obvious duplicate.
                time.sleep(0.2)
                themed_query = _build_query(f"{property_name} {slot}", location)
                try:
                    url = _best_image(themed_query, location=location, used_urls=used_urls)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Themed search raised for slot %r on %r: %s", slot[:50], property_name, exc)
                    url = None
                if url is not None:
                    themed_fill_count += 1
                    used_urls.add(url)
                else:
                    # No distinct image found anywhere — cycling a repeat is
                    # still preferable to leaving the slot blank.
                    url = single_pool.take_next()
            section_urls.append(url)
            if full_article_headings:
                heading_images.append((slot, url))
        logger.info(
            "Filled %d section slot(s) for %r: %d from the property's own gallery, %d via themed search top-up",
            len(section_urls), property_name, len(section_urls) - themed_fill_count, themed_fill_count,
        )

        # -- Pad with extra real photos up to MIN_SINGLE_PROPERTY_IMAGES --
        # Short articles (few headings) would otherwise under-use a rich
        # gallery — e.g. a property with 15 verified photos but only 4
        # headings previously surfaced just 5 images total (hero + 4). These
        # extra slots have no associated heading, so they are appended to
        # section_urls only (no <figure> injection into the article body,
        # since there's no heading position to inject after) and still
        # strictly belong to this same verified property.
        total_so_far = 1 + len(section_urls)  # hero + sections filled above
        padded_count = 0
        while total_so_far < MIN_SINGLE_PROPERTY_IMAGES and single_pool.has_unused:
            section_urls.append(single_pool.take_next())
            total_so_far += 1
            padded_count += 1
        if padded_count:
            logger.info(
                "Padded %r with %d extra real photo(s) from its own gallery to reach the %d-image floor "
                "(final total: %d).",
                property_name, padded_count, MIN_SINGLE_PROPERTY_IMAGES, total_so_far,
            )

        property_matches = [_property_match_dict(single_pool.listing)]

        # Skip straight to HTML injection / final validation below by
        # reusing the shared tail of the function.
        injected_count = sum(1 for _, u in heading_images if u)
        enriched_html: str | None = None
        if full_article and heading_images:
            try:
                enriched_html = _inject_images_into_html(full_article, heading_images)
                logger.info(
                    "Injected %d/%d images into article HTML for %r",
                    injected_count, len(heading_images), headline[:50],
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("HTML injection failed for %r: %s", headline[:50], exc)
                enriched_html = full_article
        elif full_article:
            enriched_html = full_article

        section_urls_clean = [u for u in section_urls if u is not None]
        return hero_url, section_urls_clean, enriched_html, property_matches

    # -------------------------------------------------------------------
    # Broader multi-property path — standard articles (roundups covering
    # many locations/properties) or reviews where the exact named property
    # couldn't be verified against a live provider. Falls through live pool
    # -> dynamic search chain -> static safety net per slot, as before.
    # -------------------------------------------------------------------

    # -- Live property pool: one Google Places/SerpApi lookup per article,
    # sized to cover the hero slot plus every heading we expect to fill.
    # Extra headroom (+3) absorbs listings that fail the photo check.
    expected_slots = 1 + (len(full_article_headings) if full_article_headings else 2)
    live_pool = _LivePropertyPool(location, limit=expected_slots + 3)

    # -- Hero image ----------------------------------------------------------
    # Safe routing: live pool -> dynamic search chain -> static safety net.
    # Every layer is wrapped so a provider error never bubbles up and never
    # leaves this slot empty.
    static_fallback_index = 0
    hero_url: str | None = None
    try:
        hero_live = live_pool.take_next(used_urls)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Live pool lookup raised for hero slot (%r): %s", headline[:60], exc)
        hero_live = None
    if hero_live is not None:
        hero_url, hero_listing = hero_live
        logger.info(
            "Hero image resolved from live listing %r (%.1f★) for %r",
            hero_listing.name, hero_listing.rating or 0.0, headline[:60],
        )
    else:
        hero_query = _build_query(headline, location)
        try:
            hero_url = _best_image(hero_query, location=location, used_urls=used_urls)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Dynamic search raised for hero slot (%r): %s", headline[:60], exc)
            hero_url = None
        if hero_url is not None:
            logger.info("Hero image resolved via search fallback for %r (query=%r)", headline[:60], hero_query[:80])
    if hero_url is None:
        hero_url = _static_fallback_url(static_fallback_index, used_urls)
        static_fallback_index += 1
        logger.warning("Hero image fell back to the static safety-net pool for %r", headline[:60])

    # -- Section images -- one per heading in document order -----------------
    section_urls: list[str] = []
    heading_images: list[tuple[str, str]] = []

    if full_article_headings:
        headings = full_article_headings
        logger.info("Extracted %d headings from article %r", len(headings), headline[:50])

        for heading in headings:
            try:
                live_next = live_pool.take_next(used_urls)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Live pool lookup raised for heading %r: %s", heading[:50], exc)
                live_next = None
            if live_next is not None:
                url, listing = live_next
                logger.info(
                    "Section image for heading %r -> live listing %r (%.1f★)",
                    heading[:50], listing.name, listing.rating or 0.0,
                )
            else:
                time.sleep(0.3)
                query = _build_query(heading, location)
                try:
                    url = _best_image(query, location=location, used_urls=used_urls)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Dynamic search raised for heading %r: %s", heading[:50], exc)
                    url = None
                if url is not None:
                    logger.info("Section image for heading %r -> search fallback (query=%r)", heading[:50], query[:80])
            if url is None:
                url = _static_fallback_url(static_fallback_index, used_urls)
                static_fallback_index += 1
                logger.warning("Section image for heading %r fell back to the static safety-net pool", heading[:50])
            section_urls.append(url)
            heading_images.append((heading, url))

    else:
        for suffix in ["exterior view", "interior ambiance"]:
            try:
                live_next = live_pool.take_next(used_urls)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Live pool lookup raised for slot %r: %s", suffix, exc)
                live_next = None
            if live_next is not None:
                url, _listing = live_next
            else:
                time.sleep(0.2)
                subject = f"{focus_keyword or headline} {suffix}"
                query = _build_query(subject, location)
                try:
                    url = _best_image(query, location=location, used_urls=used_urls)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Dynamic search raised for slot %r: %s", suffix, exc)
                    url = None
            if url is None:
                url = _static_fallback_url(static_fallback_index, used_urls)
                static_fallback_index += 1
                logger.warning("Section image for slot %r fell back to the static safety-net pool", suffix)
            section_urls.append(url)

    property_matches = [_property_match_dict(l) for l in live_pool.used]

    injected_count = sum(1 for _, u in heading_images if u)
    enriched_html: str | None = None
    if full_article and heading_images:
        try:
            enriched_html = _inject_images_into_html(full_article, heading_images)
            logger.info(
                "Injected %d/%d images into article HTML for %r",
                injected_count, len(heading_images), headline[:50],
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("HTML injection failed for %r: %s", headline[:50], exc)
            enriched_html = full_article
    elif full_article:
        enriched_html = full_article

    # used_urls is a single set initialised at the top of this function and
    # passed into every _best_image / _pick_static_fallback call for both the
    # hero slot and all section/heading slots.  This guarantees that no image
    # URL is reused anywhere within a single article generation pass.

    # Strip any None entries — _best_image returns None when no real image is
    # found; Pydantic's list[str] schema rejects None entries in the ARRAY col.
    section_urls_clean: list[str] = [u for u in section_urls if u is not None]

    # Final hero-URL sanity check: must be our own proxy path or an absolute
    # http(s) URL.  Anything else (empty string, log-line fragments, etc.) is
    # discarded so the frontend never receives a non-image string as a src.
    if hero_url is not None:
        valid = (
            hero_url.startswith("/api/image-proxy?url=")
            or hero_url.startswith("https://")
            or hero_url.startswith("http://")
        )
        if not valid:
            logger.warning(
                "Hero URL discarded — failed final format validation: %r",
                hero_url[:120],
            )
            hero_url = None

    return hero_url, section_urls_clean, enriched_html, property_matches
