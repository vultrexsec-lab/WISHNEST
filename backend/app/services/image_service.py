"""
AI image generation for WishNest articles.

Uses the free Pollinations.ai API — no API key required, zero cost.
Images are served directly as URLs in the format:
  https://image.pollinations.ai/prompt/{encoded_prompt}?width=W&height=H&seed=N&nologo=true

The `seed` parameter is derived from a hash of each article's headline +
focus_keyword + location, guaranteeing a unique image per article even when
two prompts share similar wording.

No local file storage, no base64 decoding, no OpenAI billing.
"""
import hashlib
import logging
import urllib.parse

logger = logging.getLogger("wishnest.image_service")


def _article_seed(headline: str, focus_keyword: str | None, location: str | None) -> int:
    """
    Deterministic per-article seed — same article always gets the same image,
    different articles always get different images.
    Maps a 32-bit unsigned integer from the MD5 of the key fields.
    """
    key = f"{headline}|{focus_keyword or ''}|{location or ''}".encode()
    digest = hashlib.md5(key).hexdigest()
    return int(digest[:8], 16)  # 0 – 4 294 967 295


def _build_prompt(
    headline: str,
    focus_keyword: str | None,
    location: str | None,
    article_type: str,
    angle: str,
) -> str:
    """
    Construct a luxury/architectural editorial photography prompt.
    Uses focus_keyword > location > headline for subject grounding.
    The headline is always included so every article gets a meaningfully
    distinct subject even when category and location are similar.
    """
    subject_parts: list[str] = []
    if focus_keyword:
        subject_parts.append(focus_keyword)
    if location:
        subject_parts.append(f"in {location}")
    # Always anchor to the headline for uniqueness
    subject_parts.append(f"— {headline[:80]}")

    subject = ", ".join(subject_parts)

    style_base = (
        "high-end architectural photography, precise material and detail shots, "
        "property review style"
        if article_type == "review"
        else "editorial travel and luxury hospitality photography, destination storytelling style"
    )

    return (
        f"High-end architectural photography, luxury hospitality style, 8K resolution, "
        f"realistic lighting. Professional {style_base}. "
        f"Subject: {subject}. "
        f"{angle} "
        f"Technical specs: 8K resolution, photorealistic, natural golden-hour or diffused daylight, "
        f"warm elegant tones, shallow depth of field, magazine-quality composition. "
        f"Aesthetic: luxury boutique hospitality, architect-designed space, refined minimalism. "
        f"Strict exclusions: no text, no watermarks, no logos, no people, no digital artifacts, "
        f"no oversaturated filters."
    )


def _pollinations_url(
    prompt: str,
    seed: int,
    width: int = 1024,
    height: int = 576,
) -> str:
    """Build a Pollinations.ai image URL from a prompt string and a numeric seed."""
    safe_prompt = urllib.parse.quote(prompt)
    return (
        f"https://image.pollinations.ai/prompt/{safe_prompt}"
        f"?width={width}&height={height}&seed={seed}&nologo=true&private=true"
    )


def generate_article_images(
    headline: str,
    focus_keyword: str | None = None,
    location: str | None = None,
    article_type: str = "standard",
) -> tuple[str | None, list[str]]:
    """
    Returns (hero_image_url, section_image_urls).

    Generates Pollinations.ai URLs — free, no API key, instant (no network call
    at generation time; the browser fetches the image directly when rendered).

    Each article receives a unique seed so images are article-specific even when
    topics or categories overlap. Never raises.
    """
    seed = _article_seed(headline, focus_keyword, location)

    try:
        hero_prompt = _build_prompt(
            headline, focus_keyword, location, article_type,
            angle=(
                "Wide establishing shot capturing the full property or destination as a cinematic "
                "hero cover image — grand scale, strong horizon line, immersive sense of place."
            ),
        )
        hero_url = _pollinations_url(hero_prompt, seed=seed, width=1280, height=720)
        logger.info("Hero image URL built for %r (seed=%d)", headline[:50], seed)
    except Exception as exc:  # noqa: BLE001
        logger.error("Hero image URL build failed for %r: %s", headline[:50], exc)
        hero_url = None

    section_urls: list[str] = []
    section_angles = [
        (
            "Close-up detail shot highlighting architectural materials, craftsmanship, and texture — "
            "raw stone, teak joinery, hand-plastered walls, or bespoke lighting fixture. "
            "Macro precision, editorial still-life quality.",
            seed + 1,  # offset seed so section images also differ from each other
        ),
        (
            "Interior or curated landscape view conveying the guest experience and atmosphere — "
            "a suite terrace with valley views, a candlelit dining setup, or a plunge pool "
            "reflecting mountain light. Intimate, aspirational, evocative.",
            seed + 2,
        ),
    ]
    for angle, section_seed in section_angles:
        try:
            prompt = _build_prompt(headline, focus_keyword, location, article_type, angle)
            url = _pollinations_url(prompt, seed=section_seed, width=1024, height=576)
            section_urls.append(url)
        except Exception as exc:  # noqa: BLE001
            logger.error("Section image URL build failed for %r: %s", headline[:50], exc)

    return hero_url, section_urls
