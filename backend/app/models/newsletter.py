"""
Newsletter subscriber table — stores email addresses collected from the
site's newsletter sign-up modal.  Duplicates are silently ignored.
"""
import uuid

from sqlalchemy import Column, DateTime, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.database import Base


class NewsletterSubscriber(Base):
    __tablename__ = "newsletter_subscribers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, nullable=False, index=True)
    # Comma-separated interest tags e.g. "architecture,hotels,second-homes"
    interests = Column(String(512), nullable=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
