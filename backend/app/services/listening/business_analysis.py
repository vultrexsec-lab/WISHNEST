from __future__ import annotations
import logging, re
from typing import Any
from urllib.parse import urlparse
import requests
logger = logging.getLogger("wishnest.listening.business")

def analyse_business(*, website_url: str | None = None, description: str | None = None, name: str | None = None) -> dict[str, Any]:
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
                body = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
                body = re.sub(r"<style[\s\S]*?</style>", " ", body, flags=re.I)
                body = re.sub(r"<[^>]+>", " ", body)
                body = re.sub(r"\s+", " ", body)
                text_bits.append(body[:8000])
        except Exception as exc:
            logger.warning("Website fetch failed: %s", exc)
            text_bits.append(f"(could not fetch {website_url})")
    if description:
        text_bits.append(description)
    blob = " ".join(text_bits).lower()
    host = ""
    if website_url:
        try:
            host = urlparse(website_url).netloc.replace("www.", "").lower()
        except Exception:
            pass
    # Domain-specific boosts
    if "wishnest" in host or "wishnest" in (name or "").lower() or "wishnest" in blob:
        blob += " hospitality architecture second home villa resort hotel reimagined design intelligence"
        if not description:
            text_bits.append(
                "WishNest hospitality architecture second home intelligence reviews resorts villas design"
            )
            blob = " ".join(text_bits).lower() + " hospitality architecture second home villa resort hotel"
    category = _guess_category(blob, title, host)
    markets = _guess_markets(blob)
    return {
        "business_name": title or name or host or "Business",
        "business_category": category,
        "offerings": _guess_offerings(category),
        "service_locations": markets,
        "target_markets": markets or ["India"],
        "buyer_personas": [
            {
                "segment": f"{category} decision maker",
                "triggers": ["looking for", "recommend", "quotation", "architect", "chahiye"],
            }
        ],
        "competitors": [],
        "campaign_objectives": [
            "Discover high-intent public conversations",
            "Qualify with source URLs",
            "No contact without consent",
        ],
        "source_website": website_url,
        "notes": "Phase A analysis",
    }

def _guess_category(blob: str, title: str, host: str = "") -> str:
    t = f"{blob} {title} {host}".lower()
    checks = [
        ("wishnest", "Hospitality · architecture · second homes"),
        ("second home", "Luxury villas / second homes"),
        ("reimagined", "Hospitality · architecture · second homes"),
        ("architect", "Architecture"),
        ("interior", "Interior design"),
        ("villa", "Luxury villas / second homes"),
        ("hospitality", "Hospitality"),
        ("hotel", "Hospitality"),
        ("resort", "Hospitality"),
        ("home automation", "Home automation"),
        ("smart home", "Home automation"),
        ("furniture", "Furniture"),
        ("construction", "Construction"),
        ("saas", "Software / SaaS"),
        ("crm", "Software / SaaS"),
    ]
    for k, cat in checks:
        if k in t:
            return cat
    return "General services"

def _guess_offerings(category: str) -> list[str]:
    mapping = {
        "Hospitality · architecture · second homes": [
            "Hospitality design intelligence",
            "Resort & hotel reviews",
            "Second-home / villa insight",
            "Reimagined property concepts",
        ],
        "Architecture": ["Residential architecture", "Villa design"],
        "Luxury villas / second homes": ["Holiday homes", "Managed villas", "Second homes"],
        "Home automation": ["Smart lighting", "Automation"],
        "Hospitality": ["Hotels", "Resorts", "Boutique stays"],
        "Furniture": ["Custom furniture"],
        "Software / SaaS": ["Software product"],
        "Construction": ["Civil works"],
        "Interior design": ["Full interiors"],
    }
    return mapping.get(category, [category])

def _guess_markets(blob: str) -> list[str]:
    cities = [
        "Dehradun", "Pune", "Goa", "Lonavala", "Mumbai", "Delhi", "Bangalore",
        "Hyderabad", "Chennai", "Jaipur", "Uttarakhand", "Maharashtra",
        "Alibaug", "Mussoorie", "India",
    ]
    found = [c for c in cities if c.lower() in blob]
    return found[:8] or ["India"]
