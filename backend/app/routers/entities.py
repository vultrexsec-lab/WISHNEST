"""
Public entity / knowledge-graph endpoints for destinations and related editorial.
Supports GEO: stable entity URLs, related reviews, internal linking.
"""
from __future__ import annotations

import re
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.article import Article, ArticleStatus

router = APIRouter(tags=["entities"])

# Seed destinations (India hospitality / second-home focus) — expanded by live article data
SEED_DESTINATIONS: list[dict[str, str]] = [
    {"slug": "lonavala", "name": "Lonavala", "region": "Maharashtra", "tagline": "Western Ghats weekenders & villa communities"},
    {"slug": "alibaug", "name": "Alibaug", "region": "Maharashtra", "tagline": "Coastal second homes & boutique stays"},
    {"slug": "mulshi", "name": "Mulshi", "region": "Maharashtra", "tagline": "Lake-facing retreats near Pune"},
    {"slug": "pune", "name": "Pune", "region": "Maharashtra", "tagline": "City base for Western Ghats escapes"},
    {"slug": "mussoorie", "name": "Mussoorie", "region": "Uttarakhand", "tagline": "Hill hospitality & heritage stays"},
    {"slug": "dehradun", "name": "Dehradun", "region": "Uttarakhand", "tagline": "Valley gateway & wellness"},
    {"slug": "nainital", "name": "Nainital", "region": "Uttarakhand", "tagline": "Lake district hospitality"},
    {"slug": "bhimtal", "name": "Bhimtal", "region": "Uttarakhand", "tagline": "Quiet lakeside escapes"},
    {"slug": "uttarakhand", "name": "Uttarakhand", "region": "Himalaya", "tagline": "Oak forests, valley retreats & alpine sanctuaries"},
    {"slug": "rajasthan", "name": "Rajasthan", "region": "Rajputana", "tagline": "Heritage havelis & desert lodges"},
    {"slug": "kerala", "name": "Kerala", "region": "Coastal South", "tagline": "Backwaters, spice gardens & biophilic retreats"},
    {"slug": "coorg", "name": "Coorg", "region": "Western Ghats", "tagline": "Coffee estates & mist valleys"},
    {"slug": "wayanad", "name": "Wayanad", "region": "Western Ghats", "tagline": "Jungle hideaways & estate stays"},
    {"slug": "himachal-pradesh", "name": "Himachal Pradesh", "region": "Himalaya", "tagline": "Orchards, pine forests & mountain villages"},
    {"slug": "goa", "name": "Goa", "region": "West Coast", "tagline": "Boutique hospitality & villa culture"},
]


def _slugify(text: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9\s-]", "", (text or "").lower())
    s = re.sub(r"\s+", "-", s.strip())
    return s[:80] or "destination"


def _seed_by_slug(slug: str) -> dict[str, str] | None:
    slug = slug.lower().strip()
    for d in SEED_DESTINATIONS:
        if d["slug"] == slug:
            return d
    return None


def _article_card(a: Article) -> dict[str, Any]:
    return {
        "id": str(a.id),
        "headline": a.headline,
        "subtitle": a.subtitle,
        "location": a.location,
        "category": a.category,
        "hero_image_url": a.hero_image_url,
        "status": a.status.value if hasattr(a.status, "value") else str(a.status),
        "published_at": a.published_at.isoformat() if a.published_at else None,
    }


def _published_filter():
    return Article.status.in_(
        [ArticleStatus.approved, ArticleStatus.published, ArticleStatus.scheduled]
    )


@router.get("/api/public/entities/destinations")
def list_destination_entities(db: Session = Depends(get_db)):
    """List destination entities: seed + locations seen on published articles."""
    by_slug: dict[str, dict[str, Any]] = {
        d["slug"]: {**d, "article_count": 0, "source": "seed"} for d in SEED_DESTINATIONS
    }
    rows = (
        db.query(Article.location)
        .filter(_published_filter())
        .filter(Article.is_trash.is_(False))
        .filter(Article.location.isnot(None))
        .filter(Article.location != "")
        .all()
    )
    counts: dict[str, int] = {}
    for (loc,) in rows:
        if not loc:
            continue
        slug = _slugify(loc)
        counts[slug] = counts.get(slug, 0) + 1
        if slug not in by_slug:
            by_slug[slug] = {
                "slug": slug,
                "name": loc.strip(),
                "region": "",
                "tagline": "WishNest editorial coverage",
                "article_count": 0,
                "source": "articles",
            }
        # fuzzy: also bump seed if location contains seed name
        for d in SEED_DESTINATIONS:
            if d["name"].lower() in loc.lower() or loc.lower() in d["name"].lower():
                by_slug[d["slug"]]["article_count"] = by_slug[d["slug"]].get("article_count", 0) + 1
    for slug, n in counts.items():
        if slug in by_slug and by_slug[slug].get("source") == "articles":
            by_slug[slug]["article_count"] = n
    out = sorted(by_slug.values(), key=lambda x: (-int(x.get("article_count") or 0), x.get("name") or ""))
    return {"destinations": out}


@router.get("/api/public/entities/destinations/{slug}")
def get_destination_entity(slug: str, db: Session = Depends(get_db)):
    """
    Destination entity hub: metadata + related published articles/reviews.
    """
    slug = _slugify(slug)
    seed = _seed_by_slug(slug)
    name = seed["name"] if seed else slug.replace("-", " ").title()

    # Match location containing name or slug tokens
    tokens = [name, slug.replace("-", " ")]
    clauses = []
    for tok in tokens:
        clauses.append(Article.location.ilike(f"%{tok}%"))
        clauses.append(Article.headline.ilike(f"%{tok}%"))
    articles = (
        db.query(Article)
        .filter(_published_filter())
        .filter(Article.is_trash.is_(False))
        .filter(or_(*clauses))
        .order_by(Article.published_at.desc().nullslast(), Article.created_at.desc())
        .limit(40)
        .all()
    )

    reviews = [a for a in articles if (a.category or "").lower() in ("reviews", "review", "") or getattr(a, "article_type", None) == "review"]
    intelligence = [a for a in articles if (a.category or "").lower() in ("intelligence", "destinations", "best-of", "best_of")]
    reimagined = [a for a in articles if (a.category or "").lower() in ("reimagined", "reimaging")]

    entity = {
        "slug": slug,
        "name": name,
        "region": seed["region"] if seed else None,
        "tagline": seed["tagline"] if seed else "WishNest destination intelligence",
        "type": "destination",
        "url": f"https://wishnest.info/destination/{slug}",
        "schema": {
            "@context": "https://schema.org",
            "@type": "TouristDestination",
            "name": name,
            "description": seed["tagline"] if seed else f"WishNest editorial coverage of {name}",
            "url": f"https://wishnest.info/destination/{slug}",
        },
        "related": {
            "all": [_article_card(a) for a in articles],
            "reviews": [_article_card(a) for a in reviews[:12]],
            "intelligence": [_article_card(a) for a in intelligence[:12]],
            "reimagined": [_article_card(a) for a in reimagined[:12]],
        },
        "counts": {
            "articles": len(articles),
            "reviews": len(reviews),
            "intelligence": len(intelligence),
            "reimagined": len(reimagined),
        },
    }
    return entity
