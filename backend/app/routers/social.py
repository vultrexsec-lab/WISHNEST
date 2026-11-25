"""CRM Social desk — channel status + compose/publish."""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.dependencies import require_admin
from app.services.postiz_service import (
    queue_compose_post,
    social_channel_status,
)

logger = logging.getLogger("wishnest.social")
router = APIRouter(tags=["social"])


class ComposeIn(BaseModel):
    channel: str = Field(..., min_length=2, max_length=32)
    content: str = Field(..., min_length=1, max_length=5000)
    url: str | None = Field(default=None, max_length=1000)
    image_url: str | None = Field(default=None, max_length=2000)
    article_id: str | None = Field(default=None, max_length=64)
    draft: bool = False


@router.get("/api/social/status")
def social_status(admin: str = Depends(require_admin)) -> dict[str, Any]:
    return social_channel_status()


@router.post("/api/social/publish")
def social_publish(
    body: ComposeIn,
    admin: str = Depends(require_admin),
) -> dict[str, Any]:
    result = queue_compose_post(
        channel=body.channel,
        content=body.content,
        url=body.url,
        image_url=body.image_url,
        article_id=body.article_id,
        draft=body.draft,
    )
    if result.get("status") == "error":
        logger.warning("social publish error: %s", result.get("detail"))
    return result
