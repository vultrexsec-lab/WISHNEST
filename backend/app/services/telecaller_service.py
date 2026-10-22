"""
AI telecaller adapters (priority order):
  1) Vapi.ai — VAPI_API_KEY + VAPI_ASSISTANT_ID + VAPI_PHONE_NUMBER_ID
  2) Bolna.ai — BOLNA_API_KEY + BOLNA_AGENT_ID
  3) Generic — TELECALLER_API_URL + TELECALLER_API_KEY

Vapi: free Vapi numbers are inbound-only. Outbound needs imported Twilio/Telnyx/DIDWW number.
"""
from __future__ import annotations

import logging
import os
from typing import Any

import requests

logger = logging.getLogger("wishnest.telecaller")


def _e164(phone: str) -> str:
    raw = (phone or "").strip()
    digits = "".join(c for c in raw if c.isdigit())
    if not digits:
        return ""
    if raw.startswith("+"):
        return "+" + digits
    if len(digits) == 10 and digits[0] in "6789":
        return "+91" + digits
    return "+" + digits


def vapi_configured() -> bool:
    return bool(
        os.environ.get("VAPI_API_KEY")
        and os.environ.get("VAPI_ASSISTANT_ID")
        and os.environ.get("VAPI_PHONE_NUMBER_ID")
    )


def bolna_configured() -> bool:
    return bool(os.environ.get("BOLNA_API_KEY") and os.environ.get("BOLNA_AGENT_ID"))


def generic_configured() -> bool:
    return bool(os.environ.get("TELECALLER_API_URL") and os.environ.get("TELECALLER_API_KEY"))


def telecaller_configured() -> bool:
    return vapi_configured() or bolna_configured() or generic_configured()


def enqueue_call(
    *,
    phone: str,
    name: str | None,
    script_summary: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    e164 = _e164(phone)
    if not e164 or len(e164) < 10:
        return {
            "status": "error",
            "detail": "Invalid phone — use E.164 e.g. 917146396887 or +917146396887",
        }

    if not telecaller_configured():
        return {
            "status": "stub_queued",
            "provider": "none",
            "to": e164,
            "detail": (
                "No call provider keys on Render. For Vapi set: "
                "VAPI_API_KEY, VAPI_ASSISTANT_ID, VAPI_PHONE_NUMBER_ID"
            ),
            "hint": (
                "Vapi free numbers cannot dial outbound — import Twilio/Telnyx number first. "
                "Then Manual Deploy after saving env."
            ),
        }

    if vapi_configured():
        return _enqueue_vapi(e164, name=name, script_summary=script_summary, metadata=metadata or {})
    if bolna_configured():
        return _enqueue_bolna(e164, name=name, script_summary=script_summary, metadata=metadata or {})
    return _enqueue_generic(e164, name=name, script_summary=script_summary, metadata=metadata or {})


def _enqueue_vapi(
    e164: str,
    *,
    name: str | None,
    script_summary: str,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    api_key = os.environ["VAPI_API_KEY"].strip()
    assistant_id = os.environ["VAPI_ASSISTANT_ID"].strip()
    phone_number_id = os.environ["VAPI_PHONE_NUMBER_ID"].strip()

    customer: dict[str, Any] = {"number": e164}
    if name:
        customer["name"] = name

    payload: dict[str, Any] = {
        "assistantId": assistant_id,
        "phoneNumberId": phone_number_id,
        "customer": customer,
    }
    if script_summary:
        payload["assistantOverrides"] = {
            "variableValues": {
                "script_notes": script_summary[:500],
                **{k: str(v)[:100] for k, v in list(metadata.items())[:5]},
            }
        }

    try:
        r = requests.post(
            "https://api.vapi.ai/call",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=45,
        )
        data = r.json() if r.content else {}
        logger.info("Vapi call HTTP %s: %s", r.status_code, str(data)[:500])
        if r.status_code >= 400:
            msg = data.get("message") if isinstance(data, dict) else None
            return {
                "status": "error",
                "provider": "vapi",
                "http_status": r.status_code,
                "detail": data if data else r.text[:400],
                "to": e164,
                "hint": (
                    str(msg)
                    if msg
                    else "Check VAPI_API_KEY (private), VAPI_ASSISTANT_ID, VAPI_PHONE_NUMBER_ID. "
                    "Free Vapi numbers cannot outbound — import Twilio/Telnyx. Credits > 0 required."
                ),
            }
        return {
            "status": "queued",
            "provider": "vapi",
            "to": e164,
            "call_id": data.get("id") if isinstance(data, dict) else None,
            "response": data,
            "detail": "Call created on Vapi — check dashboard.vapi.ai Calls / Logs",
        }
    except Exception as exc:  # noqa: BLE001
        logger.exception("Vapi enqueue failed: %s", exc)
        return {"status": "error", "provider": "vapi", "detail": str(exc), "to": e164}


def _enqueue_bolna(
    e164: str,
    *,
    name: str | None,
    script_summary: str,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    api_key = os.environ["BOLNA_API_KEY"].strip()
    agent_id = os.environ["BOLNA_AGENT_ID"].strip()
    from_num = (os.environ.get("BOLNA_FROM_NUMBER") or "").strip()
    payload: dict[str, Any] = {
        "agent_id": agent_id,
        "recipient_phone_number": e164,
    }
    if from_num:
        payload["from_phone_number"] = _e164(from_num)
    user_data: dict[str, Any] = {"script_notes": (script_summary or "")[:500]}
    if name:
        user_data["name"] = name
    payload["user_data"] = user_data
    try:
        r = requests.post(
            "https://api.bolna.ai/call",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=45,
        )
        data = r.json() if r.content else {}
        if r.status_code >= 400:
            return {
                "status": "error",
                "provider": "bolna",
                "http_status": r.status_code,
                "detail": data if data else r.text[:400],
                "to": e164,
            }
        return {
            "status": "queued",
            "provider": "bolna",
            "to": e164,
            "response": data,
            "execution_id": data.get("execution_id") or data.get("id"),
        }
    except Exception as exc:  # noqa: BLE001
        logger.exception("Bolna failed: %s", exc)
        return {"status": "error", "provider": "bolna", "detail": str(exc), "to": e164}


def _enqueue_generic(
    e164: str,
    *,
    name: str | None,
    script_summary: str,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    base = os.environ["TELECALLER_API_URL"].rstrip("/")
    key = os.environ["TELECALLER_API_KEY"]
    payload = {
        "phone": e164,
        "name": name,
        "script": (script_summary or "")[:2000],
        "metadata": metadata,
    }
    try:
        r = requests.post(
            f"{base}/api/v1/calls",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json=payload,
            timeout=30,
        )
        if r.status_code >= 400:
            return {
                "status": "error",
                "provider": "generic",
                "detail": r.text[:500],
                "http_status": r.status_code,
                "to": e164,
            }
        return {
            "status": "queued",
            "provider": "generic",
            "to": e164,
            "response": r.json() if r.content else {},
        }
    except Exception as exc:  # noqa: BLE001
        logger.exception("Generic telecaller failed: %s", exc)
        return {"status": "error", "provider": "generic", "detail": str(exc), "to": e164}
