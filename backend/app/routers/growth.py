"""Growth & Intelligence OS — admin APIs (Campaign Manager control module)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_admin
from app.models.growth import ArrowxOpportunity, GrowthContact, SeoGeoRun
from app.services.agentreach_service import agentreach_configured, create_cold_sequence_draft
from app.services.postiz_service import postiz_configured
from app.services.email_service import email_configured

router = APIRouter(tags=["growth-os"])


class GrowthStatusOut(BaseModel):
    product: str
    pipeline: str
    integrations: dict[str, bool]
    counts: dict[str, int]


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
            "mautic": False,  # Phase B
            "whatsapp_business": False,
            "telecaller": False,
        },
        counts={
            "contacts": db.query(GrowthContact).count(),
            "arrowx_opportunities": db.query(ArrowxOpportunity).count(),
            "seo_geo_runs": db.query(SeoGeoRun).count(),
        },
    )


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
    messages: list[str] = []


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
