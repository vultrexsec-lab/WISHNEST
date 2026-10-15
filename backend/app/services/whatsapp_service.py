"""
WhatsApp adapter — supports:
  1) Infobip (INFOBIP_API_KEY + INFOBIP_BASE_URL + INFOBIP_WHATSAPP_FROM)
  2) Meta Cloud API (WHATSAPP_TOKEN + WHATSAPP_PHONE_NUMBER_ID)

Caller must enforce opt-in / whatsapp_permission where required.
"""
from __future__ import annotations

import logging
import os
from typing import Any

import requests

logger = logging.getLogger("wishnest.whatsapp")


def _digits(phone: str) -> str:
    return "".join(c for c in (phone or "") if c.isdigit())


def infobip_configured() -> bool:
    return bool(
        os.environ.get("INFOBIP_API_KEY")
        and os.environ.get("INFOBIP_BASE_URL")
        and os.environ.get("INFOBIP_WHATSAPP_FROM")
    )


def meta_configured() -> bool:
    return bool(
        os.environ.get("WHATSAPP_TOKEN")
        and os.environ.get("WHATSAPP_PHONE_NUMBER_ID")
    )


def whatsapp_configured() -> bool:
    return infobip_configured() or meta_configured()


def send_whatsapp_text(
    *,
    to_phone: str,
    body: str,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Send a single text message via Infobip (preferred if configured) or Meta."""
    phone = _digits(to_phone)
    if not phone:
        return {"status": "error", "detail": "invalid phone"}

    text = (body or "")[:4000]
    if dry_run:
        return {
            "status": "dry_run",
            "provider": "infobip" if infobip_configured() else "meta" if meta_configured() else "none",
            "to": phone,
            "text": text[:200],
        }

    if not whatsapp_configured():
        logger.info("WhatsApp not configured — stub queue to %s", phone)
        return {"status": "stub_queued", "to": phone, "detail": "Set INFOBIP_* or WHATSAPP_* env vars"}

    if infobip_configured():
        return _send_infobip(phone, text)
    return _send_meta(phone, text)


def _send_infobip(to_phone: str, text: str) -> dict[str, Any]:
    """
    Infobip WhatsApp text API:
    POST {BASE}/whatsapp/1/message/text
    Auth: App {API_KEY}
    """
    base = os.environ["INFOBIP_BASE_URL"].strip().rstrip("/")
    if not base.startswith("http"):
        base = f"https://{base}"
    api_key = os.environ["INFOBIP_API_KEY"].strip()
    sender = _digits(os.environ["INFOBIP_WHATSAPP_FROM"])

    url = f"{base}/whatsapp/1/message/text"
    payload = {
        "from": sender,
        "to": to_phone,
        "content": {"text": text},
    }
    try:
        r = requests.post(
            url,
            headers={
                "Authorization": f"App {api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            json=payload,
            timeout=30,
        )
        data = r.json() if r.content else {}
        if r.status_code >= 400:
            logger.warning("Infobip WA error %s: %s", r.status_code, data)
            return {
                "status": "error",
                "provider": "infobip",
                "http_status": r.status_code,
                "detail": data,
            }
        return {"status": "sent", "provider": "infobip", "response": data}
    except Exception as exc:  # noqa: BLE001
        logger.exception("Infobip WhatsApp failed: %s", exc)
        return {"status": "error", "provider": "infobip", "detail": str(exc)}


def _send_meta(to_phone: str, text: str) -> dict[str, Any]:
    base = (os.environ.get("WHATSAPP_API_BASE") or "https://graph.facebook.com/v18.0").rstrip("/")
    phone_id = os.environ["WHATSAPP_PHONE_NUMBER_ID"]
    token = os.environ["WHATSAPP_TOKEN"]
    payload = {
        "messaging_product": "whatsapp",
        "to": to_phone,
        "type": "text",
        "text": {"body": text},
    }
    try:
        r = requests.post(
            f"{base}/{phone_id}/messages",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=payload,
            timeout=30,
        )
        data = r.json() if r.content else {}
        if r.status_code >= 400:
            return {"status": "error", "provider": "meta", "detail": data, "http_status": r.status_code}
        return {"status": "sent", "provider": "meta", "response": data}
    except Exception as exc:  # noqa: BLE001
        logger.exception("Meta WhatsApp failed: %s", exc)
        return {"status": "error", "provider": "meta", "detail": str(exc)}
