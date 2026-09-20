from __future__ import annotations

import hmac
import html
import secrets
import time
from urllib.parse import quote

from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    OAuthAuthorizationServerProvider,
    RefreshToken,
    construct_redirect_uri,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken
from pydantic import AnyHttpUrl
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse, Response


class OwnerOAuthProvider(
    OAuthAuthorizationServerProvider[AuthorizationCode, RefreshToken, AccessToken]
):
    """Single-user OAuth provider for a self-hosted personal MCP."""

    def __init__(
        self,
        *,
        username: str,
        password: str,
        public_base_url: str,
        resource_url: str,
        scope: str = "desktop",
        access_ttl: int = 3600,
        refresh_ttl: int = 30 * 24 * 3600,
    ) -> None:
        if not username or not password:
            raise ValueError("OAuth username/password must be configured.")
        self.username = username
        self.password = password
        self.public_base_url = public_base_url.rstrip("/")
        self.resource_url = resource_url
        self.scope = scope
        self.access_ttl = access_ttl
        self.refresh_ttl = refresh_ttl
        self.clients: dict[str, OAuthClientInformationFull] = {}
        self.auth_codes: dict[str, AuthorizationCode] = {}
        self.access_tokens: dict[str, AccessToken] = {}
        self.refresh_tokens: dict[str, RefreshToken] = {}
        self.pending: dict[str, dict[str, object]] = {}

    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        return self.clients.get(client_id)

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        if not client_info.client_id:
            raise ValueError("client_id is required")
        self.clients[client_info.client_id] = client_info

    async def authorize(
        self,
        client: OAuthClientInformationFull,
        params: AuthorizationParams,
    ) -> str:
        if not client.client_id:
            raise ValueError("client_id is required")
        state = params.state or secrets.token_urlsafe(24)
        self.pending[state] = {
            "client_id": client.client_id,
            "redirect_uri": str(params.redirect_uri),
            "redirect_uri_provided_explicitly": params.redirect_uri_provided_explicitly,
            "code_challenge": params.code_challenge,
            "scopes": params.scopes or [self.scope, "offline_access"],
            "resource": params.resource or self.resource_url,
        }
        return f"{self.public_base_url}/login?state={quote(state)}"

    async def login_page(self, state: str) -> HTMLResponse:
        if not state or state not in self.pending:
            raise HTTPException(400, "Invalid or expired OAuth state.")
        safe_state = html.escape(state, quote=True)
        action = html.escape(f"{self.public_base_url}/login/callback", quote=True)
        body = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>OwnerOps Desktop</title></head>
<body style="font-family:system-ui;max-width:420px;margin:48px auto;padding:0 20px">
<h2>Authorize OwnerOps Desktop</h2>
<p>Sign in to allow this MCP client to access the configured desktop tools.</p>
<form method="post" action="{action}">
<input type="hidden" name="state" value="{safe_state}">
<label>Username</label><br>
<input name="username" autocomplete="username" required style="width:100%;padding:8px"><br><br>
<label>Password</label><br>
<input type="password" name="password" autocomplete="current-password" required
 style="width:100%;padding:8px"><br><br>
