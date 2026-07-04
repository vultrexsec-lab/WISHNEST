"""
POST /api/research

Accepts a plain-text research brief and immediately returns 202 Accepted,
then runs the full pipeline in a background thread so the HTTP request
never times out:

  1. Firecrawl search/scrape of relevant public sources.
  2. OpenAI drafting of complete, publication-ready article packages.
  3. Persists each draft as an Article row with status='draft'.

The frontend polls GET /api/articles to pick up new drafts as they appear.
"""
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from app.config import get_settings
from app.database import SessionLocal
from app.dependencies import require_admin
from app.schemas.article import ResearchRequest, ResearchResponse
from app.services.research_pipeline import ResearchPipelineError, run_research_pipeline

router = APIRouter(tags=["research"])

logger = logging.getLogger("wishnest.research")


def _run_pipeline_in_background(brief: str, category: str | None = None) -> None:
    """
    Background worker: opens its own DB session (the request session is
    already closed by the time this runs), executes the full pipeline,
    and logs success or failure.  Never raises — any unhandled exception
    is caught here so the background thread doesn't silently die.
    """
    db = SessionLocal()
    try:
        created = run_research_pipeline(brief, db, category=category)
        logger.info(
            "Research pipeline complete for brief %r — %d article(s) created.",
            brief[:80],
            len(created),
        )
    except ResearchPipelineError as exc:
        logger.error("Research pipeline failed for brief %r: %s", brief[:80], exc)
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "Unexpected error in research pipeline for brief %r: %s", brief[:80], exc
        )
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
    The client should poll GET /api/articles to see new drafts as they arrive.
    """
    settings = get_settings()

    if not settings.openai_api_key or not settings.firecrawl_api_key:
        raise HTTPException(
            status_code=503,
            detail="OPENAI_API_KEY / FIRECRAWL_API_KEY not configured.",
        )

    background_tasks.add_task(_run_pipeline_in_background, payload.query, payload.category)

    return ResearchResponse(
        message="Research started — drafts will appear in Pending Review within a few minutes.",
        query=payload.query,
        draft_article_ids=[],
    )
