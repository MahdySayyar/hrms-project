"""Explicit proxy: legacy browser affinity or shared-session per-request round robin."""
import json
import os
import asyncio
import logging
from contextlib import asynccontextmanager
from urllib.parse import quote, urlsplit

import aiohttp
from yarl import URL
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

def configured_backends(encoded, mode="native"):
    backends = json.loads(encoded)
    if mode not in {"native", "compose", "shared"} or not isinstance(backends, list) or not 1 <= len(backends) <= 8:
        raise RuntimeError("Choose 1..8 explicit native or Compose proxy backends.")
    for url in backends:
        parsed = urlsplit(url)
        allowed = parsed.hostname == "127.0.0.1" if mode == "native" else (
            parsed.hostname in {"web", *[f"web{i}" for i in range(2, 9)]} and parsed.port == 8000)
        if not allowed or parsed.scheme != "http" or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in {"", "/"}:
            raise RuntimeError("Proxy backend is outside the explicit internal allowlist.")
    return [url.rstrip("/") for url in backends]


PROXY_MODE = os.getenv("HRMS_PROXY_MODE", "native")
BACKENDS = configured_backends(os.environ["HRMS_NATIVE_BACKENDS"], PROXY_MODE)
PROXY_TIMEOUT = int(os.getenv("HRMS_PROXY_TIMEOUT", "30"))
if not 1 <= PROXY_TIMEOUT <= 180:
    raise RuntimeError("HRMS_PROXY_TIMEOUT must be 1..180 seconds.")
AFFINITY_COOKIE = "hrms_affinity"
HOP_HEADERS = {b"connection", b"keep-alive", b"proxy-authenticate", b"proxy-authorization",
               b"te", b"trailer", b"transfer-encoding", b"upgrade", b"content-length"}


@asynccontextmanager
async def lifespan(app):
    async with aiohttp.ClientSession(trust_env=False,
        timeout=aiohttp.ClientTimeout(total=PROXY_TIMEOUT, connect=2),
        connector=(aiohttp.TCPConnector(limit=512, force_close=True) if PROXY_MODE in {"compose", "shared"}
                   else aiohttp.TCPConnector(limit=512, keepalive_timeout=15)),
        cookie_jar=aiohttp.DummyCookieJar(), auto_decompress=False) as client:
        # Pinned aiohttp 3.13.2 retries persistent connections for idempotent methods.
        # Disable that too: this proxy must make only one attempt for every method.
        client._retry_connection = False
        app.state.client = client
        app.state.next_worker = 0
        yield


app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)


def forwarded_headers(raw_headers, *, keep_length=False):
    excluded = HOP_HEADERS.copy()
    if keep_length:
        excluded.remove(b"content-length")
    for key, value in raw_headers:
        if key.lower() == b"connection":
            excluded.update(part.strip().lower() for part in value.split(b","))
    return [(key, value) for key, value in raw_headers if key.lower() not in excluded]


def assignment(request):
    value = request.cookies.get(AFFINITY_COOKIE, "")
    if PROXY_MODE != "shared" and value.isascii() and value.isdigit() and len(value) == 1 and int(value) < len(BACKENDS):
        return int(value), False
    index = request.app.state.next_worker
    request.app.state.next_worker = (index + 1) % len(BACKENDS)
    return index, PROXY_MODE != "shared"


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
        "web_processes": len(BACKENDS), "session_storage": "shared Redis" if PROXY_MODE == "shared" else "process-local with browser affinity"}), index, new)


@app.api_route("/{path:path}", methods=["GET", "POST", "HEAD", "PUT", "PATCH", "DELETE", "OPTIONS"])
async def forward(request: Request, path: str):
    index, new = assignment(request)
    raw_path = request.scope.get("raw_path")
    encoded_path = raw_path.decode("ascii") if raw_path is not None else quote(request.scope["path"])
    query = request.scope["query_string"]
    target = BACKENDS[index] + encoded_path
    if query:
        target += "?" + query.decode("ascii")
    headers = [(key.decode("latin-1"), value.decode("latin-1"))
        for key, value in forwarded_headers(request.headers.raw)]
    try:
        async with request.app.state.client.request(request.method, URL(target, encoded=True), headers=headers,
            data=await request.body(), allow_redirects=False) as backend:
            content = await backend.read()
            status = backend.status
            metadata_only = status != 204 and (request.method == "HEAD" or status == 304)
            response_headers = forwarded_headers(backend.raw_headers, keep_length=metadata_only)
    except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
        logging.getLogger(__name__).warning("Proxy transport failure: method=%s worker=%s error=%s",
            request.method, index, type(exc).__name__)
        response = Response("سامانه موقتاً در دسترس نیست؛ کمی بعد دوباره تلاش کنید.", status_code=503,
            media_type="text/plain; charset=utf-8", headers={"Retry-After": "2", "Cache-Control": "no-store"})
        return affinity(response, index, new)
    response = Response(content, status_code=status)
    response.raw_headers = response_headers
    if not metadata_only and status != 204:
        response.headers["Content-Length"] = str(len(content))
    return affinity(response, index, new)
