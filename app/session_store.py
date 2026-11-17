"""Explicit memory/Redis opaque-session storage; no account or password cache."""
import hashlib
import json
import math
import os
import re
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import redis


@dataclass
class Session:
    admin_id: int | None
    csrf_token: str
    expires_at: float


class SessionStoreUnavailable(Exception):
    """Sanitized dependency failure, translated to a fail-closed HTTP 503."""


class MemorySessionStore:
    SWEEP_INTERVAL_SECONDS = 30

    def __init__(self, sessions=None, lock=None):
        self.sessions = sessions if sessions is not None else {}
        self.lock = lock if lock is not None else threading.Lock()
        self.next_sweep = float("-inf")

    def _sweep_expired(self, now):
        tick = time.monotonic()
        if tick >= self.next_sweep:
            expired = [token for token, session in self.sessions.items() if session.expires_at <= now]
            for token in expired:
                del self.sessions[token]
            self.next_sweep = tick + self.SWEEP_INTERVAL_SECONDS

    def get(self, token):
        with self.lock:
            value = self.sessions.get(token)
            if value and value.expires_at > time.time():
                return value
            self.sessions.pop(token, None)
            return None

    def put(self, token, session):
        with self.lock:
            self._sweep_expired(time.time())
            self.sessions[token] = session

    def delete(self, token):
        with self.lock:
            self.sessions.pop(token, None)

    def rotate(self, old_token, new_token, session):
        with self.lock:
            now = time.time()
            previous = self.sessions.get(old_token)
            if not previous or previous.expires_at <= now:
                self.sessions.pop(old_token, None)
                return False
            self._sweep_expired(now)
            self.sessions.pop(old_token)
            self.sessions[new_token] = session
            return True

    def ping(self):
        return True


class RedisSessionStore:
    ROTATE = """
        local previous = redis.call('GET', KEYS[1])
        if not previous then return 0 end
        local ok, value = pcall(cjson.decode, previous)
        if not ok or type(value.expires_at) ~= 'number' or value.expires_at <= tonumber(ARGV[3]) then return 0 end
        if redis.call('EXISTS', KEYS[2]) == 1 then return 0 end
        redis.call('SET', KEYS[2], ARGV[1], 'EX', ARGV[2])
        redis.call('DEL', KEYS[1])
        return 1
    """

    def __init__(self, client, namespace="hrms:sessions"):
        if not re.fullmatch(r"[a-zA-Z0-9:_-]{1,100}", namespace):
            raise ValueError("Choose a simple explicit Redis session namespace.")
        self.client = client
        self.namespace = namespace

    def key(self, token):
        return self.namespace + ":" + hashlib.sha256(token.encode()).hexdigest()

    def operation(self, function, *args, **kwargs):
        try:
            return function(*args, **kwargs)
        except redis.RedisError:
            raise SessionStoreUnavailable("Session storage unavailable.") from None

    def get(self, token):
        if not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
            return None
        encoded = self.operation(self.client.get, self.key(token))
        if encoded is None:
            return None
        try:
            value = json.loads(encoded)
            session = Session(**value)
            if (session.admin_id is not None and (type(session.admin_id) is not int or session.admin_id <= 0)) \
                    or not re.fullmatch(r"[A-Za-z0-9_-]{43}", session.csrf_token) \
                    or not isinstance(session.expires_at, (float, int)) or not math.isfinite(session.expires_at):
                return None
            return session if session.expires_at > time.time() else None
        except (ValueError, TypeError):
            return None

    def put(self, token, session):
        ttl = max(1, math.ceil(session.expires_at - time.time()))
        self.operation(self.client.set, self.key(token), json.dumps(asdict(session)), ex=ttl)

    def delete(self, token):
        if re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
            self.operation(self.client.delete, self.key(token))

    def rotate(self, old_token, new_token, session):
        if not re.fullmatch(r"[A-Za-z0-9_-]{43}", old_token):
            return False
        ttl = max(1, math.ceil(session.expires_at - time.time()))
        return bool(self.operation(self.client.eval, self.ROTATE, 2, self.key(old_token),
            self.key(new_token), json.dumps(asdict(session)), ttl, time.time()))

    def ping(self):
        return self.operation(self.client.ping)


def configured_store(sessions, lock):
    mode = os.getenv("HRMS_SESSION_BACKEND", "memory")
    if mode == "memory":
        return MemorySessionStore(sessions, lock)
    if mode != "redis":
        raise RuntimeError("HRMS_SESSION_BACKEND must be memory or redis.")
    password_path = os.getenv("HRMS_REDIS_PASSWORD_FILE", "")
    if not password_path:
        raise RuntimeError("Shared sessions require HRMS_REDIS_PASSWORD_FILE.")
    password = Path(password_path).read_text(encoding="utf-8").strip()
    if len(password) < 12:
        raise RuntimeError("Redis password is too short.")
    client = redis.Redis(host=os.getenv("HRMS_REDIS_HOST", "redis"),
        port=int(os.getenv("HRMS_REDIS_PORT", "6379")), password=password,
        ssl=os.getenv("HRMS_REDIS_TLS", "false").lower() == "true",
        socket_connect_timeout=1, socket_timeout=1, max_connections=32,
        decode_responses=True, retry_on_timeout=False, health_check_interval=30)
    return RedisSessionStore(client, os.getenv("HRMS_REDIS_NAMESPACE", "hrms:sessions"))
