"""SQLite user accounts (thread-safe sync; call from asyncio.to_thread in routes)."""

from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

_lock = threading.Lock()


def _db_path(data_dir: Path) -> Path:
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "users.sqlite"


def init_db(data_dir: Path) -> None:
    path = _db_path(data_dir)
    with _lock:
        conn = sqlite3.connect(str(path), check_same_thread=False)
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY COLLATE NOCASE,
                    password_hash TEXT NOT NULL,
                    is_admin INTEGER NOT NULL DEFAULT 0,
                    disabled INTEGER NOT NULL DEFAULT 0,
                    created_at REAL NOT NULL
                )
                """
            )
            conn.commit()
        finally:
            conn.close()


def count_users(data_dir: Path) -> int:
    path = _db_path(data_dir)
    if not path.exists():
        return 0
    with _lock:
        conn = sqlite3.connect(str(path), check_same_thread=False)
        try:
            row = conn.execute("SELECT COUNT(*) FROM users").fetchone()
            return int(row[0]) if row else 0
        finally:
            conn.close()


def create_user(
    data_dir: Path,
    *,
    user_id: str,
    password_hash: str,
    is_admin: bool = False,
) -> None:
    uid = user_id.strip()
    path = _db_path(data_dir)
    with _lock:
        conn = sqlite3.connect(str(path), check_same_thread=False)
        try:
            conn.execute(
                "INSERT INTO users (user_id, password_hash, is_admin, disabled, created_at) VALUES (?,?,?,?,?)",
                (uid, password_hash, 1 if is_admin else 0, 0, time.time()),
            )
            conn.commit()
        finally:
            conn.close()


def get_user_row(data_dir: Path, user_id: str) -> dict[str, Any] | None:
    uid = user_id.strip()
    path = _db_path(data_dir)
    if not path.exists():
        return None
    with _lock:
        conn = sqlite3.connect(str(path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            cur = conn.execute(
                "SELECT user_id, password_hash, is_admin, disabled, created_at FROM users WHERE user_id = ? COLLATE NOCASE",
                (uid,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return {
                "user_id": row["user_id"],
                "password_hash": row["password_hash"],
                "is_admin": bool(row["is_admin"]),
                "disabled": bool(row["disabled"]),
                "created_at": float(row["created_at"]),
            }
        finally:
            conn.close()


def list_users(data_dir: Path) -> list[dict[str, Any]]:
    path = _db_path(data_dir)
    if not path.exists():
        return []
    with _lock:
        conn = sqlite3.connect(str(path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            cur = conn.execute(
                "SELECT user_id, is_admin, disabled, created_at FROM users ORDER BY user_id COLLATE NOCASE"
            )
            return [
                {
                    "user_id": r["user_id"],
                    "is_admin": bool(r["is_admin"]),
                    "disabled": bool(r["disabled"]),
                    "created_at": float(r["created_at"]),
                }
                for r in cur.fetchall()
            ]
        finally:
            conn.close()


def update_user(
    data_dir: Path,
    user_id: str,
    *,
    password_hash: str | None = None,
    is_admin: bool | None = None,
    disabled: bool | None = None,
) -> bool:
    uid = user_id.strip()
    path = _db_path(data_dir)
    fields: list[str] = []
    vals: list[Any] = []
    if password_hash is not None:
        fields.append("password_hash = ?")
        vals.append(password_hash)
    if is_admin is not None:
        fields.append("is_admin = ?")
        vals.append(1 if is_admin else 0)
    if disabled is not None:
        fields.append("disabled = ?")
        vals.append(1 if disabled else 0)
    if not fields:
        return False
    vals.append(uid)
    with _lock:
        conn = sqlite3.connect(str(path), check_same_thread=False)
        try:
            cur = conn.execute(
                f"UPDATE users SET {', '.join(fields)} WHERE user_id = ? COLLATE NOCASE",
                vals,
            )
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()


def count_active_admins(data_dir: Path) -> int:
    path = _db_path(data_dir)
    if not path.exists():
        return 0
    with _lock:
        conn = sqlite3.connect(str(path), check_same_thread=False)
        try:
            row = conn.execute(
                "SELECT COUNT(*) FROM users WHERE is_admin = 1 AND disabled = 0"
            ).fetchone()
            return int(row[0]) if row else 0
        finally:
            conn.close()
