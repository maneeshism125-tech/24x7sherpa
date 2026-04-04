from __future__ import annotations

import time
from typing import Any

import bcrypt
import jwt

# bcrypt only considers the first 72 UTF-8 bytes (library may raise if longer).
_BCRYPT_MAX = 72


def _pw_bytes(plain: str) -> bytes:
    return plain.encode("utf-8")[:_BCRYPT_MAX]


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(_pw_bytes(plain), bcrypt.gensalt(rounds=12)).decode("ascii")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_pw_bytes(plain), hashed.encode("ascii"))
    except (ValueError, TypeError):
        return False


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
