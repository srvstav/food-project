@echo off
cd /d "%~dp0"
set PYTHONUTF8=1
if not exist "backend\.env" (
  echo Run setup.bat first.
  pause
  exit /b 1
)
"backend\.venv\Scripts\python.exe" demo_data.py %1
pause
