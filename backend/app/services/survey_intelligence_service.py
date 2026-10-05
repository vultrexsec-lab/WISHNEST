"""Aggregate survey answers into demand signals and ArrowX opportunity drafts."""
from __future__ import annotations

from collections import Counter
from typing import Any


def aggregate_demand_signals(responses: list[dict[str, Any]]) -> dict[str, Any]:
    """responses: list of answer dicts (flat key → value)."""
    if not responses:
        return {"response_count": 0, "signals": {}}

    budgets: Counter[str] = Counter()
    property_types: Counter[str] = Counter()
    locations: Counter[str] = Counter()
    intents: Counter[str] = Counter()
    other: dict[str, Counter[str]] = {}

    for ans in responses:
        if not isinstance(ans, dict):
            continue
        for k, v in ans.items():
            if v is None or v == "":
                continue
            key = str(k).lower()
            val = str(v).strip()
            if not val:
                continue
            if "budget" in key or "price" in key or "ticket" in key:
                budgets[val] += 1
            elif "property" in key or "villa" in key or "type" in key:
                property_types[val] += 1
            elif "location" in key or "destination" in key or "city" in key:
                locations[val] += 1
            elif "intent" in key or "purpose" in key or "use" in key:
                intents[val] += 1
            else:
                other.setdefault(key, Counter())[val] += 1

    def top(c: Counter[str], n: int = 8) -> list[dict[str, Any]]:
        return [{"value": k, "count": v} for k, v in c.most_common(n)]

    return {
        "response_count": len(responses),
        "signals": {
            "budget": top(budgets),
            "property_type": top(property_types),
            "location": top(locations),
            "intent": top(intents),
            "other": {k: top(v, 5) for k, v in other.items()},
        },
    }


def opportunity_title(survey_title: str, destination: str | None, signals: dict[str, Any]) -> str:
    dest = destination or "India"
    n = signals.get("response_count") or 0
    return f"Demand signal: {survey_title} ({dest}) — {n} responses"


def opportunity_summary(signals: dict[str, Any]) -> str:
    s = signals.get("signals") or {}
    parts = []
    for label, key in (
        ("Budget", "budget"),
        ("Property", "property_type"),
        ("Location", "location"),
        ("Intent", "intent"),
    ):
        items = s.get(key) or []
        if items:
            top3 = ", ".join(f"{i['value']} ({i['count']})" for i in items[:3])
            parts.append(f"{label}: {top3}")
    return " | ".join(parts) if parts else "Survey responses aggregated; review raw signals."
