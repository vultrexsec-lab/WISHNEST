"""
POST /api/research

Accepts a plain-text research brief and immediately returns 202 Accepted,
then runs the full pipeline in a background thread so the HTTP request
never times out.

Race-condition protection (three layers):

  1. Process-level in-flight mutex — keyed by a normalised fingerprint of
     the resolved place_id (or the raw query when no place_id is available).
     A second POST with the same key while the first is still running gets
     an immediate 409 Conflict, so double-clicks and rapid retries never
     launch two parallel pipelines for the same property.

  2. Pipeline-level pre-check — run_research_pipeline checks the DB for an
     existing non-trashed article with the same place_id before calling
     OpenAI, providing a second guard after any process restart.

  3. DB-level partial unique index — uq_articles_place_id_active on
     articles(place_id) WHERE place_id IS NOT NULL AND is_trash = false,
     created by _sync_schema() on startup. If both upper layers somehow
     race through, the INSERT raises IntegrityError which is caught and
     logged rather than creating a duplicate row.
"""
import hashlib
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

# ── Per-job status store ──────────────────────────────────────────────────────
_JOBS: dict[str, dict] = {}
_JOBS_LOCK = Lock()
_MAX_JOBS = 200


def _set_job(job_id: str, **fields) -> None:
    with _JOBS_LOCK:
        _JOBS.setdefault(job_id, {}).update(fields)
        if len(_JOBS) > _MAX_JOBS:
            oldest_key = next(iter(_JOBS))
            _JOBS.pop(oldest_key, None)


def _get_job(job_id: str) -> dict | None:
    with _JOBS_LOCK:
        return dict(_JOBS[job_id]) if job_id in _JOBS else None


# ── In-flight mutex — prevents duplicate pipelines for the same property ─────
# Key: SHA-256 of normalised place_id (preferred) or raw query text.
# Value: the job_id that is currently running so we can return it to the caller.
_IN_FLIGHT: dict[str, str] = {}   # fingerprint -> job_id
_IN_FLIGHT_LOCK = Lock()


def _fingerprint(place_id: str | None, query: str) -> str:
    """Stable 16-char key for a pipeline run."""
    raw = (place_id or query.strip().lower())
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _acquire_slot(fp: str, job_id: str) -> bool:
    """Register *job_id* as the in-flight run for fingerprint *fp*.
    Returns True if acquired, False if another run is already active."""
    with _IN_FLIGHT_LOCK:
        if fp in _IN_FLIGHT:
            return False
        _IN_FLIGHT[fp] = job_id
        return True


def _release_slot(fp: str) -> None:
    with _IN_FLIGHT_LOCK:
        _IN_FLIGHT.pop(fp, None)


# ── Places resolver ───────────────────────────────────────────────────────────

def _resolve_query_to_property(query: str) -> tuple[str, str | None]:
    """
    Try to resolve *query* to a specific named Google Maps property via
    Places Text Search. Returns (resolved_brief, place_id).

    Falls through with the original query and place_id=None if Places is
    not configured or returns no match — Firecrawl handles it as before.
    Never raises.
    """
    try:
        from app.services.places_service import text_search_place
        listing = text_search_place(query, max_photos=15)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Places Text Search raised for query %r: %s", query[:80], exc)
        return query, None

    if listing is None:
        logger.info("No Google Places match for query %r — using original brief.", query[:80])
        return query, None

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
        "Broad query %r resolved to %r (place_id=%r, %.1f★).",
        query[:80], name, listing.place_id, listing.rating or 0.0,
    )
    return resolved_brief, listing.place_id


# ── Background worker ─────────────────────────────────────────────────────────

def _run_pipeline_in_background(
    job_id: str,
    fp: str,
    brief: str,
    category: str | None = None,
    place_id: str | None = None,
) -> None:
    """
    Opens its own DB session, runs the full pipeline, records status, and
    always releases the in-flight slot so subsequent requests aren't blocked.
    Never raises.
    """
    db = SessionLocal()
    try:
        created = run_research_pipeline(brief, db, category=category, place_id=place_id)
        logger.info(
            "Research pipeline complete for brief %r — %d article(s) created.",
            brief[:80], len(created),
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
        _release_slot(fp)


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/api/research", status_code=202, response_model=ResearchResponse)
def start_research(
    payload: ResearchRequest,
    background_tasks: BackgroundTasks,
    admin: str = Depends(require_admin),
):
    """
    Kick off the research pipeline in the background and return 202 immediately.

    If the same query or place_id is already being processed (in-flight), returns
    409 Conflict so the caller knows not to enqueue a second run. The frontend
    uses the job_id to poll GET /api/research/status/{job_id} for pass/fail
    feedback, then GET /api/articles to see new drafts as they arrive.
    """
    settings = get_settings()

    if not settings.openai_api_key or not settings.firecrawl_api_key:
        raise HTTPException(
            status_code=503,
            detail="OPENAI_API_KEY / FIRECRAWL_API_KEY not configured.",
        )

    # Resolve the raw query to a specific Google Maps property if possible.
    resolved_brief, place_id = _resolve_query_to_property(payload.query)

    # ── In-flight duplicate guard ────────────────────────────────────────────
    fp = _fingerprint(place_id, payload.query)
    job_id = uuid.uuid4().hex

    if not _acquire_slot(fp, job_id):
        # Another request for the same property/query is already in progress.
        running_job_id = _IN_FLIGHT.get(fp, "")
        logger.warning(
            "Duplicate request rejected — place_id=%r query=%r already in-flight (job %s).",
            place_id, payload.query[:60], running_job_id,
        )
        raise HTTPException(
            status_code=409,
            detail=(
                "A research job for this property is already running. "
                "Please wait for it to complete before starting another."
            ),
        )

    _set_job(job_id, status="pending", message="Research started.", article_count=0)

    background_tasks.add_task(
        _run_pipeline_in_background,
        job_id,
        fp,
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
    (e.g. OpenAI quota exceeded) within seconds instead of appearing to hang.
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
