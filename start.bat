@echo off
setlocal
cd /d "%~dp0"
title MUJ Mess (Java) - server (close this window to stop)
if not exist "backend\.env" (
  echo Run setup.bat first.
  pause
  exit /b 1
)
where java >nul 2>nul
if errorlevel 1 (
  echo Java is not installed. Install JDK 17 or newer from https://adoptium.net and run this again.
  pause
  exit /b 1
)
if not exist "backend\target\mess.jar" (
  echo Building the Java backend - the first time downloads Maven and takes a few minutes...
  pushd backend
  call mvnw.cmd -q -B package -DskipTests
  if errorlevel 1 ( popd & echo Build failed. & pause & exit /b 1 )
  popd
)
start "" /min cmd /c "timeout /t 4 /nobreak >nul && start http://localhost:8000"
java -jar backend\target\mess.jar
pause
