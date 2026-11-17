"""رمزهای استاندارد و نشست opaque در حافظه یا store مشترک صریح."""
import hashlib
import hmac
import os
import secrets
import threading
import time

from argon2 import PasswordHasher, Type, extract_parameters
from argon2.exceptions import InvalidHashError, VerificationError

from fastapi import HTTPException, Request
from .session_store import Session, configured_store

COOKIE_NAME = "hrms_session"
SESSION_SECONDS = int(os.getenv("SESSION_HOURS", "8")) * 3600
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"
PASSWORD_HASHER = PasswordHasher(memory_cost=19456, time_cost=2, parallelism=1,
    salt_len=16, hash_len=32, type=Type.ID)


def hash_password(password: str) -> str:
    return PASSWORD_HASHER.hash(password)


def verify_password(password: str, stored: str) -> bool:
    if not isinstance(password, str) or not isinstance(stored, str):
        return False
    try:
        if stored.startswith("$argon2id$"):
            parameters = extract_parameters(stored)
            if parameters.type != Type.ID or parameters.version != 19 \
                    or not 1 <= parameters.time_cost <= 10 or not 8 <= parameters.memory_cost <= 262144 \
                    or not 1 <= parameters.parallelism <= 16:
                return False
            return PASSWORD_HASHER.verify(stored, password)
        algorithm, iterations, salt, expected = stored.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(iterations))
        return hmac.compare_digest(digest.hex(), expected)
    except (ValueError, TypeError, InvalidHashError, VerificationError):
        return False


def password_needs_upgrade(stored: str) -> bool:
    if stored.startswith("pbkdf2_sha256$"):
        return True
    parameters = extract_parameters(stored)
    # Stronger stored parameters are not downgraded merely because they differ.
    return parameters.memory_cost < 19456 or parameters.time_cost < 2 \
        or parameters.hash_len < 32 or parameters.salt_len < 16


sessions: dict[str, Session] = {}
session_lock = threading.Lock()
session_store = configured_store(sessions, session_lock)


def credential_marker(password_hash: str) -> str:
    return hashlib.sha256(password_hash.encode()).hexdigest()


def new_session(admin_id: int | None = None) -> tuple[str, Session]:
    now = time.time()
    lifetime = SESSION_SECONDS if admin_id is not None else 1800
    token = secrets.token_urlsafe(32)
    marker = None
    if admin_id is not None:
        from .database import Admin, SessionLocal
        with SessionLocal() as db:
            user = db.get(Admin, admin_id)
            marker = credential_marker(user.password_hash) if user else None
    session = Session(admin_id, secrets.token_urlsafe(32), now + lifetime, marker)
    session_store.put(token, session)
    return token, session


def current_session(request: Request) -> Session | None:
    token = request.cookies.get(COOKIE_NAME, "")
    session = session_store.get(token)
    if session is not None:
        snapshot = getattr(request.state, "session_snapshot", None)
        # Preserve same-request identity only after rereading the store for revocation.
        if snapshot == session:
            return snapshot
        request.state.session_snapshot = session
    return session


def discard_session(request: Request) -> None:
    session_store.delete(request.cookies.get(COOKIE_NAME, ""))


def rotate_session(request: Request, admin_id: int, password_hash: str) -> str:
    token = secrets.token_urlsafe(32)
    session = Session(admin_id, secrets.token_urlsafe(32), time.time() + SESSION_SECONDS, credential_marker(password_hash))
    if not session_store.rotate(request.cookies.get(COOKIE_NAME, ""), token, session):
        raise HTTPException(403, "اعتبار فرم منقضی شده است؛ صفحه را تازه کنید و دوباره تلاش کنید.")
    return token


def set_session_cookie(response, token: str, authenticated: bool = True) -> None:
    response.set_cookie(COOKIE_NAME, token, max_age=SESSION_SECONDS if authenticated else 1800,
                        httponly=True, secure=COOKIE_SECURE, samesite="lax", path="/")


def require_login(request: Request) -> Session:
    session = current_session(request)
    if not session or session.admin_id is None:
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    if getattr(request.state, "authenticated_session", None) is session:
        return session
    from .database import Admin, SessionLocal
    with SessionLocal() as db:
        user = db.get(Admin, session.admin_id)
    if not user or not user.is_active or session.credential_marker != credential_marker(user.password_hash):
        discard_session(request)
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    request.state.user = user
    request.state.authenticated_session = session
    return session


def check_csrf(request: Request, form: dict) -> None:
    session = current_session(request)
    token = str(form.get("csrf_token", ""))
    if not session or not token.isascii() or not hmac.compare_digest(token, session.csrf_token):
        raise HTTPException(403, "اعتبار فرم منقضی شده است؛ صفحه را تازه کنید و دوباره تلاش کنید.")
