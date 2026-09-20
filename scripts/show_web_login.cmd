@echo off
setlocal
cd /d "%~dp0\.."
if not exist ".env" (
  echo Missing .env
  exit /b 1
)
for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
  if /I "%%A"=="OWNEROPS_WEB_USERNAME" echo Username: %%B
  if /I "%%A"=="OWNEROPS_WEB_PASSWORD" echo Password: %%B
)
