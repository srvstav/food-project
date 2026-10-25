@echo off
cd /d "%~dp0"
echo Builds the database on the cloud MySQL (Aiven) from backend\.env.cloud and backend\ca.pem
call setup.bat cloud
