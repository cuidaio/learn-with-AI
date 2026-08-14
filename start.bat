@echo off
title learn-with-AI Launcher

echo ============================================
echo        learn-with-AI   Launcher
echo ============================================
echo.

REM == 1. Check .env ==
if not exist ".env" (
    echo [INFO] .env not found, copying from template...
    copy ".env.example" ".env" >nul
    echo.
    echo [ACTION] Please open .env in a editor and fill in YOUR OWN:
    echo          - EMBEDDING_BASE_URL / EMBEDDING_API_KEY / EMBEDDING_MODEL
    echo          - LLM_BASE_URL       / LLM_API_KEY       / LLM_MODEL
    echo.
    echo Then re-run this script.
    echo.
    pause
    exit /b 1
)

REM == 2. Check Docker CLI installed ==
where docker >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker not installed. Download Docker Desktop first:
    echo         https://www.docker.com/products/docker-compose/
    pause
    exit /b 1
)

REM == 3. Check Docker daemon running ==
docker version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker is installed but not running.
    echo         Please start Docker Desktop, wait until it says "Docker is running", then re-run this script.
    pause
    exit /b 1
)

REM == 4. Detect compose command (v2 first, fallback to v1) ==
docker compose version >nul 2>&1
if errorlevel 1 (
    set "COMPOSE=docker-compose"
) else (
    set "COMPOSE=docker compose"
)

echo [START] Pulling images and building (first run takes a few minutes)...
%COMPOSE% up -d
if errorlevel 1 (
    echo.
    echo [ERROR] Start failed. Common causes:
    echo         - Invalid API key in .env
    echo         - Port 5173 / 7480 / 5432 / 6379 already in use
    pause
    exit /b 1
)

echo.
echo ============================================
echo  Done! Open in browser:
echo.
echo    Frontend : http://localhost:5173
echo    Backend  : http://localhost:7480
echo    API Docs : http://localhost:7480/docs
echo ============================================
echo.
echo View logs : %COMPOSE% logs -f backend
echo Stop       : %COMPOSE% down
echo.
pause
