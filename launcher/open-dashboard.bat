@echo off
setlocal
title Job Scope
cd /d "%~dp0.."

set "PY=python"
where python >nul 2>&1 || set "PY=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"

rem Rebuilds the page from the last run's cached _run.json and opens it.
rem No network, no fetching — about a second.
"%PY%" scripts\build_dashboard.py
if errorlevel 1 goto failed
exit /b 0

:failed
echo.
echo   Could not open the dashboard. Run a full hunt first (Job Scope).
echo.
pause
exit /b 1
