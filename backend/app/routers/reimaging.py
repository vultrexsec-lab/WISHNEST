"""
Reimaging Studio API — admin-only.

POST /api/reimaging/hotel
  { "hotel_name": str, "prompt": str }
  → pulls Google Maps photos, redesigns, writes article, saves draft

POST /api/reimaging/upload
  JSON body (no multipart — avoids python-multipart dependency at boot):
  {
    "prompt": str,
    "hotel_name": optional str,
    "images_base64": [ "base64...", ... ]   # raw base64, no data: prefix
  }
  → redesigns uploaded images, writes article, saves draft
"""
from __future__ import annotations

import base64
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.dependencies import require_admin
from app.services.reimaging_service import run_reimaging_hotel, run_reimaging_upload

router = APIRouter(tags=["reimaging"])
logger = logging.getLogger("wishnest.reimaging")

MAX_UPLOAD_BYTES = 12 * 1024 * 1024  # 12 MB per image (decoded)
MAX_IMAGES = 6


class HotelReimagingRequest(BaseModel):
    hotel_name: str = Field(..., min_length=2, max_length=300)
    prompt: str = Field(..., min_length=5, max_length=2000)


class UploadReimagingRequest(BaseModel):
    prompt: str = Field(..., min_length=5, max_length=2000)
    hotel_name: str | None = Field(default=None, max_length=300)
    # Raw base64 strings (no "data:image/...;base64," prefix required;
    # prefix is stripped if present)
    images_base64: list[str] = Field(..., min_length=1, max_length=MAX_IMAGES)


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


def _strip_data_url(s: str) -> str:
    """Remove data-URL prefix if the client sent one."""
    s = (s or "").strip()
    if "," in s and s.lower().startswith("data:"):
        return s.split(",", 1)[1].strip()
    return s


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
def reimaging_from_upload(
    body: UploadReimagingRequest,
    admin: str = Depends(require_admin),
):
    """Mode B: base64 image(s) + redesign prompt → AI redesign → draft article.

    Uses JSON body (not multipart) so the app boots without python-multipart.
    """
    b64_list: list[str] = []
    for raw in body.images_base64[:MAX_IMAGES]:
        cleaned = _strip_data_url(raw)
        if not cleaned or len(cleaned) < 100:
            continue
        # Rough size check on base64 (decoded ≈ 3/4 of encoded length)
        approx_bytes = (len(cleaned) * 3) // 4
        if approx_bytes > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=400,
                detail="One image exceeds the 12 MB limit.",
            )
        try:
            # Validate it is valid base64
            base64.b64decode(cleaned, validate=True)
        except Exception:
            raise HTTPException(
                status_code=400,
                detail="Invalid base64 image data.",
            ) from None
        b64_list.append(cleaned)

    if not b64_list:
        raise HTTPException(status_code=400, detail="No valid images could be read.")

    try:
        result = run_reimaging_upload(
            prompt=body.prompt.strip(),
            image_b64_list=b64_list,
            hotel_name=(body.hotel_name or "").strip() or None,
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
