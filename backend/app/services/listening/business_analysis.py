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
            r = requests.get(website_url, timeout=15, headers={"User-Agent": "WishNestListeningBot/1.0 (+https://wishnest.info)"})
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
    category = _guess_category(blob, title)
    host = ""
    if website_url:
        try:
            host = urlparse(website_url).netloc.replace("www.", "")
        except Exception:
            pass
    markets = _guess_markets(blob)
    return {
        "business_name": title or name or host or "Business",
        "business_category": category,
        "offerings": _guess_offerings(category),
        "service_locations": markets,
        "target_markets": markets or ["India"],
        "buyer_personas": [{"segment": f"{category} buyer", "triggers": ["looking for", "recommend", "cost", "chahiye"]}],
        "competitors": [],
        "campaign_objectives": ["Discover high-intent public conversations", "Qualify with source URLs", "No contact without consent"],
        "source_website": website_url,
        "notes": "Phase A heuristic analysis",
    }

def _guess_category(blob: str, title: str) -> str:
    checks = [("architect","Architecture"),("interior","Interior design"),("villa","Luxury villas / second homes"),
              ("second home","Second homes"),("home automation","Home automation"),("smart home","Home automation"),
              ("furniture","Furniture"),("hotel","Hospitality"),("resort","Hospitality"),("construction","Construction"),
              ("saas","Software / SaaS"),("crm","Software / SaaS")]
    for k, cat in checks:
        if k in blob or k in title.lower():
            return cat
    return "General services"

def _guess_offerings(category: str) -> list[str]:
    return {"Architecture":["Residential architecture","Villa design"],"Luxury villas / second homes":["Holiday homes","Managed villas"],
            "Home automation":["Smart lighting","Automation"],"Hospitality":["Hotels","Resorts"],"Furniture":["Custom furniture"],
            "Software / SaaS":["Software product"],"Construction":["Civil works"],"Interior design":["Full interiors"]}.get(category, [category])

def _guess_markets(blob: str) -> list[str]:
    cities = ["Dehradun","Pune","Goa","Lonavala","Mumbai","Delhi","Bangalore","Hyderabad","Chennai","Jaipur","Uttarakhand","Maharashtra","India"]
    found = [c for c in cities if c.lower() in blob]
    return found[:8] or ["India"]
