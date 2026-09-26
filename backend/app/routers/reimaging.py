"""
Reimaging Studio API — admin-only.

POST /api/reimaging/hotel
  { "hotel_name": str, "prompt": str }
  → pulls Google Maps photos, redesigns, writes article, saves draft

POST /api/reimaging/upload
  multipart/form-data:
    prompt: str
    hotel_name: optional str
    images: one or more image files
  → redesigns uploaded images, writes article, saves draft

GET /api/reimaging/status/{job_id}
  (optional future polling; currently jobs run synchronously with generous timeout)
"""
from __future__ import annotations

import base64
import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.dependencies import require_admin
from app.services.reimaging_service import run_reimaging_hotel, run_reimaging_upload

router = APIRouter(tags=["reimaging"])
logger = logging.getLogger("wishnest.reimaging")

MAX_UPLOAD_BYTES = 12 * 1024 * 1024  # 12 MB per image
ALLOWED_CONTENT = {"image/jpeg", "image/jpg", "image/png", "image/webp"}


class HotelReimagingRequest(BaseModel):
    hotel_name: str = Field(..., min_length=2, max_length=300)
    prompt: str = Field(..., min_length=5, max_length=2000)


class ReimagingResult(BaseModel):
    article_id: str
    hotel_name: str | None = None
    listing_name: str | None = None
    google_rating: float | None = None
    original_photo_urls: list[str] = []
    redesigned_image_urls: list[str] = []
    headline: str | None = None
    subtitle: str | None = None
    executive_summary: str | None = None
    wishnest_verdict: str | None = None
    status: str = "draft"
    message: str = ""


@router.post("/api/reimaging/hotel", response_model=ReimagingResult)
def reimaging_from_hotel(
    body: HotelReimagingRequest,
    admin: str = Depends(require_admin),
):
    """Mode A: hotel name + redesign prompt → Google Maps photos → AI redesign → draft article."""
    try:
        result = run_reimaging_hotel(body.hotel_name.strip(), body.prompt.strip())
        return ReimagingResult(**result)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Reimaging hotel mode failed")
        raise HTTPException(
            status_code=500,
            detail=f"Reimaging failed: {exc}",
        ) from exc


@router.post("/api/reimaging/upload", response_model=ReimagingResult)
async def reimaging_from_upload(
    prompt: str = Form(..., min_length=5, max_length=2000),
    hotel_name: str | None = Form(default=None),
    images: list[UploadFile] = File(...),
    admin: str = Depends(require_admin),
):
    """Mode B: user-uploaded image(s) + redesign prompt → AI redesign → draft article."""
    if not images:
        raise HTTPException(status_code=400, detail="At least one image file is required.")

    b64_list: list[str] = []
    for f in images[:6]:
        content_type = (f.content_type or "").lower()
        if content_type not in ALLOWED_CONTENT:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type “{content_type}”. Use JPEG, PNG, or WebP.",
            )
        data = await f.read()
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=400,
                detail=f"Image “{f.filename}” exceeds 12 MB limit.",
            )
        if len(data) < 100:
            continue
        b64_list.append(base64.b64encode(data).decode("ascii"))

    if not b64_list:
        raise HTTPException(status_code=400, detail="No valid images could be read.")

    try:
        result = run_reimaging_upload(
            prompt=prompt.strip(),
            image_b64_list=b64_list,
            hotel_name=(hotel_name or "").strip() or None,
        )
        return ReimagingResult(**result)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Reimaging upload mode failed")
        raise HTTPException(
            status_code=500,
            detail=f"Reimaging failed: {exc}",
        ) from exc
