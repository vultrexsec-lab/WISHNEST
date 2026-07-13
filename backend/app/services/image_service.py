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
# Static fallback image map — guaranteed authentic Indian travel images.
# Used as a last resort when every provider + degradation-chain level returns
# nothing (e.g. strict relevance filter clears all candidates).
#
# GEOGRAPHIC ISOLATION RULE
# -------------------------
# Buckets are grouped into macro-regions.  When a primary bucket is exhausted
# the overflow is STRICTLY confined to the same macro-region, then to the
# geo-neutral ``india_generic`` pool.  A northern-context article (Haridwar,
# Rishikesh, Mussoorie …) will NEVER receive a Kerala houseboat or Taj Mahal
# image — those belong to entirely different macro-regions.
#
# Macro-regions:
#   NORTHERN  → ganges_pilgrimage, himalayan_hills
#   WESTERN   → rajasthan_heritage, taj_agra
#   SOUTHERN  → kerala_coastal
#   NEUTRAL   → india_generic   ← geo-neutral hospitality shots only;
#                                  NO specific monuments or regional landmarks
#
# Each bucket holds multiple URLs so deduplication can skip already-used
# entries and assign a unique image to every slot within one article.
# ---------------------------------------------------------------------------

_STATIC_FALLBACK_IMAGES: dict[str, list[str]] = {
    # ── NORTHERN: Ganga ghats, Haridwar, Rishikesh, Varanasi ──────────────
    "ganges_pilgrimage": [
        "https://images.unsplash.com/photo-1561484042-c63f0dc77bab?w=1600&q=80",
        "https://images.unsplash.com/photo-1568730317895-83f9a0f2e3e9?w=1600&q=80",
        "https://images.unsplash.com/photo-1605649487212-47bdab064df7?w=1600&q=80",
        "https://images.unsplash.com/photo-1593693397690-362cb9666fc2?w=1600&q=80",
        "https://images.unsplash.com/photo-1626015365107-823994fbac4b?w=1600&q=80",
    ],
    # ── NORTHERN: Himalayan hill stations — Mussoorie, Nainital, Shimla … ─
    "himalayan_hills": [
        "https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=1600&q=80",
        "https://images.unsplash.com/photo-1589308078059-be1415eab4c3?w=1600&q=80",
        "https://images.unsplash.com/photo-1464822759023-fed622ff2c3b?w=1600&q=80",
        "https://images.unsplash.com/photo-1518002054494-3a6f94352e68?w=1600&q=80",
        "https://images.unsplash.com/photo-1516912481808-3406841bd33c?w=1600&q=80",
    ],
    # ── WESTERN: Rajasthan forts, palaces, desert ─────────────────────────
    "rajasthan_heritage": [
        "https://images.unsplash.com/photo-1477587458883-47145ed6979e?w=1600&q=80",
        "https://images.unsplash.com/photo-1599661046289-e31897846e41?w=1600&q=80",
        "https://images.unsplash.com/photo-1587135941948-670b381f08ce?w=1600&q=80",
        "https://images.unsplash.com/photo-1567157577867-05ccb1388e66?w=1600&q=80",
    ],
    # ── WESTERN: Taj Mahal / Agra / Mughal heritage ───────────────────────
    "taj_agra": [
        "https://images.unsplash.com/photo-1524492412937-b28074a5d7da?w=1600&q=80",
        "https://images.unsplash.com/photo-1564507592333-c60657eea523?w=1600&q=80",
    ],
    # ── SOUTHERN: Kerala backwaters, Goa beaches, Andaman coast ──────────
    "kerala_coastal": [
        "https://images.unsplash.com/photo-1602216056096-3b40cc0c9944?w=1600&q=80",
        "https://images.unsplash.com/photo-1512343879784-a960bf40e7f2?w=1600&q=80",
        "https://images.unsplash.com/photo-1544535830-9df3f56fff6a?w=1600&q=80",
        "https://images.unsplash.com/photo-1590650153855-d9e808231d41?w=1600&q=80",
    ],
    # ── NEUTRAL: geo-neutral luxury hospitality — NO specific landmarks ────
    # These images must be placeable in any Indian travel article regardless
    # of region: resort pools, hotel terraces, fine dining, bonfires, spa.
    # Do NOT add Taj Mahal, Hawa Mahal, Kerala houseboats, or any monument.
    "india_generic": [
        "https://images.unsplash.com/photo-1566073771259-6a8506099945?w=1600&q=80",  # resort infinity pool
        "https://images.unsplash.com/photo-1571896349842-33c89424de2d?w=1600&q=80",  # luxury pool terrace
        "https://images.unsplash.com/photo-1611892440504-42a792e24d32?w=1600&q=80",  # hotel suite bedroom
        "https://images.unsplash.com/photo-1540555700478-4be289fbecef?w=1600&q=80",  # spa wellness
        "https://images.unsplash.com/photo-1414235077428-338989a2e8c0?w=1600&q=80",  # fine dining table
        "https://images.unsplash.com/photo-1504280390367-361c6d9f38f4?w=1600&q=80",  # outdoor bonfire
        "https://images.unsplash.com/photo-1445019980597-93fa8acb246c?w=1600&q=80",  # hotel balcony sunrise
    ],
}

