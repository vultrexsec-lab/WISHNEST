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
from app.models.growth import (
    ArrowxOpportunity,
    AudienceSegment,
    GrowthCampaign,
    GrowthContact,
    GrowthSurvey,
    GrowthSurveyResponse,
    OutreachJob,
    SeoGeoRun,
)
from app.services.campaign_service import generate_campaign_pack
from app.services.email_service import email_configured, send_email
from app.services.survey_intelligence_service import (
    aggregate_demand_signals,
    opportunity_summary,
    opportunity_title,
)
from app.models.newsletter import NewsletterSubscriber
from app.services.agentreach_service import (
    agentreach_configured,
    create_cold_sequence_draft,
    submit_approved_sequence,
)
from app.services.whatsapp_service import whatsapp_configured, send_whatsapp_text
from app.services.telecaller_service import telecaller_configured, enqueue_call
from app.services.mautic_service import (
    mautic_configured,
    push_campaign_email_pack,
    upsert_contact,
)
from app.services.postiz_service import (
    postiz_configured,
    queue_article_distribution,
    queue_social_posts,
)

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
    counts: dict[str, Any]


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
    by_type: dict[str, int] = {}
    for ctype in CONTACT_TYPES:
        by_type[ctype] = (
            db.query(GrowthContact)
            .filter(GrowthContact.contact_type == ctype)
            .count()
        )
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
            "whatsapp_business": whatsapp_configured(),
            "telecaller": telecaller_configured(),
        },
        counts={
            "contacts": db.query(GrowthContact).count(),
            "arrowx_opportunities": db.query(ArrowxOpportunity).count(),
            "seo_geo_runs": db.query(SeoGeoRun).count(),
            "newsletter_subscribers": db.query(NewsletterSubscriber).count(),
            "segments_saved": db.query(AudienceSegment).count(),
            "campaigns": db.query(GrowthCampaign).count(),
            "surveys": db.query(GrowthSurvey).count(),
            "survey_responses": db.query(GrowthSurveyResponse).count(),
            "outreach_jobs": db.query(OutreachJob).count(),
            "by_type": by_type,
        },
    )


def _apply_contact_filters(
    query,
    *,
    contact_type: str | None = None,
    state: str | None = None,
    city: str | None = None,
    destination: str | None = None,
    email_permission: bool | None = None,
    exclude_suppressed: bool = True,
    q: str | None = None,
):
    if contact_type:
        # support comma-separated types
        types = [x.strip().lower().replace(" ", "_") for x in contact_type.split(",") if x.strip()]
        if len(types) == 1:
            query = query.filter(GrowthContact.contact_type == types[0])
        elif types:
            query = query.filter(GrowthContact.contact_type.in_(types))
    if state:
        query = query.filter(GrowthContact.state.ilike(state.strip()))
    if city:
        query = query.filter(GrowthContact.city.ilike(city.strip()))
    if destination:
        query = query.filter(GrowthContact.destination.ilike(f"%{destination.strip()}%"))
    if email_permission is True:
        query = query.filter(GrowthContact.email_permission.is_(True))
    if exclude_suppressed:
        query = query.filter(GrowthContact.unsubscribed.is_(False))
        query = query.filter(GrowthContact.do_not_contact.is_(False))
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(
            (GrowthContact.email.ilike(like))
            | (GrowthContact.name.ilike(like))
            | (GrowthContact.company.ilike(like))
            | (GrowthContact.city.ilike(like))
            | (GrowthContact.destination.ilike(like))
        )
    return query


@router.get("/api/growth/contacts")
def list_contacts(
    db: Session = Depends(get_db),
    admin: str = Depends(require_admin),
    contact_type: str | None = None,
    state: str | None = None,
    city: str | None = None,
    destination: str | None = None,
    email_permission: bool | None = None,
    exclude_suppressed: bool = True,
    q: str | None = None,
    limit: int = 100,
    offset: int = 0,
):
    query = db.query(GrowthContact).order_by(GrowthContact.created_at.desc())
    query = _apply_contact_filters(
        query,
        contact_type=contact_type,
        state=state,
        city=city,
        destination=destination,
        email_permission=email_permission,
        exclude_suppressed=exclude_suppressed,
        q=q,
    )
    total = query.count()
    rows = query.offset(max(0, offset)).limit(min(limit, 200)).all()
    return {"total": total, "contacts": [_contact_out(r) for r in rows]}


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




