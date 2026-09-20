from __future__ import annotations

import asyncio
import fnmatch
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from mcp.server.mcpserver import MCPServer

load_dotenv()


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _split_env(name: str, default: str) -> tuple[str, ...]:
    raw = os.getenv(name, default)
    return tuple(item.strip() for item in raw.split(";") if item.strip())

@dataclass(frozen=True)
class Settings:
    roots: tuple[Path, ...]
    deny_names: tuple[str, ...]
    max_read_bytes: int
    max_write_bytes: int
    shell_enabled: bool
    shell: str
    shell_timeout: int
    shell_max_output: int
    shell_allow: tuple[str, ...]


def _load_settings() -> Settings:
    roots = tuple(Path(v).expanduser().resolve() for v in _split_env(
        "DESKTOP_MCP_ROOTS", str(Path.cwd())
    ))
    return Settings(
        roots=roots,
        deny_names=_split_env("DESKTOP_MCP_DENY_NAMES", ".ssh;.gnupg;.aws;.azure"),
        max_read_bytes=int(os.getenv("DESKTOP_MCP_MAX_READ_BYTES", "1048576")),
        max_write_bytes=int(os.getenv("DESKTOP_MCP_MAX_WRITE_BYTES", "1048576")),
        shell_enabled=_env_bool("DESKTOP_MCP_SHELL_ENABLED", True),
        shell=os.getenv("DESKTOP_MCP_SHELL", "cmd").strip().lower(),
        shell_timeout=int(os.getenv("DESKTOP_MCP_SHELL_TIMEOUT", "60")),
        shell_max_output=int(os.getenv("DESKTOP_MCP_SHELL_MAX_OUTPUT", "200000")),
        shell_allow=_split_env("DESKTOP_MCP_SHELL_ALLOW", "git;python;uv;node;npm;npx;pytest;ruff;where;dir;type;echo;findstr;tasklist"),
    )

SETTINGS = _load_settings()
AUTH_MODE = os.getenv("DESKTOP_MCP_AUTH_MODE", "bearer").strip().lower()
OAUTH_PROVIDER = None

if AUTH_MODE == "oauth":
    from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions, RevocationOptions
    from pydantic import AnyHttpUrl

    from oauth_provider import OwnerOAuthProvider

    public_base = os.environ["DESKTOP_MCP_PUBLIC_BASE"].rstrip("/")
    resource_url = os.environ["DESKTOP_MCP_PUBLIC_URL"]
    OAUTH_PROVIDER = OwnerOAuthProvider(
        username=os.environ["DESKTOP_MCP_OAUTH_USERNAME"],
        password=os.environ["DESKTOP_MCP_OAUTH_PASSWORD"],
        public_base_url=public_base,
        resource_url=resource_url,
    )
    mcp = MCPServer(
        "OwnerOps Desktop",
        auth_server_provider=OAUTH_PROVIDER,
        auth=AuthSettings(
            issuer_url=AnyHttpUrl(public_base),
            resource_server_url=AnyHttpUrl(resource_url),
            required_scopes=["desktop"],
            validate_token_resource=True,
            client_registration_options=ClientRegistrationOptions(
                enabled=True,
                valid_scopes=["desktop", "offline_access"],
                default_scopes=["desktop", "offline_access"],
            ),
            revocation_options=RevocationOptions(enabled=True),
        ),
    )
else:
    mcp = MCPServer("OwnerOps Desktop")


class PolicyError(ValueError):
    pass


def _is_inside(child: Path, parent: Path) -> bool:
    return child == parent or parent in child.parents


def resolve_scoped_path(path: str, *, must_exist: bool = False) -> Path:
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = SETTINGS.roots[0] / candidate
    resolved = candidate.resolve(strict=False)

    lowered_parts = {part.lower() for part in resolved.parts}
    for denied in SETTINGS.deny_names:
        if denied.lower() in lowered_parts:
            raise PolicyError(f"Path contains denied component: {denied}")

    if not any(_is_inside(resolved, root) for root in SETTINGS.roots):
        roots = ", ".join(str(root) for root in SETTINGS.roots)
        raise PolicyError(f"Path is outside allowed roots: {roots}")

    if must_exist and not resolved.exists():
        raise FileNotFoundError(str(resolved))
    return resolved


def validate_shell(command: str, cwd: Path) -> str:
    if not SETTINGS.shell_enabled:
        raise PolicyError("Shell execution is disabled.")
    if not command.strip():
        raise PolicyError("Command must not be empty.")
    if len(command) > 8000:
        raise PolicyError("Command is too long.")
    if any(token in command for token in ("&", "|", ">", "<", "\n", "\r")):
        raise PolicyError("Shell chaining and redirection are disabled.")

    first = command.strip().split(maxsplit=1)[0].strip('"').lower()
    allowed = {item.lower() for item in SETTINGS.shell_allow}
    if first not in allowed:
        raise PolicyError(f"Executable is not allowlisted: {first}")

    resolve_scoped_path(str(cwd), must_exist=True)
    return first