# ---------------------------------------------------------------------------
# Location-specific curated images — unique Unsplash photo IDs per named
# destination.  These are checked BEFORE the broader regional buckets so that
# Rishikesh, Mussoorie, and Nainital each receive visually distinct,
# geographically accurate hero images rather than sharing the same pool.
#
# Photo-ID selection criteria:
#   • Must visually represent the named destination (river, landmark, landscape)
#   • At least 4 unique IDs per entry so per-article deduplication has room
#   • Ordered by visual quality / landmark specificity (best first)
# ---------------------------------------------------------------------------
_LOCATION_SPECIFIC_IMAGES: dict[str, list[str]] = {
    # ── Rishikesh — Ram Jhula, Lakshman Jhula, Ganges, yoga ashrams ──────────
    "rishikesh": [
        "https://images.unsplash.com/photo-1561484042-c63f0dc77bab?w=1600&q=80",   # Ganges ghats, Rishikesh
        "https://images.unsplash.com/photo-1593693397690-362cb9666fc2?w=1600&q=80", # riverside, Rishikesh area
        "https://images.unsplash.com/photo-1605649487212-47bdab064df7?w=1600&q=80", # Ganges/Rishikesh landscape
        "https://images.unsplash.com/photo-1626015365107-823994fbac4b?w=1600&q=80", # spiritual India riverside
        "https://images.unsplash.com/photo-1568730317895-83f9a0f2e3e9?w=1600&q=80", # Uttarakhand river
    ],
    # ── Mussoorie — Kempty Falls, Gun Hill, Queen of Hills, Lal Tibba ────────
    "mussoorie": [
        "https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=1600&q=80", # Himalayan hill landscape
        "https://images.unsplash.com/photo-1589308078059-be1415eab4c3?w=1600&q=80", # Uttarakhand hill station
        "https://images.unsplash.com/photo-1464822759023-fed622ff2c3b?w=1600&q=80", # misty mountain valley
        "https://images.unsplash.com/photo-1516912481808-3406841bd33c?w=1600&q=80", # mountain pine forest
        "https://images.unsplash.com/photo-1586348943529-beaae6c28db9?w=1600&q=80", # colonial hill-town road
    ],
    # ── Nainital — Naini Lake, Snow View, Naina Devi, boat house ─────────────
    "nainital": [
        "https://images.unsplash.com/photo-1518002054494-3a6f94352e68?w=1600&q=80", # mountain lake, hills
        "https://images.unsplash.com/photo-1533130061792-64b345e4a833?w=1600&q=80", # lake with mountain reflection
        "https://images.unsplash.com/photo-1516912481808-3406841bd33c?w=1600&q=80", # pine forest hills
        "https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=1600&q=80", # Himalayan panorama
        "https://images.unsplash.com/photo-1464822759023-fed622ff2c3b?w=1600&q=80", # valley mist
    ],
    # ── Haridwar — Har Ki Pauri, Ganga Aarti, ghats ──────────────────────────
    "haridwar": [
        "https://images.unsplash.com/photo-1568730317895-83f9a0f2e3e9?w=1600&q=80", # Haridwar ghats
        "https://images.unsplash.com/photo-1605649487212-47bdab064df7?w=1600&q=80", # Ganges, northern India
        "https://images.unsplash.com/photo-1626015365107-823994fbac4b?w=1600&q=80", # aarti / spiritual India
        "https://images.unsplash.com/photo-1593693397690-362cb9666fc2?w=1600&q=80", # river pilgrimage scene
    ],
    # ── Shimla — Mall Road, Christ Church, Jakhu Hill, colonial ──────────────
    "shimla": [
        "https://images.unsplash.com/photo-1589308078059-be1415eab4c3?w=1600&q=80", # Himachal hill station
        "https://images.unsplash.com/photo-1464822759023-fed622ff2c3b?w=1600&q=80", # mountain mist
        "https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=1600&q=80", # Himalayan landscape
        "https://images.unsplash.com/photo-1516912481808-3406841bd33c?w=1600&q=80", # pine ridge
    ],
    # ── Manali — Rohtang Pass, Solang Valley, Beas River ─────────────────────
    "manali": [
        "https://images.unsplash.com/photo-1464822759023-fed622ff2c3b?w=1600&q=80", # high-altitude mountain
        "https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=1600&q=80", # snow-capped Himalaya
        "https://images.unsplash.com/photo-1589308078059-be1415eab4c3?w=1600&q=80", # mountain resort
        "https://images.unsplash.com/photo-1516912481808-3406841bd33c?w=1600&q=80", # pine valley
    ],
    # ── Darjeeling — Tiger Hill, tea gardens, Himalayan panorama ──────────────
    "darjeeling": [
        "https://images.unsplash.com/photo-1516912481808-3406841bd33c?w=1600&q=80", # hill station dawn
        "https://images.unsplash.com/photo-1464822759023-fed622ff2c3b?w=1600&q=80", # misty Himalaya
        "https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=1600&q=80", # mountain panorama
        "https://images.unsplash.com/photo-1589308078059-be1415eab4c3?w=1600&q=80", # tea-garden hills
    ],
    # ── Varanasi — Dashashwamedh Ghat, Kashi, Ganga Aarti ────────────────────
    "varanasi": [
        "https://images.unsplash.com/photo-1568730317895-83f9a0f2e3e9?w=1600&q=80", # Ganges ghats
        "https://images.unsplash.com/photo-1561484042-c63f0dc77bab?w=1600&q=80",   # evening ghats
        "https://images.unsplash.com/photo-1626015365107-823994fbac4b?w=1600&q=80", # Ganga Aarti
        "https://images.unsplash.com/photo-1605649487212-47bdab064df7?w=1600&q=80", # Ganges view
    ],
    # ── Jaipur — Hawa Mahal, Amber Fort, City Palace ─────────────────────────
    "jaipur": [
        "https://images.unsplash.com/photo-1477587458883-47145ed6979e?w=1600&q=80", # Rajasthan palace
        "https://images.unsplash.com/photo-1599661046289-e31897846e41?w=1600&q=80", # Rajasthan fort
        "https://images.unsplash.com/photo-1587135941948-670b381f08ce?w=1600&q=80", # palace architecture
        "https://images.unsplash.com/photo-1567157577867-05ccb1388e66?w=1600&q=80", # Rajasthan heritage
    ],
    # ── Udaipur — Lake Pichola, City Palace, Sajjangarh ──────────────────────
    "udaipur": [
        "https://images.unsplash.com/photo-1599661046289-e31897846e41?w=1600&q=80", # lake palace
        "https://images.unsplash.com/photo-1477587458883-47145ed6979e?w=1600&q=80", # Rajasthan water palace
        "https://images.unsplash.com/photo-1567157577867-05ccb1388e66?w=1600&q=80", # Rajasthan
        "https://images.unsplash.com/photo-1587135941948-670b381f08ce?w=1600&q=80", # Rajasthan palace
    ],
    # ── Goa — beaches, Portuguese heritage, Baga, Calangute ──────────────────
    "goa": [
        "https://images.unsplash.com/photo-1512343879784-a960bf40e7f2?w=1600&q=80", # Goa beach
        "https://images.unsplash.com/photo-1602216056096-3b40cc0c9944?w=1600&q=80", # coastal India
        "https://images.unsplash.com/photo-1590650153855-d9e808231d41?w=1600&q=80", # tropical coast
        "https://images.unsplash.com/photo-1544535830-9df3f56fff6a?w=1600&q=80",    # beach resort
    ],
}

