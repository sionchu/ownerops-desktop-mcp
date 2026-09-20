@echo off
setlocal
cd /d "%~dp0\.."

if not exist ".env" (
  echo Missing .env. Copy .env.example to .env and configure it.
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
  echo Missing Python environment. Run scripts\install.cmd first.
  exit /b 1
)
if not exist "node_modules\@wonderwhy-er\desktop-commander\dist\index.js" (
  echo Missing Desktop Commander package. Run scripts\install.cmd first.
  exit /b 1
)
if not exist "C:\Users\getch\.dotnet\tools\mcpproxy.exe" (
  echo Missing McpProxy. See README aggregate prerequisites.
  exit /b 1
)
if not exist "config\mcp-proxy.json" (
  echo Missing aggregate config.
  exit /b 1
)
if not exist "runtime\win32-venv\Scripts\win32-mcp-server.exe" (
  echo Missing win32-mcp-server runtime. See README aggregate prerequisites.
  exit /b 1
)
if not exist "runtime\windows-mcp-dist\WindowsMcp.exe" (
  echo Missing Windows-mcp runtime. See README aggregate prerequisites.
  exit /b 1
)
if not exist "runtime\everything-venv\Scripts\everything-mcp.exe" (
  echo Missing Everything MCP runtime. See README aggregate prerequisites.
  exit /b 1
)
if not exist "runtime\bin\es.exe" (
  echo Missing Everything CLI runtime. See README aggregate prerequisites.
  exit /b 1
)
if not exist "C:\Program Files\Tesseract-OCR\tesseract.exe" (
  echo Missing Tesseract OCR runtime. See README aggregate prerequisites.
  exit /b 1
)

".venv\Scripts\python.exe" "scripts\web_gateway.py"
