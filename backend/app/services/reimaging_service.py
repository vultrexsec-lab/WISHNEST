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
MAX_REDESIGNED = 6

IMAGE_GEN_MODEL = "gpt-image-1"
VISION_MODEL = "gpt-4o"
ARTICLE_MODEL = "gpt-4o-mini"


def _client() -> OpenAI:
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured.")
    return OpenAI(api_key=settings.openai_api_key)


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

EDIT_MODELS = (
    IMAGE_GEN_MODEL,
    "gpt-image-1",
    "gpt-image-1-mini",
    "gpt-image-1.5",
    "gpt-image-2",
)


def _ensure_media_dir() -> Path:
    _MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    return _MEDIA_DIR


def _persist_image_bytes(data: bytes, ext: str = "png") -> str:
    folder = _ensure_media_dir()
    name = f"{uuid.uuid4().hex}.{ext.lstrip('.')}"
    (folder / name).write_bytes(data)
    return f"{_MEDIA_URL_PREFIX}/{name}"


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
    for model in EDIT_MODELS:
        if model in seen:
            continue
        seen.add(model)
        try:
            result = client.images.edit(
                model=model,
                image=_bytes_to_file(image_bytes, "source.png"),
                prompt=prompt[:32000],
                size="1536x1024",
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
                try:
                    r = requests.get(url, timeout=30)
                    r.raise_for_status()
                    return _persist_image_bytes(r.content, "png")
                except Exception as dl_exc:
                    logger.warning("Download edit result failed: %s", dl_exc)
                    return url
        except Exception as exc:
            last_err = exc
            logger.warning("images.edit model=%s failed: %s", model, exc)

    # Fallback: generate without reference
    for model in EDIT_MODELS:
        try:
            result = client.images.generate(
                model=model,
                prompt=prompt[:32000],
                size="1536x1024",
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
    b64 = base64.b64encode(raw).decode("ascii")
    edit_prompt = _vision_redesign_prompt(client, b64, user_prompt, hotel_context)
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
    edit_prompt = _vision_redesign_prompt(client, image_b64, user_prompt, hotel_context)
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
  "cta": string
}

Tone: independent, design-literate, precise. This is a REIMAGINED design concept piece —
celebrate the design intelligence of the upgrades while remaining grounded and editorial.
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
        hero = redesigned_urls[0] if redesigned_urls else (original_urls[0] if original_urls else None)
        sections = redesigned_urls[1:] if len(redesigned_urls) > 1 else redesigned_urls

        # Pad captions / alt_text to match image count
        captions = list(package.get("captions") or [])
        alt_text = list(package.get("alt_text") or [])
        while len(captions) < len(redesigned_urls):
            captions.append(f"Reimagined view of {hotel_name or 'the property'}")
        while len(alt_text) < len(redesigned_urls):
            alt_text.append(f"Reimagined design concept for {hotel_name or 'property'}")

        article = Article(
            article_type=ArticleType.review if hotel_name else ArticleType.standard,
            status=ArticleStatus.draft,
            category="reimagined",
            headline=package.get("headline") or f"Reimagined: {hotel_name or 'Design Concept'}",
            subtitle=package.get("subtitle"),
            full_article=package.get("full_article"),
            executive_summary=package.get("executive_summary"),
            pull_quotes=package.get("pull_quotes"),
            seo_title=package.get("seo_title"),
            meta_description=package.get("meta_description"),
            focus_keyword=package.get("focus_keyword"),
            keywords=package.get("keywords"),
            image_credits=package.get("image_credits")
            or ["WishNest Reimaging Studio · AI-assisted concept"],
            captions=captions[: len(redesigned_urls) or 1],
            alt_text=alt_text[: len(redesigned_urls) or 1],
            hero_image_url=hero,
            section_image_urls=sections or None,
            location=(listing.address if listing else None) or hotel_name,
            best_for=package.get("best_for"),
            not_ideal_for=package.get("not_ideal_for"),
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
