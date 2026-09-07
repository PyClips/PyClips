@echo off
cd /d "%~dp0"
set PYTHONPATH=%~dp0
"%~dp0..\python\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8001
