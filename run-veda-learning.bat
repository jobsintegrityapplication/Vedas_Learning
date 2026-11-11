@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "API_PORT=8000"
set "WEB_PORT=8080"
set "MAILHOG_UI_PORT=8025"

if not exist ".env" (
  if not exist ".env.example" (
    echo ERROR: .env.example is missing.
    pause
    exit /b 1
  )
  echo Creating local .env from .env.example. Existing .env files are never overwritten.
  copy /y ".env.example" ".env" >nul
  if errorlevel 1 (
    echo ERROR: Could not create .env.
    pause
    exit /b 1
  )
)

for /f "tokens=1,* delims==" %%A in ('findstr /b "HOST_API_PORT=" ".env"') do set "API_PORT=%%B"
for /f "tokens=1,* delims==" %%A in ('findstr /b "HOST_WEB_PORT=" ".env"') do set "WEB_PORT=%%B"
for /f "tokens=1,* delims==" %%A in ('findstr /b "HOST_MAILHOG_UI_PORT=" ".env"') do set "MAILHOG_UI_PORT=%%B"

where docker >nul 2>&1
if errorlevel 1 (
  echo ERROR: Docker Desktop is required. Install it, then run this file again.
  pause
  exit /b 1
)

docker info >nul 2>&1
if errorlevel 1 (
  echo Docker Desktop is installed but its engine is stopped. Trying to start Docker Desktop...
  if exist "%ProgramFiles%\Docker\Docker\Docker Desktop.exe" (
    start "Docker Desktop" "%ProgramFiles%\Docker\Docker\Docker Desktop.exe"
  ) else if exist "%LocalAppData%\Programs\DockerDesktop\Docker Desktop.exe" (
    start "Docker Desktop" "%LocalAppData%\Programs\DockerDesktop\Docker Desktop.exe"
  ) else (
    echo ERROR: Start Docker Desktop manually, wait for it to finish starting, then rerun this file.
    pause
    exit /b 1
  )
)

echo Waiting for Docker Desktop...
set /a DOCKER_TRIES=0
:wait_docker
docker info >nul 2>&1
if not errorlevel 1 goto docker_ready
set /a DOCKER_TRIES+=1
if %DOCKER_TRIES% geq 60 (
  echo ERROR: Docker did not become ready. Check Docker Desktop and try again.
  pause
  exit /b 1
)
timeout /t 5 /nobreak >nul
goto wait_docker

:docker_ready
echo Starting Vedas Learning services and building the web app. First run may take several minutes...
docker compose up --build -d
if errorlevel 1 (
  echo ERROR: Startup failed. Recent service logs:
  docker compose logs --tail=100
  pause
  exit /b 1
)

echo Waiting for the API and web app to become ready...
set /a READY_TRIES=0
:wait_ready
curl.exe -fsS "http://127.0.0.1:%API_PORT%/ready" >nul 2>&1
if errorlevel 1 goto retry_ready
curl.exe -fsS "http://127.0.0.1:%WEB_PORT%/" >nul 2>&1
if not errorlevel 1 goto app_ready

:retry_ready
set /a READY_TRIES+=1
if %READY_TRIES% geq 90 (
  echo ERROR: The app did not become ready. Recent service logs:
  docker compose logs --tail=100
  pause
  exit /b 1
)
timeout /t 2 /nobreak >nul
goto wait_ready

:app_ready
echo Vedas Learning is ready at http://127.0.0.1:%WEB_PORT%
echo Local email inbox for verification codes: http://127.0.0.1:%MAILHOG_UI_PORT%
start "" "http://127.0.0.1:%WEB_PORT%/"
start "" "http://127.0.0.1:%MAILHOG_UI_PORT%/"
echo The services keep running after this window closes. To stop them, run stop-veda-learning.bat.
pause
exit /b 0
