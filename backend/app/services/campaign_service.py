"""AI campaign pack generator — drafts only; human approval required before send."""
from __future__ import annotations

import json
import logging
from typing import Any

from openai import OpenAI

from app.config import get_settings

logger = logging.getLogger("wishnest.campaign")


def generate_campaign_pack(
    *,
    name: str,
    campaign_type: str,
    classification: str,
    objective: str | None,
    audience_summary: str,
    channels: list[str],
    cta_label: str | None,
    cta_url: str | None,
) -> dict[str, Any]:
    settings = get_settings()
    base = {
        "email": {
            "subjects": [],
            "bodies": [],
            "follow_ups": [],
        },
        "whatsapp": {"messages": []},
        "linkedin": {"posts": []},
        "social": {"captions": []},
        "notes": "Draft only — approve before any send.",
    }

    if not settings.openai_api_key:
        base["email"]["subjects"] = [f"{name}: {cta_label or 'Learn more'}"]
        base["email"]["bodies"] = [
            f"Draft for {name}.\n\nObjective: {objective or campaign_type}.\n"
            f"Audience: {audience_summary}.\n\n"
            f"CTA: {cta_label or 'Get started'} → {cta_url or 'https://wishnest.info'}"
        ]
        base["whatsapp"]["messages"] = [
            f"Hi — {cta_label or name}. Details: {cta_url or 'https://wishnest.info'}"
        ]
        base["linkedin"]["posts"] = [
            f"{name}\n\n{objective or ''}\n\n{cta_label or ''} {cta_url or ''}"
        ]
        return base

    try:
        client = OpenAI(api_key=settings.openai_api_key)
        prompt = f"""You are WishNest Campaign Intelligence (independent hospitality / architecture editorial brand — not a sales CRM tone).
Classification: {classification} (never present editorial as paid placement).
Campaign: {name}
Type: {campaign_type}
Objective: {objective or "n/a"}
Audience: {audience_summary}
Channels: {", ".join(channels) or "email"}
CTA: {cta_label or "Learn more"} → {cta_url or "https://wishnest.info"}

Return JSON only:
{{
  "email": {{
    "subjects": ["3 subject variants"],
    "bodies": ["2 short email drafts, WishNest editorial voice"],
    "follow_ups": ["2 follow-up emails"]
  }},
  "whatsapp": {{ "messages": ["2 short permission-aware messages"] }},
  "linkedin": {{ "posts": ["2 LinkedIn posts"] }},
  "social": {{ "captions": ["2 IG/FB captions"] }},
  "notes": "brief compliance note"
}}
"""
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.5,
        )
        data = json.loads(resp.choices[0].message.content or "{}")
        if isinstance(data, dict) and data.get("email"):
            return data
    except Exception as exc:  # noqa: BLE001
        logger.warning("Campaign AI pack failed: %s", exc)
        base["notes"] = f"AI unavailable — heuristic draft. ({exc})"
    return base
