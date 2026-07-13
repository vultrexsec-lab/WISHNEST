"""
Orchestrates the full WishNest AI Research Editor Agent pipeline:

  1. Firecrawl search/scrape for the brief -> source material + source_urls
  2. OpenAI drafting -> one or more complete article packages
  3. Validate each package against ArticleCreate, attach source_urls
  4. Persist each as an Article row with status='draft' (WITHOUT images first)
  5. Generate Pollinations.ai image URLs and patch the saved rows (non-blocking)

Saving before image generation means articles always appear in the dashboard
even if image URL building fails. Images are patched in a second UPDATE pass.

Returns the created Article rows so the router can build the response.
"""
import logging

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.models.article import Article, ArticleStatus
from app.schemas.article import ArticleCreate
from app.services.firecrawl_service import FirecrawlError, search_and_scrape
from app.services.image_service import generate_article_images
from app.services.openai_service import generate_article_packages

logger = logging.getLogger("wishnest.research_pipeline")

# ── SEO field coercion ────────────────────────────────────────────────────────
_SEO_TITLE_MIN, _SEO_TITLE_MAX = 50, 60
_META_DESC_MIN, _META_DESC_MAX = 150, 160


def _coerce_seo_fields(raw: dict) -> None:
    """
    Mutate *raw* in-place: auto-fix seo_title and meta_description so they
    satisfy Pydantic length constraints — rather than discarding valid articles
    because of a few-character SEO overshoot after retries.
    """
    title: str = raw.get("seo_title") or ""
    if title:
        # Trim overly long titles at the last space before the limit
        if len(title) > _SEO_TITLE_MAX:
            cut = title[:_SEO_TITLE_MAX].rsplit(" ", 1)[0]
            # If we ended up shorter than min, just hard-cut at max
            title = cut if len(cut) >= _SEO_TITLE_MIN else title[:_SEO_TITLE_MAX]
        # Pad too-short titles by appending "| WishNest"
        if len(title) < _SEO_TITLE_MIN:
            suffix = " | WishNest"
            title = (title + suffix)[: _SEO_TITLE_MAX]
            if len(title) < _SEO_TITLE_MIN:
                title = title.ljust(_SEO_TITLE_MIN)
        raw["seo_title"] = title

    desc: str = raw.get("meta_description") or ""
    if desc:
        if len(desc) > _META_DESC_MAX:
            # Trim at a word boundary, leaving room for a CTA arrow
            trimmed = desc[: _META_DESC_MAX - 2].rsplit(" ", 1)[0]
            desc = (trimmed + " →")[: _META_DESC_MAX]
        if len(desc) < _META_DESC_MIN:
            # Append a filler CTA to reach minimum length
            fillers = [
                " Discover more on WishNest →",
                " Read the full guide on WishNest →",
                " Explore now on WishNest →",
            ]
            for filler in fillers:
                candidate = desc.rstrip("→").rstrip() + filler
                if _META_DESC_MIN <= len(candidate) <= _META_DESC_MAX:
                    desc = candidate
                    break
            else:
                # Last resort: pad/truncate to exact range
                desc = desc.ljust(_META_DESC_MIN)[: _META_DESC_MAX]
        raw["meta_description"] = desc


# OpenAI sometimes returns grade values using Python enum-name style
# (e.g. "a_plus", "b_minus") or plain lowercase ("a", "b+").
# Normalise all variants to the canonical WishNest grade strings.
_GRADE_FIELDS = [
    "architecture_grade", "landscape_grade", "connectivity_grade",
    "delight_grade", "eat_explore_grade",
]
_GRADE_NAME_TO_VALUE: dict[str, str] = {
    "a_plus": "A+", "a": "A", "a_minus": "A-",
    "b_plus": "B+", "b": "B", "b_minus": "B-",
    "c_plus": "C+", "c": "C", "c_minus": "C-",
    "d_plus": "D+", "d": "D",
}

# Numeric ABCDE score fields (float 1.0–10.0) plus their paired grade field.
_SCORE_FIELDS = [
    "architecture_score", "landscape_score", "connectivity_score",
    "delight_score", "eat_explore_score",
]
_SCORE_TO_GRADE: dict[str, str] = {
    "architecture_score": "architecture_grade",
    "landscape_score":    "landscape_grade",
    "connectivity_score": "connectivity_grade",
    "delight_score":      "delight_grade",
    "eat_explore_score":  "eat_explore_grade",
}


