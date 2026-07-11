#!/usr/bin/env bash
# Backend startup wrapper — avoids shell quoting issues with secret values
set -e
cd "$(dirname "$0")"

# Ensure all SQLAlchemy tables exist before the server starts.
# create_all() is idempotent — it's a no-op when the tables are already there,
# so running this on every startup is safe and fixes first-boot on Render where
# no one has manually run create_tables.py against the new Postgres instance.
echo "→ Ensuring database tables exist…"
uv run python create_tables.py

# --timeout-keep-alive raised well past the default 5s: on Render the first
# request after an idle spin-down can take a while to get a full response
# while the instance cold-starts, and a short keep-alive timeout risked the
# server dropping that connection out from under the client mid-boot.
exec uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --timeout-keep-alive 120
