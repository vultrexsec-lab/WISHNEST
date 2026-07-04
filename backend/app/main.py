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

# Explicit origins that must always be allowed (Vercel frontend + Replit dev).
# allow_credentials=True requires named origins — wildcard "*" is forbidden by
# the browser when credentials mode is "include".
_ALWAYS_ALLOWED = [
    "https://public-brown-one-94.vercel.app",
    "https://b7f50de8-22d2-4e87-b4bd-7ec7e0b00cfc-00-1yj2ksywkheg8.pike.replit.dev",
]
_env_origins = [
    o.strip()
    for o in settings.cors_origins_raw.split(",")
    if o.strip() and o.strip() != "*"
]
_allow_origins = list(dict.fromkeys(_ALWAYS_ALLOWED + _env_origins))  # dedup, order-stable

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

app.include_router(auth.router)
app.include_router(research.router)
app.include_router(articles.router)
app.include_router(approve.router)
app.include_router(newsletter.router)


@app.get("/api/health")
def health_check():
    return {"status": "ok"}
