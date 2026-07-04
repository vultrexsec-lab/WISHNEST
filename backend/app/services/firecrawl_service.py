"""
Firecrawl integration — search the public web for relevant sources for a
research brief, and return their scraped markdown content + URLs so the
OpenAI drafting step has real source material to work from.

Docs: https://docs.firecrawl.dev/api-reference/endpoint/search
"""
import requests

from app.config import get_settings

FIRECRAWL_SEARCH_URL = "https://api.firecrawl.dev/v1/search"


class FirecrawlError(RuntimeError):
    pass


def search_and_scrape(query: str, limit: int = 5) -> list[dict]:
    """
    Runs a Firecrawl search for `query` and returns scraped results:
    [{ "url": str, "title": str, "content": str }, ...]

    Raises FirecrawlError on any request failure so the caller can turn it
    into a clean HTTP error.
    """
    settings = get_settings()
    if not settings.firecrawl_api_key:
        raise FirecrawlError("FIRECRAWL_API_KEY is not configured.")

    try:
        response = requests.post(
            FIRECRAWL_SEARCH_URL,
            headers={
                "Authorization": f"Bearer {settings.firecrawl_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "query": query,
                "limit": limit,
                "scrapeOptions": {"formats": ["markdown"]},
            },
            timeout=60,
        )
    except requests.RequestException as exc:
        raise FirecrawlError(f"Firecrawl request failed: {exc}") from exc

    if response.status_code != 200:
        raise FirecrawlError(
            f"Firecrawl returned {response.status_code}: {response.text[:500]}"
        )

    body = response.json()
    results = body.get("data", [])

    scraped = []
    for item in results:
        url = item.get("url")
        if not url:
            continue
        scraped.append(
            {
                "url": url,
                "title": item.get("title") or "",
                "content": (item.get("markdown") or item.get("description") or "")[:8000],
            }
        )

    return scraped
