# ── WishNest Backend — FastAPI on Python 3.11 ────────────────────────────────
# Deploy on Render, DigitalOcean App Platform, Railway, or any Docker host.
#
# Required runtime environment variables (set in your hosting dashboard):
#   DATABASE_URL        PostgreSQL connection string
#   SESSION_SECRET      JWT signing secret (long random string)
#   ADMIN_USERNAME      Dashboard admin login
#   ADMIN_PASSWORD      Dashboard admin password
#   OPENAI_API_KEY      or CHATGPT_API_KEY
#   FIRECRAWL_API_KEY
#   CORS_ORIGINS        Comma-separated allowed origins, e.g. https://wishnest.vercel.app
# ─────────────────────────────────────────────────────────────────────────────

FROM python:3.11-slim

# Install uv (fast Python package manager)
RUN pip install --no-cache-dir uv

WORKDIR /app

# Copy dependency manifests first for Docker layer caching
COPY pyproject.toml uv.lock ./

# Install production dependencies into an in-project virtualenv
RUN uv sync --frozen --no-dev

# Copy backend source
COPY backend/ ./backend/

EXPOSE 8000

# Use the venv's uvicorn directly, run from backend/ so `app.main` resolves
CMD ["sh", "-c", "cd /app/backend && /app/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2"]
