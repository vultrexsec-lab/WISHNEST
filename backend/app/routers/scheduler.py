"""
GET  /api/scheduler/status   — scheduler status + run history (admin only)
POST /api/scheduler/trigger  — manually trigger auto-generation (admin only)
"""
import logging
import re
from datetime import datetime, timedelta
from typing import Any
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.dependencies import require_admin
from app.models.article import Article, ArticleStatus
from app.models.automation import AutomationSettings
from app.services import scheduler_service

router = APIRouter(tags=["scheduler"])
logger = logging.getLogger("wishnest.scheduler_router")


class TriggerRequest(BaseModel):
    category: Optional[str] = None  # None = all categories


class AutomationSettingsUpdate(BaseModel):
    enabled: Optional[bool] = None
    daily_time: Optional[str] = None
    timezone: Optional[str] = None
    notification_email: Optional[str] = None
    public_app_url: Optional[str] = None

    @field_validator("daily_time")
    @classmethod
    def validate_daily_time(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", value):
            raise ValueError("daily_time must use 24-hour HH:MM format.")
        return value

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: Optional[str]) -> Optional[str]:
        if value is not None:
            try:
                ZoneInfo(value)
            except ZoneInfoNotFoundError as exc:
                raise ValueError(f"Unknown IANA timezone: {value}") from exc
        return value

    @field_validator("public_app_url")
    @classmethod
    def validate_public_app_url(cls, value: Optional[str]) -> Optional[str]:
        if value and not re.match(r"^https?://", value):
            raise ValueError("public_app_url must start with http:// or https://.")
        return value.rstrip("/") if value else value


def _automation_response(settings: AutomationSettings) -> dict[str, Any]:
    return {
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


@router.get("/api/editorial/daily")
def daily_editorial_status(db: Session = Depends(get_db)):
    """Expose only safe, non-admin scheduling information to the public site."""
    settings = scheduler_service.get_or_create_automation_settings(db)
    try:
        local_now = datetime.now(ZoneInfo(settings.timezone))
    except ZoneInfoNotFoundError:
        local_now = datetime.now(ZoneInfo("Asia/Kolkata"))

    hour, minute = (int(part) for part in settings.daily_time.split(":"))
    next_run = local_now.replace(
        hour=hour,
        minute=minute,
        second=0,
        microsecond=0,
    )
    if next_run <= local_now:
        next_run += timedelta(days=1)

    latest = (
        db.query(Article)
        .filter(
            Article.is_trash.is_(False),
            Article.status.in_(
                [ArticleStatus.approved, ArticleStatus.scheduled, ArticleStatus.published]
            ),
        )
        .order_by(Article.published_at.desc().nullslast(), Article.created_at.desc())
        .first()
    )
    return {
        "enabled": bool(settings.enabled),
        "daily_time": settings.daily_time,
        "timezone": settings.timezone,
        "next_run_at": next_run.isoformat(),
        "last_ready_date": (
            settings.last_run_date.isoformat()
            if settings.last_run_status == "success" and settings.last_run_date
            else None
        ),
        "latest_article": (
            {
                "id": str(latest.id),
                "headline": latest.headline,
                "category": latest.category,
                "hero_image_url": latest.hero_image_url,
                "published_at": (
                    latest.published_at.isoformat()
                    if latest.published_at
                    else latest.created_at.isoformat()
                ),
            }
            if latest
            else None
        ),
    }


@router.get("/api/scheduler/status")
def scheduler_status(admin: str = Depends(require_admin)):
    """Return scheduler running state, next run time, active categories, and recent history."""
    return scheduler_service.get_scheduler_status()


@router.patch("/api/scheduler/settings")
def update_scheduler_settings(
    payload: AutomationSettingsUpdate,
    db: Session = Depends(get_db),
    admin: str = Depends(require_admin),
):
    """Persist pause/resume, daily local time, and notification preferences."""
    settings = scheduler_service.get_or_create_automation_settings(db)
    changes = payload.model_dump(exclude_unset=True)
    for key, value in changes.items():
        if key in {"notification_email", "public_app_url"} and value == "":
            value = None
        setattr(settings, key, value)
    db.commit()
    db.refresh(settings)

    if "daily_time" in changes or "timezone" in changes:
        scheduler_service.refresh_schedule(settings.daily_time, settings.timezone)

    logger.info(
        "Daily automation settings updated by admin=%r: enabled=%s time=%s timezone=%s",
        admin,
        settings.enabled,
        settings.daily_time,
        settings.timezone,
    )
    return {
        "message": (
            "Daily automation enabled."
            if settings.enabled
            else "Daily automation paused."
        ),
        "automation": _automation_response(settings),
        "scheduler": scheduler_service.get_scheduler_status(),
    }


@router.post("/api/scheduler/trigger", status_code=202)
def trigger_auto_generate(
    payload: TriggerRequest = TriggerRequest(),
    admin: str = Depends(require_admin),
):
    """
    Manually kick off the auto-generation pipeline for one or all categories.
    Returns 202 immediately — progress visible in GET /api/scheduler/status.
    Returns 409 if the requested category (or any run) is already in progress.
    """
    settings = get_settings()
    if not settings.openai_api_key:
        raise HTTPException(
            status_code=503,
            detail="OPENAI_API_KEY not configured. Add it to Replit Secrets.",
        )
    if not settings.firecrawl_api_key:
        raise HTTPException(
            status_code=503,
            detail="FIRECRAWL_API_KEY not configured. Add it to Replit Secrets.",
        )

    try:
        scheduler_service.trigger_now(category=payload.category)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        # Already in progress
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    label = payload.category or "all categories"
    logger.info("Manual trigger by admin=%r for category=%r", admin, label)
    return {
        "message": f"Auto-generation triggered for {label}. Articles will appear in Pending Review shortly.",
        "category": payload.category,
    }