def _score_to_grade(score: float) -> str:
    """Convert a 1.0–10.0 numeric score to a WishNest letter grade."""
    if score >= 9.0:  return "A+"
    if score >= 8.0:  return "A"
    if score >= 7.5:  return "A-"
    if score >= 7.0:  return "B+"
    if score >= 6.0:  return "B"
    if score >= 5.5:  return "B-"
    if score >= 5.0:  return "C+"
    if score >= 4.0:  return "C"
    if score >= 3.5:  return "C-"
    if score >= 3.0:  return "D+"
    return "D"


def _normalise_scores(raw: dict) -> None:
    """
    Mutate *raw* in-place:
    1. Clamp any numeric score to [1.0, 10.0].
    2. Derive the paired letter grade from the score (overrides whatever the
       LLM independently returned for that grade field, keeping both in sync).
    3. Compute abcde_overall from the average of all present scores.
    """
    clean_scores: list[float] = []
    for field in _SCORE_FIELDS:
        val = raw.get(field)
        if val is None:
            continue
        try:
            clamped = max(1.0, min(10.0, float(val)))
        except (TypeError, ValueError):
            raw[field] = None
            continue
        raw[field] = round(clamped, 1)
        clean_scores.append(clamped)
        # Derive letter grade from score
        raw[_SCORE_TO_GRADE[field]] = _score_to_grade(clamped)

    # Compute overall grade from average of all numeric scores
    if clean_scores:
        avg = sum(clean_scores) / len(clean_scores)
        raw["abcde_overall"] = _score_to_grade(avg)


def _normalise_grades(raw: dict) -> None:
    """Mutate *raw* in-place: convert any grade field to its canonical value."""
    for field in _GRADE_FIELDS:
        val = raw.get(field)
        if not isinstance(val, str):
            continue
        key = val.lower().replace("+", "_plus").replace("-", "_minus").strip()
        if key in _GRADE_NAME_TO_VALUE:
            raw[field] = _GRADE_NAME_TO_VALUE[key]
        else:
            raw[field] = val.upper()


def _apply_live_ratings(article: Article, property_matches: list[dict]) -> bool:
    """
    Blend genuine Google Maps ratings for the live properties featured in
    this article into the WishNest ABCDE scorecard, so the published grades
    reflect real user consensus rather than a purely LLM-estimated score.

    property_matches: [{"name", "rating", "review_count", "maps_url"}, ...]
    as returned by `generate_article_images`. Ratings are on Google's native
    1.0-5.0 scale; WishNest scores are 1.0-10.0, so we scale by 2x.

    Blend, not override: each dimension score keeps 40% of the LLM's original
    editorial judgement and takes 60% from the live rating, so a strong photo
    gallery of well-reviewed properties visibly lifts the grade without
    completely discarding the qualitative analysis. Also writes the raw
    Google metrics into `property_snapshot` for transparency.

    Returns True if the article's scores/snapshot were modified.
    """
    ratings = [m["rating"] for m in property_matches if m.get("rating")]
    if not ratings:
        return False

    avg_google_rating = sum(ratings) / len(ratings)  # 1.0-5.0
    live_score = avg_google_rating * 2.0             # scale to 1.0-10.0

    changed = False
    for field, grade_field in _SCORE_TO_GRADE.items():
        existing = getattr(article, field)
        if existing is not None:
            blended = existing * 0.4 + live_score * 0.6
        else:
            blended = live_score
        blended = round(max(1.0, min(10.0, blended)), 1)
        if blended != existing:
            setattr(article, field, blended)
            setattr(article, grade_field, _score_to_grade(blended))
            changed = True

    if changed:
        new_scores = [getattr(article, f) for f in _SCORE_TO_GRADE if getattr(article, f) is not None]
        if new_scores:
            article.abcde_overall = _score_to_grade(sum(new_scores) / len(new_scores))

    snapshot = dict(article.property_snapshot or {})
    snapshot["google_live_rating"] = round(avg_google_rating, 1)
    snapshot["google_live_review_count"] = sum(m.get("review_count") or 0 for m in property_matches) or None
    snapshot["google_live_sources"] = [
        {"name": m.get("name"), "rating": m.get("rating"), "maps_url": m.get("maps_url")}
        for m in property_matches
        if m.get("name")
    ]
    article.property_snapshot = snapshot
    changed = True

    logger.info(
        "Applied live Google ratings to %r: avg %.1f★ across %d propert%s -> abcde_overall=%s",
        article.headline[:50], avg_google_rating, len(ratings),
        "y" if len(ratings) == 1 else "ies", article.abcde_overall,
    )
    return changed


