@echo off
setlocal EnableDelayedExpansion

echo.
echo  AI-OS v2 — Setup
echo  ================
echo.

:: Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Install Python 3.10+ from https://python.org
    pause
    exit /b 1
)
echo [OK] Python found

:: Check Node
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Node.js not found. Install Node.js 18+ from https://nodejs.org
    pause
    exit /b 1
)
echo [OK] Node.js found

:: Python dependencies
echo.
echo Installing Python dependencies...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] pip install failed
    pause
    exit /b 1
)
echo [OK] Python dependencies installed

:: .env setup
if not exist .env (
    copy .env.example .env >nul
    echo [OK] Created .env from example
    echo.
    echo  !! Open .env and add your ANTHROPIC_API_KEY before starting.
    echo  !! Get your key at https://console.anthropic.com
) else (
    echo [OK] .env already exists
)

:: Frontend dependencies
echo.
echo Installing frontend dependencies...
cd frontend
call npm install
if %errorlevel% neq 0 (
    echo [ERROR] npm install failed
    cd ..
    pause
    exit /b 1
)
call npm run build
if %errorlevel% neq 0 (
    echo [ERROR] frontend build failed
    cd ..
    pause
    exit /b 1
)
cd ..
echo [OK] Frontend dependencies installed and built

echo.
echo  Setup complete!
echo.
echo  Next steps:
echo    1. Open .env and fill in your API keys
echo    2. Fill in knowledge_base\thesis\investment_thesis.md
echo    3. Run: start.bat
echo.
pause
