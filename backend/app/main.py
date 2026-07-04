"""
WishNest AI Research Editor Agent — FastAPI backend entrypoint.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import approve, articles, auth, newsletter, research

settings = get_settings()

app = FastAPI(
    title="WishNest AI Research Editor Agent",
    description="Backend powering research, drafting, scoring and human-approved publishing of WishNest editorial content.",
    version="0.1.0",
)

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
