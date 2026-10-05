"""
Postiz social distribution engine (magazine continuous path).
Real API when POSTIZ_API_URL + POSTIZ_API_KEY are set; otherwise queues as stub.
"""
from __future__ import annotations

import logging
import os
from typing import Any

import requests

logger = logging.getLogger("wishnest.postiz")


def postiz_configured() -> bool:
    return bool(os.environ.get("POSTIZ_API_URL") and os.environ.get("POSTIZ_API_KEY"))


def queue_article_distribution(
    *,
    article_id: str,
    headline: str,
    summary: str,
    url: str,
    channels: list[str] | None = None,
) -> dict[str, Any]:
    """
    Push a social distribution job for an approved editorial piece.
    Cold outreach must NOT use this path (use AgentReach).
    """
    channels = channels or ["linkedin", "facebook", "instagram"]
    payload = {
        "type": "wishnest_editorial",
        "article_id": article_id,
        "headline": headline,
        "summary": (summary or "")[:500],
        "url": url,
        "channels": channels,
    }

    if not postiz_configured():
        logger.info("Postiz not configured — stub queue for article %s", article_id)
        return {"status": "stub_queued", "payload": payload}

    base = os.environ["POSTIZ_API_URL"].rstrip("/")
    key = os.environ["POSTIZ_API_KEY"]
    try:
        r = requests.post(
            f"{base}/api/public/v1/posts",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json=payload,
            timeout=30,
        )
        if r.status_code >= 400:
            logger.warning("Postiz API %s: %s", r.status_code, r.text[:300])
            return {"status": "error", "detail": r.text[:500], "payload": payload}
        body: Any = {}
        try:
            body = r.json() if r.content else {}
        except Exception:  # noqa: BLE001
            body = {}
        return {"status": "queued", "response": body, "payload": payload}
    except Exception as exc:  # noqa: BLE001
        logger.exception("Postiz queue failed: %s", exc)
        return {"status": "error", "detail": str(exc), "payload": payload}
