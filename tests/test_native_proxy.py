"""Native proxy contracts over real HTTP using disposable localhost servers."""
import gzip
import importlib
import os
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest import TestCase
from unittest.mock import patch

import aiohttp
from fastapi.testclient import TestClient


@contextmanager
def upstream(handler):
    calls = []
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        def handle_request(self):
            body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            calls.append({"method": self.command, "path": self.path,
                "headers": {key.lower(): value for key, value in self.headers.items()}, "body": body})
            result = handler(calls[-1])
            if result is None:
                self.close_connection = True
                self.connection.close()
                return
            status, headers, data = result
            self.send_response(status)
            for key, value in headers:
                self.send_header(key, value)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(data)
        do_GET = do_POST = do_DELETE = do_HEAD = handle_request
        def log_message(self, *_):
            pass
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", calls
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


class NativeProxyContracts(TestCase):
    @classmethod
    def setUpClass(cls):
        with patch.dict(os.environ, {"HRMS_NATIVE_BACKENDS": '["http://127.0.0.1:19001","http://127.0.0.1:19002"]'}):
            cls.proxy = importlib.import_module("app.native_proxy")

    def test_tc_01_05_affinity_and_upstream_cookies_are_preserved(self):
        def handler(_):
            return 200, [("Set-Cookie", "hrms_session=opaque-test; Path=/; HttpOnly; SameSite=Lax"),
                ("Set-Cookie", "second_test=value; Path=/")], "ساختگی".encode()
        with upstream(handler) as (first_url, first_calls), upstream(handler) as (second_url, second_calls), \
             patch.object(self.proxy, "BACKENDS", [first_url, second_url]), TestClient(self.proxy.app) as client:
            first = client.get("/instance")
            worker = first.headers["X-HRMS-Worker"]
            self.assertIn("httponly", first.headers["set-cookie"].lower())
            self.assertEqual(client.get("/login").headers["X-HRMS-Worker"], worker)
            response = client.post("/hr/leave/new?synthetic=%2F%26", data={"synthetic": "value"})
            self.assertEqual(response.headers["X-HRMS-Worker"], worker)
            self.assertEqual(len(response.headers.get_list("set-cookie")), 2)
            calls = first_calls if worker == "0" else second_calls
            self.assertEqual(len(second_calls if worker == "0" else first_calls), 0)
            self.assertEqual(client.cookies.get("hrms_session"), "opaque-test")
            self.assertIn("hrms_session=opaque-test", calls[-1]["headers"]["cookie"])
            self.assertEqual(calls[-1]["body"], b"synthetic=value")
            self.assertEqual(calls[-1]["path"], "/hr/leave/new?synthetic=%2F%26")
            self.assertIsInstance(self.proxy.app.state.client.cookie_jar, aiohttp.DummyCookieJar)
            client.cookies.clear()
            client.get("/login", headers={"Cookie": f"hrms_affinity={worker}"})
            self.assertNotIn("hrms_session", calls[-1]["headers"].get("cookie", ""))

    def test_tc_01_06_failed_mutation_is_not_retried(self):
        with upstream(lambda _: None) as (url, calls), patch.object(self.proxy, "BACKENDS", [url]), \
             TestClient(self.proxy.app) as client:
            self.assertFalse(self.proxy.app.state.client._retry_connection)
            for method in ("POST", "DELETE"):
                count = len(calls)
                response = client.request(method, "/hr/leave/new", content=b"synthetic=value")
                self.assertEqual(response.status_code, 503)
                self.assertEqual(len(calls), count + 1)
                self.assertIn("موقتاً", response.text)
                self.assertEqual(response.headers["Retry-After"], "2")
                self.assertEqual(response.headers["Cache-Control"], "no-store")

    def test_tc_01_07_encoding_connection_headers_and_redirect_boundary(self):
        content = gzip.compress("ساختگی".encode())
        def handler(call):
            if call["path"] == "/redirect":
                return 303, [("Location", "/must-not-follow")], b""
            return 200, [("Content-Encoding", "gzip"), ("Connection", "X-Upstream-Private"),
                ("X-Upstream-Private", "remove")], content
        with upstream(handler) as (url, calls), patch.object(self.proxy, "BACKENDS", [url]), \
             TestClient(self.proxy.app) as client:
            response = client.get("/encoded", headers={"Connection": "X-Request-Private", "X-Request-Private": "remove"})
            self.assertEqual(response.content, "ساختگی".encode())
            self.assertEqual(response.headers["Content-Encoding"], "gzip")
            self.assertEqual(int(response.headers["Content-Length"]), len(content))
            self.assertNotIn("x-upstream-private", response.headers)
            self.assertNotIn("x-request-private", calls[0]["headers"])
            count = len(calls)
            response = client.post("/redirect", follow_redirects=False)
            self.assertEqual(response.status_code, 303)
            self.assertEqual(response.headers["Location"], "/must-not-follow")
            self.assertEqual(len(calls), count + 1)
            client.cookies.set("hrms_affinity", "9")
            self.assertEqual(client.get("/instance").headers["X-HRMS-Worker"], "0")
