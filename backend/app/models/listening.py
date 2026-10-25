"""ArrowX / WishNest Phase 1 — Social listening & buyer intelligence."""
from __future__ import annotations

import uuid

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.database import Base


class ListeningBusiness(Base):
    __tablename__ = "listening_businesses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    website_url = Column(String(512), nullable=True)
    description = Column(Text, nullable=True)
    category = Column(String(128), nullable=True)
    offerings = Column(JSONB, nullable=True)
    target_markets = Column(JSONB, nullable=True)
    buyer_personas = Column(JSONB, nullable=True)
    competitors = Column(JSONB, nullable=True)
    profile = Column(JSONB, nullable=True)
    status = Column(String(32), nullable=False, default="active")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ListeningCampaign(Base):
    __tablename__ = "listening_campaigns"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    platforms = Column(JSONB, nullable=True)  # ["reddit","youtube","bluesky","web"]
    keywords = Column(JSONB, nullable=True)
    negative_keywords = Column(JSONB, nullable=True)
    target_geography = Column(JSONB, nullable=True)
    status = Column(String(32), nullable=False, default="draft")  # draft, active, paused
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    meta = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ListeningDiscoveryJob(Base):
    __tablename__ = "listening_discovery_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    status = Column(String(32), nullable=False, default="queued")  # queued, running, done, failed
    platforms = Column(JSONB, nullable=True)
    posts_found = Column(Integer, default=0)
    opportunities_created = Column(Integer, default=0)
    error = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ListeningPost(Base):
    __tablename__ = "listening_posts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    platform = Column(String(32), nullable=False, index=True)
    external_id = Column(String(255), nullable=True, index=True)
    url = Column(String(1024), nullable=False)
    title = Column(String(512), nullable=True)
    body = Column(Text, nullable=True)
    author_handle = Column(String(255), nullable=True)
    language = Column(String(16), nullable=True)
    location_mentioned = Column(String(255), nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    comment_count = Column(Integer, default=0)
    like_count = Column(Integer, default=0)
    share_count = Column(Integer, default=0)
    raw = Column(JSONB, nullable=True)
    collected_at = Column(DateTime(timezone=True), server_default=func.now())


class ListeningComment(Base):
    __tablename__ = "listening_comments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    post_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    external_id = Column(String(255), nullable=True)
    body = Column(Text, nullable=True)
    author_handle = Column(String(255), nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    like_count = Column(Integer, default=0)
    parent_external_id = Column(String(255), nullable=True)
    collected_at = Column(DateTime(timezone=True), server_default=func.now())


class ListeningOpportunity(Base):
    """Qualified public conversation — not automatically a contactable lead."""

    __tablename__ = "listening_opportunities"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    post_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    platform = Column(String(32), nullable=False, index=True)
    source_url = Column(String(1024), nullable=False)
    excerpt = Column(Text, nullable=True)
    category = Column(String(128), nullable=True)
    requirement = Column(Text, nullable=True)
    location = Column(String(255), nullable=True)
    budget_hint = Column(String(128), nullable=True)
    intent_score = Column(Integer, default=0, index=True)
    intent_band = Column(String(32), nullable=True)  # high, medium, low, research
    stage = Column(String(64), nullable=True)
    recommended_action = Column(String(255), nullable=True)
    contact_eligible = Column(Boolean, default=False)  # always false unless consented later
    public_author = Column(String(255), nullable=True)
    evidence = Column(JSONB, nullable=True)
    status = Column(String(32), nullable=False, default="new")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
