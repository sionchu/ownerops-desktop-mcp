@echo off
setlocal
cd /d "%~dp0\.."
npm install --ignore-scripts
if errorlevel 1 exit /b %errorlevel%
uv sync --dev
if errorlevel 1 exit /b %errorlevel%
call scripts\install_web.cmd
if errorlevel 1 exit /b %errorlevel%
echo OwnerOps Desktop MCP dependencies installed.
