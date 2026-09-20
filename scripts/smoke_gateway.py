from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
PORT = 8876
URL = f"http://127.0.0.1:{PORT}/mcp"
TOKEN = "ownerops-ci-smoke-token"
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
}


def parse_response(response: httpx.Response) -> dict:
    content_type = response.headers.get("content-type", "")
    if "application/json" in content_type:
        return response.json()
    for line in response.text.splitlines():
        if line.startswith("data:"):
            return json.loads(line[5:].strip())
    raise RuntimeError(f"Unexpected MCP response: {content_type} {response.text[:500]}")


def main() -> int:
    exe = shutil.which("mcp-stdio")
    if not exe:
        raise RuntimeError("mcp-stdio is not available on PATH")

    runtime_home = ROOT / "runtime" / "smoke-home"
    config_dir = runtime_home / ".claude-server-commander"
    config_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "config" / "desktop-commander.config.json", config_dir / "config.json")

    desktop = ROOT / "node_modules" / "@wonderwhy-er" / "desktop-commander" / "dist" / "index.js"
    env = os.environ.copy()
    env.update(
        {
            "MCP_STDIO_SERVE_TOKEN": TOKEN,
            "USERPROFILE": str(runtime_home),
            "HOME": str(runtime_home),
            "DESKTOP_COMMANDER_DISABLE_TELEMETRY": "1",
        }
    )

    process = subprocess.Popen(
        [
            exe,
            "serve",
            "--host",
            "127.0.0.1",
            "--port",
            str(PORT),
            "--path",
            "/mcp",
            "--max-sessions",
            "2",
            "--session-idle-ttl",
            "60",
            "--",
            "node",
            str(desktop),
        ],
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    try:
        client = httpx.Client(
            timeout=10,
            headers={
                "Authorization": f"Bearer {TOKEN}",
                "Accept": "application/json, text/event-stream",
                "Content-Type": "application/json",
            },
        )
        deadline = time.time() + 20
        while time.time() < deadline:
            try:
                unauth = httpx.post(URL, json={}, timeout=1)
                if unauth.status_code == 401:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(0.25)
        else:
            raise RuntimeError("Gateway did not become ready")

        init = client.post(
            URL,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "ownerops-smoke", "version": "0.3.0"},
                },
            },
        )
        init.raise_for_status()
        session_id = init.headers.get("mcp-session-id")
        if not session_id:
            raise RuntimeError("Gateway did not return Mcp-Session-Id")

        headers = {"Mcp-Session-Id": session_id, "MCP-Protocol-Version": "2025-06-18"}
        client.post(
            URL,
            headers=headers,
            json={"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
        )

        listed = client.post(
            URL,
            headers=headers,
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        )
        listed.raise_for_status()
        payload = parse_response(listed)
        names = {tool["name"] for tool in payload["result"]["tools"]}
        missing = sorted(REQUIRED - names)
        if missing:
            raise RuntimeError(f"Missing Desktop Commander tools: {missing}")

        print(f"Gateway smoke PASS: {len(names)} tools exposed")
        print("\n".join(sorted(names)))
        return 0
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()


if __name__ == "__main__":
    sys.exit(main())
