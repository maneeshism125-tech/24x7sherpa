from __future__ import annotations

import time
from typing import Any

import jwt
from passlib.context import CryptContext

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    return _pwd.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd.verify(plain, hashed)


def mint_token(*, user_id: str, is_admin: bool, secret: str, expire_seconds: int) -> str:
    now = int(time.time())
    payload: dict[str, Any] = {
        "sub": user_id,
        "adm": bool(is_admin),
        "iat": now,
        "exp": now + expire_seconds,
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def decode_token(token: str, secret: str) -> dict[str, Any]:
    return jwt.decode(token, secret, algorithms=["HS256"])
