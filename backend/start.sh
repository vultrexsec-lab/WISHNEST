#!/usr/bin/env bash
# Backend startup wrapper — avoids shell quoting issues with secret values
#
# Startup sequence (all steps are idempotent / safe on every restart):
#
#   1. create_tables.py  — Base.metadata.create_all():
#        • Fresh DB  → creates every table with all current model columns.
#        • Existing DB → no-op (SQLAlchemy skips tables that already exist).
#
#   2. apply_columns.py  — raw ALTER TABLE … ADD COLUMN IF NOT EXISTS:
#        • Adds any missing columns directly via SQL, bypassing Alembic's
#          version-tracking state.  Fixes the Render failure mode where
#          alembic_version was stamped at head from an earlier bad deploy
#          (when articles didn't exist yet), so `alembic upgrade head` would
#          be a no-op even though the ABCDE columns were never created.
#
#   3. alembic upgrade head:
#        • Applies any pending column-level migrations for future schema
#          changes.  Non-fatal: a warning is logged but the server still
#          starts if this step fails.
#
# We do NOT use "set -e" so that a non-fatal warning doesn't prevent uvicorn
# from starting.  Steps 1 and 2 exit with code 1 on hard errors.

cd "$(dirname "$0")"

# ── Step 1: ensure all tables exist (handles fresh databases) ─────────────
echo "→ [1/3] Creating tables (idempotent)…"
if ! uv run python create_tables.py; then
    echo "WARNING: create_tables.py reported an error — continuing (lifespan schema sync may recover)."
fi

# ── Step 2: force-add any missing columns via raw SQL ─────────────────────
echo "→ [2/3] Synchronising columns (apply_columns.py)…"
if ! uv run python apply_columns.py; then
    echo "ERROR: apply_columns.py failed — check DATABASE_URL and connectivity."
    exit 1
fi

# ── Step 3: apply any pending Alembic migrations ──────────────────────────
echo "→ [3/3] Running Alembic migrations (upgrade head)…"
if ! uv run alembic upgrade head; then
    echo "WARNING: alembic upgrade head reported an error (non-fatal)."
fi

# ── Start the API server ──────────────────────────────────────────────────
echo "→ Starting uvicorn…"
exec uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --timeout-keep-alive 120
