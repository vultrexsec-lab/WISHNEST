from __future__ import annotations
import re
from typing import Any

_DOMAIN = re.compile(
    r"architect|architecture|interior|villa|resort|hotel|hospitality|second\s*home|"
    r"holiday\s*home|boutique|FF&E|renovation|designer|furniture|automation|smart\s*home|"
    r"construction|developer|procurement",
    re.I,
)

_HIGH = [
    (r"looking for\s+\w+", 55),
    (r"need\s+(an?\s+)?\w+", 55),
    (r"recommend\s+\w+", 55),
    (r"any\s+recommendations?", 55),
    (r"quotation|quote\s+for|pricing|how much", 70),
    (r"budget|₹|rs\.?|inr|lakh|crore", 85),
    (r"this month|next month|asap|urgent|timeline", 80),
    (r"chahiye", 50),
]
_MED = [
    (r"considering|planning to|thinking of", 45),
    (r"vs\s+|alternative to|better than", 40),
    (r"disappointed|bad experience|switching from", 50),
]
_LOW = [
    (r"what is|how does|info on", 25),
    (r"interesting|might try", 20),
]

_NOISE = re.compile(
    r"car\s+service|general\s+knowledge|current\s+affairs|malaysia\s+jobs?|"
    r"workers?\s+chahiye|GSA\s*\(|General Services Administration|"
    r"union budget|how to service any car",
    re.I,
)

def score_intent(text: str, must_terms: list[str] | None = None) -> dict[str, Any]:
    t = (text or "").lower()
    if _NOISE.search(t):
        return {"intent_score": 5, "intent_band": "noise", "signals": ["noise_filter"]}
    score, hits = 10, []
    domain_hit = bool(_DOMAIN.search(t))
    for pattern, pts in _HIGH + _MED + _LOW:
        if re.search(pattern, t, re.I):
            score = max(score, pts)
            hits.append(pattern)
    if domain_hit and score >= 50:
        score = min(100, score + 25)
        hits.append("domain_term")
    if must_terms:
        mt = [m.lower() for m in must_terms if m]
        if mt and not any(m in t for m in mt) and not domain_hit:
            score = min(score, 25)
            hits.append("no_category_match")
    if re.search(
        r"(looking for|need|recommend).{0,50}(architect|designer|villa|resort|hotel|furniture|automation)",
        t,
    ):
        score = max(score, 92)
        hits.append("explicit_supplier_request")
    score = min(100, score)
    band = "high" if score >= 80 else "medium" if score >= 60 else "low" if score >= 30 else "research"
    if score < 20:
        band = "noise"
    return {"intent_score": score, "intent_band": band, "signals": hits[:12]}

def classify_conversation(
    text: str,
    category_hint: str | None = None,
    must_terms: list[str] | None = None,
) -> dict[str, Any]:
    t = text or ""
    intent = score_intent(t, must_terms=must_terms)
    cities = [
        "Dehradun", "Pune", "Goa", "Lonavala", "Mumbai", "Delhi", "Bangalore", "Bengaluru",
        "Hyderabad", "Chennai", "Jaipur", "Uttarakhand", "Maharashtra", "Gurgaon", "Noida", "Alibaug",
    ]
    location = next((c for c in cities if c.lower() in t.lower()), None)
    m = re.search(r"(₹\s*[\d,.]+\s*(lakh|crore|L|Cr)?)|(\d+\s*(lakh|crore))", t, re.I)
    budget = m.group(0) if m else None
    stage = (
        "Supplier Discovery"
        if intent["intent_score"] >= 70
        else ("Evaluation" if intent["intent_score"] >= 50 else "Awareness")
    )
    action = (
        "Helpful public response (no cold DM)"
        if intent["intent_score"] >= 60
        else "Monitor / content opportunity"
    )
    return {
        "category": category_hint or "General",
        "requirement": t.strip()[:400],
        "location": location,
        "budget_hint": budget,
        "stage": stage,
        "recommended_action": action,
        "contact_eligible": False,
        **intent,
    }
