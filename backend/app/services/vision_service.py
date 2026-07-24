"""
Google Cloud Vision API integration for WishNest's Automated Visual
Verification Pipeline.

Workflow per image:
  1. Send image URL to Vision API (LABEL_DETECTION, TEXT_DETECTION,
     WEB_DETECTION, OBJECT_LOCALIZATION).
  2. Extract labels, objects, OCR text, and web entities.
  3. Validate that the detected content matches the intended section topic.
     Images whose labels share NO significant tokens with the section topic
     are automatically rejected (e.g. an indoor restaurant image rejected
     when the section is about "Outdoor Pool & Gardens").
  4. Return a VisionResult with full metadata so the LLM can use it as
     grounded context when writing the section article.

Requires the environment variable GOOGLE_CLOUD_VISION_API_KEY.
If the key is absent, validation is skipped and all images are accepted
(non-blocking degradation).
"""
from __future__ import annotations

import base64
import logging
import re
from dataclasses import dataclass, field
from typing import Optional

import requests

from app.config import get_settings

logger = logging.getLogger("wishnest.vision_service")

_VISION_ENDPOINT = "https://vision.googleapis.com/v1/images:annotate"
_REQUEST_TIMEOUT = 12  # seconds


# ---------------------------------------------------------------------------
# Topic → keyword validation mapping
# ---------------------------------------------------------------------------
# Maps common section topics to sets of keywords we expect to appear in
# Vision API label / object output.  If NONE of the expected keywords appear
# in the detected labels, the image is rejected as off-topic.
# Keys are lower-cased; partial substring matching is used.

_TOPIC_KEYWORD_MAP: dict[str, list[str]] = {
    # Outdoor / nature sections
    "pool": ["pool", "swimming", "water", "outdoor", "aquatic", "blue"],
    "garden": ["garden", "plant", "flower", "nature", "outdoor", "green", "lawn", "landscape"],
    "outdoor": ["outdoor", "nature", "sky", "garden", "landscape", "exterior", "terrace", "yard"],
    "terrace": ["terrace", "balcony", "outdoor", "patio", "rooftop", "view"],
    "landscape": ["landscape", "nature", "mountain", "valley", "forest", "scenic", "countryside"],
    "beach": ["beach", "ocean", "sea", "water", "sand", "coast", "shore", "wave"],
    "mountain": ["mountain", "hill", "peak", "highland", "scenic", "nature", "sky"],
    "forest": ["forest", "tree", "wood", "nature", "green", "jungle", "wildlife"],
    # Indoor / architectural sections
    "room": ["room", "interior", "bed", "furniture", "indoor", "suite", "bedroom"],
    "bedroom": ["bedroom", "bed", "pillow", "room", "interior", "sleep"],
    "bathroom": ["bathroom", "bath", "shower", "sink", "toilet", "tile"],
    "lobby": ["lobby", "hotel", "interior", "reception", "hall", "foyer"],
    "restaurant": ["restaurant", "dining", "food", "table", "meal", "cuisine", "cafe", "dish", "plate"],
    # STRICT food/dining entries — require a positive food signal
    "culinary": ["food", "dish", "meal", "restaurant", "dining", "cuisine", "plate", "chef",
                 "kitchen", "beverage", "cooking", "breakfast", "lunch", "dinner"],
    "dining": ["dining", "restaurant", "food", "meal", "plate", "cuisine", "dish", "chef"],
    "food": ["food", "dish", "meal", "cuisine", "plate", "restaurant", "beverage", "cooking"],
    "local cuisine": ["food", "dish", "cuisine", "meal", "cooking", "restaurant", "local"],
    "eat": ["food", "dish", "meal", "restaurant", "dining", "plate", "cuisine"],
    "delights": ["food", "dish", "meal", "cuisine", "plate", "dining", "restaurant"],
    "kitchen": ["kitchen", "cooking", "food", "stove", "appliance", "culinary", "chef", "dish"],
    "spa": ["spa", "wellness", "massage", "relax", "treatment", "pool", "sauna"],
    "gym": ["gym", "fitness", "exercise", "equipment", "sport", "health"],
    # Architectural / exterior
    "architecture": ["architecture", "building", "structure", "design", "facade", "exterior"],
    "exterior": ["exterior", "building", "facade", "architecture", "outdoor"],
    "view": ["view", "scenic", "panorama", "landscape", "sky", "horizon"],
    # Location types
    "hotel": ["hotel", "resort", "building", "architecture", "room", "property"],
    "resort": ["resort", "hotel", "luxury", "pool", "outdoor", "property"],
    "property": ["property", "building", "estate", "real estate", "architecture"],
    "heritage": ["heritage", "historical", "old", "ancient", "monument", "architecture"],
}

