"""
SEO + GEO optimization for every approved WishNest editorial piece.
Magazine path: approve → SEO/GEO → store run → queue Postiz distribution.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from sqlalchemy.orm import Session

from app.models.article import Article
from app.models.growth import SeoGeoRun
from openai import OpenAI
from app.config import get_settings

logger = logging.getLogger("wishnest.seo_geo")


def _slugify(text: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9\s-]", "", (text or "").lower())
    s = re.sub(r"\s+", "-", s.strip())
    return s[:80] or "article"


def generate_seo_geo_pack(article: Article) -> dict[str, Any]:
    """Call OpenAI for SEO + GEO pack; fallback to deterministic heuristics."""
    headline = article.headline or "WishNest article"
    body = (article.executive_summary or "")[:1200]
    location = article.location or ""
    category = article.category or "editorial"

    settings = get_settings()
    client = OpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None
    if client:
        try:
            prompt = f"""You are WishNest's SEO + GEO editor for independent hospitality/architecture journalism (India).
Article headline: {headline}
Location: {location}
Category: {category}
Summary: {body}

Return JSON only:
{{
  "primary_keyword": "string",
  "secondary_keywords": ["..."],
  "meta_title": "max 60 chars",
  "meta_description": "max 155 chars",
  "suggested_slug": "url-slug",
  "direct_answer": "40-80 word direct answer for AI/search extraction",
  "h2_outline": ["..."],
  "faqs": [{{"q":"...","a":"..."}}],
  "entities": ["places", "brands", "concepts"],
  "internal_link_suggestions": ["destination or topic paths"],
  "seo_score": 0-100,
  "geo_score": 0-100,
  "image_alt": "string"
}}"""
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.3,
            )
            data = json.loads(resp.choices[0].message.content or "{}")
            if isinstance(data, dict) and data.get("meta_title"):
                return data
        except Exception as exc:  # noqa: BLE001
            logger.warning("SEO/GEO OpenAI failed: %s", exc)

    # Heuristic fallback
    kw = (article.focus_keyword or headline.split("—")[0].strip())[:80]
    return {
        "primary_keyword": kw,
        "secondary_keywords": [location, category] if location else [category],
        "meta_title": headline[:60],
        "meta_description": (article.executive_summary or article.subtitle or headline)[:155],
        "suggested_slug": _slugify(headline),
        "direct_answer": (article.executive_summary or headline)[:400],
        "h2_outline": [],
        "faqs": [],
        "entities": [x for x in [location, "WishNest"] if x],
        "internal_link_suggestions": [],
        "seo_score": 55.0,
        "geo_score": 50.0,
        "image_alt": headline[:120],
    }


def build_article_schema(article: Article, pack: dict[str, Any]) -> dict[str, Any]:
    return {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": article.headline,
        "description": pack.get("meta_description") or article.executive_summary,
        "datePublished": article.published_at.isoformat() if article.published_at else None,
        "author": {"@type": "Organization", "name": "WishNest"},
        "publisher": {
            "@type": "Organization",
            "name": "WishNest",
            "url": "https://wishnest.info",
        },
        "mainEntityOfPage": f"https://wishnest.info/article/{article.id}",
        "keywords": pack.get("primary_keyword"),
    }


def run_seo_geo_for_article(db: Session, article: Article) -> SeoGeoRun:
    pack = generate_seo_geo_pack(article)
    schema = build_article_schema(article, pack)
    run = SeoGeoRun(
        article_id=str(article.id),
        seo_score=float(pack.get("seo_score") or 0),
        geo_score=float(pack.get("geo_score") or 0),
        primary_keyword=str(pack.get("primary_keyword") or "")[:255] or None,
        meta_title=str(pack.get("meta_title") or "")[:512] or None,
        meta_description=str(pack.get("meta_description") or "")[:1024] or None,
        direct_answer=pack.get("direct_answer"),
        faq_json=pack.get("faqs"),
        schema_json=schema,
        internal_links=pack.get("internal_link_suggestions"),
        postiz_status="pending",
        raw=pack,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    logger.info(
        "SEO/GEO run for article %s — seo=%s geo=%s",
        article.id,
        run.seo_score,
        run.geo_score,
    )
    return run
