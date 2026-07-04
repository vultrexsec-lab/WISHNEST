"""
Minimal admin authentication: single hardcoded admin account (credentials
from env/secrets: ADMIN_USERNAME / ADMIN_PASSWORD) + JWT bearer tokens
signed with SESSION_SECRET. No user table — this only protects the
editorial dashboard, not multi-user accounts.
"""
import datetime
import secrets

import jwt

from app.config import get_settings

ALGORITHM = "HS256"
TOKEN_TTL_HOURS = 24


class AuthError(Exception):
    pass


def verify_credentials(username: str, password: str) -> bool:
    settings = get_settings()
    if not settings.admin_username or not settings.admin_password:
        raise AuthError("Admin credentials are not configured on the server.")
    valid_username = secrets.compare_digest(username, settings.admin_username)
    valid_password = secrets.compare_digest(password, settings.admin_password)
    return valid_username and valid_password


def create_access_token(username: str) -> str:
    settings = get_settings()
    if not settings.jwt_secret:
        raise AuthError("Server signing secret is not configured.")
    now = datetime.datetime.now(datetime.timezone.utc)
    payload = {
        "sub": username,
        "iat": now,
        "exp": now + datetime.timedelta(hours=TOKEN_TTL_HOURS),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def decode_access_token(token: str) -> str:
    """Returns the username (sub claim) if valid, raises AuthError otherwise."""
    settings = get_settings()
    if not settings.jwt_secret:
        raise AuthError("Server signing secret is not configured.")
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
    except jwt.PyJWTError as exc:
        raise AuthError(f"Invalid or expired token: {exc}") from exc
    username = payload.get("sub")
    if not username:
        raise AuthError("Token missing subject claim.")
    return username
