@echo off
echo ==============================================
echo       Starting Ledger AI Services...
echo ==============================================

echo 1. Starting Python Backend API...
start "Ledger AI Backend API" cmd /k "cd backend && .\venv\Scripts\activate && uvicorn backend:app --reload"

echo 2. Starting React Frontend...
start "Ledger AI Frontend Server" cmd /k "cd frontend && npm run dev"

echo ==============================================
echo   All services have been started!
echo   * A new window opened for the Backend (Port 8000).
echo   * A new window opened for the Frontend (Port 5173).
echo   Please keep both black windows open!
echo ==============================================
pause
