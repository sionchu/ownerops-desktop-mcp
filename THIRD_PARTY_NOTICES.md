# Third-party notices

OwnerOps Desktop MCP is a self-hosting and aggregation layer. Upstream engines
and runtime components remain under their own licenses.

## Desktop Commander MCP

- Project: https://github.com/wonderwhy-er/DesktopCommanderMCP
- Package: `@wonderwhy-er/desktop-commander`
- Pinned version: `0.2.51`
- License: MIT
- Copyright: Eduard Ruzga and Desktop Commander contributors

Desktop Commander is the canonical OwnerOps filesystem, terminal, process,
search, edit, and document backend.

## mcp-stdio

- Project: https://github.com/shigechika/mcp-stdio
- Pinned version: `0.43.6`
- License: MIT

mcp-stdio provides the stdio-to-Streamable-HTTP OAuth gateway used by ChatGPT Web.

## McpProxy

- Project: https://github.com/MoaidHathot/mcp-proxy
- Installed version: `1.22.0`
- License: MIT

McpProxy aggregates the curated upstream stdio MCP servers into one endpoint.

## Win32 MCP Server

- Project: https://github.com/RandyNorthrup/win32-mcp-server
- Package: `win32-mcp-server`
- Installed version: `2.6.1`
- License: MIT
- Author: Randy Northrup

The OwnerOps runtime pins the Python MCP SDK used by this isolated environment
to `mcp==1.30.0`.

## Windows-mcp

- Project: https://github.com/danielsimonjr/Windows-mcp
- Runtime commit: `2a74b3e085fedfb2a5149674997675f636f11a01`
- License: MIT
- Copyright: JEOMON GEORGE

OwnerOps exposes only a curated allowlist of this server's system-specific
tools. Duplicate file/UI/screenshot/process-shell tools are filtered out.

## Everything MCP

- Project: https://github.com/elis132/everything-mcp
- Package: `everything-mcp`
- Installed version: `1.0.6`
- License: MIT

Everything MCP uses the local Everything command-line interface for indexed
Windows file search.

## Tesseract OCR

- Project: https://github.com/tesseract-ocr/tesseract
- Installed version: `5.5.3`
- License: Apache License 2.0

Tesseract is used by Win32 MCP OCR capabilities. Its dependencies may use
different open-source licenses as documented by the upstream project.

## Model Context Protocol SDK

- JavaScript parity-test package: `@modelcontextprotocol/sdk@1.30.0`
- Python SDK in the isolated Win32/Everything runtimes: `mcp==1.30.0`

Those packages retain their upstream licenses and notices.

Runtime virtual environments, compiled executables, OCR binaries, local OAuth
state, screenshots, and other machine-specific artifacts are kept under
`runtime/` or external installation paths and are not vendored into this
repository.
