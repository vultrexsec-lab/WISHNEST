"""
SerpApi Google Maps integration — live hotel/villa/boutique-stay photos
and ratings for a given city or town.

All property search now goes exclusively through SerpApi's Google Maps
engine (SERPAPI_KEY). The direct Google Places Text Search endpoint
(maps.googleapis.com/maps/api/place/textsearch) has been removed to
eliminate REQUEST_DENIED billing errors and concurrent duplicate firing.

Photo galleries are fetched from SerpApi's dedicated google_maps_photos
engine for each discovered property's data_id, giving the same full
gallery a user sees on Google Maps (pool, rooms, dining, exteriors, etc.)
at full resolution — not just the single search-result thumbnail.

If SERPAPI_KEY is not configured, a one-time setup notice is logged and
every function returns an empty list / None. Callers MUST treat that as
"no live data available" and fall back to their own degraded path — this
module never raises and never fabricates a listing.
"""
import logging
import re
from dataclasses import dataclass

import requests

from app.config import get_settings

logger = logging.getLogger("wishnest.places_service")

_REQUEST_TIMEOUT = 10
_warned_missing_key = False

# Minimum pixel dimension for every property photo. SerpApi thumbnails come
# back hardcoded to small sizes (e.g. "=w203-h135-k-no"); rewriting just the
# numeric width/height returns the SAME real photo at full resolution with no
# extra API calls.
_TARGET_PHOTO_SIZE = 1600

_LH3_SIZE_RE = re.compile(r"=w\d+-h\d+(-[a-zA-Z0-9-]+)?$")
_LH3_SIZE_RE_S = re.compile(r"=s\d+(-[a-zA-Z0-9-]+)?$")


def _upscale_lh3_photo_url(url: str | None, size: int = _TARGET_PHOTO_SIZE) -> str | None:
    """
    Rewrite a googleusercontent.com photo URL's trailing size segment to
    request *size* pixels instead of whatever (often tiny) thumbnail
    dimensions the provider hardcoded. Leaves non-googleusercontent URLs
    and URLs with no recognizable size suffix untouched.
    """
    if not url or "googleusercontent.com" not in url:
        return url
    if _LH3_SIZE_RE.search(url):
        return _LH3_SIZE_RE.sub(f"=w{size}-h{size}-k-no", url)
    if _LH3_SIZE_RE_S.search(url):
        return _LH3_SIZE_RE_S.sub(f"=s{size}", url)
    if "=" not in url.rsplit("/", 1)[-1]:
        return f"{url}=w{size}-h{size}-k-no"
    return url


@dataclass
class PropertyListing:
    """One real, named business listing with a live photo + live rating."""
    name: str
    photo_url: str | None       # raw upstream URL — caller is responsible for proxying it
    rating: float | None        # Google star rating, 1.0-5.0
    review_count: int | None
    address: str | None
    maps_url: str | None
    # Unique identifier — SerpApi `data_id`. Used for de-duplication: the
    # scheduler records this on each Article row so the same property is
    # never covered twice.
    place_id: str | None = None
    # Every other real photo belonging to THIS SAME listing (may be empty if
    # the provider only ever returns one). Used for review articles about a
    # single named property so every image slot cycles through this one
    # business's own verified photo pool instead of mixing in stock images.
    photo_urls: list[str] = None  # type: ignore[assignment]
    # SerpApi category tags for each photo in photo_urls — parallel list
    # where photo_tags[i] holds lowercased tag strings for photo_urls[i]
    # (e.g. ["exterior", "front of property"]).  Empty list when SerpApi
    # returned no tag data for that photo.  Used by the smart pool to route
    # exterior photos to intro/conclusion/connectivity sections, food photos
    # to culinary sections, and to exclude portrait photos from non-staff
    # sections.
    photo_tags: list[list[str]] = None  # type: ignore[assignment]

    def __post_init__(self):
        if self.photo_urls is None:
            self.photo_urls = [self.photo_url] if self.photo_url else []
        if self.photo_tags is None:
            self.photo_tags = [[] for _ in self.photo_urls]


