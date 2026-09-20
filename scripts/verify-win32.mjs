import path from "node:path";
import process from "node:process";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";

const root = path.resolve(import.meta.dirname, "..");
const exe = path.join(root, "runtime", "win32-venv", "Scripts", "win32-mcp-server.exe");
const transport = new StdioClientTransport({
  command: exe,
  args: [],
  cwd: root,
  env: {
    ...process.env,
    WIN32_MCP_SECURITY_PROFILE: "interactive",
    WIN32_MCP_RESULT_ENVELOPE: "1",
    TESSERACT_CMD: String.raw`C:\Program Files\Tesseract-OCR\tesseract.exe`,
  },
});
const client = new Client({ name: "win32-verify", version: "0.4.0" }, { capabilities: {} });
try {
  await client.connect(transport);
  const response = await client.listTools();
  const names = response.tools.map((tool) => tool.name).sort();
  console.log("Win32 tool count:", names.length);
  if (names.length !== 53) throw new Error(`Expected 53 Win32 tools, got ${names.length}`);
  for (const required of ["capture_screen", "ocr_screen_structured", "list_windows", "uia_inspect_window"]) {
    if (!names.includes(required)) throw new Error(`Missing Win32 tool: ${required}`);
  }
  console.log("Win32 standalone parity: PASS");
} finally {
  await client.close();
}
