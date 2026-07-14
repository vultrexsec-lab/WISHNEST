"""
Google Places / SerpApi integration — live hotel/villa/boutique-stay photos
and ratings for a given city or town.

This replaces the old static "premium luxury hotel" Unsplash pool: every
photo returned here belongs to a real, named business listing pulled live
from Google Maps, and every rating is that business's genuine aggregate
Google user rating (not an LLM guess).

Provider chain
--------------
  1. Google Places API (GOOGLE_PLACES_API_KEY) — Text Search + Place Photos.
     Preferred: official API, includes `rating` and `user_ratings_total`
     directly on the Text Search result.
  2. SerpApi's Google Maps engine (SERPAPI_KEY) — used only when the Places
     key is absent (or the Places call itself failed/returned nothing).
  3. Neither key configured — logs a one-time, clearly-labelled setup
     notice and returns an empty list. Callers MUST treat an empty list as
     "no live data available" and fall back to their own degraded path;
     this module never raises and never fabricates a listing.
"""
import logging
import re
import urllib.parse
from dataclasses import dataclass

import requests

from app.config import get_settings

logger = logging.getLogger("wishnest.places_service")

_REQUEST_TIMEOUT = 10
_warned_missing_key = False

# Minimum pixel dimension we ask for on every property photo — applies to
# both the Google Places Photo endpoint (`maxwidth`/`maxheight` params) and
# SerpApi/lh3.googleusercontent.com URLs (rewritten `=wNNN-hNNN-...` size
# suffix). 1600px matches the Google Places Photo call already used in
# `_resolve_google_photo_url` and is large enough for full-width hero/section
# images without visible upscaling artifacts.
_TARGET_PHOTO_SIZE = 1600

# lh3.googleusercontent.com (and other googleusercontent.com) photo URLs encode
# the requested size as a trailing "=wNNN-hNNN-<flags>" (or "=sNNN-<flags>")
# segment. SerpApi's google_maps_photos / google_maps thumbnails come back
# hardcoded to small sizes (e.g. "=w203-h135-k-no") — rewriting just the
# numeric width/height to our target size returns the SAME real photo at full
# resolution instead of a thumbnail crop, with no extra API calls.
_LH3_SIZE_RE = re.compile(r"=w\d+-h\d+(-[a-zA-Z0-9-]+)?$")
_LH3_SIZE_RE_S = re.compile(r"=s\d+(-[a-zA-Z0-9-]+)?$")


def _upscale_lh3_photo_url(url: str | None, size: int = _TARGET_PHOTO_SIZE) -> str | None:
    """
    Rewrite a googleusercontent.com (lh3/lh5/...) photo URL's trailing size
    segment to request *size* pixels instead of whatever (often tiny)
    thumbnail dimensions the provider hardcoded. Leaves non-googleusercontent
    URLs and URLs with no recognizable size suffix untouched — this is a
    best-effort quality upgrade, never a correctness requirement.
    """
    if not url or "googleusercontent.com" not in url:
        return url
    if _LH3_SIZE_RE.search(url):
        return _LH3_SIZE_RE.sub(f"=w{size}-h{size}-k-no", url)
    if _LH3_SIZE_RE_S.search(url):
        return _LH3_SIZE_RE_S.sub(f"=s{size}", url)
    # No recognizable size suffix at all — append one rather than leaving the
    # provider's implicit (often small) default in place.
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
    # Every other real photo belonging to THIS SAME listing (may be empty if
    # the provider only ever returns one). Used for review articles about a
    # single named property, so every image slot in the article can be
    # strictly filled from this one business's own photo pool instead of
    # mixing in other businesses or generic stock photos.
    photo_urls: list[str] = None  # type: ignore[assignment]

    def __post_init__(self):
        if self.photo_urls is None:
            self.photo_urls = [self.photo_url] if self.photo_url else []


