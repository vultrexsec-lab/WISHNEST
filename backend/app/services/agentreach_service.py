"""
AgentReach — cold first-contact sequences (e.g. resort owners).
Separate from Mautic opted-in nurture. No bulk send without human approval.
"""
from __future__ import annotations

import logging
import os
from typing import Any

import requests

logger = logging.getLogger("wishnest.agentreach")


def agentreach_configured() -> bool:
    return bool(os.environ.get("AGENTREACH_API_URL") and os.environ.get("AGENTREACH_API_KEY"))


def create_cold_sequence_draft(
    *,
    campaign_name: str,
    audience_label: str,
    geography: str,
    offer: str,
    messages: list[str],
    contact_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Create a draft cold sequence — never auto-sends."""
    draft = {
        "campaign_name": campaign_name,
        "audience": audience_label,
        "geography": geography,
        "offer": offer,
        "messages": messages,
        "contact_ids": contact_ids or [],
        "status": "draft_pending_approval",
        "channel": "agentreach_cold",
    }
    if not agentreach_configured():
        logger.info("AgentReach stub draft: %s", campaign_name)
        return {"status": "stub_draft", "draft": draft}

    base = os.environ["AGENTREACH_API_URL"].rstrip("/")
    key = os.environ["AGENTREACH_API_KEY"]
    try:
        r = requests.post(
            f"{base}/api/v1/sequences",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json=draft,
            timeout=30,
        )
        if r.status_code >= 400:
            return {"status": "error", "detail": r.text[:500], "draft": draft}
        data = r.json() if r.content else {}
        return {"status": "draft", "draft": draft, "external": data}
    except Exception as exc:  # noqa: BLE001
        logger.exception("AgentReach draft failed: %s", exc)
        return {"status": "error", "detail": str(exc), "draft": draft}


def submit_approved_sequence(payload: dict[str, Any]) -> dict[str, Any]:
    """Submit an already human-approved sequence to AgentReach (still vendor-side controls)."""
    if not agentreach_configured():
        return {"status": "stub_submitted", "payload": payload}
    base = os.environ["AGENTREACH_API_URL"].rstrip("/")
    key = os.environ["AGENTREACH_API_KEY"]
    try:
        r = requests.post(
            f"{base}/api/v1/sequences/activate",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json=payload,
            timeout=30,
        )
        if r.status_code >= 400:
            return {"status": "error", "detail": r.text[:500]}
        return {"status": "submitted", "response": r.json() if r.content else {}}
    except Exception as exc:  # noqa: BLE001
        logger.exception("AgentReach submit failed: %s", exc)
        return {"status": "error", "detail": str(exc)}
