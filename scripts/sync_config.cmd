@echo off
setlocal
cd /d "%~dp0\.."
if not exist "runtime\home\.claude-server-commander" mkdir "runtime\home\.claude-server-commander"
copy /Y "config\desktop-commander.config.json" "runtime\home\.claude-server-commander\config.json"
