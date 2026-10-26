@echo off
setlocal
cd /d "%~dp0"
rem Opens MySQL Workbench already connected, with db\demo_queries.sql loaded.
rem   workbench.bat         this laptops MySQL (root@127.0.0.1)
rem   workbench.bat cloud   the cloud MySQL (details saved by setup_cloud.bat)
set "WB="
for /d %%D in ("%ProgramFiles%\MySQL\MySQL Workbench*") do if exist "%%D\MySQLWorkbench.exe" set "WB=%%D\MySQLWorkbench.exe"
if not defined WB (
  echo MySQL Workbench is not installed. Get it from https://dev.mysql.com/downloads/workbench/
  pause
  exit /b 1
)
set "CONN=root@127.0.0.1:3306"
if /i "%~1"=="cloud" (
  if not exist "backend\.workbench_cloud" (
    echo No cloud details on this laptop. Run setup_cloud.bat first, or connect by hand: see WORKBENCH.md
    pause
    exit /b 1
  )
  set /p CONN=<"backend\.workbench_cloud"
)
echo Opening Workbench on %CONN% with db\demo_queries.sql
echo It asks for the password once. Then put the cursor in a query and press Ctrl+Enter.
start "" "%WB%" --query "%CONN%" --open "%~dp0db\demo_queries.sql"
