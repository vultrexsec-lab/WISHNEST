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

    # --- Auth ---
    admin_username: str = os.environ.get("ADMIN_USERNAME", "")
    admin_password: str = os.environ.get("ADMIN_PASSWORD", "")
    jwt_secret: str = os.environ.get("SESSION_SECRET", "")

    # --- App ---
    environment: str = os.environ.get("ENVIRONMENT", "development")
    # Comma-separated list of allowed CORS origins. Set CORS_ORIGINS in secrets
    # for production. Defaults to permissive dev-only setting.
    cors_origins: list[str] = [
        origin.strip()
        for origin in os.environ.get("CORS_ORIGINS", "*").split(",")
    ]


@lru_cache
def get_settings() -> Settings:
    return Settings()
