"""
Real image search for WishNest articles.

Multi-provider fallback chain so an article NEVER publishes without images:

  1. DuckDuckGo Images (free, no API key) — primary source.
  2. Pexels API (free, requires PEXELS_API_KEY) — used when DDG returns nothing
     or errors (rate limit, network blip, library issue).
  3. Unsplash API (free, requires UNSPLASH_ACCESS_KEY) — used when both of the
     above fail.
  4. Picsum (https://picsum.photos, no key, deterministic per-query seed) —
     absolute last resort so a slot is never left empty.

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

Never raises — any per-image failure silently falls through to the next
provider, and the final provider (Picsum) never fails.
"""
import hashlib
import html
import logging
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

def _build_query(subject: str, location: str | None) -> str:
    """
    Build a search query that heavily weights the exact landmark/location
    string instead of letting generic subject words (e.g. "luxury stay")
    dominate and pull back unrelated stock photography.

    Wraps the subject and location as quoted phrases (which DuckDuckGo,
    Pexels, and Unsplash all treat as literal phrase hints) and appends
    "India" whenever a location is present and India isn't already implied,
    since most WishNest destinations are Indian spiritual/cultural sites and
    unqualified queries (e.g. "Ram Jhula") otherwise skew toward generic or
    western results.
    """
    subject = (subject or "").strip()
    if not subject:
        return location or ""

    parts = [f'"{subject}"']
    if location:
        loc = location.strip()
        if loc and loc.lower() not in subject.lower():
            parts.append(f'"{loc}"')
        if "india" not in subject.lower() and "india" not in loc.lower():
            parts.append("India")
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
# Provider 4: Picsum — deterministic, keyless, never fails. Absolute last resort.
# ---------------------------------------------------------------------------

def _picsum_fallback_url(query: str) -> str:
    """
    A deterministic (same query -> same image) placeholder photo. Not
    contextually relevant, but guarantees a slot is never left blank.
    """
    seed = hashlib.sha1(query.encode("utf-8")).hexdigest()[:16]
    return f"https://picsum.photos/seed/{seed}/1200/800"


# ---------------------------------------------------------------------------
# Fallback chain
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


def _best_image(query: str, guarantee: bool = True) -> str | None:
    """
    Return the single best validated (and proxied) image URL for *query*.
    If `guarantee` is True (default), always returns a URL — falling back to
    a deterministic Picsum placeholder when every real provider fails.
    """
    urls = _search_all_providers(query, max_results=5)
    if urls:
        return _proxied_url(urls[0])
    if guarantee:
        logger.warning("All image providers failed for %r — using Picsum fallback.", query[:60])
        return _proxied_url(_picsum_fallback_url(query))
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
    Search for real images (with automatic provider fallback) and inject
    them into the article. Guarantees every slot gets a real, working image
    URL — no article should ever publish completely blank.

    Returns:
        (hero_image_url, section_image_urls, enriched_full_article)

    - hero_image_url:        URL of the best wide shot for the article header
                              (proxied through /api/image-proxy).
    - section_image_urls:    One URL per extracted heading (for gallery widgets).
    - enriched_full_article: full_article HTML with <figure> blocks injected after
                              each h2/h3 heading. None if full_article was not provided.

    Never raises; individual provider failures fall through the chain and,
    as a last resort, a deterministic placeholder image is used so the slot
    is never left empty.
    """
    # -- Hero image (always guaranteed) --------------------------------------
    hero_query = _build_query(headline, location)
    hero_url = _best_image(hero_query, guarantee=True)
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
            url = _best_image(query, guarantee=True)
            section_urls.append(url)
            heading_images.append((heading, url))
            logger.info("Section image for heading %r -> resolved (query=%r)", heading[:50], query[:80])

    else:
        for suffix in ["exterior view", "interior ambiance"]:
            time.sleep(0.2)
            subject = f"{focus_keyword or headline} {suffix}"
            query = _build_query(subject, location)
            url = _best_image(query, guarantee=True)
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

    return hero_url, section_urls, enriched_html
