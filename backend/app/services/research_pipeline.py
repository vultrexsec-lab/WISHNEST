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
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.article import Article, ArticleStatus, ArticleType
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

# Reverse map: canonical letter grade → approximate numeric midpoint score.
# Used by _ensure_abcde_overall to derive an overall grade when only letter
# grades (not numeric scores) were returned by the LLM.
_GRADE_TO_SCORE: dict[str, float] = {
    "A+": 9.5, "A": 8.5, "A-": 7.75,
    "B+": 7.25, "B": 6.5, "B-": 5.75,
    "C+": 5.25, "C": 4.5, "C-": 3.75,
    "D+": 3.25, "D": 2.0,
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


def _ensure_abcde_overall(raw: dict) -> None:
    """
    Guarantee ``abcde_overall`` is always a non-blank string after normalisation.

    ``_normalise_scores()`` derives it from numeric score fields, but when the
    LLM returns only letter grades (no numeric scores) — which happens routinely
    for landmark / destination articles — ``clean_scores`` stays empty and the
    field is never written.  This function is the final backstop:

    1. Already set → nothing to do.
    2. Individual letter grades present → convert each to its numeric midpoint
       (via ``_GRADE_TO_SCORE``), average them, and map back to a letter.
    3. No grade fields at all → default to ``"B"`` (neutral; never blank).
    """
    if raw.get("abcde_overall"):
        return  # already written by _normalise_scores

    present_scores: list[float] = []
    for grade_field in _GRADE_FIELDS:
        g = raw.get(grade_field)
        if g and isinstance(g, str):
            score = _GRADE_TO_SCORE.get(g.upper().strip())
            if score is not None:
                present_scores.append(score)

    if present_scores:
        avg = sum(present_scores) / len(present_scores)
        raw["abcde_overall"] = _score_to_grade(avg)
        logger.info(
            "abcde_overall derived from %d letter grade(s) (avg midpoint %.2f → %s)",
            len(present_scores), avg, raw["abcde_overall"],
        )
    else:
        raw["abcde_overall"] = "B"
        logger.warning(
            "abcde_overall missing and no ABCDE grade fields found — defaulting to 'B'."
        )


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


def regenerate_article_images(article: Article, db: Session) -> bool:
    """
    Re-run the image pipeline for an ALREADY-SAVED article (as opposed to the
    creation-time pass in `run_research_pipeline`). Used by the admin
    "regenerate images" action so a review article that was originally
    published with a thin/duplicated photo set (e.g. because no live
    provider was configured yet) can be refreshed once real data is
    available, without re-running the (expensive, non-idempotent) research +
    drafting steps.

    Returns True if the article row was changed and committed.
    """
    hero_url, section_urls, enriched_html, property_matches = generate_article_images(
        headline=article.headline,
        focus_keyword=article.focus_keyword,
        location=article.location,
        article_type=article.article_type.value,
        full_article=article.full_article,
        category=article.category,
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
            "Regenerated images for %r — hero: %s, sections: %d, html_enriched: %s",
            article.headline[:50],
            "yes" if hero_url else "no",
            len(section_urls),
            "yes" if html_changed else "no",
        )
    else:
        logger.info("Image regeneration found nothing new for %r.", article.headline[:50])
    return patched_any


def run_research_pipeline(
    brief: str,
    db: Session,
    category: str | None = None,
    place_id: str | None = None,
    article_count: int = 1,
) -> list[Article]:
    # ── 0. Pre-flight duplicate guard ────────────────────────────────────────
    # If a place_id is known, check the DB before spending money on Firecrawl
    # and OpenAI. This is the second layer of duplicate prevention (the first
    # is the in-flight process mutex in research.py; the third is the DB-level
    # partial unique index uq_articles_place_id_active).
    if place_id:
        existing = (
            db.query(Article)
            .filter(Article.place_id == place_id, Article.is_trash.is_(False))
            .first()
        )
        if existing:
            logger.info(
                "Duplicate skipped — article for place_id=%r already exists "
                "(id=%s, headline=%r).",
                place_id, existing.id, (existing.headline or "")[:60],
            )
            return [existing]

    # ── 1. Research sources via Firecrawl ────────────────────────────────────
    try:
        sources = search_and_scrape(brief)
    except FirecrawlError as exc:
        logger.warning("Firecrawl step failed, continuing without sources: %s", exc)
        sources = []

    source_urls = [s["url"] for s in sources]

    # ── 2. Draft article packages via OpenAI ─────────────────────────────────
    try:
        raw_packages = generate_article_packages(brief, sources, count=article_count)
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

        _normalise_scores(raw)      # clamp floats, derive letter grades + overall
        _normalise_grades(raw)      # catch any remaining letter-grade format quirks
        _ensure_abcde_overall(raw)  # guarantee abcde_overall is always a non-blank string
        _coerce_seo_fields(raw)     # auto-fix minor SEO length violations

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

        # Destinations must always be article_type=review — they require full
        # ABCDE grading and a Premium schema. Override whatever the LLM returned
        # so a mis-labelled brief never produces a STANDARD badge on a destination
        # article.  (Also guarded upstream in build_property_brief, but this is
        # the authoritative server-side enforcement.)
        if category == "destinations" and article.article_type != ArticleType.review:
            logger.info(
                "Forced article_type=review for destinations article %r (was %r)",
                (article.headline or "")[:60], article.article_type,
            )
            article.article_type = ArticleType.review

        # Final pre-save grade safety net: _ensure_abcde_overall() already ran
        # on `raw`, but Pydantic's model_dump + re-construction can silently
        # drop a field if the schema marks it Optional. Verify directly on the
        # ORM object and patch if needed so the DB never stores a blank grade.
        if not article.abcde_overall:
            # Derive from individual grade fields already on the ORM object
            _grade_scores = [
                _GRADE_TO_SCORE[g]
                for f in _GRADE_FIELDS
                if (g := (getattr(article, f) or "").upper().strip()) in _GRADE_TO_SCORE
            ]
            article.abcde_overall = (
                _score_to_grade(sum(_grade_scores) / len(_grade_scores))
                if _grade_scores else "B"
            )
            logger.warning(
                "Pre-save grade patch applied for %r: abcde_overall set to %r",
                (article.headline or "")[:60], article.abcde_overall,
            )

        try:
            db.add(article)
            db.commit()
            db.refresh(article)
            created.append(article)
            logger.info("Saved article (no images yet): %r", article.headline[:60])
        except IntegrityError as exc:
            # Hit the DB-level partial unique index uq_articles_place_id_active —
            # another concurrent INSERT already committed for this place_id.
            # Roll back and skip rather than creating a duplicate row.
            db.rollback()
            logger.warning(
                "Duplicate insert blocked by DB constraint for place_id=%r "
                "(headline=%r): %s",
                place_id, validated.headline[:60], exc.orig,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to save article %r: %s", validated.headline[:60], exc)
            db.rollback()

    if not created:
        raise ResearchPipelineError(
            "OpenAI did not return any article package that matched the required schema."
        )

    # ── 3b. Record the live property's place_id for de-duplication ───────────
    # When this pipeline run was triggered by live discovery (scheduler or the
    # broad-search resolver), the caller supplies the Google Places place_id /
    # SerpApi data_id that uniquely identifies the property. Writing it here
    # ensures the next scheduler run excludes this property from discovery.
    if place_id:
        try:
            for article in created:
                article.place_id = place_id
            db.commit()
            logger.info(
                "Recorded place_id=%r on %d article(s) for de-duplication.",
                place_id, len(created),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to record place_id=%r on articles: %s", place_id, exc)
            try:
                db.rollback()
            except Exception:
                pass

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
                category=article.category,
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
