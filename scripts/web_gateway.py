from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import html
import json
import os
import subprocess
import time
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import parse_qs, quote, urlsplit

import httpx
import uvicorn
from dotenv import load_dotenv
from starlette.applications import Starlette
from starlette.background import BackgroundTask
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse, Response, StreamingResponse
from starlette.routing import Route

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

PUBLIC_URL = os.environ["OWNEROPS_PUBLIC_URL"].rstrip("/")
PUBLIC_PATH = urlsplit(PUBLIC_URL).path.rstrip("/")
PROXY_HOST = os.getenv("OWNEROPS_PROXY_HOST", "127.0.0.1")
PROXY_PORT = int(os.getenv("OWNEROPS_PROXY_PORT", "8765"))
BACKEND_HOST = os.getenv("OWNEROPS_BACKEND_HOST", "127.0.0.1")
BACKEND_PORT = int(os.getenv("OWNEROPS_BACKEND_PORT", "8766"))
USERNAME = os.environ["OWNEROPS_WEB_USERNAME"]
PASSWORD = os.environ["OWNEROPS_WEB_PASSWORD"]
COOKIE_SECRET = os.environ["OWNEROPS_WEB_COOKIE_SECRET"].encode("utf-8")
TOKEN_STORE = ROOT / os.getenv("OWNEROPS_OAUTH_TOKEN_STORE", "runtime/oauth-state.json")
CHATGPT_REDIRECT = os.getenv(
    "OWNEROPS_CHATGPT_REDIRECT",
    "https://chatgpt.com/connector_platform_oauth_redirect",
)
TRUSTED_USER_HEADER = "X-OwnerOps-User"
COOKIE_NAME = "ownerops_web_session"
COOKIE_TTL = 15 * 60
BACKEND_ORIGIN = f"http://{BACKEND_HOST}:{BACKEND_PORT}"

HOP_BY_HOP = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}


