"""
apply_columns.py — Idempotent column-level schema synchroniser.

Runs BEFORE uvicorn on every startup.  Uses raw SQL
  ALTER TABLE articles ADD COLUMN IF NOT EXISTS …
so it is completely independent of Alembic's version-tracking state.

This handles the specific Render failure mode where alembic_version was
already stamped at head (from a deployment where articles didn't exist yet)
so `alembic upgrade head` is a no-op on subsequent deploys, even though the
new columns were never actually added to the articles table.
"""
import sys
from sqlalchemy import text
from app.database import engine

# (col_name, postgres_type) — must stay in sync with app/models/article.py
REQUIRED_COLS = [
    ("architecture_score",  "DOUBLE PRECISION"),
    ("landscape_score",     "DOUBLE PRECISION"),
    ("connectivity_score",  "DOUBLE PRECISION"),
    ("delight_score",       "DOUBLE PRECISION"),
    ("eat_explore_score",   "DOUBLE PRECISION"),
    ("abcde_overall",       "TEXT"),
    ("is_trash",            "BOOLEAN NOT NULL DEFAULT false"),
]


def main() -> None:
    try:
        with engine.connect() as conn:
            for col, pg_type in REQUIRED_COLS:
                stmt = text(
                    f"ALTER TABLE articles ADD COLUMN IF NOT EXISTS {col} {pg_type}"
                )
                conn.execute(stmt)
                print(f"  ✓ articles.{col} ({pg_type})")
            conn.commit()
        print("apply_columns: schema synchronised.")
    except Exception as exc:
        # Articles table may not exist yet (create_tables.py hasn't run, or
        # DATABASE_URL is wrong).  Don't hard-fail — let the next step deal
        # with it and surface a clearer error.
        print(f"apply_columns: WARNING — {exc}", file=sys.stderr)


if __name__ == "__main__":
    main()
