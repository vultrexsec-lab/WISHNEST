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
from app.services.places_service import (
    PropertyListing,
    fetch_landmark_attractions,
    fetch_premium_stays,
    fetch_property_by_name,
)

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

# Verified, high-quality food/dining placeholders — used ONLY when ALL dynamic
# search providers (DDG, Pexels, Unsplash) fail for a culinary/dining section
# so that no broken or missing image appears under a food heading.
# These are generic food/restaurant shots with no visible branding so they are
# safe alongside any LLM-generated culinary text.
PREMIUM_FOOD_PLACEHOLDER_IMAGES: list[str] = [
    "https://images.unsplash.com/photo-1414235077428-338989a2e8c0?w=1600&q=80",  # F1 restaurant table setting
    "https://images.unsplash.com/photo-1504674900247-0877df9cc836?w=1600&q=80",  # F2 colourful food flat-lay
    "https://images.unsplash.com/photo-1555396273-367ea4eb4db5?w=1600&q=80",  # F3 warm restaurant interior
    "https://images.unsplash.com/photo-1567620905732-2d1ec7ab7445?w=1600&q=80",  # F4 plated gourmet dish
    "https://images.unsplash.com/photo-1540189549336-e6e99c3679fe?w=1600&q=80",  # F5 fresh ingredients bowl
]


# Verified lounge/lobby/exterior placeholders — used ONLY when ALL dynamic
# search providers fail for a hospitality or general section so the slot
# never shows a bathroom or blank image under a guest-experience heading.
PREMIUM_LOUNGE_EXTERIOR_IMAGES: list[str] = [
    "https://images.unsplash.com/photo-1590490360182-c33d57733427?w=1600&q=80",  # L1 hotel suite lounge area
    "https://images.unsplash.com/photo-1564501049412-61c2a3083791?w=1600&q=80",  # L2 hotel lobby interior
    "https://images.unsplash.com/photo-1540555700478-4be289fbecef?w=1600&q=80",  # L3 grand hotel exterior
    "https://images.unsplash.com/photo-1551882547-ff40c63fe5fa?w=1600&q=80",  # L4 luxury hotel entrance
    "https://images.unsplash.com/photo-1455587734955-081b22074882?w=1600&q=80",  # L5 hotel reception/lobby
]


def _lounge_fallback_url(used_urls: set[str]) -> str:
    """
    Pick a verified lounge / lobby / exterior placeholder that has not already
    been used in this article.  Falls back to the first entry if every
    placeholder is already used.  Designed for hospitality and general sections
    where the property photo pool cannot be trusted (untagged Google Maps photos
    may be bathrooms or bedrooms).
    """
    for raw_url in PREMIUM_LOUNGE_EXTERIOR_IMAGES:
        if raw_url not in used_urls:
            used_urls.add(raw_url)
            return raw_url
    return PREMIUM_LOUNGE_EXTERIOR_IMAGES[0]


def _food_fallback_url(used_urls: set[str]) -> str:
    """
    Pick a verified food/dining placeholder that has not already been used in
    this article.  Returns the DIRECT Unsplash URL (not proxied) so it is
    100% guaranteed to load in the browser — Unsplash's CDN is public and
    does not use hotlink protection for standard image URLs.  Falls back to
    the first entry if every placeholder is already used.
    """
    for raw_url in PREMIUM_FOOD_PLACEHOLDER_IMAGES:
        if raw_url not in used_urls:
            used_urls.add(raw_url)
            return raw_url
    # All five already used — repeat the first; duplication beats blank.
    return PREMIUM_FOOD_PLACEHOLDER_IMAGES[0]


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


# ---------------------------------------------------------------------------
# Landmark / destination category detection
# ---------------------------------------------------------------------------

# Category values (from the DB / scheduler) that indicate an article is about
# tourist attractions, monuments, or scenic places rather than hotels/villas.
# Checked case-insensitively so UI display names ("Best Places & Destinations")
# and internal slugs ("destinations") both match.
_LANDMARK_CATEGORIES: frozenset[str] = frozenset({
    "destinations",
    "best places",
    "best places & destinations",
    "best-of-destinations",
    "destination",
    "places",
})


def _is_landmark_category(category: str | None) -> bool:
    """Return True when *category* indicates a landmark / destination article."""
    return bool(category and category.strip().lower() in _LANDMARK_CATEGORIES)


class _LandmarkPool:
    """
    Like `_LivePropertyPool` but for 'Best Places & Destinations' category
    articles. Queries SerpApi for tourist attractions and landmarks (India Gate,
    Qutub Minar, hill stations, ghats, etc.) instead of hotels/resorts, so
    every image slot carries genuine geographic content rather than hospitality
    interiors.

    When SerpApi returns no landmark results the pool is simply empty
    (`available` is False) and callers fall through to the dynamic image-search
    chain (DDG / Pexels / Unsplash with a location-anchored query). The static
    hotel safety-net (`PREMIUM_LUXURY_HOTEL_IMAGES`) is intentionally NEVER
    used for landmark articles — hotel clipart on a monument article is the
    exact failure mode this pool exists to prevent.
    """

    def __init__(self, location: str | None, limit: int = 10):
        try:
            self.listings: list[PropertyListing] = fetch_landmark_attractions(location, limit=limit)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Landmark attraction fetch raised for %r: %s", location, exc)
            self.listings = []
        self._next_index = 0
        self.used: list[PropertyListing] = []

    @property
    def available(self) -> bool:
        return self._next_index < len(self.listings)

    def take_next(self, used_urls: set[str]) -> "tuple[str, PropertyListing] | None":
        """Return (proxied_url, listing) for the next unused attraction, or None."""
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


