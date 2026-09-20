@echo off
cd /d "%~dp0"
uv run python http_server.py >> ownerops-mcp.log 2>&1
