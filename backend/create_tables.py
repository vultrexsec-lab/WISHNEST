"""
Idempotent table creation against DATABASE_URL.

Handles the Postgres edge case where a previous failed CREATE left an
orphaned type name (UniqueViolation on pg_type) while the table itself
may or may not exist — common on Render redeploys.
Also treats DuplicateTable as success when the relation already exists.
"""
from __future__ import annotations

import logging

from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError, ProgrammingError, OperationalError

from app.database import Base, engine

# Register all models on Base.metadata
from app.models import article  # noqa: F401
from app.models import newsletter  # noqa: F401
from app.models import automation  # noqa: F401
from app.models import media_blob  # noqa: F401
from app.models import submission  # noqa: F401
from app.models import growth  # noqa: F401
from app.models import listening  # noqa: F401
from app.models import use_engine  # noqa: F401

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("wishnest.create_tables")


def _create_one(table) -> None:
    name = table.name
    try:
        insp = inspect(engine)
        if insp.has_table(name):
            log.info("Table already exists: %s", name)
            return
    except Exception as exc:
        log.warning("inspect failed for %s: %s", name, exc)

    try:
        table.create(bind=engine, checkfirst=True)
        log.info("Created table: %s", name)
    except IntegrityError as exc:
        log.warning("IntegrityError creating %s (will verify): %s", name, exc)
        try:
            if inspect(engine).has_table(name):
                log.info("Table present after IntegrityError: %s", name)
                return
        except Exception:
            pass
        log.warning("Skipping create for %s — fix manually if missing.", name)
    except ProgrammingError as exc:
        # DuplicateTable / already exists — safe to continue
        msg = str(exc).lower()
        if "already exists" in msg or "duplicate" in msg:
            log.info("Table already exists (ProgrammingError): %s", name)
            return
        log.warning("ProgrammingError creating %s: %s", name, exc)
    except OperationalError as exc:
        log.warning("OperationalError creating %s: %s", name, exc)


def main() -> None:
    try:
        Base.metadata.create_all(bind=engine, checkfirst=True)
        log.info("Tables created successfully (create_all).")
        return
    except (IntegrityError, ProgrammingError, OperationalError) as exc:
        log.warning("create_all failed (%s), retrying per-table: %s", type(exc).__name__, exc)

    for table in Base.metadata.sorted_tables:
        _create_one(table)

    log.info("Per-table create pass finished.")


if __name__ == "__main__":
    main()
