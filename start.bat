@echo off
echo Starting E-AI Media Intelligence Platform...
echo.

echo [1/2] Starting FastAPI backend on port 8000...
start "E-AI Backend" cmd /k "cd /d "%~dp0backend" && venv\Scripts\uvicorn main:app --reload --port 8000"

timeout /t 3 /nobreak >nul

echo [2/2] Starting Next.js frontend on port 3000...
start "E-AI Frontend" cmd /k "cd /d "%~dp0frontend" && npm run dev"

echo.
echo Both servers are starting:
echo   Backend:  http://localhost:8000
echo   Frontend: http://localhost:3000
echo   API Docs: http://localhost:8000/docs
echo.
pause
