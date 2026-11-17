"""Real KDF migration and PostgreSQL/Redis session correctness, including fail-closed paths."""
import hashlib
import json
import os
import re
import secrets
import shutil
import socket
import subprocess
import time
import uuid
from unittest import TestCase
from unittest.mock import patch

import redis
from argon2 import extract_parameters
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DatabaseSession

from app import main, security
from app.database import Admin
from app.hr_models import AuditLog
from app.session_store import MemorySessionStore, RedisSessionStore, Session, SessionStoreUnavailable
from tests.support import PostgresTestCase


def legacy_hash(password):
    salt = secrets.token_hex(16)
    value = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 600000)
    return f"pbkdf2_sha256$600000${salt}${value.hex()}"


class MemoryExpiryContracts(TestCase):
    def test_tc_01_25_throttled_sweeps_preserve_expiry_and_rotation(self):
        store = MemorySessionStore()
        with patch("app.session_store.time.time", return_value=1000) as wall, \
             patch("app.session_store.time.monotonic", return_value=50) as tick:
            expired = Session(None, "synthetic", 1005)
            active = Session(None, "synthetic", 1100)
            for token in ("read", "rotate", "sweep"):
                store.put(token, expired)
            wall.return_value = 1005
            tick.return_value = 55
            store.put("still-valid", active)
            self.assertIn("sweep", store.sessions)
            self.assertIsNone(store.get("read"))
            self.assertFalse(store.rotate("rotate", "unauthorized", active))
            self.assertIsNone(store.get("unauthorized"))
            tick.return_value = 80
            self.assertTrue(store.rotate("still-valid", "new-token", active))
            self.assertNotIn("sweep", store.sessions)
            self.assertIsNone(store.get("still-valid"))
            self.assertEqual(store.get("new-token"), active)
            store.delete("new-token")
            self.assertIsNone(store.get("new-token"))


class PasswordProfiles(TestCase):
    def test_tc_01_17_argon_profile_unique_salts_wrong_and_legacy_passwords(self):
        password = "Synthetic-new-password"
        first, second = security.hash_password(password), security.hash_password(password)
        self.assertNotEqual(first, second)
        profile = extract_parameters(first)
        self.assertEqual((profile.memory_cost, profile.time_cost, profile.parallelism, profile.salt_len, profile.hash_len),
            (19456, 2, 1, 16, 32))
        for stored in (first, legacy_hash(password)):
            self.assertTrue(security.verify_password(password, stored))
            self.assertFalse(security.verify_password("Wrong-synthetic-password", stored))
        for invalid in ("", "malformed", "$argon2id$malformed", "pbkdf2_sha256$not-int$salt$digest", None):
            self.assertFalse(security.verify_password(password, invalid))
        self.assertFalse(security.password_needs_upgrade(first))


class PasswordMigration(PostgresTestCase):
    def test_tc_01_18_legacy_upgrade_is_atomic_and_only_after_success(self):
        password = "Synthetic-legacy-password"
        original = legacy_hash(password)
        with self.factory.begin() as db:
            account = Admin(username="legacy-" + uuid.uuid4().hex, display_name="ساختگی", password_hash=original, role="hr", is_active=True)
            db.add(account)
            db.flush()
            account_id, username = account.id, account.username
        with TestClient(main.app, raise_server_exceptions=False) as client:
            token = re.search(r'name="csrf_token" value="([^"]+)"', client.get("/login").text).group(1)
            old_cookie = client.cookies.get(security.COOKIE_NAME)
            payload = {"username": username, "password": "Wrong-password", "csrf_token": token}
            self.assertEqual(client.post("/login", data=payload, follow_redirects=False).status_code, 401)
            with self.factory() as db:
                self.assertEqual(db.get(Admin, account_id).password_hash, original)
            payload["password"] = password
            with patch.object(main, "audit", side_effect=RuntimeError("Synthetic failure")):
                self.assertEqual(client.post("/login", data=payload, follow_redirects=False).status_code, 500)
            with self.factory() as db:
                self.assertEqual(db.get(Admin, account_id).password_hash, original)
            self.assertEqual(client.cookies.get(security.COOKIE_NAME), old_cookie)
            self.assertEqual(client.post("/login", data=payload, follow_redirects=False).status_code, 303)
            with self.factory() as db:
                upgraded = db.get(Admin, account_id).password_hash
                self.assertTrue(upgraded.startswith("$argon2id$"))
                self.assertTrue(security.verify_password(password, upgraded))
                self.assertEqual(db.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.actor_id == account_id)), 1)


class RedisFixture:
    @classmethod
    def start_redis(cls):
        cls.redis_container = None
        url = os.getenv("HRMS_TEST_REDIS_URL")
        if not url:
            if not shutil.which("docker"):
                raise RuntimeError("These real shared-session tests require Docker or HRMS_TEST_REDIS_URL.")
            with socket.socket() as probe:
                probe.bind(("127.0.0.1", 0))
                port = probe.getsockname()[1]
            cls.redis_container = "hrms-redis-tests-" + uuid.uuid4().hex
            subprocess.run(["docker", "run", "--rm", "-d", "--name", cls.redis_container,
                "-p", f"127.0.0.1:{port}:6379", "redis:7.4.7-bookworm", "redis-server", "--save", "", "--appendonly", "no"],
                check=True, stdout=subprocess.DEVNULL)
            url = f"redis://127.0.0.1:{port}/0"
        cls.redis_client = redis.Redis.from_url(url, decode_responses=True, socket_connect_timeout=1, socket_timeout=1)
        for _ in range(100):
            try:
                if cls.redis_client.ping():
                    return
            except redis.RedisError:
                time.sleep(.1)
        raise RuntimeError("Synthetic Redis fixture did not become ready.")

    @classmethod
    def stop_redis(cls):
        cls.redis_client.close()
        if cls.redis_container:
            subprocess.run(["docker", "stop", cls.redis_container], check=True, stdout=subprocess.DEVNULL)

    def store(self):
        store = RedisSessionStore(self.redis_client, "hrms:test:" + uuid.uuid4().hex)
        def cleanup():
            keys = list(self.redis_client.scan_iter(store.namespace + ":*"))
            if keys:
                self.redis_client.delete(*keys)
        self.addCleanup(cleanup)
        return store


