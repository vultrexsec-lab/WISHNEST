from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID
from sqlalchemy.orm import Session
from app.models.listening import ListeningCampaign, ListeningDiscoveryJob, ListeningOpportunity, ListeningPost
from app.services.listening.connectors import search_all
from app.services.listening.intent import classify_conversation
logger = logging.getLogger("wishnest.listening.discovery")

def run_discovery_job(db: Session, job_id: UUID) -> dict[str, Any]:
    job = db.get(ListeningDiscoveryJob, job_id)
    if not job: return {"status": "error", "detail": "job not found"}
    campaign = db.get(ListeningCampaign, job.campaign_id)
    if not campaign:
        job.status, job.error = "failed", "campaign missing"; db.commit()
        return {"status": "error", "detail": "campaign missing"}
    job.status = "running"
    job.started_at = datetime.now(timezone.utc)
    db.commit()
    try:
        kw_blob = campaign.keywords or {}
        keywords = list(kw_blob.get("buying_intent") or []) + list(kw_blob.get("primary") or []) if isinstance(kw_blob, dict) else list(kw_blob or [])
        keywords = [str(k) for k in keywords if k][:15]
        platforms = job.platforms or campaign.platforms or ["reddit", "bluesky", "youtube", "web"]
        if isinstance(platforms, str): platforms = [platforms]
        posts_data = search_all(keywords, list(platforms), limit_per=6)
        posts_found, opps = 0, 0
        category = (campaign.meta or {}).get("category") if isinstance(campaign.meta, dict) else None
        for pd in posts_data:
            url = (pd.get("url") or "").strip()
            if not url: continue
            body = f"{pd.get('title') or ''}\n{pd.get('body') or ''}".strip()
            post = ListeningPost(campaign_id=campaign.id, platform=pd.get("platform") or "web",
                external_id=pd.get("external_id"), url=url[:1024], title=(pd.get("title") or "")[:512] or None,
                body=body[:8000] or None, author_handle=pd.get("author_handle"),
                comment_count=int(pd.get("comment_count") or 0), like_count=int(pd.get("like_count") or 0),
                share_count=int(pd.get("share_count") or 0), raw=pd.get("raw"))
            db.add(post); db.flush(); posts_found += 1
            must = []
            if isinstance(kw_blob, dict):
                must = list(kw_blob.get("must_match_any") or kw_blob.get("primary") or [])[:12]
            classified = classify_conversation(body, category_hint=category, must_terms=must)
            if classified.get("intent_band") == "noise":
                continue
            if classified["intent_score"] < 55:
                continue
            if (pd.get("raw") or {}).get("stub"):
                continue
            db.add(ListeningOpportunity(
                campaign_id=campaign.id, post_id=post.id, platform=post.platform, source_url=post.url,
                excerpt=(body[:500] if body else None), category=classified.get("category"),
                requirement=classified.get("requirement"), location=classified.get("location"),
                budget_hint=classified.get("budget_hint"), intent_score=classified.get("intent_score") or 0,
                intent_band=classified.get("intent_band"), stage=classified.get("stage"),
                recommended_action=classified.get("recommended_action"), contact_eligible=False,
                public_author=post.author_handle,
                evidence={"signals": classified.get("signals"), "title": post.title, "platform": post.platform},
                status="new"))
            opps += 1
        campaign.last_run_at = datetime.now(timezone.utc)
        job.posts_found, job.opportunities_created, job.status = posts_found, opps, "done"
        job.finished_at = datetime.now(timezone.utc)
        db.commit()
        return {"status": "done", "posts_found": posts_found, "opportunities_created": opps, "job_id": str(job.id)}
    except Exception as exc:
        logger.exception("Discovery failed: %s", exc)
        job.status, job.error = "failed", str(exc)[:1000]
        job.finished_at = datetime.now(timezone.utc)
        db.commit()
        return {"status": "failed", "detail": str(exc)}
