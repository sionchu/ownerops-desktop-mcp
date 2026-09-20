import path from "node:path";
import process from "node:process";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";

const root = path.resolve(import.meta.dirname, "..");
const transport = new StdioClientTransport({
  command: String.raw`C:\Users\getch\.dotnet\tools\mcpproxy.exe`,
  args: ["-t", "stdio", "-c", path.join(root, "config", "mcp-proxy.json")],
  cwd: root,
  env: { ...process.env, DOTNET_CLI_TELEMETRY_OPTOUT: "1" },
});
const client = new Client(
  { name: "ownerops-aggregate-verify", version: "0.5.0" },
  { capabilities: {} },
);
const expectedWeb = new Set([
  "web_fetch", "web_crawl",
  "browser_open", "browser_snapshot", "browser_click",
  "browser_fill", "browser_press", "browser_screenshot", "browser_close",
]);

try {
  await client.connect(transport);
  const response = await client.listTools();
  const names = response.tools.map((tool) => tool.name).sort();
  const win = names.filter((name) => name.startsWith("win_"));
  const sys = names.filter((name) => name.startsWith("sys_"));
  const search = names.filter((name) => name.startsWith("search_"));
  const web = names.filter((name) => expectedWeb.has(name));
  const desktop = names.filter(
    (name) => !name.startsWith("win_")
      && !name.startsWith("sys_")
      && !name.startsWith("search_")
      && !expectedWeb.has(name),
  );

  console.log("Aggregate tool count:", names.length);
  console.log("Desktop tools:", desktop.length);
  console.log("Win32 tools:", win.length);
  console.log("System tools:", sys.length);
  console.log("Search tools:", search.length);
  console.log("Web tools:", web.length);

  if (names.length !== 118) throw new Error(`Expected 118 tools, got ${names.length}`);
  if (desktop.length !== 26) throw new Error(`Expected 26 Desktop tools, got ${desktop.length}`);
  if (win.length !== 53) throw new Error(`Expected 53 Win32 tools, got ${win.length}`);
  if (sys.length !== 25) throw new Error(`Expected 25 curated System tools, got ${sys.length}`);
  if (search.length !== 5) throw new Error(`Expected 5 Everything tools, got ${search.length}`);
  if (web.length !== expectedWeb.size) throw new Error(`Expected 9 Web tools, got ${web.length}`);
  for (const required of [
    "start_process", "win_capture_screen", "win_uia_inspect_window",
    "sys_system_info", "sys_event_log", "sys_registry_get",
    "sys_service", "sys_scheduled_task", "sys_security_audit",
    "search_everything_search", ...expectedWeb,
  ]) {
    if (!names.includes(required)) throw new Error(`Missing required tool: ${required}`);
  }

  for (const forbidden of [
    "sys_screenshot", "sys_ocr", "sys_click", "sys_type",
    "sys_file_read", "sys_file_write", "sys_powershell",
    "sys_start_process", "sys_process", "sys_window", "sys_wmi_query",
    "browser_eval", "browser_type", "browser_upload", "browser_download",
  ]) {
    if (names.includes(forbidden)) throw new Error(`Duplicate/risky tool should be filtered: ${forbidden}`);
  }
  const unexpectedWeb = names.filter(
    (name) => (name.startsWith("web_") || name.startsWith("browser_")) && !expectedWeb.has(name),
  );
  if (unexpectedWeb.length) throw new Error(`Unexpected Web surface: ${unexpectedWeb.join(", ")}`);

  console.log("OwnerOps aggregate parity: PASS");
} finally {
  await client.close();
}
