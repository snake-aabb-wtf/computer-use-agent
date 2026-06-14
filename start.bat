@echo off
title Computer Use Agent
cd /d "%~dp0"

echo ============================================
echo   Computer Use Agent - Startup
echo ============================================
echo.

:: Check if venv exists
if exist "venv\Scripts\activate.bat" (
    echo [OK] Virtual environment found
    call venv\Scripts\activate.bat
    echo [OK] Activated venv
) else (
    echo [..] Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo [FAIL] Failed to create venv
        pause
        exit /b 1
    )
    echo [OK] Virtual environment created

    echo [..] Installing dependencies...
    call venv\Scripts\activate.bat
    pip install -r requirements.txt
    if errorlevel 1 (
        echo [FAIL] Failed to install dependencies
        pause
        exit /b 1
    )
    echo [OK] Dependencies installed
)

echo.
echo [..] Starting Computer Use Agent...
echo.
python -X utf8 -m computer_use_agent %*
pause