# Negative labels that always reject an image regardless of section topic
_REJECT_LABELS: frozenset[str] = frozenset([
    "map", "menu", "plumbing", "pipe", "wiring", "circuit",
    "diagram", "chart", "graph", "logo", "advertisement", "banner",
    "screenshot", "document", "text", "page", "book",
    "toilet installation", "plumber",
])

# ---------------------------------------------------------------------------
# Strict culinary / dining enforcement
# ---------------------------------------------------------------------------
# When a section topic mentions any of these triggers, the image MUST carry a
# positive food signal. A mountain, flower valley, or generic nature shot is
# NEVER acceptable under a food heading — even if the topic text contains a
# word like "delights" or "explore" that technically overlaps with outdoor labels.

_CULINARY_TOPIC_TRIGGERS: frozenset[str] = frozenset({
    "culinary", "dining", "food", "cuisine", "local cuisine",
    "restaurant", "breakfast", "meal", "meals", "eat", "explore",
    "gastro", "gastronomy", "beverage", "cafe", "chef", "delights",
    "flavours", "flavors", "taste", "tasting", "kitchen",
})

# Labels from Vision API that positively confirm food/dining content
_FOOD_POSITIVE_LABELS: frozenset[str] = frozenset({
    "food", "dish", "meal", "cuisine", "restaurant", "dining room",
    "breakfast", "lunch", "dinner", "kitchen", "café", "cafe",
    "buffet", "tableware", "plate", "bowl", "beverage", "drink",
    "food and drink", "cutlery", "brunch", "baking", "chef", "dessert",
    "bakery", "bar", "coffee", "tea", "cocktail", "appetizer",
    "salad", "soup", "cooking", "snack", "spice", "ingredient",
    "menu", "street food", "delicacy", "delicacies", "culinary",
    "dining", "gourmet", "gastronomy",
})

# Labels that strongly indicate NON-food (nature/outdoor) content — these
# should HARD-REJECT an image for any culinary section
_NATURE_LABELS_REJECT_CULINARY: frozenset[str] = frozenset({
    "mountain", "mountains", "valley", "forest", "tree", "trees",
    "flower", "flowers", "meadow", "field", "hill", "hills",
    "landscape", "nature", "wilderness", "sky", "cloud", "clouds",
    "sunrise", "sunset", "waterfall", "river", "lake", "ocean",
    "beach", "jungle", "wildlife", "fauna", "flora",
})


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class VisionLabel:
    description: str
    score: float
    topicality: float = 0.0


@dataclass
class VisionObject:
    name: str
    confidence: float


@dataclass
class VisionResult:
    image_url: str
    labels: list[VisionLabel] = field(default_factory=list)
    objects: list[VisionObject] = field(default_factory=list)
    face_count: int = 0
    ocr_text: str = ""
    web_entities: list[str] = field(default_factory=list)
    is_valid: bool = True
    rejection_reason: Optional[str] = None
    # Structured context summary for LLM grounding
    context_summary: str = ""

    def label_names(self) -> list[str]:
        return [lb.description.lower() for lb in self.labels]

    def all_detected_terms(self) -> list[str]:
        """Combined flat list of all detected terms for grounding the LLM."""
        terms = self.label_names()
        terms += [obj.name.lower() for obj in self.objects]
        terms += [e.lower() for e in self.web_entities]
        return list(dict.fromkeys(terms))  # deduplicated, order preserved


# ---------------------------------------------------------------------------
# Core Vision API call
# ---------------------------------------------------------------------------

