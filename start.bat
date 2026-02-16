@echo off
REM Atom Personal Edition - One-Command Start (Windows)
REM Starts both backend and frontend with a single command

echo ╔════════════════════════════════════════════════════════════╗
echo ║  🚀 Atom Personal Edition - Starting...                       ║
echo ╚════════════════════════════════════════════════════════════╝
echo.

REM Check prerequisites
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python 3 not found. Please install Python 3.11+
    pause
    exit /b 1
)

npm --version >nul 2>&1
if errorlevel 1 (
    echo ❌ npm not found. Please install Node.js
    pause
    exit /b 1
)

REM Check if backend venv exists
if not exist "backend\venv" (
    echo ❌ Backend not installed. Running install script first...
    install-native.bat
    echo.
)

REM Function to cleanup processes
goto :start

:cleanup
echo.
echo 🛑 Stopping Atom...

if defined BACKEND_PID (
    taskkill /PID %BACKEND_PID% /F >nul 2>&1
    echo ✅ Backend stopped
)

if defined FRONTEND_PID (
    taskkill /PID %FRONTEND_PID% /F >nul 2>&1
    echo ✅ Frontend stopped
)

echo 👋 Atom stopped. Goodbye!
goto :end

:start
REM Start backend in background
echo 📊 Starting backend...
cd backend

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Check if port 8000 is in use
netstat -ano | findstr :8000 | findstr LISTENING >nul 2>&1
if errorlevel 0 (
    echo ⚠️  Port 8000 in use, using port 8001
    set PORT=8001
) else (
    set PORT=8000
)

start /B python -m uvicorn main_api_app:app --host 0.0.0.0 --port %PORT% --reload
set BACKEND_PID=%ERRORLEVEL%

echo ✅ Backend starting on port %PORT%
cd ..

REM Give backend a moment to start
timeout /t 3 /nobreak >nul

REM Start frontend in background
echo 🎨 Starting frontend...
cd frontend-nextjs

REM Check if port 3000 is in use
netstat -ano | findstr :3000 | findstr LISTENING >nul 2>&1
if errorlevel 0 (
    echo ⚠️  Port 3000 in use, using port 3001
    set /A FRONT_PORT=3001
) else (
    set /A FRONT_PORT=3000
)

start /B npm run dev
set FRONTEND_PID=%ERRORLEVEL%

echo ✅ Frontend starting on port %FRONT_PORT%
cd ..

REM Wait a moment for services to start
timeout /t 3 /nobreak >nul

echo.
echo ╔════════════════════════════════════════════════════════════╗
echo ║  ✅ Atom is Running!                                         ║
echo ╚════════════════════════════════════════════════════════════╝
echo.
echo 🌐 Dashboard:      http://localhost:%FRONT_PORT%
echo 🔌 Backend API:    http://localhost:%PORT%
echo 📚 API Docs:      http://localhost:%PORT%/docs
echo.
echo 📋 View Logs:
echo    Backend:  Check backend terminal
echo    Frontend: Check frontend terminal
echo.
echo 🛑 To Stop: Close this window or press Ctrl+C
echo.

REM Wait indefinitely
pause
goto :cleanup

:end