def _cookie_value(username: str) -> str:
    expires = int(time.time()) + COOKIE_TTL
    payload = f"{username}|{expires}".encode("utf-8")
    encoded = base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")
    signature = hmac.new(COOKIE_SECRET, encoded.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{encoded}.{signature}"


def _cookie_user(value: str | None) -> str | None:
    if not value or "." not in value:
        return None
    encoded, signature = value.rsplit(".", 1)
    expected = hmac.new(COOKIE_SECRET, encoded.encode("ascii"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return None
    try:
        padded = encoded + "=" * (-len(encoded) % 4)
        raw = base64.urlsafe_b64decode(padded).decode("utf-8")
        username, expires_text = raw.rsplit("|", 1)
        if int(expires_text) < int(time.time()):
            return None
        if not hmac.compare_digest(username, USERNAME):
            return None
        return username
    except (ValueError, UnicodeDecodeError):
        return None


def _valid_next(value: str) -> bool:
    return value.startswith("/authorize?") and "\r" not in value and "\n" not in value


def _login_html(next_path: str, *, error: str = "") -> str:
    escaped_next = html.escape(next_path, quote=True)
    escaped_action = html.escape(PUBLIC_URL + "/login", quote=True)
    error_html = (
        f'<p style="color:#b42318">{html.escape(error)}</p>'
        if error
        else ""
    )
    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>OwnerOps Desktop authorization</title>
<style>
body {{ font-family: system-ui, sans-serif; max-width: 430px; margin: 64px auto; padding: 0 20px; }}
input {{ box-sizing: border-box; width: 100%; padding: 10px; margin: 6px 0 16px; }}
button {{ padding: 10px 16px; cursor: pointer; }}
small {{ color: #666; }}
</style>
</head>
<body>
<h2>OwnerOps Desktop</h2>
<p>Authorize ChatGPT to use the configured Desktop Commander tools on this PC.</p>
{error_html}
<form method="post" action="{escaped_action}">
<input type="hidden" name="next" value="{escaped_next}">
<label>Username</label>
<input name="username" autocomplete="username" required>
<label>Password</label>
<input type="password" name="password" autocomplete="current-password" required>
<button type="submit">Authorize</button>
</form>
<p><small>This login only authorizes the local OwnerOps MCP gateway.</small></p>
</body>
</html>"""


async def login_get(request: Request) -> Response:
    next_path = request.query_params.get("next", "")
    if not _valid_next(next_path):
        return JSONResponse({"error": "invalid authorization continuation"}, status_code=400)
    return HTMLResponse(
        _login_html(next_path),
        headers={"Cache-Control": "no-store"},
    )


async def login_post(request: Request) -> Response:
    raw = (await request.body()).decode("utf-8", errors="replace")
    form = {key: values[0] for key, values in parse_qs(raw, keep_blank_values=True).items()}
    next_path = form.get("next", "")
    username = form.get("username", "")
    password = form.get("password", "")

    if not _valid_next(next_path):
        return JSONResponse({"error": "invalid authorization continuation"}, status_code=400)

    if not (
        hmac.compare_digest(username, USERNAME)
        and hmac.compare_digest(password, PASSWORD)
    ):
        return HTMLResponse(
            _login_html(next_path, error="Invalid credentials."),
            status_code=401,
            headers={"Cache-Control": "no-store"},
        )

    response = RedirectResponse(PUBLIC_URL + next_path, status_code=303)
    response.set_cookie(
        COOKIE_NAME,
        _cookie_value(username),
        max_age=COOKIE_TTL,
        path=PUBLIC_PATH or "/",
        secure=True,
        httponly=True,
        samesite="lax",
    )
    return response


def _backend_path(local_path: str) -> str:
    if local_path.startswith("/.well-known/"):
        return local_path
    return (PUBLIC_PATH or "") + local_path


def _outbound_headers(request: Request) -> dict[str, str]:
    headers: dict[str, str] = {}
    for key, value in request.headers.items():
        lower = key.lower()
        if lower in HOP_BY_HOP or lower in {
            "host",
            "content-length",
            "cookie",
            TRUSTED_USER_HEADER.lower(),
        }:
            continue
        headers[key] = value
    headers["X-Forwarded-Proto"] = "https"
    headers["X-Forwarded-Host"] = urlsplit(PUBLIC_URL).netloc
    return headers


async def _close_response(response: httpx.Response) -> None:
    await response.aclose()


async def proxy(request: Request) -> Response:
    local_path = request.url.path
    query = request.url.query

    if local_path == "/authorize":
        user = _cookie_user(request.cookies.get(COOKIE_NAME))
        if user is None:
            continuation = local_path + (f"?{query}" if query else "")
            return RedirectResponse(
                PUBLIC_URL + "/login?next=" + quote(continuation, safe=""),
                status_code=302,
            )

    backend_path = _backend_path(local_path)
    backend_url = BACKEND_ORIGIN + backend_path + (f"?{query}" if query else "")
    headers = _outbound_headers(request)

    if local_path == "/authorize":
        headers[TRUSTED_USER_HEADER] = USERNAME

    body = await request.body()
    client: httpx.AsyncClient = request.app.state.http
    outbound = client.build_request(
        request.method,
        backend_url,
        headers=headers,
        content=body,
    )
    upstream = await client.send(outbound, stream=True)

    response_headers: dict[str, str] = {}
    for key, value in upstream.headers.items():
        lower = key.lower()
        if lower in HOP_BY_HOP or lower == "content-length":
            continue
        response_headers[key] = value

    if local_path.startswith("/.well-known/oauth-authorization-server") and upstream.status_code == 200:
        content = await upstream.aread()
        await upstream.aclose()
        metadata = json.loads(content)
        scopes = list(metadata.get("scopes_supported") or [])
        if "offline_access" not in scopes:
            scopes.append("offline_access")
        metadata["scopes_supported"] = scopes
        return JSONResponse(
            metadata,
            status_code=200,
            headers={k: v for k, v in response_headers.items() if k.lower() != "content-type"},
        )

    async def iterator():
        async for chunk in upstream.aiter_raw():
            yield chunk

    return StreamingResponse(
        iterator(),
        status_code=upstream.status_code,
        headers=response_headers,
        background=BackgroundTask(_close_response, upstream),
    )


def _backend_command() -> list[str]:
    executable = ROOT / ".venv" / "Scripts" / "mcp-stdio.exe"
    proxy = Path.home() / ".dotnet" / "tools" / "mcpproxy.exe"
    proxy_config = ROOT / "config" / "mcp-proxy.json"
    return [
        str(executable),
        "serve",
        "--enable-oauth",
        "--public-url",
        PUBLIC_URL,
        "--trusted-user-header",
        TRUSTED_USER_HEADER,
        "--allow-redirect-uri",
        CHATGPT_REDIRECT,
        "--token-store",
        str(TOKEN_STORE),
        "--host",
        BACKEND_HOST,
        "--port",
        str(BACKEND_PORT),
        "--max-sessions",
        "4",
        "--max-sessions-per-owner",
        "1",
        "--session-idle-ttl",
        "900",
        "--",
        str(proxy),
        "-t",
        "stdio",
        "-c",
        str(proxy_config),
    ]


async def _wait_backend() -> None:
    url = BACKEND_ORIGIN + "/.well-known/oauth-authorization-server" + PUBLIC_PATH
    deadline = time.monotonic() + 20
    async with httpx.AsyncClient(timeout=1) as client:
        while time.monotonic() < deadline:
            try:
                response = await client.get(url)
                if response.status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            await asyncio.sleep(0.25)
    raise RuntimeError("OAuth backend did not become ready")


@asynccontextmanager
async def lifespan(app: Starlette):
    runtime = ROOT / "runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    TOKEN_STORE.parent.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    runtime_home = ROOT / "runtime" / "home"
    env["USERPROFILE"] = str(runtime_home)
    env["HOME"] = str(runtime_home)
    env["DESKTOP_COMMANDER_DISABLE_TELEMETRY"] = "1"
    env["DOTNET_CLI_TELEMETRY_OPTOUT"] = "1"

    # Node child_process.spawn resolves powershell.exe through PATH. Some ChatGPT/
    # Desktop Commander launch environments omit the Windows PowerShell directory,
    # even though System32 itself is present. Repair it for every upstream child.
    powershell_dir = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "WindowsPowerShell" / "v1.0"
    system32_dir = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32"
    inherited_path = env.get("PATH", "")
    env["PATH"] = os.pathsep.join(
        [str(powershell_dir), str(system32_dir), inherited_path]
    )

    backend_log = open(runtime / "oauth-backend.log", "a", encoding="utf-8")
    backend = subprocess.Popen(
        _backend_command(),
        cwd=ROOT,
        env=env,
        stdout=backend_log,
        stderr=subprocess.STDOUT,
        text=True,
    )
    app.state.backend = backend
    app.state.backend_log = backend_log
    app.state.http = httpx.AsyncClient(timeout=None)

    try:
        await _wait_backend()
        yield
    finally:
        await app.state.http.aclose()
        if backend.poll() is None:
            backend.terminate()
            try:
                backend.wait(timeout=5)
            except subprocess.TimeoutExpired:
                backend.kill()
        backend_log.close()


app = Starlette(
    routes=[
        Route("/login", login_get, methods=["GET"]),
        Route("/login", login_post, methods=["POST"]),
        Route("/{path:path}", proxy, methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]),
    ],
    lifespan=lifespan,
)


if __name__ == "__main__":
    uvicorn.run(app, host=PROXY_HOST, port=PROXY_PORT)
