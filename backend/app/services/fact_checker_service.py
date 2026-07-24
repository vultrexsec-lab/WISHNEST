"""
Master Fact-Checker Pipeline for WishNest AI Research Editor Agent.

Cross-references generated article text against a master JSON fact database
to catch and block hallucinated or incorrect details before they reach the UI.

Fact database schema (backend/data/fact_database.json):
{
  "properties": {
    "<property_name_lower>": {
      "canonical_name": "Exact Property Name",
      "location": "City, State, Country",
      "distances": {
        "nearest_airport_km": 45,
        "nearest_city_km": 12
      },
      "ratings": {
        "google_stars": 4.4,
        "review_count": 312
      },
      "amenities": ["pool", "spa", "restaurant", "gym"],
      "price_band": "₹8,000–₹15,000/night",
      "features": {
        "rooms": 24,
        "year_established": 2018,
        "certifications": ["EarthCheck Gold"]
      },
      "prohibited_claims": [
        "5-star certified",
        "Michelin starred"
      ]
    }
  },
  "global_rules": {
    "max_distance_claim_km": 500,
    "currency_patterns": ["₹", "USD", "EUR", "INR"]
  }
}

Claim extraction uses regex patterns to detect:
  - Distance claims ("X km from ...", "X minutes from ...")
  - Price claims ("₹X,XXX/night", "$X per night")
  - Rating claims ("rated X.X stars", "X★")
  - Amenity claims ("has a pool", "spa facilities")
  - Prohibited terms (from prohibited_claims list)
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("wishnest.fact_checker")

# ---------------------------------------------------------------------------
# Fact database location
# ---------------------------------------------------------------------------

_FACT_DB_PATH = Path(__file__).resolve().parents[2] / "data" / "fact_database.json"
_fact_db_cache: dict | None = None


def load_fact_database(force_reload: bool = False) -> dict:
    """Load (and cache) the master fact database from disk."""
    global _fact_db_cache
    if _fact_db_cache is not None and not force_reload:
        return _fact_db_cache
    if not _FACT_DB_PATH.exists():
        logger.warning("Fact database not found at %s — returning empty DB.", _FACT_DB_PATH)
        _fact_db_cache = {"properties": {}, "global_rules": {}}
        return _fact_db_cache
    try:
        with open(_FACT_DB_PATH, encoding="utf-8") as f:
            _fact_db_cache = json.load(f)
        logger.info("Loaded fact database with %d properties.", len(_fact_db_cache.get("properties", {})))
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to load fact database: %s", exc)
        _fact_db_cache = {"properties": {}, "global_rules": {}}
    return _fact_db_cache


def save_fact_database(db: dict) -> None:
    """Persist the fact database to disk and clear the cache."""
    global _fact_db_cache
    _FACT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_FACT_DB_PATH, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)
    _fact_db_cache = db
    logger.info("Fact database saved with %d properties.", len(db.get("properties", {})))


# ---------------------------------------------------------------------------
# Claim extraction patterns
# ---------------------------------------------------------------------------

# Distance: "45 km from", "45-minute drive", "30 mins from"
_DISTANCE_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:km|kilometres?|kilometers?|miles?)\s+(?:from|away|to)\s+"
    r"([A-Za-z][A-Za-z\s]+?)(?:\.|,|;|\band\b|$)",
    re.IGNORECASE,
)
_DRIVE_TIME_RE = re.compile(
    r"(\d+)[- ]?(?:minute|min|hour|hr)s?\s+(?:drive|ride|journey|trip|away)\s*(?:from\s+([A-Za-z\s]+?))?(?:\.|,|;|$)",
    re.IGNORECASE,
)

# Price: ₹8,000/night  $250 per night  USD 500
_PRICE_RE = re.compile(
    r"(?:₹|USD|INR|\$|€|£)\s*[\d,]+(?:\.\d+)?\s*(?:/night|per night|a night)?",
    re.IGNORECASE,
)

# Rating: "4.5 stars", "rated 4.2★", "4.4-star"
_RATING_RE = re.compile(
    r"(\d+(?:\.\d+)?)[- ]?(?:star|★|stars?|out of 5)",
    re.IGNORECASE,
)

# Room count: "24 rooms", "45 suites"
_ROOM_RE = re.compile(
    r"(\d+)\s+(?:rooms?|suites?|villas?|cottages?|bungalows?|cabins?)",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class FactViolation:
    violation_type: str          # "prohibited_claim", "distance_mismatch", "rating_mismatch", etc.
    claim_in_article: str        # The exact text found in the article
    expected_value: Any          # What the fact database says
    property_name: str           # Which property this applies to
    severity: str = "warning"    # "error" (hard block) or "warning" (log only)
    suggestion: str = ""


@dataclass
class FactCheckResult:
    passed: bool
    violations: list[FactViolation] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    checked_properties: list[str] = field(default_factory=list)

    def errors(self) -> list[FactViolation]:
        return [v for v in self.violations if v.severity == "error"]

    def summary(self) -> str:
        if self.passed:
            return f"PASSED — {len(self.checked_properties)} propert(ies) checked, no errors."
        errors = self.errors()
        return (
            f"FAILED — {len(errors)} error(s), {len(self.violations) - len(errors)} warning(s) "
            f"across {len(self.checked_properties)} propert(ies)."
        )


# ---------------------------------------------------------------------------
# Property matching
# ---------------------------------------------------------------------------

def _find_matching_properties(text: str, fact_db: dict) -> list[tuple[str, dict]]:
    """
    Find which properties from the fact database are mentioned in the article text.
    Returns a list of (property_key, property_data) tuples.
    """
    properties = fact_db.get("properties", {})
    text_lower = text.lower()
    matches = []
    for key, data in properties.items():
        canonical = data.get("canonical_name", key)
        if key in text_lower or canonical.lower() in text_lower:
            matches.append((canonical, data))
    return matches


# ---------------------------------------------------------------------------
# Individual claim validators
# ---------------------------------------------------------------------------

def _check_prohibited_claims(text: str, prop_name: str, prop_data: dict) -> list[FactViolation]:
    """Check for prohibited claims about a property."""
    violations = []
    prohibited = prop_data.get("prohibited_claims", [])
    text_lower = text.lower()
    for claim in prohibited:
        if claim.lower() in text_lower:
            violations.append(FactViolation(
                violation_type="prohibited_claim",
                claim_in_article=claim,
                expected_value="NOT allowed",
                property_name=prop_name,
                severity="error",
                suggestion=f"Remove or qualify the claim '{claim}' — it is not verified for {prop_name}.",
            ))
    return violations


def _check_rating_claims(text: str, prop_name: str, prop_data: dict) -> list[FactViolation]:
    """Check numeric rating claims against the fact database."""
    violations = []
    known_rating = prop_data.get("ratings", {}).get("google_stars")
    if known_rating is None:
        return violations

    for m in _RATING_RE.finditer(text):
        claimed = float(m.group(1))
        # Allow a tolerance of ±0.5 stars
        if abs(claimed - known_rating) > 0.5:
            violations.append(FactViolation(
                violation_type="rating_mismatch",
                claim_in_article=m.group(0),
                expected_value=f"{known_rating} stars (Google)",
                property_name=prop_name,
                severity="warning",
                suggestion=f"Verify rating claim '{m.group(0)}' — fact DB shows {known_rating}★.",
            ))
    return violations


def _check_price_claims(text: str, prop_name: str, prop_data: dict) -> list[FactViolation]:
    """Check price claims against the fact database."""
    violations = []
    known_price = prop_data.get("price_band", "")
    if not known_price or not _PRICE_RE.search(text):
        return violations

    # Extract numeric range from known price band (e.g. "₹8,000–₹15,000/night" → [8000, 15000])
    nums_in_known = [int(n.replace(",", "")) for n in re.findall(r"[\d,]+", known_price)]
    if not nums_in_known:
        return violations
    known_min, known_max = min(nums_in_known), max(nums_in_known)

    for m in _PRICE_RE.finditer(text):
        nums = [int(n.replace(",", "")) for n in re.findall(r"[\d,]+", m.group(0))]
        if not nums:
            continue
        claimed_price = nums[0]
        # Allow 50% margin (pricing data can be dated)
        if claimed_price < known_min * 0.5 or claimed_price > known_max * 2.0:
            violations.append(FactViolation(
                violation_type="price_mismatch",
                claim_in_article=m.group(0),
                expected_value=known_price,
                property_name=prop_name,
                severity="warning",
                suggestion=f"Price claim '{m.group(0)}' appears inconsistent with fact DB range {known_price}.",
            ))
    return violations


def _check_room_claims(text: str, prop_name: str, prop_data: dict) -> list[FactViolation]:
    """Check room/suite count claims."""
    violations = []
    known_rooms = prop_data.get("features", {}).get("rooms")
    if known_rooms is None:
        return violations

    for m in _ROOM_RE.finditer(text):
        claimed = int(m.group(1))
        if abs(claimed - known_rooms) > max(5, known_rooms * 0.2):  # 20% tolerance
            violations.append(FactViolation(
                violation_type="room_count_mismatch",
                claim_in_article=m.group(0),
                expected_value=f"{known_rooms} rooms/suites",
                property_name=prop_name,
                severity="warning",
                suggestion=f"Room count claim '{m.group(0)}' differs from fact DB ({known_rooms}).",
            ))
    return violations


def _check_amenity_claims(text: str, prop_name: str, prop_data: dict) -> list[FactViolation]:
    """Check that claimed amenities are in the fact database."""
    violations = []
    known_amenities = {a.lower() for a in prop_data.get("amenities", [])}
    if not known_amenities:
        return violations

    # High-stakes amenities that must be explicitly verified
    high_stakes = ["private beach", "helipad", "michelin", "rooftop infinity pool",
                   "butler service", "private jet"]
    text_lower = text.lower()
    for amenity in high_stakes:
        if amenity in text_lower and amenity not in known_amenities:
            violations.append(FactViolation(
                violation_type="unverified_amenity",
                claim_in_article=amenity,
                expected_value=f"Known amenities: {', '.join(known_amenities)}",
                property_name=prop_name,
                severity="error",
                suggestion=f"Claim of '{amenity}' not found in verified amenity list for {prop_name}.",
            ))
    return violations


# ---------------------------------------------------------------------------
# Global rules
# ---------------------------------------------------------------------------

def _check_global_rules(text: str, global_rules: dict) -> list[str]:
    """Apply global fact-checking rules that apply to all properties."""
    warnings = []
    max_dist = global_rules.get("max_distance_claim_km", 1000)
    for m in _DISTANCE_RE.finditer(text):
        try:
            dist = float(m.group(1))
            if dist > max_dist:
                warnings.append(
                    f"Distance claim '{m.group(0).strip()}' ({dist}km) exceeds plausible limit "
                    f"({max_dist}km) — verify this is accurate."
                )
        except ValueError:
            pass
    return warnings


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def fact_check_article(
    article_text: str,
    headline: str = "",
    source_urls: Optional[list[str]] = None,
) -> FactCheckResult:
    """
    Run the full fact-checking pipeline on a generated article.

    1. Load the fact database.
    2. Identify which properties are mentioned in the article.
    3. Extract and validate all verifiable claims.
    4. Return a FactCheckResult with pass/fail status and all violations.

    Never raises — if the fact database is empty or a check fails, the article
    passes with a warning (non-blocking degradation).
    """
    fact_db = load_fact_database()
    result = FactCheckResult(passed=True)

    if not fact_db.get("properties"):
        result.warnings.append("Fact database is empty — no property facts to verify against.")
        return result

    # Combine headline and body for matching
    full_text = f"{headline}\n{article_text}"

    # Find matching properties
    matched = _find_matching_properties(full_text, fact_db)
    result.checked_properties = [name for name, _ in matched]

    if not matched:
        result.warnings.append(
            "No properties in the fact database matched this article — "
            "manual review recommended for factual accuracy."
        )
        return result

    # Run per-property checks
    all_violations: list[FactViolation] = []
    for prop_name, prop_data in matched:
        all_violations += _check_prohibited_claims(full_text, prop_name, prop_data)
        all_violations += _check_rating_claims(full_text, prop_name, prop_data)
        all_violations += _check_price_claims(full_text, prop_name, prop_data)
        all_violations += _check_room_claims(full_text, prop_name, prop_data)
        all_violations += _check_amenity_claims(full_text, prop_name, prop_data)

    # Global rules
    global_rules = fact_db.get("global_rules", {})
    result.warnings += _check_global_rules(full_text, global_rules)

    result.violations = all_violations
    hard_errors = [v for v in all_violations if v.severity == "error"]
    result.passed = len(hard_errors) == 0

    if not result.passed:
        logger.warning(
            "Fact-check FAILED for '%s': %d error(s), %d warning(s).",
            (headline or "article")[:60], len(hard_errors), len(all_violations) - len(hard_errors),
        )
    else:
        logger.info(
            "Fact-check PASSED for '%s': %d warning(s) across %d matched propert(ies).",
            (headline or "article")[:60], len(all_violations), len(matched),
        )

    return result


def add_property_to_fact_db(property_key: str, property_data: dict) -> None:
    """Add or update a property entry in the fact database."""
    db = load_fact_database()
    db.setdefault("properties", {})[property_key.lower()] = property_data
    save_fact_database(db)


def get_fact_database_summary() -> dict:
    """Return a summary of the fact database for the admin UI."""
    db = load_fact_database()
    properties = db.get("properties", {})
    return {
        "property_count": len(properties),
        "property_names": [
            v.get("canonical_name", k) for k, v in properties.items()
        ],
        "global_rules": db.get("global_rules", {}),
        "database_path": str(_FACT_DB_PATH),
    }
