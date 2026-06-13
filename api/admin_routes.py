from __future__ import annotations

import asyncio
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status

from api.auth_crypto import hash_password
from api.deps import require_admin, settings_dep
from api.schemas import (
    AdminCreateUserBody,
    AdminPatchUserBody,
    CurrentUser,
    UserAdminRow,
)
from api.user_store import (
    count_active_admins,
    create_user,
    get_user_row,
    is_email_taken,
    list_users,
    update_user,
)
from sherpa.config import Settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])


def _row_to_admin(row: dict) -> UserAdminRow:
    return UserAdminRow(
        user_id=row["user_id"],
        is_admin=row["is_admin"],
        disabled=row["disabled"],
        created_at=row["created_at"],
        email=row.get("email"),
        address=row.get("address"),
    )


def _list_sync(settings: Settings) -> list[UserAdminRow]:
    return [_row_to_admin(u) for u in list_users(settings.data_dir)]


@router.get("/users", response_model=list[UserAdminRow])
async def admin_list_users(
    settings: Annotated[Settings, Depends(settings_dep)],
) -> list[UserAdminRow]:
    return await asyncio.to_thread(_list_sync, settings)


def _create_sync(settings: Settings, body: AdminCreateUserBody) -> UserAdminRow:
    uid = body.user_id.strip()
    if get_user_row(settings.data_dir, uid):
        raise HTTPException(status.HTTP_409_CONFLICT, "User id already exists")
    em = str(body.email).strip().lower() if body.email is not None else None
    if em and is_email_taken(settings.data_dir, em):
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already in use")
    addr = body.address.strip() if body.address and body.address.strip() else None
    create_user(
        settings.data_dir,
        user_id=uid,
        password_hash=hash_password(body.password),
        is_admin=body.is_admin,
        email=em,
        address=addr,
    )
    row = get_user_row(settings.data_dir, uid)
    assert row
    return _row_to_admin(row)


@router.post("/users", response_model=UserAdminRow, status_code=status.HTTP_201_CREATED)
async def admin_create_user(
    body: AdminCreateUserBody,
    settings: Annotated[Settings, Depends(settings_dep)],
) -> UserAdminRow:
    try:
        return await asyncio.to_thread(_create_sync, settings, body)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("admin create user")
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e


def _patch_sync(
    settings: Settings,
    user_id: str,
    body: AdminPatchUserBody,
    actor: CurrentUser,
) -> UserAdminRow:
    target = get_user_row(settings.data_dir, user_id)
    if not target:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    active_admins = count_active_admins(settings.data_dir)
    will_disable = body.disabled is True
    will_demote = body.is_admin is False
    if will_disable and target["is_admin"] and not target["disabled"] and active_admins <= 1:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot disable the only active admin")
    if will_demote and target["is_admin"] and active_admins <= 1:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Cannot remove admin role from the only active admin",
        )
    d = body.model_dump(exclude_unset=True)
    upd: dict = {}
    if "password" in d and body.password is not None:
        upd["password_hash"] = hash_password(body.password)
    if "is_admin" in d:
        upd["is_admin"] = body.is_admin
    if "disabled" in d:
        upd["disabled"] = body.disabled
    if "email" in d:
        em = str(body.email).strip().lower() if body.email else None
        if em and is_email_taken(settings.data_dir, em, except_user_id=user_id):
            raise HTTPException(status.HTTP_409_CONFLICT, "Email already in use")
        upd["email"] = em
    if "address" in d:
        upd["address"] = (
            body.address.strip() if body.address and body.address.strip() else None
        )
    if not upd:
        row = get_user_row(settings.data_dir, user_id)
        assert row
        return _row_to_admin(row)
    ok = update_user(settings.data_dir, user_id, upd)
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    row = get_user_row(settings.data_dir, user_id)
    assert row
    _ = actor
    return _row_to_admin(row)


@router.patch("/users/{user_id}", response_model=UserAdminRow)
async def admin_patch_user(
    body: AdminPatchUserBody,
    user: Annotated[CurrentUser, Depends(require_admin)],
    settings: Annotated[Settings, Depends(settings_dep)],
    user_id: str = Path(..., min_length=3, max_length=32),
) -> UserAdminRow:
    try:
        return await asyncio.to_thread(_patch_sync, settings, user_id, body, user)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("admin patch user")
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e
