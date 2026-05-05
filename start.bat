@echo off
echo.
echo  AI-OS v2 — Starting servers
echo  ============================
echo.

if not exist .env (
    echo [ERROR] .env not found. Run setup.bat first.
    pause
    exit /b 1
)

:: Kill anything already on these ports
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000 "') do taskkill /f /pid %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":3000 "') do taskkill /f /pid %%a >nul 2>&1

echo Starting FastAPI backend on http://localhost:8000 ...
start "AI-OS Backend" cmd /k "cd /d %~dp0 && uvicorn api.main:app --port 8000"

timeout /t 5 /nobreak >nul

echo Starting Next.js frontend on http://localhost:3000 ...
echo NOTE: Uses production mode (npm run start) for stability.
echo       If you changed frontend code, run: cd frontend && npm run build first.
start "AI-OS Frontend" cmd /k "cd /d %~dp0frontend && npm run start"

echo.
echo  Both servers are starting in separate windows.
echo.
echo  Open http://localhost:3000 in your browser.
echo  API docs at http://localhost:8000/docs
echo.
