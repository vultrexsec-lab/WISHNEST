"""
Postiz social distribution engine.

Magazine continuous path: approved article → SEO/GEO → queue_article_distribution
Campaign path: approved social captions → queue_social_posts

Cold outreach must NOT use this module (AgentReach).
Env:
  POSTIZ_API_URL
  POSTIZ_API_KEY
  POSTIZ_POSTS_PATH  (optional, default /api/public/v1/posts)
"""
from __future__ import annotations

import logging
import os
from typing import Any

import requests

logger = logging.getLogger("wishnest.postiz")


def postiz_configured() -> bool:
    return bool(os.environ.get("POSTIZ_API_URL") and os.environ.get("POSTIZ_API_KEY"))


def _posts_url() -> str:
    base = os.environ["POSTIZ_API_URL"].rstrip("/")
    path = (os.environ.get("POSTIZ_POSTS_PATH") or "/api/public/v1/posts").strip()
    if not path.startswith("/"):
        path = "/" + path
    return f"{base}{path}"


def _post_to_postiz(payload: dict[str, Any]) -> dict[str, Any]:
    if not postiz_configured():
        logger.info("Postiz not configured — stub queue: %s", payload.get("type"))
        return {"status": "stub_queued", "payload": payload}

    key = os.environ["POSTIZ_API_KEY"]
    try:
        r = requests.post(
            _posts_url(),
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=45,
        )
        body: Any = {}
        try:
            body = r.json() if r.content else {}
        except Exception:  # noqa: BLE001
            body = {"text": r.text[:500]}
        if r.status_code >= 400:
            logger.warning("Postiz API %s: %s", r.status_code, str(body)[:400])
            return {
                "status": "error",
                "http_status": r.status_code,
                "detail": body,
                "payload": payload,
            }
        return {"status": "queued", "response": body, "payload": payload}
    except Exception as exc:  # noqa: BLE001
        logger.exception("Postiz queue failed: %s", exc)
        return {"status": "error", "detail": str(exc), "payload": payload}


def queue_article_distribution(
    *,
    article_id: str,
    headline: str,
    summary: str,
    url: str,
    channels: list[str] | None = None,
) -> dict[str, Any]:
    """Magazine continuous: one editorial piece → multi-channel social job."""
    channels = channels or ["linkedin", "facebook", "instagram"]
    content = f"{headline}\n\n{(summary or '')[:400]}\n\n{url}".strip()
    payload = {
        "type": "wishnest_editorial",
        "source": "magazine",
        "article_id": article_id,
        "headline": headline,
        "summary": (summary or "")[:500],
        "url": url,
        "content": content,
        "channels": channels,
        # Common self-hosted scheduler fields (ignored if unsupported)
        "schedule": "now",
        "draft": False,
    }
    return _post_to_postiz(payload)


def queue_social_posts(
    *,
    campaign_id: str,
    campaign_name: str,
    posts: list[str],
    channels: list[str] | None = None,
    cta_url: str | None = None,
) -> dict[str, Any]:
    """
    Campaign Manager social path: push each caption as a Postiz job.
    Does not replace AgentReach cold sequences.
    """
    channels = channels or ["linkedin", "instagram", "facebook"]
    if not posts:
        return {"status": "error", "detail": "No social posts in pack"}

    results: list[dict[str, Any]] = []
    for i, text in enumerate(posts):
        body = text.strip()
        if cta_url and cta_url not in body:
            body = f"{body}\n\n{cta_url}"
        payload = {
            "type": "wishnest_campaign_social",
            "source": "campaign_manager",
            "campaign_id": campaign_id,
            "campaign_name": campaign_name,
            "index": i,
            "content": body,
            "channels": channels,
            "schedule": "now",
            "draft": True,  # safer default for campaign packs until human publishes in Postiz
        }
        results.append(_post_to_postiz(payload))

    ok = sum(1 for r in results if r.get("status") in ("queued", "stub_queued"))
    return {
        "status": "ok" if ok else "error",
        "posts_queued": ok,
        "results": results,
        "postiz_configured": postiz_configured(),
    }


def queue_linkedin_posts(
    *,
    campaign_id: str,
    campaign_name: str,
    posts: list[str],
    cta_url: str | None = None,
) -> dict[str, Any]:
    return queue_social_posts(
        campaign_id=campaign_id,
        campaign_name=campaign_name,
        posts=posts,
        channels=["linkedin"],
        cta_url=cta_url,
    )
