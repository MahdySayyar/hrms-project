"""Real private-worker and PostgreSQL negative/boundary contracts for concurrent login."""
import asyncio
import importlib
import json
import os
import re
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app import main, security
from app.database import Admin
from app.hr_models import AuditLog
from app.login_capacity import PasswordCapacity, PasswordCapacityFull
from tests.support import PostgresTestCase


class PrivatePasswordWork(IsolatedAsyncioTestCase):
    async def test_tc_01_10_private_queue_limits_retry_and_async_progress(self):
        for workers, pending in ((0, 1), (5, 5), (2, 1), (1, 513)):
            with self.assertRaises(ValueError):
                PasswordCapacity(workers, pending)
        capacity = PasswordCapacity(workers=1, max_pending=2)
        entered, release = threading.Event(), threading.Event()
        tasks = []
        def work(_password, _hash):
            entered.set()
            release.wait(5)
            return True
        try:
            tasks.append(asyncio.create_task(capacity.verify(work, "synthetic", "synthetic")))
            self.assertTrue(await asyncio.to_thread(entered.wait, 2))
            tasks.append(asyncio.create_task(capacity.verify(work, "synthetic", "synthetic")))
            await asyncio.sleep(.03)
            with self.assertRaises(PasswordCapacityFull):
                await capacity.verify(work, "synthetic", "synthetic")
            # This async checkpoint runs while the real private thread is still blocked.
            self.assertFalse(tasks[0].done())
            release.set()
            self.assertEqual(await asyncio.gather(*tasks), [True, True])
            self.assertTrue(await capacity.verify(work, "synthetic", "synthetic"))
        finally:
            release.set()
            await asyncio.gather(*tasks, return_exceptions=True)
            capacity.close()


class LoginCapacityContracts(PostgresTestCase):
    password = "Synthetic-Login-Capacity-Password"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.stored_hash = security.hash_password(cls.password)

    def setUp(self):
        self.capacity = PasswordCapacity(workers=1, max_pending=1)
        self.addCleanup(self.capacity.close)
        self.patch = patch.object(main, "password_capacity", self.capacity)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        with self.factory() as db:
            account = Admin(username="login_test_" + uuid.uuid4().hex, display_name="حساب ساختگی",
                password_hash=self.stored_hash, role="hr", is_active=True)
            db.add(account)
            db.commit()
            self.account_id, self.username = account.id, account.username

    def client(self):
        client = TestClient(main.app, raise_server_exceptions=False)
        self.addCleanup(client.close)
        page = client.get("/login")
        token = re.search(r'name="csrf_token" value="([^"]+)"', page.text).group(1)
        return client, {"username": self.username, "password": self.password, "csrf_token": token}

    def audits(self):
        with self.factory() as db:
            return db.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.action == "login", AuditLog.actor_id == self.account_id))

    def test_tc_01_11_database_released_and_stale_credentials_denied(self):
        for change in ("inactive", "hash"):
            with self.factory() as db:
                account = db.get(Admin, self.account_id)
                account.is_active, account.password_hash = True, self.stored_hash
                db.commit()
            client, payload = self.client()
            old_cookie = client.cookies.get(security.COOKIE_NAME)
            def verify(_password, _hash):
                self.assertEqual(self.sandbox.engine.pool.checkedout(), 0)
                with self.factory() as db:
                    account = db.get(Admin, self.account_id)
                    if change == "inactive":
                        account.is_active = False
                    else:
                        account.password_hash = "A-different-stored-hash"
                    db.commit()
                return True
            with patch.object(main, "verify_password", verify):
                self.assertEqual(client.post("/login", data=payload, follow_redirects=False).status_code, 401)
            self.assertEqual(client.cookies.get(security.COOKIE_NAME), old_cookie)
            self.assertEqual(self.audits(), 0)

    def test_tc_01_12_full_login_capacity_preserves_health_and_retry(self):
        first, payload = self.client()
        second, second_payload = self.client()
        entered, release = threading.Event(), threading.Event()
        def verify(_password, _hash):
            entered.set()
            release.wait(5)
            return True
        with ThreadPoolExecutor(max_workers=1) as runner, patch.object(main, "verify_password", verify):
            future = runner.submit(first.post, "/login", data=payload, follow_redirects=False)
            try:
                self.assertTrue(entered.wait(3))
                self.assertEqual(second.get("/health").status_code, 200)
                response = second.post("/login", data=second_payload, follow_redirects=False)
                self.assertEqual(response.status_code, 503)
                self.assertEqual(response.headers.get("retry-after"), "2")
                self.assertEqual(self.audits(), 0)
                self.assertEqual(second.get("/", follow_redirects=False).status_code, 303)
            finally:
                release.set()
            self.assertEqual(future.result(timeout=3).status_code, 303)
            self.assertEqual(second.post("/login", data=second_payload, follow_redirects=False).status_code, 303)
        self.assertEqual(self.audits(), 2)

    def test_tc_01_13_expired_csrf_after_password_work_has_no_login(self):
        client, payload = self.client()
        old_cookie = client.cookies.get(security.COOKIE_NAME)
        def verify(_password, _hash):
            with security.session_lock:
                security.sessions.pop(old_cookie, None)
            return True
        with patch.object(main, "verify_password", verify):
            self.assertEqual(client.post("/login", data=payload, follow_redirects=False).status_code, 403)
        self.assertEqual(self.audits(), 0)
        self.assertEqual(client.get("/", follow_redirects=False).status_code, 303)

    def test_tc_01_14_failed_audit_never_issues_authenticated_cookie(self):
        client, payload = self.client()
        old_cookie = client.cookies.get(security.COOKIE_NAME)
        with patch.object(main, "audit", side_effect=RuntimeError("Synthetic audit failure")):
            self.assertEqual(client.post("/login", data=payload, follow_redirects=False).status_code, 500)
        self.assertEqual(self.audits(), 0)
        self.assertEqual(client.cookies.get(security.COOKIE_NAME), old_cookie)
        self.assertEqual(client.get("/", follow_redirects=False).status_code, 303)

    def test_tc_01_15_proxy_internal_backend_allowlist_boundaries(self):
        with patch.dict(os.environ, {"HRMS_NATIVE_BACKENDS": '["http://127.0.0.1:19001"]'}):
            proxy = importlib.import_module("app.native_proxy")
        self.assertEqual(proxy.configured_backends('["http://web:8000","http://web4:8000"]', "compose"), ["http://web:8000", "http://web4:8000"])
        self.assertEqual(proxy.configured_backends('["http://127.0.0.1:19001"]'), ["http://127.0.0.1:19001"])
        for urls, mode in (([], "compose"), (["http://web:8000"] * 9, "compose"),
                (["http://example.com:8000"], "compose"), (["http://web:8001"], "compose"),
                (["https://web:8000"], "compose"), (["http://user:password@web:8000"], "compose"),
                (["http://web:8000?x=1"], "compose"), (["http://web:8000"], "native")):
            with self.assertRaises(RuntimeError):
                proxy.configured_backends(json.dumps(urls), mode)
