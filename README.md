# OwnerOps Desktop MCP

Self-hosted remote access to the **official Desktop Commander MCP engine**.

This project does not reimplement Desktop Commander's file, terminal, process, search, or document tools.
It pins the upstream engine and adds a reproducible remote gateway around it.

## Architecture

```text
ChatGPT / Codex / other MCP client
              |
       Streamable HTTP
              |
       Tailscale / tunnel
              |
        mcp-stdio gateway
              |
             stdio
              |
 @wonderwhy-er/desktop-commander
              |
          Windows PC
```

## Pinned upstream components

- Desktop Commander MCP: `@wonderwhy-er/desktop-commander@0.2.51`
- mcp-stdio gateway: `mcp-stdio==0.43.6`

Both upstream projects are MIT licensed. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Desktop Commander parity

The gateway exposes the actual upstream Desktop Commander tool catalog, including:

- configuration: `get_config`, `set_config_value`
- filesystem: read, multi-read, write, directory listing/creation, move, metadata
- search: start/paginate/stop/list searches
- editing: `edit_block`
- terminal: start process, interact, read output, terminate
- process/session management: list sessions/processes and kill process
- upstream document/image helpers included by the pinned Desktop Commander release

Cloud-account-only tools from the paid Desktop Commander Remote service
(`who_am_i`, usage billing, device dashboard metadata) are intentionally not part of this project.

## Isolation from an existing Desktop Commander install

The gateway overrides `USERPROFILE`/`HOME` for the upstream child process and keeps its own runtime home:

```text
runtime/home/.claude-server-commander/config.json
```

This prevents the self-hosted instance from sharing the currently installed Desktop Commander config.

The committed policy template allows file tools only under:

- `C:\Users\getch\mcp`
- `C:\Users\getch\Documents`
- `C:\Users\getch\Downloads`

Desktop Commander's upstream warning still applies: `allowedDirectories` constrains filesystem tools,
not everything a terminal child process can access. Its default dangerous-command blocklist is retained.

## Install

```cmd
scripts\install.cmd
copy .env.example .env
```

Generate a long random value for `MCP_STDIO_SERVE_TOKEN`.

## Run

```cmd
scripts\start_gateway.cmd
```

Local endpoint:

```text
http://127.0.0.1:8765/mcp
```

The gateway is authenticated with a static bearer token by default.

## Tailscale

This machine already uses Tailscale Funnel. A path route can expose the loopback gateway:

```cmd
tailscale funnel --bg --yes --set-path /ownerops http://127.0.0.1:8765
```

Resulting endpoint:

```text
https://<tailnet-host>/ownerops/mcp
```

For production use with ChatGPT web, prefer OpenAI Secure MCP Tunnel when available so the local service
does not need to be public. ChatGPT Desktop/Codex Streamable HTTP clients can also use bearer auth directly.

## Verification

Verify the raw upstream stdio engine:

```cmd
npm run verify:desktop
```

Verify the complete HTTP bridge:

```cmd
uv run python scripts\smoke_gateway.py
```

The smoke test checks authentication, MCP initialization, session handling, `tools/list`, and the expected
Desktop Commander core tool set.

## Updating Desktop Commander

Do not copy upstream source into this repository. Update the pinned npm version, reinstall, run both
verification commands, review the tool-list diff, then commit the lockfile changes.

## License

OwnerOps deployment code is MIT licensed. Upstream dependencies retain their own licenses.
