"""
WhatsApp Business API adapter (opted-in only).
Env: WHATSAPP_TOKEN, WHATSAPP_PHONE_NUMBER_ID, WHATSAPP_API_BASE (optional Graph URL)
"""
from __future__ import annotations

import logging
import os
from typing import Any

import requests

logger = logging.getLogger("wishnest.whatsapp")


def whatsapp_configured() -> bool:
    return bool(
        os.environ.get("WHATSAPP_TOKEN")
        and os.environ.get("WHATSAPP_PHONE_NUMBER_ID")
    )


def send_whatsapp_text(
    *,
    to_phone: str,
    body: str,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Send a single text message. Caller must enforce whatsapp_permission."""
    phone = "".join(c for c in (to_phone or "") if c.isdigit() or c == "+")
    if not phone:
        return {"status": "error", "detail": "invalid phone"}
    payload = {
        "messaging_product": "whatsapp",
        "to": phone.lstrip("+"),
        "type": "text",
        "text": {"body": body[:4000]},
    }
    if dry_run or not whatsapp_configured():
        logger.info("WhatsApp stub/dry_run to %s", phone)
        return {"status": "stub_queued" if not whatsapp_configured() else "dry_run", "payload": payload}

    base = (os.environ.get("WHATSAPP_API_BASE") or "https://graph.facebook.com/v18.0").rstrip("/")
    phone_id = os.environ["WHATSAPP_PHONE_NUMBER_ID"]
    token = os.environ["WHATSAPP_TOKEN"]
    try:
        r = requests.post(
            f"{base}/{phone_id}/messages",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=payload,
            timeout=30,
        )
        data = r.json() if r.content else {}
        if r.status_code >= 400:
            return {"status": "error", "detail": data, "http_status": r.status_code}
        return {"status": "sent", "response": data}
    except Exception as exc:  # noqa: BLE001
        logger.exception("WhatsApp send failed: %s", exc)
        return {"status": "error", "detail": str(exc)}
