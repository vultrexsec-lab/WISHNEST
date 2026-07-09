"""
WishNest AI Research Editor Agent — FastAPI backend entrypoint.
"""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.routers import approve, articles, auth, newsletter, research
from app.routers import scheduler as scheduler_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start the weekly scheduler on boot; stop it on shutdown."""
    from app.services import scheduler_service
    scheduler_service.start_scheduler()
    yield
    scheduler_service.stop_scheduler()


app = FastAPI(
    title="WishNest AI Research Editor Agent",
    description="Backend powering research, drafting, scoring and human-approved publishing of WishNest editorial content.",
    version="0.1.0",
    lifespan=lifespan,
)

# Serve AI-generated article images under /api/static
STATIC_IMAGES_DIR = Path(__file__).resolve().parent / "static" / "images"
STATIC_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/api/static/images", StaticFiles(directory=str(STATIC_IMAGES_DIR)), name="static-images")

# CORS — allow_credentials=True requires explicit origins (no wildcard).
_ALWAYS_ALLOWED = [
    "https://public-brown-one-94.vercel.app",
    "https://b7f50de8-22d2-4e87-b4bd-7ec7e0b00cfc-00-1yj2ksywkheg8.pike.replit.dev",
]
_env_origins = [
    o.strip()
    for o in settings.cors_origins_raw.split(",")
    if o.strip() and o.strip() != "*"
]
_allow_origins = list(dict.fromkeys(_ALWAYS_ALLOWED + _env_origins))

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
app.include_router(scheduler_router.router)


@app.get("/")
def root():
    return {"status": "ok", "service": "WishNest API"}


@app.get("/api/health")
def health_check():
    return {"status": "ok"}
