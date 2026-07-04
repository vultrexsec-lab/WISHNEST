"""
PUT /api/approve-article/{id}

Human-in-the-loop approval endpoint. An article is never published or
scheduled automatically — it always starts as 'draft' and only moves to
'approved' / 'scheduled' once a human calls this endpoint from the frontend.

NOTE: this only flips status/scheduling metadata. The actual "publish at the
scheduled time" trigger (e.g. a cron/worker job) is intentionally not wired
up yet — structure only, per current scope.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_admin
from app.models.article import Article, ArticleStatus
from app.schemas.article import ApproveArticleRequest, ApproveArticleResponse

router = APIRouter(tags=["approval"])


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

    db.commit()
    db.refresh(article)
    return article
