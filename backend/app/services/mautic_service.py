"""
Mautic adapter — opted-in nurture CRM (NOT cold outreach; that is AgentReach).

Env:
  MAUTIC_BASE_URL=https://mautic.example.com
  MAUTIC_USER=...
  MAUTIC_PASSWORD=...   # or MAUTIC_API_TOKEN for bearer

When unset, sync is a no-op stub so WishNest master contacts still work.
"""
from __future__ import annotations

import logging
import os
from typing import Any

import requests

logger = logging.getLogger("wishnest.mautic")


def mautic_configured() -> bool:
    base = (os.environ.get("MAUTIC_BASE_URL") or "").strip()
    user = (os.environ.get("MAUTIC_USER") or "").strip()
    password = (os.environ.get("MAUTIC_PASSWORD") or "").strip()
    token = (os.environ.get("MAUTIC_API_TOKEN") or "").strip()
    return bool(base and (token or (user and password)))


def _auth() -> tuple[str, dict[str, str] | None, tuple[str, str] | None]:
    base = (os.environ.get("MAUTIC_BASE_URL") or "").rstrip("/")
    token = (os.environ.get("MAUTIC_API_TOKEN") or "").strip()
    if token:
        return base, {"Authorization": f"Bearer {token}"}, None
    user = (os.environ.get("MAUTIC_USER") or "").strip()
    password = (os.environ.get("MAUTIC_PASSWORD") or "").strip()
    return base, None, (user, password)


def upsert_contact(
    *,
    email: str | None,
    first_name: str | None = None,
    last_name: str | None = None,
    phone: str | None = None,
    company: str | None = None,
    tags: list[str] | None = None,
    custom: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create/update a Mautic contact by email. Returns status + external id if any."""
    if not email:
        return {"status": "skipped", "reason": "no_email"}
    if not mautic_configured():
        logger.info("Mautic not configured — stub sync for %s", email)
        return {"status": "stub_synced", "email": email}

    base, headers, basic = _auth()
    payload: dict[str, Any] = {"email": email}
    if first_name:
        payload["firstname"] = first_name
    if last_name:
        payload["lastname"] = last_name
    if phone:
        payload["mobile"] = phone
        payload["phone"] = phone
    if company:
        payload["company"] = company
    if tags:
        payload["tags"] = tags
    if custom:
        payload.update(custom)

    try:
        # Mautic REST: POST /api/contacts/new
        r = requests.post(
            f"{base}/api/contacts/new",
            json=payload,
            headers=headers or {"Content-Type": "application/json"},
            auth=basic,
            timeout=30,
        )
        if r.status_code >= 400:
            logger.warning("Mautic upsert %s: %s", r.status_code, r.text[:400])
            return {"status": "error", "detail": r.text[:500]}
        data = r.json() if r.content else {}
        contact = (data.get("contact") or data) if isinstance(data, dict) else {}
        cid = contact.get("id")
        return {"status": "synced", "external_mautic_id": str(cid) if cid else None, "raw": data}
    except Exception as exc:  # noqa: BLE001
        logger.exception("Mautic upsert failed: %s", exc)
        return {"status": "error", "detail": str(exc)}
