@echo off
setlocal
cd /d "%~dp0\.."

if not exist "node_modules\@wonderwhy-er\desktop-commander\dist\index.js" (
  echo Missing Desktop Commander package. Run scripts\install.cmd first. 1>&2
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

node "%CD%\node_modules\@wonderwhy-er\desktop-commander\dist\index.js"
