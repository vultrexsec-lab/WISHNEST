from __future__ import annotations
import re
from typing import Any

_HIGH = [(r"looking for\s+\w+",70),(r"need\s+(an?\s+)?\w+",70),(r"recommend\s+\w+",70),(r"any\s+recommendations?",70),
         (r"quotation|quote\s+for|pricing|how much",75),(r"budget|₹|rs\.?|inr|lakh|crore",90),
         (r"this month|next month|asap|urgent|timeline",85),(r"chahiye|kitna|sugges",70)]
_MED = [(r"considering|planning to|thinking of",55),(r"vs\s+|alternative to|better than",50),(r"disappointed|bad experience|switching from",60)]
_LOW = [(r"what is|how does|info on",30),(r"interesting|might try",25)]

def score_intent(text: str) -> dict[str, Any]:
    t = (text or "").lower()
    score, hits = 15, []
    for pattern, pts in _HIGH + _MED + _LOW:
        if re.search(pattern, t, re.I):
            score = max(score, pts)
            hits.append(pattern)
    if re.search(r"(looking for|need|recommend).{0,40}(architect|designer|villa|automation|furniture|hotel)", t):
        score = max(score, 95)
        hits.append("explicit_supplier_request")
    score = min(100, score)
    band = "high" if score >= 80 else "medium" if score >= 60 else "low" if score >= 30 else "research"
    return {"intent_score": score, "intent_band": band, "signals": hits[:12]}

def classify_conversation(text: str, category_hint: str | None = None) -> dict[str, Any]:
    t = text or ""
    intent = score_intent(t)
    cities = ["Dehradun","Pune","Goa","Lonavala","Mumbai","Delhi","Bangalore","Bengaluru","Hyderabad","Chennai","Jaipur","Uttarakhand","Maharashtra","Gurgaon","Noida","Alibaug"]
    location = next((c for c in cities if c.lower() in t.lower()), None)
    m = re.search(r"(₹\s*[\d,.]+\s*(lakh|crore|L|Cr)?)|(\d+\s*(lakh|crore))", t, re.I)
    budget = m.group(0) if m else None
    stage = "Supplier Discovery" if intent["intent_score"] >= 70 else ("Evaluation" if intent["intent_score"] >= 50 else "Awareness")
    action = "Helpful public response (no cold DM)" if intent["intent_score"] >= 60 else "Monitor / content opportunity"
    return {"category": category_hint or "General", "requirement": t.strip()[:400], "location": location,
            "budget_hint": budget, "stage": stage, "recommended_action": action, "contact_eligible": False, **intent}
