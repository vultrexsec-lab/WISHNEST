"""
Google Maps-only image pipeline for WishNest articles.

Every photo displayed in a WishNest article comes EXCLUSIVELY from the
specific property's own Google Maps photo gallery, fetched via SerpApi's
google_maps_photos engine.  No external image sources (DuckDuckGo, Pexels,
Unsplash, OpenAI, Picsum, or any other provider) are ever used.

Source hierarchy
----------------
1. SerpApi google_maps_photos gallery — full property gallery keyed by the
   Google Maps data_id (place_id) for the exact named business.
2. The single thumbnail photo already stored on the PropertyListing object
   (same source, already fetched during the initial Places lookup).

Fallback rule (100% property-only)
-----------------------------------
If a section type (e.g. "culinary") has no exact-match photo in the pool,
another high-quality real photo from the same property gallery is used instead
(exterior, balcony, outdoor area, lobby, etc.).  A real property photo is
always preferable to a blank slot and infinitely preferable to a stock image
or AI-generated render from an unrelated source.

A slot is only left blank when the property's entire photo gallery has been
exhausted for this article.  This is rare for galleries with 20+ photos.

All returned URLs are rewritten to go through our own `/api/image-proxy`
route so that:
  - Hotlinking/referrer restrictions on the origin CDN never break the
    published article (we fetch server-side and re-serve the bytes).
  - The frontend never depends on a third-party image host's uptime.
"""
import html
import logging
import re
import urllib.parse

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
# NOTE: All external image sources (Unsplash, Pexels, DuckDuckGo, OpenAI,
# Picsum, etc.) have been removed. Every photo in WishNest articles comes
# exclusively from the specific property's own Google Maps photo gallery,
# fetched via SerpApi's google_maps_photos engine. No stock images, no
# AI-generated renders, no images from rival properties or unrelated sources.
# ---------------------------------------------------------------------------


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
    (`available` is False) and callers leave the slot blank rather than
    substituting a photo from an unrelated external source — a blank section
    is always preferable to a hotel photo appearing on a monument article.
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
    "tent", "tents", "camp", "campsite", "camping", "glamping",
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

# Strict BEDROOM-only tokens for room_design sections.
# Bathroom/washroom/toilet tokens removed — those go to _BATHROOM_PHOTO_TAG_TOKENS
# and are explicitly EXCLUDED from room_design sections.
_ROOM_DESIGN_PHOTO_TAG_TOKENS: frozenset[str] = frozenset({
    "rooms", "room", "bedroom", "suite", "accommodation",
    "living room", "interior", "bed", "bedding",
})

