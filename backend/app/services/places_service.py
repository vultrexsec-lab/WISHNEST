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

# Non-hospitality entities must never become property reviews (client quality audit).
_BLOCKED_NAME_FRAGMENTS = (
    "india gate", "gateway of india", "mysuru palace", "mysore palace",
    "red fort", "qutub minar", "taj mahal", "lotus temple", "humayun",
    "national museum", "railway station", "bus stand", "airport",
    "sotheby's", "sothebys", "sotheby", "knight frank", "cushman", "colliers",
    "real estate", "realestate", "realty", "realtor", "brokerage", "broker",
    "property dealer", "property consultant", "sales office", "showroom",
    "private limited", "pvt ltd", "pvt. ltd", "pvt ltd.", "limited company",
    "corporate office", "head office", "co-working", "coworking",
    "charminar", "victoria memorial", "hawa mahal",
    "amer fort", "amber fort", "city palace", "jal mahal", "fatehpur sikri",
    "ajanta", "ellora", "konark", "meenakshi temple", "golden temple",
    "statue of unity", "howrah bridge", "marina beach",
    "homes private", "properties private", "developers private",
    "construction pvt", "infra pvt", "buildcon", "realtors",
)
_BLOCKED_TYPE_FRAGMENTS = (
    "tourist_attraction", "museum", "hindu_temple", "church", "mosque",
    "cemetery", "park", "zoo", "amusement", "shopping_mall", "department_store",
    "real_estate_agency", "lawyer", "atm", "bank", "gas_station", "parking",
    "school", "university", "hospital", "doctor", "embassy", "government",
    "locality", "political", "route", "intersection",
)
_HOSPITALITY_TYPE_HINTS = (
    "hotel", "lodging", "resort", "guest_house", "guest house", "hostel",
    "motel", "villa", "homestay", "home stay", "bed_and_breakfast",
    "boutique_hotel", "boutique hotel", "campground", "spa_hotel", "retreat",
)


def is_hospitality_listing(
    name: str | None,
    place_type: str | None = None,
    types: list | None = None,
    address: str | None = None,
) -> bool:
    """
    Return False for monuments, civic landmarks, pure offices, and other
    non-stay entities that must not enter the property-review pipeline.
    """
    blob = " ".join(
        str(x).lower()
        for x in [name or "", place_type or "", address or ""]
        + list(types or [])
    )
    for frag in _BLOCKED_NAME_FRAGMENTS:
        if frag in blob:
            return False
    for frag in _BLOCKED_TYPE_FRAGMENTS:
        if frag in blob:
            return False
    # If SerpApi/Google gives explicit types, require a hospitality hint when present
    type_blob = " ".join(str(x).lower() for x in ([place_type] if place_type else []) + list(types or []))
    if type_blob.strip():
        if any(h in type_blob for h in _HOSPITALITY_TYPE_HINTS):
            return True
        # typed but no hospitality signal → reject
        if any(x in type_blob for x in ("establishment", "point_of_interest", "premise")):
            # weak types only — allow if name looks like a stay
            n = (name or "").lower()
            if any(h in n for h in ("hotel", "resort", "villa", "lodge", "inn", "retreat", "homestay", "palace hotel", "suites")):
                return True
            return False
    n = (name or "").lower()
    if any(
        h in n
        for h in (
            "hotel", "resort", "villa", "lodge", "inn", "retreat", "homestay",
            "boutique stay", "camp", "suites", "palace hotel", "guest house",
            "guesthouse", "bungalow stay", "farmstay",
        )
    ):
        return True
    # No clear hospitality signal — reject (prevents monuments / POIs as "reviews")
    return False



