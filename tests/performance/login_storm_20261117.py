"""One synchronized valid-login burst with independent cookies and live-site probes."""
import asyncio
import json
import math
import random
import re
import time
from collections import Counter

import aiohttp


def summarize(rows):
    durations = sorted(item["duration_ms"] for item in rows)
    return {"requests": len(rows), "failures": sum(not item["passed"] for item in rows),
            "statuses": dict(Counter(str(item["status"]) for item in rows)),
            "p50_ms": durations[max(0, math.ceil(len(rows) * .5) - 1)] if rows else None,
            "p95_ms": durations[max(0, math.ceil(len(rows) * .95) - 1)] if rows else None,
            "max_ms": durations[-1] if rows else None}


async def measure(base_url, users, password, marker, timeout=180):
    connector = aiohttp.TCPConnector(limit=0, force_close=True)
    clients = [aiohttp.ClientSession(connector=connector, connector_owner=False,
               cookie_jar=aiohttp.CookieJar(unsafe=True), trust_env=False) for _ in range(users + 1)]
    finished = asyncio.Event()
    login_rows, probe_rows = [], []
    started = time.monotonic()

    async def request(client, method, path, name, expected=200, deadline=10, **kwargs):
        now = time.monotonic()
        status, body, worker, error = None, "", None, None
        try:
            async with client.request(method, base_url + path, allow_redirects=False,
                    timeout=aiohttp.ClientTimeout(total=deadline), **kwargs) as response:
                status = response.status
                worker = response.headers.get("X-HRMS-Worker")
                body = await response.text()
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            error = type(exc).__name__
        return {"name": name, "started_offset_ms": round((now - started) * 1000, 2),
                "duration_ms": round((time.monotonic() - now) * 1000, 2), "status": status, "passed": status == expected, "worker": worker, "error_type": error}, body

    async def form(client):
        row, body = await request(client, "GET", "/login", "prepare.form", deadline=30)
        token = re.search(r'name="csrf_token" value="([^"]+)"', body)
        if not row["passed"] or not token:
            raise RuntimeError("A synthetic login form was unavailable")
        return token.group(1)

    async def login(index, token):
        row, _ = await request(clients[index], "POST", "/login", "login", expected=303, deadline=timeout,
                data={"username": f"capacity-{index:04d}", "password": password, "csrf_token": token})
        row["client_index"] = index
        login_rows.append(row)

    async def probes():
        while not finished.is_set():
            for path in ("/health", "/"):
                row, _ = await request(clients[-1], "GET", path, "probe.health" if path == "/health" else "probe.dashboard", deadline=2)
                probe_rows.append(row)
            await asyncio.sleep(.2)

    try:
        row, body = await request(clients[-1], "GET", "/instance", "marker")
        if not row["passed"] or json.loads(body).get("instance") != marker:
            raise RuntimeError("Refusing load against an unverified lab target")
        observer_token = await form(clients[-1])
        row, _ = await request(clients[-1], "POST", "/login", "observer.login", expected=303, deadline=30,
            data={"username": f"capacity-{users:04d}", "password": password, "csrf_token": observer_token})
        if not row["passed"]:
            raise RuntimeError("The independent observer did not authenticate")
        tokens = await asyncio.gather(*(form(client) for client in clients[:-1]))
        # All forms are ready. Tasks begin on the same event-loop turn; actual dispatch spread is recorded.
        begin = time.monotonic()
        probe_task = asyncio.create_task(probes())
        try:
            await asyncio.gather(*(login(i, token) for i, token in enumerate(tokens)))
        finally:
            finished.set()
            await probe_task
        end = time.monotonic()
        async def session_check(index):
            row, body = await request(clients[index], "GET", "/", "verify.session", deadline=30)
            row["passed"] = row["passed"] and 'id="username"' not in body and f"حساب آزمایش {index:04d}" in body
            return row
        session_rows = await asyncio.gather(*(session_check(i) for i in range(users)))
        offsets = [row["started_offset_ms"] for row in login_rows]
        cookies = [next((cookie.value for cookie in client.cookie_jar if cookie.key == "hrms_session"), None) for client in clients[:-1]]
        return {"users": users, "prepared_cookie_csrf_pairs": len(tokens), "unique_authenticated_cookies": len(set(cookies) - {None}), "login": summarize(login_rows),
                "dispatch_spread_ms": round(max(offsets) - min(offsets), 2), "burst_elapsed_seconds": round(end - begin, 3),
                "probes": summarize(probe_rows), "health_probes": summarize([r for r in probe_rows if r["name"] == "probe.health"]),
                "dashboard_probes": summarize([r for r in probe_rows if r["name"] == "probe.dashboard"]),
                "session_checks": summarize(session_rows), "workers_observed": dict(Counter(str(r["worker"]) for r in login_rows)),
                "raw_login_rows": login_rows, "raw_probe_rows": probe_rows,
                "login_request_timeout_seconds": timeout, "probe_timeout_seconds": 2}
    finally:
        await asyncio.gather(*(client.close() for client in clients))
        await connector.close()
