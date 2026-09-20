# ownerops-desktop-mcp

Small self-hosted desktop MCP for personal development machines.

## Scope

Clean-v0 intentionally exposes only:
- `get_policy`
- `list_directory`
- `read_file`
- `write_file`
- `search_files`
- `run_shell`

There is no delete tool, registry tool, privilege escalation tool, or arbitrary process-kill tool.

## Security model

Filesystem tools resolve every path and require it to stay under `DESKTOP_MCP_ROOTS`.
Sensitive directory names can be denied with `DESKTOP_MCP_DENY_NAMES`.

The shell is intentionally more constrained than a normal terminal:
- working directory must be under an allowed root
- only executables in `DESKTOP_MCP_SHELL_ALLOW` may run
- command chaining and redirection are disabled
- execution has a timeout and output cap

Important: the shell policy is **not an OS sandbox**. An allowed executable can potentially access
resources outside the workspace. For a hard boundary, run the agent as a dedicated low-privilege
OS account or add a container/sandbox execution mode.

## Setup

```powershell
git clone https://github.com/sionchu/ownerops-desktop-mcp.git
cd ownerops-desktop-mcp
copy .env.example .env
uv sync
```

Edit `.env` and set explicit allowed roots and a long random token.

## Local stdio test

```powershell
uv run python server.py
```

## HTTP server

```powershell
uv run python http_server.py
```

Default endpoint: `http://127.0.0.1:8765/mcp`
Health endpoint: `http://127.0.0.1:8765/health`

HTTP mode supports `DESKTOP_MCP_AUTH_MODE=bearer`.
Send `Authorization: Bearer <DESKTOP_MCP_TOKEN>`.

## Tailscale

Prefer a private Tailscale path or a secure MCP tunnel. If using Tailscale Funnel, keep bearer
authentication enabled and do not commit `.env`.

A future OAuth adapter can be added without changing the filesystem/shell tool layer.

## Development

```powershell
uv run pytest
uv run ruff check .
```

## License

MIT
