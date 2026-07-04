"""
POST /api/auth/login

Single-admin login for the editorial Review Dashboard. Returns a bearer JWT
on success; the frontend stores it and sends it as `Authorization: Bearer
<token>` on subsequent dashboard/approval requests.
"""
from fastapi import APIRouter, HTTPException

from app.schemas.article import LoginRequest, LoginResponse
from app.services.auth_service import AuthError, create_access_token, verify_credentials

router = APIRouter(tags=["auth"])


@router.post("/api/auth/login", response_model=LoginResponse)
def login(payload: LoginRequest):
    try:
        ok = verify_credentials(payload.username, payload.password)
    except AuthError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if not ok:
        raise HTTPException(status_code=401, detail="Invalid username or password.")

    try:
        token = create_access_token(payload.username)
    except AuthError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return LoginResponse(access_token=token, token_type="bearer")
