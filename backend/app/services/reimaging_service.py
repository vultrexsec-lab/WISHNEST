"""
Reimaging Studio service.

Two modes:
  1. Hotel name + prompt  → pull 6–9 real Google Maps photos → redesign via OpenAI
  2. Uploaded image(s) + prompt → redesign via OpenAI

Then generate a full WishNest-style article package (draft) so the result
can be reviewed and posted through the existing approval flow.

Does NOT modify any existing research / image / article pipelines.
"""
from __future__ import annotations

import re

from pathlib import Path

import base64
import io
import logging
import uuid
from typing import Any

import requests
from openai import OpenAI

from app.config import get_settings
from app.database import SessionLocal
from app.models.article import Article, ArticleStatus, ArticleType, Grade
from app.services.places_service import text_search_place, PropertyListing

logger = logging.getLogger("wishnest.reimaging_service")

# How many source photos to pull from Google Maps when using hotel-name mode
MIN_SOURCE_PHOTOS = 6
MAX_SOURCE_PHOTOS = 9
# How many redesigned images to generate per run
MAX_REDESIGNED = 2  # keep API cost low; user can re-run for more

IMAGE_GEN_MODEL = "gpt-image-1"
VISION_MODEL = "gpt-4o"
ARTICLE_MODEL = "gpt-4o-mini"


def _client() -> OpenAI:
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured.")
    return OpenAI(api_key=settings.openai_api_key)


def _grok_client() -> OpenAI:
    """xAI Grok — OpenAI-compatible API for before/after article text."""
    settings = get_settings()
    key = settings.xai_api_key
    if not key:
        raise RuntimeError(
            "XAI_API_KEY is not configured. Add your Grok API key on Render to write before/after articles."
        )
    return OpenAI(api_key=key, base_url="https://api.x.ai/v1")


def _grok_model() -> str:
    return (get_settings().xai_model or "grok-2-latest").strip() or "grok-2-latest"


def _download_image_as_b64(url: str, timeout: int = 15) -> str | None:
    """Download an image and return base64 string (no data: prefix)."""
    try:
        r = requests.get(
            url,
            timeout=timeout,
            headers={"User-Agent": "WishNest-Reimaging/1.0"},
            allow_redirects=True,
        )
        r.raise_for_status()
        content_type = r.headers.get("Content-Type", "image/jpeg").split(";")[0].strip()
        if not content_type.startswith("image/"):
            return None
        return base64.b64encode(r.content).decode("ascii")
    except Exception as exc:
        logger.warning("Failed to download image %s: %s", url[:80], exc)
        return None


def _fetch_hotel_photos(hotel_name: str) -> tuple[PropertyListing | None, list[str]]:
    """
    Resolve hotel_name via SerpApi/Google Maps and return up to MAX_SOURCE_PHOTOS
    high-res photo URLs. Falls back to empty list if Places is unavailable.
    """
    listing = text_search_place(hotel_name, max_photos=MAX_SOURCE_PHOTOS)
    if not listing:
        return None, []

    urls: list[str] = []
    if listing.photo_url:
        urls.append(listing.photo_url)
    if listing.photo_urls:
        for u in listing.photo_urls:
            if u and u not in urls:
                urls.append(u)
            if len(urls) >= MAX_SOURCE_PHOTOS:
                break

    return listing, urls[:MAX_SOURCE_PHOTOS]


def _vision_redesign_prompt(
    client: OpenAI,
    image_b64: str,
    user_prompt: str,
    hotel_context: str | None = None,
) -> str:
    """Enrich a short user brief into a stronger image-edit instruction."""
    try:
        context_line = (
            f"This photo is from the property: {hotel_context}. "
            if hotel_context
            else "This is a photo of a building / interior / outdoor space. "
        )
        system = (
            "You are a world-class hospitality architect and interior designer. "
            "Given a real photo and a redesign brief, write a single detailed "
            "image-edit instruction (60–120 words). Preserve the same space and "
            "layout; only apply the brief. Output ONLY the instruction."
        )
        user_content = [
            {
                "type": "text",
                "text": f"{context_line}User redesign brief: {user_prompt}\n\nWrite the edit instruction now.",
            },
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{image_b64}",
                    "detail": "low",
                },
            },
        ]
        resp = client.chat.completions.create(
            model=VISION_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_content},
            ],
            max_tokens=280,
            temperature=0.4,
        )
        out = (resp.choices[0].message.content or "").strip()
        return out if len(out) > 20 else user_prompt
    except Exception as exc:
        logger.warning("Vision redesign prompt failed, using raw prompt: %s", exc)
        return user_prompt


_MEDIA_DIR = Path(__file__).resolve().parent.parent / "data" / "reimaging_media"
_MEDIA_URL_PREFIX = "/api/reimaging/media"


def _api_public_base() -> str:
    """Absolute API origin so article <img> works on Vercel (not relative /api on the frontend host)."""
    import os
    for key in ("PUBLIC_API_BASE_URL", "RENDER_EXTERNAL_URL"):
        val = (os.environ.get(key) or "").strip().rstrip("/")
        if val.startswith("http"):
            return val
    return ""


def _public_media_url(path_or_url: str) -> str:
    """Ensure media/proxy paths are absolute when public API base is known."""
    if not path_or_url:
        return path_or_url
    u = path_or_url.strip()
    if u.startswith("http://") or u.startswith("https://") or u.startswith("data:"):
        return u
    base = _api_public_base()
    if u.startswith("/") and base:
        return f"{base}{u}"
    return u


# Prefer one model to avoid burning credits on retries
EDIT_MODELS = (
    IMAGE_GEN_MODEL,  # gpt-image-1
    "gpt-image-1-mini",  # cheaper fallback only if primary fails
)


def _ensure_media_dir() -> Path:
    _MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    return _MEDIA_DIR