@router.get("/api/growth/segments/stats")
def segment_stats(
    db: Session = Depends(get_db),
    admin: str = Depends(require_admin),
):
    """Built-in segment counts for Campaign Manager audience step."""
    buckets = [
        ("resorts_hotels", ["resort_owner", "hotel_owner"]),
        ("brokers", ["broker"]),
        ("landowners", ["landowner"]),
        ("developers", ["developer"]),
        ("investors", ["investor"]),
        ("architects", ["architect"]),
        ("subscribers", ["subscriber"]),
        ("consumers", ["consumer"]),
    ]
    out = []
    for key, types in buckets:
        n = (
            db.query(GrowthContact)
            .filter(GrowthContact.contact_type.in_(types))
            .filter(GrowthContact.do_not_contact.is_(False))
            .count()
        )
        out.append({"id": key, "label": key.replace("_", " ").title(), "types": types, "count": n})
    # geo rollups
    from sqlalchemy import func as sqla_func
    cities = (
        db.query(GrowthContact.city, sqla_func.count(GrowthContact.id))
        .filter(GrowthContact.city.isnot(None), GrowthContact.city != "")
        .group_by(GrowthContact.city)
        .order_by(sqla_func.count(GrowthContact.id).desc())
        .limit(15)
        .all()
    )
    destinations = (
        db.query(GrowthContact.destination, sqla_func.count(GrowthContact.id))
        .filter(GrowthContact.destination.isnot(None), GrowthContact.destination != "")
        .group_by(GrowthContact.destination)
        .order_by(sqla_func.count(GrowthContact.id).desc())
        .limit(15)
        .all()
    )
    return {
        "segments": out,
        "top_cities": [{"name": c, "count": n} for c, n in cities if c],
        "top_destinations": [{"name": d, "count": n} for d, n in destinations if d],
    }


class SegmentCreate(BaseModel):
    name: str
    description: str | None = None
    filters: dict[str, Any] = Field(default_factory=dict)


