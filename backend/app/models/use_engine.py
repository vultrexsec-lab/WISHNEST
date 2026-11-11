"""Universal Sales Engine (USE) — MVP P1 foundation models."""
from __future__ import annotations

import uuid

from sqlalchemy import Boolean, Column, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.database import Base


class UseTenant(Base):
    __tablename__ = "use_tenants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug = Column(String(64), nullable=False, unique=True, index=True)
    name = Column(String(255), nullable=False)
    product_summary = Column(Text, nullable=True)
    website = Column(String(512), nullable=True)
    geography = Column(String(255), nullable=True)
    knowledge = Column(JSONB, nullable=True)  # approved facts only
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class UseStrategy(Base):
    __tablename__ = "use_strategies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    status = Column(String(32), nullable=False, default="draft")  # draft|rival_done|approved|rejected
    a01_output = Column(JSONB, nullable=True)
    a02_output = Column(JSONB, nullable=True)
    a00_output = Column(JSONB, nullable=True)  # campaign manager plan after CEO approve
    ceo_notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class UseAuditLog(Base):
    __tablename__ = "use_audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    strategy_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    agent_id = Column(String(16), nullable=False)  # A00|A01|A02|CEO|SYSTEM
    action = Column(String(64), nullable=False)
    status = Column(String(32), nullable=False, default="COMPLETED")
    detail = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class UseLead(Base):
    """P2A — tenant-scoped lead with explicit consent flags (no cold scrape import here)."""

    __tablename__ = "use_leads"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    name = Column(String(255), nullable=True)
    email = Column(String(255), nullable=True, index=True)
    phone = Column(String(64), nullable=True)
    company = Column(String(255), nullable=True)
    role = Column(String(128), nullable=True)
    source = Column(String(128), nullable=True)  # manual, inbound, import
    stage = Column(String(64), nullable=False, default="new")  # new|qualified|nurture|unfit|won
    email_consent = Column(Boolean, default=False)
    whatsapp_consent = Column(Boolean, default=False)
    phone_consent = Column(Boolean, default=False)
    do_not_contact = Column(Boolean, default=False)
    notes = Column(Text, nullable=True)
    meta = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
