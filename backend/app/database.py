"""
database (same DATABASE_URL already provisioned for this project).
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import get_settings

settings = get_settings()

if not settings.database_url:
    raise RuntimeError("DATABASE_URL is not set. Ensure the database is provisioned.")

# Short connect timeout so Render deploys do not hang when Postgres is
# suspended / unreachable — startup scripts fail fast instead of 5+ min timeout.
_url = settings.database_url
if _url.startswith("postgres://"):
    _url = "postgresql://" + _url[len("postgres://") :]

engine = create_engine(
    _url,
    pool_pre_ping=True,
    pool_recycle=300,
    connect_args={"connect_timeout": 8},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency that yields a DB session per-request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