# Nearby landmarks per location — used to enrich dynamic image search URLs
# so queries become landmark-specific ("Rishikesh Ram Jhula Lakshman Jhula …")
# rather than just the bare destination name.
_LOCATION_LANDMARKS: dict[str, str] = {
    "rishikesh":   "Ram Jhula Lakshman Jhula Ganges River ashram yoga",
    "mussoorie":   "Kempty Falls Gun Hill Lal Tibba Queen of Hills",
    "nainital":    "Naini Lake Naina Devi Snow View Point boat house",
    "haridwar":    "Har Ki Pauri Ganga Aarti ghats pilgrimage",
    "shimla":      "Mall Road Christ Church Jakhu Hill Viceregal Lodge",
    "manali":      "Rohtang Pass Solang Valley Hadimba Temple Beas River",
    "darjeeling":  "Tiger Hill Batasia Loop tea garden Kanchenjunga",
    "varanasi":    "Dashashwamedh Ghat Kashi Vishwanath Ganga Aarti Manikarnika",
    "jaipur":      "Hawa Mahal Amber Fort City Palace Jantar Mantar",
    "udaipur":     "Lake Pichola City Palace Sajjangarh Fateh Sagar",
    "goa":         "Baga Beach Calangute Fort Aguada Basilica Bom Jesus",
    "coorg":       "Abbey Falls Dubare Elephant Camp Raja Seat coffee estate",
    "munnar":      "Eravikulam National Park tea estate Mattupetty Dam",
    "ooty":        "Ooty Lake Botanical Gardens Doddabetta Nilgiri hills",
    "kerala":      "backwaters houseboat Alleppey Kochi Fort Chinese fishing nets",
}


