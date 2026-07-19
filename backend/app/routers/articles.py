"""
GET    /api/articles                       - list articles; optional ?status=, ?category=, ?search=, ?trash= (admin only)
GET    /api/articles/{id}                  - fetch a single article
PUT    /api/approve-article/{id}           - human approval + optional scheduling (registered in main.py)
PUT    /api/articles/{id}/trash            - move an article to the Recycle Bin (admin only)
PUT    /api/articles/{id}/restore          - restore an article out of the Recycle Bin back to draft (admin only)
PUT    /api/articles/{id}/regenerate-images - re-fetch hero/section images for an existing article (admin only)
DELETE /api/articles/{id}                  - permanently delete an article (admin only)
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import optional_admin, require_admin
from app.models.article import Article, ArticleStatus
from app.schemas.article import ArticleOut
from app.services.research_pipeline import regenerate_article_images

router = APIRouter(tags=["articles"])

PUBLIC_STATUSES = [ArticleStatus.approved, ArticleStatus.scheduled, ArticleStatus.published]

# Every response that serves live article data must never be cached by the
# browser, a CDN, or an intermediate proxy — approved/published articles
# must be visible instantly everywhere, not just after a hard refresh.
_NO_STORE_HEADERS = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
}


@router.get("/api/articles", response_model=list[ArticleOut])
def list_articles(
    response: Response,
    status: ArticleStatus | None = None,
    category: str | None = None,
    search: str | None = None,
    trash: bool = False,
    db: Session = Depends(get_db),
    admin: str | None = Depends(optional_admin),
):
    response.headers.update(_NO_STORE_HEADERS)

    query = db.query(Article)

    # --- Recycle Bin visibility ---
    # Trashed articles never appear anywhere — public site or admin's normal
    # tabs — except in the dedicated Trash tab, which only an authenticated
    # admin may request via ?trash=true.
    if trash:
        if not admin:
            raise HTTPException(status_code=403, detail="Admin access required to view the Recycle Bin.")
        query = query.filter(Article.is_trash.is_(True))
    else:
        query = query.filter(Article.is_trash.is_(False))

        # --- Status visibility ---
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

    articles = query.order_by(Article.created_at.desc()).all()
    # Sanitise legacy rows: ARRAY columns may contain NULL entries written
    # before the image-service None-filter was added. Strip them in-place so
    # Pydantic never sees a None inside list[str] even if the schema validator
    # somehow doesn't fire (e.g. response_model bypass paths).
    for a in articles:
        if a.section_image_urls:
            # Mirror the schema validator: accept only fully-formed http(s) URLs.
            # This removes None entries (legacy rows), empty strings, and placeholder
            # strings like "[Section 5 — Property Name…]" that the image service
            # writes when a slot cannot be filled with a real image URL.
            a.section_image_urls = [
                u for u in a.section_image_urls
                if isinstance(u, str) and (
                    u.startswith("http://") or u.startswith("https://")
                )
            ]
    return articles


@router.get("/api/articles/{article_id}", response_model=ArticleOut)
def get_article(
    article_id: uuid.UUID,
    response: Response,
    db: Session = Depends(get_db),
    admin: str | None = Depends(optional_admin),
):
    response.headers.update(_NO_STORE_HEADERS)

    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    if not admin and (article.is_trash or article.status not in PUBLIC_STATUSES):
        raise HTTPException(status_code=404, detail="Article not found")
    return article


@router.put("/api/articles/{article_id}/trash", response_model=ArticleOut)
def trash_article(
    article_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin: str = Depends(require_admin),
):
    """Move an article to the Recycle Bin. It immediately disappears from
    both the active dashboard tabs and the public site, but is not deleted —
    it can be restored later."""
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    article.is_trash = True
    db.commit()
    db.refresh(article)
    return article


@router.put("/api/articles/{article_id}/restore", response_model=ArticleOut)
def restore_article(
    article_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin: str = Depends(require_admin),
):
    """Restore a trashed article back to the active dashboard as a draft."""
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    article.is_trash = False
    article.status = ArticleStatus.draft
    db.commit()
    db.refresh(article)
    return article


@router.put("/api/articles/{article_id}/regenerate-images", response_model=ArticleOut)
def regenerate_images(
    article_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin: str = Depends(require_admin),
):
    """
    Re-run the live photo pipeline for one existing article (e.g. because it
    was originally generated before a live photo provider was configured, or
    ended up with a thin/duplicated gallery). Does not touch the article
    text — only hero_image_url, section_image_urls, the injected <figure>
    blocks in full_article, and (if live ratings are available) the ABCDE
    scores.
    """
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    regenerate_article_images(article, db)
    db.refresh(article)
    return article


@router.delete("/api/articles/{article_id}", status_code=204)
def delete_article(
    article_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin: str = Depends(require_admin),
):
    """Permanently wipe an article's record from the database. Irreversible —
    intended to be called from the Recycle Bin's "Delete Permanently" action."""
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    db.delete(article)
    db.commit()
    return None