# SerpApi tag tokens that identify bathroom / WC photos.
# Used to classify them into PHOTO_CAT_BATHROOM and exclude from room_design.
_BATHROOM_PHOTO_TAG_TOKENS: frozenset[str] = frozenset({
    "bathroom", "washroom", "restroom", "toilet", "shower", "bathtub",
    "lavatory", "wc", "sink", "plumbing", "bath", "shower room",
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
        # Culinary: ONLY food/dining/plated photos. Portrait, room interior,
        # outdoor, exterior, and bathroom all excluded. A pool or bedroom
        # photo must never appear under "Culinary Delights".
        return (
            _CULINARY_PHOTO_TAG_TOKENS,
            _PORTRAIT_PHOTO_TAG_TOKENS | _ROOM_INTERIOR_PHOTO_TAG_TOKENS
            | _OUTDOOR_PHOTO_TAG_TOKENS | _EXTERIOR_PHOTO_TAG_TOKENS
            | _BATHROOM_PHOTO_TAG_TOKENS,
        )
    if section_type == "connectivity":
        # Connectivity / Amenities: entrance, gate, road, lounge, game room,
        # reception, or parking. Outdoor nature and kitchen excluded.
        return (
            _CONNECTIVITY_PHOTO_TAG_TOKENS
            | frozenset({"lounge", "reception", "lobby", "parking", "game room",
                         "games room", "billiards", "snooker", "ping pong"}),
            _PORTRAIT_PHOTO_TAG_TOKENS | _CULINARY_PHOTO_TAG_TOKENS
            | _ROOM_INTERIOR_PHOTO_TAG_TOKENS | _OUTDOOR_PHOTO_TAG_TOKENS
            | _BATHROOM_PHOTO_TAG_TOKENS,
        )
    if section_type in ("intro", "general"):
        # Introduction / Conclusion: exterior/facade first; never kitchen,
        # portrait, room interior, or bathroom.
        return (
            _EXTERIOR_PHOTO_TAG_TOKENS | _OUTDOOR_PHOTO_TAG_TOKENS,
            _PORTRAIT_PHOTO_TAG_TOKENS | _CULINARY_PHOTO_TAG_TOKENS
            | _ROOM_INTERIOR_PHOTO_TAG_TOKENS | _BATHROOM_PHOTO_TAG_TOKENS,
        )
    if section_type == "outdoor":
        # Outdoor Spaces: garden/pool preferred; NEVER portrait, kitchen,
        # room interior, or bathroom.
        return (
            _OUTDOOR_PHOTO_TAG_TOKENS | _EXTERIOR_PHOTO_TAG_TOKENS,
            _PORTRAIT_PHOTO_TAG_TOKENS | _CULINARY_PHOTO_TAG_TOKENS
            | _ROOM_INTERIOR_PHOTO_TAG_TOKENS | _BATHROOM_PHOTO_TAG_TOKENS,
        )
    if section_type == "hospitality":
        # Guest Experience: lobby/entrance/facade preferred — but deliberately
        # NOT pool/garden/terrace so outdoor photos remain for Outdoor sections.
        return (
            _HOSPITALITY_PREFERRED_PHOTO_TAG_TOKENS,
            _CULINARY_PHOTO_TAG_TOKENS | _ROOM_INTERIOR_PHOTO_TAG_TOKENS
            | _BATHROOM_PHOTO_TAG_TOKENS,
        )
    if section_type == "room_design":
        # Room Design: STRICTLY bedroom interiors — bed, furniture, interior.
        # Bathroom/toilet/shower, outdoor, exterior, and kitchen ALL excluded.
        # "STRICTLY NO washroom/toilet pictures in Room Design."
        return (
            _ROOM_DESIGN_PHOTO_TAG_TOKENS,
            _PORTRAIT_PHOTO_TAG_TOKENS | _CULINARY_PHOTO_TAG_TOKENS
            | _OUTDOOR_PHOTO_TAG_TOKENS | _EXTERIOR_PHOTO_TAG_TOKENS
            | _BATHROOM_PHOTO_TAG_TOKENS,
        )
    # Catch-all: no strong preference; exclude portraits, kitchen, and bathroom.
    return (
        frozenset(),
        _PORTRAIT_PHOTO_TAG_TOKENS | _CULINARY_PHOTO_TAG_TOKENS | _BATHROOM_PHOTO_TAG_TOKENS,
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
            self.listing = fetch_property_by_name(headline, location, max_photos=100)
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
        *section_type* using tag-based smart routing, or None ONLY when the
        pool is completely exhausted (all photos already used).

        Strategy — always fill, never blank:
          Pass 1  — preferred tags present AND no excluded tags.
          Pass 2  — no excluded tags at all (neutral / untagged photo).
          Pass 3  — visually attractive alternative: exterior → outdoor →
                    garden/pool/terrace/common-area tags, skipping only the
                    single hardest content mismatch for this section.
          Pass 4  — absolute last resort: any remaining unused property photo.
                    A real photo from the property gallery always beats a blank.

        Strict rejections (handled upstream, before photos enter the pool):
          • Extremely dark / blurry images → filtered in _hand_out / SerpApi stage.
          • Close-up guest selfies / portraits → excluded by tag or Vision API.
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

        # Pass 2: any photo with no excluded tags (untagged counts as neutral).
        for i, (_, tags) in enumerate(self._photos):
            if i in self._used:
                continue
            if not (set(tags) & exclude):
                return self._hand_out(i)

        # Pass 3: smart visual fallback — attractive property photos preferred.
        # Priority: exterior façade/entrance → outdoor garden/pool/terrace →
        # common-area / amenity → any other tagged photo.
        # Hard skips prevent the worst editorial mismatches per section type.
        _APPEAL_PREFER = (
            _EXTERIOR_PHOTO_TAG_TOKENS
            | _OUTDOOR_PHOTO_TAG_TOKENS
            | frozenset({"pool", "terrace", "patio", "garden", "courtyard",
                         "lobby", "lounge", "reception", "common area"})
        )

        # Per-section hard skips: all tag tokens that must NEVER appear for
        # that section type, even in the "attractive fallback" pass.
        #
        # room_design: strictly indoor — ALL outdoor / exterior tokens blocked.
        #   Outdoor lawn, cottage exterior, garden, or pool photos must never
        #   appear under "Room Design and Comfort" even as a last-resort fallback.
        #
        # culinary: ALL building-exterior / landscape tokens blocked.
        #   When no food photo exists, indoor seating / amenity photos are
        #   preferred (handled by _APPEAL_PREFER tokens that remain: lobby,
        #   lounge, reception, courtyard, terrace, patio, pool). Only pure
        #   exterior facade and nature-landscape tokens are hard-blocked here
        #   so that a terrace-dining photo can still surface as a culinary
        #   stand-in, but a shot of the building front or a mountain valley
        #   can never be shown under a "Culinary Delights" section.
        _HARD_SKIP: dict[str, frozenset[str]] = {
            "outdoor": frozenset({
                "bedroom", "bed", "bathtub", "toilet", "shower",
            }),
            "room_design": frozenset(
                # Block every outdoor / exterior token so lawn, cottage
                # exterior, and garden photos never land in room sections.
                _OUTDOOR_PHOTO_TAG_TOKENS
                | _EXTERIOR_PHOTO_TAG_TOKENS
                | frozenset({"street", "road", "parking", "scenic",
                             "panoramic view", "landscape", "valley",
                             "forest", "nature", "greenery", "lawn",
                             "grounds", "approach", "scenic view"})
            ),
            "culinary": frozenset({
                "bedroom", "bed",
                # Hard-block exterior building / facade tokens for culinary.
                # Terrace, patio, courtyard are NOT blocked — they can be
                # legitimate outdoor-dining seating areas.
                "exterior", "outside", "outside view", "building", "facade",
                "front of property", "outside of building", "property exterior",
                "street view", "approach", "driveway", "gate", "gate house",
                # Large-landscape / pure-nature tokens — never culinary.
                "landscape", "valley", "forest", "nature", "greenery",
                "lawn", "grounds", "panoramic view", "scenic",
            }),
        }
        hard_skip = _HARD_SKIP.get(section_type, frozenset())

        for i, (_, tags) in enumerate(self._photos):
            if i in self._used:
                continue
            tag_set = set(tags)
            if tag_set & hard_skip:
                continue
            if tag_set & _APPEAL_PREFER:
                return self._hand_out(i)

        # Pass 4: absolute last resort — any unused property photo.
        # A real photo from this property, however imperfect, beats a blank slot.
        for i in range(len(self._photos)):
            if i not in self._used:
                return self._hand_out(i)

        # Pool fully exhausted — every photo already assigned to another section.
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
# 6 canonical photo categories used throughout WishNest editorial articles
# ---------------------------------------------------------------------------
PHOTO_CAT_DINING    = "dining_food"           # Local dishes, dining area, kitchen, plated food
PHOTO_CAT_ROOMS     = "rooms_stay"            # Bedrooms, bed interiors — NOT bathrooms
PHOTO_CAT_BATHROOM  = "bathroom_wc"           # Toilet, shower, bathtub — excluded from Room Design
PHOTO_CAT_OUTDOOR   = "outdoor_views"         # Gardens, mountains, landscape, pool, nature
PHOTO_CAT_AMENITY   = "amenities_experience"  # Game room, lounge, reception, spa, terrace, deck
PHOTO_CAT_EXTERIOR  = "exterior_architecture" # Building facade, entrance, aerial view

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
    # ── Rooms & Stay (bedroom interiors ONLY — bathrooms are separate) ─────
    "bedroom": PHOTO_CAT_ROOMS, "bed": PHOTO_CAT_ROOMS, "pillow": PHOTO_CAT_ROOMS,
    "room": PHOTO_CAT_ROOMS, "suite": PHOTO_CAT_ROOMS, "mattress": PHOTO_CAT_ROOMS,
    "sofa": PHOTO_CAT_ROOMS, "furniture": PHOTO_CAT_ROOMS,
    "interior design": PHOTO_CAT_ROOMS, "ceiling": PHOTO_CAT_ROOMS, "floor": PHOTO_CAT_ROOMS,
    "closet": PHOTO_CAT_ROOMS, "wardrobe": PHOTO_CAT_ROOMS,
    "curtain": PHOTO_CAT_ROOMS, "nightstand": PHOTO_CAT_ROOMS, "lamp": PHOTO_CAT_ROOMS,
    "accommodation": PHOTO_CAT_ROOMS, "lodging": PHOTO_CAT_ROOMS,
    # ── Bathroom / WC (separate category — excluded from Room Design) ──────
    # Mapping these to PHOTO_CAT_BATHROOM prevents toilet/shower photos from
    # being assigned to "Room Design and Comfort" article sections.
    "bathroom": PHOTO_CAT_BATHROOM, "bathtub": PHOTO_CAT_BATHROOM,
    "shower": PHOTO_CAT_BATHROOM, "toilet": PHOTO_CAT_BATHROOM,
    "towel": PHOTO_CAT_BATHROOM, "sink": PHOTO_CAT_BATHROOM,
    "plumbing fixture": PHOTO_CAT_BATHROOM, "faucet": PHOTO_CAT_BATHROOM,
    "bidet": PHOTO_CAT_BATHROOM, "washroom": PHOTO_CAT_BATHROOM,
    "restroom": PHOTO_CAT_BATHROOM, "lavatory": PHOTO_CAT_BATHROOM,
    "plumbing": PHOTO_CAT_BATHROOM, "drain": PHOTO_CAT_BATHROOM,
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
    # ── Amenities & Experience (game room, lounge, reception, pool, spa) ───
    "swimming pool": PHOTO_CAT_AMENITY, "pool": PHOTO_CAT_AMENITY,
    "spa": PHOTO_CAT_AMENITY, "gym": PHOTO_CAT_AMENITY, "fitness centre": PHOTO_CAT_AMENITY,
    "terrace": PHOTO_CAT_AMENITY, "balcony": PHOTO_CAT_AMENITY, "deck": PHOTO_CAT_AMENITY,
    "patio": PHOTO_CAT_AMENITY, "jacuzzi": PHOTO_CAT_AMENITY, "hot tub": PHOTO_CAT_AMENITY,
    "yoga": PHOTO_CAT_AMENITY, "wellness": PHOTO_CAT_AMENITY, "sauna": PHOTO_CAT_AMENITY,
    "recreation": PHOTO_CAT_AMENITY, "leisure": PHOTO_CAT_AMENITY, "courtyard": PHOTO_CAT_AMENITY,
    "infinity pool": PHOTO_CAT_AMENITY, "rooftop": PHOTO_CAT_AMENITY,
    # Game room / indoor activities — valid for Connectivity / Amenities sections
    "billiards": PHOTO_CAT_AMENITY, "billiard": PHOTO_CAT_AMENITY,
    "pool table": PHOTO_CAT_AMENITY, "snooker": PHOTO_CAT_AMENITY,
    "table tennis": PHOTO_CAT_AMENITY, "ping pong": PHOTO_CAT_AMENITY,
    "game room": PHOTO_CAT_AMENITY, "games room": PHOTO_CAT_AMENITY,
    "foosball": PHOTO_CAT_AMENITY, "arcade": PHOTO_CAT_AMENITY,
    "indoor activity": PHOTO_CAT_AMENITY, "lounge": PHOTO_CAT_AMENITY,
    "waiting room": PHOTO_CAT_AMENITY, "lobby lounge": PHOTO_CAT_AMENITY,
    "parking": PHOTO_CAT_AMENITY, "parking lot": PHOTO_CAT_AMENITY,
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
    # Culinary: food/dining/plated images ONLY — no pool, no bedroom.
    "culinary":     [PHOTO_CAT_DINING],
    # Outdoor Spaces: only garden/lawn/landscape/camping imagery. Pools and
    # generic amenities are deliberately not accepted as a substitute.
    "outdoor":      [PHOTO_CAT_OUTDOOR],
    # Room Design: STRICTLY bedroom interiors — bathroom is now a SEPARATE
    # category (PHOTO_CAT_BATHROOM) and is EXCLUDED from this section.
    "room_design":  [PHOTO_CAT_ROOMS],
    # Connectivity / Amenities: entrance/gate/road FIRST, then game room /
    # lounge / reception / parking (AMENITY). No outdoor nature shots.
    "connectivity": [PHOTO_CAT_EXTERIOR, PHOTO_CAT_AMENITY],
    "intro":        [PHOTO_CAT_EXTERIOR, PHOTO_CAT_OUTDOOR],
    # Hospitality is a service/arrival section, not a food or bedroom section.
    # Amenity photos cover reception, lounges, and guest-service areas without
    # borrowing the dining or outdoor pools.
    "hospitality":  [PHOTO_CAT_EXTERIOR, PHOTO_CAT_AMENITY],
    "general":      [PHOTO_CAT_EXTERIOR, PHOTO_CAT_OUTDOOR, PHOTO_CAT_AMENITY],
}

# Strict exclusion — these categories MUST NOT appear in these sections.
# PHOTO_CAT_BATHROOM is excluded from EVERY section (bathroom photos are
# never editorially appropriate for any article section heading).
#
# These exclusions protect against *core* category mismatches.  They are
# intentionally narrower than the preferred-category list: when an exact
# match is unavailable, the safe fallback policy below may use an exterior,
# landscape, or decor/amenity photo instead of leaving a section blank.
_SECTION_EXCLUDED_VISION_CATS: dict[str, frozenset[str]] = {
    # Culinary: never show rooms, bathrooms, or outdoor/pool imagery as food.
    # Exterior architecture is an acceptable neutral property fallback.
    "culinary": frozenset({
        PHOTO_CAT_ROOMS, PHOTO_CAT_BATHROOM, PHOTO_CAT_AMENITY,
    }),
    # Outdoor Spaces: never show rooms, food, or bathrooms.  Exterior and
    # amenity/decor photos are safe neutral fallbacks.
    "outdoor": frozenset({
        PHOTO_CAT_DINING, PHOTO_CAT_ROOMS, PHOTO_CAT_BATHROOM,
    }),
    # Connectivity: prefer entrance/amenity, but landscape/exterior is a safe
    # property-context fallback when access-specific imagery is unavailable.
    "connectivity": frozenset({
        PHOTO_CAT_ROOMS, PHOTO_CAT_BATHROOM, PHOTO_CAT_DINING,
    }),
    # Room Design: prefer bedroom interior, but do not leave the section blank
    # for a safe exterior/landscape/decor image. Never use food or bathrooms.
    "room_design": frozenset({
        PHOTO_CAT_DINING, PHOTO_CAT_BATHROOM,
    }),
    # Intro / General: no rooms, no bathroom, no dining.
    "intro": frozenset({PHOTO_CAT_ROOMS, PHOTO_CAT_BATHROOM, PHOTO_CAT_DINING}),
    "general": frozenset({PHOTO_CAT_ROOMS, PHOTO_CAT_BATHROOM, PHOTO_CAT_DINING}),
    # Hospitality: no bathroom, dining, or rooms. Exterior, landscape, and
    # decor/amenity imagery are safe property-context fallbacks.
    "hospitality": frozenset({
        PHOTO_CAT_BATHROOM, PHOTO_CAT_DINING, PHOTO_CAT_ROOMS,
    }),
}

# These section types have a protected core category.  They still receive a
# safe fallback when the core category is unavailable; this set is retained
# as a policy marker for callers that need to distinguish protected sections.
_STRICT_SECTION_TYPES: frozenset[str] = frozenset({
    "culinary", "outdoor", "room_design", "hospitality",
})

# Ordered neutral fallbacks used after preferred categories are exhausted.
# Every category here is a real property-gallery category and is already
# filtered for faces, selfies, and low quality during pool construction.
# Bathroom and unknown photos are deliberately absent.
_SAFE_FALLBACK_VISION_CATS: dict[str, tuple[str, ...]] = {
    # Generic landscape/exterior context is acceptable when no dining photo
    # exists, but _is_safe_section_fallback rejects pool-specific imagery.
    "culinary": (PHOTO_CAT_EXTERIOR, PHOTO_CAT_OUTDOOR),
    "outdoor": (PHOTO_CAT_OUTDOOR, PHOTO_CAT_EXTERIOR, PHOTO_CAT_AMENITY),
    "room_design": (PHOTO_CAT_ROOMS, PHOTO_CAT_EXTERIOR, PHOTO_CAT_OUTDOOR, PHOTO_CAT_AMENITY),
    "connectivity": (PHOTO_CAT_EXTERIOR, PHOTO_CAT_AMENITY, PHOTO_CAT_OUTDOOR),
    "hospitality": (PHOTO_CAT_EXTERIOR, PHOTO_CAT_AMENITY, PHOTO_CAT_OUTDOOR),
    "intro": (PHOTO_CAT_EXTERIOR, PHOTO_CAT_OUTDOOR, PHOTO_CAT_AMENITY),
    "general": (PHOTO_CAT_EXTERIOR, PHOTO_CAT_OUTDOOR, PHOTO_CAT_AMENITY),
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


def _is_safe_section_fallback(
    photo: _ClassifiedPhoto,
    section_type: str,
    selection_label: str,
) -> bool:
    """Reject visually specific fallback photos that would mislead a section."""
    if "fallback" not in selection_label:
        return True

    tags = {tag.lower() for tag in photo.serpapi_tags}
    if section_type == "culinary" and tags & {
        "pool",
        "swimming pool",
        "infinity pool",
        "water feature",
    }:
        return False
    return True


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
            if vr:
                # FACE_DETECTION is authoritative and independent of label
                # ordering. A person can be visually prominent while Vision's
                # top label is "hotel", "room", or "landscape".
                if getattr(vr, "face_count", 0):
                    return "selfie", 0.0, True

            if vr and vr.labels:
                label_names_scored = [(lb.description.lower(), lb.score) for lb in vr.labels]
                all_label_names = {n for n, _ in label_names_scored}

                # Any explicit face/selfie signal is a hard rejection. The old
                # implementation only rejected a face when "person" was first,
                # which allowed a bedroom/background label to mask a selfie.
                if all_label_names & (_SELFIE_VISION_LABELS | {"face", "portrait"}):
                    return "selfie", 0.0, True

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

                # Outdoor evidence wins over weak indoor/furniture labels. This
                # prevents a garden table/umbrella photo from being classified
                # as a room merely because Vision also returned "furniture",
                # "table", or "design".
                outdoor_signals = {
                    PHOTO_CAT_OUTDOOR,
                    PHOTO_CAT_AMENITY,
                    PHOTO_CAT_EXTERIOR,
                }
                if cat_scores.get(PHOTO_CAT_OUTDOOR, 0.0) > 0 and (
                    cat_scores.get(PHOTO_CAT_ROOMS, 0.0) < 0.75
                    or cat_scores[PHOTO_CAT_OUTDOOR] >= cat_scores.get(PHOTO_CAT_ROOMS, 0.0)
                ):
                    for outdoor_cat in outdoor_signals:
                        if outdoor_cat != PHOTO_CAT_OUTDOOR:
                            cat_scores.pop(outdoor_cat, None)
                    cat_scores[PHOTO_CAT_OUTDOOR] += 0.5

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
                    # ── People / portrait rejection ───────────────────────────
                    # Only reject when the PRIMARY subject is a person (top
                    # Vision label).  Hotel photos routinely contain guests in
                    # the background — a lobby shot with staff, a terrace with
                    # diners — and those are editorially valuable.  Rejecting
                    # every photo that contains ANY person label was wiping out
                    # the majority of the property gallery.
                    #
                    # Hard rejects:  selfie / close-up face labels (handled
                    # above), or top label is a person.
                    # Soft penalty:  person present but not primary subject —
                    # keep the photo with a reduced quality score so it ranks
                    # below people-free shots of the same category.
                    people_present = bool(all_label_names & _PERSON_VISION_LABELS)
                    if people_present:
                        top_label_is_person = (
                            label_names_scored[0][0] in _PERSON_VISION_LABELS
                            if label_names_scored else False
                        )
                        if top_label_is_person:
                            # Primary subject is a person — treat as selfie/portrait
                            return "selfie", 0.0, True
                        # Person present but not the primary subject (background
                        # guest / staff).  Keep with reduced quality so
                        # people-free photos of the same category surface first.
                        return best_cat, quality * 0.5, False
                    return best_cat, quality, False

                # No editorial category matched — use top-label confidence as
                # a quality proxy.  Very low confidence means Vision saw mostly
                # noise (dark / blurry / low-res image).
                if all_top3_unusable or top_confidence < _MIN_UNCLASSIFIED_LABEL_CONFIDENCE:
                    return "low_quality", 0.0, False
                # People-first unclassified → reject as portrait
                if all_label_names & _PERSON_VISION_LABELS:
                    if label_names_scored and label_names_scored[0][0] in _PERSON_VISION_LABELS:
                        return "selfie", 0.0, True
                    top_confidence *= 0.25
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
        # Bathroom MUST be checked before room_interior — SerpApi sometimes
        # tags bathroom photos with "rooms" as a secondary tag.
        if tag_set & _BATHROOM_PHOTO_TAG_TOKENS:
            return PHOTO_CAT_BATHROOM, 0.7, False
        if tag_set & _OUTDOOR_PHOTO_TAG_TOKENS:
            return PHOTO_CAT_OUTDOOR, 0.7, False
        # Lobby/reception/lounge photos belong to guest experience/amenities,
        # not Room Design. Keep this before the broad room-interior check.
        if tag_set & {"lobby", "reception", "concierge", "lounge", "common area"}:
            return PHOTO_CAT_AMENITY, 0.7, False
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
        max_vision_calls: int = 75,
    ) -> None:
        self._by_category: dict[str, list[_ClassifiedPhoto]] = {
            PHOTO_CAT_DINING:    [],
            PHOTO_CAT_ROOMS:     [],
            PHOTO_CAT_BATHROOM:  [],   # toilet/shower — excluded from Room Design
            PHOTO_CAT_OUTDOOR:   [],
            PHOTO_CAT_AMENITY:   [],
            PHOTO_CAT_EXTERIOR:  [],
            "unknown":           [],
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

            # Run Vision API on up to max_vision_calls photos for accurate
            # classification; remaining photos fall back to SerpApi tag-based
            # classification which is fast (no extra API call).
            classify_url = raw_url if i < max_vision_calls else ""
            cat, quality, is_selfie = _classify_photo_vision_category(classify_url, tags)

            if is_selfie or cat == "selfie":
                logger.debug("SmartPhotoPool: filtered selfie/portrait — %s", raw_url[:60])
                continue

            # Reject photos flagged as too dark, blurry, or low-resolution.
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
            "SmartPhotoPool built: %d photos | dining=%d rooms=%d bathroom=%d "
            "outdoor=%d amenity=%d exterior=%d unknown=%d",
            self._total,
            len(self._by_category[PHOTO_CAT_DINING]),
            len(self._by_category[PHOTO_CAT_ROOMS]),
            len(self._by_category[PHOTO_CAT_BATHROOM]),
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
        allow_reuse: bool = False,
    ) -> tuple[str, str] | None:
        """
        Return (proxied_url, vision_category) for the best matching photo for
        *section_type*, or None when no eligible photo exists.

        Strategy:
          Pass 1 — preferred category match (best quality first).
          Pass 2 — approved neutral property-gallery fallback categories.
          Pass 3 — if allow_reuse is true, reuse the highest-quality eligible
                   preferred/safe photo after unique photos are exhausted.

        Hard rejections happen upstream during pool construction (faces,
        selfies, and low_quality/dark/blurry photos are filtered before photos
        are stored). Core section exclusions are enforced here as well.
        """
        avoid = global_used or set()
        preferred = _SECTION_TO_VISION_CATEGORIES.get(
            section_type, [PHOTO_CAT_EXTERIOR, PHOTO_CAT_OUTDOOR]
        )
        excluded = _SECTION_EXCLUDED_VISION_CATS.get(section_type, frozenset())

        def _log_and_return(photo: _ClassifiedPhoto, label: str) -> tuple[str, str]:
            self._used_proxied.add(photo.proxied_url)
            logger.info(
                "SmartPhotoPool: section=%r → %s cat=%r (q=%.2f)",
                section_type, label, photo.vision_category, photo.quality_score,
            )
            return photo.proxied_url, photo.vision_category

        # A category can only be considered a fallback when it is not a core
        # mismatch for this section. Keep this guard close to selection so a
        # future fallback-list edit cannot accidentally re-enable a banned
        # category.
        safe_fallback = _SAFE_FALLBACK_VISION_CATS.get(
            section_type,
            (PHOTO_CAT_EXTERIOR, PHOTO_CAT_OUTDOOR, PHOTO_CAT_AMENITY),
        )

        def _pick_unused(categories: tuple[str, ...], label: str):
            for cat in categories:
                if cat in excluded or cat == PHOTO_CAT_BATHROOM:
                    continue
                for photo in self._by_category.get(cat, []):
                    if not _is_safe_section_fallback(photo, section_type, label):
                        continue
                    if self._unused(photo, avoid):
                        return _log_and_return(photo, label)
            return None

        # Exact matches win. For sections whose preferred list includes
        # multiple categories, preserve that editorial priority.
        exact = _pick_unused(tuple(preferred), "preferred")
        if exact is not None:
            return exact

        # Use classified safe-fallback categories first.
        fallback = _pick_unused(tuple(safe_fallback), "safe-fallback")
        if fallback is not None:
            return fallback

        # Pass 3: try "unknown"-category photos as an additional safe fallback.
        # These are real property-gallery photos that Vision couldn't classify
        # into a named category (e.g. abstract decor, dim corridor, unusual
        # angle).  They are not selfies or low-quality (those were filtered at
        # pool construction time).  Better than a blank slot, ranked below any
        # classified photo of the right type.
        if "unknown" not in excluded:
            for photo in self._by_category.get("unknown", []):
                if not _is_safe_section_fallback(photo, section_type, "safe-fallback"):
                    continue
                if self._unused(photo, avoid):
                    return _log_and_return(photo, "unknown-fallback")

        if allow_reuse:
            # Small galleries can have fewer photos than article sections.
            # Reuse only an eligible preferred/safe photo, never a bathroom,
            # or a category hard-excluded above.
            for categories, label in (
                (tuple(preferred), "preferred-reuse"),
                (tuple(safe_fallback), "safe-fallback-reuse"),
            ):
                reusable_candidates: list[_ClassifiedPhoto] = []
                for cat in categories:
                    if cat in excluded or cat == PHOTO_CAT_BATHROOM:
                        continue
                    reusable_candidates.extend(
                        photo
                        for photo in self._by_category.get(cat, [])
                        if _is_safe_section_fallback(photo, section_type, label)
                    )
                reusable_candidates.sort(
                    key=lambda photo: photo.quality_score,
                    reverse=True,
                )
                if reusable_candidates:
                    return _log_and_return(reusable_candidates[0], label)

        # Pass 4: absolute last resort — any unused non-bathroom property photo.
        # A real photo from the property gallery always beats a blank section slot.
        # Culinary still blocks pool photos via _is_safe_section_fallback; all
        # other categories accept any real gallery photo here.
        for cat, bucket in self._by_category.items():
            if cat == PHOTO_CAT_BATHROOM:
                continue
            for photo in bucket:
                if not _is_safe_section_fallback(photo, section_type, "safe-fallback"):
                    continue
                if self._unused(photo, avoid):
                    logger.warning(
                        "SmartPhotoPool: section=%r using last-resort photo "
                        "(cat=%r) — no better match available.",
                        section_type, cat,
                    )
                    return _log_and_return(photo, "last-resort")

        logger.warning(
            "SmartPhotoPool: no eligible photo for section=%r; "
            "pool fully exhausted or every photo is excluded.",
            section_type,
        )
        return None

    def pick_any(self, global_used: set[str] | None = None) -> str | None:
        """Return any available photo (for padding / hero fallback).
        Bathroom photos are excluded — they should never be used as hero shots.
        """
        avoid = global_used or set()
        all_photos: list[_ClassifiedPhoto] = []
        for cat, bucket in self._by_category.items():
            if cat == PHOTO_CAT_BATHROOM:
                continue
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
    max_photos: int = 100,
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
        PHOTO_CAT_DINING:    "Culinary experience",
        PHOTO_CAT_ROOMS:     "Room and amenities",
        PHOTO_CAT_BATHROOM:  "Bathroom and amenities",
        PHOTO_CAT_OUTDOOR:   "Outdoor spaces",
        PHOTO_CAT_AMENITY:   "Amenities and experience",
        PHOTO_CAT_EXTERIOR:  "Exterior view",
        "unknown":           "",
    }.get(vision_category, "")


# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Section type classification
#
# Each article heading is classified into one of seven types so the image
# routing logic can apply contextually correct constraints from the Google
# Maps photo pool:
#
#   "culinary"     — dining, food, cuisine, kitchen, "Eat & Explore", etc.
#   "outdoor"      — garden, pool, terrace, outdoor spaces, landscape, etc.
#   "room_design"  — room comforts, architecture, design, amenities, spa, etc.
#   "connectivity" — getting here, transport, access, distance, etc.
#   "hospitality"  — guest experience, reviews, staff, service, etc.
#   "intro"        — introduction, overview, about, setting, etc.
#   "general"      — everything else (history, conclusion, unclassified, …)
# ---------------------------------------------------------------------------

_CULINARY_HEADING_TOKENS: frozenset[str] = frozenset({
    "culinary", "dining", "food", "restaurant", "kitchen", "cuisine",
    "breakfast", "meal", "meals", "eat", "explore", "gastro", "gastronomy",
    "beverage", "drinks", "cafe", "menu", "chef", "cook", "cooking",
    "delights", "flavours", "flavors", "taste", "tasting",
})

_CONNECTIVITY_HEADING_TOKENS: frozenset[str] = frozenset({
    "connectivity", "accessible", "accessibility",
    "transport", "transportation", "getting", "commute",
    "access", "distance", "proximity",
    "road", "highway", "airport", "station", "railway", "rail",
    "route", "routes", "directions", "reaching",
})

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
    "design", "interior", "interiors", "amenities", "amenity",
    "stay", "lodging", "bathroom", "hygiene", "sanitation",
    "facility", "facilities", "spa", "wellness",
})

