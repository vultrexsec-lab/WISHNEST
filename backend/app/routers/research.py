"""
POST /api/research

Accepts a plain-text research brief and immediately returns 202 Accepted,
then runs the full pipeline in a background thread so the HTTP request
never times out:

  1. Firecrawl search/scrape of relevant public sources.
  2. OpenAI drafting of complete, publication-ready article packages.
  3. Persists each draft as an Article row with status='draft'.

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


def _run_pipeline_in_background(job_id: str, brief: str, category: str | None = None) -> None:
    """
    Background worker: opens its own DB session (the request session is
    already closed by the time this runs), executes the full pipeline,
    and records success/failure status for the frontend to poll. Never
    raises — any unhandled exception is caught here so the background
    thread doesn't silently die.
    """
    db = SessionLocal()
    try:
        created = run_research_pipeline(brief, db, category=category)
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
    The client should poll GET /api/research/status/{job_id} for fast pass/fail
    feedback, then GET /api/articles to see new drafts as they arrive.
    """
    settings = get_settings()

    if not settings.openai_api_key or not settings.firecrawl_api_key:
        raise HTTPException(
            status_code=503,
            detail="OPENAI_API_KEY / FIRECRAWL_API_KEY not configured.",
        )

    job_id = uuid.uuid4().hex
    _set_job(job_id, status="pending", message="Research started.", article_count=0)

    background_tasks.add_task(_run_pipeline_in_background, job_id, payload.query, payload.category)

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
