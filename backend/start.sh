#!/usr/bin/env bash
# Backend startup wrapper — avoids shell quoting issues with secret values
set -e
cd "$(dirname "$0")"
exec uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
