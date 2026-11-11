"""USE MVP P1 API — tenants, strategy, rival, CEO, campaign manager, audit.
P1_DEPLOY_MARKER=7c23b30
"""
from __future__ import annotations

import re
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_admin
from app.models.use_engine import UseAuditLog, UseLead, UseStrategy, UseTenant
from app.services import use_engine_service as svc

router = APIRouter(prefix="/api/use", tags=["use-engine"])

def _ensure_leads_table(db: Session) -> None:
    """Idempotent — Render may have skipped CREATE on prior boot."""
    from sqlalchemy import text
    try:
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS use_leads (
                id UUID PRIMARY KEY,
                tenant_id UUID NOT NULL,
                name VARCHAR(255),
                email VARCHAR(255),
                phone VARCHAR(64),
                company VARCHAR(255),
                role VARCHAR(128),
                source VARCHAR(128),
                stage VARCHAR(64) NOT NULL DEFAULT 'new',
                email_consent BOOLEAN DEFAULT false,
                whatsapp_consent BOOLEAN DEFAULT false,
                phone_consent BOOLEAN DEFAULT false,
                do_not_contact BOOLEAN DEFAULT false,
                notes TEXT,
                meta JSONB,
                created_at TIMESTAMPTZ DEFAULT now(),
                updated_at TIMESTAMPTZ DEFAULT now()
            )
        """))
        db.execute(text("CREATE INDEX IF NOT EXISTS ix_use_leads_tenant ON use_leads (tenant_id)"))
        db.execute(text("CREATE INDEX IF NOT EXISTS ix_use_leads_email ON use_leads (email)"))
        db.commit()
    except Exception:
        db.rollback()




def _slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    return (s or "tenant")[:60]


class TenantIn(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    product_summary: str | None = None
    website: str | None = None
    geography: str | None = None
    knowledge: dict[str, Any] | None = None


class CeoDecisionIn(BaseModel):
    approve: bool
    notes: str | None = None


def _tenant_out(t: UseTenant) -> dict:
    return {
        "id": str(t.id),
        "slug": t.slug,
        "name": t.name,
        "product_summary": t.product_summary,
        "website": t.website,
        "geography": t.geography,
        "knowledge": t.knowledge,
        "is_active": t.is_active,
        "created_at": t.created_at.isoformat() if t.created_at else None,
    }


def _strategy_out(s: UseStrategy) -> dict:
    return {
        "id": str(s.id),
        "tenant_id": str(s.tenant_id),
        "status": s.status,
        "a01_output": s.a01_output,
        "a02_output": s.a02_output,
        "a00_output": s.a00_output,
        "ceo_notes": s.ceo_notes,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    }


@router.get("/status")
def use_status(_admin: dict = Depends(require_admin)):
    return {
        "module": "USE",
        "mvp": "1.1",
        "phase": "P2A",
        "agents": ["A00", "A01", "A02", "CEO"],
        "live_spend": False,
        "note": "P2A: tenant-scoped leads + consent + email draft only. No live ad spend.",
    }


@router.get("/tenants")
def list_tenants(db: Session = Depends(get_db), _admin: dict = Depends(require_admin)):
    rows = db.query(UseTenant).order_by(UseTenant.created_at.desc()).all()
    return [_tenant_out(t) for t in rows]


@router.post("/tenants")
def create_tenant(body: TenantIn, db: Session = Depends(get_db), _admin: dict = Depends(require_admin)):
    base = _slugify(body.name)
    slug = base
    n = 2
    while db.query(UseTenant).filter(UseTenant.slug == slug).first():
        slug = f"{base}-{n}"
        n += 1
    t = UseTenant(
        slug=slug,
        name=body.name.strip(),
        product_summary=(body.product_summary or "").strip() or None,
        website=(body.website or "").strip() or None,
        geography=(body.geography or "").strip() or None,
        knowledge=body.knowledge or {},
        is_active=True,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    svc.audit(db, agent_id="SYSTEM", action="tenant_created", tenant_id=t.id, detail={"slug": slug})
    return _tenant_out(t)


@router.get("/tenants/{tenant_id}")
def get_tenant(tenant_id: str, db: Session = Depends(get_db), _admin: dict = Depends(require_admin)):
    t = db.query(UseTenant).filter(UseTenant.id == uuid.UUID(tenant_id)).first()
    if not t:
        raise HTTPException(404, "Tenant not found")
    return _tenant_out(t)


@router.get("/tenants/{tenant_id}/strategies")
def list_strategies(tenant_id: str, db: Session = Depends(get_db), _admin: dict = Depends(require_admin)):
    tid = uuid.UUID(tenant_id)
    rows = (
        db.query(UseStrategy)
        .filter(UseStrategy.tenant_id == tid)
        .order_by(UseStrategy.created_at.desc())
        .all()
    )
    return [_strategy_out(s) for s in rows]


@router.post("/tenants/{tenant_id}/strategies")
def create_strategy(tenant_id: str, db: Session = Depends(get_db), _admin: dict = Depends(require_admin)):
    t = db.query(UseTenant).filter(UseTenant.id == uuid.UUID(tenant_id)).first()
    if not t:
        raise HTTPException(404, "Tenant not found")
    s = UseStrategy(tenant_id=t.id, status="draft")
    db.add(s)
    db.commit()
    db.refresh(s)
    svc.audit(db, agent_id="SYSTEM", action="strategy_created", tenant_id=t.id, strategy_id=s.id)
    return _strategy_out(s)


@router.get("/strategies/{strategy_id}")
def get_strategy(strategy_id: str, db: Session = Depends(get_db), _admin: dict = Depends(require_admin)):
    s = db.query(UseStrategy).filter(UseStrategy.id == uuid.UUID(strategy_id)).first()
    if not s:
        raise HTTPException(404, "Strategy not found")
    return _strategy_out(s)


@router.post("/strategies/{strategy_id}/run-a01")
def run_a01(strategy_id: str, db: Session = Depends(get_db), _admin: dict = Depends(require_admin)):
    s = db.query(UseStrategy).filter(UseStrategy.id == uuid.UUID(strategy_id)).first()
    if not s:
        raise HTTPException(404, "Strategy not found")
    t = db.query(UseTenant).filter(UseTenant.id == s.tenant_id).first()
    if not t:
        raise HTTPException(404, "Tenant not found")
    try:
        s = svc.run_a01_strategy(db, t, s)
    except RuntimeError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        raise HTTPException(500, f"A01 failed: {e}") from e
    return _strategy_out(s)


@router.post("/strategies/{strategy_id}/run-a02")
def run_a02(strategy_id: str, db: Session = Depends(get_db), _admin: dict = Depends(require_admin)):
    s = db.query(UseStrategy).filter(UseStrategy.id == uuid.UUID(strategy_id)).first()
    if not s:
        raise HTTPException(404, "Strategy not found")
    t = db.query(UseTenant).filter(UseTenant.id == s.tenant_id).first()
    if not t:
        raise HTTPException(404, "Tenant not found")
    try:
        s = svc.run_a02_rival(db, t, s)
    except RuntimeError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        raise HTTPException(500, f"A02 failed: {e}") from e
    return _strategy_out(s)


@router.post("/strategies/{strategy_id}/ceo-decision")
def ceo_decision(
    strategy_id: str,
    body: CeoDecisionIn,
    db: Session = Depends(get_db),
    _admin: dict = Depends(require_admin),
):
    s = db.query(UseStrategy).filter(UseStrategy.id == uuid.UUID(strategy_id)).first()
    if not s:
        raise HTTPException(404, "Strategy not found")
    t = db.query(UseTenant).filter(UseTenant.id == s.tenant_id).first()
    if not t:
        raise HTTPException(404, "Tenant not found")
    try:
        s = svc.ceo_decide(db, t, s, approve=body.approve, notes=body.notes)
    except RuntimeError as e:
        raise HTTPException(400, str(e)) from e
    return _strategy_out(s)


@router.post("/strategies/{strategy_id}/run-a00")
def run_a00(strategy_id: str, db: Session = Depends(get_db), _admin: dict = Depends(require_admin)):
    s = db.query(UseStrategy).filter(UseStrategy.id == uuid.UUID(strategy_id)).first()
    if not s:
        raise HTTPException(404, "Strategy not found")
    t = db.query(UseTenant).filter(UseTenant.id == s.tenant_id).first()
    if not t:
        raise HTTPException(404, "Tenant not found")
    try:
        s = svc.run_a00_campaign_manager(db, t, s)
    except RuntimeError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        raise HTTPException(500, f"A00 failed: {e}") from e
    return _strategy_out(s)


@router.get("/audit")
def list_audit(
    tenant_id: str | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    _admin: dict = Depends(require_admin),
):
    q = db.query(UseAuditLog).order_by(UseAuditLog.created_at.desc())
    if tenant_id:
        q = q.filter(UseAuditLog.tenant_id == uuid.UUID(tenant_id))
    rows = q.limit(min(limit, 200)).all()
    return [
        {
            "id": str(r.id),
            "tenant_id": str(r.tenant_id) if r.tenant_id else None,
            "strategy_id": str(r.strategy_id) if r.strategy_id else None,
            "agent_id": r.agent_id,
            "action": r.action,
            "status": r.status,
            "detail": r.detail,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]



# ─── P2A Leads ───────────────────────────────────────────────────────────────

class LeadIn(BaseModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    company: str | None = None
    role: str | None = None
    source: str = "manual"
    email_consent: bool = False
    whatsapp_consent: bool = False
    phone_consent: bool = False
    notes: str | None = None


class LeadStageIn(BaseModel):
    stage: str = Field(..., min_length=2, max_length=64)
    do_not_contact: bool | None = None
    email_consent: bool | None = None
    notes: str | None = None


def _lead_out(r: UseLead) -> dict:
    return {
        "id": str(r.id),
        "tenant_id": str(r.tenant_id),
        "name": r.name,
        "email": r.email,
        "phone": r.phone,
        "company": r.company,
        "role": r.role,
        "source": r.source,
        "stage": r.stage,
        "email_consent": bool(r.email_consent),
        "whatsapp_consent": bool(r.whatsapp_consent),
        "phone_consent": bool(r.phone_consent),
        "do_not_contact": bool(r.do_not_contact),
        "notes": r.notes,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


@router.get("/tenants/{tenant_id}/leads")
def list_leads(
    tenant_id: str,
    db: Session = Depends(get_db),
    _admin: dict = Depends(require_admin),
):
    tid = uuid.UUID(tenant_id)
    _ensure_leads_table(db)
    rows = (
        db.query(UseLead)
        .filter(UseLead.tenant_id == tid)
        .order_by(UseLead.created_at.desc())
        .limit(200)
        .all()
    )
    return [_lead_out(r) for r in rows]


@router.post("/tenants/{tenant_id}/leads")
def create_lead(
    tenant_id: str,
    body: LeadIn,
    db: Session = Depends(get_db),
    _admin: dict = Depends(require_admin),
):
    t = db.query(UseTenant).filter(UseTenant.id == uuid.UUID(tenant_id)).first()
    if not t:
        raise HTTPException(404, "Tenant not found")
    if not (body.email or body.phone or body.name):
        raise HTTPException(400, "Provide at least name, email, or phone")
    _ensure_leads_table(db)
    try:
        row = svc.create_lead(
            db,
            t,
            name=body.name,
            email=body.email,
            phone=body.phone,
            company=body.company,
            role=body.role,
            source=body.source or "manual",
            email_consent=body.email_consent,
            whatsapp_consent=body.whatsapp_consent,
            phone_consent=body.phone_consent,
            notes=body.notes,
        )
    except RuntimeError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        raise HTTPException(500, f"Lead create failed: {e}") from e
    return _lead_out(row)


@router.patch("/leads/{lead_id}")
def update_lead(
    lead_id: str,
    body: LeadStageIn,
    db: Session = Depends(get_db),
    _admin: dict = Depends(require_admin),
):
    row = db.query(UseLead).filter(UseLead.id == uuid.UUID(lead_id)).first()
    if not row:
        raise HTTPException(404, "Lead not found")
    stage = body.stage.strip().lower()
    if stage not in ("new", "qualified", "nurture", "unfit", "won"):
        raise HTTPException(400, "stage must be new|qualified|nurture|unfit|won")
    row.stage = stage
    if body.do_not_contact is not None:
        row.do_not_contact = body.do_not_contact
    if body.email_consent is not None:
        row.email_consent = body.email_consent
    if body.notes is not None:
        row.notes = body.notes
    db.commit()
    db.refresh(row)
    svc.audit(
        db,
        agent_id="SYSTEM",
        action="lead_updated",
        tenant_id=row.tenant_id,
        detail={"lead_id": str(row.id), "stage": row.stage},
    )
    return _lead_out(row)


@router.post("/leads/{lead_id}/draft-email")
def draft_lead_email(
    lead_id: str,
    db: Session = Depends(get_db),
    _admin: dict = Depends(require_admin),
):
    row = db.query(UseLead).filter(UseLead.id == uuid.UUID(lead_id)).first()
    if not row:
        raise HTTPException(404, "Lead not found")
    t = db.query(UseTenant).filter(UseTenant.id == row.tenant_id).first()
    if not t:
        raise HTTPException(404, "Tenant not found")
    draft = svc.draft_outreach_email(t, row)
    svc.audit(
        db,
        agent_id="SYSTEM",
        action="lead_email_drafted",
        tenant_id=row.tenant_id,
        detail={"lead_id": str(row.id), "status": draft.get("status")},
    )
    return draft