def _log_missing_key_notice() -> None:
    """Emit a single, unmistakable console notice the first time we discover
    that no live property-data provider is configured. Never breaks the
    request that triggered it — this is purely informational."""
    global _warned_missing_key
    if _warned_missing_key:
        return
    _warned_missing_key = True
    logger.warning(
        "\n"
        "─────────────────────────────────────────────────────────────────\n"
        "  WishNest setup notice: no live property-data source configured.\n"
        "  Live Google Maps hotel photos + real star ratings are disabled.\n"
        "\n"
        "  To enable them, add ONE of these in the Replit Secrets tab:\n"
        "    • GOOGLE_PLACES_API_KEY  (preferred — Places API + Photos)\n"
        "    • SERPAPI_KEY            (fallback — SerpApi Google Maps)\n"
        "\n"
        "  Until then, articles fall back to the existing dynamic image\n"
        "  search chain and LLM-estimated scores.\n"
        "─────────────────────────────────────────────────────────────────"
    )


def _resolve_google_photo_url(photo_ref: str, api_key: str) -> str | None:
    """
    Resolve a Google Place Photo reference to the final CDN URL (typically
    `lh3.googleusercontent.com/...`) WITHOUT ever returning a URL that embeds
    our API key.

    The Places Photo endpoint itself requires `key=<api_key>` as a query
    param, but it immediately 302s to a key-free googleusercontent.com URL.
    We follow that redirect server-side and hand back only the `Location`
    header — never the request URL that carried the key. If the response is
    a direct 200 (no redirect) we discard it rather than risk leaking the
    key-bearing URL to callers, since every other slot has none of this risk.
    """
    request_url = (
        "https://maps.googleapis.com/maps/api/place/photo"
        f"?maxwidth=1600&photoreference={urllib.parse.quote(photo_ref)}"
        f"&key={api_key}"
    )
    try:
        resp = requests.get(
            request_url, timeout=_REQUEST_TIMEOUT, allow_redirects=False, stream=True,
        )
        location = resp.headers.get("Location")
        if location and "key=" not in location:
            return location
        logger.warning(
            "Google Places photo endpoint did not redirect to a key-free URL "
            "(status=%s) — dropping this photo rather than leaking the API key.",
            resp.status_code,
        )
        return None
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to resolve Google Places photo URL: %s", exc)
        return None


def _coerce_rating(value) -> float | None:
    """Best-effort numeric coercion — providers occasionally return ratings
    as strings or omit them; never let a malformed value blow up scoring."""
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


