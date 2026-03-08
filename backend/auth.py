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
from urllib.parse import urlencode

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
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                username   TEXT    UNIQUE NOT NULL COLLATE NOCASE,
                pw_hash    TEXT    NOT NULL DEFAULT '',
                created    TEXT    NOT NULL,
                google_sub TEXT,
                email      TEXT
            )
        """)
        # Migrations: add Google SSO columns to existing databases
        for col_def in ["google_sub TEXT", "email TEXT"]:
            try:
                c.execute(f"ALTER TABLE users ADD COLUMN {col_def}")
            except sqlite3.OperationalError:
                pass  # column already exists
        c.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_google_sub "
            "ON users(google_sub) WHERE google_sub IS NOT NULL"
        )
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


# ---------------------------------------------------------------------------
# Google SSO utilities
# ---------------------------------------------------------------------------

_GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/auth"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"

# Read from environment at call-time so unit tests can patch os.environ
def _google_client_id() -> str:
    return os.environ.get("GOOGLE_CLIENT_ID", "")

def _google_client_secret() -> str:
    return os.environ.get("GOOGLE_CLIENT_SECRET", "")

def _google_redirect_uri() -> str:
    return os.environ.get("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback")

def _frontend_url() -> str:
    return os.environ.get("FRONTEND_URL", "http://localhost:5173")


def google_sso_enabled() -> bool:
    """True when Google OAuth2 credentials are configured."""
    return bool(_google_client_id() and _google_client_secret())


def google_auth_url() -> str:
    """Return the Google OAuth2 authorization URL to redirect the user to."""
    params = {
        "client_id":     _google_client_id(),
        "redirect_uri":  _google_redirect_uri(),
        "response_type": "code",
        "scope":         "openid email profile",
        "access_type":   "offline",
        "prompt":        "select_account",
    }
    return f"{_GOOGLE_AUTH_URL}?{urlencode(params)}"


def google_callback(code: str) -> str:
    """
    Exchange an auth code for tokens, verify the ID token, upsert the user,
    and return a JWT access token.

    Raises HTTPException on any error.
    """
    import requests as _req

    client_id     = _google_client_id()
    client_secret = _google_client_secret()
    redirect_uri  = _google_redirect_uri()

    if not client_id or not client_secret:
        raise HTTPException(status_code=503, detail="Google SSO is not configured.")

    # 1. Exchange code for tokens
    try:
        token_resp = _req.post(_GOOGLE_TOKEN_URL, data={
            "code":          code,
            "client_id":     client_id,
            "client_secret": client_secret,
            "redirect_uri":  redirect_uri,
            "grant_type":    "authorization_code",
        }, timeout=10)
        token_resp.raise_for_status()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Google token exchange failed: {exc}")

    tokens = token_resp.json()
    id_token_str = tokens.get("id_token")
    if not id_token_str:
        raise HTTPException(status_code=502, detail="No id_token in Google response.")

    # 2. Verify the ID token using google-auth
    try:
        from google.oauth2 import id_token as _id_token
        from google.auth.transport import requests as _greq
        id_info = _id_token.verify_oauth2_token(id_token_str, _greq.Request(), client_id)
    except Exception as exc:
        raise HTTPException(status_code=401, detail=f"Google ID token verification failed: {exc}")

    google_sub = id_info.get("sub")
    email      = id_info.get("email", "")
    name       = id_info.get("name", email.split("@")[0] if email else "user")

    if not google_sub:
        raise HTTPException(status_code=401, detail="Google ID token missing 'sub' claim.")

    # 3. Upsert user and issue JWT
    user = _upsert_google_user(google_sub, email, name)
    return create_token(user)


def _upsert_google_user(google_sub: str, email: str, name: str) -> dict:
    """Find or create a user by Google sub. Returns {id, username}."""
    with _conn() as c:
        row = c.execute(
            "SELECT id, username FROM users WHERE google_sub = ?", (google_sub,)
        ).fetchone()
        if row:
            return {"id": row["id"], "username": row["username"]}

        # New user — derive username from name/email, ensure uniqueness
        base = (name or email.split("@")[0] or "user").replace(" ", "_").lower()
        username = base
        i = 1
        while c.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone():
            username = f"{base}{i}"
            i += 1

        cur = c.execute(
            "INSERT INTO users (username, pw_hash, google_sub, email, created) VALUES (?,?,?,?,?)",
            (username, "", google_sub, email, datetime.now(timezone.utc).isoformat()),
        )
        return {"id": cur.lastrowid, "username": username}
