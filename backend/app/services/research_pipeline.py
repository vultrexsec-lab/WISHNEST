"""
Orchestrates the full WishNest AI Research Editor Agent pipeline:

  1. Firecrawl search/scrape for the brief -> source material + source_urls
  2. OpenAI drafting -> one or more complete article packages
  3. Validate each package against ArticleCreate, attach source_urls
  4. Persist each as an Article row with status='draft' (WITHOUT images first)
  5. Generate DALL-E 3 images and patch the saved rows (non-blocking)

Saving before image generation means articles always appear in the dashboard
even if DALL-E fails or is slow. Images are patched in a second UPDATE pass.

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

        _normalise_grades(raw)

        try:
            validated = ArticleCreate(**raw)
        except ValidationError as exc:
            seo_errors = [
                f"{e['loc'][-1]}: {e['msg']}"
                for e in exc.errors()
                if e.get("loc") and e["loc"][-1] in ("seo_title", "meta_description")
            ]
            if seo_errors:
                logger.warning(
                    "Skipping article — SEO hard constraints still violated after retries: %s",
                    "; ".join(seo_errors),
                )
            else:
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

    # ── 4. Generate DALL-E 3 images and patch saved rows ─────────────────────
    # Runs after all articles are committed, so a slow/failing image never
    # blocks an article from appearing. Each patch is committed individually.
    for article in created:
        try:
            hero_url, section_urls = generate_article_images(
                headline=article.headline,
                focus_keyword=article.focus_keyword,
                location=article.location,
                article_type=article.article_type.value,
            )
            if hero_url or section_urls:
                article.hero_image_url = hero_url
                article.section_image_urls = section_urls or None
                db.add(article)
                db.commit()
                db.refresh(article)
                logger.info(
                    "Patched images for %r — hero: %s, sections: %d",
                    article.headline[:50],
                    "yes" if hero_url else "no",
                    len(section_urls),
                )
            else:
                logger.info("No images generated for %r — article saved without images.", article.headline[:50])
        except Exception as exc:  # noqa: BLE001
            logger.warning("Image patch failed for %r: %s", article.headline[:50], exc)
            try:
                db.rollback()
            except Exception:
                pass

    return created
