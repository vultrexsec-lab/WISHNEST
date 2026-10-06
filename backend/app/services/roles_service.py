"""
Simple role map for Growth OS admins.
Env ADMIN_ROLES = JSON object username -> role
  e.g. {"admin":"admin","editor":"editor","sales":"sales"}

Roles: admin | editor | sales | analyst
Default: any valid JWT user is treated as admin if not listed.
"""
from __future__ import annotations

import json
import os
from typing import Literal

Role = Literal["admin", "editor", "sales", "analyst"]

PERMISSIONS: dict[str, set[str]] = {
    "admin": {"*"},
    "editor": {
        "editorial",
        "seo_geo",
        "surveys_read",
        "campaigns_read",
        "entities",
    },
    "sales": {
        "contacts",
        "campaigns",
        "outreach",
        "arrowx",
        "surveys",
        "market_network",
    },
    "analyst": {
        "analytics",
        "surveys_read",
        "campaigns_read",
        "arrowx_read",
        "market_network_read",
    },
}


def role_for_user(username: str) -> Role:
    raw = (os.environ.get("ADMIN_ROLES") or "").strip()
    if not raw:
        return "admin"
    try:
        data = json.loads(raw)
        r = str(data.get(username) or data.get(username.lower()) or "admin").lower()
        if r in PERMISSIONS:
            return r  # type: ignore[return-value]
    except Exception:
        pass
    return "admin"


def has_permission(username: str, perm: str) -> bool:
    role = role_for_user(username)
    allowed = PERMISSIONS.get(role, set())
    return "*" in allowed or perm in allowed
