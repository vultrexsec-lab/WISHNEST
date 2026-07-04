"""
AI image generation for WishNest articles using DALL-E 3.

DALL-E 3 returns a hosted HTTPS URL (not base64), so no storage infrastructure
is needed and the DB column stays a normal-sized string. URLs are valid for
~1 hour — for permanent storage, download and re-host on a CDN separately.

Generates per article:
  - one hero image  (1792×1024 landscape — ideal cover/hero)
  - up to 2 section images (1024×1024 square)

Image generation is wrapped in try/except so a failure never crashes the pipeline.
"""
import logging

from openai import OpenAI

from app.config import get_settings

logger = logging.getLogger("wishnest.image_service")

IMAGE_MODEL = "dall-e-3"
HERO_SIZE = "1792x1024"     # landscape, best for hero/cover
SECTION_SIZE = "1024x1024"  # square, best for in-article sections
IMAGE_QUALITY = "standard"  # "standard" or "hd"; hd costs 2x


def _build_prompt(
    headline: str,
    focus_keyword: str | None,
    location: str | None,
    article_type: str,
    angle: str,
) -> str:
    """
    Construct a strict professional editorial photography prompt.
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
        f"Professional {style_base}. "
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

    Uses DALL-E 3 which returns hosted HTTPS URLs — no base64, no storage needed.
    Never raises — failures are logged and that slot returns None/skipped so the
    pipeline always persists the article even without images.
    """
    settings = get_settings()
    if not settings.openai_api_key:
        logger.warning("OPENAI_API_KEY not configured; skipping image generation.")
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
        url = hero_result.data[0].url
        if url:
            hero_url = url
            logger.info("Hero image generated for %r", headline[:50])
        else:
            logger.warning("Hero image: DALL-E 3 returned no URL for %r", headline[:50])
    except Exception as exc:  # noqa: BLE001
        logger.warning("Hero image generation failed for %r: %s", headline[:50], exc)

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
            url = result.data[0].url
            if url:
                section_urls.append(url)
            else:
                logger.warning("Section image: no URL returned for %r", headline[:50])
        except Exception as exc:  # noqa: BLE001
            logger.warning("Section image generation failed for %r: %s", headline[:50], exc)

    return hero_url, section_urls
