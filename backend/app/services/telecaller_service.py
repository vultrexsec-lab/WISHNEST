"""
AI telecaller queue adapter (Bolna / LiveKit-style).
Env: TELECALLER_API_URL, TELECALLER_API_KEY
Only enqueue contacts with phone_permission and not suppressed.
"""
from __future__ import annotations

import logging
import os
from typing import Any

import requests

logger = logging.getLogger("wishnest.telecaller")


def telecaller_configured() -> bool:
    return bool(os.environ.get("TELECALLER_API_URL") and os.environ.get("TELECALLER_API_KEY"))


def enqueue_call(
    *,
    phone: str,
    name: str | None,
    script_summary: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "phone": phone,
        "name": name,
        "script": script_summary[:2000],
        "metadata": metadata or {},
        "status": "queued",
    }
    if not telecaller_configured():
        logger.info("Telecaller stub queue for %s", phone)
        return {"status": "stub_queued", "payload": payload}

    base = os.environ["TELECALLER_API_URL"].rstrip("/")
    key = os.environ["TELECALLER_API_KEY"]
    try:
        r = requests.post(
            f"{base}/api/v1/calls",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json=payload,
            timeout=30,
        )
        if r.status_code >= 400:
            return {"status": "error", "detail": r.text[:500]}
        return {"status": "queued", "response": r.json() if r.content else {}}
    except Exception as exc:  # noqa: BLE001
        logger.exception("Telecaller enqueue failed: %s", exc)
        return {"status": "error", "detail": str(exc)}
