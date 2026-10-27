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

# ---------- Invitation / multi-step conversation templates ----------

INVITE_MESSAGE = (
    "Hello from WishNest — we invite independent hotels & resorts to a "
    "complimentary listing on WishNest.info (no listing fee, no booking commission).\n\n"
    "Reply YES if you'd like details, or STOP to opt out."
)

MSG_AFTER_YES = (
    "Thank you. Here's a quick overview:\n\n"
    "• Complimentary editorial listing on WishNest.info\n"
    "• Focus: architecture, hospitality & guest experience\n"
    "• No fees, no commission\n\n"
    "Please reply with your *property name and city* "
    "(e.g. Amanbagh, Rajasthan)."
)

MSG_ASK_TYPE = (
    "Got it — thanks.\n\n"
    "What type of property is it?\n"
    "Reply with one: hotel / resort / villa / retreat / other."
)

MSG_ASK_CALL = (
    "Perfect.\n\n"
    "When should our team call you for a short conversation?\n"
    "Reply with a preferred day/time "
    "(e.g. tomorrow 11am, or Thu 4pm IST)."
)

MSG_SCHEDULED = (
    "Thank you — we've noted your preferred time.\n\n"
    "Our team will call you shortly on this number about the complimentary listing. "
    "No obligation.\n\n"
    "— WishNest"
)

MSG_STOP = "Understood. You won't receive further messages from WishNest. Thank you."
MSG_CALL_NOW = "Got it. Our team will call you shortly on this number. Thank you."
MSG_FALLBACK_STEP0 = (
    "Thanks for your message. Reply *YES* for listing details, "
    "*CALL* for a callback, or *STOP* to opt out."
)
MSG_FALLBACK_IN_FLOW = (
    "Thanks — please reply to the last question, "
    "or type *CALL* for a callback / *STOP* to opt out."
)

REPLY_YES = MSG_AFTER_YES
REPLY_STOP = MSG_STOP
REPLY_CALL = MSG_CALL_NOW
REPLY_DETAILS = MSG_ASK_TYPE
REPLY_FALLBACK = MSG_FALLBACK_STEP0


def _digits(phone: str) -> str:
    return "".join(c for c in (phone or "") if c.isdigit())



def normalize_wa_phone(phone: str) -> str:
    """E.164 digits. 10-digit Indian numbers get 91 prefix."""
    d = _digits(phone)
    if len(d) == 10 and d[0] in "6789":
        d = "91" + d
    return d


def yes_link_for(phone: str) -> str:
    import os
    base = (
        os.environ.get("PUBLIC_API_BASE")
        or os.environ.get("BACKEND_PUBLIC_URL")
        or "https://wishnest-backend-kgu2.onrender.com"
    ).rstrip("/")
    d = normalize_wa_phone(phone)
    return f"{base}/api/public/wa-yes?p={d}"



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
    phone = normalize_wa_phone(to_phone)
    if not phone or len(phone) < 10:
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


def build_invite_message(to_phone: str) -> str:
    """Invite text + one-tap YES link (backup when WA inbound decrypt fails)."""
    phone = normalize_wa_phone(to_phone)
    link = yes_link_for(phone)
    return (
        "Hello from WishNest — we invite independent hotels & resorts to a "
        "complimentary listing on WishNest.info (no listing fee, no booking commission).\n\n"
        "Reply *YES* if you'd like details, or *STOP* to opt out.\n\n"
        f"Or tap here for YES: {link}"
    )


def send_invite(to_phone: str, *, dry_run: bool = False) -> dict[str, Any]:
    """Send the standard YES/STOP invitation (with web YES backup link)."""
    body = build_invite_message(to_phone)
    return send_whatsapp_text(to_phone=to_phone, body=body, dry_run=dry_run)



def classify_inbound(text: str) -> str:
    """Return intent: yes | stop | call | other."""
    t = (text or "").strip().lower()
    if not t:
        return "other"
    if re.search(r"\b(stop|unsubscribe|opt\s*out|रोको|बंद)\b", t):
        return "stop"
    if re.search(r"\b(call|callback|call\s*me|call\s*back)\b", t):
        return "call"
    if re.search(r"\b(yes|yeah|yep|ok|okay|interested|हाँ|हां|जी)\b", t) or t in ("y", "ha", "haan"):
        return "yes"
    return "other"


def handle_inbound(
    phone: str,
    text: str,
    *,
    current_step: int = 0,
    wa_meta: dict | None = None,
) -> dict[str, Any]:
    """
    Multi-step conversation (auto-reply, no human needed):

      0  await YES/STOP/CALL
      1  await property name + city
      2  await property type
      3  await preferred call time
      4  done (scheduled)

    Returns fields for the router to persist on contact.meta / flags.
    """
    phone = _digits(phone)
    raw = (text or "").strip()
    intent = classify_inbound(raw)
    step = int(current_step or 0)
    meta = dict(wa_meta or {})
    collected = dict(meta.get("collected") or {})

    auto_reply: str | None = None
    next_step = step
    set_permission: bool | None = None
    callback_requested = False
    details_received = False
    scheduled = False

    # Global overrides
    if intent == "stop":
        auto_reply = MSG_STOP
        next_step = 0
        set_permission = False
    elif intent == "call":
        auto_reply = MSG_CALL_NOW
        next_step = 4
        set_permission = True if step >= 1 else None
        callback_requested = True
        scheduled = True
    elif step == 0:
        if intent == "yes":
            auto_reply = MSG_AFTER_YES
            next_step = 1
            set_permission = True
        else:
            auto_reply = MSG_FALLBACK_STEP0
    elif step == 1:
        # property name + city
        if len(raw) < 3:
            auto_reply = MSG_FALLBACK_IN_FLOW
        else:
            collected["property"] = raw[:500]
            auto_reply = MSG_ASK_TYPE
            next_step = 2
            details_received = True
            set_permission = True
    elif step == 2:
        collected["property_type"] = raw[:200]
        auto_reply = MSG_ASK_CALL
        next_step = 3
        set_permission = True
    elif step == 3:
        collected["preferred_call_time"] = raw[:300]
        auto_reply = MSG_SCHEDULED
        next_step = 4
        callback_requested = True
        scheduled = True
        set_permission = True
    else:
        # step >= 4 done
        auto_reply = (
            "We've already noted your details. Our team will be in touch. "
            "Type STOP if you no longer wish to hear from us."
        )

    meta["wa_step"] = next_step
    meta["collected"] = collected
    if scheduled:
        meta["callback_status"] = "queued"

    # Do not send here — Baileys service sends the auto_reply to avoid doubles / missed webhooks
    send_result = None

    return {
        "phone": phone,
        "intent": intent,
        "text": raw,
        "step": step,
        "next_step": next_step,
        "auto_reply": auto_reply,
        "send_result": send_result,
        "set_permission": set_permission,
        "callback_requested": callback_requested,
        "details_received": details_received,
        "scheduled": scheduled,
        "meta": meta,
        "collected": collected,
    }


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
