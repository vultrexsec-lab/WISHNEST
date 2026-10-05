"""Growth & Intelligence OS — shared records (contacts, opportunities, SEO runs)."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.database import Base


class GrowthContact(Base):
    """Universal contact — synced later with Mautic; WishNest source of truth for enrichment."""

    __tablename__ = "growth_contacts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    external_mautic_id = Column(String(64), nullable=True, index=True)
    name = Column(String(255), nullable=True)
    email = Column(String(255), nullable=True, index=True)
    phone = Column(String(64), nullable=True, index=True)
    company = Column(String(255), nullable=True)
    contact_type = Column(String(64), nullable=True, index=True)  # resort_owner, broker, ...
    country = Column(String(64), nullable=True)
    state = Column(String(128), nullable=True)
    city = Column(String(128), nullable=True)
    destination = Column(String(128), nullable=True)
    email_permission = Column(Boolean, default=False)
    whatsapp_permission = Column(Boolean, default=False)
    phone_permission = Column(Boolean, default=False)
    unsubscribed = Column(Boolean, default=False)
    do_not_contact = Column(Boolean, default=False)
    tags = Column(Text, nullable=True)
    interests = Column(Text, nullable=True)
    intelligence_score = Column(Integer, default=0)
    commercial_score = Column(Integer, default=0)
    source = Column(String(128), nullable=True)
    notes = Column(Text, nullable=True)
    meta = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ArrowxOpportunity(Base):
    """Qualified commercial opportunity routed toward ArrowX (not merged into editorial)."""

    __tablename__ = "arrowx_opportunities"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    contact_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    source_type = Column(String(64), nullable=False)  # survey, campaign, submission, telecaller
    source_id = Column(String(128), nullable=True)
    title = Column(String(512), nullable=False)
    summary = Column(Text, nullable=True)
    destination = Column(String(128), nullable=True)
    demand_signals = Column(JSONB, nullable=True)
    status = Column(String(64), nullable=False, default="new")  # new, reviewing, routed, closed
    consent_commercial = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class SeoGeoRun(Base):
    """SEO + GEO optimization result attached to an article before/at publish."""

    __tablename__ = "seo_geo_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    article_id = Column(String(64), nullable=False, index=True)
    seo_score = Column(Float, nullable=True)
    geo_score = Column(Float, nullable=True)
    primary_keyword = Column(String(255), nullable=True)
    meta_title = Column(String(512), nullable=True)
    meta_description = Column(String(1024), nullable=True)
    direct_answer = Column(Text, nullable=True)
    faq_json = Column(JSONB, nullable=True)
    schema_json = Column(JSONB, nullable=True)
    internal_links = Column(JSONB, nullable=True)
    postiz_status = Column(String(64), nullable=True)  # pending, queued, published, skipped, error
    postiz_payload = Column(JSONB, nullable=True)
    raw = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AudienceSegment(Base):
    """Named, reusable audience definition for campaigns."""

    __tablename__ = "audience_segments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    # Filters stored as JSON: contact_types[], states[], cities[], destinations[],
    # email_permission_only, exclude_suppressed
    filters = Column(JSONB, nullable=False, default=dict)
    contact_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class GrowthCampaign(Base):
    """Campaign Manager draft/live campaign (control module)."""

    __tablename__ = "growth_campaigns"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    campaign_type = Column(String(64), nullable=False, default="lead_generation")
    classification = Column(String(64), nullable=False, default="commercial")  # editorial|research|commercial|sponsored
    objective = Column(String(128), nullable=True)
    audience_filters = Column(JSONB, nullable=True)  # contact_types, geo, segment_id
    audience_count = Column(Integer, default=0)
    channels = Column(JSONB, nullable=True)  # email, whatsapp, linkedin, ...
    cta_label = Column(String(255), nullable=True)
    cta_url = Column(String(512), nullable=True)
    status = Column(String(64), nullable=False, default="draft")
    # draft | ai_generating | ready_for_review | approved | scheduled | live | paused | completed
    pack = Column(JSONB, nullable=True)  # AI-generated campaign pack
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class GrowthSurvey(Base):
    """Lightweight survey for demand intelligence → ArrowX."""

    __tablename__ = "growth_surveys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(255), nullable=False)
    destination = Column(String(128), nullable=True)
    topic = Column(String(128), nullable=True)  # second_home, hospitality, villa, ...
    status = Column(String(64), nullable=False, default="active")  # active, closed
    questions = Column(JSONB, nullable=True)  # [{id, label, type, options?}]
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class GrowthSurveyResponse(Base):
    __tablename__ = "growth_survey_responses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    survey_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    contact_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    email = Column(String(255), nullable=True)
    answers = Column(JSONB, nullable=False, default=dict)
    consent_commercial = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