# ---------------------------------------------------------------------------
# Photo tag classification — SerpApi category tags per pool photo
# ---------------------------------------------------------------------------

# Lowercased SerpApi photo tag tokens signalling exterior / facade content.
# Preferred for intro, accessibility, conclusion, and general sections.
_EXTERIOR_PHOTO_TAG_TOKENS: frozenset[str] = frozenset({
    "exterior", "front", "facade", "building", "outside", "outside view",
    "front of property", "outside of building", "street view", "approach",
    "property exterior", "entrance", "gate", "driveway", "landscaping",
    "garden", "grounds", "lawn", "panoramic view", "scenic", "outside area",
})

# Tokens signalling food / dining / kitchen content.
# Preferred for culinary sections; excluded from all others.
_CULINARY_PHOTO_TAG_TOKENS: frozenset[str] = frozenset({
    "food & drink", "food", "drinks", "beverages", "menu", "dining room",
    "kitchen", "breakfast", "lunch", "dinner", "chef", "meal", "cuisine",
    "cafe", "bar", "buffet", "restaurant", "cooking", "dishes", "dining",
})

# Tokens signalling a close-up portrait or staff member.
# Excluded from all sections except explicit hospitality headings.
_PORTRAIT_PHOTO_TAG_TOKENS: frozenset[str] = frozenset({
    "people", "staff", "owner", "employee", "team", "host", "hosts",
    "guests", "portrait", "selfie", "person", "individuals",
})

# Tokens signalling bedroom / room interior / bathroom content.
_ROOM_INTERIOR_PHOTO_TAG_TOKENS: frozenset[str] = frozenset({
    "rooms", "room", "bedroom", "suite", "interior", "accommodation",
    "bathroom", "washroom", "restroom", "toilet", "living room", "lobby",
    "reception", "lounge", "corridor", "hallway",
})

# Tokens signalling outdoor / garden / pool content.
_OUTDOOR_PHOTO_TAG_TOKENS: frozenset[str] = frozenset({
    "outdoor", "outdoors", "open air", "garden", "pool", "swimming pool",
    "terrace", "balcony", "patio", "veranda", "deck", "courtyard",
    "nature", "landscape", "greenery", "valley", "forest",
})

# Tokens for hospitality/reception sections — lobby/entrance ONLY.
# Deliberately does NOT include pool, garden, or terrace tokens so that
# outdoor photos are NOT consumed by guest-experience sections first,
# leaving them available for the actual Outdoor Spaces section.
_HOSPITALITY_PREFERRED_PHOTO_TAG_TOKENS: frozenset[str] = frozenset({
    "exterior", "front", "facade", "building", "outside", "outside view",
    "front of property", "outside of building", "entrance", "gate", "driveway",
    "lobby", "reception", "lounge", "concierge",
})


def _section_photo_preferences(
    section_type: str,
) -> tuple[frozenset[str], frozenset[str]]:
    """
    Return ``(preferred_tags, excluded_tags)`` for *section_type*.

    The smart pool scanner first tries photos whose tags overlap with
    ``preferred_tags``.  If none exist, any photo whose tags do NOT overlap
    with ``excluded_tags`` is returned.  Photos whose tags overlap with
    ``excluded_tags`` are never returned for this section (blank beats wrong).
    Untagged photos (empty tag list) never match preferred and never match
    excluded — they're treated as generic and returned in Pass 2.
    """
    if section_type in ("connectivity", "intro", "general"):
        # Accessibility / Conclusion / Introduction: exterior/facade first;
        # never kitchen, portrait, or room interior.
        return (
            _EXTERIOR_PHOTO_TAG_TOKENS | _OUTDOOR_PHOTO_TAG_TOKENS,
            _PORTRAIT_PHOTO_TAG_TOKENS | _CULINARY_PHOTO_TAG_TOKENS | _ROOM_INTERIOR_PHOTO_TAG_TOKENS,
        )
    if section_type == "culinary":
        # Culinary: food/dining preferred; never portrait or bedroom.
        return (
            _CULINARY_PHOTO_TAG_TOKENS,
            _PORTRAIT_PHOTO_TAG_TOKENS | _ROOM_INTERIOR_PHOTO_TAG_TOKENS,
        )
    if section_type == "outdoor":
        # Outdoor Spaces: garden/pool preferred; NEVER portrait, kitchen, OR
        # room/bathroom interior.  Adding _ROOM_INTERIOR_PHOTO_TAG_TOKENS to
        # excluded is the critical fix that prevents bathtub photos from
        # appearing under "Outdoor Spaces and Amenities".
        return (
            _OUTDOOR_PHOTO_TAG_TOKENS | _EXTERIOR_PHOTO_TAG_TOKENS,
            _PORTRAIT_PHOTO_TAG_TOKENS | _CULINARY_PHOTO_TAG_TOKENS | _ROOM_INTERIOR_PHOTO_TAG_TOKENS,
        )
    if section_type == "hospitality":
        # Guest Experience: lobby/entrance/facade preferred — but deliberately
        # NOT pool/garden/terrace.  Using _OUTDOOR_PHOTO_TAG_TOKENS here caused
        # pool images to be consumed by this section first, leaving the actual
        # Outdoor Spaces section with nothing but bathroom photos.
        return (
            _HOSPITALITY_PREFERRED_PHOTO_TAG_TOKENS,
            _CULINARY_PHOTO_TAG_TOKENS | _ROOM_INTERIOR_PHOTO_TAG_TOKENS,
        )
    if section_type == "room_design":
        # Rooms / Amenities: room interior preferred; portraits and kitchen excluded.
        return (
            _ROOM_INTERIOR_PHOTO_TAG_TOKENS,
            _PORTRAIT_PHOTO_TAG_TOKENS | _CULINARY_PHOTO_TAG_TOKENS,
        )
    # Catch-all: no strong preference; exclude portraits and kitchen.
    return (
        frozenset(),
        _PORTRAIT_PHOTO_TAG_TOKENS | _CULINARY_PHOTO_TAG_TOKENS,
    )


