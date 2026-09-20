from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

BASE = os.environ["OWNEROPS_PUBLIC_URL"].rstrip("/")
USERNAME = os.environ["OWNEROPS_WEB_USERNAME"]
PASSWORD = os.environ["OWNEROPS_WEB_PASSWORD"]
REDIRECT = os.getenv(
    "OWNEROPS_CHATGPT_REDIRECT",
    "https://chatgpt.com/connector_platform_oauth_redirect",
)
RESOURCE = BASE + "/mcp"

REQUIRED = {
    "get_config",
    "set_config_value",
    "read_file",
    "read_multiple_files",
    "write_file",
    "create_directory",
    "list_directory",
    "move_file",
    "start_search",
    "get_more_search_results",
    "stop_search",
    "list_searches",
    "get_file_info",
    "edit_block",
    "start_process",
    "read_process_output",
    "interact_with_process",
    "force_terminate",
    "list_sessions",
    "list_processes",
    "kill_process",
    "write_pdf",
}


def b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def response_json(response: httpx.Response) -> dict:
    content_type = response.headers.get("content-type", "")
    if "application/json" in content_type:
        return response.json()
    for line in response.text.splitlines():
        if line.startswith("data:"):
            return json.loads(line[5:].strip())
    raise RuntimeError(f"Unexpected response: {response.status_code} {content_type} {response.text[:500]}")


def main() -> int:
    parsed = urlsplit(BASE)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    prefix = parsed.path.rstrip("/")
    as_metadata_url = origin + "/.well-known/oauth-authorization-server" + prefix
    prm_url = origin + "/.well-known/oauth-protected-resource" + prefix + "/mcp"

    client = httpx.Client(timeout=20, follow_redirects=False)

    metadata_response = client.get(as_metadata_url)
    metadata_response.raise_for_status()
    metadata = metadata_response.json()
    assert metadata["issuer"] == BASE
    assert metadata["authorization_response_iss_parameter_supported"] is True
    assert "S256" in metadata["code_challenge_methods_supported"]
    assert "refresh_token" in metadata["grant_types_supported"]
    assert "offline_access" in metadata.get("scopes_supported", [])

    prm_response = client.get(prm_url)
    prm_response.raise_for_status()
    prm = prm_response.json()
    assert prm["resource"] == RESOURCE
    assert BASE in prm["authorization_servers"]

    registration = client.post(
        BASE + "/register",
        json={
            "client_name": "OwnerOps ChatGPT compatibility smoke test",
            "redirect_uris": [REDIRECT],
            "token_endpoint_auth_method": "none",
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
        },
    )
    registration.raise_for_status()
    client_id = registration.json()["client_id"]

    verifier = secrets.token_urlsafe(64)
    challenge = b64url(hashlib.sha256(verifier.encode("ascii")).digest())
    state = secrets.token_urlsafe(20)
    authorize_query = urlencode(
        {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": REDIRECT,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "state": state,
            "resource": RESOURCE,
            "scope": "offline_access",
        }
    )
    authorize_url = BASE + "/authorize?" + authorize_query

    first = client.get(authorize_url)
    assert first.status_code == 302
    login_url = first.headers["location"]
    assert login_url.startswith(BASE + "/login?next=")

    login_page = client.get(login_url)
    login_page.raise_for_status()

    next_path = parse_qs(urlsplit(login_url).query)["next"][0]
    signed_in = client.post(
        BASE + "/login",
        data={
            "username": USERNAME,
            "password": PASSWORD,
            "next": next_path,
        },
    )
    assert signed_in.status_code == 303
    assert signed_in.headers["location"].startswith(BASE + "/authorize?")

    authorized = client.get(signed_in.headers["location"])
    assert authorized.status_code == 302
    callback = authorized.headers["location"]
    callback_parts = urlsplit(callback)
    assert callback.startswith(REDIRECT + "?")
    callback_query = parse_qs(callback_parts.query)
    assert callback_query["state"][0] == state
    assert callback_query["iss"][0] == BASE
    code = callback_query["code"][0]

    token_response = client.post(
        BASE + "/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "client_id": client_id,
            "redirect_uri": REDIRECT,
            "code_verifier": verifier,
            "resource": RESOURCE,
        },
    )
    token_response.raise_for_status()
    token = token_response.json()
    assert token.get("access_token")
    assert token.get("refresh_token")
    assert "offline_access" in token.get("scope", "")

    mcp_headers = {
        "Authorization": "Bearer " + token["access_token"],
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
    }
    initialized = client.post(
        RESOURCE,
        headers=mcp_headers,
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "ownerops-chatgpt-smoke", "version": "0.4.0"},
            },
        },
    )
    initialized.raise_for_status()
    session_id = initialized.headers.get("mcp-session-id")
    if not session_id:
        raise RuntimeError("Mcp-Session-Id missing")

    session_headers = {
        **mcp_headers,
        "Mcp-Session-Id": session_id,
        "MCP-Protocol-Version": "2025-06-18",
    }
    client.post(
        RESOURCE,
        headers=session_headers,
        json={"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
    )

    tools_response = client.post(
        RESOURCE,
        headers=session_headers,
        json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
    )
    tools_response.raise_for_status()
    tools_payload = response_json(tools_response)
    names = {item["name"] for item in tools_payload["result"]["tools"]}
    missing = sorted(REQUIRED - names)
    if missing:
        raise RuntimeError("Missing Desktop Commander tools: " + ", ".join(missing))

    refreshed = client.post(
        BASE + "/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": token["refresh_token"],
            "client_id": client_id,
            "resource": RESOURCE,
        },
    )
    refreshed.raise_for_status()
    refreshed_token = refreshed.json()
    assert refreshed_token.get("access_token")
    assert refreshed_token.get("refresh_token")

    print(f"ChatGPT-style OAuth smoke PASS: {len(names)} tools exposed")
    print("OAuth: DCR + PKCE S256 + iss + resource + refresh token PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise
