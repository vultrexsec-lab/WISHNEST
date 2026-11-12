"""USE P3 — paid channel readiness + plan-only campaign records (no spend without keys + flag)."""
from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger("wishnest.use_ads")


def channel_status() -> dict[str, Any]:
    """Report which ad platforms have credentials configured on the server."""
    meta_token = (os.environ.get("META_ADS_ACCESS_TOKEN") or os.environ.get("FACEBOOK_ACCESS_TOKEN") or "").strip()
    meta_account = (os.environ.get("META_AD_ACCOUNT_ID") or os.environ.get("FACEBOOK_AD_ACCOUNT_ID") or "").strip()
    google_dev = (os.environ.get("GOOGLE_ADS_DEVELOPER_TOKEN") or "").strip()
    google_cust = (os.environ.get("GOOGLE_ADS_CUSTOMER_ID") or "").strip()
    google_refresh = (os.environ.get("GOOGLE_ADS_REFRESH_TOKEN") or "").strip()
    li_token = (os.environ.get("LINKEDIN_ACCESS_TOKEN") or "").strip()
    li_account = (os.environ.get("LINKEDIN_AD_ACCOUNT_ID") or "").strip()

    live = (os.environ.get("USE_ADS_LIVE_SPEND") or "").strip().lower() in ("1", "true", "yes")

    channels = {
        "meta_facebook": {
            "label": "Meta / Facebook / Instagram Ads",
            "configured": bool(meta_token and meta_account),
            "missing": [k for k, v in {
                "META_ADS_ACCESS_TOKEN": meta_token,
                "META_AD_ACCOUNT_ID": meta_account,
            }.items() if not v],
            "live_api": False,
        },
        "google": {
            "label": "Google Ads",
            "configured": bool(google_dev and google_cust and google_refresh),
            "missing": [k for k, v in {
                "GOOGLE_ADS_DEVELOPER_TOKEN": google_dev,
                "GOOGLE_ADS_CUSTOMER_ID": google_cust,
                "GOOGLE_ADS_REFRESH_TOKEN": google_refresh,
            }.items() if not v],
            "live_api": False,
        },
        "linkedin": {
            "label": "LinkedIn Campaign Manager",
            "configured": bool(li_token and li_account),
            "missing": [k for k, v in {
                "LINKEDIN_ACCESS_TOKEN": li_token,
                "LINKEDIN_AD_ACCOUNT_ID": li_account,
            }.items() if not v],
            "live_api": False,
        },
    }
    return {
        "live_spend_allowed": live,
        "note": (
            "P3 stores channel readiness and plan-only briefs. "
            "Set platform tokens on Render, then USE_ADS_LIVE_SPEND=true only when you intend real spend."
        ),
        "channels": channels,
    }


def build_channel_briefs(a00: dict[str, Any] | None, tenant_name: str) -> dict[str, Any]:
    """Turn A00 campaign plan into per-channel setup checklist (no API spend)."""
    a00 = a00 or {}
    playbooks = a00.get("channel_playbooks") or {}
    briefs = {}
    for key, label in (
        ("meta", "Meta / Facebook / Instagram"),
        ("google", "Google Ads"),
        ("linkedin", "LinkedIn"),
    ):
        pb = playbooks.get(key) if isinstance(playbooks, dict) else None
        if not isinstance(pb, dict):
            pb = {}
        briefs[key] = {
            "label": label,
            "tenant": tenant_name,
            "status": pb.get("status") or a00.get("execution_status") or "plan_only",
            "now": pb.get("now") or "No live campaigns — complete credentials and human launch gate first.",
            "when_ready": pb.get("when_ready"),
            "excluded": pb.get("excluded"),
            "test_design_proposal": pb.get("test_design_proposal"),
            "requires_before_launch": (a00.get("requires_human_before_launch") or [])[:8],
            "live_spend": False,
        }
    return {
        "campaign_name": a00.get("campaign_name") or f"{tenant_name} P3 plan",
        "execution_status": "PLAN_ONLY",
        "live_spend_allowed": False,
        "briefs": briefs,
    }
