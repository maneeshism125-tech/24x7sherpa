from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status
from jwt.exceptions import PyJWTError
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from api.auth_crypto import decode_token
from api.user_store import get_user_row
from api.schemas import CurrentUser
from sherpa.config import Settings, get_settings

security = HTTPBearer(auto_error=False)


def settings_dep() -> Settings:
    return get_settings()


async def get_current_user(
    settings: Annotated[Settings, Depends(settings_dep)],
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
) -> CurrentUser:
    if settings.auth_disabled:
        return CurrentUser(user_id="local", is_admin=True)
    if creds is None or creds.scheme.lower() != "bearer":
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Missing or invalid Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        data = decode_token(creds.credentials, settings.jwt_secret)
    except PyJWTError:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    uid = data.get("sub")
    if not uid or not isinstance(uid, str):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token payload")
    row = get_user_row(settings.data_dir, uid)
    if not row or row["disabled"]:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account disabled or not found")
    return CurrentUser(user_id=row["user_id"], is_admin=row["is_admin"])


async def require_admin(user: Annotated[CurrentUser, Depends(get_current_user)]) -> CurrentUser:
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")
    return user
