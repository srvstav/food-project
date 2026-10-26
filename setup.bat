@echo off
setlocal
cd /d "%~dp0"
set PYTHONUTF8=1
title MUJ Mess - setup
echo ==== MUJ Mess: first-time setup ====
echo.
set "PY="
where py >nul 2>nul
if not errorlevel 1 set "PY=py -3"
if not defined PY (
  where python >nul 2>nul
  if not errorlevel 1 set "PY=python"
)
if not defined PY (
  echo Python is not installed.
  echo Install it from https://www.python.org/downloads/ and tick "Add python.exe to PATH".
  goto :fail
)
if not exist "backend\.venv\Scripts\python.exe" (
  echo Creating the Python environment...
  %PY% -m venv backend\.venv
  if errorlevel 1 goto :fail
)
echo Installing packages - the first time takes a minute...
"backend\.venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r requirements.txt
if errorlevel 1 goto :fail
echo.
"backend\.venv\Scripts\python.exe" setup.py %1
if errorlevel 1 goto :fail
echo.
echo Setup finished. Now double-click start.bat
pause
exit /b 0
:fail
echo.
echo Setup did not finish. Read the message above, fix it, and run setup.bat again.
pause
exit /b 1
