"""
GET  /api/scheduler/status   — scheduler status + run history (admin only)
POST /api/scheduler/trigger  — manually trigger auto-generation (admin only)
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.config import get_settings
from app.dependencies import require_admin
from app.services import scheduler_service

router = APIRouter(tags=["scheduler"])
logger = logging.getLogger("wishnest.scheduler_router")


class TriggerRequest(BaseModel):
    category: Optional[str] = None  # None = all categories


@router.get("/api/scheduler/status")
def scheduler_status(admin: str = Depends(require_admin)):
    """Return scheduler running state, next run time, active categories, and recent history."""
    return scheduler_service.get_scheduler_status()


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