class _SinglePropertyPhotoPool:
    """
    Strict, single-business image source for review articles about ONE named
    property. Every slot comes from that property's own verified Google Maps
    photo gallery — never a different business, never stock images.

    Supports SerpApi tag-based smart selection: exterior photos are routed to
    intro/connectivity/conclusion sections, food photos to culinary sections,
    and portrait photos are excluded from non-hospitality sections.
    Untagged photos (the common case) are treated as generic and used when no
    better-tagged option is available.

    `available` is True only when at least one real photo was found; callers
    must fall back to the multi-property pipeline when it's False.
    """

    def __init__(self, headline: str, location: str | None):
        self.listing: PropertyListing | None = None
        try:
            # 20 photos gives more headroom for tag-based filtering — extra
            # photos ensure that even after excluding portraits/kitchens for
            # unsuitable sections there are real photos remaining.
            self.listing = fetch_property_by_name(headline, location, max_photos=20)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Single-property lookup raised for %r: %s", headline[:60], exc)
            self.listing = None

        # Build internal list of (raw_url, lowercased_tags) tuples.
        # Guard against missing photo_tags attribute on older objects.
        if self.listing:
            raw_urls = self.listing.photo_urls
            raw_tags = getattr(self.listing, "photo_tags", None) or [[] for _ in raw_urls]
            self._photos: list[tuple[str, list[str]]] = [
                (url, [t.lower() for t in (tags or []) if isinstance(t, str)])
                for url, tags in zip(raw_urls, raw_tags)
            ]
        else:
            self._photos = []

        # Track which indices have been handed out — never reuse until all
        # are exhausted.
        self._used: set[int] = set()

    @property
    def available(self) -> bool:
        return bool(self._photos)

    @property
    def has_unused(self) -> bool:
        return len(self._used) < len(self._photos)

    @property
    def unused_count(self) -> int:
        return max(0, len(self._photos) - len(self._used))

    def _hand_out(self, index: int) -> tuple[str, list[str]]:
        """Return (proxied_url, tags) and mark index as used."""
        self._used.add(index)
        url = _proxied_url(self._photos[index][0])
        tags = list(self._photos[index][1])  # copy of lowercased tags
        return url, tags

    def take_for_section(self, section_type: str) -> tuple[str, list[str]] | None:
        """
        Return (proxied_url, actual_tags) for the best-matching photo for
        *section_type* using tag-based smart routing, or None if the pool is
        exhausted or every remaining photo has excluded tags for this section.

        Pass 1 — preferred tag match (and no excluded tags).
        Pass 2 — no excluded tags (any neutral/untagged photo is acceptable).
        Pass 3 — all remaining photos are excluded → return None (blank slot).

        Photos skipped in Pass 3 remain in the pool for future sections that
        may accept them (e.g. a bedroom photo skipped for "Culinary" may still
        be used for "room_design").

        Returns actual SerpApi tags alongside the URL so callers can generate
        captions that reflect the real photo content rather than the section name.
        """
        prefer, exclude = _section_photo_preferences(section_type)

        # Pass 1: preferred tags AND no excluded tags
        for i, (_, tags) in enumerate(self._photos):
            if i in self._used:
                continue
            tag_set = set(tags)
            if tag_set & exclude:
                continue
            if prefer and (tag_set & prefer):
                return self._hand_out(i)

        # Pass 2: no excluded tags (untagged photos qualify here)
        for i, (_, tags) in enumerate(self._photos):
            if i in self._used:
                continue
            if not (set(tags) & exclude):
                return self._hand_out(i)

        # Pass 3: only excluded-tag photos remain — leave slot blank
        return None

    def take_any_remaining(self) -> tuple[str, list[str]] | None:
        """Return (proxied_url, actual_tags) for next unused photo regardless
        of tags — used for padding slots where any real photo is better than
        blank."""
        for i in range(len(self._photos)):
            if i not in self._used:
                return self._hand_out(i)
        return None


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


# ---------------------------------------------------------------------------
# Outdoor-context / indoor-metadata mismatch detection
#
# Problem: a section heading like "Outdoor Spaces and Amenities" generates a
# query whose generic token "amenities" matches hotel-room or bathroom images
# tagged "hotel amenities" — semantically wrong for an outdoor/nature section.
#
# Fix: if the search query signals an outdoor / garden / nature context, images
# whose metadata contains indoor-space tokens (bathroom, sink, bedroom, etc.)
# are hard-rejected regardless of token-overlap score.
# ---------------------------------------------------------------------------

