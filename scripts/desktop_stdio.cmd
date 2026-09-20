@echo off
setlocal
cd /d "%~dp0\.."

if not exist "C:\Users\getch\.dotnet\tools\mcpproxy.exe" (
  echo Missing McpProxy. See README aggregate prerequisites. 1>&2
  exit /b 1
)
if not exist "config\mcp-proxy.json" (
  echo Missing aggregate config. 1>&2
  exit /b 1
)

set "DOTNET_CLI_TELEMETRY_OPTOUT=1"
"C:\Users\getch\.dotnet\tools\mcpproxy.exe" -t stdio -c "%CD%\config\mcp-proxy.json"
