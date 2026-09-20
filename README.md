# ownerops-desktop-mcp

Self-hosted personal desktop MCP. The goal is a small, inspectable alternative to a paid
desktop-control bridge rather than a feature-for-feature clone.

## Clean-v0 tools

- `get_policy`
- `list_directory`
- `read_file`
- `write_file`
- `search_files`
- `run_shell`

No delete, registry, privilege-escalation, or arbitrary process-kill tool is exposed.

## Security

Filesystem access is constrained by `DESKTOP_MCP_ROOTS`. Every file path is resolved before
use and must remain under an allowed root. Sensitive directory names can additionally be denied
with `DESKTOP_MCP_DENY_NAMES`.

The shell is deliberately restricted:
- its working directory must be inside an allowed root
- only commands in `DESKTOP_MCP_SHELL_ALLOW` may start
- shell chaining and redirection are rejected
- runtime and output are capped

The shell policy is not an OS sandbox. An allowlisted executable may still reach host resources.
For a hard boundary, run under a dedicated low-privilege account or add a container sandbox.

## Authentication

HTTP mode supports:
- `oauth` — OAuth authorization code flow, S256 PKCE, dynamic client registration,
  refresh-token rotation, and `offline_access`
- `bearer` — static bearer token for simple MCP clients
- `none` — local/private testing only

OAuth credentials and tokens live outside Git in `.env`.

## Setup

```powershell
git clone https://github.com/sionchu/ownerops-desktop-mcp.git
cd ownerops-desktop-mcp
copy .env.example .env
uv sync --dev
uv run pytest
uv run ruff check .
```

Set explicit roots and generate strong OAuth credentials before remote use.

## Run

```powershell
uv run python http_server.py
```

Local MCP endpoint: `http://127.0.0.1:8765/mcp`

`start_mcp.cmd` is provided for Windows startup/task-scheduler use.

## Tailscale Funnel example

If the public base is `https://host.example/ownerops`:

```powershell
tailscale funnel --bg --set-path /ownerops http://127.0.0.1:8765
```

RFC 9728 protected-resource metadata is advertised at a root well-known URL. If another
service already owns `/`, add a narrow route for that exact metadata path as well.

Prefer a private Tailscale path or OpenAI Secure MCP Tunnel when available instead of a public
Funnel. If Funnel is used, keep OAuth enabled.

## Development

The project tracks MCP Python SDK 2.x and CI runs on Windows with pytest and Ruff.

## License

MIT
