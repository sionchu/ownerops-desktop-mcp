# OwnerOps Desktop MCP

Self-hosted Windows desktop control for ChatGPT and other MCP clients.

OwnerOps keeps the official Desktop Commander engine as the canonical filesystem,
terminal, and process backend, then adds focused Windows automation and system
capabilities through a curated McpProxy aggregate. The default surface is kept
intentionally smaller than the union of every upstream tool.

## Architecture

```text
Local MCP client                         ChatGPT Web
      |                                      |
      | stdio                                | HTTPS / OAuth 2.1 + PKCE
      v                                      v
                 OwnerOps Desktop
                    McpProxy
                       |
        +--------------+--------------+--------------+
        |              |              |              |
 Desktop Commander  Win32 MCP    Windows-mcp   Everything MCP
     26 tools        53 tools       25 tools       5 tools
        |              |              |              |
        +--------------+--------------+--------------+
                       |
                  Windows PC
```

For ChatGPT Web, `mcp-stdio` wraps the same aggregate behind the OwnerOps OAuth gateway.

## Default tool surface

The default aggregate exposes exactly **109 tools**:

| Backend | Tools | Role |
|---|---:|---|
| Desktop Commander | 26 | Files, directories, editing, terminal, process/session management, PDF |
| Win32 MCP | 53 | Windows UI automation, input, clipboard, windows, UIA, capture/OCR |
| Windows-mcp | 25 | Curated system diagnostics and administration |
| Everything MCP | 5 | Indexed machine-wide file search |

The Windows-mcp allowlist keeps only system-specific capabilities:
audio, certificates, Defender, disk inspection, drivers, environment variables,
event logs, NTFS streams/change journal, firewall, integrity checks, network,
notifications, deep process inspection, registry, reliability, scheduled tasks,
security audit, services, startup report, storage health, system information,
signature verification, and directory watching.

Generic duplicate System tools for file I/O, mouse/keyboard, window control,
screenshot/OCR, process launching, PowerShell, and raw WMI are not exposed.
Those responsibilities already have canonical OwnerOps backends.

Playwright/browser tools are also excluded from the default aggregate. Browser
automation is a separate concern and previously added 45 tools without improving
Windows desktop-control parity.

## Runtime components

- `@wonderwhy-er/desktop-commander@0.2.51`
- `mcp-stdio==0.43.6`
- McpProxy `1.22.0`
- `win32-mcp-server==2.6.1` with Python MCP SDK `1.30.0`
- Windows-mcp from `danielsimonjr/Windows-mcp`, locally pinned by runtime build
- `everything-mcp==1.0.6`
- Tesseract OCR `5.5.3`
- parity-test SDK `@modelcontextprotocol/sdk@1.30.0`

## Security model

Desktop Commander runs with its own isolated home:

```text
runtime/home/.claude-server-commander/config.json
```

The committed baseline intentionally sets `allowedDirectories: []`, so Desktop
Commander filesystem tools can access the full filesystem permitted by the
Windows account. The live runtime config is expected to report the same value
through `get_config`; `scripts\sync_config.cmd` reapplies the committed baseline
when an explicit reset is needed.

Telemetry is disabled and the upstream dangerous-command blocklist remains enabled.
`allowedDirectories` controls Desktop Commander filesystem policy only; it does
not bypass Windows ACLs or sandbox arbitrary child processes started from the terminal.

Win32 MCP runs with the `interactive` security profile. Ordinary GUI automation
remains available, while its high-risk `start_process`, `kill_process`, and
`close_window` paths are blocked by that profile. OwnerOps already has safer
canonical process-management paths.

Curated Windows-mcp mutating operations keep their upstream `confirm:true`
requirements. McpProxy logging masks sensitive data and response logging is off.

## Install

Base repo dependencies:

```cmd
scripts\install.cmd
```

This installs the committed Node/Python project dependencies. Secrets stay in
`.env`, which is gitignored.
The aggregate also expects machine-local runtimes under `runtime/`:

```text
runtime/win32-venv/Scripts/win32-mcp-server.exe
runtime/windows-mcp-dist/WindowsMcp.exe
runtime/everything-venv/Scripts/everything-mcp.exe
runtime/bin/es.exe
C:\Users\getch\.dotnet\tools\mcpproxy.exe
C:\Program Files\Tesseract-OCR\tesseract.exe
```

These runtime artifacts are intentionally gitignored instead of vendored into
the repository. `scripts\start_web_gateway.cmd` performs preflight checks for
the required aggregate executables.

## Local MCP endpoint

Run:

```cmd
scripts\desktop_stdio.cmd
```

The script starts McpProxy in stdio mode using `config\mcp-proxy.json`.

## ChatGPT Web endpoint

Production MCP URL:

```text
https://naver-mcp-home.taild017a0.ts.net/ownerops/mcp
```

OAuth issuer:

```text
https://naver-mcp-home.taild017a0.ts.net/ownerops
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

The login proxy listens on `127.0.0.1:8765`; the OAuth backend listens on
`127.0.0.1:8766`. Only the intended HTTPS route should be exposed externally.

Run the gateway with:

```cmd
scripts\start_web_gateway.cmd
```

To display the locally generated OwnerOps login credentials:

```cmd
scripts\show_web_login.cmd
```

## Verification

Raw Desktop Commander parity:

```cmd
npm run verify:desktop
```

Win32 standalone catalog:

```cmd
npm run verify:win32
```
Curated aggregate catalog:

```cmd
npm run verify:aggregate
```

Production-style OAuth smoke:

```cmd
.venv\Scripts\python.exe scripts\smoke_web_oauth.py
```

The OAuth smoke verifies discovery, DCR, login, PKCE, issuer/resource binding,
token exchange, refresh-token rotation, MCP session handling, the exact
109-tool catalog, Desktop Commander terminal/Git/Python regressions, and safe
representative Win32/System/Everything calls.

The smoke parser treats both MCP-level `isError` and tool-level JSON
`{"error": true}` envelopes as failures.

## Screen capture and OCR note

Win32 capture/OCR depends on Windows desktop capture APIs. A reachable desktop
session can still deny graphics capture, for example when the active session or
display path does not expose a capturable surface. In that state, window
enumeration and UI Automation may continue to work while screenshot/OCR calls
return a Windows graphics/BitBlt error.

Do not treat tool registration or a top-level MCP success envelope as proof that
capture worked; verify the returned tool payload.

## ChatGPT tool refresh

After changing the aggregate tool catalog, reconnect or rescan the OwnerOps
custom app in ChatGPT so its cached tool schemas match the current 109-tool
server surface.

## Updating

When an upstream component changes:

1. update only the intended pinned/runtime component
2. review the upstream tool-list diff
3. keep one canonical backend for overlapping capabilities
4. run Desktop, Win32, and aggregate parity checks
5. run the production OAuth smoke
6. verify representative real calls, not only `tools/list`
7. review `git diff` and remove experimental artifacts before committing

Do not add an MCP merely because it exposes more tools. New backends should add
a distinct capability that cannot be covered cleanly by the existing canonical
paths.

Package inventory is intentionally handled through the existing shell
(`winget`, application-specific CLIs, etc.) instead of adding another package
manager MCP. Browser automation and session recording are likewise kept outside
the default aggregate unless a concrete OwnerOps workflow requires them.

## License

OwnerOps deployment code is MIT licensed. Upstream dependencies retain their
own licenses; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
