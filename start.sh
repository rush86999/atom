#!/bin/bash

# Atom Personal Edition - One-Command Start
# Starts both backend and frontend with a single command

set -e

echo "╔════════════════════════════════════════════════════════════╗"
echo "║  🚀 Atom Personal Edition - Starting...                       ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Check prerequisites
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Please install Python 3.11+"
    exit 1
fi

if ! command -v npm &> /dev/null; then
    echo "❌ npm not found. Please install Node.js"
    exit 1
fi

# Check if backend venv exists
if [ ! -d "backend/venv" ]; then
    echo "❌ Backend not installed. Running install script first..."
    ./install-native.sh
    echo ""
fi

# Function to cleanup background processes on exit
cleanup() {
    echo ""
    echo "🛑 Stopping Atom..."

    # Kill backend
    if [ -n "$BACKEND_PID" ]; then
        kill $BACKEND_PID 2>/dev/null || true
        echo "✅ Backend stopped"
    fi

    # Kill frontend
    if [ -n "$FRONTEND_PID" ]; then
        kill $FRONTEND_PID 2>/dev/null || true
        echo "✅ Frontend stopped"
    fi

    echo "👋 Atom stopped. Goodbye!"
}

# Set trap for cleanup
trap cleanup EXIT INT TERM

# Start backend in background
echo "📊 Starting backend..."
cd backend
source venv/bin/activate

# Check if port 8000 is in use, if so use 8001
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    echo "⚠️  Port 8000 in use, using port 8001"
    PORT=8001
else
    PORT=8000
fi

python -m uvicorn main_api_app:app --host 0.0.0.0 --port $PORT --reload > /tmp/atom-backend.log 2>&1 &
BACKEND_PID=$!

echo "✅ Backend starting on port $PORT (PID: $BACKEND_PID)"
echo "   Logs: tail -f /tmp/atom-backend.log"

cd ..

# Give backend a moment to start
sleep 3

# Start frontend in background
echo "🎨 Starting frontend..."
cd frontend-nextjs

# Check if port 3000 is in use, if so use 3001
if lsof -Pi :3000 -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    echo "⚠️  Port 3000 in use, using port 3001"
    PORT=3001
else
    PORT=3000
fi

npm run dev > /tmp/atom-frontend.log 2>&1 &
FRONTEND_PID=$!

echo "✅ Frontend starting on port $PORT (PID: $FRONTEND_PID)"
echo "   Logs: tail -f /tmp/atom-frontend.log"

cd ..

# Wait a moment for services to start
sleep 3

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║  ✅ Atom is Running!                                         ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "🌐 Dashboard:      http://localhost:$((PORT-2000))"
echo "🔌 Backend API:    http://localhost:$PORT"
echo "📚 API Docs:      http://localhost:$PORT/docs"
echo ""
echo "📋 View Logs:"
echo "   Backend:  tail -f /tmp/atom-backend.log"
echo "   Frontend: tail -f /tmp/atom-frontend.log"
echo ""
echo "🛑 To Stop: Press Ctrl+C"
echo ""

# Keep script running
wait
