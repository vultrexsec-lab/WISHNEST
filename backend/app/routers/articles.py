"""
GET  /api/articles              - list articles; optional ?status=, ?category=, ?search=
GET  /api/articles/{id}         - fetch a single article
PUT  /api/approve-article/{id}  - human approval + optional scheduling (registered in main.py)
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import optional_admin
from app.models.article import Article, ArticleStatus
from app.schemas.article import ArticleOut

router = APIRouter(tags=["articles"])

PUBLIC_STATUSES = [ArticleStatus.approved, ArticleStatus.scheduled, ArticleStatus.published]


@router.get("/api/articles", response_model=list[ArticleOut])
def list_articles(
    status: ArticleStatus | None = None,
    category: str | None = None,
    search: str | None = None,
    db: Session = Depends(get_db),
    admin: str | None = Depends(optional_admin),
):
    query = db.query(Article)

    # --- Visibility ---
    if admin:
        if status is not None:
            query = query.filter(Article.status == status)
    else:
        if status is not None and status in PUBLIC_STATUSES:
            query = query.filter(Article.status == status)
        else:
            query = query.filter(Article.status.in_(PUBLIC_STATUSES))

    # --- Category filter ---
    if category:
        query = query.filter(Article.category == category)

    # --- Full-text search (headline, subtitle, location, focus_keyword) ---
    if search:
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Article.headline.ilike(term),
                Article.subtitle.ilike(term),
                Article.location.ilike(term),
                Article.focus_keyword.ilike(term),
                Article.executive_summary.ilike(term),
            )
        )

    return query.order_by(Article.created_at.desc()).all()


@router.get("/api/articles/{article_id}", response_model=ArticleOut)
def get_article(
    article_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin: str | None = Depends(optional_admin),
):
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    if not admin and article.status not in PUBLIC_STATUSES:
        raise HTTPException(status_code=404, detail="Article not found")
    return article
