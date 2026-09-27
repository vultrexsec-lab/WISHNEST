"""
Reimaging Studio API — admin-only.

POST /api/reimaging/fetch-photos
  { "hotel_name": str }
  → returns 6–8 Google Maps photos for the property (preview only)

POST /api/reimaging/hotel
  { "hotel_name": str, "prompt": str }
  → pulls Google Maps photos, redesigns, writes article, saves draft

POST /api/reimaging/upload
  JSON body (no multipart):
  {
    "prompt": str,
    "hotel_name": optional str,
    "images_base64": [ "base64...", ... ]
  }
  → redesigns uploaded images, writes article, saves draft
"""
from __future__ import annotations

import base64
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.dependencies import require_admin
from app.services.places_service import text_search_place
from app.services.reimaging_service import run_reimaging_hotel, run_reimaging_upload

router = APIRouter(tags=["reimaging"])
logger = logging.getLogger("wishnest.reimaging")

MAX_UPLOAD_BYTES = 12 * 1024 * 1024
MAX_IMAGES = 6
FETCH_PHOTO_COUNT = 8


class HotelReimagingRequest(BaseModel):
    hotel_name: str = Field(..., min_length=2, max_length=300)
    prompt: str = Field(..., min_length=5, max_length=2000)
    # Optional: user-selected photo URLs from fetch-photos (only these are redesigned)
    photo_urls: list[str] | None = Field(default=None, max_length=9)


class FetchPhotosRequest(BaseModel):
    hotel_name: str = Field(..., min_length=2, max_length=300)


class FetchPhotosResponse(BaseModel):
    hotel_name: str
    listing_name: str | None = None
    google_rating: float | None = None
    review_count: int | None = None
    address: str | None = None
    photo_urls: list[str] = []
    message: str = ""


class UploadReimagingRequest(BaseModel):
    prompt: str = Field(..., min_length=5, max_length=2000)
    hotel_name: str | None = Field(default=None, max_length=300)
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
    s = (s or "").strip()
    if "," in s and s.lower().startswith("data:"):
        return s.split(",", 1)[1].strip()
    return s


@router.post("/api/reimaging/fetch-photos", response_model=FetchPhotosResponse)
def fetch_hotel_photos(
    body: FetchPhotosRequest,
    admin: str = Depends(require_admin),
):
    """Preview: resolve hotel name and return 6–8 Google Maps photo URLs."""
    name = body.hotel_name.strip()
    listing = text_search_place(name, max_photos=FETCH_PHOTO_COUNT)
    if not listing:
        raise HTTPException(
            status_code=404,
            detail=f"No Google Maps listing found for “{name}”. Try a more specific name.",
        )

    urls: list[str] = []
    if listing.photo_url:
        urls.append(listing.photo_url)
    if listing.photo_urls:
        for u in listing.photo_urls:
            if u and u not in urls:
                urls.append(u)
            if len(urls) >= FETCH_PHOTO_COUNT:
                break

    if not urls:
        raise HTTPException(
            status_code=404,
            detail=f"Found “{listing.name}” but no photos are available.",
        )

    return FetchPhotosResponse(
        hotel_name=name,
        listing_name=listing.name,
        google_rating=listing.rating,
        review_count=listing.review_count,
        address=listing.address,
        photo_urls=urls[:FETCH_PHOTO_COUNT],
        message=f"Found {len(urls[:FETCH_PHOTO_COUNT])} photos for {listing.name}.",
    )


@router.post("/api/reimaging/hotel", response_model=ReimagingResult)
def reimaging_from_hotel(
    body: HotelReimagingRequest,
    admin: str = Depends(require_admin),
):
    """Mode A: hotel name + redesign prompt → Google Maps photos → AI redesign → draft article."""
    try:
        result = run_reimaging_hotel(
            body.hotel_name.strip(),
            body.prompt.strip(),
            photo_urls=body.photo_urls,
        )
        return ReimagingResult(**result)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Reimaging hotel mode failed")
        msg = str(exc)
        if "uq_articles_place_id_active" in msg or "UniqueViolation" in msg or "duplicate key" in msg.lower():
            msg = (
                "A draft for this property already exists. "
                "Open the main Dashboard, trash or publish it, then try again — "
                "or wait for the latest backend deploy which allows multiple reimaging drafts."
            )
        else:
            msg = f"Reimaging failed: {msg[:400]}"
        raise HTTPException(status_code=500, detail=msg) from exc


@router.post("/api/reimaging/upload", response_model=ReimagingResult)
def reimaging_from_upload(
    body: UploadReimagingRequest,
    admin: str = Depends(require_admin),
):
    """Mode B: base64 image(s) + redesign prompt → AI redesign → draft article."""
    b64_list: list[str] = []
    for raw in body.images_base64[:MAX_IMAGES]:
        cleaned = _strip_data_url(raw)
        if not cleaned or len(cleaned) < 100:
            continue
        approx_bytes = (len(cleaned) * 3) // 4
        if approx_bytes > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=400,
                detail="One image exceeds the 12 MB limit.",
            )
        try:
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