@router.get("/api/growth/segments")
def list_saved_segments(
    db: Session = Depends(get_db),
    admin: str = Depends(require_admin),
):
    rows = db.query(AudienceSegment).order_by(AudienceSegment.created_at.desc()).limit(50).all()
    return [
        {
            "id": str(r.id),
            "name": r.name,
            "description": r.description,
            "filters": r.filters or {},
            "contact_count": r.contact_count or 0,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


@router.post("/api/growth/segments")
def create_segment(
    body: SegmentCreate,
    db: Session = Depends(get_db),
    admin: str = Depends(require_admin),
):
    name = (body.name or "").strip()
    if not name:
        raise HTTPException(400, "name required")
    filters = body.filters or {}
    types = filters.get("contact_types") or filters.get("contact_type")
    type_param = None
    if isinstance(types, list):
        type_param = ",".join(str(x) for x in types)
    elif isinstance(types, str):
        type_param = types
    query = db.query(GrowthContact)
    query = _apply_contact_filters(
        query,
        contact_type=type_param,
        state=filters.get("state"),
        city=filters.get("city"),
        destination=filters.get("destination"),
        email_permission=True if filters.get("email_permission_only") else None,
        exclude_suppressed=filters.get("exclude_suppressed", True),
    )
    count = query.count()
    row = AudienceSegment(
        name=name,
        description=(body.description or "").strip() or None,
        filters=filters,
        contact_count=count,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {
        "id": str(row.id),
        "name": row.name,
        "filters": row.filters,
        "contact_count": row.contact_count,
    }


@router.post("/api/growth/segments/{segment_id}/refresh-count")
def refresh_segment_count(
    segment_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin: str = Depends(require_admin),
):
    row = db.query(AudienceSegment).filter(AudienceSegment.id == segment_id).first()
    if not row:
        raise HTTPException(404, "Segment not found")
    filters = row.filters or {}
    types = filters.get("contact_types") or filters.get("contact_type")
    type_param = ",".join(types) if isinstance(types, list) else types
    query = db.query(GrowthContact)
    query = _apply_contact_filters(
        query,
        contact_type=type_param,
        state=filters.get("state"),
        city=filters.get("city"),
        destination=filters.get("destination"),
        email_permission=True if filters.get("email_permission_only") else None,
        exclude_suppressed=filters.get("exclude_suppressed", True),
    )
    row.contact_count = query.count()
    db.commit()
    return {"id": str(row.id), "contact_count": row.contact_count}




class CampaignCreate(BaseModel):
    name: str
    campaign_type: str = "lead_generation"
    classification: str = "commercial"
    objective: str | None = None
    audience_filters: dict[str, Any] = Field(default_factory=dict)
    channels: list[str] = Field(default_factory=lambda: ["email"])
    cta_label: str | None = "Get Your Project Reviewed"
    cta_url: str | None = "https://wishnest.info/get-reviewed"
    notes: str | None = None
    generate_pack: bool = True


def _campaign_out(r: GrowthCampaign) -> dict[str, Any]:
    return {
        "id": str(r.id),
        "name": r.name,
        "campaign_type": r.campaign_type,
        "classification": r.classification,
        "objective": r.objective,
        "audience_filters": r.audience_filters or {},
        "audience_count": r.audience_count or 0,
        "channels": r.channels or [],
        "cta_label": r.cta_label,
        "cta_url": r.cta_url,
        "status": r.status,
        "pack": r.pack,
        "notes": r.notes,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    }


def _audience_count(db: Session, filters: dict[str, Any] | None) -> int:
    filters = filters or {}
    types = filters.get("contact_types") or filters.get("contact_type")
    type_param = ",".join(types) if isinstance(types, list) else types
    query = db.query(GrowthContact)
    query = _apply_contact_filters(
        query,
        contact_type=type_param,
        state=filters.get("state"),
        city=filters.get("city"),
        destination=filters.get("destination"),
        email_permission=True if filters.get("email_permission_only") else None,
        exclude_suppressed=filters.get("exclude_suppressed", True),
    )
    return query.count()


@router.get("/api/growth/campaigns")
def list_campaigns(
    db: Session = Depends(get_db),
    admin: str = Depends(require_admin),
    limit: int = 30,
):
    rows = (
        db.query(GrowthCampaign)
        .order_by(GrowthCampaign.created_at.desc())
        .limit(min(limit, 50))
        .all()
    )
    return [_campaign_out(r) for r in rows]


@router.post("/api/growth/campaigns")
def create_campaign(
    body: CampaignCreate,
    db: Session = Depends(get_db),
    admin: str = Depends(require_admin),
):
    name = (body.name or "").strip()
    if not name:
        raise HTTPException(400, "name required")
    classification = (body.classification or "commercial").strip().lower()
    if classification not in ("editorial", "research", "commercial", "sponsored"):
        classification = "commercial"
    channels = body.channels or ["email"]
    filters = body.audience_filters or {}
    count = _audience_count(db, filters)
    row = GrowthCampaign(
        name=name,
        campaign_type=(body.campaign_type or "lead_generation")[:64],
        classification=classification,
        objective=(body.objective or "")[:128] or None,
        audience_filters=filters,
        audience_count=count,
        channels=channels,
        cta_label=body.cta_label,
        cta_url=body.cta_url,
        status="draft",
        notes=body.notes,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    if body.generate_pack:
        row.status = "ai_generating"
        db.commit()
        types = filters.get("contact_types") or []
        audience_summary = (
            f"types={types}; count≈{count}; "
            f"geo={filters.get('destination') or filters.get('city') or filters.get('state') or 'India'}"
        )
        pack = generate_campaign_pack(
            name=name,
            campaign_type=row.campaign_type,
            classification=classification,
            objective=row.objective,
            audience_summary=audience_summary,
            channels=list(channels),
            cta_label=row.cta_label,
            cta_url=row.cta_url,
        )
        row.pack = pack
        row.status = "ready_for_review"
        db.commit()
        db.refresh(row)

    return _campaign_out(row)


@router.get("/api/growth/campaigns/{campaign_id}")
def get_campaign(
    campaign_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin: str = Depends(require_admin),
):
    row = db.query(GrowthCampaign).filter(GrowthCampaign.id == campaign_id).first()
    if not row:
        raise HTTPException(404, "Campaign not found")
    return _campaign_out(row)


@router.post("/api/growth/campaigns/{campaign_id}/regenerate-pack")
def regenerate_pack(
    campaign_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin: str = Depends(require_admin),
):
    row = db.query(GrowthCampaign).filter(GrowthCampaign.id == campaign_id).first()
    if not row:
        raise HTTPException(404, "Campaign not found")
    filters = row.audience_filters or {}
    types = filters.get("contact_types") or []
    audience_summary = f"types={types}; count≈{row.audience_count}"
    pack = generate_campaign_pack(
        name=row.name,
        campaign_type=row.campaign_type,
        classification=row.classification,
        objective=row.objective,
        audience_summary=audience_summary,
        channels=list(row.channels or ["email"]),
        cta_label=row.cta_label,
        cta_url=row.cta_url,
    )
    row.pack = pack
    row.status = "ready_for_review"
    db.commit()
    db.refresh(row)
    return _campaign_out(row)


@router.post("/api/growth/campaigns/{campaign_id}/approve")
def approve_campaign(
    campaign_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin: str = Depends(require_admin),
):
    """Human approval gate — does not send; marks approved for later execution."""
    row = db.query(GrowthCampaign).filter(GrowthCampaign.id == campaign_id).first()
    if not row:
        raise HTTPException(404, "Campaign not found")
    row.status = "approved"
    db.commit()
    db.refresh(row)
    return _campaign_out(row)


@router.post("/api/growth/campaigns/{campaign_id}/push-email-mautic")
def push_email_to_mautic(
    campaign_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin: str = Depends(require_admin),
):
    """
    Step 5 — Email path: take approved (or ready) AI email pack → Mautic email drafts.
    Never bulk-sends. Cold outreach must use AgentReach, not this endpoint.
    """
    row = db.query(GrowthCampaign).filter(GrowthCampaign.id == campaign_id).first()
    if not row:
        raise HTTPException(404, "Campaign not found")
    channels = [str(c).lower() for c in (row.channels or [])]
    if channels and "email" not in channels:
        raise HTTPException(400, "Campaign has no email channel")
    pack = row.pack or {}
    email_pack = pack.get("email") or {}
    subjects = list(email_pack.get("subjects") or [])
    bodies = list(email_pack.get("bodies") or [])
    follow_ups = list(email_pack.get("follow_ups") or [])
    if not bodies and not follow_ups:
        raise HTTPException(400, "No email bodies in campaign pack — regenerate first")

    result = push_campaign_email_pack(
        campaign_name=row.name,
        subjects=subjects,
        bodies=bodies,
        follow_ups=follow_ups,
    )

    # Persist execution metadata on pack
    meta = dict(pack) if isinstance(pack, dict) else {}
    meta["mautic_email_push"] = {
        "status": result.get("status"),
        "drafts_created": result.get("drafts_created"),
        "mautic_configured": result.get("mautic_configured"),
        "drafts": result.get("drafts"),
    }
    row.pack = meta
    if result.get("status") == "ok":
        # Stay approved; note that drafts live in Mautic
        if row.status == "draft":
            row.status = "ready_for_review"
    db.commit()
    db.refresh(row)
    return {"campaign": _campaign_out(row), "mautic": result}


@router.post("/api/growth/campaigns/{campaign_id}/push-social-postiz")
def push_social_to_postiz(
    campaign_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin: str = Depends(require_admin),
):
    """
    Step 6 — Social path: LinkedIn/IG/FB captions from AI pack → Postiz (draft/queue).
    Magazine continuous articles use approve → SEO/GEO → Postiz separately.
    """
    row = db.query(GrowthCampaign).filter(GrowthCampaign.id == campaign_id).first()
    if not row:
        raise HTTPException(404, "Campaign not found")
    pack = row.pack or {}
    posts: list[str] = []
    linkedin = (pack.get("linkedin") or {}).get("posts") or []
    captions = (pack.get("social") or {}).get("captions") or []
    posts.extend([str(x) for x in linkedin if x])
    posts.extend([str(x) for x in captions if x])
    if not posts:
        raise HTTPException(400, "No LinkedIn/social captions in pack — regenerate first")

    channels = [str(c).lower() for c in (row.channels or [])]
    social_channels = [c for c in channels if c in ("linkedin", "instagram", "facebook", "social", "threads")]
    if not social_channels:
        social_channels = ["linkedin", "instagram", "facebook"]
    # normalize "social" bucket
    social_channels = ["instagram" if c == "social" else c for c in social_channels]

    result = queue_social_posts(
        campaign_id=str(row.id),
        campaign_name=row.name,
        posts=posts,
        channels=social_channels,
        cta_url=row.cta_url,
    )
    meta = dict(pack) if isinstance(pack, dict) else {}
    meta["postiz_social_push"] = {
        "status": result.get("status"),
        "posts_queued": result.get("posts_queued"),
        "postiz_configured": result.get("postiz_configured"),
        "results": result.get("results"),
    }
    row.pack = meta
    db.commit()
    db.refresh(row)
    return {"campaign": _campaign_out(row), "postiz": result}


@router.post("/api/growth/seo-geo/{run_id}/requeue-postiz")
def requeue_seo_geo_postiz(
    run_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin: str = Depends(require_admin),
):
    """Re-send magazine article distribution job for an existing SEO/GEO run."""
    run = db.query(SeoGeoRun).filter(SeoGeoRun.id == run_id).first()
    if not run:
        raise HTTPException(404, "SEO/GEO run not found")
    article = None
    try:
        from app.models.article import Article
        article = db.query(Article).filter(Article.id == run.article_id).first()
    except Exception:  # noqa: BLE001
        article = None
    headline = (run.meta_title or run.primary_keyword or run.article_id) or "WishNest"
    summary = run.direct_answer or ""
    url = f"https://wishnest.info/article/{run.article_id}"
    if article is not None:
        headline = article.headline or headline
        summary = (article.executive_summary or article.subtitle or summary)[:500]
    dist = queue_article_distribution(
        article_id=str(run.article_id),
        headline=str(headline),
        summary=str(summary or ""),
        url=url,
    )
    run.postiz_status = dist.get("status") or "queued"
    run.postiz_payload = dist
    db.commit()
    db.refresh(run)
    return {
        "id": str(run.id),
        "article_id": run.article_id,
        "postiz_status": run.postiz_status,
        "postiz": dist,
    }




# ── Surveys → ArrowX (Step 7) ──────────────────────────────────────────────

DEFAULT_SURVEY_QUESTIONS = [
    {"id": "budget", "label": "Budget range", "type": "choice", "options": ["< ₹1 Cr", "₹1–2 Cr", "₹2–3 Cr", "₹3–5 Cr", "₹5 Cr+"]},
    {"id": "property_type", "label": "Preferred property", "type": "choice", "options": ["Villa", "Apartment", "Managed Villa", "Resort room / fractional"]},
    {"id": "location", "label": "Preferred location / destination", "type": "text"},
    {"id": "intent", "label": "Primary intent", "type": "choice", "options": ["Self-use", "Managed rental", "Investment", "Hospitality project"]},
]


class SurveyCreate(BaseModel):
    title: str
    destination: str | None = None
    topic: str | None = "second_home"
    questions: list[dict[str, Any]] | None = None


@router.get("/api/growth/surveys")
def list_surveys(
    db: Session = Depends(get_db),
    admin: str = Depends(require_admin),
):
    rows = db.query(GrowthSurvey).order_by(GrowthSurvey.created_at.desc()).limit(40).all()
    out = []
    for r in rows:
        n = db.query(GrowthSurveyResponse).filter(GrowthSurveyResponse.survey_id == r.id).count()
        out.append({
            "id": str(r.id),
            "title": r.title,
            "destination": r.destination,
            "topic": r.topic,
            "status": r.status,
            "questions": r.questions,
            "response_count": n,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })
    return out


@router.post("/api/growth/surveys")
def create_survey(
    body: SurveyCreate,
    db: Session = Depends(get_db),
    admin: str = Depends(require_admin),
):
    title = (body.title or "").strip()
    if not title:
        raise HTTPException(400, "title required")
    row = GrowthSurvey(
        title=title,
        destination=(body.destination or "").strip() or None,
        topic=(body.topic or "second_home")[:128],
        status="active",
        questions=body.questions or DEFAULT_SURVEY_QUESTIONS,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {
        "id": str(row.id),
        "title": row.title,
        "destination": row.destination,
        "topic": row.topic,
        "status": row.status,
        "questions": row.questions,
        "response_count": 0,
    }


class SurveyResponseIn(BaseModel):
    email: str | None = None
    answers: dict[str, Any] = Field(default_factory=dict)
    consent_commercial: bool = False
    contact_id: str | None = None


@router.post("/api/growth/surveys/{survey_id}/responses")
def add_survey_response(
    survey_id: uuid.UUID,
    body: SurveyResponseIn,
    db: Session = Depends(get_db),
    admin: str = Depends(require_admin),
):
    survey = db.query(GrowthSurvey).filter(GrowthSurvey.id == survey_id).first()
    if not survey:
        raise HTTPException(404, "Survey not found")
    contact_uuid = None
    if body.contact_id:
        try:
            contact_uuid = uuid.UUID(body.contact_id)
        except ValueError:
            contact_uuid = None
    row = GrowthSurveyResponse(
        survey_id=survey.id,
        contact_id=contact_uuid,
        email=(body.email or "").strip().lower() or None,
        answers=body.answers or {},
        consent_commercial=bool(body.consent_commercial),
    )
    db.add(row)
    # Optionally upsert growth contact from email
    if row.email:
        existing = db.query(GrowthContact).filter(GrowthContact.email == row.email).first()
        if not existing:
            db.add(
                GrowthContact(
                    email=row.email,
                    contact_type="consumer",
                    destination=survey.destination,
                    email_permission=True,
                    source="survey",
                    tags="survey_response",
                )
            )
    db.commit()
    db.refresh(row)
    return {
        "id": str(row.id),
        "survey_id": str(survey.id),
        "email": row.email,
        "answers": row.answers,
        "consent_commercial": row.consent_commercial,
    }


@router.get("/api/growth/surveys/{survey_id}/insights")
def survey_insights(
    survey_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin: str = Depends(require_admin),
):
    survey = db.query(GrowthSurvey).filter(GrowthSurvey.id == survey_id).first()
    if not survey:
        raise HTTPException(404, "Survey not found")
    rows = db.query(GrowthSurveyResponse).filter(GrowthSurveyResponse.survey_id == survey_id).all()
    answers = [r.answers for r in rows if r.answers]
    signals = aggregate_demand_signals(answers)
    return {
        "survey_id": str(survey.id),
        "title": survey.title,
        "destination": survey.destination,
        **signals,
    }


@router.post("/api/growth/surveys/{survey_id}/to-arrowx")
def survey_to_arrowx(
    survey_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin: str = Depends(require_admin),
):
    """
    Convert aggregated survey demand into an ArrowX opportunity record.
    Only marks consent_commercial on the opportunity if any response opted in;
    does not expose individual respondent data to ArrowX payload beyond aggregates.
    """
    survey = db.query(GrowthSurvey).filter(GrowthSurvey.id == survey_id).first()
    if not survey:
        raise HTTPException(404, "Survey not found")
    rows = db.query(GrowthSurveyResponse).filter(GrowthSurveyResponse.survey_id == survey_id).all()
    if not rows:
        raise HTTPException(400, "No responses to aggregate")
    signals = aggregate_demand_signals([r.answers for r in rows if r.answers])
    any_consent = any(bool(r.consent_commercial) for r in rows)
    opp = ArrowxOpportunity(
        source_type="survey",
        source_id=str(survey.id),
        title=opportunity_title(survey.title, survey.destination, signals)[:512],
        summary=opportunity_summary(signals),
        destination=survey.destination,
        demand_signals=signals,
        status="new",
        consent_commercial=any_consent,
    )
    db.add(opp)
    db.commit()
    db.refresh(opp)
    return {
        "id": str(opp.id),
        "title": opp.title,
        "summary": opp.summary,
        "destination": opp.destination,
        "status": opp.status,
        "consent_commercial": opp.consent_commercial,
        "demand_signals": opp.demand_signals,
    }


class TestEmailIn(BaseModel):
    to_email: str
    subject: str | None = None


@router.post("/api/growth/campaigns/{campaign_id}/send-test-email")
def send_campaign_test_email(
    campaign_id: uuid.UUID,
    body: TestEmailIn,
    db: Session = Depends(get_db),
    admin: str = Depends(require_admin),
):
    """Send ONE test email of the first pack body to a single address (Brevo/SMTP)."""
    if not email_configured():
        raise HTTPException(
            400,
            "Email not configured. Set BREVO_API_KEY + BREVO_FROM_EMAIL on Render.",
        )
    to_email = (body.to_email or "").strip().lower()
    if not to_email or "@" not in to_email:
        raise HTTPException(400, "Valid to_email required")
    row = db.query(GrowthCampaign).filter(GrowthCampaign.id == campaign_id).first()
    if not row:
        raise HTTPException(404, "Campaign not found")
    pack = row.pack or {}
    email_pack = pack.get("email") or {}
    subjects = list(email_pack.get("subjects") or [])
    bodies = list(email_pack.get("bodies") or [])
    if not bodies:
        raise HTTPException(400, "No email body in pack")
    subject = (body.subject or (subjects[0] if subjects else row.name)).strip()
    subject = f"[TEST] {subject}"[:200]
    text = bodies[0]
    html = text if "<" in text else f"<html><body><pre style='font-family:sans-serif;white-space:pre-wrap'>{text}</pre></body></html>"
    try:
        send_email(to_email=to_email, subject=subject, html_body=html, text_body=text)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"Send failed: {exc}") from exc
    return {
        "status": "sent",
        "to_email": to_email,
        "subject": subject,
        "campaign_id": str(row.id),
    }


class ColdDraftIn(BaseModel):
    campaign_name: str
    audience_label: str = "Independent resort owners"
    geography: str = "India"
    offer: str = "Complimentary WishNest hospitality review"
    messages: list[str] = Field(default_factory=list)
    contact_ids: list[str] = Field(default_factory=list)


@router.post("/api/growth/agentreach/draft")
def agentreach_draft(
    body: ColdDraftIn,
    db: Session = Depends(get_db),
    admin: str = Depends(require_admin),
):
    """Cold outreach draft only — never auto-sends. Separate from Mautic nurture."""
    msgs = body.messages or [
        f"Introducing WishNest — independent hospitality intelligence. {body.offer}.",
        "Follow-up: would a structured property review be useful for your team?",
    ]
    result = create_cold_sequence_draft(
        campaign_name=body.campaign_name,
        audience_label=body.audience_label,
        geography=body.geography,
        offer=body.offer,
        messages=msgs,
        contact_ids=body.contact_ids,
    )
    job = OutreachJob(
        channel="agentreach",
        status="draft" if result.get("status") in ("draft", "stub_draft") else "error",
        title=body.campaign_name[:255],
        payload=result.get("draft"),
        result=result,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return {"job_id": str(job.id), "status": job.status, **result}


@router.post("/api/growth/agentreach/jobs/{job_id}/approve-submit")
def agentreach_approve_submit(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin: str = Depends(require_admin),
):
    """Human gate: approve cold sequence then submit to AgentReach (or stub)."""
    job = db.query(OutreachJob).filter(OutreachJob.id == job_id, OutreachJob.channel == "agentreach").first()
    if not job:
        raise HTTPException(404, "AgentReach job not found")
    payload = job.payload or {}
    result = submit_approved_sequence(payload if isinstance(payload, dict) else {"raw": payload})
    job.status = "submitted" if result.get("status") in ("submitted", "stub_submitted") else "error"
    job.result = result
    db.commit()
    db.refresh(job)
    return {"job_id": str(job.id), "status": job.status, "result": result}


class WhatsAppTestIn(BaseModel):
    phone: str
    message: str
    contact_id: str | None = None
    dry_run: bool = False


@router.post("/api/growth/whatsapp/send")
def whatsapp_send(
    body: WhatsAppTestIn,
    db: Session = Depends(get_db),
    admin: str = Depends(require_admin),
):
    """
    Single WhatsApp message — requires contact whatsapp_permission when contact_id given.
    """
    if body.contact_id:
        try:
            cid = uuid.UUID(body.contact_id)
        except ValueError as e:
            raise HTTPException(400, "invalid contact_id") from e
        contact = db.query(GrowthContact).filter(GrowthContact.id == cid).first()
        if not contact:
            raise HTTPException(404, "Contact not found")
        if contact.do_not_contact or contact.unsubscribed:
            raise HTTPException(400, "Contact suppressed")
        if not contact.whatsapp_permission:
            raise HTTPException(400, "No WhatsApp permission on contact")
        phone = body.phone or contact.phone
    else:
        phone = body.phone
    if not phone:
        raise HTTPException(400, "phone required")
    result = send_whatsapp_text(to_phone=phone, body=body.message, dry_run=body.dry_run)
    job = OutreachJob(
        channel="whatsapp",
        status=result.get("status") or "error",
        title=f"WA {phone}"[:255],
        payload={"phone": phone, "message": body.message[:500]},
        result=result,
    )
    db.add(job)
    db.commit()
    return {"job_id": str(job.id), **result}


class TelecallerIn(BaseModel):
    contact_id: str | None = None
    phone: str | None = None
    name: str | None = None
    script_summary: str = "WishNest hospitality review introduction call."
    opportunity_id: str | None = None


@router.post("/api/growth/telecaller/enqueue")
def telecaller_enqueue(
    body: TelecallerIn,
    db: Session = Depends(get_db),
    admin: str = Depends(require_admin),
):
    """Queue AI telecaller job — phone_permission required when contact linked."""
    phone = body.phone
    name = body.name
    meta: dict = {}
    if body.contact_id:
        try:
            cid = uuid.UUID(body.contact_id)
        except ValueError as e:
            raise HTTPException(400, "invalid contact_id") from e
        contact = db.query(GrowthContact).filter(GrowthContact.id == cid).first()
        if not contact:
            raise HTTPException(404, "Contact not found")
        if contact.do_not_contact:
            raise HTTPException(400, "Contact is DNC")
        if not contact.phone_permission:
            raise HTTPException(400, "No phone/call permission")
        phone = phone or contact.phone
        name = name or contact.name
        meta["contact_id"] = str(contact.id)
    if body.opportunity_id:
        meta["opportunity_id"] = body.opportunity_id
    if not phone:
        raise HTTPException(400, "phone required")
    result = enqueue_call(
        phone=phone,
        name=name,
        script_summary=body.script_summary,
        metadata=meta,
    )
    job = OutreachJob(
        channel="telecaller",
        status=result.get("status") or "error",
        title=f"Call {name or phone}"[:255],
        payload={"phone": phone, "name": name, "script": body.script_summary, "meta": meta},
        result=result,
    )
    db.add(job)
    db.commit()
    return {"job_id": str(job.id), **result}


@router.get("/api/growth/outreach/jobs")
def list_outreach_jobs(
    db: Session = Depends(get_db),
    admin: str = Depends(require_admin),
    channel: str | None = None,
    limit: int = 30,
):
    q = db.query(OutreachJob).order_by(OutreachJob.created_at.desc())
    if channel:
        q = q.filter(OutreachJob.channel == channel.strip().lower())
    rows = q.limit(min(limit, 50)).all()
    return [
        {
            "id": str(r.id),
            "channel": r.channel,
            "status": r.status,
            "title": r.title,
            "payload": r.payload,
            "result": r.result,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


# ── Public survey (no admin auth) ───────────────────────────────────────────

@router.get("/api/public/surveys/{survey_id}")
def public_get_survey(survey_id: uuid.UUID, db: Session = Depends(get_db)):
    """Public read of an active survey (questions only — no PII)."""
    survey = db.query(GrowthSurvey).filter(GrowthSurvey.id == survey_id).first()
    if not survey or survey.status != "active":
        raise HTTPException(404, "Survey not found or closed")
    return {
        "id": str(survey.id),
        "title": survey.title,
        "destination": survey.destination,
        "topic": survey.topic,
        "questions": survey.questions or [],
    }


@router.post("/api/public/surveys/{survey_id}/responses")
def public_add_survey_response(
    survey_id: uuid.UUID,
    body: SurveyResponseIn,
    db: Session = Depends(get_db),
):
    """Public submit — same storage as admin sample responses."""
    survey = db.query(GrowthSurvey).filter(GrowthSurvey.id == survey_id).first()
    if not survey or survey.status != "active":
        raise HTTPException(404, "Survey not found or closed")
    if not body.answers:
        raise HTTPException(400, "answers required")
    row = GrowthSurveyResponse(
        survey_id=survey.id,
        contact_id=None,
        email=(body.email or "").strip().lower() or None,
        answers=body.answers or {},
        consent_commercial=bool(body.consent_commercial),
    )
    db.add(row)
    if row.email:
        existing = db.query(GrowthContact).filter(GrowthContact.email == row.email).first()
        if not existing:
            db.add(
                GrowthContact(
                    email=row.email,
                    contact_type="consumer",
                    destination=survey.destination,
                    email_permission=True,
                    source="survey_public",
                    tags="survey_response,public",
                )
            )
    db.commit()
    db.refresh(row)
    return {
        "ok": True,
        "id": str(row.id),
        "message": "Thank you — your response was recorded.",
    }
