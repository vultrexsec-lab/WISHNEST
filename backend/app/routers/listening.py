"""Phase 1 Social Listening API — business → keywords → discovery → opportunities."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_admin
from app.models.listening import (
    ListeningBusiness,
    ListeningCampaign,
    ListeningDiscoveryJob,
    ListeningOpportunity,
    ListeningPost,
)
from app.services.listening import analyse_business, generate_keywords, run_discovery_job

router = APIRouter(prefix="/api/listening", tags=["listening"])


class AnalyseIn(BaseModel):
    website_url: str | None = None
    description: str | None = None
    name: str | None = None


class BusinessCreate(BaseModel):
    name: str
    website_url: str | None = None
    description: str | None = None
    analyse: bool = True


class CampaignCreate(BaseModel):
    business_id: UUID
    name: str
    platforms: list[str] = Field(default_factory=lambda: ["reddit", "bluesky", "youtube", "web"])
    generate_keywords: bool = True


class DiscoveryIn(BaseModel):
    campaign_id: UUID
    platforms: list[str] | None = None


@router.get("/status")
def listening_status(_: str = Depends(require_admin)):
    return {
        "module": "arrowx_listening_phase1",
        "platforms": {
            "reddit": "public JSON search",
            "bluesky": "public API",
            "youtube": "YOUTUBE_API_KEY optional",
            "web": "best-effort public results",
        },
        "compliance": "Public conversation intelligence only — not cold-contact lists",
    }


@router.post("/business/analyse")
def api_analyse(body: AnalyseIn, _: str = Depends(require_admin)):
    if not body.website_url and not body.description:
        raise HTTPException(400, "website_url or description required")
    return analyse_business(
        website_url=body.website_url,
        description=body.description,
        name=body.name,
    )


@router.post("/businesses")
def create_business(body: BusinessCreate, db: Session = Depends(get_db), _: str = Depends(require_admin)):
    profile = None
    category = None
    offerings = None
    markets = None
    personas = None
    if body.analyse:
        profile = analyse_business(
            website_url=body.website_url,
            description=body.description,
            name=body.name,
        )
        category = profile.get("business_category")
        offerings = profile.get("offerings")
        markets = profile.get("target_markets")
        personas = profile.get("buyer_personas")
        name = profile.get("business_name") or body.name
    else:
        name = body.name
    row = ListeningBusiness(
        name=name,
        website_url=body.website_url,
        description=body.description,
        category=category,
        offerings=offerings,
        target_markets=markets,
        buyer_personas=personas,
        profile=profile,
        status="active",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _biz(row)


@router.get("/businesses")
def list_businesses(db: Session = Depends(get_db), _: str = Depends(require_admin)):
    rows = db.query(ListeningBusiness).order_by(ListeningBusiness.created_at.desc()).limit(50).all()
    return [_biz(r) for r in rows]


@router.post("/campaigns")
def create_campaign(body: CampaignCreate, db: Session = Depends(get_db), _: str = Depends(require_admin)):
    biz = db.get(ListeningBusiness, body.business_id)
    if not biz:
        raise HTTPException(404, "business not found")
    keywords = None
    if body.generate_keywords:
        keywords = generate_keywords(
            category=biz.category or biz.name,
            offerings=list(biz.offerings or []) if biz.offerings else None,
            locations=list(biz.target_markets or []) if biz.target_markets else None,
        )
    row = ListeningCampaign(
        business_id=biz.id,
        name=body.name,
        platforms=body.platforms,
        keywords=keywords,
        negative_keywords=(keywords or {}).get("negative") if keywords else None,
        target_geography=biz.target_markets,
        status="active",
        meta={"category": biz.category},
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _camp(row)


@router.get("/campaigns")
def list_campaigns(db: Session = Depends(get_db), _: str = Depends(require_admin)):
    rows = db.query(ListeningCampaign).order_by(ListeningCampaign.created_at.desc()).limit(50).all()
    return [_camp(r) for r in rows]


@router.post("/keywords/generate")
def api_keywords(
    category: str,
    locations: str | None = None,
    _: str = Depends(require_admin),
):
    locs = [x.strip() for x in (locations or "").split(",") if x.strip()] or None
    return generate_keywords(category=category, locations=locs)


@router.post("/discovery/jobs")
def start_discovery(body: DiscoveryIn, db: Session = Depends(get_db), _: str = Depends(require_admin)):
    camp = db.get(ListeningCampaign, body.campaign_id)
    if not camp:
        raise HTTPException(404, "campaign not found")
    job = ListeningDiscoveryJob(
        campaign_id=camp.id,
        status="queued",
        platforms=body.platforms or camp.platforms,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    result = run_discovery_job(db, job.id)
    db.refresh(job)
    return {
        "job": _job(job),
        "result": result,
    }


@router.get("/discovery/jobs/{job_id}")
def get_job(job_id: UUID, db: Session = Depends(get_db), _: str = Depends(require_admin)):
    job = db.get(ListeningDiscoveryJob, job_id)
    if not job:
        raise HTTPException(404, "job not found")
    return _job(job)


@router.get("/opportunities")
def list_opportunities(
    campaign_id: UUID | None = None,
    min_score: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
):
    q = db.query(ListeningOpportunity).order_by(
        ListeningOpportunity.intent_score.desc(),
        ListeningOpportunity.created_at.desc(),
    )
    if campaign_id:
        q = q.filter(ListeningOpportunity.campaign_id == campaign_id)
    if min_score:
        q = q.filter(ListeningOpportunity.intent_score >= min_score)
    rows = q.limit(min(limit, 100)).all()
    return [_opp(r) for r in rows]


@router.get("/posts")
def list_posts(
    campaign_id: UUID | None = None,
    limit: int = 40,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
):
    q = db.query(ListeningPost).order_by(ListeningPost.collected_at.desc())
    if campaign_id:
        q = q.filter(ListeningPost.campaign_id == campaign_id)
    return [
        {
            "id": str(p.id),
            "platform": p.platform,
            "url": p.url,
            "title": p.title,
            "body": (p.body or "")[:300],
            "author_handle": p.author_handle,
            "like_count": p.like_count,
            "comment_count": p.comment_count,
            "collected_at": p.collected_at.isoformat() if p.collected_at else None,
        }
        for p in q.limit(min(limit, 100)).all()
    ]


@router.get("/overview")
def overview(db: Session = Depends(get_db), _: str = Depends(require_admin)):
    return {
        "businesses": db.query(ListeningBusiness).count(),
        "campaigns": db.query(ListeningCampaign).count(),
        "posts": db.query(ListeningPost).count(),
        "opportunities": db.query(ListeningOpportunity).count(),
        "high_intent": db.query(ListeningOpportunity)
        .filter(ListeningOpportunity.intent_score >= 80)
        .count(),
    }


def _biz(r: ListeningBusiness) -> dict[str, Any]:
    return {
        "id": str(r.id),
        "name": r.name,
        "website_url": r.website_url,
        "category": r.category,
        "offerings": r.offerings,
        "target_markets": r.target_markets,
        "buyer_personas": r.buyer_personas,
        "profile": r.profile,
        "status": r.status,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


def _camp(r: ListeningCampaign) -> dict[str, Any]:
    return {
        "id": str(r.id),
        "business_id": str(r.business_id),
        "name": r.name,
        "platforms": r.platforms,
        "keywords": r.keywords,
        "status": r.status,
        "last_run_at": r.last_run_at.isoformat() if r.last_run_at else None,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


def _job(r: ListeningDiscoveryJob) -> dict[str, Any]:
    return {
        "id": str(r.id),
        "campaign_id": str(r.campaign_id),
        "status": r.status,
        "platforms": r.platforms,
        "posts_found": r.posts_found,
        "opportunities_created": r.opportunities_created,
        "error": r.error,
        "started_at": r.started_at.isoformat() if r.started_at else None,
        "finished_at": r.finished_at.isoformat() if r.finished_at else None,
    }


def _opp(r: ListeningOpportunity) -> dict[str, Any]:
    return {
        "id": str(r.id),
        "campaign_id": str(r.campaign_id) if r.campaign_id else None,
        "platform": r.platform,
        "source_url": r.source_url,
        "excerpt": r.excerpt,
        "category": r.category,
        "requirement": r.requirement,
        "location": r.location,
        "budget_hint": r.budget_hint,
        "intent_score": r.intent_score,
        "intent_band": r.intent_band,
        "stage": r.stage,
        "recommended_action": r.recommended_action,
        "contact_eligible": r.contact_eligible,
        "public_author": r.public_author,
        "evidence": r.evidence,
        "status": r.status,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }
