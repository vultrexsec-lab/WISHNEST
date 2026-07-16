"""
POST /api/research

Accepts a plain-text research brief and immediately returns 202 Accepted,
then runs the full pipeline in a background thread so the HTTP request
never times out:

  1. [NEW] Broad-query resolver: the query is first sent to Google Places
     Text Search. If a real business is matched, its exact name, address,
     rating, and place_id are extracted and used to build a targeted
     article brief — instead of running a generic LLM-context search.
     This fixes queries like "Top 5 star hotel in Mussoorie" which
     previously returned inaccurate or hallucinated content.

  2. Firecrawl search/scrape of relevant public sources.
  3. OpenAI drafting of complete, publication-ready article packages.
  4. Persists each draft as an Article row with status='draft'.
  5. Records the place_id on the article for scheduler de-duplication.

The frontend polls GET /api/research/status/{job_id} for fast pass/fail
feedback (usually within seconds), and GET /api/articles to pick up new
drafts as they appear.
"""
import logging
import uuid
from threading import Lock

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from app.config import get_settings
from app.database import SessionLocal
from app.dependencies import require_admin
from app.schemas.article import ResearchRequest, ResearchResponse, ResearchStatusResponse
from app.services.research_pipeline import ResearchPipelineError, run_research_pipeline

router = APIRouter(tags=["research"])

logger = logging.getLogger("wishnest.research")

# In-memory job status tracker. Good enough for a single-process dev/small-scale
# deployment — lets the frontend get near-instant pass/fail feedback instead of
# blindly polling /api/articles for up to 3 minutes with no idea whether the
# pipeline already failed. Not persisted across restarts; that's fine since a
# job's lifetime is a few minutes at most.
_JOBS: dict[str, dict] = {}
_JOBS_LOCK = Lock()
_MAX_JOBS = 200  # simple bound so this dict never grows unbounded


def _set_job(job_id: str, **fields) -> None:
    with _JOBS_LOCK:
        _JOBS.setdefault(job_id, {}).update(fields)
        if len(_JOBS) > _MAX_JOBS:
            oldest_key = next(iter(_JOBS))
            _JOBS.pop(oldest_key, None)


def _get_job(job_id: str) -> dict | None:
    with _JOBS_LOCK:
        return dict(_JOBS[job_id]) if job_id in _JOBS else None


def _resolve_query_to_property(query: str) -> tuple[str, str | None]:
    """
    Try to resolve *query* to a specific named Google Maps property via
    Places Text Search. Returns (resolved_brief, place_id).

    If a real match is found:
    - Returns a targeted brief anchored to the property's real name, address,
      and Google rating (much more accurate than generic LLM context).
    - Returns the place_id for de-duplication recording.

    If no match is found (API not configured, quota exhausted, no results):
    - Returns the original query unchanged, with place_id=None.
    - The pipeline falls through to Firecrawl + OpenAI as before.

    Never raises — any failure returns the original query untouched.
    """
    try:
        from app.services.places_service import text_search_place
        listing = text_search_place(query, max_photos=15)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Places Text Search raised for query %r: %s", query[:80], exc)
        return query, None

    if listing is None:
        logger.info(
            "No Google Places match for query %r — running with original brief.", query[:80]
        )
        return query, None

    # Build a targeted brief from the live property's verified details
    name = listing.name or query
    address = listing.address or "India"
    maps_link = f"\nGoogle Maps: {listing.maps_url}" if listing.maps_url else ""

    if listing.rating:
        rating_str = (
            f"{listing.rating:.1f}★"
            + (f" ({listing.review_count:,} Google reviews)" if listing.review_count else "")
        )
    else:
        rating_str = "not yet rated on Google"

    resolved_brief = (
        f"Research and write a full WishNest editorial review for '{name}'.\n\n"
        f"Location: {address}{maps_link}\n"
        f"Google Rating: {rating_str}\n\n"
        f"Original search query: {query}\n\n"
        "This is a real business resolved from Google Maps. Research its:\n"
        "- Architecture, design, and aesthetic quality\n"
        "- Guest experience, hospitality, and service\n"
        "- Outdoor spaces, pool, gardens, views\n"
        "- Dining, local cuisine, and food quality\n"
        "- Connectivity, accessibility, and getting there\n"
        "- Price band and value for money\n"
        "- What makes it unique in its region\n\n"
        "Generate a complete WishNest article package including: headline, subtitle, "
        "full_article (rich HTML), executive_summary, pull_quotes, FAQ section, "
        "SEO fields (seo_title 50-60 chars, meta_description 150-160 chars, focus_keyword, keywords), "
        "WishNest ABCDE scoring (numeric scores 1.0-10.0 AND letter grades), key_takeaways, "
        "wishnest_verdict, developer_lessons, and the full social media package.\n\n"
        f"Set article_type to \"review\".\n"
        f"Set location to \"{address}\"."
    )

    logger.info(
        "Broad query %r resolved to property %r (place_id=%r, %.1f★) — using targeted brief.",
        query[:80], name, listing.place_id, listing.rating or 0.0,
    )
    return resolved_brief, listing.place_id


