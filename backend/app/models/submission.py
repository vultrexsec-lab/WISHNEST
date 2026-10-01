"""Hospitality project submissions (Get Reviewed intake)."""
from __future__ import annotations

import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class HospitalitySubmission(Base):
    __tablename__ = "hospitality_submissions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reference = Column(String(32), unique=True, nullable=False, index=True)

    property_name = Column(String(255), nullable=False)
    project_stage = Column(String(64), nullable=False)  # existing | upcoming | under_development
    property_type = Column(String(128), nullable=True)

    company_name = Column(String(255), nullable=True)
    contact_name = Column(String(255), nullable=False)
    contact_role = Column(String(128), nullable=True)  # owner | gm | developer | other
    email = Column(String(255), nullable=False, index=True)
    phone = Column(String(64), nullable=True)
    whatsapp = Column(String(64), nullable=True)

    location = Column(String(255), nullable=True)
    website = Column(String(512), nullable=True)
    social_links = Column(Text, nullable=True)
    unit_count = Column(String(64), nullable=True)  # keys / villas / units

    project_details = Column(Text, nullable=True)
    review_focus = Column(Text, nullable=True)

    consent_contact = Column(Boolean, nullable=False, default=False)
    consent_materials = Column(Boolean, nullable=False, default=False)

    status = Column(String(64), nullable=False, default="application_received", index=True)
    source = Column(String(64), nullable=True, default="website")
    utm_source = Column(String(128), nullable=True)
    utm_medium = Column(String(128), nullable=True)
    utm_campaign = Column(String(128), nullable=True)
    admin_notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    files = relationship(
        "SubmissionFile",
        back_populates="submission",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class SubmissionFile(Base):
    __tablename__ = "submission_files"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    submission_id = Column(
        UUID(as_uuid=True),
        ForeignKey("hospitality_submissions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    original_name = Column(String(512), nullable=False)
    stored_name = Column(String(512), nullable=False)
    content_type = Column(String(128), nullable=True)
    size_bytes = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    submission = relationship("HospitalitySubmission", back_populates="files")
