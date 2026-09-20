from __future__ import annotations

import hmac
import os
from contextlib import asynccontextmanager

import uvicorn
from dotenv import load_dotenv
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from server import mcp

load_dotenv()


class BearerAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path == "/health":
            return await call_next(request)
        mode = os.getenv("DESKTOP_MCP_AUTH_MODE", "bearer").lower()
        if mode == "none":
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
    return JSONResponse({"ok": True, "service": "ownerops-desktop-mcp"})


@asynccontextmanager
async def lifespan(_: Starlette):
    async with mcp.session_manager.run():
        yield


app = Starlette(
    routes=[Route("/health", health), Mount("/", app=mcp.streamable_http_app(stateless_http=True, json_response=True))],
    middleware=[Middleware(BearerAuthMiddleware)],
    lifespan=lifespan,
)


if __name__ == "__main__":
    uvicorn.run(
        app,
        host=os.getenv("DESKTOP_MCP_HOST", "127.0.0.1"),
        port=int(os.getenv("DESKTOP_MCP_PORT", "8765")),
    )
