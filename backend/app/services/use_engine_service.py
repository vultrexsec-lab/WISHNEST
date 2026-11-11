import uuid
"""USE MVP P1 — Grok agents A01, A02, A00 + audit. No live ad spend."""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from openai import OpenAI
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.use_engine import UseAuditLog, UseStrategy, UseTenant

logger = logging.getLogger("wishnest.use_engine")

ALLOWED_AGENTS = {"A00", "A01", "A02", "CEO", "SYSTEM"}


def _grok() -> OpenAI:
    settings = get_settings()
    key = settings.xai_api_key
    if not key:
        raise RuntimeError(
            "XAI_API_KEY / GROK_API_KEY is not configured. Add it on Render to run USE agents."
        )
    return OpenAI(api_key=key, base_url="https://api.x.ai/v1")


def _model() -> str:
    return (get_settings().xai_model or "grok-4.7").strip() or "grok-4.7"


def _model_candidates() -> list[str]:
    primary = _model()
    # Fallback order if primary 404s on xAI
    fallbacks = ["grok-4.7", "grok-4-latest", "grok-4", "grok-3", "grok-2-latest", "grok-2"]
    out: list[str] = []
    for m in [primary] + fallbacks:
        if m and m not in out:
            out.append(m)
    return out


def _chat_json(messages: list[dict], *, temperature: float = 0.4) -> str:
    """Call xAI chat completions; retry on 404 model-not-found."""
    client = _grok()
    last_err: Exception | None = None
    for model in _model_candidates():
        try:
            completion = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
            )
            return completion.choices[0].message.content or ""
        except Exception as exc:
            last_err = exc
            err_s = str(exc).lower()
            # retry only model-missing style errors
            if "404" in err_s or "not found" in err_s or "model" in err_s:
                logger.warning("xAI model %s failed: %s — trying next", model, exc)
                continue
            raise
    raise RuntimeError(f"xAI chat failed for all models: {last_err}") from last_err


