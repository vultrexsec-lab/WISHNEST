"""
GET /api/image-proxy?url=<encoded original image URL>

Downloads the image server-side and streams it back to the client. This
makes published articles resilient to:
  - Hotlink/referrer protection on the origin CDN (common with DDG image
    results, which point at arbitrary third-party sites).
  - CORS restrictions that would otherwise block the browser from loading
    the image directly.
  - The origin host going down after publish — we still serve whatever we
    last cached, and can be swapped for a persistent cache later without
    changing any article content.

Only http(s) URLs are allowed, and only actual image responses are
streamed through — everything else is rejected.
"""
import logging
import urllib.parse

import requests
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

logger = logging.getLogger("wishnest.image_proxy")

router = APIRouter(tags=["image-proxy"])

_ALLOWED_SCHEMES = {"http", "https"}
_MAX_BYTES = 15 * 1024 * 1024  # 15MB safety cap
_TIMEOUT = 10


@router.get("/api/image-proxy")
def proxy_image(url: str = Query(..., description="Original image URL to fetch and re-serve")):
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in _ALLOWED_SCHEMES or not parsed.netloc:
        raise HTTPException(status_code=400, detail="Invalid image URL.")

    try:
        resp = requests.get(
            url,
            timeout=_TIMEOUT,
            stream=True,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; WishNestImageProxy/1.0)",
                "Accept": "image/*",
            },
        )
        resp.raise_for_status()

        content_type = resp.headers.get("Content-Type", "")
        if not content_type.startswith("image/"):
            raise HTTPException(status_code=502, detail="Upstream did not return an image.")

        body = resp.content
        if len(body) > _MAX_BYTES:
            raise HTTPException(status_code=502, detail="Image too large.")

        return Response(
            content=body,
            media_type=content_type,
            headers={"Cache-Control": "public, max-age=604800, immutable"},
        )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.warning("Image proxy failed for %s: %s", url[:120], exc)
        raise HTTPException(status_code=502, detail="Failed to fetch upstream image.") from exc
