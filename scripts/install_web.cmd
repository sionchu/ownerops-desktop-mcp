@echo off
setlocal
set "PYTHONUTF8=1"
cd /d "%~dp0\.."

if not exist "runtime\crawl4ai-mcp-venv\Scripts\python.exe" (
  python -m venv runtime\crawl4ai-mcp-venv
  if errorlevel 1 exit /b 1
)

runtime\crawl4ai-mcp-venv\Scripts\python.exe -m pip install --upgrade pip
if errorlevel 1 exit /b 1
runtime\crawl4ai-mcp-venv\Scripts\python.exe -m pip install "mcp==1.30.0" "crawl4ai==0.7.8" "playwright==1.63.0"
if errorlevel 1 exit /b 1
runtime\crawl4ai-mcp-venv\Scripts\python.exe -m playwright install chromium
if errorlevel 1 exit /b 1

if not exist "runtime\agent-browser" mkdir "runtime\agent-browser"
npm install --prefix runtime\agent-browser agent-browser@0.38.1 --save-exact
if errorlevel 1 exit /b 1
runtime\agent-browser\node_modules\.bin\agent-browser.cmd install
if errorlevel 1 exit /b 1

echo OwnerOps Web runtime installed.
