@echo off
rem Rebuild the Java backend after changing any .java file, and run the unit tests.
cd /d "%~dp0backend"
call mvnw.cmd -B package
pause
