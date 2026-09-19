@echo off
echo Starting LANDSYNC Backend and Frontend...
echo.

start "LANDSYNC Backend" cmd /k "cd backend && python main.py"
start "LANDSYNC Frontend" cmd /k "npm run dev"

echo Both services started in separate windows.
echo Close each window to stop services.
