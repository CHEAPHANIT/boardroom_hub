@echo off
cd /d "%~dp0frontend"
if not exist node_modules (
  echo Installing npm packages...
  call npm install
)
echo.
echo  App: http://localhost:5173   (the Flask API must be running on port 5000)
echo.
call npm run dev
pause
