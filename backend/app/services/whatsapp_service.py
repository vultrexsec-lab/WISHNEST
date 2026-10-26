"""
WhatsApp adapter — supports:
  1) Baileys (self-hosted, free) — BAILEYS_URL + BAILEYS_API_KEY
  2) Infobip (INFOBIP_API_KEY + INFOBIP_BASE_URL + INFOBIP_WHATSAPP_FROM)
  3) Meta Cloud API (WHATSAPP_TOKEN + WHATSAPP_PHONE_NUMBER_ID)

Priority: Baileys → Infobip → Meta

Infobip free trial limits (platform, not our code):
  - Only the phone number verified at Infobip signup receives messages
"""
from __future__ import annotations

import logging
import os
import re
from typing import Any

import requests

logger = logging.getLogger("wishnest.whatsapp")

# ---------- Invitation / reply templates ----------

INVITE_MESSAGE = (
    "Hello from WishNest — we invite independent hotels & resorts to a "
    "complimentary listing on WishNest.info (no listing fee, no booking commission).\n\n"
    "Reply YES if you'd like details, or STOP to opt out."
)

REPLY_YES = (
    "Thank you. Here's a quick overview:\n\n"
    "• Complimentary editorial listing on WishNest.info\n"
    "• Focus: architecture, hospitality & guest experience\n"
    "• No fees, no commission\n\n"
    "Reply with your property name + city,\n"
    "or type CALL if you'd like us to call you back."
)

REPLY_STOP = "Understood. You won't receive further messages from WishNest. Thank you."

REPLY_CALL = "Got it. Our team will call you shortly on this number. Thank you."

REPLY_DETAILS = "Received. We'll review and get back to you soon. Thank you."

REPLY_FALLBACK = (
    "Thanks for your message. Reply YES for listing details, "
    "CALL for a callback, or STOP to opt out."
)


def _digits(phone: str) -> str:
    return "".join(c for c in (phone or "") if c.isdigit())


def baileys_configured() -> bool:
    return bool(os.environ.get("BAILEYS_URL") and os.environ.get("BAILEYS_API_KEY"))


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
    return baileys_configured() or infobip_configured() or meta_configured()


def whatsapp_provider_label() -> str:
    if baileys_configured():
        return "baileys"
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
    """Send text (or Infobip template when configured)."""
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
            "detail": "Set BAILEYS_URL + BAILEYS_API_KEY (or Infobip/Meta) on Render",
        }

    if baileys_configured():
        return _send_baileys(phone, text)

    if infobip_configured():
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


def send_invite(to_phone: str, *, dry_run: bool = False) -> dict[str, Any]:
    """Send the standard YES/STOP invitation."""
    return send_whatsapp_text(to_phone=to_phone, body=INVITE_MESSAGE, dry_run=dry_run)


def classify_inbound(text: str) -> str:
    """Return intent: yes | stop | call | details | other."""
    t = (text or "").strip().lower()
    if not t:
        return "other"
    # STOP first
    if re.search(r"\b(stop|unsubscribe|opt\s*out|रोको|बंद)\b", t):
        return "stop"
    if re.search(r"\b(yes|yeah|yep|ok|okay|interested|हाँ|हां|जी)\b", t) or t in ("y", "ha", "haan"):
        return "yes"
    if re.search(r"\b(call|callback|call\s*me|call\s*back|phone)\b", t):
        return "call"
    # Heuristic: looks like property + place
    if len(t) > 8 and any(c.isalpha() for c in t):
        return "details"
    return "other"


