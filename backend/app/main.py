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
from app.routers import approve, articles, auth, image_proxy, newsletter, research, vision, reimaging, submissions, growth
from app.routers import scheduler as scheduler_router
from app.models import automation  # noqa: F401 ensures settings table metadata is loaded
from app.models import media_blob  # noqa: F401 ensures media_blobs table metadata is loaded
from app.models import submission  # noqa: F401 ensures hospitality_submissions tables are loaded

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
        ("place_id",            "TEXT"),
        ("newsletter_sent_at",  "TIMESTAMPTZ"),
    ]
    log = logging.getLogger("wishnest.schema")
    try:
        with engine.connect() as conn:
            # The daily automation is opt-in and must survive API restarts.
            automation.AutomationSettings.__table__.create(bind=conn, checkfirst=True)
            for col, pg_type in REQUIRED_COLS:
                conn.execute(
                    text(f"ALTER TABLE articles ADD COLUMN IF NOT EXISTS {col} {pg_type}")
                )
            automation_cols = [
                ("enabled", "BOOLEAN NOT NULL DEFAULT false"),
                ("daily_time", "VARCHAR(5) NOT NULL DEFAULT '08:00'"),
                ("timezone", "VARCHAR(64) NOT NULL DEFAULT 'Asia/Kolkata'"),
                ("notification_email", "TEXT"),
                ("public_app_url", "TEXT"),
                ("last_run_date", "DATE"),
                ("last_run_status", "VARCHAR(32)"),
                ("last_run_message", "TEXT"),
                ("last_run_at", "TIMESTAMPTZ"),
                ("last_article_id", "VARCHAR(64)"),
                ("updated_at", "TIMESTAMPTZ NOT NULL DEFAULT now()"),
            ]
            for col, pg_type in automation_cols:
                conn.execute(
                    text(
                        f"ALTER TABLE automation_settings "
                        f"ADD COLUMN IF NOT EXISTS {col} {pg_type}"
                    )
                )
            # Partial unique index: one active (non-trashed) article per place_id.
            # Prevents duplicate rows when the scheduler or concurrent POST /api/research
            # requests race to insert articles for the same Google Maps property.
            # IF NOT EXISTS keeps this idempotent across restarts.
            conn.execute(text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_articles_place_id_active "
                "ON articles (place_id) "
                "WHERE place_id IS NOT NULL AND is_trash = false"
            ))
            # Persistent image storage for Reimaging Studio (survives disk resets)
            conn.execute(text(
                """
                CREATE TABLE IF NOT EXISTS media_blobs (
                    id UUID PRIMARY KEY,
                    content_type VARCHAR(64) NOT NULL DEFAULT 'image/png',
                    filename VARCHAR(255),
                    data BYTEA NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            ))
            conn.execute(text(
                """
                CREATE TABLE IF NOT EXISTS hospitality_submissions (
                    id UUID PRIMARY KEY,
                    reference VARCHAR(32) NOT NULL UNIQUE,
                    property_name VARCHAR(255) NOT NULL,
                    project_stage VARCHAR(64) NOT NULL,
                    property_type VARCHAR(128),
                    company_name VARCHAR(255),
                    contact_name VARCHAR(255) NOT NULL,
                    contact_role VARCHAR(128),
                    email VARCHAR(255) NOT NULL,
                    phone VARCHAR(64),
                    whatsapp VARCHAR(64),
                    location VARCHAR(255),
                    website VARCHAR(512),
                    social_links TEXT,
                    unit_count VARCHAR(64),
                    project_details TEXT,
                    review_focus TEXT,
                    consent_contact BOOLEAN NOT NULL DEFAULT false,
                    consent_materials BOOLEAN NOT NULL DEFAULT false,
                    status VARCHAR(64) NOT NULL DEFAULT 'application_received',
                    source VARCHAR(64),
                    admin_notes TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            ))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_hospitality_submissions_email ON hospitality_submissions (email)"
            ))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_hospitality_submissions_status ON hospitality_submissions (status)"
            ))
            conn.execute(text(
                """
                CREATE TABLE IF NOT EXISTS submission_files (
                    id UUID PRIMARY KEY,
                    submission_id UUID NOT NULL REFERENCES hospitality_submissions(id) ON DELETE CASCADE,
                    original_name VARCHAR(512) NOT NULL,
                    stored_name VARCHAR(512) NOT NULL,
                    content_type VARCHAR(128),
                    size_bytes INTEGER,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            ))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_submission_files_submission_id ON submission_files (submission_id)"
            ))
            conn.commit()

            for col, typ in (
                ("utm_source", "VARCHAR(128)"),
                ("utm_medium", "VARCHAR(128)"),
                ("utm_campaign", "VARCHAR(128)"),
            ):
                conn.execute(text(
                    f"ALTER TABLE hospitality_submissions ADD COLUMN IF NOT EXISTS {col} {typ}"
                ))
            conn.commit()

            conn.execute(text(
                "ALTER TABLE newsletter_subscribers ADD COLUMN IF NOT EXISTS interests VARCHAR(512)"
            ))
            conn.commit()
        
            # Growth & Intelligence OS tables
            for tbl_sql in (
                """
                CREATE TABLE IF NOT EXISTS growth_contacts (
                    id UUID PRIMARY KEY,
                    external_mautic_id VARCHAR(64),
                    name VARCHAR(255),
                    email VARCHAR(255),
                    phone VARCHAR(64),
                    company VARCHAR(255),
                    contact_type VARCHAR(64),
                    country VARCHAR(64),
                    state VARCHAR(128),
                    city VARCHAR(128),
                    destination VARCHAR(128),
                    email_permission BOOLEAN DEFAULT false,
                    whatsapp_permission BOOLEAN DEFAULT false,
                    phone_permission BOOLEAN DEFAULT false,
                    unsubscribed BOOLEAN DEFAULT false,
                    do_not_contact BOOLEAN DEFAULT false,
                    tags TEXT,
                    interests TEXT,
                    intelligence_score INTEGER DEFAULT 0,
                    commercial_score INTEGER DEFAULT 0,
                    source VARCHAR(128),
                    notes TEXT,
                    meta JSONB,
                    created_at TIMESTAMPTZ DEFAULT now(),
                    updated_at TIMESTAMPTZ DEFAULT now()
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS arrowx_opportunities (
                    id UUID PRIMARY KEY,
                    contact_id UUID,
                    source_type VARCHAR(64) NOT NULL,
                    source_id VARCHAR(128),
                    title VARCHAR(512) NOT NULL,
                    summary TEXT,
                    destination VARCHAR(128),
                    demand_signals JSONB,
                    status VARCHAR(64) NOT NULL DEFAULT 'new',
                    consent_commercial BOOLEAN DEFAULT false,
                    created_at TIMESTAMPTZ DEFAULT now(),
                    updated_at TIMESTAMPTZ DEFAULT now()
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS seo_geo_runs (
                    id UUID PRIMARY KEY,
                    article_id VARCHAR(64) NOT NULL,
                    seo_score FLOAT,
                    geo_score FLOAT,
                    primary_keyword VARCHAR(255),
                    meta_title VARCHAR(512),
                    meta_description VARCHAR(1024),
                    direct_answer TEXT,
                    faq_json JSONB,
                    schema_json JSONB,
                    internal_links JSONB,
                    postiz_status VARCHAR(64),
                    postiz_payload JSONB,
                    raw JSONB,
                    created_at TIMESTAMPTZ DEFAULT now()
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS audience_segments (
                    id UUID PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    description TEXT,
                    filters JSONB NOT NULL DEFAULT '{}',
                    contact_count INTEGER DEFAULT 0,
                    created_at TIMESTAMPTZ DEFAULT now(),
                    updated_at TIMESTAMPTZ DEFAULT now()
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS growth_campaigns (
                    id UUID PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    campaign_type VARCHAR(64) NOT NULL DEFAULT 'lead_generation',
                    classification VARCHAR(64) NOT NULL DEFAULT 'commercial',
                    objective VARCHAR(128),
                    audience_filters JSONB,
                    audience_count INTEGER DEFAULT 0,
                    channels JSONB,
                    cta_label VARCHAR(255),
                    cta_url VARCHAR(512),
                    status VARCHAR(64) NOT NULL DEFAULT 'draft',
                    pack JSONB,
                    notes TEXT,
                    created_at TIMESTAMPTZ DEFAULT now(),
                    updated_at TIMESTAMPTZ DEFAULT now()
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS growth_surveys (
                    id UUID PRIMARY KEY,
                    title VARCHAR(255) NOT NULL,
                    destination VARCHAR(128),
                    topic VARCHAR(128),
                    status VARCHAR(64) NOT NULL DEFAULT 'active',
                    questions JSONB,
                    created_at TIMESTAMPTZ DEFAULT now(),
                    updated_at TIMESTAMPTZ DEFAULT now()
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS growth_survey_responses (
                    id UUID PRIMARY KEY,
                    survey_id UUID NOT NULL,
                    contact_id UUID,
                    email VARCHAR(255),
                    answers JSONB NOT NULL DEFAULT '{}',
                    consent_commercial BOOLEAN DEFAULT false,
                    created_at TIMESTAMPTZ DEFAULT now()
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS outreach_jobs (
                    id UUID PRIMARY KEY,
                    channel VARCHAR(64) NOT NULL,
                    status VARCHAR(64) NOT NULL DEFAULT 'draft',
                    title VARCHAR(255) NOT NULL,
                    payload JSONB,
                    result JSONB,
                    created_at TIMESTAMPTZ DEFAULT now(),
                    updated_at TIMESTAMPTZ DEFAULT now()
                )
                """,
            ):
                try:
                    conn.execute(text(tbl_sql))
                except Exception as te:
                    log.warning("Growth table create skipped: %s", te)
            conn.commit()

        log.info("Schema sync: media_blobs + hospitality_submissions + newsletter interests present.")
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
app.include_router(submissions.router)
app.include_router(scheduler_router.router)
app.include_router(vision.router)
app.include_router(reimaging.router)
app.include_router(growth.router)


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
