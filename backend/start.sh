#!/usr/bin/env bash
# Backend startup wrapper — avoids shell quoting issues with secret values
set -e
cd "$(dirname "$0")"

# Run all pending Alembic migrations before the server starts.
# This is idempotent: already-applied migrations are skipped, so it is safe
# on every restart. Covers both fresh databases (runs all migrations from the
# base) and existing ones (applies only new migrations like the ABCDE scores).
echo "→ Running database migrations…"
uv run alembic upgrade head

# --timeout-keep-alive raised well past the default 5s: on Render the first
# request after an idle spin-down can take a while to get a full response
# while the instance cold-starts, and a short keep-alive timeout risked the
# server dropping that connection out from under the client mid-boot.
exec uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --timeout-keep-alive 120
