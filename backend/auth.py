"""
Auth utilities for Data Compass.

Provides:
  - SQLite-backed user accounts  (PBKDF2 — stdlib only, no passlib)
  - JWT access tokens            (PyJWT)
  - Server-side session storage  (one row per session, per user)
  - FastAPI dependency           get_current_user
"""
import json
import os
import sqlite3
import hashlib
import hmac as _hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_SECRET    = os.environ.get("JWT_SECRET") or secrets.token_hex(32)
_ALGORITHM = "HS256"
_TOKEN_EXPIRE_DAYS = 7

_DB_PATH = os.path.join(os.path.dirname(__file__), "data", "app.db")
_bearer  = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# DB bootstrap
# ---------------------------------------------------------------------------

def _conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)
    c = sqlite3.connect(_DB_PATH, check_same_thread=False)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA foreign_keys=ON")
    return c


def init_db() -> None:
    """Create tables if they don't exist. Called once at startup."""
    with _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT    UNIQUE NOT NULL COLLATE NOCASE,
                pw_hash  TEXT    NOT NULL,
                created  TEXT    NOT NULL
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id         TEXT    PRIMARY KEY,
                user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                title      TEXT    NOT NULL DEFAULT '',
                ts         INTEGER NOT NULL DEFAULT 0,
                messages   TEXT    NOT NULL DEFAULT '[]',
                provider   TEXT    NOT NULL DEFAULT '',
                query_type TEXT    NOT NULL DEFAULT 'sql',
                updated    TEXT    NOT NULL
            )
        """)
        c.execute(
            "CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id, ts DESC)"
        )


# ---------------------------------------------------------------------------
# Password utilities  (PBKDF2-SHA256, stdlib only)
# ---------------------------------------------------------------------------

def _hash_pw(password: str) -> str:
    salt = secrets.token_hex(16)
    dk   = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 260_000)
    return f"{salt}:{dk.hex()}"


def _check_pw(password: str, stored: str) -> bool:
    try:
        salt, stored_hex = stored.split(":", 1)
    except ValueError:
        return False
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 260_000)
    return _hmac.compare_digest(dk.hex(), stored_hex)


# ---------------------------------------------------------------------------
# User CRUD
# ---------------------------------------------------------------------------

def create_user(username: str, password: str) -> dict:
    username = username.strip()
    if len(username) < 3:
        raise ValueError("Username must be at least 3 characters.")
    if len(password) < 6:
        raise ValueError("Password must be at least 6 characters.")
    pw_hash = _hash_pw(password)
    with _conn() as c:
        try:
            cur = c.execute(
                "INSERT INTO users (username, pw_hash, created) VALUES (?,?,?)",
                (username, pw_hash, datetime.now(timezone.utc).isoformat()),
            )
            return {"id": cur.lastrowid, "username": username}
        except sqlite3.IntegrityError:
            raise ValueError(f"Username '{username}' is already taken.")


def authenticate_user(username: str, password: str) -> Optional[dict]:
    with _conn() as c:
        row = c.execute(
            "SELECT id, username, pw_hash FROM users WHERE username = ?",
            (username.strip(),),
        ).fetchone()
    if not row or not _check_pw(password, row["pw_hash"]):
        return None
    return {"id": row["id"], "username": row["username"]}


# ---------------------------------------------------------------------------
# JWT utilities
# ---------------------------------------------------------------------------

def create_token(user: dict) -> str:
    exp = datetime.now(timezone.utc) + timedelta(days=_TOKEN_EXPIRE_DAYS)
    return jwt.encode(
        {"sub": user["username"], "uid": user["id"], "exp": exp},
        _SECRET,
        algorithm=_ALGORITHM,
    )


def _decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, _SECRET, algorithms=[_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired — please log in again.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token.")


# ---------------------------------------------------------------------------
# FastAPI dependency — injects decoded token payload or raises 401
# ---------------------------------------------------------------------------

def get_current_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> dict:
    if not creds:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return _decode_token(creds.credentials)


# ---------------------------------------------------------------------------
# Session CRUD
# ---------------------------------------------------------------------------

def list_sessions(user_id: int) -> list:
    with _conn() as c:
        rows = c.execute(
            "SELECT id, title, ts, provider, query_type, messages "
            "FROM sessions WHERE user_id = ? ORDER BY ts DESC",
            (user_id,),
        ).fetchall()
    return [
        {
            "id":        r["id"],
            "title":     r["title"],
            "timestamp": r["ts"],
            "provider":  r["provider"],
            "queryType": r["query_type"],
            "messages":  json.loads(r["messages"]),
        }
        for r in rows
    ]


def upsert_session(user_id: int, session: dict) -> None:
    with _conn() as c:
        c.execute(
            """
            INSERT INTO sessions (id, user_id, title, ts, messages, provider, query_type, updated)
            VALUES (?,?,?,?,?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET
              title      = excluded.title,
              messages   = excluded.messages,
              provider   = excluded.provider,
              query_type = excluded.query_type,
              updated    = excluded.updated
            """,
            (
                session["id"],
                user_id,
                session.get("title", ""),
                session.get("timestamp", 0),
                json.dumps(session.get("messages", [])),
                session.get("provider", ""),
                session.get("queryType", "sql"),
                datetime.now(timezone.utc).isoformat(),
            ),
        )


def delete_session(user_id: int, session_id: str) -> None:
    with _conn() as c:
        c.execute(
            "DELETE FROM sessions WHERE id = ? AND user_id = ?",
            (session_id, user_id),
        )
