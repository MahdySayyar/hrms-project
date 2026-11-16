"""Local native capacity experiment: async proxy with browser affinity, not HA."""
import json
import os
import asyncio
from contextlib import asynccontextmanager
from urllib.parse import urlsplit

import aiohttp
from yarl import URL
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

BACKENDS = json.loads(os.environ["HRMS_NATIVE_BACKENDS"])
if not 1 <= len(BACKENDS) <= 8 or any(urlsplit(url).hostname != "127.0.0.1" for url in BACKENDS):
    raise RuntimeError("Native proxy backends must be 1..8 explicitly configured localhost URLs.")
AFFINITY_COOKIE = "hrms_affinity"
HOP_HEADERS = {b"connection", b"keep-alive", b"proxy-authenticate", b"proxy-authorization",
               b"te", b"trailer", b"transfer-encoding", b"upgrade", b"content-length"}


@asynccontextmanager
async def lifespan(app):
    async with aiohttp.ClientSession(trust_env=False,
        timeout=aiohttp.ClientTimeout(total=30, connect=2),
        connector=aiohttp.TCPConnector(limit=512, keepalive_timeout=15),
        cookie_jar=aiohttp.DummyCookieJar(), auto_decompress=False) as client:
        # Pinned aiohttp 3.13.2 retries persistent connections for idempotent methods.
        # Disable that too: this proxy must make only one attempt for every method.
        client._retry_connection = False
        app.state.client = client
        app.state.next_worker = 0
        yield


app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)


def forwarded_headers(raw_headers):
    excluded = HOP_HEADERS.copy()
    for key, value in raw_headers:
        if key.lower() == b"connection":
            excluded.update(part.strip().lower() for part in value.split(b","))
    return [(key, value) for key, value in raw_headers if key.lower() not in excluded]


def assignment(request):
    value = request.cookies.get(AFFINITY_COOKIE, "")
    if value.isascii() and value.isdigit() and len(value) == 1 and int(value) < len(BACKENDS):
        return int(value), False
    index = request.app.state.next_worker
    request.app.state.next_worker = (index + 1) % len(BACKENDS)
    return index, True


def affinity(response, index, new):
    response.headers["X-HRMS-Worker"] = str(index)
    if new:
        response.set_cookie(AFFINITY_COOKIE, str(index), httponly=True, samesite="lax", path="/",
            secure=os.getenv("COOKIE_SECURE", "false").lower() == "true")
    return response


@app.get("/instance")
async def instance(request: Request):
    index, new = assignment(request)
    return affinity(JSONResponse({"instance": os.getenv("INSTANCE_ID", "hrms-local-1"),
        "web_processes": len(BACKENDS), "session_storage": "process-local with browser affinity"}), index, new)


@app.api_route("/{path:path}", methods=["GET", "POST", "HEAD", "PUT", "PATCH", "DELETE", "OPTIONS"])
async def forward(request: Request, path: str):
    index, new = assignment(request)
    target = BACKENDS[index] + request.url.path
    if request.url.query:
        target += "?" + request.url.query
    headers = [(key.decode("latin-1"), value.decode("latin-1"))
        for key, value in forwarded_headers(request.headers.raw)]
    try:
        async with request.app.state.client.request(request.method, URL(target, encoded=True), headers=headers,
            data=await request.body(), allow_redirects=False) as backend:
            content = await backend.read()
            status = backend.status
            response_headers = forwarded_headers(backend.raw_headers)
    except (aiohttp.ClientError, asyncio.TimeoutError):
        response = Response("سامانه موقتاً در دسترس نیست؛ کمی بعد دوباره تلاش کنید.", status_code=503,
            media_type="text/plain; charset=utf-8", headers={"Retry-After": "2", "Cache-Control": "no-store"})
        return affinity(response, index, new)
    response = Response(content, status_code=status)
    # Preserve separate cookies and encoded bytes, with a newly calculated length.
    response.raw_headers = response_headers
    response.headers["Content-Length"] = str(len(content))
    return affinity(response, index, new)
