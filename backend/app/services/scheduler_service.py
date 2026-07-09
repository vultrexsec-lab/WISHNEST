"""
Weekly auto-generation scheduler for WishNest.

Runs three research pipeline jobs every week — one each for:
  • Hospitality / reviews
  • Best places / destinations
  • Villas / best-of

Each job runs in a background thread (identical pattern to manual /api/research).
Run history (last 30 entries) is kept in memory so the dashboard can display it.
"""
import logging
import threading
from datetime import datetime, timezone
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.database import SessionLocal
from app.services.research_pipeline import ResearchPipelineError, run_research_pipeline

logger = logging.getLogger("wishnest.scheduler")

# ── Weekly auto-generation briefs per category ────────────────────────────────
AUTO_BRIEFS = [
    {
        "category": "reviews",
        "label": "Hospitality & Reviews",
        "brief": (
            "Research and review the best boutique resorts, luxury hospitality properties, "
            "design-led hotels, heritage homestays and unique stays in India this week. "
            "Cover architecture quality, guest experience, ABCDE scoring, location, pricing."
        ),
    },
    {
        "category": "destinations",
        "label": "Best Places & Destinations",
        "brief": (
            "Best travel destinations and places to visit in India — mountains, forests, "
            "heritage cities, hidden gems, ghumne wali jagah and emerging hotspots. "
            "Include what to do, where to stay, food, local culture, best season to visit, ratings."
        ),
    },
    {
        "category": "best-of",
        "label": "Villas & Best Of",
        "brief": (
            "Best luxury villas, private estates, premium holiday homes and curated villa stays "
            "available in India right now. Focus on design quality, privacy, outdoor spaces, "
            "amenities, value for money and interior/exterior quality."
        ),
    },
]

# ── In-memory run history (last 30 runs across all categories) ────────────────
_HISTORY: list[dict] = []
_HISTORY_LOCK = threading.Lock()
_MAX_HISTORY = 30

_scheduler: Optional[BackgroundScheduler] = None
_next_run: Optional[datetime] = None
_started_at: Optional[str] = None


# ── Internal helpers ──────────────────────────────────────────────────────────

def _record_run(category: str, label: str, status: str, message: str, article_count: int) -> None:
    with _HISTORY_LOCK:
        _HISTORY.append({
            "category": category,
            "label": label,
            "status": status,
            "message": message,
            "article_count": article_count,
            "ran_at": datetime.now(timezone.utc).isoformat(),
        })
        while len(_HISTORY) > _MAX_HISTORY:
            _HISTORY.pop(0)


def _run_category(brief: str, category: str, label: str) -> None:
    """Single-category pipeline run — called by the scheduler or manual trigger."""
    db = SessionLocal()
    try:
        logger.info("Scheduler: starting auto-generation for category=%r (%s)", category, label)
        created = run_research_pipeline(brief, db, category=category)
        msg = f"{len(created)} article(s) drafted."
        logger.info("Scheduler: completed category=%r — %s", category, msg)
        _record_run(category, label, "success", msg, len(created))
    except ResearchPipelineError as exc:
        logger.error("Scheduler: pipeline error for category=%r: %s", category, exc)
        _record_run(category, label, "failed", str(exc), 0)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Scheduler: unexpected error for category=%r: %s", category, exc)
        _record_run(category, label, "failed", f"Unexpected error: {exc}", 0)
    finally:
        db.close()


def _weekly_auto_generate() -> None:
    """Weekly job: generates one article per category, in sequence."""
    logger.info("Scheduler: weekly auto-generation started.")
    for item in AUTO_BRIEFS:
        _run_category(item["brief"], item["category"], item["label"])
    logger.info("Scheduler: weekly auto-generation finished.")
    # Refresh next_run after the job completes
    global _next_run
    if _scheduler:
        job = _scheduler.get_job("weekly_auto_generate")
        if job:
            _next_run = job.next_run_time


# ── Public API ────────────────────────────────────────────────────────────────

def start_scheduler() -> None:
    """Start the background scheduler. Call once from FastAPI lifespan startup."""
    global _scheduler, _next_run, _started_at

    if _scheduler is not None:
        return  # already running

    _scheduler = BackgroundScheduler(timezone="UTC")
    trigger = IntervalTrigger(weeks=1)
    job = _scheduler.add_job(
        _weekly_auto_generate,
        trigger,
        id="weekly_auto_generate",
        replace_existing=True,
    )
    _scheduler.start()
    _next_run = job.next_run_time
    _started_at = datetime.now(timezone.utc).isoformat()
    logger.info("Scheduler started. Next auto-generation: %s", _next_run)


def stop_scheduler() -> None:
    """Gracefully stop the scheduler. Call from FastAPI lifespan shutdown."""
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("Scheduler stopped.")


def get_scheduler_status() -> dict:
    """Return current scheduler state for the dashboard API."""
    global _next_run

    # Refresh next_run from live job metadata
    if _scheduler:
        job = _scheduler.get_job("weekly_auto_generate")
        if job:
            _next_run = job.next_run_time

    with _HISTORY_LOCK:
        history = list(reversed(_HISTORY))  # newest first

    return {
        "running": _scheduler is not None and _scheduler.running,
        "next_run": _next_run.isoformat() if _next_run else None,
        "started_at": _started_at,
        "categories": [
            {"category": b["category"], "label": b["label"]} for b in AUTO_BRIEFS
        ],
        "history": history,
    }


def trigger_now(category: str | None = None) -> None:
    """
    Manually trigger auto-generation for one or all categories.
    Runs in a background thread and returns immediately.
    """
    if category:
        items = [b for b in AUTO_BRIEFS if b["category"] == category]
        if not items:
            raise ValueError(f"Unknown category: {category!r}")
    else:
        items = AUTO_BRIEFS

    def _run() -> None:
        for item in items:
            _run_category(item["brief"], item["category"], item["label"])

    thread = threading.Thread(target=_run, daemon=True, name=f"scheduler-trigger-{category or 'all'}")
    thread.start()