def _google_places_search(location: str, limit: int) -> list[PropertyListing]:
    api_key = get_settings().google_places_api_key
    if not api_key:
        return []

    query = f"top rated luxury hotels resorts villas boutique stays in {location}"
    try:
        resp = requests.get(
            "https://maps.googleapis.com/maps/api/place/textsearch/json",
            params={"query": query, "key": api_key},
            timeout=_REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        status = data.get("status")
        if status not in ("OK", "ZERO_RESULTS"):
            logger.warning(
                "Google Places textsearch error for %r: %s (%s)",
                location, status, data.get("error_message", ""),
            )
            return []

        listings: list[PropertyListing] = []
        for place in data.get("results", []):
            photos = place.get("photos") or []
            if not photos:
                # A listing with no live photo is useless for the image
                # grid — skip it rather than surfacing a name-only card.
                continue
            photo_ref = photos[0].get("photo_reference")
            if not photo_ref:
                continue
            # Never store/return the maxwidth=...&key=<api_key> request URL —
            # resolve it server-side to the key-free CDN URL Google redirects
            # to. Skip the listing entirely if that resolution fails, rather
            # than risk leaking the API key to article HTML/JSON.
            photo_url = _resolve_google_photo_url(photo_ref, api_key)
            if not photo_url:
                continue
            place_id = place.get("place_id")
            listings.append(
                PropertyListing(
                    name=place.get("name") or "",
                    photo_url=photo_url,
                    rating=_coerce_rating(place.get("rating")),
                    review_count=_coerce_review_count(place.get("user_ratings_total")),
                    address=place.get("formatted_address"),
                    maps_url=(
                        f"https://www.google.com/maps/place/?q=place_id:{place_id}"
                        if place_id else None
                    ),
                )
            )
            if len(listings) >= limit:
                break
        return listings
    except Exception as exc:  # noqa: BLE001
        logger.warning("Google Places search failed for %r: %s", location, exc)
        return []


def _google_place_details_photos(place_id: str, api_key: str, max_photos: int) -> list[str]:
    """
    Fetch up to *max_photos* real photo URLs belonging to ONE specific
    Google Place (via Place Details), resolved to key-free CDN URLs.
    Returns [] on any failure — callers must never publish a photo from a
    different business as a substitute.
    """
    try:
        resp = requests.get(
            "https://maps.googleapis.com/maps/api/place/details/json",
            params={"place_id": place_id, "fields": "photo", "key": api_key},
            timeout=_REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") != "OK":
            return []
        photos = (data.get("result") or {}).get("photos") or []
        urls: list[str] = []
        for photo in photos[:max_photos]:
            photo_ref = photo.get("photo_reference")
            if not photo_ref:
                continue
            url = _resolve_google_photo_url(photo_ref, api_key)
            if url:
                urls.append(url)
        return urls
    except Exception as exc:  # noqa: BLE001
        logger.warning("Google Place Details photo fetch failed for place_id=%r: %s", place_id, exc)
        return []


def _serpapi_maps_photos_gallery(data_id: str, api_key: str, max_photos: int) -> list[str]:
    """
    Fetch up to *max_photos* real photo URLs from SerpApi's dedicated
    `google_maps_photos` engine for the business identified by *data_id* —
    the same public photo gallery a user sees scrolling through that
    business's own Google Maps listing (exteriors, rooms, pool, dining,
    etc), not just the single search-result thumbnail. Returns [] on any
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
        urls: list[str] = []
        for photo in photos[:max_photos]:
            url = photo.get("thumbnail") or photo.get("image")
            if url:
                urls.append(_upscale_lh3_photo_url(url) or url)
        return urls
    except Exception as exc:  # noqa: BLE001
        logger.warning("SerpApi google_maps_photos lookup failed for data_id=%r: %s", data_id, exc)
        return []


def fetch_property_by_name(
    name: str, location: str | None = None, max_photos: int = 15,
) -> PropertyListing | None:
    """
    Look up ONE specific, named business (e.g. "Hyatt Dehradun") and return a
    PropertyListing carrying every real photo we can find that belongs to
    THAT SAME business (via Google Place Details, or a single SerpApi
    thumbnail as a lesser fallback).

    This is the strict, single-property counterpart to `fetch_premium_stays`
    (which returns MANY DIFFERENT businesses for a location). It exists so a
    review article about one named property never mixes in another
    business's photos or a generic stock image — every slot cycles through
    this one listing's own verified photo pool instead.

    Returns None (never raises) if the property can't be matched or has no
    real photos at all — callers must treat that as "no strict pool
    available" and fall back to their own broader/degraded path.
    """
    name = (name or "").strip()
    if not name:
        return None
    query = f"{name} {location or ''}".strip()

    settings = get_settings()

    # -- Google Places: Text Search for the exact business, then Place
    # Details to pull its FULL photo gallery (not just the first photo).
    if settings.google_places_api_key:
        api_key = settings.google_places_api_key
        try:
            resp = requests.get(
                "https://maps.googleapis.com/maps/api/place/textsearch/json",
                params={"query": query, "key": api_key},
                timeout=_REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results") or []
            if data.get("status") == "OK" and results:
                place = results[0]
                place_id = place.get("place_id")
                photo_urls = (
                    _google_place_details_photos(place_id, api_key, max_photos)
                    if place_id else []
                )
                if not photo_urls:
                    # Details lookup failed/empty — fall back to the single
                    # photo already present on the text-search result, if any.
                    photos = place.get("photos") or []
                    if photos and photos[0].get("photo_reference"):
                        single = _resolve_google_photo_url(photos[0]["photo_reference"], api_key)
                        if single:
                            photo_urls = [single]
                if photo_urls:
                    logger.info(
                        "Strict single-property photo pool resolved for %r via Google Places: %d photo(s)",
                        name, len(photo_urls),
                    )
                    return PropertyListing(
                        name=place.get("name") or name,
                        photo_url=photo_urls[0],
                        rating=_coerce_rating(place.get("rating")),
                        review_count=_coerce_review_count(place.get("user_ratings_total")),
                        address=place.get("formatted_address"),
                        maps_url=(
                            f"https://www.google.com/maps/place/?q=place_id:{place_id}"
                            if place_id else None
                        ),
                        photo_urls=photo_urls,
                    )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Google Places single-property lookup failed for %r: %s", name, exc)

    # -- SerpApi fallback: the initial google_maps search result usually
    # carries only a single thumbnail, but every listing also has a
    # `data_id` we can feed into SerpApi's dedicated `google_maps_photos`
    # engine to pull the FULL public photo gallery for that exact business
    # (the same gallery you'd see scrolling through its Google Maps listing
    # — pool, rooms, dining, exteriors, etc). We always try that enrichment
    # step; the single thumbnail is only used as a last-resort if it fails.
    if settings.serpapi_key:
        try:
            resp = requests.get(
                "https://serpapi.com/search.json",
                params={
                    "engine": "google_maps",
                    "q": query,
                    "type": "search",
                    "api_key": settings.serpapi_key,
                },
                timeout=_REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
            results = data.get("local_results") or data.get("place_results") or []
            if isinstance(results, dict):
                results = [results]
            if results:
                place = results[0]
                thumbnail = _upscale_lh3_photo_url(
                    place.get("thumbnail") or place.get("photo") or place.get("serpapi_thumbnail")
                )
                data_id = place.get("data_id")

                photo_urls: list[str] = []
                if data_id:
                    photo_urls = _serpapi_maps_photos_gallery(
                        data_id, settings.serpapi_key, max_photos,
                    )

                if not photo_urls:
                    # Gallery lookup unavailable/empty — fall back to
                    # whatever single photo(s) the search result itself
                    # carried, still strictly belonging to this business.
                    extra = place.get("photos") or []
                    extra_urls = [
                        _upscale_lh3_photo_url(p.get("thumbnail") or p.get("image"))
                        for p in extra
                        if isinstance(p, dict) and (p.get("thumbnail") or p.get("image"))
                    ][:max_photos]
                    photo_urls = [u for u in ([thumbnail] + extra_urls) if u]

                # De-dup while preserving order.
                seen: set[str] = set()
                photo_urls = [u for u in photo_urls if not (u in seen or seen.add(u))]
                if photo_urls:
                    logger.info(
                        "Strict single-property photo pool resolved for %r via SerpApi: %d photo(s)",
                        name, len(photo_urls),
                    )
                    return PropertyListing(
                        name=place.get("title") or name,
                        photo_url=photo_urls[0],
                        rating=_coerce_rating(place.get("rating")),
                        review_count=_coerce_review_count(place.get("reviews")),
                        address=place.get("address"),
                        maps_url=place.get("link"),
                        photo_urls=photo_urls,
                    )
        except Exception as exc:  # noqa: BLE001
            logger.warning("SerpApi single-property lookup failed for %r: %s", name, exc)

    return None


def _serpapi_maps_search(location: str, limit: int) -> list[PropertyListing]:
    api_key = get_settings().serpapi_key
    if not api_key:
        return []

    query = f"top rated luxury hotels resorts villas boutique stays in {location}"
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
                continue
            listings.append(
                PropertyListing(
                    name=place.get("title") or "",
                    photo_url=thumbnail,
                    rating=_coerce_rating(place.get("rating")),
                    review_count=_coerce_review_count(place.get("reviews")),
                    address=place.get("address"),
                    maps_url=place.get("link"),
                )
            )
            if len(listings) >= limit:
                break
        return listings
    except Exception as exc:  # noqa: BLE001
        logger.warning("SerpApi Google Maps search failed for %r: %s", location, exc)
        return []


def fetch_premium_stays(location: str | None, limit: int = 8) -> list[PropertyListing]:
    """
    Return up to *limit* real, distinct premium hotel/villa/boutique-stay
    listings for *location*, each carrying a live Google Maps photo URL and
    a live star rating pulled from an actual business listing.

    Provider order: Google Places API, then SerpApi Google Maps. Returns an
    empty list (never raises, never fabricates data) when neither provider
    is configured or both fail — callers must treat that as "no live data"
    and fall back to their own path rather than assuming a listing exists.
    """
    location = (location or "").strip()
    if not location:
        return []

    for provider in (_google_places_search, _serpapi_maps_search):
        try:
            listings = provider(location, limit)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Property listing provider %s raised for %r: %s",
                provider.__name__, location, exc,
            )
            listings = []
        if listings:
            logger.info(
                "Live property listings resolved for %r via %s: %d found",
                location, provider.__name__, len(listings),
            )
            return listings

    if not get_settings().google_places_api_key and not get_settings().serpapi_key:
        _log_missing_key_notice()
    else:
        logger.info("No live property listings found for %r from any configured provider.", location)
    return []
