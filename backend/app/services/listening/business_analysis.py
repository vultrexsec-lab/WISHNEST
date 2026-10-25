"""Website / description → business profile (Phase 1)."""
from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import urlparse

import requests

logger = logging.getLogger("wishnest.listening.business")


def analyse_business(
    *,
    website_url: str | None = None,
    description: str | None = None,
    name: str | None = None,
) -> dict[str, Any]:
    text_bits: list[str] = []
    title = name or ""
    if website_url:
        try:
            r = requests.get(
                website_url,
                timeout=15,
                headers={"User-Agent": "WishNestListeningBot/1.0 (+https://wishnest.info)"},
            )
            if r.ok:
                html = r.text[:120_000]
                m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
                if m:
                    title = re.sub(r"\s+", " ", m.group(1)).strip()[:255] or title
                # crude text extract
                body = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
                body = re.sub(r"<style[\s\S]*?</style>", " ", body, flags=re.I)
                body = re.sub(r"<[^>]+>", " ", body)
                body = re.sub(r"\s+", " ", body)
                text_bits.append(body[:8000])
        except Exception as exc:  # noqa: BLE001
            logger.warning("Website fetch failed: %s", exc)
            text_bits.append(f"(could not fetch {website_url})")
    if description:
        text_bits.append(description)
    blob = " ".join(text_bits).lower()

    category = _guess_category(blob, title)
    offerings = _guess_offerings(blob, category)
    markets = _guess_markets(blob)
    personas = _default_personas(category)

    host = ""
    if website_url:
        try:
            host = urlparse(website_url).netloc.replace("www.", "")
        except Exception:  # noqa: BLE001
            host = ""

    return {
        "business_name": title or name or host or "Business",
        "business_category": category,
        "offerings": offerings,
        "service_locations": markets,
        "target_markets": markets or ["India"],
        "buyer_personas": personas,
        "competitors": [],
        "pricing_context": None,
        "campaign_objectives": [
            "Discover high-intent public conversations",
            "Qualify opportunities with source URLs",
            "Do not contact without consent",
        ],
        "source_website": website_url,
        "notes": "Phase 1 heuristic analysis — refine in UI before running discovery.",
    }


def _guess_category(blob: str, title: str) -> str:
    checks = [
        ("architect", "Architecture"),
        ("interior", "Interior design"),
        ("villa", "Luxury villas / second homes"),
        ("second home", "Second homes"),
        ("home automation", "Home automation"),
        ("smart home", "Home automation"),
        ("furniture", "Furniture"),
        ("hotel", "Hospitality"),
        ("resort", "Hospitality"),
        ("construction", "Construction"),
        ("saas", "Software / SaaS"),
        ("crm", "Software / SaaS"),
    ]
    for k, cat in checks:
        if k in blob or k in title.lower():
            return cat
    return "General services"


def _guess_offerings(blob: str, category: str) -> list[str]:
    base = {
        "Architecture": ["Residential architecture", "Villa design", "Construction drawings"],
        "Luxury villas / second homes": ["Holiday homes", "Managed villas", "Investment properties"],
        "Home automation": ["Smart lighting", "Automation installation", "Integration"],
        "Hospitality": ["Hotels", "Resorts", "Boutique stays"],
        "Furniture": ["Custom furniture", "Furnishing packages"],
        "Software / SaaS": ["Software product", "Implementation"],
        "Construction": ["Civil works", "Project management"],
        "Interior design": ["Full interior design", "Styling"],
    }.get(category, [category])
    return base


def _guess_markets(blob: str) -> list[str]:
    cities = [
        "Dehradun", "Pune", "Goa", "Lonavala", "Mumbai", "Delhi", "Bangalore",
        "Hyderabad", "Chennai", "Jaipur", "Uttarakhand", "Maharashtra", "India",
    ]
    found = [c for c in cities if c.lower() in blob]
    return found[:8] or ["India"]


def _default_personas(category: str) -> list[dict[str, Any]]:
    return [
        {
            "segment": f"{category} buyer",
            "motivation": "Quality and trusted specialist",
            "channels": ["Reddit", "YouTube", "Forums", "Search"],
            "triggers": ["looking for", "recommend", "cost", "near me"],
        }
    ]