# Tokens that signal an outdoor / garden / nature context in the query text.
_OUTDOOR_CONTEXT_TOKENS: frozenset[str] = frozenset({
    "outdoor", "outdoors", "outside", "open-air", "openair",
    "garden", "gardens", "grounds", "lawn", "courtyard", "patio",
    "terrace", "balcony", "deck", "verandah", "veranda",
    "pool", "infinity", "landscape", "landscaping",
    "forest", "trail", "trek", "nature", "natural",
    "valley", "mountain", "hill", "scenic", "vista", "view",
    "sky", "sunrise", "sunset", "surroundings", "environment",
    "meadow", "field", "jungle", "wildlife",
})

# Tokens in image metadata (title / source URL) that definitively indicate
# an indoor / bathroom / bedroom space — never appropriate under an outdoor
# section heading.
_INDOOR_MISMATCH_TOKENS: frozenset[str] = frozenset({
    "bathroom", "washroom", "restroom", "lavatory", "toilet",
    "bathtub", "bathing", "shower", "showerroom",
    "sink", "faucet", "tap", "plumbing", "vanity",
    "bedroom", "closet", "wardrobe", "corridor", "hallway",
    "laundry", "linen", "towel", "bath",
})

# Compiled regex for rejecting bathroom/plumbing AND bedroom/room-interior
# content when the calling section makes such images contextually wrong
# (culinary, outdoor).  NOT a global ban — bathroom and bedroom photos are
# legitimate editorial content in architecture, room-comforts, and hygiene
# sections where guests need to assess stay quality.  This gate fires ONLY
# when reject_plumbing=True (i.e. for every section except "room_design").
_INDOOR_BATHROOM_RE = re.compile(
    r"\b(?:"
    r"bathroom|washroom|restroom|lavatory|toilet|bathtub|bathing"
    r"|shower[\s_\-]?room|sink|faucet|plumbing"
    # bedroom / room-interior terms — wrong under Culinary / Outdoor headings
    r"|bedroom|bedrooms|bed[\s_\-]?room|guest[\s_\-]?room|hotel[\s_\-]?room"
    r"|suite[\s_\-]?interior|room[\s_\-]?interior|interior[\s_\-]?room"
    r"|sleeping[\s_\-]?area|bed[\s_\-]?area|accommodation[\s_\-]?interior"
    r")\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Section type classification
#
# Each article heading is classified into one of four types so the image
# routing logic can apply contextually correct constraints:
#
#   "culinary"    — dining, food, cuisine, kitchen, "Eat & Explore", etc.
#   "outdoor"     — garden, pool, terrace, outdoor spaces, landscape, etc.
#   "room_design" — room comforts, architecture, design, amenities, spa, etc.
#   "general"     — everything else (connectivity, history, conclusion, …)
#
# Bathroom / plumbing images are ALLOWED in "room_design" (guests need to see
# hygiene quality) but FORBIDDEN in "culinary" and "outdoor".
# ---------------------------------------------------------------------------

_CULINARY_HEADING_TOKENS: frozenset[str] = frozenset({
    "culinary", "dining", "food", "restaurant", "kitchen", "cuisine",
    "breakfast", "meal", "meals", "eat", "explore", "gastro", "gastronomy",
    "beverage", "drinks", "cafe", "menu", "chef", "cook", "cooking",
    "delights", "flavours", "flavors", "taste", "tasting",
})

# Tokens that classify a heading as "connectivity / accessibility" — these
# sections need exterior / entrance / gate imagery, NOT interior pool photos.
_CONNECTIVITY_HEADING_TOKENS: frozenset[str] = frozenset({
    "connectivity", "accessible", "accessibility",
    "transport", "transportation", "getting", "commute",
    "access", "distance", "proximity",
    "road", "highway", "airport", "station", "railway", "rail",
    "route", "routes", "directions", "reaching",
})

# Introduction / overview headings — should ALWAYS map to exterior/facade imagery.
# A property pool image (Google Maps user-uploaded) is too unpredictable here:
# it could be a bathroom, a corridor, or a random staff photo. Routing these
# sections to an exterior search guarantees the opening image of the article
# matches the introductory text (which describes the property's setting and
# architecture, not its plumbing).
_INTRO_HEADING_TOKENS: frozenset[str] = frozenset({
    "introduction", "intro", "overview", "about", "background",
    "welcome", "setting", "context", "preface", "prologue",
    "location", "situated", "nestled", "perched", "hidden",
})

_OUTDOOR_HEADING_TOKENS: frozenset[str] = frozenset({
    "outdoor", "outdoors", "outside", "open-air", "openair",
    "garden", "gardens", "grounds", "lawn", "courtyard", "patio",
    "pool", "infinity", "terrace", "balcony", "deck", "verandah", "veranda",
    "landscape", "landscaping", "nature", "natural",
    "forest", "trail", "valley", "mountain", "hill",
    "view", "views", "vista", "scenic", "scenery",
    "sunrise", "sunset", "sky", "environment",
    "surroundings", "meadow", "field", "jungle", "wildlife",
})

_ROOM_DESIGN_HEADING_TOKENS: frozenset[str] = frozenset({
    "room", "rooms", "suite", "suites", "comforts", "comfort",
    "bedroom", "accommodation",
    # NOTE: "architecture" / "architectural" intentionally excluded here.
    # Headings like "Architectural Marvel" describe the BUILDING DESIGN, not
    # room comforts — they should receive an exterior/property photo (general),
    # not a bedroom or bathroom image.  Those tokens now fall through to general.
    "design", "interior", "interiors", "amenities", "amenity",
    "stay", "lodging", "bathroom", "hygiene", "sanitation",
    "facility", "facilities", "spa", "wellness",
})

# Tokens that classify a heading as "hospitality / guest experience" — these
# sections describe staff quality, check-in, reviews, and service, NOT rooms.
# They must NEVER receive a bathroom or bedroom photo from the property pool.
# Fallback: warm lounge / lobby / reception imagery.
_HOSPITALITY_HEADING_TOKENS: frozenset[str] = frozenset({
    "hospitality", "experience", "experiences", "guest", "guests",
    "service", "services", "staff", "team", "host", "hosting",
    "review", "reviews", "rating", "ratings", "feedback",
    "check-in", "checkin", "checkout", "check-out",
    "concierge", "reception", "front-desk", "frontdesk",
    "welcome", "warmth", "care", "attention",
    "impression", "impressions", "testimonial", "testimonials",
})

# Section-specific image-search query suffixes — appended when doing a
# targeted search for a section so providers return contextually correct photos.
_SECTION_QUERY_SUFFIX: dict[str, str] = {
    "intro":         "exterior front entrance facade hotel building outside",
    "culinary":      "dining food restaurant cuisine kitchen",
    "outdoor":       "outdoor garden exterior grounds terrace pool",
    "room_design":   "room interior suite bedroom accommodation",
    "connectivity":  "exterior lobby entrance facade gate hotel front",
    "hospitality":   "hotel lounge lobby reception warm welcoming interior",
    "general":       "hotel exterior facade property grounds architecture",
}

# Human-readable labels for figure captions — describe what TYPE of image
# the section is expected to contain, so "Image: Introduction" becomes
# "Exterior view — Introduction" instead of a plain section heading echo.
# Used as the FALLBACK when actual photo tags are unavailable.
_SECTION_CAPTION_PREFIX: dict[str, str] = {
    "intro":         "Exterior view",
    "culinary":      "Culinary experience",
    "outdoor":       "Outdoor spaces",
    "room_design":   "Room and amenities",
    "connectivity":  "Entrance and access",
    "hospitality":   "Guest experience",
    "general":       "Property feature",
}


def _caption_prefix_from_actual_tags(tags: list[str]) -> str | None:
    """
    Derive the most accurate caption prefix from the *actual* SerpApi tags of
    the chosen photo rather than from the section heading type.

    This prevents "Exterior view" being written under a bedroom photo, or
    "Outdoor spaces" being written under a bathtub image.

    Returns None when tags are empty or unrecognisable — the caller then falls
    back to the section-type-derived prefix from _SECTION_CAPTION_PREFIX.

    Tag priority (most specific first):
      1. Bathroom / bathtub / plumbing  → "Bathroom and amenities"
      2. Pool / outdoor / garden        → "Outdoor spaces"
      3. Food / dining / kitchen        → "Culinary experience"
      4. Bedroom / room / suite interior → "Room and amenities"
      5. Exterior / facade / entrance   → "Exterior view"
    """
    if not tags:
        return None
    tag_set = set(tags)  # already lowercased by pool constructor
    if tag_set & {
        "bathroom", "washroom", "restroom", "bathtub", "bathing",
        "shower", "toilet", "lavatory",
    }:
        return "Bathroom and amenities"
    if tag_set & {
        "pool", "swimming pool", "outdoor", "outdoors", "garden",
        "terrace", "courtyard", "patio", "balcony", "veranda", "deck",
        "open air", "landscape", "greenery",
    }:
        return "Outdoor spaces"
    if tag_set & {
        "food & drink", "food", "drinks", "beverages", "dining room",
        "kitchen", "breakfast", "lunch", "dinner", "chef", "meal",
        "cuisine", "cafe", "bar", "buffet", "restaurant",
    }:
        return "Culinary experience"
    if tag_set & {
        "rooms", "room", "bedroom", "suite", "interior", "accommodation",
        "living room", "lounge", "corridor", "hallway",
    }:
        return "Room and amenities"
    if tag_set & {
        "exterior", "front", "facade", "building", "outside",
        "front of property", "entrance", "gate", "driveway",
    }:
        return "Exterior view"
    return None

# Property-neutral fallback queries used ONLY when the specific property's
# own verified photo pool is completely exhausted for culinary/outdoor sections.
#
# CRITICAL CONSTRAINT: These queries must NEVER include a property name, a
# location, a hotel name, a restaurant name, or any term that could cause an
# image provider to return photos of another business.
# — "Nirvaha Farms dining Dehradun" → might match a Dehradun restaurant ✗
# — "fresh organic vegetables farm produce" → generic, brand-free, safe ✓
#
# A flat-lay of farm vegetables or a sunlit garden path is always editorially
# preferable to a rival property's dining room appearing under "Culinary Delights".
# If even this neutral search fails, the slot is left intentionally blank.
_SECTION_NEUTRAL_FALLBACK: dict[str, str] = {
    "culinary":     "fresh organic vegetables farm produce ingredients natural food",
    "outdoor":      "outdoor natural scenery green garden peaceful vegetation sunlight",
    # Hospitality/experience sections: warm lounge/lobby imagery — never a bathroom.
    "hospitality":  "hotel lounge lobby reception area warm welcoming atmosphere elegant",
    # General/catch-all sections: safe exterior shot — universally appropriate
    # for history, conclusion, overview, and any unclassified heading type.
    "general":      "luxury hotel exterior architecture property beautiful grounds facade",
}


def _classify_section(heading: str) -> str:
    """
    Return the section type for *heading*: one of
    ``"culinary"``, ``"outdoor"``, ``"room_design"``, ``"connectivity"``,
    ``"hospitality"``, ``"intro"``, or ``"general"``.

    Bathroom / plumbing images are appropriate only for ``"room_design"``
    sections.  The image routing layer uses this classification to decide
    whether to take from the live property pool or do a targeted thematic
    search, and whether to pass ``reject_plumbing=True`` to the search chain.

    "connectivity" headings (accessibility, transport, getting there, etc.)
    are routed to exterior / entrance / facade imagery so the section photo
    never shows an interior room or pool when readers are expecting a shot of
    the building's approach or front gate.

    "hospitality" headings (guest experience, reviews, staff, service, etc.)
    are routed to warm lounge / lobby imagery — they must never receive a
    bathroom or bedroom photo from the property pool.
    """
    tokens = set(re.findall(r"[a-z]+", heading.lower()))
    if tokens & _CULINARY_HEADING_TOKENS:
        return "culinary"
    if tokens & _OUTDOOR_HEADING_TOKENS:
        return "outdoor"
    if tokens & _ROOM_DESIGN_HEADING_TOKENS:
        return "room_design"
    if tokens & _CONNECTIVITY_HEADING_TOKENS:
        return "connectivity"
    if tokens & _HOSPITALITY_HEADING_TOKENS:
        return "hospitality"
    # Check intro LAST so specific types above take precedence (e.g. a heading
    # like "Introduction to the Garden" should be "outdoor", not "intro").
    if tokens & _INTRO_HEADING_TOKENS:
        return "intro"
    return "general"


# ---------------------------------------------------------------------------
# Hard content-type rejection — non-photographic / non-editorial media
# ---------------------------------------------------------------------------

# Keywords that definitively identify non-photo content regardless of query.
# Applied to the combined title + source-URL string before any relevance check.
# clipart / charts / diagrams / course illustrations / stock-art watermarks
# are NEVER appropriate in a WishNest editorial article.
_BAD_CONTENT_RE = re.compile(
    r"\b(?:"
    r"clipart|clip[\s_\-]?art|cartoon|vector|icon|icons?|logo|logos?"
    r"|diagram|chart|charts?|infographic|infograph|illustration|illustrations?"
    r"|drawing|sketch|sticker|badge|certificate|watermark"
    r"|course|tutorial|lecture|powerpoint|presentation|slide|slides?|ebook|template"
    r"|emission|emiss|carbon|co2|greenhouse|pollut"
    r"|stock[\s_\-]?photo|royalty[\s_\-]?free|shutterstock|gettyimages"
    r"|istockphoto|dreamstime|depositphoto|alamy|freepik|vecteezy"
    r")\b",
    re.IGNORECASE,
)


def _is_bad_content(title: str | None, source_url: str | None) -> bool:
    """
    Return True when the image is definitively non-photographic (clipart,
    diagram, chart, course illustration, stock-art watermark, etc.).

    Called before the token-relevance check so that a bad-content image is
    always rejected even if it happens to share geographic tokens with the
    query (e.g. an "India Gate emissions chart" would otherwise pass the
    relevance filter).
    """
    text = f"{title or ''} {source_url or ''}"
    return bool(_BAD_CONTENT_RE.search(text))


def _is_relevant(
    query: str,
    title: str | None,
    source_url: str | None,
    *,
    reject_plumbing: bool = False,
) -> bool:
    """
    Reject a candidate image if any of the following conditions are met:

      (a) It is definitively non-photographic (clipart, chart, diagram, etc.) —
          hard rejection applied before any token check.

      (b) [Section-controlled] When ``reject_plumbing=True`` (set by the caller
          for culinary and outdoor sections), the image metadata contains
          bathroom / washroom / indoor-plumbing content and is rejected.
          This is NOT a global ban — bathroom images are legitimate editorial
          content in architecture / room-comfort / hygiene sections where guests
          need to verify stay quality.  ``reject_plumbing`` is only True when
          the current section makes such images contextually wrong.

      (c) The query signals an OUTDOOR / GARDEN / NATURE context (tokens such as
          "outdoor", "garden", "terrace", "pool", "landscape", "valley", etc.)
          AND the image metadata contains INDOOR-SPACE tokens (bathroom, bedroom,
          sink, corridor, etc.).  This prevents a generic tag like "amenities"
          from matching a washroom photo filed under "Outdoor Spaces and
          Amenities" even when the explicit outdoor-section routing bypasses the
          live pool and goes directly to the dynamic-search chain.

      (d) Its title/source metadata shares no significant words with the search
          query (token-overlap check).  Stops a landmark query from silently
          accepting an unrelated stock photo.

    If the provider gives us no title/source metadata (bare URL only) we allow
    the image through for (b)–(d) — can't filter what we can't read — but
    (a) still runs because it inspects the source URL itself.
    """
    metadata_text = f"{title or ''} {source_url or ''}"

    # ── (a) Hard reject: definitively non-photographic content ───────────────
    if _is_bad_content(title, source_url):
        return False

    # ── (b) Section-controlled bathroom / plumbing rejection ─────────────────
    # Only active when the caller explicitly signals that plumbing images are
    # inappropriate for the current section (culinary, outdoor).
    if reject_plumbing and _INDOOR_BATHROOM_RE.search(metadata_text):
        logger.debug(
            "Rejected plumbing/bathroom image for section-restricted query %r: metadata=%r",
            query[:50], metadata_text[:80],
        )
        return False

    # ── (c) Outdoor-context / indoor-metadata mismatch ───────────────────────
    # Secondary safety net: even when the live pool is bypassed, the dynamic-
    # search chain can still pull bathroom images for outdoor queries via
    # generic tags ("amenities"). Evaluate the FULL query string for outdoor
    # signals so environmental tokens win over generic ones.
    query_lower = query.lower()
    metadata_lower = metadata_text.lower()

    has_outdoor_context = any(tok in query_lower for tok in _OUTDOOR_CONTEXT_TOKENS)
    if has_outdoor_context:
        has_indoor_metadata = any(tok in metadata_lower for tok in _INDOOR_MISMATCH_TOKENS)
        if has_indoor_metadata:
            logger.debug(
                "Rejected indoor image for outdoor-context query %r: metadata=%r",
                query[:50], metadata_text[:80],
            )
            return False

    # ── (d) Token-overlap relevance check ────────────────────────────────────
    query_tokens = _significant_tokens(query)
    if not query_tokens:
        return True

    metadata_tokens = _significant_tokens(metadata_text)
    if not metadata_tokens:
        return True  # bare URL — can't judge; bad-content gate already ran

    return bool(query_tokens & metadata_tokens)


# ---------------------------------------------------------------------------
# Provider 1: DuckDuckGo image search (no API key required)
# ---------------------------------------------------------------------------

def _ddg_image_search(query: str, max_results: int = 5, *, reject_plumbing: bool = False) -> list[str]:
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
                if not _is_relevant(query, r.get("title"), r.get("source") or r.get("url"), reject_plumbing=reject_plumbing):
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

def _pexels_image_search(query: str, max_results: int = 5, *, reject_plumbing: bool = False) -> list[str]:
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
            if not _is_relevant(query, title, source_url, reject_plumbing=reject_plumbing):
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

def _unsplash_image_search(query: str, max_results: int = 5, *, reject_plumbing: bool = False) -> list[str]:
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
            if not _is_relevant(query, title, source_url, reject_plumbing=reject_plumbing):
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

def _search_all_providers(query: str, max_results: int = 5, *, reject_plumbing: bool = False) -> list[str]:
    """Try each provider in order; return the first non-empty result list."""
    for provider in (_ddg_image_search, _pexels_image_search, _unsplash_image_search):
        try:
            urls = provider(query, max_results=max_results, reject_plumbing=reject_plumbing)
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
    *,
    reject_plumbing: bool = False,
) -> str | None:
    """
    Return the best validated (and proxied) image URL for *query* that has
    not already been used in the current article.

    Tries the exact query first, then progressively broader but always
    India-relevant fallback queries (see `_degraded_query_chain`).  Fetches
    8 candidates per query level so there is room to skip duplicates.

    ``reject_plumbing=True`` propagates into every provider call so that
    bathroom / plumbing images are skipped throughout the entire degradation
    chain — used for culinary and outdoor section searches.

    Returns None only when every query level across every provider is
    exhausted — a blank slot is always preferable to a random foreign image.
    Picsum is intentionally never used.
    """
    for attempt_query in _degraded_query_chain(query, location):
        urls = _search_all_providers(attempt_query, max_results=8, reject_plumbing=reject_plumbing)
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
    heading_images: list[tuple[str, str, list[str]]],  # [(heading, url, actual_tags), ...]
) -> str:
    """
    Insert a <figure> block immediately *after* each closing </h2> or </h3> tag.
    Matches headings positionally so duplicate heading texts are handled correctly.
    All interpolated values are HTML-escaped to prevent XSS.

    actual_tags (third element of each tuple) are the real SerpApi photo-category
    tags from the chosen image.  They drive caption generation so the caption
    accurately reflects the actual photo content (e.g. "Room and amenities" for
    a bedroom photo, not "Exterior view" just because it's in an intro section).
    Pass an empty list when tags are unavailable; the caption then falls back to
    the section-type-derived prefix.
    """
    if not heading_images:
        return full_article_html

    img_iter = iter(heading_images)
    current: tuple[str, str, list[str]] | None = next(img_iter, None)

    def _replace_heading(match: re.Match) -> str:
        nonlocal current, img_iter

        inner = match.group(3)
        full_match = match.group(0)

        heading_text = _strip_tags(inner)

        if current is None:
            return full_match

        _expected_text, url, actual_tags = current
        current = next(img_iter, None)

        safe_url = _safe_image_url(url)
        if not safe_url:
            return full_match

        alt = html.escape(heading_text[:120], quote=True)

        # Caption priority:
        #   1. Derive from the photo's actual SerpApi tags (most accurate).
        #   2. Fall back to the section-type-derived label (e.g. "Exterior view"
        #      for intro sections when no tags are available).
        # This prevents captions like "Exterior view — Introduction to Amanbagh"
        # appearing under a photo that is clearly an indoor bedroom.
        caption_prefix = _caption_prefix_from_actual_tags(actual_tags)
        if caption_prefix is None:
            section_type_for_caption = _classify_section(heading_text)
            caption_prefix = _SECTION_CAPTION_PREFIX.get(section_type_for_caption, "Property feature")
        caption = html.escape(f"{caption_prefix} — {heading_text[:60]}", quote=False)

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
    category: str | None = None,
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
        # Hero: prefer exterior/facade shot (intro preference) for the opening image.
        hero_result = single_pool.take_for_section("intro")
        if hero_result is not None:
            hero_url, _hero_tags = hero_result
            used_urls.add(hero_url)
        else:
            hero_url = None
        logger.info(
            "Hero image resolved from strict single-property pool %r (%d photo(s) available) for %r",
            property_name, len(single_pool.listing.photo_urls), headline[:60],
        )

        section_urls = []
        heading_images: list[tuple[str, str, list[str]]] = []
        slots = full_article_headings if full_article_headings else ["exterior view", "interior ambiance"]
        pool_fill_count = 0
        fallback_fill_count = 0
        for slot in slots:
            section_type = _classify_section(slot)
            url: str | None = None
            actual_tags: list[str] = []

            # ── ALL sections: tag-matched photo from property's Google Maps pool ─
            # Only real photos from this exact property are used.  The smart pool
            # scanner first finds photos whose SerpApi tags match the section type
            # (exterior for Accessibility/Conclusion, food for Culinary, etc.) then
            # falls back to any untagged/neutral photo.  Portraits are excluded
            # from all non-hospitality sections; kitchen photos locked to Culinary.
            # Blank slot beats wrong content.
            slot_result = single_pool.take_for_section(section_type)
            if slot_result is not None:
                url, actual_tags = slot_result
                pool_fill_count += 1
                logger.info(
                    "Section slot %r (type=%r) -> tag-matched Google Maps photo (tags=%r)",
                    slot[:50], section_type, actual_tags[:5],
                )
            else:
                logger.warning(
                    "Section slot %r (type=%r) -> no suitable pool photo "
                    "(portrait/kitchen/bathroom excluded or pool exhausted), leaving blank.",
                    slot[:50], section_type,
                )

            section_urls.append(url)
            if full_article_headings:
                heading_images.append((slot, url, actual_tags))

        logger.info(
            "Filled %d section slot(s) for %r: %d from the property's own gallery, "
            "%d via property-neutral stock fallback",
            len(section_urls), property_name, pool_fill_count, fallback_fill_count,
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
            padded_result = single_pool.take_any_remaining()
            if padded_result is None:
                break
            padded_url, _padded_tags = padded_result
            section_urls.append(padded_url)
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
        injected_count = sum(1 for _, u, _t in heading_images if u)
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
    #
    # For 'Best Places & Destinations' / 'destinations' category articles we
    # query SerpApi for tourist attractions and landmarks instead of
    # hotels/resorts — hotel interiors are semantically wrong for a monument
    # or scenic-spot article (the root cause of the India Gate image bug).
    expected_slots = 1 + (len(full_article_headings) if full_article_headings else 2)
    _landmark = _is_landmark_category(category)
    if _landmark:
        live_pool: _LivePropertyPool | _LandmarkPool = _LandmarkPool(location, limit=expected_slots + 3)
        logger.info(
            "Using landmark/attraction pool for category=%r article %r",
            category, headline[:60],
        )
    else:
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
            "Hero image resolved from live Google Maps listing %r (%.1f★) for %r",
            hero_listing.name, hero_listing.rating or 0.0, headline[:60],
        )
    else:
        # No Google Maps photo available — leave hero blank.
        # Stock/DDG/Pexels/Unsplash images are never used.
        logger.warning(
            "No Google Maps photo available for hero slot of %r — leaving blank.",
            headline[:60],
        )

    # -- Section images -- one per heading in document order -----------------
    section_urls: list[str] = []
    heading_images: list[tuple[str, str]] = []

    if full_article_headings:
        headings = full_article_headings
        logger.info("Extracted %d headings from article %r", len(headings), headline[:50])

        for heading in headings:
            section_type = _classify_section(heading)
            url: str | None = None

            # ALL section types: strictly from the Google Maps live pool.
            # No DDG, Pexels, Unsplash, or stock fallback images are used.
            # If the pool is exhausted the slot stays blank — a missing image
            # is always preferable to a synthetic or unrelated photo.
            try:
                live_next = live_pool.take_next(used_urls)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Live pool lookup raised for heading %r: %s", heading[:50], exc)
                live_next = None
            if live_next is not None:
                url, listing = live_next
                logger.info(
                    "Section image for heading %r (type=%r) -> Google Maps listing %r (%.1f★)",
                    heading[:50], section_type, listing.name, listing.rating or 0.0,
                )
            else:
                logger.warning(
                    "Section image for heading %r (type=%r) -> Google Maps pool exhausted, leaving blank.",
                    heading[:50], section_type,
                )

            section_urls.append(url)
            heading_images.append((heading, url))

    else:
        for suffix in ["exterior view", "interior ambiance"]:
            url: str | None = None
            try:
                live_next = live_pool.take_next(used_urls)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Live pool lookup raised for slot %r: %s", suffix, exc)
                live_next = None
            if live_next is not None:
                url, _listing = live_next
            else:
                # Google Maps pool exhausted — leave blank; no stock fallback.
                logger.warning(
                    "No Google Maps photo available for slot %r — leaving blank.", suffix,
                )
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
