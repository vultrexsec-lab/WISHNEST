"""
WishNest AI Research Editor Agent — FastAPI backend entrypoint.
"""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.routers import approve, articles, auth, image_proxy, newsletter, research
from app.routers import scheduler as scheduler_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

settings = get_settings()


def _sync_schema() -> None:
    """
    Force-add every ABCDE score column that might be missing from the articles
    table using raw SQL (ALTER TABLE … ADD COLUMN IF NOT EXISTS).

    This runs synchronously inside the lifespan handler before uvicorn begins
    serving requests, so it is guaranteed to execute even if start.sh's
    apply_columns.py step was skipped or silently failed on the host (Render).
    It is completely independent of Alembic's version-tracking state.
    """
    import logging
    from sqlalchemy import text
    from app.database import engine

    REQUIRED_COLS = [
        ("architecture_score",  "DOUBLE PRECISION"),
        ("landscape_score",     "DOUBLE PRECISION"),
        ("connectivity_score",  "DOUBLE PRECISION"),
        ("delight_score",       "DOUBLE PRECISION"),
        ("eat_explore_score",   "DOUBLE PRECISION"),
        ("abcde_overall",       "TEXT"),
        ("is_trash",            "BOOLEAN NOT NULL DEFAULT false"),
    ]
    log = logging.getLogger("wishnest.schema")
    try:
        with engine.connect() as conn:
            for col, pg_type in REQUIRED_COLS:
                conn.execute(
                    text(f"ALTER TABLE articles ADD COLUMN IF NOT EXISTS {col} {pg_type}")
                )
            conn.commit()
        log.info("Schema sync: all ABCDE columns present.")
    except Exception as exc:
        # Log but don't crash — the articles table may not exist yet on a
        # completely fresh DB; create_tables.py in start.sh handles that case.
        log.warning("Schema sync skipped: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Sync schema, start the weekly scheduler on boot; stop it on shutdown."""
    _sync_schema()
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
    "https://wishnest.info",
    "https://www.wishnest.info",
    "https://wishnests.netlify.app",
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
app.include_router(image_proxy.router)
app.include_router(approve.router)
app.include_router(newsletter.router)
app.include_router(scheduler_router.router)


@app.get("/api/health")
def health_check():
    return {"status": "ok"}


# ── Serve built React frontend for all non-API routes ─────────────────────
# Mount the Vite build output so assets (JS/CSS/images) are served directly.
# The catch-all route below handles SPA client-side routing (e.g. /dashboard).
FRONTEND_DIST = Path(__file__).resolve().parents[2] / "dist" / "public"

if FRONTEND_DIST.exists():
    app.mount(
        "/assets",
        StaticFiles(directory=str(FRONTEND_DIST / "assets")),
        name="frontend-assets",
    )

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        """
        Catch-all: serve index.html for every path that isn't an /api route,
        so React Router (wouter) handles client-side navigation.
        """
        # Serve known static root files directly (favicon, robots.txt, etc.)
        candidate = FRONTEND_DIST / full_path
        if candidate.is_file():
            return FileResponse(str(candidate))
        # Everything else → SPA shell
        return FileResponse(str(FRONTEND_DIST / "index.html"))
else:
    @app.get("/")
    def root():
        return {"status": "ok", "service": "WishNest API (frontend not built)"}
