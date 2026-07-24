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

from dataclasses import dataclass, field

from app.config import get_settings
from app.services.places_service import (
    PropertyListing,
    _serpapi_maps_photos_gallery,
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

# Strict connectivity tokens — only clear entry points, roads, or gates.
# This is a deliberate subset of _EXTERIOR_PHOTO_TAG_TOKENS that excludes
# soft landscape tokens ("landscaping", "grounds", "lawn") that can surface
# blurry bush / hedge photos under a Connectivity / Getting Here section.
_CONNECTIVITY_PHOTO_TAG_TOKENS: frozenset[str] = frozenset({
    "entrance", "entrance gate", "gate", "gate house",
    "driveway", "road", "pathway", "path", "walkway", "lane",
    "front", "front of property", "street view", "approach",
    "exterior", "facade", "building", "outside of building",
    "property exterior", "outside", "outside view",
})

# Strict indoor-room tokens for room_design sections.
# Deliberately excludes "lobby", "corridor", "hallway" which can produce
# external building shots, and "lounge" which can be an outdoor terrace photo.
_ROOM_DESIGN_PHOTO_TAG_TOKENS: frozenset[str] = frozenset({
    "rooms", "room", "bedroom", "suite", "accommodation",
    "bathroom", "washroom", "restroom", "toilet", "living room",
    "interior", "bed", "bedding",
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
    if section_type == "culinary":
        # Culinary: ONLY food/dining photos. Portrait and all non-food tags excluded.
        # No fallback to room/outdoor — blank section beats a wrong image here.
        return (
            _CULINARY_PHOTO_TAG_TOKENS,
            _PORTRAIT_PHOTO_TAG_TOKENS | _ROOM_INTERIOR_PHOTO_TAG_TOKENS
            | _OUTDOOR_PHOTO_TAG_TOKENS | _EXTERIOR_PHOTO_TAG_TOKENS,
        )
    if section_type == "connectivity":
        # Connectivity/Access: ONLY clear road, pathway, entrance, or gate.
        # Outdoor nature tags (bushes, garden, landscape) are excluded because
        # they surface blurry vegetation photos that are not about access/approach.
        return (
            _CONNECTIVITY_PHOTO_TAG_TOKENS,
            _PORTRAIT_PHOTO_TAG_TOKENS | _CULINARY_PHOTO_TAG_TOKENS
            | _ROOM_INTERIOR_PHOTO_TAG_TOKENS | _OUTDOOR_PHOTO_TAG_TOKENS,
        )
    if section_type in ("intro", "general"):
        # Introduction / Conclusion: exterior/facade first; never kitchen,
        # portrait, or room interior.
        return (
            _EXTERIOR_PHOTO_TAG_TOKENS | _OUTDOOR_PHOTO_TAG_TOKENS,
            _PORTRAIT_PHOTO_TAG_TOKENS | _CULINARY_PHOTO_TAG_TOKENS | _ROOM_INTERIOR_PHOTO_TAG_TOKENS,
        )
    if section_type == "outdoor":
        # Outdoor Spaces: garden/pool preferred; NEVER portrait, kitchen, OR
        # room/bathroom interior.
        return (
            _OUTDOOR_PHOTO_TAG_TOKENS | _EXTERIOR_PHOTO_TAG_TOKENS,
            _PORTRAIT_PHOTO_TAG_TOKENS | _CULINARY_PHOTO_TAG_TOKENS | _ROOM_INTERIOR_PHOTO_TAG_TOKENS,
        )
    if section_type == "hospitality":
        # Guest Experience: lobby/entrance/facade preferred — but deliberately
        # NOT pool/garden/terrace so outdoor photos remain for Outdoor sections.
        return (
            _HOSPITALITY_PREFERRED_PHOTO_TAG_TOKENS,
            _CULINARY_PHOTO_TAG_TOKENS | _ROOM_INTERIOR_PHOTO_TAG_TOKENS,
        )
    if section_type == "room_design":
        # Rooms / Amenities: STRICTLY indoor bedroom/bathroom interiors.
        # Outdoor cottage shots and exterior building photos are excluded —
        # they belong to outdoor/exterior sections, not room comforts.
        return (
            _ROOM_DESIGN_PHOTO_TAG_TOKENS,
            _PORTRAIT_PHOTO_TAG_TOKENS | _CULINARY_PHOTO_TAG_TOKENS
            | _OUTDOOR_PHOTO_TAG_TOKENS | _EXTERIOR_PHOTO_TAG_TOKENS,
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
            self.listing = fetch_property_by_name(headline, location, max_photos=75)
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
        *section_type* using tag-based smart routing, or None only when the
        pool is fully exhausted.

        Pass 1 — preferred tag match (and no excluded tags).
        Pass 2 — no excluded tags (any neutral/untagged photo is acceptable).
        Pass 3 — last resort: any remaining unused photo from the property's
                  own gallery, regardless of tags. Exterior/entrance/grounds
                  photos are preferred as universally appropriate fallbacks.
                  Any real property photo beats a blank slot.

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

        # Pass 2: no excluded tags (untagged photos qualify here).
        # Exception: culinary sections require a POSITIVE food-tag signal.
        # An untagged photo could be anything (nature, room, selfie) — placing
        # it under a Dining / Culinary heading is never safe. Return None and
        # let the caller use a verified food placeholder instead.
        if section_type == "culinary":
            return None
        for i, (_, tags) in enumerate(self._photos):
            if i in self._used:
                continue
            if not (set(tags) & exclude):
                return self._hand_out(i)

        # Pass 3: section-specific last resort.
        #
        # Strict sections have editorial contracts — blank beats wrong:
        #   "culinary"     — already returned None above; never reaches here.
        #   "connectivity" — only exterior/entrance/gate tags accepted.
        #   "room_design"  — only indoor room/bedroom/bathroom tags accepted.
        #   Everything else — prefer exterior/outdoor tags, then accept anything.

        if section_type == "connectivity":
            # Connectivity must show a clear entrance, gate, or road.
            # Outdoor nature shots (bushes, garden) are not acceptable here.
            for i, (_, tags) in enumerate(self._photos):
                if i in self._used:
                    continue
                if set(tags) & _CONNECTIVITY_PHOTO_TAG_TOKENS:
                    return self._hand_out(i)
            # No entrance/gate/road photo found → blank connectivity section.
            return None

        if section_type == "room_design":
            # Room design must show an indoor bedroom or bathroom interior.
            # Outdoor cottage/garden shots are not acceptable here.
            for i, (_, tags) in enumerate(self._photos):
                if i in self._used:
                    continue
                if set(tags) & _ROOM_DESIGN_PHOTO_TAG_TOKENS:
                    return self._hand_out(i)
            # No indoor room photo found → blank room-design section.
            return None

        # For all other non-culinary sections: prefer exterior/outdoor tags,
        # then accept any remaining photo — a real property shot always beats blank.
        _EXTERIOR_PREFER = _EXTERIOR_PHOTO_TAG_TOKENS | _OUTDOOR_PHOTO_TAG_TOKENS
        for i, (_, tags) in enumerate(self._photos):
            if i in self._used:
                continue
            if set(tags) & _EXTERIOR_PREFER:
                return self._hand_out(i)
        # Absolute last resort: any unused photo from the property gallery.
        for i in range(len(self._photos)):
            if i not in self._used:
                return self._hand_out(i)
        return None

    def take_any_remaining(self) -> tuple[str, list[str]] | None:
        """Return (proxied_url, actual_tags) for next unused photo regardless
        of tags — used for padding slots where any real photo is better than
        blank."""
        for i in range(len(self._photos)):
            if i not in self._used:
                return self._hand_out(i)
        return None


# ===========================================================================
# Smart Category-Based Photo Pool — Vision-API-powered image selection
# ===========================================================================
#
# Replaces the simple sequential/tag-based photo selection with a pipeline
# that:
#   1. Classifies every fetched photo into one of 5 editorial categories using
#      Google Cloud Vision API (primary) or SerpApi tags (fallback).
#   2. Filters out selfies, close-up portraits, and blurry customer snapshots.
#   3. For each article section, picks the single BEST quality photo that
#      strictly matches the section's content category.
#   4. Enforces hard cross-category exclusions (e.g. NEVER puts a dining photo
#      under an Outdoor section).
# ===========================================================================

# ---------------------------------------------------------------------------
# 5 canonical photo categories used throughout WishNest editorial articles
# ---------------------------------------------------------------------------
PHOTO_CAT_DINING   = "dining_food"           # Rooms — Local dishes, dining area, kitchen
PHOTO_CAT_ROOMS    = "rooms_stay"            # Bedrooms, room interiors, bathrooms
PHOTO_CAT_OUTDOOR  = "outdoor_views"         # Gardens, mountains, landscape, nature
PHOTO_CAT_AMENITY  = "amenities_experience"  # Pool, spa, activities, terrace, deck
PHOTO_CAT_EXTERIOR = "exterior_architecture" # Building facade, entrance, lobby

# ---------------------------------------------------------------------------
# Google Cloud Vision API label → WishNest photo category
# Covers the most common labels returned for hotel/resort photography.
# ---------------------------------------------------------------------------
_VISION_LABEL_TO_CATEGORY: dict[str, str] = {
    # ── Dining & Food ──────────────────────────────────────────────────────
    "food": PHOTO_CAT_DINING, "dish": PHOTO_CAT_DINING, "meal": PHOTO_CAT_DINING,
    "cuisine": PHOTO_CAT_DINING, "restaurant": PHOTO_CAT_DINING, "dining room": PHOTO_CAT_DINING,
    "breakfast": PHOTO_CAT_DINING, "lunch": PHOTO_CAT_DINING, "dinner": PHOTO_CAT_DINING,
    "kitchen": PHOTO_CAT_DINING, "café": PHOTO_CAT_DINING, "cafe": PHOTO_CAT_DINING,
    "buffet": PHOTO_CAT_DINING, "tableware": PHOTO_CAT_DINING, "plate": PHOTO_CAT_DINING,
    "bowl": PHOTO_CAT_DINING, "cooking": PHOTO_CAT_DINING, "beverage": PHOTO_CAT_DINING,
    "drink": PHOTO_CAT_DINING, "food and drink": PHOTO_CAT_DINING, "cutlery": PHOTO_CAT_DINING,
    "brunch": PHOTO_CAT_DINING, "baking": PHOTO_CAT_DINING, "chef": PHOTO_CAT_DINING,
    "dessert": PHOTO_CAT_DINING, "bakery": PHOTO_CAT_DINING, "bar": PHOTO_CAT_DINING,
    "coffee": PHOTO_CAT_DINING, "tea": PHOTO_CAT_DINING, "cocktail": PHOTO_CAT_DINING,
    "appetizer": PHOTO_CAT_DINING, "salad": PHOTO_CAT_DINING, "soup": PHOTO_CAT_DINING,
    # ── Rooms & Stay ───────────────────────────────────────────────────────
    "bedroom": PHOTO_CAT_ROOMS, "bed": PHOTO_CAT_ROOMS, "pillow": PHOTO_CAT_ROOMS,
    "room": PHOTO_CAT_ROOMS, "suite": PHOTO_CAT_ROOMS, "mattress": PHOTO_CAT_ROOMS,
    "bathroom": PHOTO_CAT_ROOMS, "bathtub": PHOTO_CAT_ROOMS, "shower": PHOTO_CAT_ROOMS,
    "towel": PHOTO_CAT_ROOMS, "sofa": PHOTO_CAT_ROOMS, "furniture": PHOTO_CAT_ROOMS,
    "interior design": PHOTO_CAT_ROOMS, "ceiling": PHOTO_CAT_ROOMS, "floor": PHOTO_CAT_ROOMS,
    "closet": PHOTO_CAT_ROOMS, "wardrobe": PHOTO_CAT_ROOMS, "mirror": PHOTO_CAT_ROOMS,
    "curtain": PHOTO_CAT_ROOMS, "nightstand": PHOTO_CAT_ROOMS, "lamp": PHOTO_CAT_ROOMS,
    "accommodation": PHOTO_CAT_ROOMS, "lodging": PHOTO_CAT_ROOMS,
    # ── Outdoor & Views ────────────────────────────────────────────────────
    "sky": PHOTO_CAT_OUTDOOR, "mountain": PHOTO_CAT_OUTDOOR, "nature": PHOTO_CAT_OUTDOOR,
    "landscape": PHOTO_CAT_OUTDOOR, "forest": PHOTO_CAT_OUTDOOR, "tree": PHOTO_CAT_OUTDOOR,
    "valley": PHOTO_CAT_OUTDOOR, "hill": PHOTO_CAT_OUTDOOR, "garden": PHOTO_CAT_OUTDOOR,
    "lawn": PHOTO_CAT_OUTDOOR, "flower": PHOTO_CAT_OUTDOOR, "plant": PHOTO_CAT_OUTDOOR,
    "sunset": PHOTO_CAT_OUTDOOR, "sunrise": PHOTO_CAT_OUTDOOR, "cloud": PHOTO_CAT_OUTDOOR,
    "river": PHOTO_CAT_OUTDOOR, "lake": PHOTO_CAT_OUTDOOR, "waterfall": PHOTO_CAT_OUTDOOR,
    "vegetation": PHOTO_CAT_OUTDOOR, "scenery": PHOTO_CAT_OUTDOOR, "panorama": PHOTO_CAT_OUTDOOR,
    "wildlife": PHOTO_CAT_OUTDOOR, "jungle": PHOTO_CAT_OUTDOOR, "meadow": PHOTO_CAT_OUTDOOR,
    "field": PHOTO_CAT_OUTDOOR, "water": PHOTO_CAT_OUTDOOR, "rock": PHOTO_CAT_OUTDOOR,
    "snow": PHOTO_CAT_OUTDOOR, "fog": PHOTO_CAT_OUTDOOR, "mist": PHOTO_CAT_OUTDOOR,
    # ── Amenities & Experience ─────────────────────────────────────────────
    "swimming pool": PHOTO_CAT_AMENITY, "pool": PHOTO_CAT_AMENITY,
    "spa": PHOTO_CAT_AMENITY, "gym": PHOTO_CAT_AMENITY, "fitness centre": PHOTO_CAT_AMENITY,
    "terrace": PHOTO_CAT_AMENITY, "balcony": PHOTO_CAT_AMENITY, "deck": PHOTO_CAT_AMENITY,
    "patio": PHOTO_CAT_AMENITY, "jacuzzi": PHOTO_CAT_AMENITY, "hot tub": PHOTO_CAT_AMENITY,
    "yoga": PHOTO_CAT_AMENITY, "wellness": PHOTO_CAT_AMENITY, "sauna": PHOTO_CAT_AMENITY,
    "recreation": PHOTO_CAT_AMENITY, "leisure": PHOTO_CAT_AMENITY, "courtyard": PHOTO_CAT_AMENITY,
    "infinity pool": PHOTO_CAT_AMENITY, "rooftop": PHOTO_CAT_AMENITY,
    # ── Exterior & Architecture ────────────────────────────────────────────
    "building": PHOTO_CAT_EXTERIOR, "architecture": PHOTO_CAT_EXTERIOR,
    "facade": PHOTO_CAT_EXTERIOR, "entrance": PHOTO_CAT_EXTERIOR,
    "hotel": PHOTO_CAT_EXTERIOR, "resort": PHOTO_CAT_EXTERIOR, "lobby": PHOTO_CAT_EXTERIOR,
    "reception": PHOTO_CAT_EXTERIOR, "driveway": PHOTO_CAT_EXTERIOR, "gate": PHOTO_CAT_EXTERIOR,
    "roof": PHOTO_CAT_EXTERIOR, "structure": PHOTO_CAT_EXTERIOR, "corridor": PHOTO_CAT_EXTERIOR,
    "hallway": PHOTO_CAT_EXTERIOR, "staircase": PHOTO_CAT_EXTERIOR, "balustrade": PHOTO_CAT_EXTERIOR,
    "property": PHOTO_CAT_EXTERIOR, "estate": PHOTO_CAT_EXTERIOR,
    # ── Road / path labels — critical for Connectivity section matching ─────
    "road": PHOTO_CAT_EXTERIOR, "path": PHOTO_CAT_EXTERIOR, "pathway": PHOTO_CAT_EXTERIOR,
    "walkway": PHOTO_CAT_EXTERIOR, "lane": PHOTO_CAT_EXTERIOR, "track": PHOTO_CAT_EXTERIOR,
    "entrance gate": PHOTO_CAT_EXTERIOR, "gate house": PHOTO_CAT_EXTERIOR,
}

# ---------------------------------------------------------------------------
# Image quality rejection — dark, blurry, or low-resolution photos
# ---------------------------------------------------------------------------

# Vision labels whose presence in the TOP-3 results flags a photo as unusable:
# completely dark / silhouetted / heavily blurred / heavily overexposed.
# When ALL top-3 labels fall inside this set the photo is rejected from the pool.
_UNUSABLE_PHOTO_LABELS: frozenset[str] = frozenset({
    "darkness", "black", "silhouette", "shadow",
    "blur", "blurry", "out of focus", "defocus",
    "underexposed", "overexposed", "grainy", "noise",
    "artifact", "glare",
})

# Minimum confidence for the single top Vision label on an otherwise-unclassified
# photo.  When Vision returns only very low-confidence labels it has seen mostly
# noise — the image is likely too dark, blurry, or low-resolution to use.
# This threshold does NOT apply when a strong editorial category was matched
# (cat_scores non-empty) — those photos are accepted regardless of this floor.
_MIN_UNCLASSIFIED_LABEL_CONFIDENCE: float = 0.35

# Vision labels that strongly indicate a selfie / close-up portrait
_SELFIE_VISION_LABELS: frozenset[str] = frozenset({
    "nose", "forehead", "chin", "cheek", "ear", "lip", "selfie",
    "close-up", "closeup", "headshot", "tooth", "teeth", "eyebrow",
    "eyelash", "skin", "wrinkle", "pore",
})

# Top-level Vision labels that identify a photo as primarily about people
_PERSON_VISION_LABELS: frozenset[str] = frozenset({
    "person", "people", "human", "face", "man", "woman", "child",
    "boy", "girl", "gentleman", "lady", "crowd", "selfie",
})

# ---------------------------------------------------------------------------
# Section type → ordered list of preferred Vision photo categories
# The pool picks from Pass-1 categories first, then falls through.
# Cross-category exclusions: culinary sections NEVER get outdoor/rooms,
# outdoor sections NEVER get dining/rooms, etc.
# ---------------------------------------------------------------------------
_SECTION_TO_VISION_CATEGORIES: dict[str, list[str]] = {
    # Culinary: food/dining images ONLY — no fallback to other categories.
    "culinary":     [PHOTO_CAT_DINING],
    "outdoor":      [PHOTO_CAT_OUTDOOR, PHOTO_CAT_AMENITY],
    # Room Design: strictly indoor bedroom/bathroom — AMENITY removed because it
    # includes outdoor pool/terrace shots that are wrong for a room section.
    "room_design":  [PHOTO_CAT_ROOMS],
    # Connectivity: entrance/gate/road exterior ONLY — no outdoor nature shots.
    "connectivity": [PHOTO_CAT_EXTERIOR],
    "intro":        [PHOTO_CAT_EXTERIOR, PHOTO_CAT_OUTDOOR],
    "hospitality":  [PHOTO_CAT_EXTERIOR, PHOTO_CAT_ROOMS],
    "general":      [PHOTO_CAT_EXTERIOR, PHOTO_CAT_OUTDOOR, PHOTO_CAT_AMENITY],
}

# Strict exclusion — these categories MUST NOT appear in these sections.
# Blank photo beats an editorially wrong photo.
_SECTION_EXCLUDED_VISION_CATS: dict[str, frozenset[str]] = {
    # Culinary: ONLY dining photos — every other category is excluded.
    "culinary":     frozenset({PHOTO_CAT_ROOMS, PHOTO_CAT_OUTDOOR, PHOTO_CAT_EXTERIOR, PHOTO_CAT_AMENITY}),
    # Outdoor Spaces: never indoor (rooms) or food photos.
    "outdoor":      frozenset({PHOTO_CAT_DINING, PHOTO_CAT_ROOMS}),
    # Connectivity: entrance/gate/road only — no rooms, no food, and no generic
    # outdoor shots (bushes, vegetation) that are not about access/approach.
    "connectivity": frozenset({PHOTO_CAT_ROOMS, PHOTO_CAT_DINING, PHOTO_CAT_OUTDOOR, PHOTO_CAT_AMENITY}),
    # Room Design: strictly indoor — no outdoor cottage shots, no exterior facades,
    # no dining photos. Only bedroom/bathroom/interior photos are valid.
    "room_design":  frozenset({PHOTO_CAT_OUTDOOR, PHOTO_CAT_EXTERIOR, PHOTO_CAT_DINING}),
}


@dataclass
class _ClassifiedPhoto:
    """A photo that has been classified into a WishNest editorial category."""
    raw_url: str
    proxied_url: str
    serpapi_tags: list[str]
    vision_category: str    # one of the PHOTO_CAT_* constants or "unknown"
    quality_score: float    # 0.0–1.0 from Vision label confidence
    is_selfie: bool = False


def _classify_photo_vision_category(
    raw_url: str,
    serpapi_tags: list[str],
) -> tuple[str, float, bool]:
    """
    Classify a single photo into a WishNest editorial category.

    Priority order:
      1. Google Cloud Vision API labels (if GOOGLE_CLOUD_VISION_API_KEY is set)
      2. SerpApi category tags (fast, no extra API call)
      3. "unknown" (unclassified — treated as generic)

    Returns (category, quality_score, is_selfie).

    Never raises — Vision failures fall back to tag-based classification.
    """
    # ── Vision API (primary) ─────────────────────────────────────────────
    settings = get_settings()
    if raw_url and settings.google_cloud_vision_api_key:
        try:
            from app.services.vision_service import scan_image  # lazy import
            vr = scan_image(raw_url)
            if vr and vr.labels:
                label_names_scored = [(lb.description.lower(), lb.score) for lb in vr.labels]
                all_label_names = {n for n, _ in label_names_scored}

                # Check for selfie: top label is person AND a close-up body-part label present
                top_label = label_names_scored[0][0] if label_names_scored else ""
                if (
                    top_label in _PERSON_VISION_LABELS
                    and all_label_names & _SELFIE_VISION_LABELS
                ):
                    return "selfie", 0.0, True
                # If every top-3 label is person-related → selfie
                top3 = {n for n, _ in label_names_scored[:3]}
                if top3.issubset(_PERSON_VISION_LABELS | _SELFIE_VISION_LABELS):
                    return "selfie", 0.0, True

                # Score each category by summing matching label confidences
                cat_scores: dict[str, float] = {}
                for label_desc, score in label_names_scored:
                    cat = _VISION_LABEL_TO_CATEGORY.get(label_desc)
                    if cat:
                        cat_scores[cat] = cat_scores.get(cat, 0.0) + score

                # ── Quality gate (applied before category return) ─────────
                # Reject photos whose top-3 Vision labels are all unusable
                # indicators (dark, blurry, silhouetted).  A strong category
                # match overrides this gate — a well-lit pool that also has a
                # "shadow" label is still a usable pool photo.
                top3_names = {n for n, _ in label_names_scored[:3]}
                top_confidence = label_names_scored[0][1] if label_names_scored else 0.0
                all_top3_unusable = bool(top3_names) and top3_names.issubset(
                    _UNUSABLE_PHOTO_LABELS
                )

                if cat_scores:
                    best_cat = max(cat_scores, key=lambda c: cat_scores[c])
                    quality = min(1.0, cat_scores[best_cat])
                    # Even with a category match, hard-block if every visible
                    # label screams "completely dark / blurry".
                    if all_top3_unusable:
                        return "low_quality", 0.0, False
                    # ── People penalty (architecture preference) ─────────────
                    # Photos where people appear alongside the property content
                    # are down-ranked so clean architectural shots, pool photos,
                    # room interiors, and garden views surface first.  The photo
                    # is still usable — it just sorts lower in the quality-ranked
                    # bucket, giving preference to people-free property imagery.
                    people_present = bool(all_label_names & _PERSON_VISION_LABELS)
                    if people_present:
                        quality *= 0.45  # ~half-score penalty keeps it usable but deprioritised
                    return best_cat, quality, False

                # No editorial category matched — use top-label confidence as
                # a quality proxy.  Very low confidence means Vision saw mostly
                # noise (dark / blurry / low-res image).
                if all_top3_unusable or top_confidence < _MIN_UNCLASSIFIED_LABEL_CONFIDENCE:
                    return "low_quality", 0.0, False
                # Apply people penalty for unclassified photos with people in them
                if all_label_names & _PERSON_VISION_LABELS:
                    top_confidence *= 0.45
                return "unknown", top_confidence, False
        except Exception as exc:  # noqa: BLE001
            logger.debug("Vision classify failed for %s: %s", raw_url[:60], exc)

    # ── SerpApi tag fallback ─────────────────────────────────────────────
    if serpapi_tags:
        tag_set = {t.lower() for t in serpapi_tags}
        if tag_set & _PORTRAIT_PHOTO_TAG_TOKENS:
            return "selfie", 0.0, True
        if tag_set & _CULINARY_PHOTO_TAG_TOKENS:
            return PHOTO_CAT_DINING, 0.7, False
        if tag_set & _OUTDOOR_PHOTO_TAG_TOKENS:
            return PHOTO_CAT_OUTDOOR, 0.7, False
        if tag_set & _ROOM_INTERIOR_PHOTO_TAG_TOKENS:
            return PHOTO_CAT_ROOMS, 0.7, False
        if tag_set & _EXTERIOR_PHOTO_TAG_TOKENS:
            return PHOTO_CAT_EXTERIOR, 0.7, False
        return "unknown", 0.4, False

    return "unknown", 0.3, False


class SmartPhotoPool:
    """
    Vision-API-powered photo pool that classifies every photo by content
    category and enforces strict section–category matching.

    Construction:
      photos: list[{"url": str, "tags": list[str]}]  — from SerpApi gallery
      max_vision_calls: cap Vision API calls per pool build (default 25)

    Usage:
      pool.pick_for_section(section_type, used_urls) → (proxied_url, category) | None
      pool.pick_any(used_urls) → proxied_url | None

    Selfies and close-up portraits are filtered out during construction and
    are never returned by any pick method.
    """

    def __init__(
        self,
        photos: list[dict],
        max_vision_calls: int = 50,
    ) -> None:
        self._by_category: dict[str, list[_ClassifiedPhoto]] = {
            PHOTO_CAT_DINING:   [],
            PHOTO_CAT_ROOMS:    [],
            PHOTO_CAT_OUTDOOR:  [],
            PHOTO_CAT_AMENITY:  [],
            PHOTO_CAT_EXTERIOR: [],
            "unknown":          [],
        }
        self._used_proxied: set[str] = set()
        self._total = 0

        for i, photo in enumerate(photos):
            raw_url = photo.get("url", "")
            tags: list[str] = photo.get("tags") or []
            if not raw_url:
                continue

            proxied = _proxied_url(raw_url)
            safe = _safe_image_url(proxied)
            if not safe:
                continue

            # Only run Vision API on first max_vision_calls photos;
            # the rest get tag-only classification to keep latency manageable.
            classify_url = raw_url if i < max_vision_calls else ""
            cat, quality, is_selfie = _classify_photo_vision_category(classify_url, tags)

            if is_selfie or cat == "selfie":
                logger.debug("SmartPhotoPool: filtered selfie/portrait — %s", raw_url[:60])
                continue

            # Reject photos flagged as too dark, blurry, or low-resolution.
            # "low_quality" is returned by _classify_photo_vision_category when
            # Vision sees only darkness/blur/noise labels or extremely low
            # confidence — these images would degrade article visual quality.
            if cat == "low_quality":
                logger.debug(
                    "SmartPhotoPool: filtered low-quality/dark/blurry photo — %s",
                    raw_url[:60],
                )
                continue

            cp = _ClassifiedPhoto(
                raw_url=raw_url,
                proxied_url=proxied,
                serpapi_tags=tags,
                vision_category=cat,
                quality_score=quality,
            )
            self._by_category.setdefault(cat, []).append(cp)
            self._total += 1

        # Sort each bucket by quality score descending so best photos surface first
        for bucket in self._by_category.values():
            bucket.sort(key=lambda p: p.quality_score, reverse=True)

        logger.info(
            "SmartPhotoPool built: %d photos | dining=%d rooms=%d outdoor=%d "
            "amenity=%d exterior=%d unknown=%d",
            self._total,
            len(self._by_category[PHOTO_CAT_DINING]),
            len(self._by_category[PHOTO_CAT_ROOMS]),
            len(self._by_category[PHOTO_CAT_OUTDOOR]),
            len(self._by_category[PHOTO_CAT_AMENITY]),
            len(self._by_category[PHOTO_CAT_EXTERIOR]),
            len(self._by_category["unknown"]),
        )

    @property
    def available(self) -> bool:
        return self._total > 0

    def _unused(self, photo: _ClassifiedPhoto, global_used: set[str]) -> bool:
        """True when this photo has not been handed out yet (locally or globally)."""
        return (
            photo.proxied_url not in self._used_proxied
            and photo.proxied_url not in global_used
        )

    def pick_for_section(
        self,
        section_type: str,
        global_used: set[str] | None = None,
    ) -> tuple[str, str] | None:
        """
        Return (proxied_url, vision_category) for the best matching photo
        for *section_type*, or None if no suitable photo is available.

        Pass 1 — strict preferred category match for this section type.
        Pass 2 — "unknown" category (unclassified real photos).
        Pass 3 — any non-excluded category (for low-stakes sections only).

        Photos excluded by hard cross-category rules are NEVER returned
        (e.g. dining photos are never returned for outdoor sections).
        """
        avoid = global_used or set()
        preferred = _SECTION_TO_VISION_CATEGORIES.get(
            section_type, [PHOTO_CAT_EXTERIOR, PHOTO_CAT_OUTDOOR]
        )
        excluded = _SECTION_EXCLUDED_VISION_CATS.get(section_type, frozenset())

        # Pass 1: preferred categories, best quality first
        for cat in preferred:
            for photo in self._by_category.get(cat, []):
                if self._unused(photo, avoid):
                    self._used_proxied.add(photo.proxied_url)
                    logger.info(
                        "SmartPhotoPool: section=%r → cat=%r (q=%.2f)",
                        section_type, cat, photo.quality_score,
                    )
                    return photo.proxied_url, cat

        # Pass 2: unknown category (unclassified but real photos).
        # STRICT SECTIONS skip this pass entirely — these sections require
        # Vision-verified photo content.  An unclassified photo could be a
        # bedroom, a bathtub, a road, or a customer selfie; none are safe to
        # publish under a section that has a specific visual contract with the
        # reader.  Blank image beats a wrong image.
        #
        # "outdoor"     — must show nature/garden/pool; unknown could be any room.
        # "connectivity"— must show exterior/entrance; unknown could be a bedroom.
        # "culinary"    — must show food/dining; unknown could be anything.
        # "room_design" — must show an actual room; unknown could be outdoor scenery.
        _STRICT_CONTENT_SECTIONS: frozenset[str] = frozenset({
            "culinary", "room_design", "outdoor", "connectivity"
        })
        if section_type not in _STRICT_CONTENT_SECTIONS:
            for photo in self._by_category.get("unknown", []):
                if self._unused(photo, avoid):
                    self._used_proxied.add(photo.proxied_url)
                    logger.info(
                        "SmartPhotoPool: section=%r → unknown fallback (q=%.2f)",
                        section_type, photo.quality_score,
                    )
                    return photo.proxied_url, "unknown"

        # Pass 3: any non-excluded category (only for low-stakes sections)
        if section_type not in ("culinary", "outdoor", "room_design", "connectivity"):
            for cat, bucket in self._by_category.items():
                if cat in excluded or cat == "unknown":
                    continue
                for photo in bucket:
                    if self._unused(photo, avoid):
                        self._used_proxied.add(photo.proxied_url)
                        logger.info(
                            "SmartPhotoPool: section=%r → cross-cat fallback cat=%r",
                            section_type, cat,
                        )
                        return photo.proxied_url, cat

        # Pass 4 (Last Resort): section-specific fallback.
        #
        # Strict content sections have editorial contracts with the reader —
        # returning a wrong photo is worse than a blank slot:
        #
        #   "culinary"     — MUST be food/dining. No fallback at all; blank
        #                    section is editorially correct when no food photo
        #                    exists in the property's gallery.
        #   "connectivity" — MUST show entrance/gate/road. Only tries
        #                    PHOTO_CAT_EXTERIOR; if none available → blank.
        #   "room_design"  — MUST show indoor bedroom/bathroom. Only tries
        #                    PHOTO_CAT_ROOMS; if none available → blank.
        #   "outdoor"      — Acceptable to show exterior/amenity shots if no
        #                    garden/nature photo is found; never rooms or dining.
        #   Everything else — general last-resort order, never dining.

        if section_type == "culinary":
            # No food photo in pool → blank. Never substitute a room/outdoor shot.
            return None

        if section_type == "connectivity":
            # Only exterior photos are valid for access/getting-here sections.
            for photo in self._by_category.get(PHOTO_CAT_EXTERIOR, []):
                if self._unused(photo, avoid):
                    self._used_proxied.add(photo.proxied_url)
                    logger.info(
                        "SmartPhotoPool: section=%r → last-resort exterior (q=%.2f)",
                        section_type, photo.quality_score,
                    )
                    return photo.proxied_url, PHOTO_CAT_EXTERIOR
            # No exterior photo → blank connectivity section.
            return None

        if section_type == "room_design":
            # Only rooms photos are valid for room-design sections.
            for photo in self._by_category.get(PHOTO_CAT_ROOMS, []):
                if self._unused(photo, avoid):
                    self._used_proxied.add(photo.proxied_url)
                    logger.info(
                        "SmartPhotoPool: section=%r → last-resort rooms (q=%.2f)",
                        section_type, photo.quality_score,
                    )
                    return photo.proxied_url, PHOTO_CAT_ROOMS
            # No indoor room photo → blank room-design section.
            return None

        # For all other sections (outdoor, intro, hospitality, general, …):
        # prefer exterior/amenity, then anything except dining.
        _GENERAL_LAST_RESORT_ORDER = [
            PHOTO_CAT_EXTERIOR,
            PHOTO_CAT_AMENITY,
            PHOTO_CAT_OUTDOOR,
            PHOTO_CAT_ROOMS,
            "unknown",
        ]
        for cat in _GENERAL_LAST_RESORT_ORDER:
            for photo in self._by_category.get(cat, []):
                if self._unused(photo, avoid):
                    self._used_proxied.add(photo.proxied_url)
                    logger.info(
                        "SmartPhotoPool: section=%r → last-resort fallback cat=%r (q=%.2f)",
                        section_type, cat, photo.quality_score,
                    )
                    return photo.proxied_url, cat

        # Pool fully exhausted for this article
        return None

    def pick_any(self, global_used: set[str] | None = None) -> str | None:
        """Return any available photo (for padding / hero fallback)."""
        avoid = global_used or set()
        all_photos: list[_ClassifiedPhoto] = []
        for bucket in self._by_category.values():
            all_photos.extend(bucket)
        all_photos.sort(key=lambda p: p.quality_score, reverse=True)
        for photo in all_photos:
            if self._unused(photo, avoid):
                self._used_proxied.add(photo.proxied_url)
                return photo.proxied_url
        return None

    def category_breakdown(self) -> dict[str, int]:
        return {cat: len(bucket) for cat, bucket in self._by_category.items()}


def _build_smart_pool_for_listing(
    listing: PropertyListing,
    max_photos: int = 75,
) -> SmartPhotoPool | None:
    """
    Fetch the full Google Maps photo gallery for *listing* (via SerpApi's
    google_maps_photos engine using the listing's data_id / place_id) and
    return a SmartPhotoPool ready for section-level selection.

    Returns None when:
      - No SerpApi key is configured.
      - The listing has no data_id (only happens when a listing was sourced
        from a context that doesn't supply data_ids, e.g. pre-fetched listings
        without enrichment).
      - SerpApi returns an empty gallery.
    """
    data_id = getattr(listing, "place_id", None)
    api_key = get_settings().serpapi_key
    if not data_id or not api_key:
        return None

    tagged = _serpapi_maps_photos_gallery(data_id, api_key, max_photos=max_photos)
    if not tagged:
        # Fall back to the single thumbnail the listing already carries
        if listing.photo_url:
            tagged = [{"url": listing.photo_url, "tags": []}]
        else:
            return None

    return SmartPhotoPool(tagged)


def _build_smart_pool_from_listing_photos(listing: PropertyListing) -> SmartPhotoPool | None:
    """
    Build a SmartPhotoPool from the photo_urls + photo_tags already stored on a
    PropertyListing (i.e. from the _SinglePropertyPhotoPool source). Used for
    the single-property (review) path where the gallery was fetched during
    `fetch_property_by_name()`.
    """
    raw_urls: list[str] = getattr(listing, "photo_urls", None) or []
    raw_tags: list[list[str]] = getattr(listing, "photo_tags", None) or [[] for _ in raw_urls]
    if listing.photo_url and not raw_urls:
        raw_urls = [listing.photo_url]
        raw_tags = [[]]

    photos = [
        {"url": url, "tags": tags}
        for url, tags in zip(raw_urls, raw_tags)
        if url
    ]
    if not photos:
        return None

    return SmartPhotoPool(photos)


def _smart_pool_caption_label(vision_category: str) -> str:
    """Human-readable caption prefix from a Vision photo category."""
    return {
        PHOTO_CAT_DINING:   "Culinary experience",
        PHOTO_CAT_ROOMS:    "Room and amenities",
        PHOTO_CAT_OUTDOOR:  "Outdoor spaces",
        PHOTO_CAT_AMENITY:  "Amenities and experience",
        PHOTO_CAT_EXTERIOR: "Exterior view",
        "unknown":          "",
    }.get(vision_category, "")


# ---------------------------------------------------------------------------


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
    "general":       "",
}


def _caption_prefix_from_actual_tags(tags: list[str]) -> str | None:
    """
    Derive the most accurate caption prefix from the *actual* tags of the
    chosen photo (either SerpApi category tags or Vision category labels).

    Priority (most specific first):
      0. Direct Vision-category label  → pass through unchanged
      1. Bathroom / bathtub / plumbing → "Bathroom and amenities"
      2. Pool / outdoor / garden       → "Outdoor spaces"
      3. Food / dining / kitchen       → "Culinary experience"
      4. Bedroom / room / suite        → "Room and amenities"
      5. Exterior / facade / entrance  → "Exterior view"

    Returns None when tags are empty or unrecognisable — the caller then
    falls back to the section-type-derived prefix from _SECTION_CAPTION_PREFIX.
    """
    if not tags:
        return None

    # Pass 0: tags may already be human-readable Vision category labels
    # (e.g. "Culinary experience", "Outdoor spaces") — return them directly.
    _VISION_LABEL_PASSTHROUGH: dict[str, str] = {
        "culinary experience":       "Culinary experience",
        "room and amenities":        "Room and amenities",
        "outdoor spaces":            "Outdoor spaces",
        "amenities and experience":  "Amenities and experience",
        "exterior view":             "Exterior view",
        "property feature":          "",
        "bathroom and amenities":    "Bathroom and amenities",
    }
    for tag in tags:
        result = _VISION_LABEL_PASSTHROUGH.get(tag.lower())
        if result:
            return result

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
        #   1. Derive from the photo's actual SerpApi / Vision tags (most accurate).
        #   2. Fall back to the section-type-derived label ONLY when actual_tags
        #      is completely empty (i.e. no tag information whatsoever). When
        #      tags are non-empty but unrecognised, use an empty prefix so the
        #      caption shows just the heading — this prevents a bedroom photo from
        #      being mislabelled "Exterior view" because it landed in an intro slot.
        caption_prefix = _caption_prefix_from_actual_tags(actual_tags)
        if caption_prefix is None:
            if not actual_tags:
                # Truly no tag information — fall back to section-type label.
                section_type_for_caption = _classify_section(heading_text)
                caption_prefix = _SECTION_CAPTION_PREFIX.get(section_type_for_caption, "")
            else:
                # Tags present but unrecognised — don't guess; show heading only.
                caption_prefix = ""
        # Only prepend the prefix when it adds information; never emit the bare
        # "Property feature" label that was previously used as a generic fallback.
        if caption_prefix:
            caption = html.escape(f"{caption_prefix} — {heading_text[:60]}", quote=False)
        else:
            caption = html.escape(heading_text[:60], quote=False)

        figure = _FIGURE_TEMPLATE.format(url=safe_url, alt=alt, caption=caption)
        return full_match + "\n" + figure

    return _HEADING_RE.sub(_replace_heading, full_article_html)


# ---------------------------------------------------------------------------
# Deep gallery URL helpers
# ---------------------------------------------------------------------------

def _decode_proxy_url(proxied_url: str) -> str | None:
    """
    Decode a ``/api/image-proxy?url=<encoded>`` URL back to the original
    upstream URL so it can be re-submitted to the Vision API.
    Returns the URL unchanged when it is already a direct http(s) URL.
    """
    if not proxied_url:
        return None
    prefix = "/api/image-proxy?url="
    if proxied_url.startswith(prefix):
        return urllib.parse.unquote(proxied_url[len(prefix):])
    return proxied_url


def build_deep_gallery_photo_assignments(
    listing: "PropertyListing",
    section_types: list[str],
) -> list[dict]:
    """
    Pre-assign the best unique photo from a property's deep gallery (75+ photos)
    to each requested editorial section type, then Vision-scan each assigned photo
    to get its exact Google Cloud Vision labels.

    This is called by the research pipeline BEFORE article text is drafted so the
    LLM can write each section paragraph to match its specific pre-assigned photo.

    Returns a list of dicts in input order::

        [
          {
            "section_type": str,   # e.g. "culinary"
            "url": str,            # proxied URL for frontend rendering
            "raw_url": str,        # original URL for Vision re-scanning
            "category": str,       # one of the PHOTO_CAT_* constants or "unknown"
            "vision_labels": list[str],  # top-8 Vision API label descriptions
          },
          ...
        ]

    Gracefully degrades: returns an empty list when the pool is unavailable,
    SERPAPI_KEY is not configured, or every Vision API call fails.
    Never raises.
    """
    # Build pool from already-fetched gallery photos stored on the listing;
    # if only a thumbnail exists, fall back to a fresh gallery fetch.
    pool = _build_smart_pool_from_listing_photos(listing)
    if pool is None or not pool.available:
        pool = _build_smart_pool_for_listing(listing, max_photos=75)
    if pool is None or not pool.available:
        return []

    used: set[str] = set()
    settings = get_settings()
    results: list[dict] = []

    for section_type in section_types:
        pick = pool.pick_for_section(section_type, used)
        if pick is not None:
            url, cat = pick
        else:
            # Any unused photo beats an empty slot for LLM grounding purposes.
            url = pool.pick_any(used)
            cat = "unknown"
            if url is None:
                continue
        used.add(url)

        raw_url = _decode_proxy_url(url) or url
        vision_labels: list[str] = []

        if raw_url and settings.google_cloud_vision_api_key:
            try:
                from app.services.vision_service import scan_image  # lazy import
                vr = scan_image(raw_url)
                if vr and vr.labels:
                    vision_labels = [lb.description for lb in vr.labels[:8]]
            except Exception as exc:  # noqa: BLE001
                logger.debug(
                    "Vision scan failed for deep gallery photo %s: %s",
                    raw_url[:60], exc,
                )

        results.append({
            "section_type": section_type,
            "url": url,
            "raw_url": raw_url,
            "category": cat,
            "vision_labels": vision_labels,
        })

    return results


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
    pre_fetched_listings: list | None = None,
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

        # ── Build SmartPhotoPool from the property's fetched gallery ──────────
        # SmartPhotoPool classifies every photo via Vision API (or SerpApi tags
        # as fallback), filters selfies, and enforces strict section–category
        # matching. This replaces the old tag-only routing.
        smart_pool = _build_smart_pool_from_listing_photos(single_pool.listing)
        if smart_pool is None or not smart_pool.available:
            # Fallback: build from the single thumbnail if gallery data absent
            if single_pool.listing.photo_url:
                smart_pool = SmartPhotoPool(
                    [{"url": single_pool.listing.photo_url, "tags": []}]
                )
        logger.info(
            "SmartPhotoPool built for single-property %r: %s",
            property_name, smart_pool.category_breakdown() if smart_pool else "empty",
        )

        # Hero: prefer exterior/facade shot for the article header
        hero_url: str | None = None
        if smart_pool and smart_pool.available:
            hero_url = smart_pool.pick_any(used_urls)
            if hero_url:
                used_urls.add(hero_url)

        logger.info(
            "Hero image resolved for %r: %s",
            headline[:60], "found" if hero_url else "not found",
        )

        section_urls = []
        heading_images: list[tuple[str, str, list[str]]] = []
        slots = full_article_headings if full_article_headings else ["exterior view", "interior ambiance"]
        pool_fill_count = 0

        for slot in slots:
            section_type = _classify_section(slot)
            url: str | None = None
            vision_cat = "unknown"

            if smart_pool and smart_pool.available:
                result = smart_pool.pick_for_section(section_type, used_urls)
                if result is not None:
                    url, vision_cat = result
                    if url:
                        used_urls.add(url)
                        pool_fill_count += 1
                        logger.info(
                            "Section %r (type=%r) → Vision cat=%r",
                            slot[:50], section_type, vision_cat,
                        )
                else:
                    # STRICT CULINARY FALLBACK: never substitute a nature/room photo
                    # for a food section. Use a verified food placeholder so the
                    # dining heading always shows food imagery. Blank beats wrong,
                    # but a food placeholder beats blank for editorial continuity.
                    if section_type == "culinary":
                        fallback = _food_fallback_url(used_urls)
                        url = fallback
                        used_urls.add(fallback)
                        vision_cat = PHOTO_CAT_DINING
                        logger.info(
                            "Section %r (culinary) → no verified food photo in SmartPool; "
                            "using food placeholder.",
                            slot[:50],
                        )
                    else:
                        logger.warning(
                            "Section %r (type=%r) → no matching photo in SmartPool, slot left blank.",
                            slot[:50], section_type,
                        )

            section_urls.append(url)
            if full_article_headings:
                # Pass vision_category as a single-element "tag list" so the
                # caption generator can use it via _smart_pool_caption_label.
                heading_images.append((slot, url, [vision_cat]))

        logger.info(
            "SmartPhotoPool filled %d/%d section slot(s) for %r",
            pool_fill_count, len(slots), property_name,
        )

        # -- Pad with extra real photos up to MIN_SINGLE_PROPERTY_IMAGES --
        total_so_far = (1 if hero_url else 0) + sum(1 for u in section_urls if u)
        padded_count = 0
        if smart_pool:
            while total_so_far < MIN_SINGLE_PROPERTY_IMAGES:
                padded_url = smart_pool.pick_any(used_urls)
                if padded_url is None:
                    break
                used_urls.add(padded_url)
                section_urls.append(padded_url)
                total_so_far += 1
                padded_count += 1
        if padded_count:
            logger.info(
                "Padded %r with %d extra real photo(s) to reach %d-image floor.",
                property_name, padded_count, MIN_SINGLE_PROPERTY_IMAGES,
            )

        property_matches = [_property_match_dict(single_pool.listing)]

        # HTML injection with Vision-derived captions
        injected_count = sum(1 for _, u, _t in heading_images if u)
        enriched_html: str | None = None
        if full_article and heading_images:
            # Build (heading, url, caption_prefix_as_tag) tuples for injection.
            # _inject_images_into_html uses the tag list to derive captions;
            # we pass the Vision category so _caption_prefix_from_actual_tags
            # picks the right label.
            _hi_for_inject = [
                (h, u, [_smart_pool_caption_label(t[0]) if t else ""])
                for h, u, t in heading_images
            ]
            try:
                enriched_html = _inject_images_into_html(full_article, _hi_for_inject)
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
    # couldn't be verified against a live provider.
    #
    # KEY DESIGN: when pre_fetched_listings are supplied (from the research
    # pipeline, which already injected those property names into the OpenAI
    # brief), we use NAME-MATCHING to assign each section's image to the
    # exact property that section was written about.  This ensures the image
    # and the article text always describe the same real business.
    # -------------------------------------------------------------------

    # -- Build the authoritative list of available listings -----------------
    # Prefer the pre-fetched set (already used to shape the OpenAI brief);
    # fall back to a fresh SerpApi query if none were pre-fetched.
    expected_slots = 1 + (len(full_article_headings) if full_article_headings else 2)
    _landmark = _is_landmark_category(category)

    all_listings: list = []

    if pre_fetched_listings:
        all_listings = list(pre_fetched_listings)
        logger.info(
            "Multi-property path: using %d pre-fetched listings for %r",
            len(all_listings), headline[:60],
        )
    elif _landmark:
        lm_pool = _LandmarkPool(location, limit=max(expected_slots + 3, 12))
        all_listings = lm_pool.listings
        logger.info(
            "Multi-property path: landmark pool (%d) for category=%r article %r",
            len(all_listings), category, headline[:60],
        )
    else:
        lp = _LivePropertyPool(location, limit=max(expected_slots + 3, 12))
        all_listings = lp.listings
        logger.info(
            "Multi-property path: live pool (%d listings) for %r",
            len(all_listings), headline[:60],
        )

    # -- Internal state for de-duplication and tracking ---------------------
    _assigned_indices: set[int] = set()
    _used_listings: list = []

    # Per-listing SmartPhotoPool cache (keyed by listing index) — avoids
    # fetching the same gallery multiple times within one article generation.
    _listing_smart_pools: dict[int, SmartPhotoPool | None] = {}

    def _get_or_build_smart_pool(listing_idx: int) -> SmartPhotoPool | None:
        """Build (or retrieve cached) SmartPhotoPool for the listing at index."""
        if listing_idx in _listing_smart_pools:
            return _listing_smart_pools[listing_idx]
        listing = all_listings[listing_idx]
        pool = _build_smart_pool_for_listing(listing, max_photos=75)
        if pool is None and getattr(listing, "photo_url", None):
            # Fallback: single-thumbnail pool (no gallery available)
            pool = SmartPhotoPool([{"url": listing.photo_url, "tags": []}])
        _listing_smart_pools[listing_idx] = pool
        return pool

    def _take_by_name_smart(heading_text: str, section_type: str):
        """
        Find a listing whose name appears in *heading_text*, fetch its full
        gallery, build a SmartPhotoPool, and pick the best-matching photo for
        *section_type*. Returns (proxied_url, listing, vision_cat) or None.
        """
        heading_lower = heading_text.lower()
        for i, listing in enumerate(all_listings):
            if i in _assigned_indices:
                continue
            name_lower = listing.name.lower()
            if name_lower not in heading_lower:
                continue
            pool = _get_or_build_smart_pool(i)
            if pool is None or not pool.available:
                continue
            result = pool.pick_for_section(section_type, used_urls)
            if result is not None:
                url, vision_cat = result
                _assigned_indices.add(i)
                used_urls.add(url)
                _used_listings.append(listing)
                logger.info(
                    "Name-matched %r → listing %r → Vision cat=%r",
                    heading_text[:50], listing.name, vision_cat,
                )
                return url, listing, vision_cat
            # Listing matched by name but its pool has no suitable photo for
            # this section type → do NOT block; try next name-matched listing.
        return None

    def _take_sequential_smart(section_type: str):
        """
        Pick the next unused listing in order, build/reuse its SmartPhotoPool,
        and return the best-matching photo for *section_type*.
        Returns (proxied_url, listing, vision_cat) or None when exhausted.
        """
        for i, listing in enumerate(all_listings):
            if i in _assigned_indices:
                continue
            pool = _get_or_build_smart_pool(i)
            if pool is None or not pool.available:
                continue
            result = pool.pick_for_section(section_type, used_urls)
            if result is not None:
                url, vision_cat = result
                _assigned_indices.add(i)
                used_urls.add(url)
                _used_listings.append(listing)
                return url, listing, vision_cat
        return None

    # -- Hero image ----------------------------------------------------------
    hero_url: str | None = None
    hero_result = _take_by_name_smart(headline, "intro") or _take_sequential_smart("intro")
    if hero_result is not None:
        hero_url, hero_listing, _hero_cat = hero_result
        logger.info(
            "Hero image resolved from Google Maps listing %r (%.1f★) for %r",
            hero_listing.name, hero_listing.rating or 0.0, headline[:60],
        )
    else:
        logger.warning(
            "No Google Maps photo available for hero slot of %r — leaving blank.",
            headline[:60],
        )

    # -- Section images — one per heading, with name-matching + SmartPool ---
    section_urls: list[str | None] = []
    heading_images: list[tuple[str, str, list[str]]] = []

    if full_article_headings:
        logger.info("Extracted %d headings from article %r", len(full_article_headings), headline[:50])

        for heading in full_article_headings:
            url: str | None = None
            vision_cat = "unknown"

            section_type = _classify_section(heading)
            slot_result = (
                _take_by_name_smart(heading, section_type)
                or _take_sequential_smart(section_type)
            )
            if slot_result is not None:
                url, matched_listing, vision_cat = slot_result
                logger.info(
                    "Section %r (type=%r) → listing %r vision_cat=%r",
                    heading[:50], section_type, matched_listing.name, vision_cat,
                )
            else:
                # STRICT CULINARY FALLBACK: never leave a food section with a
                # nature/room/generic photo. Use a verified food placeholder.
                if section_type == "culinary":
                    fallback = _food_fallback_url(used_urls)
                    url = fallback
                    used_urls.add(fallback)
                    vision_cat = PHOTO_CAT_DINING
                    logger.info(
                        "Section %r (culinary) → Google Maps pool exhausted for food photos; "
                        "using verified food placeholder.",
                        heading[:50],
                    )
                else:
                    logger.warning("Section %r → pool exhausted, slot blank.", heading[:50])

            section_urls.append(url)
            heading_images.append((heading, url, [_smart_pool_caption_label(vision_cat)]))

    else:
        for section_type in ("intro", "general"):
            url = None
            slot_result = _take_sequential_smart(section_type)
            if slot_result:
                url, _, vc = slot_result
                heading_images.append(("", url, [_smart_pool_caption_label(vc)]))
            section_urls.append(url)

    # -- Minimum 10 real images floor ---------------------------------------
    MIN_MULTI_PROPERTY_IMAGES = 10
    total_so_far = (1 if hero_url else 0) + sum(1 for u in section_urls if u)
    while total_so_far < MIN_MULTI_PROPERTY_IMAGES:
        extra_result = _take_sequential_smart("general")
        if extra_result is None:
            break
        extra_url, _, _ = extra_result
        section_urls.append(extra_url)
        total_so_far += 1
    if total_so_far < MIN_MULTI_PROPERTY_IMAGES:
        logger.info(
            "Could only source %d/%d images for %r — Google Maps pool exhausted.",
            total_so_far, MIN_MULTI_PROPERTY_IMAGES, headline[:60],
        )

    property_matches = [_property_match_dict(l) for l in _used_listings]

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

    # Strip None entries — Pydantic's list[str] rejects None in the ARRAY col.
    section_urls_clean: list[str] = [u for u in section_urls if u is not None]

    # Final hero-URL sanity check.
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
