@echo off
setlocal
cd /d "%~dp0\.."

if not exist ".env" (
  echo Missing .env. Copy .env.example to .env and configure it.
  exit /b 1
)

for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
  if not "%%A"=="" set "%%A=%%B"
)

if "%OWNEROPS_HOST%"=="" set "OWNEROPS_HOST=127.0.0.1"
if "%OWNEROPS_PORT%"=="" set "OWNEROPS_PORT=8765"
if "%MCP_STDIO_SERVE_TOKEN%"=="" (
  echo MCP_STDIO_SERVE_TOKEN is required.
  exit /b 1
)
if not exist ".venv\Scripts\mcp-stdio.exe" (
  echo Missing Python environment. Run scripts\install.cmd first.
  exit /b 1
)
if not exist "node_modules\@wonderwhy-er\desktop-commander\dist\index.js" (
  echo Missing Desktop Commander package. Run scripts\install.cmd first.
  exit /b 1
)

set "OWNEROPS_RUNTIME_HOME=%CD%\runtime\home"
if not exist "%OWNEROPS_RUNTIME_HOME%\.claude-server-commander" mkdir "%OWNEROPS_RUNTIME_HOME%\.claude-server-commander"
if not exist "%OWNEROPS_RUNTIME_HOME%\.claude-server-commander\config.json" (
  copy /Y "config\desktop-commander.config.json" "%OWNEROPS_RUNTIME_HOME%\.claude-server-commander\config.json" >NUL
)

set "USERPROFILE=%OWNEROPS_RUNTIME_HOME%"
set "HOME=%OWNEROPS_RUNTIME_HOME%"
set "DESKTOP_COMMANDER_DISABLE_TELEMETRY=1"

".venv\Scripts\mcp-stdio.exe" serve ^
  --host %OWNEROPS_HOST% ^
  --port %OWNEROPS_PORT% ^
  --path /mcp ^
  --max-sessions 4 ^
  --session-idle-ttl 900 ^
  -- node "%CD%\node_modules\@wonderwhy-er\desktop-commander\dist\index.js"
