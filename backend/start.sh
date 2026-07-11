#!/usr/bin/env bash
# Backend startup wrapper — avoids shell quoting issues with secret values
#
# Startup sequence (all steps are idempotent / safe on every restart):
#
#   1. create_tables.py   — Base.metadata.create_all():
#        • Fresh DB  → creates every table (articles, newsletter_subscribers, …)
#          including all columns currently in the SQLAlchemy models.
#        • Existing DB → no-op (SQLAlchemy skips tables that already exist).
#
#   2. alembic upgrade head:
#        • Fresh DB (just created above) → both migrations detect that every
#          column already exists and skip gracefully.  alembic_version is
#          stamped at head so future column-level migrations run correctly.
#        • Existing DB without alembic_version → runs all migrations;
#          each migration guards against pre-existing columns.
#        • Existing DB at an older revision → applies only the new migrations.
#
# We do NOT use "set -e" so that a non-fatal alembic warning/error doesn't
# prevent uvicorn from starting.  Each step logs its own failure clearly.

cd "$(dirname "$0")"

# ── Step 1: ensure all tables exist (handles fresh databases) ─────────────
echo "→ Creating tables (idempotent, safe on every restart)…"
if ! uv run python create_tables.py; then
    echo "ERROR: create_tables.py failed — check DATABASE_URL and connectivity."
    exit 1
fi

# ── Step 2: apply any pending column-level migrations ────────────────────
echo "→ Running database migrations (alembic upgrade head)…"
if ! uv run alembic upgrade head; then
    echo "WARNING: alembic upgrade failed. The server will still start, but"
    echo "         some new columns may be missing until the issue is resolved."
fi

# ── Step 3: start the API server ─────────────────────────────────────────
# --timeout-keep-alive 120: keeps connections alive long enough for Render
# cold-start requests that can take many seconds to receive a full response.
echo "→ Starting uvicorn…"
exec uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --timeout-keep-alive 120