def _persist_image_bytes(data: bytes, ext: str = "png") -> str:
    """
    Store image bytes in Postgres (media_blobs) so they survive Render restarts.
    Also mirror to local disk as a hot cache. Returns /api/reimaging/media/{uuid}.
    """
    from app.models.media_blob import MediaBlob

    if not data:
        raise RuntimeError("Cannot persist empty image")

    ext = (ext or "png").lstrip(".").lower()
    if ext in ("jpg", "jpeg"):
        ctype = "image/jpeg"
    elif ext == "webp":
        ctype = "image/webp"
    else:
        ctype = "image/png"
        ext = "png"

    blob_id = uuid.uuid4()
    filename = f"{blob_id.hex}.{ext}"

    db = SessionLocal()
    try:
        row = MediaBlob(
            id=blob_id,
            content_type=ctype,
            filename=filename,
            data=data,
        )
        db.add(row)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    # Best-effort disk cache (optional; DB is source of truth)
    try:
        folder = _ensure_media_dir()
        (folder / filename).write_bytes(data)
    except Exception as disk_exc:
        logger.warning("Disk cache write skipped: %s", disk_exc)

    logger.info("Persisted redesign image %s (%d bytes) to media_blobs", blob_id, len(data))
    path = f"{_MEDIA_URL_PREFIX}/{blob_id}"
    return _public_media_url(path)


def _bytes_to_file(data: bytes, filename: str = "source.png"):
    buf = io.BytesIO(data)
    buf.name = filename
    return buf


def _edit_image_with_prompt(
    client: OpenAI,
    image_bytes: bytes,
    edit_prompt: str,
) -> str | None:
    """
    Redesign using OpenAI images.edit with the real source photo as reference.
    Falls back to text-only images.generate if edit is unavailable.
    """
    if not image_bytes or len(image_bytes) < 100:
        logger.warning("Empty or tiny source image for edit")
        return None
    if len(image_bytes) > 20 * 1024 * 1024:
        logger.warning("Source image too large (%d bytes)", len(image_bytes))
        return None

    prompt = (edit_prompt or "").strip()
    if len(prompt) < 5:
        prompt = (
            "Edit this photo to look more luxurious and refined while keeping "
            "the same layout and architecture. Photorealistic hospitality photography."
        )
    if not prompt.lower().startswith(
        ("edit", "redesign", "modify", "transform", "improve", "make")
    ):
        prompt = f"Edit this photo: {prompt}"

    last_err: Exception | None = None
    seen: set[str] = set()
    sizes_to_try = ("1024x1024",)  # single size = fewer failed retries / lower cost

    # Write a real temp file — some SDK versions are picky about BytesIO
    import tempfile
    import os
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp.write(image_bytes)
            tmp_path = tmp.name
    except Exception as exc:
        logger.warning("Temp file write failed, using BytesIO: %s", exc)
        tmp_path = None

    for model in EDIT_MODELS:
        if model in seen:
            continue
        seen.add(model)
        for size in sizes_to_try:
            try:
                if tmp_path:
                    img_handle = open(tmp_path, "rb")
                else:
                    img_handle = _bytes_to_file(image_bytes, "source.png")
                try:
                    kwargs = {
                        "model": model,
                        "image": img_handle,
                        "prompt": prompt[:32000],
                        "n": 1,
                    }
                    if size != "auto":
                        kwargs["size"] = size
                    result = client.images.edit(**kwargs)
                finally:
                    try:
                        img_handle.close()
                    except Exception:
                        pass

                if not result or not result.data:
                    logger.warning("images.edit model=%s size=%s returned empty data", model, size)
                    continue
                item = result.data[0]
                b64 = getattr(item, "b64_json", None)
                if b64:
                    out = _persist_image_bytes(base64.b64decode(b64), "png")
                    logger.info("images.edit success model=%s size=%s -> %s", model, size, out)
                    return out
                url = getattr(item, "url", None)
                if url:
                    try:
                        r = requests.get(url, timeout=30)
                        r.raise_for_status()
                        out = _persist_image_bytes(r.content, "png")
                        logger.info("images.edit URL success model=%s -> %s", model, out)
                        return out
                    except Exception as dl_exc:
                        logger.warning("Download edit result failed: %s", dl_exc)
                        return url
            except Exception as exc:
                last_err = exc
                logger.warning("images.edit model=%s size=%s failed: %s", model, size, exc)
                # If size is unsupported, try next size; otherwise next model
                continue

    if tmp_path:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass

    # Fallback: one text-only generate (last resort, costs another image call)
    for model in EDIT_MODELS[:1]:
        try:
            result = client.images.generate(
                model=model,
                prompt=prompt[:32000],
                size="1024x1024",
                n=1,
            )
            if not result.data:
                continue
            item = result.data[0]
            b64 = getattr(item, "b64_json", None)
            if b64:
                return _persist_image_bytes(base64.b64decode(b64), "png")
            url = getattr(item, "url", None)
            if url:
                return url
        except Exception as exc:
            last_err = exc
            logger.warning("images.generate model=%s failed: %s", model, exc)

    if last_err:
        logger.error("All image redesign attempts failed: %s", last_err)
    return None


def _redesign_from_url(
    client: OpenAI,
    source_url: str,
    user_prompt: str,
    hotel_context: str | None = None,
) -> str | None:
    try:
        r = requests.get(
            source_url,
            timeout=20,
            headers={"User-Agent": "WishNest-Reimaging/1.0"},
            allow_redirects=True,
        )
        r.raise_for_status()
        raw = r.content
    except Exception as exc:
        logger.warning("Download source photo failed: %s", exc)
        return None
    if not raw or len(raw) < 100:
        return None
    # Skip GPT-4o vision (expensive). Use the user's redesign brief directly.
    context = f"Property: {hotel_context}. " if hotel_context else ""
    edit_prompt = (
        f"Edit this architectural photo. {context}"
        f"{user_prompt} "
        "Keep the same camera angle and overall structure; improve materials, "
        "lighting, and finishes. Photorealistic hospitality architecture photography."
    )
    return _edit_image_with_prompt(client, raw, edit_prompt)


def _redesign_from_b64(
    client: OpenAI,
    image_b64: str,
    user_prompt: str,
    hotel_context: str | None = None,
) -> str | None:
    try:
        raw = base64.b64decode(image_b64)
    except Exception as exc:
        logger.warning("Invalid base64 image: %s", exc)
        return None
    context = f"Property: {hotel_context}. " if hotel_context else ""
    edit_prompt = (
        f"Edit this architectural photo. {context}"
        f"{user_prompt} "
        "Keep the same camera angle and overall structure; improve materials, "
        "lighting, and finishes. Photorealistic hospitality architecture photography."
    )
    return _edit_image_with_prompt(client, raw, edit_prompt)


