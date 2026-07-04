"""
Newsletter endpoints:
  POST /api/newsletter/subscribe   — add an email (idempotent).
  POST /api/newsletter/unsubscribe — remove an email (idempotent).
"""
import logging
import re

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.newsletter import NewsletterSubscriber

router = APIRouter(tags=["newsletter"])
logger = logging.getLogger("wishnest.newsletter")

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class SubscribeRequest(BaseModel):
    email: str


class SubscribeResponse(BaseModel):
    message: str


@router.post("/api/newsletter/subscribe", response_model=SubscribeResponse)
def subscribe(payload: SubscribeRequest, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()

    if not _EMAIL_RE.match(email):
        return SubscribeResponse(message="Invalid email address")

    existing = (
        db.query(NewsletterSubscriber)
        .filter(NewsletterSubscriber.email == email)
        .first()
    )
    if existing:
        # Idempotent — same success response, no enumeration leakage
        return SubscribeResponse(message="Subscribed successfully")

    subscriber = NewsletterSubscriber(email=email)
    db.add(subscriber)
    try:
        db.commit()
        logger.info("New subscriber: %s", email)
    except IntegrityError:
        db.rollback()  # race condition — already inserted
    return SubscribeResponse(message="Subscribed successfully")


@router.post("/api/newsletter/unsubscribe", response_model=SubscribeResponse)
def unsubscribe(payload: SubscribeRequest, db: Session = Depends(get_db)):
    """
    Idempotent unsubscribe.  Returns the same generic message whether or not
    the email existed — prevents subscriber-existence enumeration.
    NOTE: For a fully hardened flow, send a signed one-time token link via
    email instead of accepting a raw email POST.
    """
    email = payload.email.strip().lower()

    if not _EMAIL_RE.match(email):
        return SubscribeResponse(message="If that address was subscribed, it has been removed.")

    existing = (
        db.query(NewsletterSubscriber)
        .filter(NewsletterSubscriber.email == email)
        .first()
    )
    if existing:
        db.delete(existing)
        db.commit()
        logger.info("Unsubscribed: %s", email)

    # Same response regardless — no enumeration leakage
    return SubscribeResponse(message="If that address was subscribed, it has been removed.")
