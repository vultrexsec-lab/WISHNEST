"""
SQLAlchemy engine/session setup, using the existing Replit PostgreSQL
database (same DATABASE_URL already provisioned for this project).
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import get_settings

settings = get_settings()

if not settings.database_url:
    raise RuntimeError("DATABASE_URL is not set. Ensure the database is provisioned.")

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency that yields a DB session per-request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
