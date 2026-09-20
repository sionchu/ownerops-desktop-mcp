from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / "runtime" / "crawl4ai-mcp-venv" / "Scripts" / "python.exe"
SERVER = ROOT / "scripts" / "web_mcp.py"
EXPECTED = {
    "web_fetch", "web_crawl",
    "browser_open", "browser_snapshot", "browser_click",
    "browser_fill", "browser_press", "browser_screenshot", "browser_close",
}


def result_text(result) -> str:
    return "\n".join(
        item.text for item in result.content
        if getattr(item, "type", None) == "text"
    )


def result_json(result) -> dict:
    text = result_text(result)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"text": text}

async def expect_error(session: ClientSession, name: str, arguments: dict) -> None:
    try:
        result = await session.call_tool(name, arguments)
    except Exception:
        return
    if not getattr(result, "isError", False):
        raise RuntimeError(f"{name} unexpectedly succeeded: {result_text(result)[:500]}")


async def main() -> None:
    params = StdioServerParameters(
        command=str(PYTHON),
        args=[str(SERVER)],
        cwd=str(ROOT),
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            names = {tool.name for tool in tools.tools}
            if names != EXPECTED:
                raise RuntimeError(f"Unexpected Web surface: {sorted(names)}")
            print("Catalog PASS: exact 9-tool Web surface")

            await expect_error(
                session,
                "web_fetch",
                {"url": "http://127.0.0.1:8766/"},
            )
            await expect_error(
                session,
                "browser_open",
                {"url": "http://127.0.0.1:8766/"},
            )
            print("Security PASS: loopback URL blocked for fetch and browser")

            fetched = await session.call_tool(
                "web_fetch",
                {"url": "https://example.com", "max_chars": 4000},
            )
            if getattr(fetched, "isError", False):
                raise RuntimeError("web_fetch failed: " + result_text(fetched))
            fetch_data = result_json(fetched)
            if "Example Domain" not in json.dumps(fetch_data):
                raise RuntimeError("web_fetch did not return expected page content")
            print("Fetch PASS: example.com")

            crawled = await session.call_tool(
                "web_crawl",
                {
                    "seed_url": "https://www.python.org/about/",
                    "max_depth": 1,
                    "max_pages": 2,
                    "max_chars_per_page": 2500,
                },
            )
            if getattr(crawled, "isError", False):
                raise RuntimeError("web_crawl failed: " + result_text(crawled))
            crawl_data = result_json(crawled)
            if int(crawl_data.get("total_pages", 0)) < 2:
                raise RuntimeError(f"web_crawl expected >=2 pages: {crawl_data}")
            print("Crawl PASS: 2 same-host pages")

            opened = await session.call_tool(
                "browser_open",
                {"url": "https://www.selenium.dev/selenium/web/web-form.html"},
            )
            if getattr(opened, "isError", False):
                raise RuntimeError("browser_open failed: " + result_text(opened))

            snapshot = await session.call_tool(
                "browser_snapshot",
                {"compact": True, "depth": 8, "interactive_only": True},
            )
            snapshot_data = result_json(snapshot)
            snap_text = snapshot_data.get("snapshot", result_text(snapshot))
            input_match = re.search(r'textbox "Text input[^"]*" \[ref=(e\d+)\]', snap_text)
            submit_match = re.search(r'button "Submit" \[ref=(e\d+)\]', snap_text)
            if not input_match or not submit_match:
                raise RuntimeError("browser_snapshot returned no usable element refs")
            input_ref = "@" + input_match.group(1)
            submit_ref = "@" + submit_match.group(1)
            print("Browser snapshot PASS: accessibility refs present")

            filled = await session.call_tool(
                "browser_fill",
                {"target": input_ref, "text": "OwnerOps Web"},
            )
            if getattr(filled, "isError", False):
                raise RuntimeError("browser_fill failed: " + result_text(filled))
            pressed = await session.call_tool("browser_press", {"key": "Tab"})
            if getattr(pressed, "isError", False):
                raise RuntimeError("browser_press failed: " + result_text(pressed))

            clicked = await session.call_tool(
                "browser_click",
                {"target": submit_ref, "settle_ms": 500},
            )
            if getattr(clicked, "isError", False):
                raise RuntimeError("browser_click failed: " + result_text(clicked))

            final_snapshot = await session.call_tool(
                "browser_snapshot",
                {"compact": True, "depth": 8, "interactive_only": False},
            )
            final_data = result_json(final_snapshot)
            final_text = final_data.get("snapshot", result_text(final_snapshot))
            if "Form submitted" not in final_text:
                raise RuntimeError("Browser action-effect verification failed")
            print("Browser action PASS: form submission verified")

            shot = await session.call_tool(
                "browser_screenshot",
                {"full_page": False},
            )
            shot_data = result_json(shot)
            shot_path = shot_data.get("path") or ""
            if not shot_path or not Path(shot_path).exists():
                raise RuntimeError(f"browser_screenshot missing output: {shot_data}")
            if not any(getattr(item, "type", None) == "image" for item in shot.content):
                raise RuntimeError("browser_screenshot returned no MCP image content")
            print("Screenshot PASS: MCP image +", shot_path)

            closed = await session.call_tool("browser_close", {})
            if getattr(closed, "isError", False):
                raise RuntimeError("browser_close failed: " + result_text(closed))
            print("Browser close PASS")
            print("OwnerOps Web functional smoke: PASS")


if __name__ == "__main__":
    asyncio.run(main())
