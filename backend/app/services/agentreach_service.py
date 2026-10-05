"""
AgentReach — cold first-contact sequences (e.g. resort owners).
Separate from Mautic opted-in nurture. No bulk send without human approval.
"""
from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger("wishnest.agentreach")


def agentreach_configured() -> bool:
    return bool(os.environ.get("AGENTREACH_API_URL") and os.environ.get("AGENTREACH_API_KEY"))


def create_cold_sequence_draft(
    *,
    campaign_name: str,
    audience_label: str,
    geography: str,
    offer: str,
    messages: list[str],
) -> dict[str, Any]:
    """Create a draft cold sequence — never auto-sends."""
    draft = {
        "campaign_name": campaign_name,
        "audience": audience_label,
        "geography": geography,
        "offer": offer,
        "messages": messages,
        "status": "draft_pending_approval",
        "channel": "agentreach_cold",
    }
    if not agentreach_configured():
        logger.info("AgentReach stub draft: %s", campaign_name)
        return {"status": "stub_draft", "draft": draft}
    # Real HTTP adapter later
    return {"status": "draft", "draft": draft}
