"""Buying-intent heuristics (0–100) + conversation classification."""
from __future__ import annotations

import re
from typing import Any


_HIGH = [
    (r"looking for\s+\w+", 70),
    (r"need\s+(an?\s+)?\w+", 70),
    (r"recommend\s+\w+", 70),
    (r"any\s+recommendations?", 70),
    (r"quotation|quote\s+for|pricing|how much", 75),
    (r"budget|₹|rs\.?|inr|lakh|crore", 90),
    (r"this month|next month|asap|urgent|timeline", 85),
    (r"chahiye|kitna|sugges", 70),
]
_MED = [
    (r"considering|planning to|thinking of", 55),
    (r"vs\s+|alternative to|better than", 50),
    (r"disappointed|bad experience|switching from", 60),
]
_LOW = [
    (r"what is|how does|info on", 30),
    (r"interesting|might try", 25),
]


def score_intent(text: str) -> dict[str, Any]:
    t = (text or "").lower()
    score = 15
    hits: list[str] = []
    for pattern, pts in _HIGH + _MED + _LOW:
        if re.search(pattern, t, re.I):
            score = max(score, pts)
            hits.append(pattern)
    # explicit supplier request boost
    if re.search(r"(looking for|need|recommend).{0,40}(architect|designer|villa|automation|furniture|hotel)", t):
        score = max(score, 95)
        hits.append("explicit_supplier_request")
    score = min(100, score)
    if score >= 80:
        band = "high"
    elif score >= 60:
        band = "medium"
    elif score >= 30:
        band = "low"
    else:
        band = "research"
    return {"intent_score": score, "intent_band": band, "signals": hits[:12]}


def classify_conversation(text: str, category_hint: str | None = None) -> dict[str, Any]:
    t = text or ""
    intent = score_intent(t)
    location = _extract_location(t)
    budget = _extract_budget(t)
    requirement = t.strip()[:400]
    stage = "Supplier Discovery" if intent["intent_score"] >= 70 else (
        "Evaluation" if intent["intent_score"] >= 50 else "Awareness"
    )
    action = (
        "Helpful public response (no cold DM)"
        if intent["intent_score"] >= 60
        else "Monitor / content opportunity"
    )
    return {
        "category": category_hint or "General",
        "requirement": requirement,
        "location": location,
        "budget_hint": budget,
        "stage": stage,
        "recommended_action": action,
        "contact_eligible": False,
        **intent,
    }


def _extract_location(t: str) -> str | None:
    cities = [
        "Dehradun", "Pune", "Goa", "Lonavala", "Mumbai", "Delhi", "Bangalore",
        "Bengaluru", "Hyderabad", "Chennai", "Jaipur", "Uttarakhand", "Maharashtra",
        "Gurgaon", "Noida", "Chandigarh", "Shimla", "Manali", "Alibaug",
    ]
    low = t.lower()
    for c in cities:
        if c.lower() in low:
            return c
    return None


def _extract_budget(t: str) -> str | None:
    m = re.search(r"(₹\s*[\d,.]+\s*(lakh|crore|L|Cr)?)|(\d+\s*(lakh|crore))", t, re.I)
    return m.group(0) if m else None
