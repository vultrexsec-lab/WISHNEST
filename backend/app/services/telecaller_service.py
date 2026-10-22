"""
AI telecaller adapters:
  1) Bolna.ai  — BOLNA_API_KEY + BOLNA_AGENT_ID  (optional BOLNA_FROM_NUMBER)
  2) Generic   — TELECALLER_API_URL + TELECALLER_API_KEY  POST {url}/api/v1/calls

India: outbound must follow TRAI/DLT and consent. Only call opted-in numbers.
"""
from __future__ import annotations

import logging
import os
from typing import Any

import requests

logger = logging.getLogger("wishnest.telecaller")


def _e164(phone: str) -> str:
    digits = "".join(c for c in (phone or "") if c.isdigit())
    if not digits:
        return ""
    if phone.strip().startswith("+"):
        return "+" + digits
    # India 10-digit → +91
    if len(digits) == 10 and digits.startswith(("6", "7", "8", "9")):
        return "+91" + digits
    return "+" + digits


def bolna_configured() -> bool:
    return bool(os.environ.get("BOLNA_API_KEY") and os.environ.get("BOLNA_AGENT_ID"))


def generic_configured() -> bool:
    return bool(os.environ.get("TELECALLER_API_URL") and os.environ.get("TELECALLER_API_KEY"))


def telecaller_configured() -> bool:
    return bolna_configured() or generic_configured()


def telecaller_provider_label() -> str:
    if bolna_configured():
        return "bolna"
    if generic_configured():
        return "generic"
    return "none"


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
        logger.info("Telecaller not configured — stub for %s", e164)
        return {
            "status": "stub_queued",
            "provider": "none",
            "to": e164,
            "detail": (
                "No telecaller keys on Render. Set BOLNA_API_KEY + BOLNA_AGENT_ID "
                "(recommended) or TELECALLER_API_URL + TELECALLER_API_KEY."
            ),
            "hint": "Add keys on Render → Manual Deploy, then try again.",
        }

    if bolna_configured():
        return _enqueue_bolna(
            e164,
            name=name,
            script_summary=script_summary,
            metadata=metadata or {},
        )
    return _enqueue_generic(
        e164,
        name=name,
        script_summary=script_summary,
        metadata=metadata or {},
    )


def _enqueue_bolna(
    e164: str,
    *,
    name: str | None,
    script_summary: str,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    """POST https://api.bolna.ai/call"""
    api_key = os.environ["BOLNA_API_KEY"].strip()
    agent_id = os.environ["BOLNA_AGENT_ID"].strip()
    from_num = (os.environ.get("BOLNA_FROM_NUMBER") or "").strip()

    payload: dict[str, Any] = {
        "agent_id": agent_id,
        "recipient_phone_number": e164,
    }
    if from_num:
        payload["from_phone_number"] = _e164(from_num) if not from_num.startswith("+") else from_num

    user_data: dict[str, Any] = {"script_notes": (script_summary or "")[:500]}
    if name:
        user_data["name"] = name
    if metadata:
        user_data.update({k: str(v)[:200] for k, v in list(metadata.items())[:10]})
    payload["user_data"] = user_data

    try:
        r = requests.post(
            "https://api.bolna.ai/call",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=45,
        )
        data = r.json() if r.content else {}
        logger.info("Bolna call HTTP %s: %s", r.status_code, str(data)[:400])
        if r.status_code >= 400:
            return {
                "status": "error",
                "provider": "bolna",
                "http_status": r.status_code,
                "detail": data if data else r.text[:400],
                "to": e164,
                "hint": (
                    "Check BOLNA_API_KEY, BOLNA_AGENT_ID, credits, and that agent is live. "
                    "recipient must be E.164 (+91...). India: DND/TRAI may block some numbers."
                ),
            }
        return {
            "status": "queued",
            "provider": "bolna",
            "to": e164,
            "response": data,
            "execution_id": data.get("execution_id") or data.get("id"),
            "detail": "Call queued at Bolna — phone should ring if credits + agent + telephony OK",
        }
    except Exception as exc:  # noqa: BLE001
        logger.exception("Bolna enqueue failed: %s", exc)
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
        logger.exception("Telecaller enqueue failed: %s", exc)
        return {"status": "error", "provider": "generic", "detail": str(exc), "to": e164}