def handle_inbound(phone: str, text: str) -> dict[str, Any]:
    """
    Classify reply, optionally auto-reply, return intent + actions for router/DB.
    Does not write to DB itself — caller should persist.
    """
    phone = _digits(phone)
    intent = classify_inbound(text)
    auto_reply: str | None = None
    if intent == "yes":
        auto_reply = REPLY_YES
    elif intent == "stop":
        auto_reply = REPLY_STOP
    elif intent == "call":
        auto_reply = REPLY_CALL
    elif intent == "details":
        auto_reply = REPLY_DETAILS
    else:
        auto_reply = REPLY_FALLBACK

    send_result = None
    if auto_reply and phone:
        send_result = send_whatsapp_text(to_phone=phone, body=auto_reply)

    return {
        "phone": phone,
        "intent": intent,
        "text": text,
        "auto_reply": auto_reply,
        "send_result": send_result,
        "set_permission": True if intent == "yes" else False if intent == "stop" else None,
        "callback_requested": intent == "call",
        "details_received": intent == "details",
    }


# ---------- Baileys ----------

def _send_baileys(to_phone: str, text: str) -> dict[str, Any]:
    base = os.environ["BAILEYS_URL"].rstrip("/")
    key = os.environ["BAILEYS_API_KEY"]
    try:
        r = requests.post(
            f"{base}/send",
            headers={"X-API-Key": key, "Content-Type": "application/json"},
            json={"phone": to_phone, "message": text},
            timeout=45,
        )
        data = r.json() if r.content else {}
        if r.status_code >= 400:
            return {
                "status": "error",
                "provider": "baileys",
                "http_status": r.status_code,
                "detail": data,
            }
        return {
            "status": data.get("status") or "sent",
            "provider": "baileys",
            "to": to_phone,
            "messageId": data.get("messageId"),
            "response": data,
        }
    except Exception as exc:  # noqa: BLE001
        logger.exception("Baileys send failed: %s", exc)
        return {"status": "error", "provider": "baileys", "detail": str(exc)}


def baileys_health() -> dict[str, Any]:
    if not baileys_configured():
        return {"configured": False}
    base = os.environ["BAILEYS_URL"].rstrip("/")
    try:
        r = requests.get(f"{base}/health", timeout=10)
        data = r.json() if r.content else {}
        return {"configured": True, "http_status": r.status_code, **data}
    except Exception as exc:  # noqa: BLE001
        return {"configured": True, "error": str(exc)}


# ---------- Infobip ----------

def _infobip_headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"App {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _parse_infobip_result(data: Any, http_status: int) -> dict[str, Any]:
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
    if isinstance(data, dict):
        msgs = data.get("messages") or []
        if msgs:
            first = msgs[0] if isinstance(msgs[0], dict) else {}
            status = (first.get("status") or {}) if isinstance(first.get("status"), dict) else {}
            return {
                "status": "accepted",
                "provider": "infobip",
                "messageId": first.get("messageId"),
                "to": first.get("to"),
                "groupName": status.get("groupName") or status.get("name"),
                "response": data,
            }
    return {"status": "accepted", "provider": "infobip", "response": data}


def _send_infobip_text(to_phone: str, text: str) -> dict[str, Any]:
    base = os.environ["INFOBIP_BASE_URL"].rstrip("/")
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
        r = requests.post(url, headers=_infobip_headers(api_key), json=payload, timeout=30)
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
    placeholders: list[str] | None = None,
    language: str = "en",
) -> dict[str, Any]:
    base = os.environ["INFOBIP_BASE_URL"].rstrip("/")
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
                    "templateData": {"body": {"placeholders": list(placeholders or [])}},
                    "language": language or "en",
                },
            }
        ]
    }
    try:
        r = requests.post(url, headers=_infobip_headers(api_key), json=payload, timeout=30)
        data = r.json() if r.content else {}
        logger.info("Infobip WA template HTTP %s: %s", r.status_code, str(data)[:500])
        if isinstance(data, dict) and data.get("messages"):
            first = data["messages"][0]
            return _parse_infobip_result(first, r.status_code)
        return _parse_infobip_result(data, r.status_code)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Infobip WhatsApp template failed: %s", exc)
        return {"status": "error", "provider": "infobip", "detail": str(exc)}


# ---------- Meta ----------

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