def _log_missing_key_notice() -> None:
    """Emit a single, unmistakable console notice the first time we discover
    that SERPAPI_KEY is not configured. Never breaks the caller."""
    global _warned_missing_key
    if _warned_missing_key:
        return
    _warned_missing_key = True
    logger.warning(
        "\n"
        "─────────────────────────────────────────────────────────────────\n"
        "  WishNest setup notice: SERPAPI_KEY is not configured.\n"
        "  Live Google Maps hotel photos + real star ratings are disabled.\n"
        "\n"
        "  To enable them, add SERPAPI_KEY in the Replit Secrets tab.\n"
        "\n"
        "  Until then, articles fall back to the existing dynamic image\n"
        "  search chain and LLM-estimated scores.\n"
        "─────────────────────────────────────────────────────────────────"
    )


def _coerce_rating(value) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_review_count(value) -> int | None:
    try:
        if value is None:
            return None
        return int(float(value))
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# SerpApi — photo gallery
# ---------------------------------------------------------------------------

def _serpapi_maps_photos_gallery(data_id: str, api_key: str, max_photos: int) -> list[dict]:
    """
    Fetch up to *max_photos* real photo URLs from SerpApi's dedicated
    `google_maps_photos` engine for the business identified by *data_id* —
    the same public photo gallery a user sees on that business's Google Maps
    listing (exteriors, rooms, pool, dining, etc). Returns [] on any
    failure or empty response; never raises.
    """
    try:
        resp = requests.get(
            "https://serpapi.com/search.json",
            params={
                "engine": "google_maps_photos",
                "data_id": data_id,
                "api_key": api_key,
            },
            timeout=_REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        photos = data.get("photos") or []
        result: list[dict] = []
        for photo in photos[:max_photos]:
            url = photo.get("thumbnail") or photo.get("image")
            if url:
                # SerpApi returns tags as a list or single string — normalise.
                raw_tag = photo.get("tag") or photo.get("tags") or []
                if isinstance(raw_tag, str):
                    raw_tag = [raw_tag]
                tags = [t.strip().lower() for t in raw_tag if isinstance(t, str) and t.strip()]
                result.append({"url": _upscale_lh3_photo_url(url) or url, "tags": tags})
        return result
    except Exception as exc:  # noqa: BLE001
        logger.warning("SerpApi google_maps_photos lookup failed for data_id=%r: %s", data_id, exc)
        return []


# ---------------------------------------------------------------------------
# SerpApi — property search (replaces Google Places Text Search entirely)
# ---------------------------------------------------------------------------

def _serpapi_maps_query(query: str, limit: int) -> list[PropertyListing]:
    """
    Run a SerpApi Google Maps search for *query* (fully-formed). Returns up
    to *limit* `PropertyListing`s with `place_id` set to the SerpApi `data_id`
    (the stable identifier used to pull a property's full photo gallery).

    This is the sole search path — the direct Google Places Text Search
    endpoint (maps.googleapis.com/maps/api/place/textsearch) has been removed
    to eliminate REQUEST_DENIED billing errors and concurrent duplicate firing.
    """
    api_key = get_settings().serpapi_key
    if not api_key:
        return []

    try:
        resp = requests.get(
            "https://serpapi.com/search.json",
            params={
                "engine": "google_maps",
                "q": query,
                "type": "search",
                "api_key": api_key,
            },
            timeout=_REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        results = data.get("local_results") or data.get("place_results") or []
        if isinstance(results, dict):
            results = [results]

        listings: list[PropertyListing] = []
        for place in results:
            thumbnail = _upscale_lh3_photo_url(
                place.get("thumbnail") or place.get("photo") or place.get("serpapi_thumbnail")
            )
            if not thumbnail:
                # Landmarks and monuments often store photos in an "images" list
                # rather than the top-level "thumbnail" key used by hotels.
                # Check that array before discarding the result entirely.
                imgs = place.get("images") or []
                if isinstance(imgs, list):
                    for img_entry in imgs[:5]:
                        if not isinstance(img_entry, dict):
                            continue
                        candidate = img_entry.get("thumbnail") or img_entry.get("image")
                        if candidate:
                            thumbnail = _upscale_lh3_photo_url(candidate)
                            break
            if not thumbnail:
                continue
            data_id = place.get("data_id")
            listings.append(
                PropertyListing(
                    name=place.get("title") or "",
                    photo_url=thumbnail,
                    rating=_coerce_rating(place.get("rating")),
                    review_count=_coerce_review_count(place.get("reviews")),
                    address=place.get("address"),
                    maps_url=place.get("link"),
                    place_id=data_id,
                )
            )
            if len(listings) >= limit:
                break
        return listings
    except Exception as exc:  # noqa: BLE001
        logger.warning("SerpApi Google Maps query failed for %r: %s", query[:80], exc)
        return []


def _serpapi_maps_search(location: str, limit: int) -> list[PropertyListing]:
    query = f"top rated luxury hotels resorts villas boutique stays in {location}"
    return _serpapi_maps_query(query, limit)


def fetch_landmark_attractions(location: str | None, limit: int = 8) -> list[PropertyListing]:
    """
    Return up to *limit* real tourist attraction / landmark listings for
    *location* via SerpApi Google Maps. Used for 'Best Places & Destinations'
    category articles in place of hotel-oriented `fetch_premium_stays`, so
    image slots carry genuine geographic / attraction content.

    Tries multiple query angles (attractions, monuments, scenic spots) so that
    even locations with few hotel-style listings still return real landmark
    photos. Returns an empty list (never raises, never fabricates data) when
    SERPAPI_KEY is not configured or SerpApi returns nothing.
    """
    location = (location or "").strip()
    if not location:
        return []

    api_key = get_settings().serpapi_key
    if not api_key:
        _log_missing_key_notice()
        return []

    query_templates = [
        f"top tourist attractions landmarks {location} India",
        f"famous monuments scenic places {location} India",
        f"must visit places tourism {location}",
    ]
    for query in query_templates:
        listings = _serpapi_maps_query(query, limit)
        if listings:
            logger.info(
                "Live attraction listings resolved for %r via SerpApi: %d found (query=%r)",
                location, len(listings), query[:80],
            )
            return listings

    logger.info("No live attraction listings found for %r from SerpApi.", location)
    return []


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def fetch_property_by_name(
    name: str, location: str | None = None, max_photos: int = 15,
) -> PropertyListing | None:
    """
    Look up ONE specific, named business (e.g. "Hyatt Dehradun") and return a
    PropertyListing carrying every real photo we can find that belongs to
    THAT SAME business (via SerpApi google_maps_photos gallery).

    Returns None (never raises) if the property can't be matched or has no
    real photos — callers must treat that as "no strict pool available" and
    fall back to a broader/degraded path.
    """
    name = (name or "").strip()
    if not name:
        return None
    query = f"{name} {location or ''}".strip()

    api_key = get_settings().serpapi_key
    if not api_key:
        _log_missing_key_notice()
        return None

    try:
        resp = requests.get(
            "https://serpapi.com/search.json",
            params={
                "engine": "google_maps",
                "q": query,
                "type": "search",
                "api_key": api_key,
            },
            timeout=_REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        results = data.get("local_results") or data.get("place_results") or []
        if isinstance(results, dict):
            results = [results]
        if not results:
            return None

        place = results[0]
        thumbnail = _upscale_lh3_photo_url(
            place.get("thumbnail") or place.get("photo") or place.get("serpapi_thumbnail")
        )
        data_id = place.get("data_id")

        tagged_photos: list[dict] = []
        if data_id:
            tagged_photos = _serpapi_maps_photos_gallery(data_id, api_key, max_photos)

        if tagged_photos:
            photo_urls: list[str] = [p["url"] for p in tagged_photos]
            photo_tags_list: list[list[str]] = [p["tags"] for p in tagged_photos]
        else:
            # Gallery lookup unavailable/empty — fall back to whatever single
            # photo(s) the search result itself carried.  No tag data available.
            extra = place.get("photos") or []
            extra_urls = [
                _upscale_lh3_photo_url(p.get("thumbnail") or p.get("image"))
                for p in extra
                if isinstance(p, dict) and (p.get("thumbnail") or p.get("image"))
            ][:max_photos]
            photo_urls = [u for u in ([thumbnail] + extra_urls) if u]
            photo_tags_list = [[] for _ in photo_urls]

        # De-dup while preserving order; keep tag list in sync.
        seen: set[str] = set()
        deduped = [
            (u, t) for u, t in zip(photo_urls, photo_tags_list)
            if not (u in seen or seen.add(u))
        ]
        photo_urls = [u for u, _ in deduped]
        photo_tags_list = [t for _, t in deduped]

        if not photo_urls:
            return None

        tagged_count = sum(1 for t in photo_tags_list if t)
        logger.info(
            "Strict single-property photo pool resolved for %r via SerpApi: %d photo(s) (%d tagged)",
            name, len(photo_urls), tagged_count,
        )
        return PropertyListing(
            name=place.get("title") or name,
            photo_url=photo_urls[0],
            rating=_coerce_rating(place.get("rating")),
            review_count=_coerce_review_count(place.get("reviews")),
            address=place.get("address"),
            maps_url=place.get("link"),
            place_id=data_id,
            photo_urls=photo_urls,
            photo_tags=photo_tags_list,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("SerpApi single-property lookup failed for %r: %s", name, exc)
        return None


def search_properties(query: str, limit: int = 20) -> list[PropertyListing]:
    """
    Direct-query version of `fetch_premium_stays` — accepts a fully-formed
    search string (e.g. "top rated luxury boutique hotels Rajasthan India")
    instead of a bare location name. Used by the discovery service for
    category-specific scheduler queries and by the broad-search resolver.

    Exclusively uses SerpApi. Returns an empty list (never raises, never
    fabricates data) when SERPAPI_KEY is not configured.
    """
    query = (query or "").strip()
    if not query:
        return []

    listings = _serpapi_maps_query(query, limit)
    if listings:
        logger.info(
            "search_properties: %d result(s) via SerpApi for query %r",
            len(listings), query[:80],
        )
    else:
        logger.info("search_properties: no results from SerpApi for query %r", query[:80])
        if not get_settings().serpapi_key:
            _log_missing_key_notice()
    return listings


def text_search_place(query: str, max_photos: int = 15) -> PropertyListing | None:
    """
    Resolve a free-form text query (e.g. "Top 5 star hotel in Mussoorie" or
    "Amanbagh Rajasthan") to the single best matching Google Maps business
    via SerpApi, returning a `PropertyListing` with its full photo gallery.

    This is the broad-query resolver used by the research router: if SerpApi
    can match a real business, its exact details feed into the article pipeline
    instead of a generic LLM-context search. Returns None (never raises) if no
    real match is found — callers fall through to the Firecrawl path.
    """
    query = (query or "").strip()
    if not query:
        return None

    result = fetch_property_by_name(query, location=None, max_photos=max_photos)
    if result:
        logger.info(
            "text_search_place: resolved %r -> %r (place_id=%r, %.1f★)",
            query[:80], result.name, result.place_id, result.rating or 0.0,
        )
    return result


def fetch_premium_stays(location: str | None, limit: int = 8) -> list[PropertyListing]:
    """
    Return up to *limit* real, distinct premium hotel/villa/boutique-stay
    listings for *location*, each carrying a live Google Maps photo URL and
    a live star rating pulled from an actual business listing via SerpApi.

    Returns an empty list (never raises, never fabricates data) when
    SERPAPI_KEY is not configured or SerpApi returns nothing.
    """
    location = (location or "").strip()
    if not location:
        return []

    listings = _serpapi_maps_search(location, limit)
    if listings:
        logger.info(
            "Live property listings resolved for %r via SerpApi: %d found",
            location, len(listings),
        )
        return listings

    if not get_settings().serpapi_key:
        _log_missing_key_notice()
    else:
        logger.info("No live property listings found for %r from SerpApi.", location)
    return []
