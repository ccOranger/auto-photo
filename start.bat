@echo off
echo ============================================
echo  Auto Photo - AI ????????
echo ============================================
echo.

echo [1/2] Starting backend server (port 8321)...
cd /d "%~dp0\backend"
start /b python start_server.py > nul 2>&1
echo Backend server starting...

echo.
echo Waiting for backend to be ready...
:wait_backend
python -c "import urllib.request; urllib.request.urlopen('http://localhost:8321/api/health',timeout=1)" > nul 2>&1
if %errorlevel% neq 0 (
    timeout /t 2 /nobreak > nul
    goto wait_backend
)
echo Backend ready!

echo.
echo [2/2] Starting frontend dev server (port 5173)...
cd /d "%~dp0\frontend"
start /b node node_modules\vite\bin\vite.js --port 5173 > nul 2>&1
echo Frontend dev server starting...

echo.
echo ============================================
echo Open in browser: http://localhost:5173
echo ============================================
echo.
pause