def is_non_hospitality_title(title: str | None) -> bool:
    """True only for clear non-stay commercial entities (realty, offices).

    Do NOT use inverse of is_hospitality_listing — destinations, beaches,
    guides and landmarks are separate editorial categories and must not be
    auto-trashed by this helper.
    """
    n = (title or "").lower()
    hard = (
        "sotheby", "sothebys", "knight frank", "cushman", "colliers",
        "realty", "real estate", "realestate", "realtors", "realtor",
        "brokerage", "property dealer", "property consultant",
        "private limited", "pvt ltd", "pvt. ltd", "pvt ltd.",
        "corporate office", "sales office", "co-working", "coworking",
        "propertyincoorg",
    )
    return any(h in n for h in hard)



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
    listing (exteriors, rooms, pool, dining, etc).

    Paginates automatically using SerpApi's `next_page_token` so that large
    galleries (50+ photos) are fully harvested rather than capped at the
    default first-page size (~10 results). Returns [] on any failure or empty
    response; never raises.
    """
    _MAX_PAGES = 6  # hard cap — prevents runaway API spend (6 × ~10 = up to 60 photos)
    try:
        result: list[dict] = []
        next_page_token: str | None = None
        pages_fetched = 0

        while len(result) < max_photos and pages_fetched < _MAX_PAGES:
            params: dict = {
                "engine": "google_maps_photos",
                "data_id": data_id,
                "api_key": api_key,
            }
            if next_page_token:
                params["next_page_token"] = next_page_token

            resp = requests.get(
                "https://serpapi.com/search.json",
                params=params,
                timeout=_REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
            pages_fetched += 1

            photos = data.get("photos") or []
            if not photos:
                break  # no more results

            for photo in photos:
                if len(result) >= max_photos:
                    break
                url = photo.get("thumbnail") or photo.get("image")
                if url:
                    # SerpApi returns tags as a list or single string — normalise.
                    raw_tag = photo.get("tag") or photo.get("tags") or []
                    if isinstance(raw_tag, str):
                        raw_tag = [raw_tag]
                    tags = [t.strip().lower() for t in raw_tag if isinstance(t, str) and t.strip()]
                    result.append({"url": _upscale_lh3_photo_url(url) or url, "tags": tags})

            # Advance to next page if available
            pagination = data.get("serpapi_pagination") or {}
            next_page_token = pagination.get("next_page_token")
            if not next_page_token:
                break  # no more pages

        if pages_fetched > 1:
            logger.info(
                "SerpApi google_maps_photos: fetched %d photos across %d page(s) for data_id=%r",
                len(result), pages_fetched, data_id,
            )
        return result
    except Exception as exc:  # noqa: BLE001
        logger.warning("SerpApi google_maps_photos lookup failed for data_id=%r: %s", data_id, exc)
        return []


# ---------------------------------------------------------------------------
# SerpApi — property search (replaces Google Places Text Search entirely)
# ---------------------------------------------------------------------------

def _serpapi_maps_query(query: str, limit: int, *, hospitality_only: bool = True) -> list[PropertyListing]:
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
            title = place.get("title") or ""
            addr = place.get("address")
            ptype = place.get("type") or place.get("category") or ""
            if hospitality_only and not is_hospitality_listing(title, ptype, address=addr):
                logger.info("Skipped non-hospitality Maps result: %r (%s)", title[:80], ptype)
                continue
            listings.append(
                PropertyListing(
                    name=title,
                    photo_url=thumbnail,
                    rating=_coerce_rating(place.get("rating")),
                    review_count=_coerce_review_count(place.get("reviews")),
                    address=addr,
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
    """Prefer 5-star hotels and resorts; merge unique listings across query angles."""
    queries = [
        f"5 star hotel luxury resort in {location}",
        f"top rated luxury resort in {location}",
        f"best heritage hotel in {location}",
        f"top rated luxury hotels resorts in {location}",
    ]
    seen: set[str] = set()
    merged: list[PropertyListing] = []
    for q in queries:
        if len(merged) >= limit:
            break
        for item in _serpapi_maps_query(q, limit):
            key = (item.place_id or item.name or "").lower()
            if not key or key in seen:
                continue
            seen.add(key)
            merged.append(item)
            if len(merged) >= limit:
                break
    return merged[:limit]


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
        listings = _serpapi_maps_query(query, limit, hospitality_only=False)
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
    name: str, location: str | None = None, max_photos: int = 75,
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
        resolved_name = place.get("title") or name
        resolved_addr = place.get("address")
        resolved_type = place.get("type") or place.get("category") or ""
        if not is_hospitality_listing(resolved_name, resolved_type, address=resolved_addr):
            logger.warning(
                "Rejected non-hospitality place for review pipeline: %r type=%r",
                resolved_name, resolved_type,
            )
            return None
        return PropertyListing(
            name=resolved_name,
            photo_url=photo_urls[0],
            rating=_coerce_rating(place.get("rating")),
            review_count=_coerce_review_count(place.get("reviews")),
            address=resolved_addr,
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

    listings = _serpapi_maps_query(query, limit, hospitality_only=True)
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


def text_search_place(query: str, max_photos: int = 75) -> PropertyListing | None:
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



_EMAIL_SKIP = (
    "example.", "sentry.", "wixpress", "domain.com", "email.com", "your@",
    "noreply", "no-reply", "donotreply", "privacy@", "legal@", "support@godaddy",
    "wordpress", "schema.org", "w3.org", "googleapis",
)


def _clean_email(em: str | None) -> str | None:
    if not em:
        return None
    el = em.strip().lower().rstrip(".,;>")
    if not el or "@" not in el:
        return None
    if any(s in el for s in _EMAIL_SKIP):
        return None
    if el.endswith((".png", ".jpg", ".gif", ".css", ".js", ".svg", ".webp")):
        return None
    return el


def _clean_phone(raw) -> str | None:
    if raw is None:
        return None
    if isinstance(raw, dict):
        raw = raw.get("number") or raw.get("national") or raw.get("international") or raw.get("text")
    s = str(raw).strip()
    if not s:
        return None
    # Keep leading + and digits
    digits = re.sub(r"[^\d+]", "", s)
    if digits.count("+") > 1:
        digits = digits.replace("+", "")
        digits = "+" + digits
    core = digits.lstrip("+")
    if len(core) < 8:
        return None
    return digits


def extract_email_from_website(url: str | None, timeout: float = 6.0) -> str | None:
    """Best-effort public email from website homepage + common contact paths."""
    if not url or not str(url).startswith("http"):
        return None
    paths = ["", "/contact", "/contact-us", "/about", "/about-us"]
    base = str(url).rstrip("/")
    headers = {"User-Agent": "WishNestBot/1.0 (+https://wishnest.info)"}
    for path in paths:
        try:
            target = base if not path else (base + path)
            resp = requests.get(target, timeout=timeout, headers=headers, allow_redirects=True)
            if not resp.ok:
                continue
            html = resp.text[:250_000]
            m = re.search(
                r"mailto:([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})",
                html,
                re.I,
            )
            if m:
                em = _clean_email(m.group(1))
                if em:
                    return em
            found = re.findall(
                r"\b([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})\b",
                html,
            )
            for em in found:
                el = _clean_email(em)
                if el:
                    return el
        except Exception as exc:
            logger.debug("email extract failed %s: %s", url, exc)
    return None


def extract_owner_from_website(url: str | None, timeout: float = 5.0) -> str | None:
    """Best-effort owner / proprietor name from public website text."""
    if not url or not str(url).startswith("http"):
        return None
    try:
        resp = requests.get(
            str(url),
            timeout=timeout,
            headers={"User-Agent": "WishNestBot/1.0 (+https://wishnest.info)"},
            allow_redirects=True,
        )
        if not resp.ok:
            return None
        # Strip tags roughly
        text = re.sub(r"<script[\s\S]*?</script>", " ", resp.text[:200_000], flags=re.I)
        text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text)
        patterns = [
            r"(?:owner|proprietor|founded by|managed by|promoted by)\s*[:\-]?\s*"
            r"(?:mr\.?|mrs\.?|ms\.?|dr\.?)?\s*([A-Z][a-zA-Z]{1,20}(?:\s+[A-Z][a-zA-Z]{1,20}){0,3})",
            r"(?:स्वामी|मालिक)\s*[:\-]?\s*([A-Za-z][A-Za-z\s]{2,40})",
        ]
        for pat in patterns:
            m = re.search(pat, text, re.I)
            if m:
                name = re.sub(r"\s+", " ", m.group(1)).strip(" .,-")
                if 3 <= len(name) <= 60 and not any(
                    x in name.lower() for x in ("hotel", "resort", "villa", "limited", "company", "private")
                ):
                    return name
    except Exception as exc:
        logger.debug("owner extract failed %s: %s", url, exc)
    return None


@dataclass
class BusinessLead:
    """Public business listing for CRM intake (not editorial photos)."""
    name: str
    address: str | None = None
    phone: str | None = None
    website: str | None = None
    rating: float | None = None
    review_count: int | None = None
    maps_url: str | None = None
    place_id: str | None = None
    category: str | None = None
    email: str | None = None
    owner_name: str | None = None


def _lead_from_maps_place(place: dict, fallback_category: str) -> BusinessLead | None:
    if not isinstance(place, dict):
        return None
    name = (place.get("title") or place.get("name") or "").strip()
    if not name:
        return None
    phone = (
        place.get("phone")
        or place.get("phone_number")
        or place.get("international_phone")
        or place.get("formatted_phone_number")
        or place.get("phoneNumber")
    )
    if not phone and isinstance(place.get("extensions"), list):
        for ext in place["extensions"]:
            if not isinstance(ext, str):
                continue
            m = re.search(r"(\+?\d[\d\s\-()]{8,}\d)", ext)
            if m:
                phone = m.group(1)
                break
    if not phone:
        for k, v in place.items():
            if not isinstance(v, str) or k in ("title", "name", "address", "description", "type", "hours"):
                continue
            m = re.search(r"(\+?91[\s\-]?\d{10}|\+?\d{10,13})", v)
            if m:
                phone = m.group(1)
                break
    website = place.get("website") or place.get("site") or place.get("web_site")
    cat = place.get("type") or place.get("category") or place.get("types")
    if isinstance(cat, list):
        cat = ", ".join(str(c) for c in cat[:3])
    return BusinessLead(
        name=name,
        address=place.get("address") or place.get("formatted_address"),
        phone=_clean_phone(phone),
        website=str(website).strip() if website else None,
        rating=_coerce_rating(place.get("rating")),
        review_count=_coerce_review_count(place.get("reviews") or place.get("user_ratings_total")),
        maps_url=place.get("link") or place.get("place_id_search"),
        place_id=place.get("data_id") or place.get("place_id") or place.get("data_cid"),
        category=str(cat) if cat else fallback_category,
        email=_clean_email(place.get("email")),
    )


def _serpapi_place_details(data_id: str | None, api_key: str, timeout: float = 8.0) -> dict:
    """Fetch full Maps place card (phone / website often only here)."""
    if not data_id or not api_key:
        return {}
    try:
        params = {
            "engine": "google_maps",
            "type": "place",
            "data_id": data_id,
            "api_key": api_key,
            "hl": "en",
            "gl": "in",
        }
        resp = requests.get(
            "https://serpapi.com/search.json",
            params=params,
            timeout=timeout,
        )
        if not resp.ok:
            return {}
        data = resp.json() or {}
        pr = data.get("place_results") or data
        return pr if isinstance(pr, dict) else {}
    except Exception as exc:
        logger.debug("place details failed %s: %s", data_id[:40] if data_id else "", exc)
        return {}


def _apply_place_details_to_lead(lead: "BusinessLead", pr: dict) -> None:
    if not pr:
        return
    if not lead.phone:
        lead.phone = _clean_phone(
            pr.get("phone")
            or pr.get("phone_number")
            or pr.get("international_phone")
            or pr.get("formatted_phone_number")
        )
    w = pr.get("website") or pr.get("site")
    if w and not lead.website:
        lead.website = str(w).strip()
    if not lead.email:
        lead.email = _clean_email(pr.get("email"))
    if not lead.address and pr.get("address"):
        lead.address = pr.get("address")


def enrich_leads_contact_fields(
    leads: list[BusinessLead],
    *,
    max_detail_lookups: int = 30,
    max_website_fetches: int = 10,
    fast: bool = True,
) -> list[BusinessLead]:
    """
    Parallel place-details for missing phones (wall-clock ~8-15s), then light website email.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    if not fast:
        max_detail_lookups = max(max_detail_lookups, 40)
        max_website_fetches = max(max_website_fetches, 20)

    api_key = get_settings().serpapi_key or ""
    # Parallel place details for leads missing phone
    need = [L for L in leads if not L.phone and L.place_id][:max_detail_lookups]
    if need and api_key:
        def _one(lead: BusinessLead):
            pr = _serpapi_place_details(lead.place_id, api_key, timeout=7.0)
            return lead, pr

        workers = min(8, len(need))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futs = [pool.submit(_one, L) for L in need]
            for fut in as_completed(futs):
                try:
                    lead, pr = fut.result()
                    _apply_place_details_to_lead(lead, pr)
                except Exception as exc:
                    logger.debug("parallel detail failed: %s", exc)

    # Also fill website for leads that already had phone but no website (for email)
    need_web = [L for L in leads if L.phone and not L.website and L.place_id][: max(0, max_detail_lookups // 2)]
    if need_web and api_key and not fast:
        def _one_web(lead: BusinessLead):
            pr = _serpapi_place_details(lead.place_id, api_key, timeout=6.0)
            return lead, pr
        with ThreadPoolExecutor(max_workers=min(6, len(need_web))) as pool:
            for fut in as_completed([pool.submit(_one_web, L) for L in need_web]):
                try:
                    lead, pr = fut.result()
                    _apply_place_details_to_lead(lead, pr)
                except Exception:
                    pass

    web_used = 0
    for lead in leads:
        if lead.website and web_used < max_website_fetches and not lead.email:
            lead.email = extract_email_from_website(lead.website, timeout=3.0) or lead.email
            web_used += 1
        if lead.website and not lead.owner_name and not fast and web_used <= max_website_fetches:
            lead.owner_name = extract_owner_from_website(lead.website, timeout=2.5)

    return leads


def search_hospitality_for_crm(
    region: str,
    category: str = "hotels",
    limit: int = 60,
) -> list[BusinessLead]:
    """
    Google Maps (via SerpApi) — many public business listings for CRM intake.
    Multiple related queries + pagination to increase coverage within a region.
    Not Google Pay, not social networks. Email almost never present.
    """
    api_key = get_settings().serpapi_key
    if not api_key:
        _log_missing_key_notice()
        return []

    region = (region or "").strip()
    category = (category or "hotels").strip()
    if not region:
        return []

    limit = max(1, min(int(limit or 100), 120))

    # Split user category + hospitality variants for wider coverage
    bits = [b.strip() for b in category.replace(",", " ").split() if b.strip()]
    # Prefer hotels/resorts first — Maps list cards more often include phone than pure villa ads
    preferred = ["hotels", "resorts", "hotel", "resort"]
    terms: list[str] = []
    for t in preferred + bits:
        tl = t.lower()
        if tl not in [x.lower() for x in terms]:
            terms.append(t)
    terms = terms[:4]

    queries = [f"{term} in {region}" for term in terms]
    # Also a broader catch-all

    out: list[BusinessLead] = []
    seen: set[str] = set()

    def _ingest(results: list) -> None:
        for place in results:
            if len(out) >= limit:
                return
            lead = _lead_from_maps_place(place, category)
            if not lead:
                continue
            key = lead.name.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(lead)

    try:
        for q in queries:
            if len(out) >= limit:
                break
            # Two pages max — keeps search under client/proxy timeout
            for start in (0, 20):
                if len(out) >= limit:
                    break
                params = {
                    "engine": "google_maps",
                    "q": q,
                    "type": "search",
                    "api_key": api_key,
                    "hl": "en",
                    "gl": "in",
                }
                if start:
                    params["start"] = start
                try:
                    resp = requests.get(
                        "https://serpapi.com/search.json",
                        params=params,
                        timeout=_REQUEST_TIMEOUT,
                    )
                    resp.raise_for_status()
                    data = resp.json()
                except Exception as exc:
                    logger.warning("CRM places page failed q=%s start=%s: %s", q[:40], start, exc)
                    break
                results = data.get("local_results") or data.get("place_results") or []
                if isinstance(results, dict):
                    results = [results]
                if not results:
                    break
                before = len(out)
                _ingest(results)
                if len(out) == before:
                    # no new unique rows
                    break
        # Fast enrich only — full website email pass is on Import (avoids 120s timeouts)
        try:
            enrich_leads_contact_fields(out[:limit], max_detail_lookups=28, max_website_fetches=8, fast=True)
        except Exception as enr:
            logger.warning("CRM places fast enrich failed: %s", enr)
        out.sort(key=lambda L: (0 if (L.phone or "").strip() else 1, (L.name or "").lower()))
        return out[:limit]
    except Exception as exp:
        logger.warning("CRM places search failed: %s", exp)
        return out[:limit]
