"""
Newsletter endpoints:
  POST /api/newsletter/subscribe   — add an email (idempotent) + optional interests.
  POST /api/newsletter/unsubscribe — remove an email (idempotent).
  GET  /api/newsletter/count       — admin total count.
  GET  /api/newsletter/stats       — admin counts by interest segment.
  GET  /api/newsletter/subscribers — admin list (email + interests).
"""
import logging
import re
from collections import Counter

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_admin
from app.models.newsletter import NewsletterSubscriber

router = APIRouter(tags=["newsletter"])
logger = logging.getLogger("wishnest.newsletter")

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_ALLOWED_INTERESTS = {
    "architecture",
    "hotels",
    "resorts",
    "villas",
    "second-homes",
    "design",
    "reimagined",
}


class SubscribeRequest(BaseModel):
    email: str
    interests: list[str] | None = None


class SubscribeResponse(BaseModel):
    message: str


class SubscriberCountResponse(BaseModel):
    count: int


class SegmentStat(BaseModel):
    interest: str
    count: int


class NewsletterStatsResponse(BaseModel):
    total: int
    segments: list[SegmentStat]


class SubscriberOut(BaseModel):
    email: str
    interests: str | None
    created_at: str | None


def _normalize_interests(raw: list[str] | None) -> str | None:
    if not raw:
        return None
    cleaned = []
    for item in raw:
        tag = (item or "").strip().lower().replace(" ", "-")
        if tag in _ALLOWED_INTERESTS and tag not in cleaned:
            cleaned.append(tag)
    return ",".join(cleaned) if cleaned else None


@router.get("/api/newsletter/count", response_model=SubscriberCountResponse)
def subscriber_count(
    db: Session = Depends(get_db),
    admin: str = Depends(require_admin),
):
    count = db.query(NewsletterSubscriber).count()
    return SubscriberCountResponse(count=count)


@router.get("/api/newsletter/stats", response_model=NewsletterStatsResponse)
def newsletter_stats(
    db: Session = Depends(get_db),
    admin: str = Depends(require_admin),
):
    rows = db.query(NewsletterSubscriber).all()
    total = len(rows)
    counter: Counter[str] = Counter()
    for r in rows:
        if not r.interests:
            counter["general"] += 1
            continue
        tags = [t.strip() for t in r.interests.split(",") if t.strip()]
        if not tags:
            counter["general"] += 1
        for t in tags:
            counter[t] += 1
    segments = [
        SegmentStat(interest=k, count=v)
        for k, v in sorted(counter.items(), key=lambda x: (-x[1], x[0]))
    ]
    return NewsletterStatsResponse(total=total, segments=segments)


@router.get("/api/newsletter/subscribers", response_model=list[SubscriberOut])
def list_subscribers(
    db: Session = Depends(get_db),
    admin: str = Depends(require_admin),
    interest: str | None = None,
):
    q = db.query(NewsletterSubscriber).order_by(NewsletterSubscriber.created_at.desc()).limit(500)
    rows = q.all()
    out: list[SubscriberOut] = []
    interest_f = (interest or "").strip().lower()
    for r in rows:
        if interest_f:
            tags = (r.interests or "").lower().split(",")
            tags = [t.strip() for t in tags]
            if interest_f == "general":
                if r.interests and r.interests.strip():
                    continue
            elif interest_f not in tags:
                continue
        out.append(
            SubscriberOut(
                email=r.email,
                interests=r.interests,
                created_at=r.created_at.isoformat() if r.created_at else None,
            )
        )
    return out


@router.post("/api/newsletter/subscribe", response_model=SubscribeResponse)
def subscribe(payload: SubscribeRequest, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()
    if not _EMAIL_RE.match(email):
        return SubscribeResponse(message="Invalid email address")

    interests = _normalize_interests(payload.interests)

    existing = (
        db.query(NewsletterSubscriber)
        .filter(NewsletterSubscriber.email == email)
        .first()
    )
    if existing:
        # Update interests if provided (merge)
        if interests:
            old = set((existing.interests or "").split(",")) if existing.interests else set()
            old = {x.strip() for x in old if x.strip()}
            new = set(interests.split(","))
            merged = ",".join(sorted(old | new))
            existing.interests = merged or None
            db.commit()
        return SubscribeResponse(message="Subscribed successfully")

    subscriber = NewsletterSubscriber(email=email, interests=interests)
    db.add(subscriber)
    try:
        db.commit()
        logger.info("New subscriber: %s interests=%s", email, interests)
    except IntegrityError:
        db.rollback()
    return SubscribeResponse(message="Subscribed successfully")


@router.post("/api/newsletter/unsubscribe", response_model=SubscribeResponse)
def unsubscribe(payload: SubscribeRequest, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()
    if not _EMAIL_RE.match(email):
        return SubscribeResponse(
            message="If that address was subscribed, it has been removed."
        )
    existing = (
        db.query(NewsletterSubscriber)
        .filter(NewsletterSubscriber.email == email)
        .first()
    )
    if existing:
        db.delete(existing)
        db.commit()
        logger.info("Unsubscribed: %s", email)
    return SubscribeResponse(
        message="If that address was subscribed, it has been removed."
    )
