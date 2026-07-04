"""
AI image generation for WishNest articles.

IMPORTANT: this OpenAI account/API key does not have access to the legacy
"dall-e-3" model (confirmed via a live API call — OpenAI returns
"The model 'dall-e-3' does not exist" for this key). The key DOES have
access to the newer "gpt-image-1" family, so that is what we use.

Unlike DALL-E 3, gpt-image-1 does not return a hosted URL — it returns the
image as base64 (b64_json). We decode it and save it to a local static
directory served by the FastAPI app at /api/static/images/<filename>.png,
then store that URL in the DB. This also means images no longer expire
after ~1 hour like DALL-E 3's hosted URLs did.

Generates per article:
  - one hero image  (1536x1024 landscape — ideal cover/hero)
  - up to 2 section images (1024x1024 square)

Image generation is wrapped in try/except so a failure never crashes the
pipeline, but every failure is logged AND printed to the terminal with the
exact exception so it's immediately visible in the backend console.
"""
import base64
import logging
import uuid
from pathlib import Path

from openai import OpenAI

from app.config import get_settings

logger = logging.getLogger("wishnest.image_service")

IMAGE_MODEL = "gpt-image-1"
HERO_SIZE = "1536x1024"    # landscape, best for hero/cover
SECTION_SIZE = "1024x1024"  # square, best for in-article sections
IMAGE_QUALITY = "high"     # gpt-image-1: "low" | "medium" | "high" | "auto"

STATIC_IMAGES_DIR = Path(__file__).resolve().parent.parent / "static" / "images"
STATIC_IMAGES_URL_PREFIX = "/api/static/images"


def _log_failure(stage: str, headline: str, exc: Exception) -> None:
    """Log AND print the exact exception so it's impossible to miss in the terminal."""
    message = f"[image_service] {stage} FAILED for {headline[:60]!r}: {type(exc).__name__}: {exc}"
    logger.error(message, exc_info=True)
    print(message, flush=True)


def _save_base64_image(b64_json: str) -> str:
    """Decode base64 PNG data, save it to the static images dir, return its served URL."""
    STATIC_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}.png"
    file_path = STATIC_IMAGES_DIR / filename
    file_path.write_bytes(base64.b64decode(b64_json))
    return f"{STATIC_IMAGES_URL_PREFIX}/{filename}"


def _build_prompt(
    headline: str,
    focus_keyword: str | None,
    location: str | None,
    article_type: str,
    angle: str,
) -> str:
    """
    Construct a strict, luxury/architectural editorial photography prompt.
    Uses focus_keyword > location > headline for subject grounding.
    """
    subject_parts: list[str] = []
    if focus_keyword:
        subject_parts.append(focus_keyword)
    if location:
        subject_parts.append(f"in {location}")
    if not subject_parts:
        subject_parts.append(headline[:80])

    subject = ", ".join(subject_parts)

    style_base = (
        "high-end architectural photography, precise material and detail shots, "
        "property review style"
        if article_type == "review"
        else "editorial travel and luxury hospitality photography, destination storytelling style"
    )

    return (
        f"High-end architectural photography, luxury hospitality style, 8k resolution, "
        f"realistic lighting. Professional {style_base}. "
        f"Subject: {subject}. "
        f"{angle} "
        f"Technical specs: 8K resolution, photorealistic, natural golden-hour or diffused daylight, "
        f"warm elegant tones, shallow depth of field, magazine-quality composition. "
        f"Aesthetic: luxury boutique hospitality, architect-designed space, refined minimalism. "
        f"Strict exclusions: no text, no watermarks, no logos, no people, no digital artifacts, "
        f"no oversaturated filters."
    )


def generate_article_images(
    headline: str,
    focus_keyword: str | None = None,
    location: str | None = None,
    article_type: str = "standard",
) -> tuple[str | None, list[str]]:
    """
    Returns (hero_image_url, section_image_urls).

    Uses gpt-image-1 (this account has no dall-e-3 access). Images are decoded
    from base64 and saved locally, served at /api/static/images/<file>.png.
    Never raises — failures are logged/printed and that slot returns
    None/skipped so the pipeline always persists the article even without images.
    """
    settings = get_settings()
    if not settings.openai_api_key:
        message = "[image_service] OPENAI_API_KEY / CHATGPT_API_KEY not configured; skipping image generation."
        logger.error(message)
        print(message, flush=True)
        return None, []

    client = OpenAI(api_key=settings.openai_api_key)

    # ── Hero image (landscape) ────────────────────────────────────────────────
    hero_url: str | None = None
    hero_prompt = _build_prompt(
        headline, focus_keyword, location, article_type,
        angle=(
            "Wide establishing shot capturing the full property or destination as a cinematic "
            "hero cover image — grand scale, strong horizon line, immersive sense of place."
        ),
    )
    try:
        hero_result = client.images.generate(
            model=IMAGE_MODEL,
            prompt=hero_prompt,
            size=HERO_SIZE,
            quality=IMAGE_QUALITY,
            n=1,
        )
        b64 = hero_result.data[0].b64_json
        if b64:
            hero_url = _save_base64_image(b64)
            logger.info("Hero image generated for %r -> %s", headline[:50], hero_url)
        else:
            print(f"[image_service] Hero image: no b64_json returned for {headline[:50]!r}", flush=True)
    except Exception as exc:  # noqa: BLE001
        _log_failure("Hero image generation", headline, exc)

    # ── Section images (square) ───────────────────────────────────────────────
    section_urls: list[str] = []
    section_angles = [
        (
            "Close-up detail shot highlighting architectural materials, craftsmanship, and texture — "
            "raw stone, teak joinery, hand-plastered walls, or bespoke lighting fixture. "
            "Macro precision, editorial still-life quality."
        ),
        (
            "Interior or curated landscape view conveying the guest experience and atmosphere — "
            "a suite terrace with valley views, a candlelit dining setup, or a plunge pool "
            "reflecting mountain light. Intimate, aspirational, evocative."
        ),
    ]
    for angle in section_angles:
        prompt = _build_prompt(headline, focus_keyword, location, article_type, angle)
        try:
            result = client.images.generate(
                model=IMAGE_MODEL,
                prompt=prompt,
                size=SECTION_SIZE,
                quality=IMAGE_QUALITY,
                n=1,
            )
            b64 = result.data[0].b64_json
            if b64:
                section_urls.append(_save_base64_image(b64))
            else:
                print(f"[image_service] Section image: no b64_json returned for {headline[:50]!r}", flush=True)
        except Exception as exc:  # noqa: BLE001
            _log_failure("Section image generation", headline, exc)

    return hero_url, section_urls