def _generate_article_package(
    client: OpenAI,
    *,
    hotel_name: str | None,
    user_prompt: str,
    source_mode: str,
    redesign_notes: list[str],
    listing: PropertyListing | None,
) -> dict[str, Any]:
    """
    Produce a WishNest-style article JSON package about the reimagined design.
    """
    property_line = hotel_name or "the uploaded property"
    location = (listing.address if listing else None) or ""
    rating_line = ""
    if listing and listing.rating:
        rating_line = f"Current Google rating: {listing.rating}/5"
        if listing.review_count:
            rating_line += f" ({listing.review_count} reviews)."

    notes_block = "\n".join(f"- {n}" for n in redesign_notes[:8]) or "- Design upgrades applied per brief."

    system = """You are the Senior Editor at WishNest (Hospitality · Architecture · Second Home Intelligence).
Produce a complete, publication-ready article package as a single JSON object.
Respond with ONLY valid JSON — no markdown fences, no commentary.

Required JSON shape:
{
  "headline": string,
  "subtitle": string,
  "full_article": string (700-1000 words, semantic HTML: <h2>, <h3>, <p>, <ul>),
  "executive_summary": string (2-3 sentences),
  "seo_title": string (50-60 characters),
  "meta_description": string (150-160 characters),
  "focus_keyword": string,
  "keywords": [string, ...],
  "captions": [string, ...] (one per redesigned image, 15-25 words editorial),
  "alt_text": [string, ...] (one per redesigned image, 8-15 words),
  "image_credits": [string, ...],
  "pull_quotes": [string, string],
  "key_takeaways": [string, string, string],
  "wishnest_verdict": string (1-2 elegant sentences),
  "best_for": [string, ...],
  "not_ideal_for": [string, ...],
  "architecture_grade": "A+"|"A"|"A-"|"B+"|"B"|"B-"|"C+"|"C"|"C-"|"D+"|"D",
  "landscape_grade": same,
  "connectivity_grade": same,
  "delight_grade": same,
  "eat_explore_grade": same,
  "architecture_score": number 1-10,
  "landscape_score": number 1-10,
  "connectivity_score": number 1-10,
  "delight_score": number 1-10,
  "eat_explore_score": number 1-10,
  "linkedin_variations": [string, string, string],
  "facebook_variations": [string, string],
  "twitter_thread": [string, ...],
  "newsletter_summary": string,
  "suggested_hashtags": [string, ...],
  "cta": string,
  "space_readings": [
    {
      "title": string (e.g. "Arrival & exterior", "Guest room", "Pool & outdoor"),
      "before_text": string (2-4 sentences: what the existing photo shows — honest, specific),
      "after_text": string (2-4 sentences: what the redesign concept changes and why it matters)
    }
  ]
}

Tone: independent, design-literate, precise. This is a REIMAGINED design concept piece.
Write space_readings for EVERY before/after pair (same count as image pairs when possible).
Each before_text explains the EXISTING condition photo; each after_text explains the REDESIGN of that same space.
Also fill ABCDE scores (numeric 1-10 first, then letters). A+ is rare. Include best_for and not_ideal_for.
Never invent fake awards or false claims about the real property."""

    user_msg = f"""Property / subject: {property_line}
Location context: {location}
{rating_line}
Source mode: {source_mode}
User redesign brief: {user_prompt}

Design upgrades applied:
{notes_block}

Write the full WishNest article package about this reimagined design concept.
Category is "reimagined". Frame it as design intelligence / what this space could become.
Include  the number of captions/alt_text equal to the number of redesign notes above.
"""

    resp = client.chat.completions.create(
        model=ARTICLE_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_msg},
        ],
        response_format={"type": "json_object"},
        temperature=0.5,
        max_tokens=4000,
    )
    import json

    raw = resp.choices[0].message.content or "{}"
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.error("Failed to parse article JSON from OpenAI")
        return {
            "headline": f"Reimagined: {property_line}",
            "subtitle": user_prompt[:120],
            "full_article": f"<p>A design reimagining of {property_line} guided by: {user_prompt}</p>",
            "executive_summary": f"Design concept for {property_line}.",
            "seo_title": f"Reimagined Design — {property_line}"[:60],
            "meta_description": f"WishNest reimagines {property_line} with a refined design concept."[:160],
            "focus_keyword": property_line,
            "keywords": [property_line, "reimagined design", "hospitality architecture"],
            "captions": [],
            "alt_text": [],
            "image_credits": ["WishNest Reimaging Studio · AI-assisted concept"],
            "key_takeaways": [],
            "wishnest_verdict": "A compelling design direction worth exploring.",
        }



def _normalise_grade_value(raw):
    """Map LLM grade strings to Grade enum members (or None)."""
    if raw is None:
        return None
    if isinstance(raw, Grade):
        return raw
    s = str(raw).strip()
    if not s:
        return None
    valid = {
        "A+": Grade.a_plus, "A": Grade.a, "A-": Grade.a_minus,
        "B+": Grade.b_plus, "B": Grade.b, "B-": Grade.b_minus,
        "C+": Grade.c_plus, "C": Grade.c, "C-": Grade.c_minus,
        "D+": Grade.d_plus, "D": Grade.d,
    }
    if s in valid:
        return valid[s]
    key = s.lower().replace(" ", "").replace("-", "_")
    mapping = {
        "a_plus": Grade.a_plus, "aplus": Grade.a_plus, "a+": Grade.a_plus,
        "a": Grade.a, "a_minus": Grade.a_minus, "aminus": Grade.a_minus, "a-": Grade.a_minus,
        "b_plus": Grade.b_plus, "bplus": Grade.b_plus, "b+": Grade.b_plus,
        "b": Grade.b, "b_minus": Grade.b_minus, "bminus": Grade.b_minus, "b-": Grade.b_minus,
        "c_plus": Grade.c_plus, "cplus": Grade.c_plus, "c+": Grade.c_plus,
        "c": Grade.c, "c_minus": Grade.c_minus, "cminus": Grade.c_minus, "c-": Grade.c_minus,
        "d_plus": Grade.d_plus, "dplus": Grade.d_plus, "d+": Grade.d_plus,
        "d": Grade.d,
    }
    return mapping.get(key)



