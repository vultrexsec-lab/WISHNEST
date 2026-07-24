"""Regression tests for strict editorial image routing."""

from types import SimpleNamespace
from unittest.mock import patch

from app.services import image_service
from app.services.image_service import (
    PHOTO_CAT_DINING,
    PHOTO_CAT_EXTERIOR,
    PHOTO_CAT_OUTDOOR,
    PHOTO_CAT_ROOMS,
    SmartPhotoPool,
    _classify_photo_vision_category,
)
from app.services.vision_service import (
    VisionLabel,
    VisionResult,
    _parse_vision_response,
    _validate_topic_match,
)


def _tagged_pool() -> SmartPhotoPool:
    return SmartPhotoPool(
        [
            {"url": "https://example.test/room.jpg", "tags": ["bedroom", "bed"]},
            {"url": "https://example.test/outdoor.jpg", "tags": ["garden", "lawn"]},
            {"url": "https://example.test/buffet.jpg", "tags": ["buffet", "food"]},
            {"url": "https://example.test/lobby.jpg", "tags": ["lobby", "reception"]},
        ],
        max_vision_calls=0,
    )


def test_room_design_only_returns_bedroom_photo():
    pool = _tagged_pool()

    picked = pool.pick_for_section("room_design")

    assert picked is not None
    assert picked[1] == PHOTO_CAT_ROOMS
    assert picked[0].endswith("room.jpg")


def test_outdoor_spaces_only_returns_outdoor_photo():
    pool = _tagged_pool()

    picked = pool.pick_for_section("outdoor")

    assert picked is not None
    assert picked[1] == PHOTO_CAT_OUTDOOR
    assert picked[0].endswith("outdoor.jpg")


def test_culinary_and_hospitality_cannot_swap_categories():
    pool = _tagged_pool()

    culinary = pool.pick_for_section("culinary")
    hospitality = pool.pick_for_section("hospitality", {culinary[0]})

    assert culinary is not None
    assert culinary[1] == PHOTO_CAT_DINING
    assert culinary[0].endswith("buffet.jpg")
    # The lobby is valid hospitality content; the buffet is not.
    assert hospitality is not None
    assert hospitality[0].endswith("lobby.jpg")
    assert hospitality[1] != PHOTO_CAT_DINING


def test_strict_section_uses_safe_fallback_instead_of_blank():
    pool = SmartPhotoPool(
        [{"url": "https://example.test/garden.jpg", "tags": ["garden", "lawn"]}],
        max_vision_calls=0,
    )

    room_pick = pool.pick_for_section("room_design")
    culinary_pick = pool.pick_for_section("culinary")

    assert room_pick is not None
    assert room_pick[1] == PHOTO_CAT_OUTDOOR
    # Outdoor/landscape is a safe general property fallback for room design,
    # while the same image is never borrowed for culinary content.
    assert culinary_pick is None


def test_safe_fallback_never_uses_bathroom_or_core_mismatch():
    pool = SmartPhotoPool(
        [
            {"url": "https://example.test/bathroom.jpg", "tags": ["bathroom", "toilet"]},
            {"url": "https://example.test/pool.jpg", "tags": ["pool", "swimming pool"]},
            {"url": "https://example.test/facade.jpg", "tags": ["building", "exterior"]},
        ],
        max_vision_calls=0,
    )

    culinary = pool.pick_for_section("culinary")
    hospitality = pool.pick_for_section("hospitality")

    assert culinary is not None
    assert culinary[0].endswith("facade.jpg")
    assert culinary[1] != image_service.PHOTO_CAT_BATHROOM
    assert hospitality is not None
    assert hospitality[1] != image_service.PHOTO_CAT_BATHROOM


def test_culinary_fallback_allows_landscape_but_rejects_pool():
    pool = SmartPhotoPool(
        [
            {"url": "https://example.test/pool.jpg", "tags": ["pool", "swimming pool"]},
            {"url": "https://example.test/valley.jpg", "tags": ["valley", "landscape"]},
        ],
        max_vision_calls=0,
    )

    picked = pool.pick_for_section("culinary")

    assert picked is not None
    assert picked[0].endswith("valley.jpg")
    assert picked[1] == PHOTO_CAT_OUTDOOR


def test_safe_photo_can_be_reused_when_gallery_is_smaller_than_sections():
    pool = SmartPhotoPool(
        [{"url": "https://example.test/facade.jpg", "tags": ["building", "exterior"]}],
        max_vision_calls=0,
    )

    first = pool.pick_for_section("hospitality", allow_reuse=True)
    second = pool.pick_for_section("connectivity", {first[0]}, allow_reuse=True)

    assert first is not None
    assert second is not None
    assert second[0] == first[0]


def test_connectivity_uses_landscape_as_safe_fallback():
    pool = SmartPhotoPool(
        [{"url": "https://example.test/valley.jpg", "tags": ["valley", "landscape"]}],
        max_vision_calls=0,
    )

    picked = pool.pick_for_section("connectivity")

    assert picked is not None
    assert picked[1] == PHOTO_CAT_OUTDOOR
    assert picked[1] != PHOTO_CAT_EXTERIOR


def test_face_detection_is_a_hard_validation_failure():
    result = _parse_vision_response(
        "https://example.test/selfie.jpg",
        {
            "faceAnnotations": [{}],
            "labelAnnotations": [{"description": "Resort", "score": 0.98}],
        },
    )

    valid, reason = _validate_topic_match(result, "General Overview")

    assert result.face_count == 1
    assert valid is False
    assert reason is not None
    assert "face" in reason.lower()


def test_classifier_rejects_face_detection_even_when_room_label_is_top():
    vision_result = VisionResult(
        image_url="https://example.test/selfie.jpg",
        labels=[VisionLabel("Bedroom", 0.99), VisionLabel("Resort", 0.9)],
        face_count=1,
    )
    settings = SimpleNamespace(google_cloud_vision_api_key="configured")

    with patch.object(image_service, "get_settings", return_value=settings), \
         patch(
             "app.services.vision_service.scan_image",
             return_value=vision_result,
         ):
        category, quality, is_selfie = _classify_photo_vision_category(
            "https://example.test/selfie.jpg", []
        )

    assert category == "selfie"
    assert quality == 0.0
    assert is_selfie is True


def test_lobby_tag_is_hospitality_amenity_not_room_design():
    category, quality, is_selfie = _classify_photo_vision_category(
        "", ["lobby", "reception"]
    )

    assert category == image_service.PHOTO_CAT_AMENITY
    assert quality > 0
    assert is_selfie is False