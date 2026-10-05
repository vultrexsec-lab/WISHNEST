"""Growth & Intelligence OS — admin APIs (Campaign Manager control module)."""
from __future__ import annotations

import csv
import io
import uuid
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_admin
from app.models.growth import ArrowxOpportunity, GrowthContact, SeoGeoRun
from app.models.newsletter import NewsletterSubscriber
from app.services.agentreach_service import agentreach_configured, create_cold_sequence_draft
from app.services.email_service import email_configured
from app.services.mautic_service import mautic_configured, upsert_contact
from app.services.postiz_service import postiz_configured

router = APIRouter(tags=["growth-os"])

CONTACT_TYPES = [
    "resort_owner",
    "hotel_owner",
    "broker",
    "developer",
    "landowner",
    "investor",
    "architect",
    "subscriber",
    "consumer",
    "other",
]


class GrowthStatusOut(BaseModel):
    product: str
    pipeline: str
    integrations: dict[str, bool]
    counts: dict[str, int]


def _contact_out(r: GrowthContact) -> dict[str, Any]:
    return {
        "id": str(r.id),
        "external_mautic_id": r.external_mautic_id,
        "name": r.name,
        "email": r.email,
        "phone": r.phone,
        "company": r.company,
        "contact_type": r.contact_type,
        "country": r.country,
        "state": r.state,
        "city": r.city,
        "destination": r.destination,
        "email_permission": bool(r.email_permission),
        "whatsapp_permission": bool(r.whatsapp_permission),
        "phone_permission": bool(r.phone_permission),
        "unsubscribed": bool(r.unsubscribed),
        "do_not_contact": bool(r.do_not_contact),
        "tags": r.tags,
        "interests": r.interests,
        "intelligence_score": r.intelligence_score or 0,
        "commercial_score": r.commercial_score or 0,
        "source": r.source,
        "notes": r.notes,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


@router.get("/api/growth/status", response_model=GrowthStatusOut)
def growth_status(
    db: Session = Depends(get_db),
    admin: str = Depends(require_admin),
):
    return GrowthStatusOut(
        product="WishNest Growth & Intelligence OS",
        pipeline=(
            "Editorial → SEO/GEO → Postiz → Subscribers → "
            "Campaigns/Surveys (Mautic) → Intelligence → ArrowX"
        ),
        integrations={
            "openai": True,
            "email_brevo_or_smtp": email_configured(),
            "postiz": postiz_configured(),
            "agentreach_cold": agentreach_configured(),
            "mautic": mautic_configured(),
            "whatsapp_business": False,
            "telecaller": False,
        },
        counts={
            "contacts": db.query(GrowthContact).count(),
            "arrowx_opportunities": db.query(ArrowxOpportunity).count(),
            "seo_geo_runs": db.query(SeoGeoRun).count(),
            "newsletter_subscribers": db.query(NewsletterSubscriber).count(),
        },
    )


@router.get("/api/growth/contacts")
def list_contacts(
    db: Session = Depends(get_db),
    admin: str = Depends(require_admin),
    contact_type: str | None = None,
    q: str | None = None,
    limit: int = 100,
    offset: int = 0,
):
    query = db.query(GrowthContact).order_by(GrowthContact.created_at.desc())
    if contact_type:
        query = query.filter(GrowthContact.contact_type == contact_type.strip().lower())
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(
            (GrowthContact.email.ilike(like))
            | (GrowthContact.name.ilike(like))
            | (GrowthContact.company.ilike(like))
            | (GrowthContact.city.ilike(like))
        )
    rows = query.offset(max(0, offset)).limit(min(limit, 200)).all()
    return [_contact_out(r) for r in rows]


class ContactCreate(BaseModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    company: str | None = None
    contact_type: str | None = "other"
    country: str | None = "India"
    state: str | None = None
    city: str | None = None
    destination: str | None = None
    email_permission: bool = False
    whatsapp_permission: bool = False
    phone_permission: bool = False
    tags: str | None = None
    interests: str | None = None
    source: str | None = "manual"
    notes: str | None = None
    sync_mautic: bool = True


@router.post("/api/growth/contacts")
def create_contact(
    body: ContactCreate,
    db: Session = Depends(get_db),
    admin: str = Depends(require_admin),
):
    email = (body.email or "").strip().lower() or None
    phone = (body.phone or "").strip() or None
    if not email and not phone:
        raise HTTPException(400, "email or phone required")

    if email:
        existing = db.query(GrowthContact).filter(GrowthContact.email == email).first()
        if existing:
            raise HTTPException(409, f"Contact already exists: {email}")

    ctype = (body.contact_type or "other").strip().lower().replace(" ", "_")
    if ctype not in CONTACT_TYPES:
        ctype = "other"

    row = GrowthContact(
        name=(body.name or "").strip() or None,
        email=email,
        phone=phone,
        company=(body.company or "").strip() or None,
        contact_type=ctype,
        country=(body.country or "").strip() or None,
        state=(body.state or "").strip() or None,
        city=(body.city or "").strip() or None,
        destination=(body.destination or "").strip() or None,
        email_permission=bool(body.email_permission),
        whatsapp_permission=bool(body.whatsapp_permission),
        phone_permission=bool(body.phone_permission),
        tags=(body.tags or "").strip() or None,
        interests=(body.interests or "").strip() or None,
        source=(body.source or "manual")[:128],
        notes=body.notes,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    mautic_result = None
    if body.sync_mautic and row.email_permission and not row.unsubscribed and not row.do_not_contact:
        parts = (row.name or "").split(None, 1)
        mautic_result = upsert_contact(
            email=row.email,
            first_name=parts[0] if parts else None,
            last_name=parts[1] if len(parts) > 1 else None,
            phone=row.phone,
            company=row.company,
            tags=[row.contact_type] if row.contact_type else None,
        )
        if mautic_result.get("external_mautic_id"):
            row.external_mautic_id = mautic_result["external_mautic_id"]
            db.commit()
            db.refresh(row)

    return {"contact": _contact_out(row), "mautic": mautic_result}


@router.post("/api/growth/contacts/import-newsletter")
def import_newsletter_subscribers(
    db: Session = Depends(get_db),
    admin: str = Depends(require_admin),
    sync_mautic: bool = False,
):
    """Pull WishNest Circle subscribers into growth_contacts (opted-in email)."""
    subs = db.query(NewsletterSubscriber).all()
    created = 0
    skipped = 0
    synced = 0
    for s in subs:
        email = (s.email or "").strip().lower()
        if not email:
            skipped += 1
            continue
        existing = db.query(GrowthContact).filter(GrowthContact.email == email).first()
        if existing:
            skipped += 1
            continue
        interests = getattr(s, "interests", None)
        row = GrowthContact(
            email=email,
            contact_type="subscriber",
            country="India",
            email_permission=True,
            interests=interests,
            source="newsletter",
            tags="wishnest_circle",
        )
        db.add(row)
        created += 1
        if sync_mautic:
            res = upsert_contact(email=email, tags=["subscriber", "wishnest_circle"])
            if res.get("external_mautic_id"):
                row.external_mautic_id = res["external_mautic_id"]
                synced += 1
    db.commit()
    return {"created": created, "skipped": skipped, "mautic_synced": synced, "total_subscribers": len(subs)}


@router.post("/api/growth/contacts/import-csv")
async def import_contacts_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    admin: str = Depends(require_admin),
    sync_mautic: bool = False,
):
    """
    CSV columns (flexible headers):
    name, email, phone, company, contact_type, city, state, destination,
    email_permission, whatsapp_permission (true/false/1/yes)
    """
    raw = await file.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise HTTPException(400, "CSV has no header row")

    def pick(row: dict, *keys: str) -> str:
        lower = { (k or "").strip().lower(): v for k, v in row.items() }
        for k in keys:
            v = lower.get(k.lower())
            if v is not None and str(v).strip():
                return str(v).strip()
        return ""

    def flag(val: str) -> bool:
        return val.strip().lower() in ("1", "true", "yes", "y")

    created = 0
    skipped = 0
    for row in reader:
        email = pick(row, "email", "e-mail", "mail").lower() or None
        phone = pick(row, "phone", "mobile", "whatsapp") or None
        if not email and not phone:
            skipped += 1
            continue
        if email:
            if db.query(GrowthContact).filter(GrowthContact.email == email).first():
                skipped += 1
                continue
        ctype = pick(row, "contact_type", "type", "segment").lower().replace(" ", "_") or "other"
        if ctype not in CONTACT_TYPES:
            ctype = "other"
        ep = flag(pick(row, "email_permission", "email_opt_in", "consent_email"))
        # newsletter-style default: if email present and no explicit false column, treat import as marketing list only if flag set
        contact = GrowthContact(
            name=pick(row, "name", "full_name", "contact_name") or None,
            email=email,
            phone=phone,
            company=pick(row, "company", "organisation", "organization") or None,
            contact_type=ctype,
            country=pick(row, "country") or "India",
            state=pick(row, "state") or None,
            city=pick(row, "city") or None,
            destination=pick(row, "destination") or None,
            email_permission=ep,
            whatsapp_permission=flag(pick(row, "whatsapp_permission", "whatsapp_opt_in")),
            phone_permission=flag(pick(row, "phone_permission", "call_opt_in")),
            source="csv_import",
            tags=pick(row, "tags") or None,
        )
        db.add(contact)
        created += 1
        if sync_mautic and contact.email_permission and contact.email:
            res = upsert_contact(
                email=contact.email,
                first_name=(contact.name or "").split(None, 1)[0] if contact.name else None,
                phone=contact.phone,
                company=contact.company,
                tags=[ctype],
            )
            if res.get("external_mautic_id"):
                contact.external_mautic_id = res["external_mautic_id"]
    db.commit()
    return {"created": created, "skipped": skipped}


@router.post("/api/growth/contacts/{contact_id}/sync-mautic")
def sync_one_to_mautic(
    contact_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin: str = Depends(require_admin),
):
    row = db.query(GrowthContact).filter(GrowthContact.id == contact_id).first()
    if not row:
        raise HTTPException(404, "Contact not found")
    if row.do_not_contact or row.unsubscribed:
        raise HTTPException(400, "Contact is suppressed (DNC / unsubscribed)")
    if not row.email_permission:
        raise HTTPException(400, "No email permission — refuse Mautic sync")
    parts = (row.name or "").split(None, 1)
    res = upsert_contact(
        email=row.email,
        first_name=parts[0] if parts else None,
        last_name=parts[1] if len(parts) > 1 else None,
        phone=row.phone,
        company=row.company,
        tags=[row.contact_type] if row.contact_type else None,
    )
    if res.get("external_mautic_id"):
        row.external_mautic_id = res["external_mautic_id"]
        db.commit()
        db.refresh(row)
    return {"contact": _contact_out(row), "mautic": res}


@router.get("/api/growth/seo-geo/recent")
def recent_seo_geo(
    db: Session = Depends(get_db),
    admin: str = Depends(require_admin),
    limit: int = 20,
):
    rows = (
        db.query(SeoGeoRun)
        .order_by(SeoGeoRun.created_at.desc())
        .limit(min(limit, 50))
        .all()
    )
    return [
        {
            "id": str(r.id),
            "article_id": r.article_id,
            "seo_score": r.seo_score,
            "geo_score": r.geo_score,
            "primary_keyword": r.primary_keyword,
            "meta_title": r.meta_title,
            "postiz_status": r.postiz_status,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


@router.get("/api/growth/arrowx/opportunities")
def list_arrowx(
    db: Session = Depends(get_db),
    admin: str = Depends(require_admin),
    limit: int = 50,
):
    rows = (
        db.query(ArrowxOpportunity)
        .order_by(ArrowxOpportunity.created_at.desc())
        .limit(min(limit, 100))
        .all()
    )
    return [
        {
            "id": str(r.id),
            "title": r.title,
            "source_type": r.source_type,
            "status": r.status,
            "destination": r.destination,
            "consent_commercial": r.consent_commercial,
            "demand_signals": r.demand_signals,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


class ColdDraftIn(BaseModel):
    campaign_name: str
    audience_label: str = "Independent resort owners"
    geography: str = "India"
    offer: str = "Complimentary WishNest hospitality review"
    messages: list[str] = Field(default_factory=list)


@router.post("/api/growth/agentreach/draft")
def agentreach_draft(
    body: ColdDraftIn,
    admin: str = Depends(require_admin),
):
    """Cold outreach draft only — never auto-sends. Separate from Mautic nurture."""
    msgs = body.messages or [
        f"Introducing WishNest — independent hospitality intelligence. {body.offer}.",
        "Follow-up: would a structured property review be useful for your team?",
    ]
    return create_cold_sequence_draft(
        campaign_name=body.campaign_name,
        audience_label=body.audience_label,
        geography=body.geography,
        offer=body.offer,
        messages=msgs,
    )
