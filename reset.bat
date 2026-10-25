@echo off
cd /d "%~dp0"
echo This WIPES the local database and rebuilds it with fresh sample data.
set /p OK=Type YES to continue: 
if /i not "%OK%"=="YES" exit /b 0
call setup.bat reset
