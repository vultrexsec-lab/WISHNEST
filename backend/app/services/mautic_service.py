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


def _request(
    method: str,
    path: str,
    *,
    json_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not mautic_configured():
        return {"status": "stub", "path": path, "body": json_body}
    base, headers, basic = _auth()
    hdrs = dict(headers or {})
    hdrs.setdefault("Content-Type", "application/json")
    try:
        r = requests.request(
            method,
            f"{base}{path}",
            json=json_body,
            headers=hdrs,
            auth=basic,
            timeout=45,
        )
        data: Any = {}
        try:
            data = r.json() if r.content else {}
        except Exception:  # noqa: BLE001
            data = {"text": r.text[:500]}
        if r.status_code >= 400:
            logger.warning("Mautic %s %s → %s %s", method, path, r.status_code, str(data)[:400])
            return {"status": "error", "http_status": r.status_code, "detail": data}
        return {"status": "ok", "http_status": r.status_code, "data": data}
    except Exception as exc:  # noqa: BLE001
        logger.exception("Mautic request failed: %s", exc)
        return {"status": "error", "detail": str(exc)}


def create_email_draft(
    *,
    name: str,
    subject: str,
    html_body: str,
    from_name: str = "WishNest",
) -> dict[str, Any]:
    """
    Create a Mautic email as draft (isPublished false).
    Human still activates/sends inside Mautic or via later API.
    """
    payload = {
        "name": name[:100],
        "subject": subject[:150],
        "customHtml": html_body,
        "emailType": "list",
        "isPublished": 0,
        "fromName": from_name,
        "language": "en",
    }
    if not mautic_configured():
        logger.info("Mautic not configured — stub email draft %r", name)
        return {
            "status": "stub_email_draft",
            "name": name,
            "subject": subject,
            "note": "Set MAUTIC_BASE_URL + credentials to create real drafts",
        }
    result = _request("POST", "/api/emails/new", json_body=payload)
    if result.get("status") == "ok":
        email_obj = (result.get("data") or {}).get("email") or result.get("data") or {}
        eid = email_obj.get("id")
        return {
            "status": "created_draft",
            "mautic_email_id": str(eid) if eid else None,
            "raw": result.get("data"),
        }
    return result


def push_campaign_email_pack(
    *,
    campaign_name: str,
    subjects: list[str],
    bodies: list[str],
    follow_ups: list[str] | None = None,
) -> dict[str, Any]:
    """
    Push each subject/body pair as a separate Mautic email draft.
    Does not send. Returns list of draft results.
    """
    drafts: list[dict[str, Any]] = []
    pairs: list[tuple[str, str]] = []
    for i, body in enumerate(bodies or []):
        subj = subjects[i] if i < len(subjects) else (subjects[0] if subjects else campaign_name)
        pairs.append((subj, body))
    for i, body in enumerate(follow_ups or []):
        subj = f"Follow-up {i + 1}: {subjects[0] if subjects else campaign_name}"
        pairs.append((subj, body))

    if not pairs:
        return {"status": "error", "detail": "No email bodies in pack"}

    for idx, (subj, body) in enumerate(pairs):
        html = body if "<" in body else f"<html><body><p>{body.replace(chr(10), '<br/>')}</p></body></html>"
        name = f"{campaign_name[:60]} · {idx + 1}"
        drafts.append(
            create_email_draft(name=name, subject=subj, html_body=html)
        )

    ok = sum(1 for d in drafts if d.get("status") in ("created_draft", "stub_email_draft"))
    return {
        "status": "ok" if ok else "error",
        "drafts_created": ok,
        "drafts": drafts,
        "mautic_configured": mautic_configured(),
    }
