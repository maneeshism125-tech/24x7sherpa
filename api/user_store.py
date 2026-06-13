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


def _migrate(conn: sqlite3.Connection) -> None:
    cur = conn.execute("PRAGMA table_info(users)")
    cols = {row[1] for row in cur.fetchall()}
    if "email" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN email TEXT")
    if "address" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN address TEXT")
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email_unique "
        "ON users(email) WHERE email IS NOT NULL AND trim(email) != ''"
    )


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
            _migrate(conn)
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
    email: str | None = None,
    address: str | None = None,
) -> None:
    uid = user_id.strip()
    em = email.strip().lower() if email and email.strip() else None
    addr = address.strip() if address and address.strip() else None
    path = _db_path(data_dir)
    with _lock:
        conn = sqlite3.connect(str(path), check_same_thread=False)
        try:
            conn.execute(
                """
                INSERT INTO users (user_id, password_hash, is_admin, disabled, created_at, email, address)
                VALUES (?,?,?,?,?,?,?)
                """,
                (uid, password_hash, 1 if is_admin else 0, 0, time.time(), em, addr),
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
                """
                SELECT user_id, password_hash, is_admin, disabled, created_at, email, address
                FROM users WHERE user_id = ? COLLATE NOCASE
                """,
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
                "email": row["email"],
                "address": row["address"],
            }
        finally:
            conn.close()


def is_email_taken(data_dir: Path, email: str, *, except_user_id: str | None = None) -> bool:
    em = email.strip().lower()
    path = _db_path(data_dir)
    if not path.exists():
        return False
    with _lock:
        conn = sqlite3.connect(str(path), check_same_thread=False)
        try:
            if except_user_id:
                row = conn.execute(
                    """
                    SELECT 1 FROM users
                    WHERE lower(trim(email)) = ? AND lower(user_id) != lower(?)
                    LIMIT 1
                    """,
                    (em, except_user_id.strip()),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT 1 FROM users WHERE lower(trim(email)) = ? LIMIT 1",
                    (em,),
                ).fetchone()
            return row is not None
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
                """
                SELECT user_id, is_admin, disabled, created_at, email, address
                FROM users ORDER BY user_id COLLATE NOCASE
                """
            )
            return [
                {
                    "user_id": r["user_id"],
                    "is_admin": bool(r["is_admin"]),
                    "disabled": bool(r["disabled"]),
                    "created_at": float(r["created_at"]),
                    "email": r["email"],
                    "address": r["address"],
                }
                for r in cur.fetchall()
            ]
        finally:
            conn.close()


def update_user(data_dir: Path, user_id: str, updates: dict[str, Any]) -> bool:
    """
    Apply partial updates. Keys: password_hash, is_admin, disabled, email, address.
    Omitted keys are left unchanged. ``email`` / ``address`` may be set to None to clear.
    """
    uid = user_id.strip()
    path = _db_path(data_dir)
    fields: list[str] = []
    vals: list[Any] = []
    if "password_hash" in updates:
        fields.append("password_hash = ?")
        vals.append(updates["password_hash"])
    if "is_admin" in updates:
        fields.append("is_admin = ?")
        vals.append(1 if updates["is_admin"] else 0)
    if "disabled" in updates:
        fields.append("disabled = ?")
        vals.append(1 if updates["disabled"] else 0)
    if "email" in updates:
        em = updates["email"]
        if em is not None and str(em).strip():
            em = str(em).strip().lower()
        else:
            em = None
        fields.append("email = ?")
        vals.append(em)
    if "address" in updates:
        addr = updates["address"]
        if addr is not None and str(addr).strip():
            addr = str(addr).strip()
        else:
            addr = None
        fields.append("address = ?")
        vals.append(addr)
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
