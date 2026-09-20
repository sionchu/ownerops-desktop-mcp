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

".venv\Scripts\python.exe" "scripts\web_gateway.py"
