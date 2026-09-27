"""Persistent binary media (reimaging outputs, etc.) stored in Postgres."""
from __future__ import annotations

import uuid

from sqlalchemy import Column, DateTime, LargeBinary, String, func
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class MediaBlob(Base):
    __tablename__ = "media_blobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    content_type = Column(String(64), nullable=False, default="image/png")
    # original filename hint (optional)
    filename = Column(String(255), nullable=True)
    data = Column(LargeBinary, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