def audit(
    db: Session,
    *,
    agent_id: str,
    action: str,
    status: str = "COMPLETED",
    tenant_id=None,
    strategy_id=None,
    detail: dict | None = None,
) -> UseAuditLog:
    if agent_id not in ALLOWED_AGENTS:
        agent_id = "SYSTEM"
    row = UseAuditLog(
        tenant_id=tenant_id,
        strategy_id=strategy_id,
        agent_id=agent_id,
        action=action,
        status=status,
        detail=detail or {},
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _parse_json(text: str) -> dict[str, Any]:
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else {"raw": data}
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                pass
        return {"raw_text": text[:8000]}


def run_a01_strategy(db: Session, tenant: UseTenant, strategy: UseStrategy) -> UseStrategy:
    """A01 Strategy Director — structured strategy only, no campaign launch."""
    client = _grok()
    knowledge = tenant.knowledge or {}
    prompt = f"""You are A01 Strategy Director for the Universal Sales Engine.
Build a practical Marketing & Sales Strategy. Do NOT invent prices, testimonials, or customer contacts.
Output ONLY valid JSON with keys:
product_understanding, market_assessment, competitor_assessment, personas (array),
positioning, lead_acquisition, channel_plans (object with meta, google, linkedin, email_whatsapp),
qualification_criteria, sales_conversion, budgets_and_kpis (proposals only), assumptions, missing_information (array).

Tenant: {tenant.name}
Website: {tenant.website or "n/a"}
Geography: {tenant.geography or "n/a"}
Product summary: {tenant.product_summary or "n/a"}
Approved knowledge JSON: {json.dumps(knowledge)[:3000]}
"""
    try:
        raw = _chat_json([
                {"role": "system", "content": "You are a senior performance marketing strategist. JSON only. No invented commercial facts."},
                {"role": "user", "content": prompt},
            ], temperature=0.4)
        data = _parse_json(raw)
        strategy.a01_output = data
        strategy.status = "draft"
        db.add(strategy)
        db.commit()
        db.refresh(strategy)
        audit(
            db,
            agent_id="A01",
            action="strategy_generated",
            tenant_id=tenant.id,
            strategy_id=strategy.id,
            detail={"keys": list(data.keys())[:20]},
        )
        return strategy
    except Exception as exc:
        logger.exception("A01 failed")
        audit(
            db,
            agent_id="A01",
            action="strategy_generated",
            status="EXECUTION_FAILED",
            tenant_id=tenant.id,
            strategy_id=strategy.id,
            detail={"error": str(exc)[:500]},
        )
        raise


def run_a02_rival(db: Session, tenant: UseTenant, strategy: UseStrategy) -> UseStrategy:
    """A02 Rival Agency — must challenge A01, not rubber-stamp."""
    if not strategy.a01_output:
        raise RuntimeError("A01 strategy required before rival review")
    client = _grok()
    prompt = f"""You are A02 Rival Agency Director. Independently attack the strategy below.
Find weak ICPs, channel risks, budget holes, weak offers, and failure modes. Propose concrete improvements.
Do NOT invent client prices or contacts. Output ONLY JSON with keys:
weaknesses (array), channel_risks (array), budget_critique, alternative_approaches (array),
required_fixes (array), overall_verdict (string).

Tenant: {tenant.name}
A01 strategy JSON: {json.dumps(strategy.a01_output)[:6000]}
"""
    try:
        raw = _chat_json([
                {"role": "system", "content": "You are a competing performance agency. Be critical. JSON only."},
                {"role": "user", "content": prompt},
            ], temperature=0.5)
        data = _parse_json(raw)
        strategy.a02_output = data
        strategy.status = "rival_done"
        db.add(strategy)
        db.commit()
        db.refresh(strategy)
        audit(
            db,
            agent_id="A02",
            action="rival_review",
            tenant_id=tenant.id,
            strategy_id=strategy.id,
            detail={"keys": list(data.keys())[:20]},
        )
        return strategy
    except Exception as exc:
        logger.exception("A02 failed")
        audit(
            db,
            agent_id="A02",
            action="rival_review",
            status="EXECUTION_FAILED",
            tenant_id=tenant.id,
            strategy_id=strategy.id,
            detail={"error": str(exc)[:500]},
        )
        raise


def ceo_decide(
    db: Session,
    tenant: UseTenant,
    strategy: UseStrategy,
    *,
    approve: bool,
    notes: str | None = None,
) -> UseStrategy:
    if strategy.status not in ("rival_done", "draft", "approved", "rejected"):
        pass
    if not strategy.a01_output:
        raise RuntimeError("Cannot decide without A01 strategy")
    strategy.ceo_notes = (notes or "").strip() or strategy.ceo_notes
    strategy.status = "approved" if approve else "rejected"
    if not approve:
        strategy.a00_output = None
    db.add(strategy)
    db.commit()
    db.refresh(strategy)
    audit(
        db,
        agent_id="CEO",
        action="strategy_approved" if approve else "strategy_rejected",
        tenant_id=tenant.id,
        strategy_id=strategy.id,
        detail={"notes": (notes or "")[:300]},
    )
    return strategy


def run_a00_campaign_manager(db: Session, tenant: UseTenant, strategy: UseStrategy) -> UseStrategy:
    """A00 Campaign Manager — plan only after CEO approval. No live spend."""
    if strategy.status != "approved":
        raise RuntimeError("CEO approval required before Campaign Manager plan")
    if not strategy.a01_output:
        raise RuntimeError("A01 strategy required")
    client = _grok()
    prompt = f"""You are A00 Campaign Manager. After CEO approval, produce an execution PLAN only.
Do NOT claim ads are live. Do NOT invent spend already spent. Budgets are proposals pending human connection of ad accounts.
Output ONLY JSON with keys:
campaign_name, objectives, timeline_weeks, channel_playbooks (meta, google, linkedin, email_whatsapp),
budget_allocation_proposal, lead_handoff_to_crm, kpis, risks, requires_human_before_launch (array of strings).

Tenant: {tenant.name}
A01: {json.dumps(strategy.a01_output)[:4000]}
A02: {json.dumps(strategy.a02_output or {})[:2000]}
CEO notes: {strategy.ceo_notes or "n/a"}
"""
    try:
        raw = _chat_json([
                {
                    "role": "system",
                    "content": "Campaign orchestrator. Plans only — no unauthorised spend or messaging. JSON only.",
                },
                {"role": "user", "content": prompt},
            ], temperature=0.4)
        data = _parse_json(raw)
        data["execution_status"] = "PLAN_ONLY"
        data["live_spend_allowed"] = False
        strategy.a00_output = data
        db.add(strategy)
        db.commit()
        db.refresh(strategy)
        audit(
            db,
            agent_id="A00",
            action="campaign_plan",
            tenant_id=tenant.id,
            strategy_id=strategy.id,
            detail={"execution_status": "PLAN_ONLY"},
        )
        return strategy
    except Exception as exc:
        logger.exception("A00 failed")
        audit(
            db,
            agent_id="A00",
            action="campaign_plan",
            status="EXECUTION_FAILED",
            tenant_id=tenant.id,
            strategy_id=strategy.id,
            detail={"error": str(exc)[:500]},
        )
        raise


# ─── P2A Leads ───────────────────────────────────────────────────────────────


def create_lead(
    db: Session,
    tenant: UseTenant,
    *,
    name: str | None,
    email: str | None,
    phone: str | None = None,
    company: str | None = None,
    role: str | None = None,
    source: str = "manual",
    email_consent: bool = False,
    whatsapp_consent: bool = False,
    phone_consent: bool = False,
    notes: str | None = None,
) -> UseLead:
    email_n = (email or "").strip().lower() or None
    if email_n:
        existing = (
            db.query(UseLead)
            .filter(UseLead.tenant_id == tenant.id, UseLead.email == email_n)
            .first()
        )
        if existing:
            # Update soft fields; never clear do_not_contact
            if name:
                existing.name = name
            if phone:
                existing.phone = phone
            if company:
                existing.company = company
            if role:
                existing.role = role
            if notes:
                existing.notes = notes
            if email_consent:
                existing.email_consent = True
            if whatsapp_consent:
                existing.whatsapp_consent = True
            if phone_consent:
                existing.phone_consent = True
            db.commit()
            db.refresh(existing)
            audit(
                db,
                agent_id="SYSTEM",
                action="lead_upserted",
                tenant_id=tenant.id,
                detail={"lead_id": str(existing.id), "email": email_n},
            )
            return existing

    row = UseLead(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        name=(name or "").strip() or None,
        email=email_n,
        phone=(phone or "").strip() or None,
        company=(company or "").strip() or None,
        role=(role or "").strip() or None,
        source=(source or "manual")[:128],
        stage="new",
        email_consent=bool(email_consent),
        whatsapp_consent=bool(whatsapp_consent),
        phone_consent=bool(phone_consent),
        do_not_contact=False,
        notes=notes,
        meta={},
    )
    try:
        db.add(row)
        db.commit()
        db.refresh(row)
    except Exception as exc:
        db.rollback()
        logger.exception("create_lead insert failed: %s", exc)
        raise RuntimeError(f"Lead save failed: {exc}") from exc
    audit(
        db,
        agent_id="SYSTEM",
        action="lead_created",
        tenant_id=tenant.id,
        detail={"lead_id": str(row.id), "email": email_n, "source": source},
    )
    return row


def draft_outreach_email(tenant: UseTenant, lead: UseLead) -> dict:
    """P2A: draft only — never auto-sends."""
    if lead.do_not_contact:
        return {"status": "blocked", "reason": "do_not_contact"}
    if not lead.email_consent:
        return {"status": "blocked", "reason": "email_consent_required"}
    if not lead.email:
        return {"status": "blocked", "reason": "email_missing"}
    greeting = f"Dear {lead.name}," if lead.name else "Hello,"
    body = (
        f"{greeting}\n\n"
        f"I'm reaching out from {tenant.name}"
        + (f" ({tenant.website})" if tenant.website else "")
        + ".\n\n"
        "We work with teams who want a clearer path from interest to a scoped conversation — "
        "without pressure tactics or unsolicited claims.\n\n"
        "If a short introduction would be useful, simply reply to this email. "
        "If not, you can ignore this message and we will not follow up from this draft alone.\n\n"
        f"Warm regards,\n{tenant.name} team"
    )
    return {
        "status": "draft_only",
        "to": lead.email,
        "subject": f"Introduction — {tenant.name}",
        "body": body,
        "live_send": False,
        "note": "P2A does not auto-send. Copy or connect approved email in a later step.",
    }