def _as_str_list(raw: Any, *, max_items: int = 12) -> list[str] | None:
    """Normalize LLM output to a list of strings (never a character-split string)."""
    if raw is None:
        return None
    if isinstance(raw, str):
        s = raw.strip()
        if not s:
            return None
        # Split common delimiters; avoid treating whole sentence as char array
        import re as _re
        parts = [p.strip() for p in _re.split(r"[,;\n]+", s) if p.strip()]
        if len(parts) <= 1 and len(s) > 40:
            return [s]
        return parts[:max_items] or None
    if isinstance(raw, (list, tuple)):
        out: list[str] = []
        for item in raw:
            if item is None:
                continue
            if isinstance(item, str):
                ss = item.strip()
                if ss:
                    out.append(ss)
            else:
                out.append(str(item))
        return out[:max_items] or None
    return [str(raw)]


def _save_as_draft(
    package: dict[str, Any],
    *,
    redesigned_urls: list[str],
    original_urls: list[str],
    hotel_name: str | None,
    listing: PropertyListing | None,
    user_prompt: str,
) -> str:
    """Persist a draft Article and return its UUID string."""
    db = SessionLocal()
    try:
        # Gallery: ALL before then ALL after (do not drop the first before image)
        gallery: list[str] = []
        for u in original_urls or []:
            if u and u not in gallery:
                gallery.append(u)
        for u in redesigned_urls or []:
            if u and u not in gallery:
                gallery.append(u)
        hero = (redesigned_urls[0] if redesigned_urls else None) or (
            original_urls[0] if original_urls else None
        )
        # Section grid must include every image (hero may also appear in header)
        sections = list(gallery) if gallery else None

        n_imgs = max(len(gallery), 1)
        captions = _as_str_list(package.get("captions")) or []
        alt_text = _as_str_list(package.get("alt_text")) or []
        while len(captions) < n_imgs:
            if len(captions) < len(original_urls or []):
                captions.append(f"Before — existing view of {hotel_name or 'the property'}")
            else:
                captions.append(f"After — redesigned concept for {hotel_name or 'property'}")
        while len(alt_text) < n_imgs:
            alt_text.append(f"WishNest reimagined view {len(alt_text)+1}")

        # Strip broken LLM <img>/figures (they use fake src + alt only), then inject real media
        body = package.get("full_article") or ""
        body = re.sub(r"<figure\b[^>]*>.*?</figure>", "", body, flags=re.I | re.S)
        body = re.sub(r"<img\b[^>]*/?>", "", body, flags=re.I)
        body = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", body)  # markdown images
        body = re.sub(r"\n{3,}", "\n\n", body).strip()

        def _img_tag(url: str, alt: str, kind: str, n: int) -> str:
            src = _public_media_url(url)
            return (
                f'<figure class="wishnest-{kind}" data-ba="{kind}">'
                f'<img src="{src}" alt="{alt}" loading="lazy" '
                f'style="max-width:100%;height:auto;border-radius:8px;display:block;margin:0.75rem 0;" />'
                f"<figcaption>{alt}</figcaption></figure>"
            )

        # Pair each before with its after + LLM space reading (fallback prose if missing)
        readings = package.get("space_readings") or []
        if not isinstance(readings, list):
            readings = []
        n_pairs = max(len(original_urls or []), len(redesigned_urls or []), 1)
        inject_parts: list[str] = []
        inject_parts.append(
            "<p><em>WishNest Reimagined™ — paired before / after design reading. "
            "Existing views are from public listing imagery; after views are design concepts.</em></p>"
        )
        for i in range(n_pairs):
            before_u = (original_urls or [None] * n_pairs)[i] if i < len(original_urls or []) else None
            after_u = (redesigned_urls or [None] * n_pairs)[i] if i < len(redesigned_urls or []) else None
            r = readings[i] if i < len(readings) and isinstance(readings[i], dict) else {}
            title = (r.get("title") or f"Space {i+1}").strip()
            before_txt = (r.get("before_text") or r.get("before") or "").strip()
            after_txt = (r.get("after_text") or r.get("after") or "").strip()
            if not before_txt:
                before_txt = (
                    f"The existing condition of this part of {hotel_name or 'the property'} "
                    "as captured in public listing imagery — the baseline for the design reading."
                )
            if not after_txt:
                after_txt = (
                    f"A redesign direction for the same space: refined materials, proportion, "
                    "and hospitality atmosphere aligned with the project brief."
                )
            inject_parts.append(f"<h2>{title}</h2>")
            if before_u:
                inject_parts.append(
                    _img_tag(before_u, f"Before {i+1} — existing condition", "before", i + 1)
                )
            inject_parts.append(f"<h3>Before — existing condition</h3><p>{before_txt}</p>")
            if after_u:
                inject_parts.append(
                    _img_tag(after_u, f"After {i+1} — redesign concept", "after", i + 1)
                )
            inject_parts.append(f"<h3>After — redesign concept</h3><p>{after_txt}</p>")

        inject = "\n".join(inject_parts)
        # Keep remaining editorial body as overall design reading
        if body:
            body = f"{inject}<h2>Design synthesis</h2>{body}"
        else:
            body = inject
        package = {**package, "full_article": body}

        # Also absolute-ise gallery URLs stored on the article row
        original_urls = [_public_media_url(u) for u in (original_urls or []) if u]
        redesigned_urls = [_public_media_url(u) for u in (redesigned_urls or []) if u]
        gallery = []
        for u in original_urls + redesigned_urls:
            if u and u not in gallery:
                gallery.append(u)
        hero = (redesigned_urls[0] if redesigned_urls else None) or (
            original_urls[0] if original_urls else None
        )
        sections = list(gallery) if gallery else None


        # Ensure ABCDE always present for public card
        def _fscore(key: str, default: float = 7.2) -> float:
            v = package.get(key)
            try:
                return float(v)
            except (TypeError, ValueError):
                return default
        for sk, default in (
            ("architecture_score", 7.2),
            ("landscape_score", 7.0),
            ("connectivity_score", 7.4),
            ("delight_score", 7.5),
            ("eat_explore_score", 7.0),
        ):
            package[sk] = _fscore(sk, default)
        try:
            from app.services.research_pipeline import _score_to_grade, _enforce_grade_reality
            _enforce_grade_reality(package)
        except Exception:
            for sk, gk in (
                ("architecture_score", "architecture_grade"),
                ("landscape_score", "landscape_grade"),
                ("connectivity_score", "connectivity_grade"),
                ("delight_score", "delight_grade"),
                ("eat_explore_score", "eat_explore_grade"),
            ):
                if not package.get(gk):
                    package[gk] = "B"
        if not package.get("best_for"):
            package["best_for"] = [
                "owners exploring a design-led repositioning",
                "architects and developers studying intervention options",
            ]
        if not package.get("not_ideal_for"):
            package["not_ideal_for"] = [
                "readers seeking a verified operational stay review only",
            ]

        article = Article(
            article_type=ArticleType.review,  # always review so public ABCDE card shows
            status=ArticleStatus.draft,
            category="reimagined",
            headline=package.get("headline") or f"Reimagined: {hotel_name or 'Design Concept'}",
            subtitle=package.get("subtitle"),
            full_article=package.get("full_article"),
            executive_summary=package.get("executive_summary"),
            pull_quotes=_as_str_list(package.get("pull_quotes")),
            seo_title=package.get("seo_title"),
            meta_description=package.get("meta_description"),
            focus_keyword=package.get("focus_keyword"),
            keywords=_as_str_list(package.get("keywords")),
            image_credits=package.get("image_credits")
            or ["WishNest Reimaging Studio · AI-assisted concept"],
            captions=captions[:n_imgs],
            alt_text=alt_text[:n_imgs],
            hero_image_url=hero,
            section_image_urls=sections or None,
            location=(listing.address if listing else None) or hotel_name,
            best_for=_as_str_list(package.get("best_for")),
            not_ideal_for=_as_str_list(package.get("not_ideal_for")),
            architecture_grade=_normalise_grade_value(package.get("architecture_grade")),
            landscape_grade=_normalise_grade_value(package.get("landscape_grade")),
            connectivity_grade=_normalise_grade_value(package.get("connectivity_grade")),
            delight_grade=_normalise_grade_value(package.get("delight_grade")),
            eat_explore_grade=_normalise_grade_value(package.get("eat_explore_grade")),
            architecture_score=package.get("architecture_score"),
            landscape_score=package.get("landscape_score"),
            connectivity_score=package.get("connectivity_score"),
            delight_score=package.get("delight_score"),
            eat_explore_score=package.get("eat_explore_score"),
            key_takeaways=package.get("key_takeaways"),
            wishnest_verdict=package.get("wishnest_verdict"),
            linkedin_variations=package.get("linkedin_variations"),
            facebook_variations=package.get("facebook_variations"),
            twitter_thread=package.get("twitter_thread"),
            newsletter_summary=package.get("newsletter_summary"),
            suggested_hashtags=package.get("suggested_hashtags"),
            cta=package.get("cta"),
            # Do NOT set place_id — unique index uq_articles_place_id_active
            # blocks a second non-trash article for the same Maps place.
            # Reimaging can produce many concept drafts per property.
            place_id=None,
            property_snapshot={
                "reimaging": True,
                "user_prompt": user_prompt,
                "original_photo_urls": original_urls,
                "redesigned_photo_urls": redesigned_urls,
                "source": "reimaging_studio",
                "maps_place_id": listing.place_id if listing else None,
                "google_rating": listing.rating if listing else None,
                "google_review_count": listing.review_count if listing else None,
            },
        )
        db.add(article)
        try:
            db.commit()
        except Exception:
            db.rollback()
            raise
        db.refresh(article)
        return str(article.id)
    finally:
        db.close()



