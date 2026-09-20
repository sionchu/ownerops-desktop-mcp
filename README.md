# OwnerOps Desktop MCP

Self-hosted access to the **official Desktop Commander MCP engine**.

This project does not reimplement Desktop Commander's file, terminal, process, search, or document tools.
It pins the upstream engine and adds isolated local launchers plus a reproducible remote gateway.

## Architecture

```text
ChatGPT Desktop / Codex ── stdio ───────────────┐
                                                ▼
                                      Desktop Commander MCP
                                                ▲
ChatGPT remote client ─ HTTPS ─ mcp-stdio ─ stdio
                           ▲
                    Tailscale / tunnel
```

## Pinned upstream components

- Desktop Commander MCP: `@wonderwhy-er/desktop-commander@0.2.51`
- mcp-stdio gateway: `mcp-stdio==0.43.6`
- MCP SDK used by parity tests: `@modelcontextprotocol/sdk@1.30.0`

Both upstream runtime projects are MIT licensed. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Desktop Commander parity

The project exposes the actual upstream Desktop Commander catalog. Current verification reports **26 tools**:

- configuration: `get_config`, `set_config_value`
- filesystem: read, multi-read, write, directory listing/creation, move, metadata
- search: start/paginate/stop/list searches
- editing: `edit_block`
- terminal: start process, interact, read output, terminate
- process/session management: list sessions/processes and kill process
- upstream helpers including `write_pdf`, usage/history and onboarding tools

Cloud-account-only tools from the paid Desktop Commander Remote service
(`who_am_i`, billing/remote usage percentage, remote device dashboard metadata) are not part of the local engine.

## Isolation from an existing Desktop Commander install

Both launchers override `USERPROFILE`/`HOME` for the upstream child and keep a dedicated runtime home:

```text
runtime/home/.claude-server-commander/config.json
```

This prevents OwnerOps from sharing the configuration used by an existing Desktop Commander installation.

The committed policy template allows filesystem tools only under:

- `C:\Users\getch\mcp`
- `C:\Users\getch\Documents`
- `C:\Users\getch\Downloads`

Desktop Commander's upstream warning still applies: `allowedDirectories` constrains filesystem tools,
not everything a terminal process can access. The upstream dangerous-command blocklist is retained.

## Install

```cmd
scripts\install.cmd
copy .env.example .env
```

Generate a long random value for `MCP_STDIO_SERVE_TOKEN`.

Dependency lifecycle scripts are intentionally disabled during npm install.

## Local ChatGPT Desktop / Codex

Use the stdio launcher:

```cmd
scripts\desktop_stdio.cmd
```

Example Codex/ChatGPT Desktop configuration:

```toml
[mcp_servers.ownerops_desktop]
command = 'C:\Users\getch\mcp\ownerops-desktop-mcp\scripts\desktop_stdio.cmd'
args = []
startup_timeout_sec = 120
tool_timeout_sec = 300
```

This is the preferred path on the same PC: no public endpoint, token, or tunnel is required.

## Remote Streamable HTTP

Run:

```cmd
scripts\start_gateway.cmd
```

Local endpoint:

```text
http://127.0.0.1:8765/mcp
```

The remote gateway uses a static bearer token by default.

## Tailscale

A Tailscale Funnel path can expose the loopback gateway:

```cmd
tailscale funnel --bg --yes --set-path /ownerops http://127.0.0.1:8765
```

Result:

```text
https://<tailnet-host>/ownerops/mcp
```

For ChatGPT web, prefer OpenAI Secure MCP Tunnel when available so the service does not need to be public.
A web custom app may require OAuth depending on the ChatGPT surface and plan; that is tracked separately from
the Desktop Commander engine itself.

## Verification

Raw upstream stdio parity:

```cmd
npm run verify:desktop
```

Complete HTTP bridge:

```cmd
uv run python scripts\smoke_gateway.py
```

The HTTP smoke test checks bearer authentication, MCP initialization, session handling, `tools/list`,
and the expected Desktop Commander core tool set.

## Updating Desktop Commander

Do not copy upstream source into this repository. Update the pinned npm version, reinstall, run both
verification commands, review the tool-list diff and `npm audit --omit=dev`, then commit lockfile changes.

## Security notes

The current upstream Desktop Commander dependency tree has npm advisories in image/document dependencies.
They are tracked in GitHub Issues rather than force-overridden across semver boundaries. Do not expose the
gateway without authentication.

## License

OwnerOps deployment code is MIT licensed. Upstream dependencies retain their own licenses.
