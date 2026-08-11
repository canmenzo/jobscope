@echo off
setlocal
title Job Scope
cd /d "%~dp0.."

set "PY=python"
where python >nul 2>&1 || set "PY=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"

echo.
echo   Job Scope - pulling the latest postings...
echo.

"%PY%" scripts\job_hunt.py
set RC=%ERRORLEVEL%
if "%RC%"=="2" goto needsetup
if not "%RC%"=="0" goto failed

"%PY%" scripts\build_dashboard.py
set RC=%ERRORLEVEL%
if not "%RC%"=="0" goto failed
exit /b 0

:needsetup
echo.
echo   No config yet. Open Claude Code and say "set up my job hunt".
goto hold

:failed
echo.
echo   Run failed (exit code %RC%). See the output above.
goto hold

:hold
echo.
pause
exit /b 1
