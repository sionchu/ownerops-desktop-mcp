import path from "node:path";
import process from "node:process";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";

const root = path.resolve(import.meta.dirname, "..");
const runtimeHome = path.join(root, "runtime", "home");
const server = path.join(
  root,
  "node_modules",
  "@wonderwhy-er",
  "desktop-commander",
  "dist",
  "index.js"
);

const required = [
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
];

const powershellDir = String.raw`C:\Windows\System32\WindowsPowerShell\v1.0`;
const system32Dir = String.raw`C:\Windows\System32`;
const repairedPath = [powershellDir, system32Dir, process.env.PATH || ""].join(path.delimiter);

const transport = new StdioClientTransport({
  command: process.execPath,
  args: [server],
  cwd: root,
  env: {
    ...process.env,
    USERPROFILE: runtimeHome,
    HOME: runtimeHome,
    PATH: repairedPath,
    DESKTOP_COMMANDER_DISABLE_TELEMETRY: "1",
  },
});

const client = new Client(
  { name: "ownerops-verify", version: "0.3.0" },
  { capabilities: {} }
);

try {
  await client.connect(transport);
  const response = await client.listTools();
  const names = response.tools.map((tool) => tool.name).sort();
  const missing = required.filter((name) => !names.includes(name));

  console.log("Desktop Commander tool count:", names.length);
  console.log(names.join("\n"));

  if (missing.length) {
    console.error("Missing required tools:", missing.join(", "));
    process.exitCode = 1;
  } else {
    console.log("Core Desktop Commander parity check: PASS");
  }

  const terminalTests = [
    ["default-shell", { command: "whoami", timeout_ms: 5000 }],
    ["powershell-by-name", { command: "whoami", timeout_ms: 5000, shell: "powershell.exe" }],
    ["cmd-by-name", { command: "whoami", timeout_ms: 5000, shell: "cmd.exe" }],
  ];

  for (const [label, args] of terminalTests) {
    const result = await client.callTool({ name: "start_process", arguments: args });
    const text = result.content?.map((item) => item.text || "").join("\n") || "";
    if (result.isError || !text.includes("Process started with PID")) {
      throw new Error(`Terminal regression failed (${label}): ${text}`);
    }
    console.log(`Terminal regression PASS: ${label}`);
  }
} finally {
  await client.close();
}