class ResearchPipelineError(RuntimeError):
    pass


def run_research_pipeline(brief: str, db: Session, category: str | None = None) -> list[Article]:
    # ── 1. Research sources via Firecrawl ────────────────────────────────────
    try:
        sources = search_and_scrape(brief)
    except FirecrawlError as exc:
        logger.warning("Firecrawl step failed, continuing without sources: %s", exc)
        sources = []

    source_urls = [s["url"] for s in sources]

    # ── 2. Draft article packages via OpenAI ─────────────────────────────────
    try:
        raw_packages = generate_article_packages(brief, sources)
    except Exception as exc:  # noqa: BLE001
        raise ResearchPipelineError(f"Article drafting failed: {exc}") from exc

    # ── 3. Validate + persist each package WITHOUT images first ───────────────
    # Saving before image generation guarantees articles appear in the dashboard
    # even if DALL-E is slow or fails. Images are patched in step 4.
    created: list[Article] = []
    for raw in raw_packages:
        raw.setdefault("source_urls", source_urls)
        if not raw.get("source_urls"):
            raw["source_urls"] = source_urls

        _normalise_scores(raw)   # clamp floats, derive letter grades + overall
        _normalise_grades(raw)   # catch any remaining letter-grade format quirks
        _coerce_seo_fields(raw)  # auto-fix minor SEO length violations

        try:
            validated = ArticleCreate(**raw)
        except ValidationError as exc:
            logger.warning("Skipping invalid article package from OpenAI: %s", exc)
            continue

        # Save immediately WITHOUT images (hero_image_url=None, section_image_urls=None)
        article = Article(
            **validated.model_dump(
                exclude={"faq_section", "internal_links", "hero_image_url", "section_image_urls", "category"}
            ),
            faq_section=[item.model_dump() for item in (validated.faq_section or [])] or None,
            internal_links=[link.model_dump() for link in (validated.internal_links or [])] or None,
            status=ArticleStatus.draft,
            hero_image_url=None,
            section_image_urls=None,
            category=category,  # use caller-supplied category, not AI-inferred
        )

        try:
            db.add(article)
            db.commit()
            db.refresh(article)
            created.append(article)
            logger.info("Saved article (no images yet): %r", article.headline[:60])
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to save article %r: %s", validated.headline[:60], exc)
            db.rollback()

    if not created:
        raise ResearchPipelineError(
            "OpenAI did not return any article package that matched the required schema."
        )

    # ── 4. Fetch real images from DuckDuckGo and patch saved rows ────────────
    # Runs after all articles are committed, so a failure never blocks an
    # article from appearing. Each patch is committed individually.
    # generate_article_images now returns a 3-tuple:
    #   (hero_url, section_urls, enriched_full_article)
    # where enriched_full_article has <figure> blocks injected after each heading.
    for article in created:
        try:
            hero_url, section_urls, enriched_html, property_matches = generate_article_images(
                headline=article.headline,
                focus_keyword=article.focus_keyword,
                location=article.location,
                article_type=article.article_type.value,
                full_article=article.full_article,
            )
            html_changed = bool(enriched_html and enriched_html != article.full_article)
            ratings_changed = _apply_live_ratings(article, property_matches)
            patched_any = bool(hero_url or section_urls or html_changed or ratings_changed)
            if hero_url or section_urls:
                article.hero_image_url = hero_url
                article.section_image_urls = section_urls or None
            if html_changed:
                article.full_article = enriched_html
            if patched_any:
                db.add(article)
                db.commit()
                db.refresh(article)
                logger.info(
                    "Patched images for %r — hero: %s, sections: %d, html_enriched: %s",
                    article.headline[:50],
                    "yes" if hero_url else "no",
                    len(section_urls),
                    "yes" if html_changed else "no",
                )
            else:
                logger.info("No images found for %r — article saved without images.", article.headline[:50])
        except Exception as exc:  # noqa: BLE001
            logger.warning("Image patch failed for %r: %s", article.headline[:50], exc)
            try:
                db.rollback()
            except Exception:
                pass

    return created
