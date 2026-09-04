"""
Daily auto-generation scheduler for WishNest.

Runs one discovery-based pipeline job per day, rotating through:
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
from datetime import date, datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import get_settings
from app.database import SessionLocal
from app.models.automation import AutomationSettings
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

# ── Cross-category place_id lock ──────────────────────────────────────────────
# Tracks which place_ids are actively being processed by any category run at
# this moment (including concurrent "Run All Now" threads). Before entering the
# pipeline for a property, a runner must acquire its place_id slot here.  If
# the slot is taken, the property is skipped — it is already being handled.
# This closes the race window where two category runs discover the same
# place_id in parallel and both enter run_research_pipeline before either
# has committed, bypassing the DB pre-check and the unique index.
_ACTIVE_PLACE_IDS_LOCK = threading.Lock()
_ACTIVE_PLACE_IDS: set[str] = set()

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


def get_or_create_automation_settings(db) -> AutomationSettings:
    """Return the singleton settings row, creating the opt-in default if needed."""
    settings = db.query(AutomationSettings).filter(AutomationSettings.id == 1).first()
    if settings:
        return settings
    settings = AutomationSettings(
        id=1,
        public_app_url=get_settings().public_app_url or None,
    )
    db.add(settings)
    db.commit()
    db.refresh(settings)
    return settings


def _run_category(item: dict) -> tuple[list, str, str]:
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
    generated_articles = []
    pipeline_error = False
    try:
        # ── Live discovery path ──────────────────────────────────────────────
        from app.services.discovery_service import (
            build_property_brief,
            discover_fresh_properties,
            get_excluded_place_ids,
        )

        logger.info(
            "Scheduler: starting live discovery for category=%r (%s)", category, label
        )
        # target_count=1 — one property per category per batch run prevents
        # semantic duplicates (two articles for near-identical locations from
        # the same query set landing in the dashboard simultaneously).
        fresh_properties = discover_fresh_properties(category, db, target_count=1, max_photos=15)

        # ── Explicit dedup + hard limit before the loop ──────────────────────
        # Belt-and-suspenders: deduplicate the returned list by place_id so
        # that a repeated data_id from the SerpApi response never enters the
        # pipeline more than once, then enforce an absolute ceiling of 1
        # property per category per run regardless of target_count.
        if fresh_properties:
            _seen_batch_pids: set[str] = set()
            _deduped: list = []
            for _p in fresh_properties:
                _pid = _p.place_id or ""
                if _pid and _pid in _seen_batch_pids:
                    logger.warning(
                        "Scheduler: dropped duplicate place_id=%r (%r) from batch before loop.",
                        _pid, _p.name,
                    )
                    continue
                if _pid:
                    _seen_batch_pids.add(_pid)
                _deduped.append(_p)
            fresh_properties = _deduped[:1]  # absolute max: 1 property per category run

        if fresh_properties:
            for listing in fresh_properties:
                pid = listing.place_id or ""

                # ── Cross-category place_id lock ─────────────────────────────
                # Acquire a process-level slot for this place_id before doing
                # anything else.  If another category run in the same batch is
                # already processing this property, skip it immediately — the
                # twin will produce the article; we must not race it.
                with _ACTIVE_PLACE_IDS_LOCK:
                    if pid and pid in _ACTIVE_PLACE_IDS:
                        logger.warning(
                            "Scheduler: skipping %r (place_id=%r) — "
                            "already being processed by a concurrent category run.",
                            listing.name, pid,
                        )
                        continue
                    if pid:
                        _ACTIVE_PLACE_IDS.add(pid)

                try:
                    # ── Fresh DB exclusion check ─────────────────────────────
                    # Re-query the DB right before entering the pipeline so we
                    # catch articles committed by a concurrent run since the
                    # initial discovery query ran (the initial query's snapshot
                    # may already be stale by the time we get here).
                    if pid:
                        current_excluded = get_excluded_place_ids(db)
                        if pid in current_excluded:
                            logger.warning(
                                "Scheduler: halting for %r (place_id=%r) — "
                                "a concurrent run already committed this article.",
                                listing.name, pid,
                            )
                            continue

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
                        generated_articles.extend(created)
                        logger.info(
                            "Scheduler: drafted %d article(s) for %r", len(created), listing.name
                        )
                    except ResearchPipelineError as exc:
                        pipeline_error = True
                        logger.error(
                            "Scheduler: pipeline error for property %r: %s", listing.name, exc
                        )
                    except Exception as exc:  # noqa: BLE001
                        pipeline_error = True
                        logger.exception(
                            "Scheduler: unexpected error for property %r: %s", listing.name, exc
                        )
                finally:
                    # Always release the slot so future runs can re-try if
                    # the pipeline failed before committing.
                    if pid:
                        with _ACTIVE_PLACE_IDS_LOCK:
                            _ACTIVE_PLACE_IDS.discard(pid)

            status = "failed" if pipeline_error and not generated_articles else "success"
            msg = f"{total_created} article(s) drafted from {len(fresh_properties)} live-discovered properties."
            if pipeline_error:
                msg += " The pipeline reported an error; check the run history."
            logger.info("Scheduler: completed category=%r — %s", category, msg)
            _record_run(category, label, status, msg, total_created)
            return generated_articles, status, msg

        # ── Fallback: no live properties found — halt gracefully ─────────────
        logger.warning(
            "Scheduler: no fresh live properties found for category=%r after exhausting "
            "all discovery queries — halting gracefully (no fallback to avoid generic content).",
            category,
        )
        msg = "No new unique properties found — all discovered properties already exist in DB."
        _record_run(category, label, "skipped", msg, 0)
        return [], "skipped", msg

    except Exception as exc:  # noqa: BLE001
        logger.exception("Scheduler: unexpected error for category=%r: %s", category, exc)
        msg = f"Unexpected error: {exc}"
        _record_run(category, label, "failed", msg, 0)
        return [], "failed", msg
    finally:
        db.close()


def _category_for_day(day: date) -> dict:
    """Rotate the daily slot deterministically so one article is drafted per day."""
    return _FALLBACK_BRIEFS[day.toordinal() % len(_FALLBACK_BRIEFS)]


def _daily_auto_generate() -> None:
    """Generate one draft for the configured local calendar day."""
    db = SessionLocal()
    settings = None
    try:
        settings = get_or_create_automation_settings(db)
        if not settings.enabled:
            logger.info("Scheduler: daily automation is paused; skipping scheduled run.")
            return

        try:
            local_now = datetime.now(ZoneInfo(settings.timezone))
        except ZoneInfoNotFoundError:
            logger.error(
                "Scheduler: invalid timezone %r; daily run skipped.",
                settings.timezone,
            )
            return
        run_date = local_now.date()

        # A DB row lock makes the job idempotent across reloads or multiple
        # backend workers: only one process may claim a local calendar day.
        locked = (
            db.query(AutomationSettings)
            .filter(AutomationSettings.id == 1)
            .with_for_update()
            .first()
        )
        if not locked or not locked.enabled or locked.last_run_date == run_date:
            return
        locked.last_run_date = run_date
        locked.last_run_status = "running"
        locked.last_run_message = "Daily article generation is in progress."
        locked.last_run_at = datetime.now(timezone.utc)
        db.commit()
    finally:
        db.close()

    item = _category_for_day(run_date)
    created, run_status, run_message = _run_category(item)
    article_count = len(created)

    notification_message = ""
    if created:
        try:
            from app.services.gmail_service import send_article_ready_email
            first = created[0]
            send_article_ready_email(
                headline=first.headline,
                article_id=str(first.id),
                category=first.category,
                notification_email=settings.notification_email,
                public_app_url=settings.public_app_url,
            )
            notification_message = " Gmail review notification sent."
        except Exception as exc:  # noqa: BLE001
            # Email must never delete or invalidate a successfully created
            # article. Surface the problem in history and the settings panel.
            notification_message = f" Gmail notification failed: {exc}"
            logger.exception("Scheduler: article notification failed: %s", exc)

    status = run_status
    message = run_message + notification_message
    update_db = SessionLocal()
    try:
        current = get_or_create_automation_settings(update_db)
        current.last_run_status = status
        current.last_run_message = message
        current.last_run_at = datetime.now(timezone.utc)
        if created:
            current.last_article_id = str(created[0].id)
        update_db.commit()
    finally:
        update_db.close()


def _weekly_auto_generate() -> None:
    """Legacy manual batch: generates one article per category in sequence."""
    progress_key = "all"
    with _PROGRESS_LOCK:
        if progress_key in _IN_PROGRESS:
            logger.warning("Scheduler: weekly job skipped — already in progress.")
            return
        _IN_PROGRESS.add(progress_key)

    try:
        logger.info("Scheduler: manual batch generation started.")
        for item in _FALLBACK_BRIEFS:
            _run_category(item)
        logger.info("Scheduler: manual batch generation finished.")
    finally:
        with _PROGRESS_LOCK:
            _IN_PROGRESS.discard(progress_key)

        # Refresh next_run after the job completes
        with _STATE_LOCK:
            if _scheduler:
                job = _scheduler.get_job("daily_auto_generate")
                if job:
                    global _next_run
                    _next_run = job.next_run_time


# ── Public API ────────────────────────────────────────────────────────────────

def start_scheduler() -> None:
    """Start the background scheduler. Call once from FastAPI lifespan startup."""
    global _scheduler, _next_run, _started_at

    db = SessionLocal()
    try:
        saved = get_or_create_automation_settings(db)
        schedule_time = saved.daily_time
        schedule_timezone = saved.timezone
    finally:
        db.close()

    with _STATE_LOCK:
        if _scheduler is not None:
            return  # already running

        sched = BackgroundScheduler(timezone="UTC")
        # The job is always scheduled, but it checks the persisted enabled
        # flag before doing work. This lets pause/resume survive restarts
        # without repeatedly adding/removing APScheduler jobs.
        try:
            hour, minute = (int(part) for part in schedule_time.split(":"))
            schedule_zone = ZoneInfo(schedule_timezone)
        except (ValueError, ZoneInfoNotFoundError):
            logger.warning(
                "Scheduler: invalid saved schedule (%s, %s); using 08:00 Asia/Kolkata.",
                schedule_time,
                schedule_timezone,
            )
            hour, minute = 8, 0
            schedule_zone = ZoneInfo("Asia/Kolkata")
        trigger = CronTrigger(
            hour=hour,
            minute=minute,
            timezone=schedule_zone,
        )
        job = sched.add_job(
            _daily_auto_generate,
            trigger,
            id="daily_auto_generate",
            replace_existing=True,
        )
        sched.start()
        _scheduler = sched
        _next_run = job.next_run_time
        _started_at = datetime.now(timezone.utc).isoformat()

    logger.info("Scheduler started. Next daily automation run: %s", _next_run)


def refresh_schedule(daily_time: str, timezone_name: str) -> None:
    """Apply dashboard schedule changes to the live APScheduler job."""
    global _next_run
    hour, minute = (int(part) for part in daily_time.split(":"))
    with _STATE_LOCK:
        if _scheduler is None:
            return
        job = _scheduler.reschedule_job(
            "daily_auto_generate",
            trigger=CronTrigger(
                hour=hour,
                minute=minute,
                timezone=ZoneInfo(timezone_name),
            ),
        )
        _next_run = job.next_run_time if job else None


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
    db = SessionLocal()
    try:
        settings = get_or_create_automation_settings(db)
        automation = {
            "enabled": bool(settings.enabled),
            "daily_time": settings.daily_time,
            "timezone": settings.timezone,
            "notification_email": settings.notification_email,
            "public_app_url": settings.public_app_url,
            "last_run_date": settings.last_run_date.isoformat()
            if settings.last_run_date
            else None,
            "last_run_status": settings.last_run_status,
            "last_run_message": settings.last_run_message,
            "last_run_at": settings.last_run_at.isoformat()
            if settings.last_run_at
            else None,
        }
    finally:
        db.close()

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
        "automation": automation,
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
