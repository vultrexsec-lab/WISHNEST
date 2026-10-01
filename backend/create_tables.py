"""
Idempotent table creation against DATABASE_URL.

Handles the Postgres edge case where a previous failed CREATE left an
orphaned type name (UniqueViolation on pg_type) while the table itself
may or may not exist — common on Render redeploys.
"""
from __future__ import annotations

import logging

from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError, ProgrammingError

from app.database import Base, engine

# Register all models on Base.metadata
from app.models import article  # noqa: F401
from app.models import newsletter  # noqa: F401
from app.models import automation  # noqa: F401
from app.models import media_blob  # noqa: F401
from app.models import submission  # noqa: F401

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("wishnest.create_tables")


def _create_one(table) -> None:
    name = table.name
    insp = inspect(engine)
    if insp.has_table(name):
        log.info("Table already exists: %s", name)
        return
    try:
        table.create(bind=engine, checkfirst=True)
        log.info("Created table: %s", name)
    except IntegrityError as exc:
        # Orphaned pg_type / concurrent create — treat as success if table now visible
        log.warning("IntegrityError creating %s (will verify): %s", name, exc)
        insp = inspect(engine)
        if insp.has_table(name):
            log.info("Table present after IntegrityError: %s", name)
            return
        # Last resort: IF NOT EXISTS via raw SQL is not trivial for full DDL;
        # drop orphaned type only if no table (dangerous) — skip instead.
        log.warning("Skipping create for %s — fix manually if missing.", name)
    except ProgrammingError as exc:
        log.warning("ProgrammingError creating %s: %s", name, exc)


def main() -> None:
    # Prefer bulk create_all; fall back to per-table on unique type conflicts
    try:
        Base.metadata.create_all(bind=engine, checkfirst=True)
        log.info("Tables created successfully (create_all).")
        return
    except IntegrityError as exc:
        log.warning("create_all hit IntegrityError, retrying per-table: %s", exc)

    for table in Base.metadata.sorted_tables:
        _create_one(table)

    log.info("Per-table create pass finished.")


if __name__ == "__main__":
    main()
