from __future__ import annotations

import hmac
import os
from contextlib import asynccontextmanager
from urllib.parse import urlparse

import uvicorn
from dotenv import load_dotenv
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from server import AUTH_MODE, OAUTH_PROVIDER, mcp

load_dotenv()


class BearerAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if AUTH_MODE != "bearer" or request.url.path == "/health":
            return await call_next(request)
        expected = os.getenv("DESKTOP_MCP_TOKEN", "")
        if not expected:
            return JSONResponse({"error": "server auth token is not configured"}, status_code=503)
        supplied = request.headers.get("authorization", "")
        if not supplied.startswith("Bearer "):
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        if not hmac.compare_digest(supplied[7:], expected):
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        return await call_next(request)


async def health(_: Request) -> JSONResponse:
    return JSONResponse({
        "ok": True,
        "service": "ownerops-desktop-mcp",
        "auth_mode": AUTH_MODE,
    })


async def oauth_login(request: Request):
    if OAUTH_PROVIDER is None:
        return JSONResponse({"error": "oauth disabled"}, status_code=404)
    return await OAUTH_PROVIDER.login_page(request.query_params.get("state", ""))


async def oauth_callback(request: Request):
    if OAUTH_PROVIDER is None:
        return JSONResponse({"error": "oauth disabled"}, status_code=404)
    return await OAUTH_PROVIDER.login_callback(request)


@asynccontextmanager
async def lifespan(_: Starlette):
    async with mcp.session_manager.run():
        yield


public_base = os.getenv("DESKTOP_MCP_PUBLIC_BASE", "http://127.0.0.1:8765")
public_host = urlparse(public_base).netloc.split(":")[0]
transport_security = TransportSecuritySettings(
    enable_dns_rebinding_protection=True,
    allowed_hosts=[
        "127.0.0.1:*",
        "localhost:*",
        "[::1]:*",
        public_host,
        f"{public_host}:*",
    ],
    allowed_origins=[
        "http://127.0.0.1:*",
        "http://localhost:*",
        "http://[::1]:*",
        public_base,
        f"{public_base}:*",
    ],
)

mcp_app = mcp.streamable_http_app(
    stateless_http=True,
    json_response=True,
    transport_security=transport_security,
)

app = Starlette(
    routes=[
        Route("/health", health),
        Route("/login", oauth_login, methods=["GET"]),
        Route("/login/callback", oauth_callback, methods=["POST"]),
        Mount("/", app=mcp_app),
    ],
    middleware=[Middleware(BearerAuthMiddleware)],
    lifespan=lifespan,
)


if __name__ == "__main__":
    uvicorn.run(
        app,
        host=os.getenv("DESKTOP_MCP_HOST", "127.0.0.1"),
        port=int(os.getenv("DESKTOP_MCP_PORT", "8765")),
    )