@mcp.tool()
def get_policy() -> dict:
    """Show the current filesystem and shell policy."""
    return {
        "allowed_roots": [str(root) for root in SETTINGS.roots],
        "denied_path_components": list(SETTINGS.deny_names),
        "max_read_bytes": SETTINGS.max_read_bytes,
        "max_write_bytes": SETTINGS.max_write_bytes,
        "shell_enabled": SETTINGS.shell_enabled,
        "shell": SETTINGS.shell,
        "shell_allow": list(SETTINGS.shell_allow),
        "shell_timeout_seconds": SETTINGS.shell_timeout,
        "shell_max_output_chars": SETTINGS.shell_max_output,
        "shell_boundary": "scoped cwd + allowlist; not an OS sandbox",
    }


@mcp.tool()
def list_directory(path: str = ".") -> list[dict]:
    """List one directory inside configured roots."""
    target = resolve_scoped_path(path, must_exist=True)
    if not target.is_dir():
        raise NotADirectoryError(str(target))

    denied = {name.lower() for name in SETTINGS.deny_names}
    items: list[dict] = []

    for item in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
        if item.name.lower() in denied:
            continue
        stat = item.stat()
        items.append({
            "name": item.name,
            "path": str(item),
            "type": "directory" if item.is_dir() else "file",
            "size": stat.st_size if item.is_file() else None,
        })
    return items


@mcp.tool()
def read_file(path: str, offset: int = 0, length: int | None = None) -> dict:
    """Read text from a file inside configured roots."""
    target = resolve_scoped_path(path, must_exist=True)
    if not target.is_file():
        raise IsADirectoryError(str(target))
    if offset < 0:
        raise ValueError("offset must be >= 0")

    cap = SETTINGS.max_read_bytes if length is None else min(length, SETTINGS.max_read_bytes)
    with target.open("rb") as handle:
        handle.seek(offset)
        data = handle.read(cap)

    return {
        "path": str(target),
        "offset": offset,
        "bytes": len(data),
        "truncated": len(data) == cap and target.stat().st_size > offset + len(data),
        "content": data.decode("utf-8", errors="replace"),
    }


@mcp.tool()
def write_file(path: str, content: str, mode: str = "overwrite") -> dict:
    """Write or append UTF-8 text inside configured roots."""
    encoded = content.encode("utf-8")
    if len(encoded) > SETTINGS.max_write_bytes:
        raise PolicyError("Write exceeds DESKTOP_MCP_MAX_WRITE_BYTES.")

    target = resolve_scoped_path(path)
    parent = resolve_scoped_path(str(target.parent))
    parent.mkdir(parents=True, exist_ok=True)
    if mode not in {"overwrite", "append"}:
        raise ValueError("mode must be 'overwrite' or 'append'")

    file_mode = "ab" if mode == "append" else "wb"
    with target.open(file_mode) as handle:
        handle.write(encoded)
    return {"path": str(target), "bytes_written": len(encoded), "mode": mode}


@mcp.tool()
def search_files(pattern: str, path: str = ".", limit: int = 200) -> list[str]:
    """Find path names by glob pattern inside configured roots."""
    root = resolve_scoped_path(path, must_exist=True)
    if not root.is_dir():
        raise NotADirectoryError(str(root))

    denied = {name.lower() for name in SETTINGS.deny_names}
    results: list[str] = []
    limit = max(1, min(limit, 1000))
    for current, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d.lower() not in denied]
        for name in dirs + files:
            if fnmatch.fnmatch(name.lower(), pattern.lower()):
                results.append(str(Path(current) / name))
                if len(results) >= limit:
                    return results
    return results


@mcp.tool()
async def run_shell(command: str, cwd: str = ".", timeout: int | None = None) -> dict:
    """Run an allowlisted shell command from a scoped working directory."""
    workdir = resolve_scoped_path(cwd, must_exist=True)
    if not workdir.is_dir():
        raise NotADirectoryError(str(workdir))
    validate_shell(command, workdir)

    seconds = SETTINGS.shell_timeout if timeout is None else min(max(timeout, 1), 300)
    if SETTINGS.shell == "powershell":
        argv = ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command]
    else:
        argv = ["cmd.exe", "/d", "/s", "/c", command]

    process = await asyncio.create_subprocess_exec(
        *argv,
        cwd=str(workdir),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    timed_out = False
    try:
        output, _ = await asyncio.wait_for(process.communicate(), timeout=seconds)
    except TimeoutError:
        timed_out = True
        process.kill()
        output, _ = await process.communicate()

    text = output.decode("utf-8", errors="replace")
    truncated = len(text) > SETTINGS.shell_max_output
    if truncated:
        text = text[:SETTINGS.shell_max_output]

    return {
        "cwd": str(workdir),
        "command": command,
        "exit_code": process.returncode,
        "timed_out": timed_out,
        "truncated": truncated,
        "output": text,
    }


if __name__ == "__main__":
    mcp.run()
