"""
Articles table — the single source of truth for every piece of content the
WishNest AI Research Editor Agent produces (standard editorial pieces and
property reviews), including SEO metadata, WishNest ABCDE scoring, the
social media package, and the human-approval workflow status.
"""
import enum
import uuid

from sqlalchemy import Boolean, Column, DateTime, Enum, Float, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.sql import func, expression

from app.database import Base


class ArticleType(str, enum.Enum):
    standard = "standard"
    review = "review"


class ArticleStatus(str, enum.Enum):
    draft = "draft"  # Pending Review — default, nothing below is published
    approved = "approved"  # Human approved, not yet scheduled
    scheduled = "scheduled"  # Approved + has a scheduled publish time
    published = "published"


class Grade(str, enum.Enum):
    a_plus = "A+"
    a = "A"
    a_minus = "A-"
    b_plus = "B+"
    b = "B"
    b_minus = "B-"
    c_plus = "C+"
    c = "C"
    c_minus = "C-"
    d_plus = "D+"
    d = "D"


class Article(Base):
    __tablename__ = "articles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # --- Classification / workflow ---
    article_type = Column(Enum(ArticleType, name="article_type"), nullable=False, default=ArticleType.standard)
    status = Column(Enum(ArticleStatus, name="article_status"), nullable=False, default=ArticleStatus.draft, index=True)
    # Recycle Bin: trashed articles are hidden from both the admin dashboard's
    # active views and the public site, without losing their data. They only
    # reappear via "Restore" (admin) or are permanently removed via
    # "Delete Permanently" (admin). Never toggled by any public endpoint.
    is_trash = Column(Boolean, nullable=False, default=False, server_default=expression.false(), index=True)

    # --- Core editorial content ---
    headline = Column(String, nullable=False)
    subtitle = Column(String, nullable=True)
    full_article = Column(Text, nullable=True)
    executive_summary = Column(Text, nullable=True)
    pull_quotes = Column(ARRAY(Text), nullable=True)
    faq_section = Column(JSONB, nullable=True)  # [{ "question": str, "answer": str }, ...]

    # --- SEO / discoverability ---
    seo_title = Column(String, nullable=True)          # target: 50-60 chars
    meta_description = Column(String, nullable=True)   # target: 150-160 chars
    focus_keyword = Column(String, nullable=True)      # primary target keyword
    keywords = Column(ARRAY(Text), nullable=True)      # head + LSI + long-tail mix
    source_urls = Column(ARRAY(Text), nullable=True)
    image_credits = Column(ARRAY(Text), nullable=True)
    captions = Column(ARRAY(Text), nullable=True)      # descriptive SEO captions
    alt_text = Column(ARRAY(Text), nullable=True)      # keyword-rich alt text
    hero_image_url = Column(Text, nullable=True)
    section_image_urls = Column(ARRAY(Text), nullable=True)
    # Internal linking strategy: [{anchor_text, target_page, context, seo_reason}]
    internal_links = Column(JSONB, nullable=True)

    # --- Review-only fields (nullable; only populated when article_type == review) ---
    property_snapshot = Column(JSONB, nullable=True)
    best_for = Column(ARRAY(Text), nullable=True)
    not_ideal_for = Column(ARRAY(Text), nullable=True)
    price_band = Column(String, nullable=True)
    location = Column(String, nullable=True)
    accessibility = Column(Text, nullable=True)

    # --- WishNest ABCDE Scoring & Rating Framework ---
    # Letter-grade enums (legacy / LLM-derived)
    architecture_grade = Column(Enum(Grade, name="grade"), nullable=True)
    landscape_grade = Column(Enum(Grade, name="grade"), nullable=True)
    connectivity_grade = Column(Enum(Grade, name="grade"), nullable=True)
    delight_grade = Column(Enum(Grade, name="grade"), nullable=True)
    eat_explore_grade = Column(Enum(Grade, name="grade"), nullable=True)
    # Numeric scores 1.0–10.0 (LLM-generated; drive the public score-card UI)
    architecture_score = Column(Float, nullable=True)
    landscape_score = Column(Float, nullable=True)
    connectivity_score = Column(Float, nullable=True)
    delight_score = Column(Float, nullable=True)
    eat_explore_score = Column(Float, nullable=True)
    # Computed overall ABCDE™ grade string (e.g. "A", "B+") derived server-side
    abcde_overall = Column(String, nullable=True)
    developer_lessons = Column(ARRAY(Text), nullable=True)
    key_takeaways = Column(ARRAY(Text), nullable=True)
    wishnest_verdict = Column(Text, nullable=True)

    # --- Social media package ---
    linkedin_variations = Column(ARRAY(Text), nullable=True)  # exactly 3 expected
    facebook_variations = Column(ARRAY(Text), nullable=True)  # exactly 2 expected
    twitter_thread = Column(ARRAY(Text), nullable=True)  # 1 thread, list of tweets
    newsletter_summary = Column(Text, nullable=True)
    suggested_hashtags = Column(ARRAY(Text), nullable=True)
    cta = Column(String, nullable=True)

    # --- Category / taxonomy ---
    category = Column(String, nullable=True, index=True)  # e.g. "intelligence", "destinations", "best-of", "reimagined"

    # --- De-duplication: Google Places place_id (or SerpApi data_id) of the
    # specific business this article was generated for. Populated for every
    # article produced by the live-discovery pipeline; NULL for articles
    # generated from a free-text brief without a Places match. The scheduler
    # checks this column before generating to guarantee no property is ever
    # covered twice. ---
    place_id = Column(String, nullable=True, index=True)

    # --- Scheduling / audit ---
    scheduled_at = Column(DateTime(timezone=True), nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