def _call_vision_api(image_url: str) -> dict:
    """
    Call the Cloud Vision REST API and return the raw annotation response dict.
    Raises requests.RequestException on network / HTTP errors.
    """
    settings = get_settings()
    api_key = settings.google_cloud_vision_api_key
    if not api_key:
        raise ValueError("GOOGLE_CLOUD_VISION_API_KEY is not configured.")

    payload = {
        "requests": [
            {
                "image": {"source": {"imageUri": image_url}},
                "features": [
                    {"type": "LABEL_DETECTION", "maxResults": 15},
                    {"type": "TEXT_DETECTION", "maxResults": 5},
                    {"type": "WEB_DETECTION", "maxResults": 10},
                    {"type": "OBJECT_LOCALIZATION", "maxResults": 10},
                    {"type": "FACE_DETECTION", "maxResults": 10},
                ],
            }
        ]
    }

    resp = requests.post(
        f"{_VISION_ENDPOINT}?key={api_key}",
        json=payload,
        timeout=_REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()

    responses = data.get("responses", [])
    if not responses:
        return {}
    return responses[0]


def _call_vision_api_base64(image_bytes: bytes) -> dict:
    """
    Call the Cloud Vision REST API with raw image bytes (base64-encoded).
    Used when a URL is not publicly accessible.
    """
    settings = get_settings()
    api_key = settings.google_cloud_vision_api_key
    if not api_key:
        raise ValueError("GOOGLE_CLOUD_VISION_API_KEY is not configured.")

    encoded = base64.b64encode(image_bytes).decode("utf-8")
    payload = {
        "requests": [
            {
                "image": {"content": encoded},
                "features": [
                    {"type": "LABEL_DETECTION", "maxResults": 15},
                    {"type": "TEXT_DETECTION", "maxResults": 5},
                    {"type": "WEB_DETECTION", "maxResults": 10},
                    {"type": "OBJECT_LOCALIZATION", "maxResults": 10},
                    {"type": "FACE_DETECTION", "maxResults": 10},
                ],
            }
        ]
    }

    resp = requests.post(
        f"{_VISION_ENDPOINT}?key={api_key}",
        json=payload,
        timeout=_REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()

    responses = data.get("responses", [])
    if not responses:
        return {}
    return responses[0]


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------

def _parse_vision_response(image_url: str, response: dict) -> VisionResult:
    """Parse the raw Vision API response into a structured VisionResult."""
    result = VisionResult(image_url=image_url)

    # Labels
    for ann in response.get("labelAnnotations", []):
        result.labels.append(VisionLabel(
            description=ann.get("description", ""),
            score=ann.get("score", 0.0),
            topicality=ann.get("topicality", 0.0),
        ))

    # Objects
    for obj in response.get("localizedObjectAnnotations", []):
        result.objects.append(VisionObject(
            name=obj.get("name", ""),
            confidence=obj.get("score", 0.0),
        ))

    # Face detection is intentionally treated as a hard editorial signal. A
    # close-up face/selfie can be missed by label detection when the image
    # also contains a hotel or landscape, so FACE_DETECTION must be requested
    # and parsed independently.
    result.face_count = len(response.get("faceAnnotations", []))

    # OCR text — first full-text annotation
    full_text = response.get("fullTextAnnotation", {})
    result.ocr_text = full_text.get("text", "").strip()
    if not result.ocr_text:
        # Fall back to individual text annotations
        text_anns = response.get("textAnnotations", [])
        if text_anns:
            result.ocr_text = text_anns[0].get("description", "").strip()

    # Web entities
    web = response.get("webDetection", {})
    for entity in web.get("webEntities", []):
        desc = entity.get("description", "")
        if desc:
            result.web_entities.append(desc)

    # Build context summary for LLM grounding
    top_labels = [lb.description for lb in result.labels[:8]]
    top_objects = [obj.name for obj in result.objects[:5]]
    result.context_summary = (
        f"Detected labels: {', '.join(top_labels)}. "
        f"Detected objects: {', '.join(top_objects)}. "
        + (f"OCR text: {result.ocr_text[:200]}. " if result.ocr_text else "")
        + (f"Web context: {', '.join(result.web_entities[:5])}." if result.web_entities else "")
    ).strip()

    return result


# ---------------------------------------------------------------------------
# Topic validation
# ---------------------------------------------------------------------------

def _extract_topic_tokens(section_topic: str) -> list[str]:
    """Extract meaningful tokens from a section heading/topic string."""
    # Remove HTML tags
    clean = re.sub(r"<[^>]+>", "", section_topic)
    # Lowercase and tokenize
    tokens = re.findall(r"[a-z]+", clean.lower())
    # Filter very short tokens and common stop words
    stop_words = {"the", "a", "an", "and", "or", "of", "in", "at", "to", "for", "is", "with"}
    return [t for t in tokens if len(t) > 2 and t not in stop_words]


def _is_culinary_topic(section_topic: str) -> bool:
    """Return True when the section topic refers to food, dining, or cuisine."""
    tokens = set(_extract_topic_tokens(section_topic))
    return bool(tokens & _CULINARY_TOPIC_TRIGGERS)


def _validate_topic_match(result: VisionResult, section_topic: str) -> tuple[bool, str | None]:
    """
    Validate that the image content matches the section topic.

    Returns (is_valid, rejection_reason).

    HARD CULINARY RULE
    ------------------
    When the section topic is about food / dining / cuisine:
      • The image MUST carry at least one positive food label.
      • If the top detected labels are nature / outdoor (mountain, valley,
        flower, forest, landscape …) the image is hard-rejected regardless of
        any other overlap, because a flower-valley shot is NEVER acceptable
        under a "Culinary Delights" or "Dining" heading.
    """
    detected = set(result.label_names())
    detected.update(obj.name.lower() for obj in result.objects)

    # Strict face/person filtering. Do this before topic matching so a selfie
    # cannot pass simply because the background happens to match the heading.
    if result.face_count:
        return False, (
            f"Image contains {result.face_count} detected face"
            f"{'s' if result.face_count != 1 else ''}; "
            "close-up faces and selfies are not permitted."
        )

    face_signal_labels = {
        "face", "selfie", "headshot", "close-up", "closeup",
        "portrait", "nose", "forehead", "chin", "cheek", "eyebrow",
        "eyelash", "lip", "skin", "wrinkle", "pore",
    }
    face_signals = detected & face_signal_labels
    if face_signals:
        return False, (
            "Image contains face/selfie signals "
            f"({', '.join(sorted(face_signals)[:4])}); "
            "close-up faces and selfies are not permitted."
        )

    # Always reject images with negative labels
    for label in detected:
        for reject_term in _REJECT_LABELS:
            if reject_term in label:
                return False, f"Image contains disallowed content: '{label}'"

    # ── HARD CULINARY RULE ───────────────────────────────────────────────────
    if _is_culinary_topic(section_topic):
        # Check for a positive food signal
        has_food = bool(detected & _FOOD_POSITIVE_LABELS)
        if not has_food:
            # Check whether it is predominantly a nature/outdoor image
            nature_hits = detected & _NATURE_LABELS_REJECT_CULINARY
            if nature_hits:
                return False, (
                    f"Culinary section requires food imagery but image shows nature content "
                    f"({', '.join(sorted(nature_hits)[:4])}). "
                    f"Nature/outdoor photos are NEVER acceptable under a food/dining heading."
                )
            # No food signal and no strong nature signal — still reject: an
            # unrecognised image is too risky for a strict editorial food section.
            if len(detected) >= 3:
                return False, (
                    f"Culinary section requires food imagery but no food labels detected "
                    f"(top labels: {', '.join(list(detected)[:4])}). "
                    f"Rejecting to prevent non-food content under dining heading."
                )
        # Food signal confirmed — accept without further topic checks
        return True, None

    # ── STANDARD TOPIC VALIDATION (non-culinary sections) ───────────────────
    # Extract topic tokens from the section heading
    topic_tokens = _extract_topic_tokens(section_topic)
    if not topic_tokens:
        return True, None  # No topic to validate against — accept

    # Try to find matching keywords from the topic map
    expected_keywords: list[str] = []
    for token in topic_tokens:
        for map_key, keywords in _TOPIC_KEYWORD_MAP.items():
            if token in map_key or map_key in token:
                expected_keywords.extend(keywords)
                break

    if not expected_keywords:
        # Topic not in map — do a direct token overlap check
        expected_keywords = topic_tokens

    # Check for any overlap between detected labels and expected keywords
    for detected_label in detected:
        for kw in expected_keywords:
            if kw in detected_label or detected_label in kw:
                return True, None  # Match found — accept

    # No overlap at all — check if it's a marginal case
    if len(detected) < 3:
        # Too few labels detected (low-quality API response) — give benefit of doubt
        return True, None

    rejection_reason = (
        f"Image labels ({', '.join(list(detected)[:5])}) "
        f"do not match section topic '{section_topic}' "
        f"(expected keywords: {', '.join(expected_keywords[:5])})"
    )
    return False, rejection_reason


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def scan_image(image_url: str) -> VisionResult:
    """
    Scan an image URL with the Google Cloud Vision API.

    Returns a VisionResult with labels, objects, OCR text, and web entities.
    If the Vision API key is not configured, returns a minimal valid result.
    Never raises — failures are logged and a safe fallback is returned.
    """
    settings = get_settings()
    if not settings.google_cloud_vision_api_key:
        logger.debug("Vision API key not configured — skipping scan for %s", image_url)
        return VisionResult(image_url=image_url, is_valid=True)

    try:
        raw = _call_vision_api(image_url)
        result = _parse_vision_response(image_url, raw)
        if result.face_count:
            result.is_valid = False
            result.rejection_reason = (
                f"Image contains {result.face_count} detected face"
                f"{'s' if result.face_count != 1 else ''}; "
                "close-up faces and selfies are not permitted."
            )
        logger.info(
            "Vision scan complete for %s: %d labels, %d objects, faces=%d, OCR=%s",
            image_url[:60], len(result.labels), len(result.objects),
            result.face_count, bool(result.ocr_text),
        )
        return result
    except Exception as exc:  # noqa: BLE001
        logger.warning("Vision API scan failed for %s: %s", image_url[:60], exc)
        # Keep the result non-throwing so tag-based gallery classification can
        # continue, but do not claim an unscanned image passed verification.
        return VisionResult(
            image_url=image_url,
            is_valid=False,
            rejection_reason="Vision scan unavailable; image could not be verified.",
            context_summary="Vision scan unavailable.",
        )


def validate_image_for_section(image_url: str, section_topic: str) -> VisionResult:
    """
    Full validation pipeline:
      1. Scan the image with Vision API.
      2. Validate that detected content matches the section topic.
      3. Mark result.is_valid and set result.rejection_reason if rejected.

    Returns the VisionResult. If Vision API is not configured, always valid.
    """
    result = scan_image(image_url)

    if not result.labels and not result.objects:
        # Nothing detected — probably API key missing or scan failed
        return result

    is_valid, reason = _validate_topic_match(result, section_topic)
    result.is_valid = is_valid
    result.rejection_reason = reason

    if not is_valid:
        logger.info(
            "Vision validation REJECTED image for section '%s': %s",
            section_topic[:60], reason,
        )
    else:
        logger.info(
            "Vision validation PASSED for section '%s': top labels=%s",
            section_topic[:60],
            [lb.description for lb in result.labels[:3]],
        )

    return result


def build_vision_context_for_llm(results: list[VisionResult]) -> str:
    """
    Build a structured context string from a list of VisionResult objects
    to pass to the LLM as grounding data for article/caption generation.

    The LLM must write section text that agrees with the visual content
    described here — ensuring 100% image-text alignment.
    """
    if not results:
        return ""

    lines = ["## VISION-VERIFIED IMAGE CONTEXT (write based on this ONLY)"]
    lines.append(
        "The following section descriptions are derived from Google Cloud Vision API "
        "scans of the actual images. Your article text and captions MUST match the "
        "visual content described below — do not invent features not listed here.\n"
    )
    for i, r in enumerate(results, 1):
        lines.append(f"### Image {i}: {r.image_url.split('?')[0][-60:]}")
        if r.labels:
            top = [f"{lb.description} ({lb.score:.0%})" for lb in r.labels[:6]]
            lines.append(f"  Detected: {', '.join(top)}")
        if r.objects:
            objs = [obj.name for obj in r.objects[:4]]
            lines.append(f"  Objects: {', '.join(objs)}")
        if r.ocr_text:
            lines.append(f"  Visible text: {r.ocr_text[:150]}")
        if r.web_entities:
            lines.append(f"  Web context: {', '.join(r.web_entities[:4])}")
        lines.append("")

    return "\n".join(lines)
