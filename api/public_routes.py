from __future__ import annotations

import asyncio
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from api.auth_crypto import mint_token, verify_password
from api.deps import settings_dep
from api.schemas import AuthConfigResponse, LoginBody, LoginResponse
from api.user_store import get_user_row
from sherpa.config import Settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["auth"])


@router.get("/api/health")
def api_health() -> dict:
    return {"ok": True, "service": "sherpa"}


@router.get("/api/auth/config", response_model=AuthConfigResponse)
def auth_config(settings: Annotated[Settings, Depends(settings_dep)]) -> AuthConfigResponse:
    return AuthConfigResponse(auth_required=not settings.auth_disabled)


def _login_sync(settings: Settings, body: LoginBody) -> LoginResponse:
    if settings.auth_disabled:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Authentication is disabled (SHERPA_AUTH_DISABLED=1); no login required.",
        )
    row = get_user_row(settings.data_dir, body.user_id)
    if not row or row["disabled"]:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid user id or password")
    if not verify_password(body.password, row["password_hash"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid user id or password")
    exp_sec = max(3600, settings.jwt_expire_hours * 3600)
    token = mint_token(
        user_id=row["user_id"],
        is_admin=row["is_admin"],
        secret=settings.jwt_secret,
        expire_seconds=exp_sec,
    )
    return LoginResponse(access_token=token, expires_in=exp_sec)


@router.post("/api/auth/login", response_model=LoginResponse)
async def auth_login(
    body: LoginBody,
    settings: Annotated[Settings, Depends(settings_dep)],
) -> LoginResponse:
    try:
        return await asyncio.to_thread(_login_sync, settings, body)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("login failed")
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e