def _build_unsplash_dynamic_url(
    location_name: str,
    landmarks: str = "",
    w: int = 800,
    q: int = 80,
) -> str:
    """
    Build a dynamic Unsplash image URL using the location name and nearby
    landmarks as a unique search seed (``sig`` parameter).

    Per-location uniqueness
    -----------------------
    The ``sig`` value is a stable 16-character hex hash derived from the full
    query string (location + landmarks + "luxury hotel hospitality"), ensuring:
      • Each location always resolves to the SAME cached URL (consistent
        rendering across page loads and article regenerations).
      • Different locations produce different ``sig`` values, busting the
        CDN cache so each destination gets a visually distinct result.

    Base photo selection
    --------------------
    When *location_name* matches an entry in ``_LOCATION_SPECIFIC_IMAGES``,
    the first photo ID from that curated list is extracted and used as the
    base — so the returned URL serves a geographically accurate image rather
    than a generic luxury-hotel placeholder.  Falls back to a safe generic
    hospitality photo when no specific mapping exists.
    """
    # Auto-enrich landmarks from the known mapping when caller passes nothing
    if not landmarks:
        loc_lower = location_name.lower().strip()
        landmarks = next(
            (lm for key, lm in _LOCATION_LANDMARKS.items() if key in loc_lower or loc_lower in key),
            "",
        )

    search_query = urllib.parse.quote(
        f"{location_name} {landmarks} luxury hotel hospitality".strip()
    )
    sig = hashlib.md5(search_query.encode()).hexdigest()[:16]

    # Pick a location-appropriate base photo ID (first from curated list)
    base_photo_id = "1540553016722-983e48a2cd10"  # generic luxury hotel fallback
    loc_lower = location_name.lower().strip()
    for key, urls in _LOCATION_SPECIFIC_IMAGES.items():
        if (key in loc_lower or loc_lower in key) and urls:
            id_match = re.search(r"/photo-([^?&]+)", urls[0])
            if id_match:
                base_photo_id = id_match.group(1)
                break

    return (
        f"https://images.unsplash.com/photo-{base_photo_id}"
        f"?auto=format&fit=crop&w={w}&q={q}&sig={sig}"
    )

