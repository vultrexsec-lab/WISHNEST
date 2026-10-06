"""ArrowX commercial handoff — export + optional webhook (never merges into editorial)."""
from __future__ import annotations

import logging
import os
from typing import Any

import requests

logger = logging.getLogger("wishnest.arrowx")


def arrowx_webhook_configured() -> bool:
    return bool(os.environ.get("ARROWX_WEBHOOK_URL"))


def opportunity_payload(row: Any) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "source_type": row.source_type,
        "source_id": row.source_id,
        "title": row.title,
        "summary": row.summary,
        "destination": row.destination,
        "demand_signals": row.demand_signals,
        "status": row.status,
        "consent_commercial": bool(row.consent_commercial),
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def push_opportunity_webhook(payload: dict[str, Any]) -> dict[str, Any]:
    url = (os.environ.get("ARROWX_WEBHOOK_URL") or "").strip()
    if not url:
        return {"status": "stub", "note": "Set ARROWX_WEBHOOK_URL to push live"}
    secret = (os.environ.get("ARROWX_WEBHOOK_SECRET") or "").strip()
    headers = {"Content-Type": "application/json"}
    if secret:
        headers["X-WishNest-Secret"] = secret
    try:
        r = requests.post(url, json={"event": "arrowx.opportunity", "opportunity": payload}, headers=headers, timeout=30)
        if r.status_code >= 400:
            return {"status": "error", "http_status": r.status_code, "detail": r.text[:400]}
        return {"status": "sent", "http_status": r.status_code}
    except Exception as exc:  # noqa: BLE001
        logger.exception("ArrowX webhook failed: %s", exc)
        return {"status": "error", "detail": str(exc)}