def _compact_image_url(url: str | None) -> str | None:
    """Avoid multi-MB data URLs in HTTP JSON responses (DB still keeps full value)."""
    if not url:
        return None
    if url.startswith("data:") and len(url) > 2000:
        return None  # client should open Dashboard to view full images
    return url


def rebuild_reimagined_article_body(article: "Article") -> bool:
    """
    Rebuild paired before/after design reading + ensure ABCDE for an existing
    reimaging article (used by dashboard Regenerate Images).
    """
    from app.models.article import Article  # noqa: F401

    snap = article.property_snapshot if isinstance(article.property_snapshot, dict) else {}
    if not snap.get("reimaging") and (article.category or "").lower() != "reimagined":
        return False

    originals = [u for u in (snap.get("original_photo_urls") or []) if u]
    afters = [u for u in (snap.get("redesigned_photo_urls") or []) if u]
    # Fallback: first half section = before, second half = after
    if not originals or not afters:
        sections = list(article.section_image_urls or [])
        if len(sections) >= 2:
            mid = len(sections) // 2
            if not originals:
                originals = sections[:mid]
            if not afters:
                afters = sections[mid:]
    if not originals and not afters:
        return False

    hotel = article.location or (article.headline or "the property")
    prompt = str(snap.get("user_prompt") or "refined hospitality design")
    n_pairs = max(len(originals), len(afters), 1)

    # Ask Grok for space readings + scores (text only)
    readings: list[dict] = []
    package: dict = {}
    try:
        client = _xai_client()
        user = (
            f"Property: {hotel}\nBrief: {prompt}\n"
            f"There are {n_pairs} before/after image pairs.\n"
            "Return JSON only with keys: space_readings (array of "
            "{title, before_text, after_text} length matching pairs), "
            "best_for, not_ideal_for, keywords, architecture_score, landscape_score, "
            "connectivity_score, delight_score, eat_explore_score, "
            "architecture_grade, landscape_grade, connectivity_grade, delight_grade, "
            "eat_explore_grade, executive_summary, wishnest_verdict.\n"
            "before_text = 2-4 sentences on existing condition; after_text = redesign of same space."
        )
        resp = client.chat.completions.create(
            model=os.environ.get("XAI_MODEL", "grok-2-latest"),
            messages=[
                {
                    "role": "system",
                    "content": (
                        "WishNest senior editor. JSON only. ABCDE numeric-first, A+ rare. "
                        "No markdown fences."
                    ),
                },
                {"role": "user", "content": user},
            ],
            temperature=0.4,
        )
        raw = (resp.choices[0].message.content or "").strip()
        if raw.startswith("```"):
            raw = raw.strip("`")
            if raw.lower().startswith("json"):
                raw = raw[4:].lstrip()
        import json as _json
        package = _json.loads(raw)
        readings = package.get("space_readings") or []
    except Exception as e:
        logger.warning("rebuild reimagined LLM failed: %s", e)
        package = {}
        readings = []

    def _img_tag(url: str, alt: str, kind: str) -> str:
        src = _public_media_url(url)
        return (
            f'<figure class="wishnest-{kind}" data-ba="{kind}">'
            f'<img src="{src}" alt="{alt}" loading="lazy" '
            f'style="max-width:100%;height:auto;border-radius:8px;display:block;margin:0.75rem 0;" />'
            f"<figcaption>{alt}</figcaption></figure>"
        )

    parts = [
        "<p><em>WishNest Reimagined™ — paired before / after design reading.</em></p>"
    ]
    for i in range(n_pairs):
        before_u = originals[i] if i < len(originals) else None
        after_u = afters[i] if i < len(afters) else None
        r = readings[i] if i < len(readings) and isinstance(readings[i], dict) else {}
        title = (r.get("title") or f"Space {i+1}").strip()
        before_txt = (r.get("before_text") or "").strip() or (
            f"Existing condition of this area at {hotel}, from public listing imagery."
        )
        after_txt = (r.get("after_text") or "").strip() or (
            f"Redesign concept for the same space: refined materials, light, and hospitality atmosphere."
        )
        parts.append(f"<h2>{title}</h2>")
        if before_u:
            parts.append(_img_tag(before_u, f"Before {i+1} — existing condition", "before"))
        parts.append(f"<h3>Before — existing condition</h3><p>{before_txt}</p>")
        if after_u:
            parts.append(_img_tag(after_u, f"After {i+1} — redesign concept", "after"))
        parts.append(f"<h3>After — redesign concept</h3><p>{after_txt}</p>")

    article.full_article = "\n".join(parts)
    if package.get("executive_summary"):
        article.executive_summary = package["executive_summary"]
    if package.get("wishnest_verdict"):
        article.wishnest_verdict = package["wishnest_verdict"]
    if package.get("best_for"):
        article.best_for = package["best_for"] if isinstance(package["best_for"], list) else [str(package["best_for"])]
    if package.get("not_ideal_for"):
        article.not_ideal_for = (
            package["not_ideal_for"]
            if isinstance(package["not_ideal_for"], list)
            else [str(package["not_ideal_for"])]
        )
    if package.get("keywords"):
        article.keywords = (
            package["keywords"] if isinstance(package["keywords"], list) else [str(package["keywords"])]
        )

    def _fs(k: str, d: float = 7.2) -> float:
        try:
            return float(package.get(k, d))
        except (TypeError, ValueError):
            return d

    article.architecture_score = _fs("architecture_score", 7.2)
    article.landscape_score = _fs("landscape_score", 7.0)
    article.connectivity_score = _fs("connectivity_score", 7.4)
    article.delight_score = _fs("delight_score", 7.5)
    article.eat_explore_score = _fs("eat_explore_score", 7.0)
    try:
        from app.services.research_pipeline import _score_to_grade, _enforce_grade_reality
        raw = {
            "architecture_score": article.architecture_score,
            "landscape_score": article.landscape_score,
            "connectivity_score": article.connectivity_score,
            "delight_score": article.delight_score,
            "eat_explore_score": article.eat_explore_score,
            "headline": article.headline or "",
        }
        _enforce_grade_reality(raw)
        article.architecture_score = raw["architecture_score"]
        article.landscape_score = raw["landscape_score"]
        article.connectivity_score = raw["connectivity_score"]
        article.delight_score = raw["delight_score"]
        article.eat_explore_score = raw["eat_explore_score"]
        article.architecture_grade = _score_to_grade(float(article.architecture_score))
        article.landscape_grade = _score_to_grade(float(article.landscape_score))
        article.connectivity_grade = _score_to_grade(float(article.connectivity_score))
        article.delight_grade = _score_to_grade(float(article.delight_score))
        article.eat_explore_grade = _score_to_grade(float(article.eat_explore_score))
        article.abcde_overall = raw.get("abcde_overall") or _score_to_grade(
            (
                float(article.architecture_score)
                + float(article.landscape_score)
                + float(article.connectivity_score)
                + float(article.delight_score)
                + float(article.eat_explore_score)
            )
            / 5.0
        )
    except Exception:
        article.architecture_grade = package.get("architecture_grade") or "B"
        article.landscape_grade = package.get("landscape_grade") or "B"
        article.connectivity_grade = package.get("connectivity_grade") or "B+"
        article.delight_grade = package.get("delight_grade") or "B+"
        article.eat_explore_grade = package.get("eat_explore_grade") or "B"

    # Keep gallery ordered before then after
    gallery = []
    for u in originals + afters:
        if u and u not in gallery:
            gallery.append(u)
    if gallery:
        article.section_image_urls = gallery
        article.hero_image_url = afters[0] if afters else originals[0]
    if not article.best_for:
        article.best_for = [
            "owners exploring design-led repositioning",
            "architects studying intervention options",
        ]
    if not article.not_ideal_for:
        article.not_ideal_for = ["readers seeking only an operational stay review"]
    if not article.keywords:
        article.keywords = ["reimagined", "hospitality design", str(hotel)[:40]]

    return True