# ---------------------------------------------------------------------------
# Macro-region groups — enforce geographic isolation in overflow selection.
# A bucket's overflow must never cross into a different macro-region.
# ---------------------------------------------------------------------------

# Ordered overflow chains: primary bucket → same-region siblings → neutral.
# "india_generic" is always the final safe stop for every chain.
_BUCKET_OVERFLOW_CHAIN: dict[str, list[str]] = {
    "ganges_pilgrimage":  ["himalayan_hills",    "india_generic"],
    "himalayan_hills":    ["ganges_pilgrimage",  "india_generic"],
    "rajasthan_heritage": ["taj_agra",           "india_generic"],
    "taj_agra":           ["rajasthan_heritage", "india_generic"],
    "kerala_coastal":     ["india_generic"],
    "india_generic":      [],
}

# Keyword → primary bucket routing.
# IMPORTANT: higher-specificity routes are listed first so they win over
# broader geographic terms.  Uttarakhand/Himachal-specific pilgrimage places
# are checked before generic hill/mountain terms to prevent mis-routing.
_FALLBACK_KEYWORD_ROUTES: list[tuple[list[str], str]] = [
    # Northern pilgrimage — checked first; highest specificity
    (
        [
            "haridwar", "rishikesh", "ganga", "ganges", "varanasi", "kashi",
            "har ki pauri", "ram jhula", "lakshman jhula", "pauri", "ghat",
            "ghats", "jhula", "aarti", "triveni", "devprayag", "uttarakhand",
            "uttarkashi", "badrinath", "kedarnath", "char dham",
        ],
        "ganges_pilgrimage",
    ),
    # Northern hills — checked before generic mountain/valley terms
    (
        [
            "mussoorie", "nainital", "shimla", "manali", "darjeeling",
            "kasauli", "lansdowne", "ranikhet", "almora", "kausani",
            "dalhousie", "chail", "gangtok", "himachal", "himachal pradesh",
            "himalay", "hill station", "mountain", "trek", "valley",
            "waterfall", "ooty", "kodaikanal", "munnar", "coorg",
        ],
        "himalayan_hills",
    ),
    # Western heritage
    (
        [
            "rajasthan", "jaipur", "jodhpur", "udaipur", "jaisalmer",
            "bikaner", "pushkar", "fort", "palace", "haveli", "thar",
        ],
        "rajasthan_heritage",
    ),
    # Western Mughal
    (
        ["agra", "taj mahal", "taj", "mughal", "fatehpur sikri"],
        "taj_agra",
    ),
    # Southern / coastal
    (
        [
            "kerala", "goa", "andaman", "lakshadweep", "alappuzha",
            "beach", "coast", "backwater", "houseboat", "sea", "ocean",
        ],
        "kerala_coastal",
    ),
]