class RedisStorageContracts(RedisFixture, TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.start_redis()

    @classmethod
    def tearDownClass(cls):
        cls.stop_redis()
        super().tearDownClass()

    def test_tc_01_19_cross_client_ttl_digest_rotation_and_revocation(self):
        first = self.store()
        client = redis.Redis(connection_pool=self.redis_client.connection_pool)
        second = RedisSessionStore(client, first.namespace)
        token, next_token, csrf = (secrets.token_urlsafe(32) for _ in range(3))
        anonymous = Session(None, csrf, time.time() + 30)
        first.put(token, anonymous)
        self.assertEqual(second.get(token), anonymous)
        self.assertNotIn(token, first.key(token))
        self.assertGreater(self.redis_client.ttl(first.key(token)), 0)
        authenticated = Session(1, csrf, time.time() + 60)
        self.assertTrue(second.rotate(token, next_token, authenticated))
        self.assertIsNone(first.get(token))
        self.assertEqual(first.get(next_token), authenticated)
        self.assertFalse(first.rotate(token, secrets.token_urlsafe(32), authenticated))
        second.delete(next_token)
        self.assertIsNone(first.get(next_token))
        expired = secrets.token_urlsafe(32)
        first.put(expired, Session(None, csrf, time.time() - 1))
        self.assertIsNone(second.get(expired))
        self.assertFalse(first.rotate(expired, next_token, authenticated))

    def test_tc_01_20_store_error_and_malformed_payload_fail_closed(self):
        store = self.store()
        token = secrets.token_urlsafe(32)
        self.redis_client.set(store.key(token), json.dumps({"admin_id": "bad", "csrf_token": None, "expires_at": time.time() + 60}))
        self.assertIsNone(store.get(token))
        with patch.object(store.client, "get", side_effect=redis.ConnectionError("Synthetic private dependency detail")):
            with self.assertRaisesRegex(SessionStoreUnavailable, "^Session storage unavailable.$"):
                store.get(token)


class RedisLoginContracts(RedisFixture, PostgresTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.start_redis()

    @classmethod
    def tearDownClass(cls):
        cls.stop_redis()
        super().tearDownClass()

    def setUp(self):
        self.shared = self.store()
        store_patch = patch.object(security, "session_store", self.shared)
        store_patch.start()
        self.addCleanup(store_patch.stop)
        self.password = "Synthetic-shared-login"
        with self.factory.begin() as db:
            account = Admin(username="shared-" + uuid.uuid4().hex, display_name="ساختگی", password_hash=security.hash_password(self.password), role="hr", is_active=True)
            db.add(account)
            db.flush()
            self.account_id, self.username = account.id, account.username

    def client_form(self):
        client = TestClient(main.app, raise_server_exceptions=False)
        self.addCleanup(client.close)
        csrf = re.search(r'name="csrf_token" value="([^"]+)"', client.get("/login").text).group(1)
        return client, {"username": self.username, "password": self.password, "csrf_token": csrf}

    def audits(self):
        with self.factory() as db:
            return db.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.actor_id == self.account_id))

    def test_tc_01_21_shared_login_csrf_revoke_and_store_failure(self):
        client, payload = self.client_form()
        self.assertEqual(client.post("/login", data=payload, follow_redirects=False).status_code, 303)
        self.assertEqual(client.get("/").status_code, 200)
        with self.factory.begin() as db:
            db.get(Admin, self.account_id).is_active = False
        self.assertEqual(client.get("/", follow_redirects=False).status_code, 303)
        client, payload = self.client_form()
        with patch.object(self.shared.client, "get", side_effect=redis.ConnectionError("Synthetic secret must not escape")):
            response = client.post("/login", data=payload, follow_redirects=False)
            self.assertEqual(response.status_code, 503)
            self.assertNotIn("Synthetic secret", response.text)
        self.assertEqual(self.audits(), 1)

    def test_tc_01_22_revoked_during_commit_has_no_audit_or_session(self):
        client, payload = self.client_form()
        old_token = client.cookies.get(security.COOKIE_NAME)
        original_audit = main.audit
        def revoke(*args, **kwargs):
            original_audit(*args, **kwargs)
            self.shared.delete(old_token)
        with patch.object(main, "audit", revoke):
            self.assertEqual(client.post("/login", data=payload, follow_redirects=False).status_code, 403)
        self.assertEqual(self.audits(), 0)
        self.assertFalse(list(self.redis_client.scan_iter(self.shared.namespace + ":*")))

    def test_tc_01_23_failed_sql_commit_removes_unissued_shared_session(self):
        client, payload = self.client_form()
        old_token = client.cookies.get(security.COOKIE_NAME)
        with patch.object(DatabaseSession, "commit", side_effect=RuntimeError("Synthetic SQL commit failure")):
            self.assertEqual(client.post("/login", data=payload, follow_redirects=False).status_code, 500)
        self.assertEqual(self.audits(), 0)
        self.assertEqual(client.cookies.get(security.COOKIE_NAME), old_token)
        self.assertFalse(list(self.redis_client.scan_iter(self.shared.namespace + ":*")))
