"""
Hard gates before an article may go public (approve / schedule / publish).

Step 2 quality rules:
  - Hospitality (or explicit reimagined) only — no monuments, realty, pure beaches/POIs as reviews
  - Location normalized to City, State (or clear place label) — no plus-codes / Khasra as display location
  - Hero image must resolve to a real image over HTTP
"""
from __future__ import annotations

import logging
import re
import urllib.parse
from typing import Any

import requests

from app.services.places_service import is_hospitality_listing, is_non_hospitality_title

logger = logging.getLogger("wishnest.publishing_gates")

_BLOCKED_TITLE = re.compile(
    r"\b("
    r"taj mahal|india gate|red fort|qutub minar|mysuru palace|mysore palace|"
    r"ellora caves|ajanta caves|national park|mattupetty dam|"
    r"sotheby|realty|private limited|pvt\.?\s*ltd|"
    r"a places in|paying guest|\bpg stay\b"
    r")\b",
    re.I,
)

_MESSY_LOC = re.compile(
    r"([A-Z0-9]{4,}\+[A-Z0-9]{2,})|"
    r"khasra\s*no|"
    r"plot\s*no\.?\s*\d|"
    r"site\s*no|"
    r"sy\.?\s*no|"
    r"HRX\d\+",
    re.I,
)

_STATE_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"rajasthan|jaipur|udaipur|jodhpur|jaisalmer|ajmer|amer\b", re.I), "Rajasthan"),
    (re.compile(r"kerala|kochi|cochin|munnar|alleppey|alappuzha|wayanad|kuttanad|fort kochi", re.I), "Kerala"),
    (re.compile(r"\bgoa\b|calangute|candolim|anjuna|assagao|benaulim|candolim", re.I), "Goa"),
    (re.compile(r"himachal|manali|shimla|palampur|dalhousie|dharamshala", re.I), "Himachal Pradesh"),
    (re.compile(r"uttarakhand|dehradun|mussoorie|nainital|rishikesh|haridwar|mukteshwar", re.I), "Uttarakhand"),
    (re.compile(r"karnataka|coorg|kodagu|madikeri|bengaluru|bangalore|mysore", re.I), "Karnataka"),
    (re.compile(r"maharashtra|mumbai|pune|lonavala", re.I), "Maharashtra"),
    (re.compile(r"madhya pradesh|maheshwar", re.I), "Madhya Pradesh"),
    (re.compile(r"tamil nadu|mahabalipuram|chennai", re.I), "Tamil Nadu"),
    (re.compile(r"delhi|new delhi", re.I), "Delhi"),
    (re.compile(r"meghalaya|shillong", re.I), "Meghalaya"),
    (re.compile(r"sikkim|gangtok", re.I), "Sikkim"),
]

_CITY_HINTS = [
    (re.compile(r"\bjaipur\b", re.I), "Jaipur"),
    (re.compile(r"\budaipur\b", re.I), "Udaipur"),
    (re.compile(r"\bjodhpur\b", re.I), "Jodhpur"),
    (re.compile(r"\bkochi\b|\bfort kochi\b|\bcochin\b", re.I), "Fort Kochi"),
    (re.compile(r"\bmunnar\b", re.I), "Munnar"),
    (re.compile(r"\blonavala\b", re.I), "Lonavala"),
    (re.compile(r"\bmadikeri\b|\bcoorg\b", re.I), "Coorg"),
    (re.compile(r"\bbenaulim\b", re.I), "Benaulim"),
    (re.compile(r"\bmahabalipuram\b|\btemple bay\b", re.I), "Mahabalipuram"),
    (re.compile(r"\bnainital\b", re.I), "Nainital"),
    (re.compile(r"\bdehradun\b", re.I), "Dehradun"),
    (re.compile(r"\bcalangute\b", re.I), "Calangute"),
    (re.compile(r"\bkuttanad\b", re.I), "Kuttanad"),
    (re.compile(r"\bgoa\b", re.I), "Goa"),
]


