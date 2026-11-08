"""رمزهای هش‌شده و نشست‌های حافظه‌ای برای اجرای تک‌پردازه‌ای."""
import hashlib
import hmac
import os
import secrets
import threading
import time
from dataclasses import dataclass

from fastapi import HTTPException, Request

COOKIE_NAME = "hrms_session"
SESSION_SECONDS = int(os.getenv("SESSION_HOURS", "8")) * 3600
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 600_000)
    return f"pbkdf2_sha256$600000${salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, iterations, salt, expected = stored.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(iterations))
        return hmac.compare_digest(digest.hex(), expected)
    except (ValueError, TypeError):
        return False


@dataclass
class Session:
    admin_id: int | None
    csrf_token: str
    expires_at: float


sessions: dict[str, Session] = {}
session_lock = threading.Lock()


def new_session(admin_id: int | None = None) -> tuple[str, Session]:
    now = time.time()
    lifetime = SESSION_SECONDS if admin_id is not None else 1800
    token = secrets.token_urlsafe(32)
    session = Session(admin_id, secrets.token_urlsafe(32), now + lifetime)
    with session_lock:
        for old_token in list(sessions):
            if sessions[old_token].expires_at <= now:
                del sessions[old_token]
        sessions[token] = session
    return token, session


def current_session(request: Request) -> Session | None:
    token = request.cookies.get(COOKIE_NAME, "")
    with session_lock:
        session = sessions.get(token)
        if session and session.expires_at > time.time():
            return session
        sessions.pop(token, None)
    return None


def discard_session(request: Request) -> None:
    with session_lock:
        sessions.pop(request.cookies.get(COOKIE_NAME, ""), None)


def set_session_cookie(response, token: str, authenticated: bool = True) -> None:
    response.set_cookie(COOKIE_NAME, token, max_age=SESSION_SECONDS if authenticated else 1800,
                        httponly=True, secure=COOKIE_SECURE, samesite="lax", path="/")


def require_login(request: Request) -> Session:
    session = current_session(request)
    if not session or session.admin_id is None:
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    from .database import Admin, SessionLocal
    with SessionLocal() as db:
        user = db.get(Admin, session.admin_id)
    if not user or not user.is_active:
        discard_session(request)
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    request.state.user = user
    return session


def check_csrf(request: Request, form: dict) -> None:
    session = current_session(request)
    token = str(form.get("csrf_token", ""))
    if not session or not hmac.compare_digest(token, session.csrf_token):
        raise HTTPException(403, "اعتبار فرم منقضی شده است؛ صفحه را تازه کنید و دوباره تلاش کنید.")
