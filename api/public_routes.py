from __future__ import annotations

import asyncio
import logging
import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from api.auth_crypto import hash_password, mint_token, verify_password
from api.deps import settings_dep
from api.schemas import AuthConfigResponse, LoginBody, LoginResponse, RegisterBody
from api.user_store import create_user, get_user_row, is_email_taken
from sherpa.config import Settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["auth"])


@router.get("/api/health")
def api_health() -> dict:
    return {"ok": True, "service": "sherpa"}


@router.get("/api/auth/config", response_model=AuthConfigResponse)
def auth_config(settings: Annotated[Settings, Depends(settings_dep)]) -> AuthConfigResponse:
    return AuthConfigResponse(
        auth_required=not settings.auth_disabled,
        allow_signup=settings.allow_public_signup and not settings.auth_disabled,
    )


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


def _register_sync(settings: Settings, body: RegisterBody) -> LoginResponse:
    if settings.auth_disabled:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Authentication is disabled; registration is not available.",
        )
    if not settings.allow_public_signup:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Public signup is disabled. Ask an administrator for an account.",
        )
    uid = body.user_id.strip()
    if get_user_row(settings.data_dir, uid):
        raise HTTPException(status.HTTP_409_CONFLICT, "This user id is already taken")
    if is_email_taken(settings.data_dir, str(body.email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "This email is already registered")
    try:
        create_user(
            settings.data_dir,
            user_id=uid,
            password_hash=hash_password(body.password),
            is_admin=False,
            email=str(body.email),
            address=body.address.strip(),
        )
    except sqlite3.IntegrityError:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Could not create account (user id or email may already exist).",
        ) from None
    row = get_user_row(settings.data_dir, uid)
    if not row:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Account creation failed")
    exp_sec = max(3600, settings.jwt_expire_hours * 3600)
    token = mint_token(
        user_id=row["user_id"],
        is_admin=row["is_admin"],
        secret=settings.jwt_secret,
        expire_seconds=exp_sec,
    )
    return LoginResponse(access_token=token, expires_in=exp_sec)


@router.post("/api/auth/register", response_model=LoginResponse)
async def auth_register(
    body: RegisterBody,
    settings: Annotated[Settings, Depends(settings_dep)],
) -> LoginResponse:
    try:
        return await asyncio.to_thread(_register_sync, settings, body)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("register failed")
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e