def normalize_location(raw: str | None, headline: str | None = None) -> str | None:
    """Return a short City, State (or place) label suitable for public cards."""
    text = " ".join(x for x in [(raw or "").strip(), (headline or "").strip()] if x)
    if not text:
        return None

    state = None
    for pat, label in _STATE_RULES:
        if pat.search(text):
            state = label
            break

    city = None
    for pat, label in _CITY_HINTS:
        if pat.search(text):
            city = label
            break

    if city and state:
        if city == "Goa" and state == "Goa":
            return "Goa"
        if city in state:  # e.g. unlikely
            return city
        return f"{city}, {state}"
    if city:
        return city
    if state:
        return state

    # Strip messy tokens from raw location
    if raw and not _MESSY_LOC.search(raw):
        parts = [p.strip() for p in raw.split(",") if p.strip()]
        clean = []
        for part in reversed(parts):
            if re.search(r"\d", part) and not re.search(r"^[A-Za-z\s]+$", part):
                continue
            if len(part) < 2 or len(part) > 40:
                continue
            if re.search(r"near |opp\.|behind |lane |road$|marg$", part, re.I) and len(parts) > 2:
                continue
            clean.append(part)
            if len(clean) >= 2:
                break
        if clean:
            return ", ".join(reversed(clean))
    return None


def title_looks_like_stay(headline: str | None, category: str | None = None) -> bool:
    h = (headline or "").strip()
    if not h:
        return False
    cat = (category or "").lower()
    if cat in ("reimagined", "reimaging", "destinations"):
        return True
    if _BLOCKED_TITLE.search(h):
        return False
    if is_non_hospitality_title(h):
        return False
    # Reuse places helper on the title alone
    if is_hospitality_listing(h, None, None, None):
        return True
    # Soft allow if category is reviews/best-of and not blocked
    if cat in ("reviews", "review", "best-of", "best_of"):
        if re.search(r"hotel|resort|villa|lodge|inn|retreat|homestay|bungalow|palace|spa|suites", h, re.I):
            return True
    return False


def hero_image_is_reachable(hero_url: str | None, *, timeout: float = 12.0) -> bool:
    if not hero_url or not str(hero_url).strip():
        return False
    url = str(hero_url).strip()
    # Relative proxy path — resolve against public backend is caller's job;
    # here we decode and hit upstream OR accept /api/image-proxy only after HEAD/GET via full URL.
    if url.startswith("/api/image-proxy"):
        # Decode upstream for direct check (avoids depending on self HTTP)
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        upstream = (qs.get("url") or [None])[0]
        if not upstream:
            return False
        url = upstream
    try:
        resp = requests.get(
            url,
            timeout=timeout,
            stream=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "image/*,*/*;q=0.8",
                "Referer": "https://www.google.com/",
            },
        )
        if resp.status_code != 200:
            return False
        ctype = (resp.headers.get("Content-Type") or "").lower()
        if ctype and not ctype.startswith("image/"):
            return False
        # read a small chunk to ensure body exists
        chunk = next(resp.iter_content(4096), b"")
        return len(chunk) > 500
    except Exception as exc:  # noqa: BLE001
        logger.info("Hero reachability failed for %s: %s", url[:80], exc)
        return False


def validate_for_public(article: Any) -> list[str]:
    """Return list of blocking reasons; empty means OK to approve."""
    reasons: list[str] = []
    headline = getattr(article, "headline", None) or ""
    location = getattr(article, "location", None) or ""
    hero = getattr(article, "hero_image_url", None)
    category = getattr(article, "category", None) or ""
    article_type = getattr(article, "article_type", None) or ""

    if getattr(article, "is_trash", False):
        reasons.append("Article is in trash.")

    if not title_looks_like_stay(headline, category or article_type):
        reasons.append(
            "Headline does not look like a hospitality stay (hotel/resort/villa/etc.). "
            "Monuments, pure POIs and realty cannot be approved as reviews."
        )

    if is_non_hospitality_title(headline):
        reasons.append("Title matches a non-hospitality commercial entity.")

    if not (location or "").strip():
        reasons.append("Location is required (use City, State — e.g. Jaipur, Rajasthan).")
    elif _MESSY_LOC.search(location):
        reasons.append(
            "Location looks like a plus-code / survey plot. Normalize to City, State before approve."
        )

    if not hero_image_is_reachable(hero):
        reasons.append(
            "Hero image is missing or not reachable. Attach a working photo before approve."
        )

    return reasons


def apply_location_normalize(article: Any) -> str | None:
    """Mutate article.location to normalized form when possible; return new value."""
    new_loc = normalize_location(getattr(article, "location", None), getattr(article, "headline", None))
    if new_loc:
        article.location = new_loc
    return new_loc
