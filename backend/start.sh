#!/usr/bin/env bash
# Production start for Render / Docker.
# Bind to $PORT (Render injects this). Do not use --reload in production.

cd "$(dirname "$0")"

echo "→ [1/3] Creating tables (idempotent)…"
if ! python create_tables.py 2>/dev/null; then
  if ! uv run python create_tables.py 2>/dev/null; then
    echo "WARNING: create_tables.py reported an error — continuing."
  fi
fi

echo "→ [2/3] Synchronising columns (apply_columns.py)…"
if ! python apply_columns.py 2>/dev/null; then
  if ! uv run python apply_columns.py 2>/dev/null; then
    echo "WARNING: apply_columns.py failed — continuing (schema sync may recover)."
  fi
fi

echo "→ [3/3] Alembic migrations…"
if ! alembic upgrade head 2>/dev/null; then
  if ! uv run alembic upgrade head 2>/dev/null; then
    echo "WARNING: alembic upgrade head reported an error (non-fatal)."
  fi
fi

PORT="${PORT:-10000}"
echo "→ Starting uvicorn on 0.0.0.0:${PORT}…"
# Prefer plain python/uvicorn (Render venv); fall back to uv
if command -v uvicorn >/dev/null 2>&1; then
  exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT" --timeout-keep-alive 120
elif [ -x "../.venv/bin/uvicorn" ]; then
  exec ../.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port "$PORT" --timeout-keep-alive 120
else
  exec python -m uvicorn app.main:app --host 0.0.0.0 --port "$PORT" --timeout-keep-alive 120
fi
