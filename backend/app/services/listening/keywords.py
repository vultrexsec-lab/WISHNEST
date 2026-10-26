from __future__ import annotations
from typing import Any

def generate_keywords(*, category: str, offerings: list[str] | None = None, locations: list[str] | None = None) -> dict[str, Any]:
    cat = (category or "services").lower()
    locs = locations or ["India"]
    primary = _primary(cat)
    intent: list[str] = []
    for term in primary[:6]:
        intent.extend([
            f"looking for {term}",
            f"need {term}",
            f"recommend {term}",
            f"{term} quotation",
            f"{term} chahiye",
            f"best {term}",
        ])
    for loc in locs[:4]:
        for term in primary[:4]:
            intent.append(f"{term} in {loc}")
            intent.append(f"{loc} {term}")
    # Never use bare "general services" as search axis
    intent = [k for k in intent if "general services" not in k.lower()]
    primary = [k for k in primary if "general services" not in k.lower()]
    return {
        "primary": list(dict.fromkeys(primary))[:20],
        "buying_intent": list(dict.fromkeys(intent))[:36],
        "related": _related(cat)[:20],
        "negative": [
            "job opening", "hiring", "salary", "internship", "meme", "joke",
            "car service", "general knowledge", "current affairs", "GSA",
            "workers chahiye", "malaysia jobs",
        ],
        "offerings_used": offerings or [],
        "locations_used": locs,
        "must_match_any": primary[:12],  # relevance gate
    }

def _primary(cat: str) -> list[str]:
    if "wishnest" in cat or ("hospitality" in cat and "architecture" in cat) or "second home" in cat:
        return [
            "boutique hotel", "resort design", "villa architect", "second home India",
            "hospitality design", "hotel renovation", "weekend home", "luxury villa",
            "architect for villa", "resort FF&E",
        ]
    if "architect" in cat:
        return ["architect", "residential architect", "villa architect", "home designer"]
    if "villa" in cat or "second" in cat:
        return ["second home", "holiday home", "luxury villa", "weekend home"]
    if "automation" in cat or "smart" in cat:
        return ["home automation", "smart home", "smart lighting"]
    if "furniture" in cat:
        return ["office furniture", "resort furniture", "hospitality furniture", "custom furniture"]
    if "hospital" in cat or "hotel" in cat or "resort" in cat:
        return ["boutique hotel", "resort design", "hotel interiors", "hospitality project"]
    if "interior" in cat:
        return ["interior designer", "villa interiors", "hotel interiors"]
    if "software" in cat or "saas" in cat:
        return ["CRM software", "SaaS tool"]
    # Avoid ultra-generic sole term
    return ["professional services quotation", "project consultant", cat.replace("general services", "consultant")]

def _related(cat: str) -> list[str]:
    if "architect" in cat or "hospitality" in cat or "villa" in cat or "second" in cat:
        return ["building a house", "farmhouse design", "hotel pre-opening", "villa investment"]
    return ["quotation", "budget", "timeline", "recommendation"]
