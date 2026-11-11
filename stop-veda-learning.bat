@echo off
setlocal EnableExtensions
cd /d "%~dp0"
where docker >nul 2>&1
if errorlevel 1 (
  echo ERROR: Docker Desktop is required.
  pause
  exit /b 1
)
docker compose down
if errorlevel 1 (
  echo ERROR: Could not stop the Vedas Learning services.
  pause
  exit /b 1
)
echo Vedas Learning services stopped. Database and audio volumes are preserved.
pause