def _run_pipeline_in_background(
    job_id: str,
    brief: str,
    category: str | None = None,
    place_id: str | None = None,
) -> None:
    """
    Background worker: opens its own DB session (the request session is
    already closed by the time this runs), executes the full pipeline,
    and records success/failure status for the frontend to poll. Never
    raises — any unhandled exception is caught here so the background
    thread doesn't silently die.
    """
    db = SessionLocal()
    try:
        created = run_research_pipeline(brief, db, category=category, place_id=place_id)
        logger.info(
            "Research pipeline complete for brief %r — %d article(s) created.",
            brief[:80],
            len(created),
        )
        _set_job(
            job_id,
            status="success",
            message=f"{len(created)} article(s) drafted and added to Pending Review.",
            article_count=len(created),
        )
    except ResearchPipelineError as exc:
        logger.error("Research pipeline failed for brief %r: %s", brief[:80], exc)
        _set_job(job_id, status="failed", message=str(exc), article_count=0)
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "Unexpected error in research pipeline for brief %r: %s", brief[:80], exc
        )
        _set_job(job_id, status="failed", message=f"Unexpected error: {exc}", article_count=0)
    finally:
        db.close()


@router.post("/api/research", status_code=202, response_model=ResearchResponse)
def start_research(
    payload: ResearchRequest,
    background_tasks: BackgroundTasks,
    admin: str = Depends(require_admin),
):
    """
    Kick off the research pipeline in the background and return 202 immediately.

    The query is first resolved against Google Places Text Search: if a real
    named business is matched, a targeted property brief replaces the raw
    query text so the article is anchored to the verified property rather than
    generic LLM context. Broad queries like "Top 5 star hotel in Mussoorie"
    are automatically mapped to the best matching real property.

    The client should poll GET /api/research/status/{job_id} for fast pass/fail
    feedback, then GET /api/articles to see new drafts as they arrive.
    """
    settings = get_settings()

    if not settings.openai_api_key or not settings.firecrawl_api_key:
        raise HTTPException(
            status_code=503,
            detail="OPENAI_API_KEY / FIRECRAWL_API_KEY not configured.",
        )

    # ── Broad-query resolver ─────────────────────────────────────────────────
    # Always try Google Places first. If the query matches a real business,
    # swap in a targeted brief. If not (or if the Places API isn't configured),
    # fall through with the original text — Firecrawl will handle it.
    resolved_brief, place_id = _resolve_query_to_property(payload.query)

    job_id = uuid.uuid4().hex
    _set_job(job_id, status="pending", message="Research started.", article_count=0)

    background_tasks.add_task(
        _run_pipeline_in_background,
        job_id,
        resolved_brief,
        payload.category,
        place_id,
    )

    return ResearchResponse(
        message="Research started — drafts will appear in Pending Review within a few minutes.",
        query=payload.query,
        draft_article_ids=[],
        job_id=job_id,
    )


@router.get("/api/research/status/{job_id}", response_model=ResearchStatusResponse)
def get_research_status(job_id: str, admin: str = Depends(require_admin)):
    """
    Fast status check for a research job — lets the frontend surface failures
    (e.g. OpenAI quota exceeded) within seconds instead of appearing to hang
    for the full polling window.
    """
    job = _get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Unknown or expired job_id.")

    return ResearchStatusResponse(
        job_id=job_id,
        status=job.get("status", "pending"),
        message=job.get("message", ""),
        article_count=job.get("article_count", 0),
    )
