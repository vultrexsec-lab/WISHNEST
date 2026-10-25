"""Keyword clusters for discovery (EN + Hinglish heuristics)."""
from __future__ import annotations

from typing import Any


def generate_keywords(
    *,
    category: str,
    offerings: list[str] | None = None,
    locations: list[str] | None = None,
) -> dict[str, Any]:
    cat = (category or "services").lower()
    locs = locations or ["India"]
    primary = _primary(cat)
    intent = _intent(cat)
    related = _related(cat)
    for loc in locs[:5]:
        intent.append(f"looking for {primary[0]} in {loc}")
        intent.append(f"{primary[0]} near {loc}")
        intent.append(f"{loc} me {primary[0]}")
    # Hinglish
    intent.extend(
        [
            f"{primary[0]} chahiye",
            f"best {primary[0]} kaunsa",
            f"{primary[0]} kitna charge",
        ]
    )
    negative = [
        "job opening",
        "hiring",
        "salary",
        "internship",
        "meme",
        "joke",
    ]
    return {
        "primary": list(dict.fromkeys(primary))[:20],
        "buying_intent": list(dict.fromkeys(intent))[:40],
        "related": list(dict.fromkeys(related))[:20],
        "negative": negative,
        "offerings_used": offerings or [],
        "locations_used": locs,
    }


def _primary(cat: str) -> list[str]:
    if "architect" in cat:
        return ["architect", "residential architect", "villa architect", "home designer"]
    if "second" in cat or "villa" in cat:
        return ["second home", "holiday home", "luxury villa", "weekend home"]
    if "automation" in cat or "smart" in cat:
        return ["home automation", "smart home", "smart lighting"]
    if "furniture" in cat:
        return ["custom furniture", "home furniture", "interior furniture"]
    if "hospital" in cat or "hotel" in cat or "resort" in cat:
        return ["boutique hotel", "resort design", "hospitality renovation"]
    if "interior" in cat:
        return ["interior designer", "villa interiors", "home interior"]
    if "software" in cat or "saas" in cat:
        return ["CRM software", "SaaS tool", "automation software"]
    return [cat, f"best {cat}", f"{cat} service"]


def _intent(cat: str) -> list[str]:
    p = _primary(cat)[0]
    return [
        f"looking for {p}",
        f"need {p}",
        f"recommend {p}",
        f"{p} cost",
        f"{p} quotation",
        f"best {p} near me",
        f"anyone know good {p}",
    ]


def _related(cat: str) -> list[str]:
    if "architect" in cat:
        return ["building a house", "farmhouse design", "construction drawings", "renovating home"]
    if "villa" in cat or "second" in cat:
        return ["villa investment", "holiday home budget", "managed villa"]
    return ["quotation", "budget", "timeline", "recommendation"]