_HOSPITALITY_HEADING_TOKENS: frozenset[str] = frozenset({
    "hospitality", "experience", "experiences", "guest", "guests",
    "service", "services", "staff", "team", "host", "hosting",
    "review", "reviews", "rating", "ratings", "feedback",
    "check-in", "checkin", "checkout", "check-out",
    "concierge", "reception", "front-desk", "frontdesk",
    "welcome", "warmth", "care", "attention",
    "impression", "impressions", "testimonial", "testimonials",
})

# Human-readable labels for figure captions.
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
    Returns None when tags are empty or unrecognisable.
    """
    if not tags:
        return None

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

    tag_set = set(tags)
    if tag_set & {"bathroom", "washroom", "restroom", "bathtub", "bathing", "shower", "toilet", "lavatory"}:
        return "Bathroom and amenities"
    if tag_set & {"pool", "swimming pool", "outdoor", "outdoors", "garden", "terrace", "courtyard",
                  "patio", "balcony", "veranda", "deck", "open air", "landscape", "greenery"}:
        return "Outdoor spaces"
    if tag_set & {"food & drink", "food", "drinks", "beverages", "dining room", "kitchen",
                  "breakfast", "lunch", "dinner", "chef", "meal", "cuisine", "cafe", "bar",
                  "buffet", "restaurant"}:
        return "Culinary experience"
    if tag_set & {"rooms", "room", "bedroom", "suite", "interior", "accommodation",
                  "living room", "lounge", "corridor", "hallway"}:
        return "Room and amenities"
    if tag_set & {"exterior", "front", "facade", "building", "outside",
                  "front of property", "entrance", "gate", "driveway"}:
        return "Exterior view"
    return None


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
        pool = _build_smart_pool_for_listing(listing, max_photos=100)
    if pool is None or not pool.available:
        return []

    used: set[str] = set()
    settings = get_settings()
    results: list[dict] = []

    for section_type in section_types:
        pick = pool.pick_for_section(section_type, used, allow_reuse=True)
        if pick is not None:
            url, cat = pick
        else:
            url = None
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

    Every image slot is filled exclusively from the named property's own
    Google Maps photo gallery (via SerpApi). No external image sources are
    ever used. If the gallery has no exact-match photo for a section type,
    the selector uses a classified, quality-ranked safe fallback from the
    same property, reusing one only when the gallery is smaller than the
    article. A slot is only left blank when no eligible non-banned photo
    exists.
    """
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
    # (e.g. "Hyatt Dehradun"). Every slot (hero + every section) is filled
    # strictly from that business's own Google Maps photo gallery. No other
    # business photo, stock image, or external source is ever mixed in.
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
            # Use the same intro-safe routing as the multi-property path so
            # the hero does not consume the only bedroom, dining, or outdoor
            # image needed by a later strict section.
            hero_result = smart_pool.pick_for_section("intro", used_urls)
            hero_url = hero_result[0] if hero_result else smart_pool.pick_any(used_urls)
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
                result = smart_pool.pick_for_section(
                    section_type, used_urls, allow_reuse=True
                )
                if result is not None:
                    # SmartPhotoPool handles preferred → safe fallback routing.
                    # No external sources are ever consulted.
                    url, vision_cat = result
                    used_urls.add(url)
                    pool_fill_count += 1
                    logger.info(
                        "Section %r (type=%r) → Vision cat=%r url=%s",
                        slot[:50], section_type, vision_cat, url[:60],
                    )
                else:
                    if url is None:
                        logger.warning(
                            "Section %r (type=%r) → no eligible safe gallery photo; "
                            "slot left blank.",
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
        pool = _build_smart_pool_for_listing(listing, max_photos=100)
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
            result = pool.pick_for_section(
                section_type, used_urls, allow_reuse=True
            )
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
            result = pool.pick_for_section(
                section_type, used_urls, allow_reuse=True
            )
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
                # All named-listing pools exhausted for the preferred category.
                # Revisit each property gallery with the same safe fallback
                # policy; never use unrestricted pick_any here.
                fallback_url: str | None = None
                for _fb_idx in range(len(all_listings)):
                    _fb_pool = _get_or_build_smart_pool(_fb_idx)
                    if _fb_pool is None:
                        continue
                    _fb_result = _fb_pool.pick_for_section(
                        section_type, used_urls, allow_reuse=True
                    )
                    if _fb_result is not None:
                        fallback_url, vision_cat = _fb_result
                        used_urls.add(fallback_url)
                        break
                if fallback_url:
                    url = fallback_url
                    logger.info(
                        "Section %r (type=%r) → safe fallback from a "
                        "Google Maps listing pool.",
                        heading[:50], section_type,
                    )
                else:
                    logger.warning(
                        "Section %r (type=%r) → all Google Maps property pools "
                        "exhausted; slot left blank.",
                        heading[:50], section_type,
                    )

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
