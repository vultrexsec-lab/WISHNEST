"""
Weekly auto-generation scheduler for WishNest.

Runs three discovery-based pipeline jobs every week — one each for:
  • Hospitality / reviews
  • Best places / destinations
  • Villas / best-of

Each job uses the live Google Places / SerpApi discovery engine to find
top-rated properties in India that have NOT yet been covered (checked via
the `place_id` column on the `articles` table), then generates a full
WishNest article for each fresh property found. This guarantees:

  1. No static/generic LLM briefs — every article is anchored to a real,
     named, live-rated property from Google Maps.
  2. No repetition — properties are excluded from future runs once covered,
     using their Google Places place_id as the persistent key.
  3. ≥10 high-res real photos per article — the discovery service enriches
     each candidate with its full Google Maps photo gallery (≤15 photos)
     before handing it to the pipeline.

Falls back to the original static brief for a category only when no fresh
live properties can be found (e.g. API not configured, quota exhausted).
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

# ── Fallback static briefs (used ONLY when live discovery finds nothing) ──────
# These are intentionally generic so they still work as a last resort even
# without a specific property to anchor the article to.
_FALLBACK_BRIEFS = [
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

# Expose the category/label metadata for the dashboard status endpoint
AUTO_BRIEFS = _FALLBACK_BRIEFS

# ── Shared state — ALL access must hold _STATE_LOCK ──────────────────────────
_STATE_LOCK = threading.Lock()
_scheduler: Optional[BackgroundScheduler] = None
_next_run: Optional[datetime] = None
_started_at: Optional[str] = None

# ── In-progress guard — tracks which category keys are currently running ──────
# "all" is used when all categories are triggered together.
_PROGRESS_LOCK = threading.Lock()
_IN_PROGRESS: set[str] = set()

# ── Run history (last 30 runs, newest-first on read) ─────────────────────────
_HISTORY: list[dict] = []
_HISTORY_LOCK = threading.Lock()
_MAX_HISTORY = 30


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


def _run_category(item: dict) -> None:
    """
    Single-category pipeline run using live Google Maps discovery.

    Strategy:
      1. Call `discover_fresh_properties(category)` to find top-rated India
         properties not yet in the DB (checked via place_id).
      2. For each fresh property, build a targeted research brief and run the
         full pipeline (Firecrawl → OpenAI → images → DB).
      3. Record the place_id on the created article rows for future dedup.
      4. If live discovery finds nothing (no API key, quota exhausted, etc.),
         fall back to the category's static generic brief so the scheduler
         never silently produces zero articles.
    """
    category: str = item["category"]
    label: str = item["label"]
    fallback_brief: str = item["brief"]

    db = SessionLocal()
    total_created = 0
    try:
        # ── Live discovery path ──────────────────────────────────────────────
        from app.services.discovery_service import build_property_brief, discover_fresh_properties

        logger.info(
            "Scheduler: starting live discovery for category=%r (%s)", category, label
        )
        # target_count=1 — one property per category per batch run prevents
        # semantic duplicates (two articles for near-identical locations from
        # the same query set landing in the dashboard simultaneously).
        fresh_properties = discover_fresh_properties(category, db, target_count=1, max_photos=15)

        if fresh_properties:
            for listing in fresh_properties:
                brief = build_property_brief(listing, category)
                logger.info(
                    "Scheduler: generating article for %r (place_id=%r)",
                    listing.name, listing.place_id,
                )
                try:
                    created = run_research_pipeline(
                        brief,
                        db,
                        category=category,
                        place_id=listing.place_id,
                    )
                    total_created += len(created)
                    logger.info(
                        "Scheduler: drafted %d article(s) for %r", len(created), listing.name
                    )
                except ResearchPipelineError as exc:
                    logger.error(
                        "Scheduler: pipeline error for property %r: %s", listing.name, exc
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.exception(
                        "Scheduler: unexpected error for property %r: %s", listing.name, exc
                    )

            msg = f"{total_created} article(s) drafted from {len(fresh_properties)} live-discovered properties."
            logger.info("Scheduler: completed category=%r — %s", category, msg)
            _record_run(category, label, "success", msg, total_created)
            return

        # ── Fallback: no live properties found — use static brief ────────────
        logger.warning(
            "Scheduler: no fresh live properties found for category=%r — "
            "falling back to static brief.", category,
        )
        try:
            created = run_research_pipeline(fallback_brief, db, category=category)
            msg = f"{len(created)} article(s) drafted (static brief fallback — no live properties found)."
            logger.info("Scheduler: completed category=%r (fallback) — %s", category, msg)
            _record_run(category, label, "success", msg, len(created))
        except ResearchPipelineError as exc:
            logger.error("Scheduler: pipeline error for category=%r (fallback): %s", category, exc)
            _record_run(category, label, "failed", str(exc), 0)

    except Exception as exc:  # noqa: BLE001
        logger.exception("Scheduler: unexpected error for category=%r: %s", category, exc)
        _record_run(category, label, "failed", f"Unexpected error: {exc}", 0)
    finally:
        db.close()


def _weekly_auto_generate() -> None:
    """Weekly job: generates articles per category in sequence."""
    progress_key = "all"
    with _PROGRESS_LOCK:
        if progress_key in _IN_PROGRESS:
            logger.warning("Scheduler: weekly job skipped — already in progress.")
            return
        _IN_PROGRESS.add(progress_key)

    try:
        logger.info("Scheduler: weekly auto-generation started.")
        for item in _FALLBACK_BRIEFS:
            _run_category(item)
        logger.info("Scheduler: weekly auto-generation finished.")
    finally:
        with _PROGRESS_LOCK:
            _IN_PROGRESS.discard(progress_key)

        # Refresh next_run after the job completes
        with _STATE_LOCK:
            if _scheduler:
                job = _scheduler.get_job("weekly_auto_generate")
                if job:
                    global _next_run
                    _next_run = job.next_run_time


# ── Public API ────────────────────────────────────────────────────────────────

def start_scheduler() -> None:
    """Start the background scheduler. Call once from FastAPI lifespan startup."""
    global _scheduler, _next_run, _started_at

    with _STATE_LOCK:
        if _scheduler is not None:
            return  # already running

        sched = BackgroundScheduler(timezone="UTC")
        trigger = IntervalTrigger(weeks=1)
        job = sched.add_job(
            _weekly_auto_generate,
            trigger,
            id="weekly_auto_generate",
            replace_existing=True,
        )
        sched.start()
        _scheduler = sched
        _next_run = job.next_run_time
        _started_at = datetime.now(timezone.utc).isoformat()

    logger.info("Scheduler started. Next auto-generation: %s", _next_run)


def stop_scheduler() -> None:
    """Gracefully stop the scheduler. Call from FastAPI lifespan shutdown."""
    global _scheduler
    with _STATE_LOCK:
        sched = _scheduler
        _scheduler = None

    if sched:
        sched.shutdown(wait=False)
        logger.info("Scheduler stopped.")


def get_scheduler_status() -> dict:
    """Return current scheduler state for the dashboard API."""
    with _STATE_LOCK:
        running = _scheduler is not None and _scheduler.running
        # Refresh next_run from live job metadata while holding the lock
        if _scheduler:
            job = _scheduler.get_job("weekly_auto_generate")
            next_run_val = job.next_run_time if job else _next_run
        else:
            next_run_val = _next_run
        started = _started_at

    with _PROGRESS_LOCK:
        active = sorted(_IN_PROGRESS)

    with _HISTORY_LOCK:
        history = list(reversed(_HISTORY))  # newest first

    return {
        "running": running,
        "run_state": "running" if active else "idle",
        "active_categories": active,
        "next_run": next_run_val.isoformat() if next_run_val else None,
        "started_at": started,
        "categories": [
            {"category": b["category"], "label": b["label"]} for b in _FALLBACK_BRIEFS
        ],
        "history": history,
    }


def trigger_now(category: str | None = None) -> None:
    """
    Manually trigger auto-generation for one or all categories.
    Runs in a background thread and returns immediately.

    Raises ValueError for unknown category.
    Raises RuntimeError if the requested category (or "all") is already in progress.
    """
    if category:
        items = [b for b in _FALLBACK_BRIEFS if b["category"] == category]
        if not items:
            raise ValueError(f"Unknown category: {category!r}")
        progress_key = category
    else:
        items = list(_FALLBACK_BRIEFS)
        progress_key = "all"

    with _PROGRESS_LOCK:
        if progress_key in _IN_PROGRESS or "all" in _IN_PROGRESS:
            label = category or "all categories"
            raise RuntimeError(f"Auto-generation for '{label}' is already in progress.")
        _IN_PROGRESS.add(progress_key)

    def _run() -> None:
        try:
            for item in items:
                _run_category(item)
        finally:
            with _PROGRESS_LOCK:
                _IN_PROGRESS.discard(progress_key)

    thread = threading.Thread(
        target=_run,
        daemon=True,
        name=f"scheduler-trigger-{progress_key}",
    )
    thread.start()
