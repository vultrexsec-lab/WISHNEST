"""Persistent settings for the daily editorial automation."""
from datetime import datetime

from sqlalchemy import Boolean, Column, Date, DateTime, Integer, String, Text
from sqlalchemy.sql import expression, func

from app.database import Base


class AutomationSettings(Base):
    """One-row settings record shared by the admin dashboard and scheduler."""

    __tablename__ = "automation_settings"

    id = Column(Integer, primary_key=True, default=1)
    enabled = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=expression.false(),
    )
    daily_time = Column(String(5), nullable=False, default="08:00", server_default="08:00")
    timezone = Column(
        String(64),
        nullable=False,
        default="Asia/Kolkata",
        server_default="Asia/Kolkata",
    )
    notification_email = Column(String, nullable=True)
    public_app_url = Column(String, nullable=True)

    last_run_date = Column(Date, nullable=True)
    last_run_status = Column(String(32), nullable=True)
    last_run_message = Column(Text, nullable=True)
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    last_article_id = Column(String(64), nullable=True)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )