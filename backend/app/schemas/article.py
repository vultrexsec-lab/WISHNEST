"""
Pydantic schemas for request/response validation, mirroring the Article
SQLAlchemy model in app/models/article.py.
"""
import logging
import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, field_validator

from app.models.article import ArticleStatus, ArticleType, Grade

logger = logging.getLogger("wishnest.schemas")

SEO_TITLE_MIN = 50
SEO_TITLE_MAX = 60
META_DESC_MIN = 150
META_DESC_MAX = 160


class FaqItem(BaseModel):
    question: str
    answer: str


class InternalLink(BaseModel):
    """One internal linking recommendation produced by the AI."""
    anchor_text: str
    target_page: str
    context: str
    seo_reason: str


class ArticleBase(BaseModel):
    article_type: ArticleType = ArticleType.standard
    category: Optional[str] = None  # e.g. "intelligence", "destinations", "best-of", "reimagined"

    # Core editorial content
    headline: str
    subtitle: Optional[str] = None
    full_article: Optional[str] = None
    executive_summary: Optional[str] = None
    pull_quotes: Optional[list[str]] = None
    faq_section: Optional[list[FaqItem]] = None

    # SEO / discoverability
    seo_title: Optional[str] = None
    meta_description: Optional[str] = None
    focus_keyword: Optional[str] = None
    keywords: Optional[list[str]] = None
    source_urls: Optional[list[str]] = None
    image_credits: Optional[list[str]] = None
    captions: Optional[list[str]] = None
    alt_text: Optional[list[str]] = None
    hero_image_url: Optional[str] = None
    section_image_urls: Optional[list[str]] = None
    internal_links: Optional[list[InternalLink]] = None

    # Review-only fields
    property_snapshot: Optional[dict[str, Any]] = None
    best_for: Optional[list[str]] = None
    not_ideal_for: Optional[list[str]] = None
    price_band: Optional[str] = None
    location: Optional[str] = None
    accessibility: Optional[str] = None

    # WishNest ABCDE Scoring & Rating Framework
    architecture_grade: Optional[Grade] = None
    landscape_grade: Optional[Grade] = None
    connectivity_grade: Optional[Grade] = None
    delight_grade: Optional[Grade] = None
    eat_explore_grade: Optional[Grade] = None
    developer_lessons: Optional[list[str]] = None
    key_takeaways: Optional[list[str]] = None
    wishnest_verdict: Optional[str] = None

    # Social media package
    linkedin_variations: Optional[list[str]] = None
    facebook_variations: Optional[list[str]] = None
    twitter_thread: Optional[list[str]] = None
    newsletter_summary: Optional[str] = None
    suggested_hashtags: Optional[list[str]] = None
    cta: Optional[str] = None

    @field_validator("seo_title")
    @classmethod
    def validate_seo_title_length(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        length = len(v)
        if not (SEO_TITLE_MIN <= length <= SEO_TITLE_MAX):
            raise ValueError(
                f"seo_title is {length} chars — MUST be {SEO_TITLE_MIN}–{SEO_TITLE_MAX}. "
                f"Current value: {v!r}"
            )
        return v

    @field_validator("meta_description")
    @classmethod
    def validate_meta_description_length(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        length = len(v)
        if not (META_DESC_MIN <= length <= META_DESC_MAX):
            raise ValueError(
                f"meta_description is {length} chars — MUST be {META_DESC_MIN}–{META_DESC_MAX}. "
                f"Current value: {v!r}"
            )
        return v


class ArticleCreate(ArticleBase):
    pass


class ArticleUpdate(BaseModel):
    """Partial update — every field optional."""

    model_config = ConfigDict(extra="ignore")

    headline: Optional[str] = None
    subtitle: Optional[str] = None
    full_article: Optional[str] = None
    status: Optional[ArticleStatus] = None
    scheduled_at: Optional[datetime] = None


class ArticleOut(ArticleBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: ArticleStatus
    scheduled_at: Optional[datetime] = None
    published_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class ResearchRequest(BaseModel):
    query: str
    category: Optional[str] = None  # category to tag generated articles with


class ResearchResponse(BaseModel):
    message: str
    query: str
    draft_article_ids: list[uuid.UUID] = []


class ApproveArticleRequest(BaseModel):
    scheduled_at: Optional[datetime] = None


class ApproveArticleResponse(BaseModel):
    id: uuid.UUID
    status: ArticleStatus
    scheduled_at: Optional[datetime] = None


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
