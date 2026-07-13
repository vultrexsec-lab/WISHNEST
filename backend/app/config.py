"""
Central configuration for the WishNest AI Research Editor Agent backend.

All secrets are read from environment variables (Replit Secrets in this
environment). Nothing sensitive is ever hardcoded here.
"""
import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Database ---
    database_url: str = os.environ.get("DATABASE_URL", "")

    # --- AI / Research providers ---
    # Accept CHATGPT_API_KEY as an alias for OPENAI_API_KEY (Replit secret name)
    openai_api_key: str = (
        os.environ.get("OPENAI_API_KEY", "")
        or os.environ.get("CHATGPT_API_KEY", "")
    )
    firecrawl_api_key: str = os.environ.get("FIRECRAWL_API_KEY", "")

    # --- Image providers (fallback chain: DDG -> Pexels -> Unsplash) ---
    pexels_api_key: str = os.environ.get("PEXELS_API_KEY", "")
    unsplash_access_key: str = os.environ.get("UNSPLASH_ACCESS_KEY", "")

    # --- Live property data (photos + ratings) for the image pipeline and
    # the scorecard calculator. Google Places is tried first; SerpApi's
    # Google Maps engine is the fallback when only that key is configured. ---
    google_places_api_key: str = os.environ.get("GOOGLE_PLACES_API_KEY", "")
    serpapi_key: str = os.environ.get("SERPAPI_KEY", "")

    # --- Auth ---
    admin_username: str = os.environ.get("ADMIN_USERNAME", "")
    admin_password: str = os.environ.get("ADMIN_PASSWORD", "")
    jwt_secret: str = os.environ.get("SESSION_SECRET", "")

    # --- App ---
    environment: str = os.environ.get("ENVIRONMENT", "development")
    # Comma-separated allowed CORS origins (kept as str so pydantic_settings
    # never tries to JSON-parse it). main.py splits on comma.
    cors_origins_raw: str = os.environ.get("CORS_ORIGINS", "")


@lru_cache
def get_settings() -> Settings:
    return Settings()
