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
import urllib.parse
from dataclasses import dataclass

import requests

from app.config import get_settings

logger = logging.getLogger("wishnest.places_service")

_REQUEST_TIMEOUT = 10
_warned_missing_key = False


@dataclass
class PropertyListing:
    """One real, named business listing with a live photo + live rating."""
    name: str
    photo_url: str | None       # raw upstream URL — caller is responsible for proxying it
    rating: float | None        # Google star rating, 1.0-5.0
    review_count: int | None
    address: str | None
    maps_url: str | None


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
            thumbnail = place.get("thumbnail") or place.get("photo") or place.get("serpapi_thumbnail")
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
