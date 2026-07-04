"""
WishNest AI Research Editor Agent — FastAPI backend entrypoint.
"""
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.routers import approve, articles, auth, newsletter, research

# Explicit logging config so every logger.info/warning/error (research pipeline,
# OpenAI service, image service, etc.) is guaranteed to print to the backend
# terminal — without this, INFO-level logs are silently dropped by default.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

settings = get_settings()

app = FastAPI(
    title="WishNest AI Research Editor Agent",
    description="Backend powering research, drafting, scoring and human-approved publishing of WishNest editorial content.",
    version="0.1.0",
)

# Serve AI-generated article images (hero + section images) under /api/static
# so they work through the same-origin dev proxy AND through VITE_API_BASE_URL
# in split-domain production deployments (Vercel frontend + Render backend).
STATIC_IMAGES_DIR = Path(__file__).resolve().parent / "static" / "images"
STATIC_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/api/static/images", StaticFiles(directory=str(STATIC_IMAGES_DIR)), name="static-images")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    # allow_credentials requires explicit origins (not wildcard "*")
    allow_credentials="*" not in settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(research.router)
app.include_router(articles.router)
app.include_router(approve.router)
app.include_router(newsletter.router)


@app.get("/api/health")
def health_check():
    return {"status": "ok"}