def run_reimaging_hotel(
    hotel_name: str,
    prompt: str,
    photo_urls: list[str] | None = None,
) -> dict[str, Any]:
    """
    Mode A: hotel name + prompt.
    If photo_urls is provided (user-selected), only those are redesigned.
    Otherwise fetches from Google Maps as before.
    """
    client = _client()
    listing, fetched_urls = _fetch_hotel_photos(hotel_name.strip())

    if photo_urls:
        # User picked specific photos — use only those (still cap)
        source_urls = [u for u in photo_urls if u and u.startswith("http")][:MAX_SOURCE_PHOTOS]
    else:
        source_urls = fetched_urls[:MAX_SOURCE_PHOTOS]

    if len(source_urls) < 1:
        raise RuntimeError(
            f"No photos available for “{hotel_name}”. "
            "Fetch photos first and select at least one, or check SERPAPI_KEY."
        )

    redesign_count = min(MAX_REDESIGNED, len(source_urls))

    redesigned_urls: list[str] = []
    redesign_notes: list[str] = []
    hotel_ctx = listing.name if listing else hotel_name

    for i, url in enumerate(source_urls[:redesign_count]):
        try:
            new_url = _redesign_from_url(client, url, prompt, hotel_context=hotel_ctx)
            if new_url:
                redesigned_urls.append(new_url)
                redesign_notes.append(prompt[:200])
            else:
                logger.warning("Redesign returned empty for photo %d", i)
        except Exception as exc:
            logger.warning("Redesign failed for photo %d: %s", i, exc)
            continue

    if not redesigned_urls:
        raise RuntimeError(
            "Image redesign failed for all source photos. "
            "Confirm OPENAI_API_KEY has GPT Image access, then try 1–2 photos."
        )

    package = _generate_article_package(
        client,
        hotel_name=hotel_name,
        user_prompt=prompt,
        source_mode="google_maps_photos",
        redesign_notes=redesign_notes,
        listing=listing,
    )

    article_id = _save_as_draft(
        package,
        redesigned_urls=redesigned_urls,
        original_urls=source_urls,
        hotel_name=hotel_name,
        listing=listing,
        user_prompt=prompt,
    )

    return {
        "article_id": article_id,
        "hotel_name": hotel_name,
        "listing_name": listing.name if listing else hotel_name,
        "google_rating": listing.rating if listing else None,
        "original_photo_urls": source_urls,
        "redesigned_image_urls": redesigned_urls,
        "headline": package.get("headline"),
        "subtitle": package.get("subtitle"),
        "executive_summary": package.get("executive_summary"),
        "wishnest_verdict": package.get("wishnest_verdict"),
        "status": "draft",
        "message": "Draft created. Review and publish from the main Dashboard.",
    }


