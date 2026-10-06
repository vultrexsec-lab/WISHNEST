"""
FastAPI dependencies for admin authentication (bearer JWT) + roles.
"""
from fastapi import Header, HTTPException

from app.services.auth_service import AuthError, decode_access_token
from app.services.roles_service import has_permission, role_for_user


def _extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1].strip()


def require_admin(authorization: str | None = Header(default=None)) -> str:
    """Raises 401 if there is no valid admin bearer token. Returns the username."""
    token = _extract_bearer_token(authorization)
    if not token:
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header.")
    try:
        return decode_access_token(token)
    except AuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


def optional_admin(authorization: str | None = Header(default=None)) -> str | None:
    """Returns the username if a valid admin token is present, else None (no error)."""
    token = _extract_bearer_token(authorization)
    if not token:
        return None
    try:
        return decode_access_token(token)
    except AuthError:
        return None


def require_permission(perm: str):
    """Dependency factory: require admin JWT + role permission."""

    def _dep(authorization: str | None = Header(default=None)) -> str:
        username = require_admin(authorization)
        if not has_permission(username, perm):
            raise HTTPException(
                status_code=403,
                detail=f"Role '{role_for_user(username)}' cannot access '{perm}'",
            )
        return username

    return _dep