<button type="submit" style="padding:10px 16px">Authorize</button>
</form></body></html>"""
        return HTMLResponse(body)

    async def login_callback(self, request: Request) -> Response:
        form = await request.form()
        username = form.get("username")
        password = form.get("password")
        state = form.get("state")
        if not all(isinstance(v, str) for v in (username, password, state)):
            raise HTTPException(400, "Missing login fields.")
        assert isinstance(username, str)
        assert isinstance(password, str)
        assert isinstance(state, str)
        pending = self.pending.get(state)
        if pending is None:
            raise HTTPException(400, "Invalid or expired OAuth state.")
        if not (
            hmac.compare_digest(username, self.username)
            and hmac.compare_digest(password, self.password)
        ):
            raise HTTPException(401, "Invalid credentials.")

        code = "oc_" + secrets.token_urlsafe(32)
        auth_code = AuthorizationCode(
            code=code,
            scopes=list(pending["scopes"]),
            expires_at=time.time() + 300,
            client_id=str(pending["client_id"]),
            code_challenge=str(pending["code_challenge"]),
            redirect_uri=AnyHttpUrl(str(pending["redirect_uri"])),
            redirect_uri_provided_explicitly=bool(
                pending["redirect_uri_provided_explicitly"]
            ),
            resource=str(pending["resource"]),
            subject=self.username,
        )
        self.auth_codes[code] = auth_code
        self.pending.pop(state, None)
        target = construct_redirect_uri(
            str(auth_code.redirect_uri),
            code=code,
            state=state,
        )
        return RedirectResponse(target, status_code=302)

    async def load_authorization_code(
        self,
        client: OAuthClientInformationFull,
        authorization_code: str,
    ) -> AuthorizationCode | None:
        code = self.auth_codes.get(authorization_code)
        if code and code.expires_at >= time.time() and code.client_id == client.client_id:
            return code
        return None

    def _issue_access_token(
        self,
        client_id: str,
        scopes: list[str],
        resource: str | None,
        subject: str | None,
    ) -> AccessToken:
        raw = "oa_" + secrets.token_urlsafe(48)
        token = AccessToken(
            token=raw,
            client_id=client_id,
            scopes=scopes,
            expires_at=int(time.time()) + self.access_ttl,
            resource=resource or self.resource_url,
            subject=subject,
        )
        self.access_tokens[raw] = token
        return token

    def _issue_refresh_token(
        self,
        client_id: str,
        scopes: list[str],
        resource: str | None,
        subject: str | None,
    ) -> RefreshToken:
        raw = "or_" + secrets.token_urlsafe(48)
        token = RefreshToken(
            token=raw,
            client_id=client_id,
            scopes=scopes,
            expires_at=int(time.time()) + self.refresh_ttl,
            resource=resource or self.resource_url,
            subject=subject,
        )
        self.refresh_tokens[raw] = token
        return token

    async def exchange_authorization_code(
        self,
        client: OAuthClientInformationFull,
        authorization_code: AuthorizationCode,
    ) -> OAuthToken:
        if not client.client_id or authorization_code.client_id != client.client_id:
            raise ValueError("Invalid OAuth client.")
        stored = self.auth_codes.pop(authorization_code.code, None)
        if stored is None or stored.expires_at < time.time():
            raise ValueError("Authorization code is invalid or expired.")

        access = self._issue_access_token(
            client.client_id,
            stored.scopes,
            stored.resource,
            stored.subject,
        )
        refresh = self._issue_refresh_token(
            client.client_id,
            stored.scopes,
            stored.resource,
            stored.subject,
        )
        return OAuthToken(
            access_token=access.token,
            token_type="Bearer",
            expires_in=self.access_ttl,
            scope=" ".join(stored.scopes),
            refresh_token=refresh.token,
        )

    async def load_access_token(self, token: str) -> AccessToken | None:
        item = self.access_tokens.get(token)
        if item and (item.expires_at is None or item.expires_at >= time.time()):
            return item
        self.access_tokens.pop(token, None)
        return None

    async def load_refresh_token(
        self,
        client: OAuthClientInformationFull,
        refresh_token: str,
    ) -> RefreshToken | None:
        item = self.refresh_tokens.get(refresh_token)
        if item is None or item.client_id != client.client_id:
            return None
        if item.expires_at is not None and item.expires_at < time.time():
            self.refresh_tokens.pop(refresh_token, None)
            return None
        return item

    async def exchange_refresh_token(
        self,
        client: OAuthClientInformationFull,
        refresh_token: RefreshToken,
        scopes: list[str],
    ) -> OAuthToken:
        if not client.client_id or refresh_token.client_id != client.client_id:
            raise ValueError("Invalid OAuth client.")
        requested = scopes or refresh_token.scopes
        if not set(requested).issubset(set(refresh_token.scopes)):
            raise ValueError("Requested scope exceeds the refresh token scope.")

        self.refresh_tokens.pop(refresh_token.token, None)
        access = self._issue_access_token(
            client.client_id,
            requested,
            refresh_token.resource,
            refresh_token.subject,
        )
        rotated = self._issue_refresh_token(
            client.client_id,
            requested,
            refresh_token.resource,
            refresh_token.subject,
        )
        return OAuthToken(
            access_token=access.token,
            token_type="Bearer",
            expires_in=self.access_ttl,
            scope=" ".join(requested),
            refresh_token=rotated.token,
        )

    async def revoke_token(self, token: AccessToken | RefreshToken) -> None:
        self.access_tokens.pop(token.token, None)
        self.refresh_tokens.pop(token.token, None)