def run_reimaging_upload(
    prompt: str,
    image_b64_list: list[str],
    hotel_name: str | None = None,
) -> dict[str, Any]:
    """
    Mode B: user-uploaded image(s) + prompt.
    image_b64_list items are raw base64 (no data: prefix).
    """
    if not image_b64_list:
        raise RuntimeError("At least one image is required.")

    client = _client()
    redesigned_urls: list[str] = []
    redesign_notes: list[str] = []

    for i, b64 in enumerate(image_b64_list[:MAX_REDESIGNED]):
        try:
            new_url = _redesign_from_b64(client, b64, prompt, hotel_context=hotel_name)
            if new_url:
                redesigned_urls.append(new_url)
                redesign_notes.append(prompt[:200])
            else:
                logger.warning("Redesign returned empty for upload %d", i)
        except Exception as exc:
            logger.warning("Redesign failed for uploaded image %d: %s", i, exc)
            continue

    if not redesigned_urls:
        raise RuntimeError(
            "Image redesign failed. "
            "Confirm OPENAI_API_KEY has GPT Image access, then try a clearer photo."
        )

    package = _generate_article_package(
        client,
        hotel_name=hotel_name,
        user_prompt=prompt,
        source_mode="user_upload",
        redesign_notes=redesign_notes,
        listing=None,
    )

    article_id = _save_as_draft(
        package,
        redesigned_urls=redesigned_urls,
        original_urls=[],  # originals were uploads; not stored as URLs
        hotel_name=hotel_name,
        listing=None,
        user_prompt=prompt,
    )

    return {
        "article_id": article_id,
        "hotel_name": hotel_name,
        "listing_name": hotel_name,
        "google_rating": None,
        "original_photo_urls": [],
        "redesigned_image_urls": redesigned_urls,
        "headline": package.get("headline"),
        "subtitle": package.get("subtitle"),
        "executive_summary": package.get("executive_summary"),
        "wishnest_verdict": package.get("wishnest_verdict"),
        "status": "draft",
        "message": "Draft created. Review and publish from the main Dashboard.",
    }


def run_reimaging_before_after(
    *,
    hotel_name: str | None,
    notes: str,
    before_images_b64: list[str],
    after_images_b64: list[str],
    before_photo_urls: list[str] | None = None,
) -> dict[str, Any]:
    """
    Manual redesign workflow (no image-generation API):
      Before = Google Maps / source photos (URLs or base64)
      After  = user uploads from ChatGPT (or any tool) redesigns
      Then text-only Grok (xAI) writes the before/after article as draft.
    """
    import json

    if not after_images_b64:
        raise ValueError("At least one AFTER (redesigned) image is required.")

    from urllib.parse import quote

    def _safe_persist_url(url: str) -> str:
        """Download + store in media_blobs; else image-proxy so the article can still render."""
        b64 = _download_image_as_b64(url, timeout=25)
        if b64:
            try:
                return _persist_image_bytes(base64.b64decode(b64), "jpg")
            except Exception as exc:
                logger.warning("Persist before failed, using proxy: %s", exc)
        return f"/api/image-proxy?url={quote(url, safe='')}"

    def _safe_persist_b64(raw: str, ext: str = "png") -> str | None:
        s = raw.split(",", 1)[-1] if raw.startswith("data:") else raw
        try:
            data = base64.b64decode(s)
            if len(data) < 80:
                return None
            return _persist_image_bytes(data, ext)
        except Exception as exc:
            logger.warning("Skip image bytes: %s", exc)
            return None

    original_urls: list[str] = []
    for url in (before_photo_urls or [])[:MAX_SOURCE_PHOTOS]:
        if not url:
            continue
        original_urls.append(_safe_persist_url(url))
    for raw in (before_images_b64 or [])[:MAX_SOURCE_PHOTOS]:
        saved = _safe_persist_b64(raw, "jpg")
        if saved:
            original_urls.append(saved)

    redesigned_urls: list[str] = []
    for raw in after_images_b64[:MAX_SOURCE_PHOTOS]:
        saved = _safe_persist_b64(raw, "png")
        if saved:
            redesigned_urls.append(saved)

    if not redesigned_urls:
        raise ValueError("Could not save any AFTER images.")

    listing = None
    if hotel_name:
        try:
            listing, _ = _fetch_hotel_photos(hotel_name)
        except Exception:
            listing = None

    property_line = (
        (listing.name if listing else None)
        or (hotel_name or "this property")
    )
    user_prompt = (notes or "").strip() or (
        "Compare the existing (before) condition with the redesigned (after) concepts. "
        "Explain what improved for hospitality design, guest experience, and positioning."
    )

    client = _grok_client()
    # Vision: send a couple of before/after pairs as context (text generation only)
    content: list[dict[str, Any]] = [
        {
            "type": "text",
            "text": (
                f"You are WishNest Reimagined editorial. Property: {property_line}.\nEditor notes: {user_prompt}\nImages labeled BEFORE (existing public listing photos) and AFTER (manually redesigned concepts).\nDo NOT invent that our API generated the after images.\nWrite a FULL WishNest-style article as JSON with keys: headline, subtitle, full_article, executive_summary, pull_quotes (array of 2-4 strings), seo_title, meta_description, focus_keyword, keywords (array), captions (array), alt_text (array), key_takeaways (array of 4-6 strings), wishnest_verdict, best_for (array of short phrases), not_ideal_for (array of short phrases), architecture_grade, landscape_grade, connectivity_grade, delight_grade, experience_grade.\nfull_article MUST be semantic HTML only (<h2>, <h3>, <p>, <ul><li>) and at least 650-900 words. Structure: (1) context of the property and place, (2) reading of the BEFORE condition — materials, guest arrival, spatial quality, what feels dated or strong, (3) reading of the AFTER direction — what the redesign is trying to improve for hospitality experience, (4) practical implications for owners/operators, (5) a measured WishNest verdict. Do not include <img> tags in full_article (images are injected by the system). Tone: independent hospitality/architecture intelligence — not a sales brochure."
            ),
        }
    ]
    # Attach up to 2 before + 2 after for vision context
    for i, url in enumerate(original_urls[:2]):
        b64 = None
        if url.startswith("/"):
            # try load from media — skip if remote only
            pass
        # Prefer raw from request; if we only have URL, download
        b64 = _download_image_as_b64(url) if url.startswith("http") else None
        if b64:
            content.append({"type": "text", "text": f"BEFORE image {i+1}:"})
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
            })
    for i, raw in enumerate(after_images_b64[:2]):
        s = raw.split(",", 1)[-1] if raw.startswith("data:") else raw
        content.append({"type": "text", "text": f"AFTER image {i+1}:"})
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{s}"},
        })

    try:
        resp = client.chat.completions.create(
            model=_grok_model(),
            messages=[{"role": "user", "content": content}],
            # json_object not always supported on all Grok models — parse robustly
            temperature=0.45,
            max_tokens=4500,
        )
        raw = (resp.choices[0].message.content or "").strip()
        if raw.startswith("```"):
            raw = raw.strip("`")
            if raw.lower().startswith("json"):
                raw = raw[4:].lstrip()
            if raw.endswith("```"):
                raw = raw[:-3].rstrip()
        package = json.loads(raw or "{}")
    except Exception as exc:
        logger.warning("Before/after article Grok failed: %s", exc)
        package = {
            "headline": f"Reimagined: {property_line}",
            "subtitle": "Before & after design study",
            "full_article": (
                f"<p>WishNest explores a before-and-after design direction for {property_line}.</p>"
                f"<p><strong>Notes:</strong> {user_prompt}</p>"
            ),
            "executive_summary": f"Before/after concept for {property_line}.",
            "seo_title": f"Reimagined — {property_line}"[:60],
            "meta_description": f"Before and after design study of {property_line}."[:160],
            "focus_keyword": property_line,
            "keywords": [property_line, "reimagined", "before after"],
            "captions": [],
            "alt_text": [],
            "wishnest_verdict": "A clear before/after design narrative for review.",
        }

    # Ensure full_article is substantial; expand if the model returned a stub
    body = (package.get("full_article") or "").strip()
    plain_len = len(__import__("re").sub(r"<[^>]+>", " ", body))
    if plain_len < 400:
        notes = user_prompt or "a refined hospitality design direction"
        package["full_article"] = f"""
<h2>Context</h2>
<p>WishNest Reimagined looks at {property_line} as a live hospitality setting rather than a static photograph.
The before images record how the property presents today. The after images explore a design direction that could
strengthen arrival, material quality, and guest experience without pretending the work is already built.</p>
<h2>Before — what the existing condition communicates</h2>
<p>Public listing photography typically emphasises occupancy and amenity. Reading those frames carefully still
reveals useful signals: proportion of rooms, quality of finishes, outdoor edges, and whether the architecture
feels specific to its place or interchangeable. For {property_line}, the before set is the baseline against which
any redesign should be judged.</p>
<h2>After — the proposed design direction</h2>
<p>The after concepts respond to editor notes: {notes}. The intent is not cosmetic novelty for its own sake, but
clearer thresholds, calmer material palettes, better daylight hierarchy, and outdoor spaces that feel owned by the
guest rather than left over. Each after frame should be read as a hypothesis — what this property could become if
design investment tracked hospitality performance.</p>
<h2>Implications for operators</h2>
<p>Owners evaluating a repositioning should treat these images as a conversation starter with architects and
operators: which rooms underperform, which edges of the site are underused, and where a modest intervention would
change the guest narrative more than a full rebuild. WishNest does not guarantee construction outcomes or revenue;
the value is a sharper brief before money is spent.</p>
<h2>WishNest verdict</h2>
<p>Used honestly, before-and-after studies help separate taste from strategy. The strongest next step is a focused
site brief — which spaces matter most, what the guest should feel in the first ten minutes, and which upgrades are
worth sequencing first.</p>
""".strip()
        if not package.get("executive_summary"):
            package["executive_summary"] = (
                f"A before-and-after design reading of {property_line}, pairing existing listing imagery "
                "with redesign concepts to clarify hospitality potential."
            )
        if not package.get("wishnest_verdict"):
            package["wishnest_verdict"] = (
                "A useful design brief in visual form — not a construction document, but a clearer conversation starter."
            )

    article_id = _save_as_draft(
        package,
        redesigned_urls=redesigned_urls,
        original_urls=original_urls,
        hotel_name=hotel_name,
        listing=listing,
        user_prompt=user_prompt,
    )
    return {
        "article_id": article_id,
        "hotel_name": hotel_name,
        "listing_name": listing.name if listing else hotel_name,
        "google_rating": listing.rating if listing else None,
        "original_photo_urls": original_urls,
        "redesigned_image_urls": redesigned_urls,
        "headline": package.get("headline"),
        "subtitle": package.get("subtitle"),
        "executive_summary": package.get("executive_summary"),
        "wishnest_verdict": package.get("wishnest_verdict"),
        "status": "draft",
        "message": "Draft saved — before (source) + after (uploaded). No image-generation API used.",
    }
