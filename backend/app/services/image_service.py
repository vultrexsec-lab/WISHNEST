"""
Real image search for WishNest articles.

Uses the DuckDuckGo Images search API (free, no API key required) to find
relevant real photographs for each article section.

Strategy:
  1. Extract h2/h3 headings from the full_article HTML (in document order).
  2. For each heading build a targeted search query and fetch the top image.
  3. Inject a <figure> block immediately after each heading tag so readers see
     a contextual photo right where the subject is discussed.
  4. Also populate hero_image_url (wide search on the headline + location) and
     section_image_urls (list of fetched URLs) for backward-compatible rendering.

Never raises — any per-image failure silently skips that slot.
"""
import html
import logging
import re
import time
import urllib.parse

logger = logging.getLogger("wishnest.image_service")

# ---------------------------------------------------------------------------
# URL safety
# ---------------------------------------------------------------------------

_SAFE_URL_RE = re.compile(
    r"^https?://"            # must be http or https
    r"[a-zA-Z0-9._~:/?#\[\]@!$&'()*+,;=%\-]+"  # RFC-3986 allowed chars only
    r"$"
)


def _safe_image_url(url: str) -> str | None:
    """
    Return the URL unchanged if it is a safe http(s) image URL, else None.
    Rejects anything that could break out of an HTML attribute context.
    """
    if not url or not isinstance(url, str):
        return None
    url = url.strip()
    if not _SAFE_URL_RE.match(url):
        return None
    # Reject javascript: or data: embedded inside the path
    lower = url.lower()
    if "javascript:" in lower or "data:" in lower:
        return None
    return url


# ---------------------------------------------------------------------------
# DuckDuckGo image search (no API key required)
# ---------------------------------------------------------------------------

def _ddg_image_search(query: str, max_results: int = 5) -> list[str]:
    """
    Return a list of validated direct image URLs from DuckDuckGo Images.
    Returns an empty list on any failure.
    """
    try:
        from ddgs import DDGS
        results: list[str] = []
        with DDGS() as ddgs:
            for r in ddgs.images(
                query,
                region="wt-wt",
                safesearch="moderate",
                size="Large",
                type_image="photo",
                layout="Wide",
                max_results=max_results,
            ):
                raw_url = r.get("image") or r.get("url") or ""
                safe = _safe_image_url(raw_url)
                if safe:
                    results.append(safe)
                if len(results) >= max_results:
                    break
        logger.debug("DDG images for %r → %d results", query[:60], len(results))
        return results
    except Exception as exc:  # noqa: BLE001
        logger.warning("DDG image search failed for %r: %s", query[:60], exc)
        return []


def _best_image(query: str) -> str | None:
    """Return the single best validated image URL for *query*, or None."""
    urls = _ddg_image_search(query, max_results=5)
    return urls[0] if urls else None


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
    '<img src="{url}" alt="{alt}" '
    'style="max-width:100%;width:100%;height:auto;border-radius:8px;object-fit:cover;" '
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

    # Build an iterator over (heading_text, url) pairs; we consume one entry
    # per heading match in document order.
    img_iter = iter(heading_images)
    current: tuple[str, str] | None = next(img_iter, None)

    def _replace_heading(match: re.Match) -> str:
        nonlocal current, img_iter

        open_tag = match.group(1)
        inner = match.group(3)
        close_tag = match.group(4)
        full_match = match.group(0)

        heading_text = _strip_tags(inner)

        if current is None:
            return full_match                   # no more images left

        _expected_text, url = current
        current = next(img_iter, None)          # advance iterator for next call

        safe_url = _safe_image_url(url)
        if not safe_url:
            return full_match                   # skip unsafe URL

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
    Search for real images and inject them into the article.

    Returns:
        (hero_image_url, section_image_urls, enriched_full_article)

    - hero_image_url:        URL of the best wide shot for the article header.
    - section_image_urls:    One URL per extracted heading (for gallery widgets).
    - enriched_full_article: full_article HTML with <figure> blocks injected after
                             each h2/h3 heading.  None if full_article was not provided.

    Never raises; individual search failures silently skip that image slot.
    """
    # ── Build a base context string used in every query ──────────────────────
    context_parts: list[str] = []
    if location:
        context_parts.append(location)
    if focus_keyword:
        context_parts.append(focus_keyword)
    context = " ".join(context_parts)

    # ── Hero image ────────────────────────────────────────────────────────────
    hero_url: str | None = None
    try:
        hero_query = f"{headline} {context}".strip()
        hero_url = _best_image(hero_query)
        if hero_url:
            logger.info("Hero image found for %r", headline[:60])
        else:
            logger.warning("No hero image found for %r", headline[:60])
    except Exception as exc:  # noqa: BLE001
        logger.error("Hero image search failed for %r: %s", headline[:60], exc)

    # ── Section images — one per heading in document order ────────────────────
    section_urls: list[str] = []
    heading_images: list[tuple[str, str]] = []   # positional: [(heading_text, url)]

    if full_article:
        headings = _extract_headings(full_article)
        logger.info("Extracted %d headings from article %r", len(headings), headline[:50])

        for heading in headings:
            time.sleep(0.4)   # polite DDG rate-limit buffer
            try:
                query = f"{heading} {context}".strip()
                url = _best_image(query)
                if url:
                    section_urls.append(url)
                    heading_images.append((heading, url))
                    logger.info("Section image for heading %r → found", heading[:50])
                else:
                    # Still append a placeholder entry so the positional iterator
                    # stays in sync; None entries are skipped during injection.
                    heading_images.append((heading, ""))
                    logger.info("Section image for heading %r → not found", heading[:50])
            except Exception as exc:  # noqa: BLE001
                heading_images.append((heading, ""))
                logger.warning("Section image failed for heading %r: %s", heading[:50], exc)

    else:
        # Fallback: generate 2 generic section images when no HTML is provided
        for i, suffix in enumerate(["exterior view", "interior ambiance"]):
            time.sleep(0.3)
            try:
                query = f"{focus_keyword or headline} {suffix} {context}".strip()
                url = _best_image(query)
                if url:
                    section_urls.append(url)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Fallback section image %d failed: %s", i, exc)

    # ── Inject images into article HTML ───────────────────────────────────────
    # Pass ALL heading entries (including empty-URL ones) to preserve 1:1
    # positional alignment. The injector skips insertion when the URL is empty.
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
