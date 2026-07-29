@echo off
setlocal
set ROOT=%~dp0

echo ==================================================
echo   Q7 - Trading Engine
echo ==================================================
echo.
echo [1/2] Starting Backend (FastAPI on :8005)...
start "Q7-Backend" cmd /c "cd /d %ROOT%backend && python -m uvicorn app.main:app --host 127.0.0.1 --port 8005"
echo.

echo [2/2] Starting Frontend (Vite on :5173)...
start "Q7-Frontend" cmd /c "cd /d %ROOT%frontend && npx vite --host 127.0.0.1 --port 5174"
echo.

timeout /t 3 >nul
start http://127.0.0.1:5174
echo.
echo Dashboard opened in browser.
echo Close this window to keep services running.
echo.
pause
