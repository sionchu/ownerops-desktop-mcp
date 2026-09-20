# OwnerOps Desktop MCP

Self-hosted ChatGPT access to the **official Desktop Commander MCP engine**.

The project does not reimplement Desktop Commander's filesystem, terminal, process, search, edit, or document tools.
It pins the upstream engine and provides isolated local stdio plus a ChatGPT-web-compatible OAuth gateway.

## Architecture

```text
Local ChatGPT Desktop / Codex
           |
          stdio
           |
Official Desktop Commander MCP
           |
        Windows PC

ChatGPT Web
    |
HTTPS / OAuth 2.1 + PKCE
    |
Tailscale Funnel
    |
OwnerOps login proxy
    |
mcp-stdio OAuth gateway
    |
   stdio
    |
Official Desktop Commander MCP
    |
 Windows PC
```

## Pinned components

- `@wonderwhy-er/desktop-commander@0.2.51`
- `mcp-stdio==0.43.6`
- parity-test SDK: `@modelcontextprotocol/sdk@1.30.0`

Runtime projects are MIT licensed. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Desktop Commander parity

Current verification exposes **26 upstream tools**, including:

- `get_config`, `set_config_value`
- `read_file`, `read_multiple_files`, `write_file`
- directory creation/listing, move, file metadata
- paginated search lifecycle
- `edit_block`
- process start/output/input/termination
- process and session listing/management
- `write_pdf`
- upstream usage/history/onboarding helpers

Paid-cloud account/device tools such as `who_am_i` and billing usage are not part of the local Desktop Commander engine.

## Filesystem policy

OwnerOps uses its own isolated Desktop Commander home:

```text
runtime/home/.claude-server-commander/config.json
```

The committed policy limits filesystem tools to:

- `C:\Users\getch\mcp`
- `C:\Users\getch\Documents`
- `C:\Users\getch\Downloads`

Telemetry is disabled and the upstream dangerous-command blocklist is retained.

Important: upstream `allowedDirectories` constrains Desktop Commander's filesystem tools; it is not an OS sandbox for arbitrary child programs launched through the terminal.

## Install

```cmd
scripts\install.cmd
```

Secrets live only in `.env`, which is gitignored.

## Local ChatGPT Desktop / Codex

```cmd
scripts\desktop_stdio.cmd
```

This machine is configured with:

```toml
[mcp_servers.ownerops_desktop]
command = 'C:\Users\getch\mcp\ownerops-desktop-mcp\scripts\desktop_stdio.cmd'
args = []
startup_timeout_sec = 120
tool_timeout_sec = 300
```

## ChatGPT Web endpoint

Production MCP URL:

```text
https://naver-mcp-home.taild017a0.ts.net/ownerops/mcp
```

OAuth issuer:

```text
https://naver-mcp-home.taild017a0.ts.net/ownerops
```

Authorization Server Metadata:

```text
https://naver-mcp-home.taild017a0.ts.net/.well-known/oauth-authorization-server/ownerops
```

Protected Resource Metadata:

```text
https://naver-mcp-home.taild017a0.ts.net/.well-known/oauth-protected-resource/ownerops/mcp
```

The web gateway supports:

- OAuth Authorization Code
- PKCE S256
- Dynamic Client Registration
- RFC 9207 `iss`
- RFC 8707 `resource`
- refresh-token rotation
- persisted OAuth state
- `offline_access`
- fixed ChatGPT redirect `https://chatgpt.com/connector_platform_oauth_redirect`

## Web login

Credentials are generated locally and are not committed.

To display them on the PC:

```cmd
scripts\show_web_login.cmd
```

The browser login is used only during OAuth authorization. MCP requests use issued OAuth access tokens afterward.

## Run web gateway

```cmd
scripts\start_web_gateway.cmd
```

The login proxy listens only on `127.0.0.1:8765`. The OAuth backend listens only on `127.0.0.1:8766`.
Tailscale Funnel exposes the HTTPS routes.

## Verification

Raw Desktop Commander parity:

```cmd
npm run verify:desktop
```

ChatGPT-style production OAuth test:

```cmd
uv run python scripts\smoke_web_oauth.py
```

The OAuth smoke test verifies discovery, DCR, browser login, PKCE, issuer validation, resource binding,
authorization-code exchange, refresh-token rotation, MCP initialization, session handling, and the 26-tool catalog.

## ChatGPT web registration

In ChatGPT developer mode create a custom app and use:

```text
MCP URL: https://naver-mcp-home.taild017a0.ts.net/ownerops/mcp
Authentication: OAuth
```

During Scan Tools, complete the OwnerOps login page. ChatGPT should then discover the upstream Desktop Commander tools.

## Updating

When Desktop Commander or mcp-stdio changes:

1. update only the pinned dependency version
2. install with lifecycle scripts disabled
3. run `npm run verify:desktop`
4. run the OAuth smoke test
5. review the tool-list diff and `npm audit --omit=dev`
6. commit lockfile changes

## Security

Do not expose the backend ports directly. Only the login proxy is routed through Tailscale Funnel.
The trusted user header is stripped from all client requests and injected only after successful OwnerOps login.
OAuth tokens and registrations persist under `runtime/`, which is gitignored.

Upstream dependency advisories are tracked in GitHub rather than force-overridden across potentially incompatible versions.

## License

OwnerOps deployment code is MIT licensed. Upstream dependencies retain their licenses.
