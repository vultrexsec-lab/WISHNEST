"""
PUT /api/approve-article/{id}

Human-in-the-loop approval endpoint. An article is never published or
scheduled automatically — it always starts as 'draft' and only moves to
'approved' / 'scheduled' once a human calls this endpoint from the frontend.

When an article is approved (made live), a newsletter email is sent to all
subscribers via Gmail SMTP (if GMAIL_USER + GMAIL_APP_PASSWORD are configured).
"""
import logging
import threading
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.dependencies import require_admin
from app.models.article import Article, ArticleStatus
from app.models.newsletter import NewsletterSubscriber
from app.schemas.article import ApproveArticleRequest, ApproveArticleResponse
from app.services.email_service import send_article_to_subscribers, email_configured

router = APIRouter(tags=["approval"])
logger = logging.getLogger("wishnest.approve")


def _send_newsletter_background(article_id: str) -> None:
    """Load article + subscribers in a fresh DB session and send emails."""
    db = SessionLocal()
    try:
        article = db.query(Article).filter(Article.id == article_id).first()
        if not article:
            return
        if article.newsletter_sent_at is not None:
            logger.info("Newsletter already sent for %s — skip", article_id)
            return

        emails = [row.email for row in db.query(NewsletterSubscriber).all()]
        summary = (
            (article.newsletter_summary or "").strip()
            or (article.executive_summary or "").strip()
            or (article.subtitle or "").strip()
            or (article.wishnest_verdict or "").strip()
            or "A new editorial piece is live on WishNest."
        )
        result = send_article_to_subscribers(
            emails=emails,
            headline=article.headline or "New on WishNest",
            summary=summary[:800],
            article_id=str(article.id),
            hero_image_url=article.hero_image_url,
        )
        if result.get("sent", 0) > 0:
            article.newsletter_sent_at = datetime.now(timezone.utc)
            if article.published_at is None:
                article.published_at = datetime.now(timezone.utc)
            db.commit()
            logger.info(
                "Newsletter for %s: sent=%s failed=%s",
                article_id,
                result.get("sent"),
                result.get("failed"),
            )
        else:
            logger.warning(
                "Newsletter not marked sent for %s: %s",
                article_id,
                result,
            )
    except Exception as exc:
        logger.exception("Newsletter background job failed for %s: %s", article_id, exc)
        db.rollback()
    finally:
        db.close()


@router.put("/api/approve-article/{article_id}", response_model=ApproveArticleResponse)
def approve_article(
    article_id: uuid.UUID,
    payload: ApproveArticleRequest,
    db: Session = Depends(get_db),
    admin: str = Depends(require_admin),
):
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    if payload.scheduled_at:
        article.status = ArticleStatus.scheduled
        article.scheduled_at = payload.scheduled_at
    else:
        article.status = ArticleStatus.approved
        if article.published_at is None:
            article.published_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(article)

    # Fire-and-forget newsletter (does not block the approve response)
    if email_configured():
        threading.Thread(
            target=_send_newsletter_background,
            args=(str(article.id),),
            daemon=True,
        ).start()
        logger.info("Newsletter job started for article %s", article.id)
    else:
        logger.info(
            "Approve ok; newsletter not sent (set BREVO_API_KEY + BREVO_FROM_EMAIL)"
        )

    return article
