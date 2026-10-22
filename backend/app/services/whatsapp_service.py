"""
WhatsApp adapter — supports:
  1) Infobip (INFOBIP_API_KEY + INFOBIP_BASE_URL + INFOBIP_WHATSAPP_FROM)
  2) Meta Cloud API (WHATSAPP_TOKEN + WHATSAPP_PHONE_NUMBER_ID)

Infobip free trial limits (platform, not our code):
  - Only the phone number verified at Infobip signup receives messages
  - Test sender only (e.g. 447860088970)
  - Free-form text only inside 24h user-initiated window; otherwise use approved templates
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


def whatsapp_provider_label() -> str:
    if infobip_configured():
        return "infobip"
    if meta_configured():
        return "meta"
    return "none"


def send_whatsapp_text(
    *,
    to_phone: str,
    body: str,
    dry_run: bool = False,
    template_name: str | None = None,
    template_placeholders: list[str] | None = None,
    template_language: str = "en",
) -> dict[str, Any]:
    """Send text or (Infobip) template message."""
    phone = _digits(to_phone)
    if not phone:
        return {"status": "error", "detail": "invalid phone — use E.164 digits e.g. 9198XXXXXXXX"}

    text = (body or "")[:4000]
    if dry_run:
        return {
            "status": "dry_run",
            "provider": whatsapp_provider_label(),
            "to": phone,
            "text": text[:200],
            "template_name": template_name,
        }

    if not whatsapp_configured():
        logger.info("WhatsApp not configured — stub queue to %s", phone)
        return {
            "status": "stub_queued",
            "to": phone,
            "detail": "Set INFOBIP_API_KEY, INFOBIP_BASE_URL, INFOBIP_WHATSAPP_FROM on Render",
        }

    if infobip_configured():
        # Prefer explicit template when provided or when env template is set for cold outreach
        tpl = (template_name or os.environ.get("INFOBIP_WA_TEMPLATE_NAME") or "").strip()
        if tpl:
            return _send_infobip_template(
                phone,
                tpl,
                placeholders=template_placeholders or [],
                language=template_language or os.environ.get("INFOBIP_WA_TEMPLATE_LANG", "en"),
            )
        return _send_infobip_text(phone, text)
    return _send_meta(phone, text)


def _infobip_headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"App {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _parse_infobip_result(data: Any, http_status: int) -> dict[str, Any]:
    """Map Infobip response to clear status (accepted ≠ delivered)."""
    if http_status >= 400:
        return {
            "status": "error",
            "provider": "infobip",
            "http_status": http_status,
            "detail": data,
            "hint": (
                "Check API key, FROM number (must be connected sender), "
                "and that the recipient is your Infobip-verified trial number."
            ),
        }

    # Single-message text API often returns {to, messageId, status: {groupName, name, description}}
    status_obj = {}
    if isinstance(data, dict):
        status_obj = data.get("status") or {}
        if not status_obj and isinstance(data.get("messages"), list) and data["messages"]:
            status_obj = (data["messages"][0] or {}).get("status") or {}

    group = (status_obj.get("groupName") or "").upper()
    name = (status_obj.get("name") or "").upper()
    desc = status_obj.get("description") or status_obj.get("action") or ""

    # Rejected groups
    if group in ("REJECTED", "UNDELIVERABLE", "EXPIRED") or name.startswith("REJECTED"):
        return {
            "status": "rejected",
            "provider": "infobip",
            "infobip_status": name or group,
            "detail": desc or data,
            "hint": (
                "Infobip free trial only delivers to the phone verified at signup. "
                "Or free-form text needs the user to message your sender first (24h window). "
                "Use an approved template for cold outbound."
            ),
            "response": data,
        }

    # Accepted / pending — not guaranteed handset delivery
    return {
        "status": "accepted",
        "provider": "infobip",
        "infobip_status": name or group or "PENDING",
        "detail": desc or "Accepted by Infobip (check Logs for DELIVERED_TO_HANDSET)",
        "message_id": (data.get("messageId") if isinstance(data, dict) else None),
        "response": data,
        "hint": (
            "Accepted ≠ delivered. Infobip trial: only verified signup number receives WA. "
            "Open portal → Analyze / Logs. If status REJECTED_DESTINATION_NOT_REGISTERED, "
            "send only to the number you verified when creating the Infobip account."
        ),
    }


def _send_infobip_text(to_phone: str, text: str) -> dict[str, Any]:
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
            headers=_infobip_headers(api_key),
            json=payload,
            timeout=30,
        )
        data = r.json() if r.content else {}
        logger.info("Infobip WA text HTTP %s: %s", r.status_code, str(data)[:500])
        return _parse_infobip_result(data, r.status_code)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Infobip WhatsApp text failed: %s", exc)
        return {"status": "error", "provider": "infobip", "detail": str(exc)}


def _send_infobip_template(
    to_phone: str,
    template_name: str,
    *,
    placeholders: list[str],
    language: str = "en",
) -> dict[str, Any]:
    """
    POST {BASE}/whatsapp/1/message/template
    Required for business-initiated messages outside the 24h window.
    """
    base = os.environ["INFOBIP_BASE_URL"].strip().rstrip("/")
    if not base.startswith("http"):
        base = f"https://{base}"
    api_key = os.environ["INFOBIP_API_KEY"].strip()
    sender = _digits(os.environ["INFOBIP_WHATSAPP_FROM"])

    url = f"{base}/whatsapp/1/message/template"
    payload = {
        "messages": [
            {
                "from": sender,
                "to": to_phone,
                "content": {
                    "templateName": template_name,
                    "templateData": {
                        "body": {"placeholders": list(placeholders or [])},
                    },
                    "language": language or "en",
                },
            }
        ]
    }
    try:
        r = requests.post(
            url,
            headers=_infobip_headers(api_key),
            json=payload,
            timeout=30,
        )
        data = r.json() if r.content else {}
        logger.info("Infobip WA template HTTP %s: %s", r.status_code, str(data)[:500])
        # Bulk response shape: {messages: [{to, messageId, status}]}
        if isinstance(data, dict) and data.get("messages"):
            first = data["messages"][0]
            return _parse_infobip_result(first, r.status_code)
        return _parse_infobip_result(data, r.status_code)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Infobip WhatsApp template failed: %s", exc)
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
        return {"status": "accepted", "provider": "meta", "response": data}
    except Exception as exc:  # noqa: BLE001
        logger.exception("Meta WhatsApp failed: %s", exc)
        return {"status": "error", "provider": "meta", "detail": str(exc)}