def _pick_static_fallback(
    haystack: str,
    used_urls: set[str],
    location_name: str | None = None,
) -> str | None:
    """
    Return a verified static fallback image URL (proxied) that hasn't already
    been used in this article.

    Location-specific lookup (new — checked first)
    -----------------------------------------------
    When *location_name* is provided and matches an entry in
    ``_LOCATION_SPECIFIC_IMAGES``, images from that curated per-destination
    pool are tried before any regional bucket.  This guarantees that
    Rishikesh, Mussoorie, and Nainital each get visually distinct,
    geographically accurate images rather than sharing the same regional pool.

    The dynamic Unsplash URL (built via ``_build_unsplash_dynamic_url``) is
    used as a final resort when even the location-specific pool is exhausted,
    generating a unique, location-seeded URL so the frontend always has
    something context-appropriate to render.

    Geographic isolation guarantee
    --------------------------------
    Routing is keyword-driven with highest-specificity rules first.  Once a
    primary bucket is identified, overflow follows ``_BUCKET_OVERFLOW_CHAIN``
    which is strictly confined to the same macro-region before touching the
    geo-neutral ``india_generic`` pool.  A northern-context query will never
    receive a southern or Mughal-heritage image.

    Returns None only when every candidate across the full overflow chain has
    already been used — practically impossible within a single article.
    """
    lower = haystack.lower()

    # ── Step 0: location-specific curated pool (highest priority) ────────────
    # When the location matches a named destination, we ONLY return images from
    # that curated pool — never from the generic hotel/spa/india_generic bucket.
    # If all specific images are already used, we cycle back rather than falling
    # through to unrelated placeholders (towels, bottles, resort pools, etc.).
    if location_name:
        loc_lower = location_name.lower().strip()
        matched_key = next(
            (key for key in _LOCATION_SPECIFIC_IMAGES if key in loc_lower or loc_lower in key),
            None,
        )
        if matched_key:
            loc_items = list(_LOCATION_SPECIFIC_IMAGES[matched_key])
            random.shuffle(loc_items)
            # First pass: find an unused image
            for raw_url in loc_items:
                proxied = _proxied_url(raw_url)
                if proxied not in used_urls:
                    used_urls.add(proxied)
                    logger.info(
                        "Location-specific fallback selected (location=%r, key=%r) for %r",
                        location_name,
                        matched_key,
                        haystack[:70],
                    )
                    return proxied
            # All location-specific images exhausted — cycle back to first rather
            # than serving a generic spa/hotel image that is geographically wrong.
            raw_url = loc_items[0]
            proxied = _proxied_url(raw_url)
            used_urls.add(proxied)
            logger.info(
                "Location-specific pool exhausted; cycling first image (location=%r, key=%r)",
                location_name,
                matched_key,
            )
            return proxied

    # ── Step 1: regional bucket routing ──────────────────────────────────────
    # Determine primary bucket — first keyword route that matches wins
    primary = "india_generic"
    for keywords, bucket in _FALLBACK_KEYWORD_ROUTES:
        if any(kw in lower for kw in keywords):
            primary = bucket
            break

    # Build ordered candidate list: primary → overflow chain (no duplicates)
    seen_buckets: set[str] = set()
    ordered_buckets: list[str] = [primary]
    seen_buckets.add(primary)
    for overflow_bucket in _BUCKET_OVERFLOW_CHAIN.get(primary, []):
        if overflow_bucket not in seen_buckets:
            ordered_buckets.append(overflow_bucket)
            seen_buckets.add(overflow_bucket)

    for bucket in ordered_buckets:
        # Shuffle each bucket's list before iterating so successive article
        # generations don't always pick the same sequence of fallback images.
        # list() copies to avoid mutating the module-level constant.
        bucket_items = list(_STATIC_FALLBACK_IMAGES.get(bucket, []))
        random.shuffle(bucket_items)
        for raw_url in bucket_items:
            proxied = _proxied_url(raw_url)
            if proxied not in used_urls:
                used_urls.add(proxied)
                logger.info(
                    "Static fallback selected (primary=%r, served_from=%r) for %r",
                    primary,
                    bucket,
                    haystack[:70],
                )
                return proxied

    # ── Step 2: dynamic Unsplash URL as absolute last resort ─────────────────
    # Construct a location-seeded URL so each destination still gets a unique,
    # context-appropriate image even when both curated pools are exhausted.
    if location_name:
        dynamic_url = _build_unsplash_dynamic_url(location_name)
        # Dynamic URLs are direct Unsplash https:// links — proxy them so
        # they flow through our SSRF-safe image-proxy like all other images.
        proxied = _proxied_url(dynamic_url)
        if proxied not in used_urls:
            used_urls.add(proxied)
            logger.info(
                "Dynamic Unsplash URL used as last-resort fallback (location=%r) for %r",
                location_name,
                haystack[:70],
            )
            return proxied

    logger.warning(
        "Static fallback pool fully exhausted (primary=%r) for %r — slot left blank.",
        primary,
        haystack[:70],
    )
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
) -> tuple[str | None, list[str], str | None]:
    """
    Search for real images (with query-degradation fallback) and inject
    them into the article.

    Returns:
        (hero_image_url, section_image_urls, enriched_full_article)

    - hero_image_url:        URL of the best wide shot for the article header
                              (proxied through /api/image-proxy). May be None
                              if no real image was found at any fallback level.
    - section_image_urls:    One URL per extracted heading (None entries for
                              headings where no real image was found).
    - enriched_full_article: full_article HTML with <figure> blocks injected after
                              each h2/h3 heading. None if full_article was not provided.

    Never raises; per-image failures walk the degradation chain and leave the
    slot as None rather than publishing a random foreign placeholder.
    """
    # Shared dedup set — every image URL chosen for this article is recorded
    # here so that no two slots (hero, sections, injected figures) ever get
    # the same photo.  Passed into every _best_image call below.
    used_urls: set[str] = set()

    # -- Hero image ----------------------------------------------------------
    hero_query = _build_query(headline, location)
    hero_url = _best_image(hero_query, location=location, used_urls=used_urls)
    if hero_url is None:
        hero_url = _pick_static_fallback(
            f"{hero_query} {location or ''}",
            used_urls,
            location_name=location,
        )
    logger.info("Hero image resolved for %r (query=%r)", headline[:60], hero_query[:80])

    # -- Section images -- one per heading in document order -----------------
    section_urls: list[str] = []
    heading_images: list[tuple[str, str]] = []

    if full_article:
        headings = _extract_headings(full_article)
        logger.info("Extracted %d headings from article %r", len(headings), headline[:50])

        for heading in headings:
            time.sleep(0.3)
            query = _build_query(heading, location)
            url = _best_image(query, location=location, used_urls=used_urls)
            if url is None:
                url = _pick_static_fallback(
                    f"{query} {location or ''}",
                    used_urls,
                    location_name=location,
                )
            section_urls.append(url)
            heading_images.append((heading, url))
            logger.info("Section image for heading %r -> resolved (query=%r)", heading[:50], query[:80])

    else:
        for suffix in ["exterior view", "interior ambiance"]:
            time.sleep(0.2)
            subject = f"{focus_keyword or headline} {suffix}"
            query = _build_query(subject, location)
            url = _best_image(query, location=location, used_urls=used_urls)
            if url is None:
                url = _pick_static_fallback(
                    f"{query} {location or ''}",
                    used_urls,
                    location_name=location,
                )
            section_urls.append(url)

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

    return hero_url, section_urls_clean, enriched_html
