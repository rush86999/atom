#!/usr/bin/env bash
set -euo pipefail

# Atom Dev Launcher
# Run: ./scripts/dev.sh
# Starts the FULL app (main_api_app) + frontend in one command.
# Ports are overridable: BACKEND_PORT=9000 FRONTEND_PORT=4000 ./scripts/dev.sh

BACKEND_PORT="${BACKEND_PORT:-8001}"
FRONTEND_PORT="${FRONTEND_PORT:-3001}"

cd "$(dirname "$0")/.."

echo "🚀 Starting Atom (backend + frontend)"
echo "====================================="

# Check .env exists
if [ ! -f "backend/.env" ]; then
    echo "❌ backend/.env not found. Run ./scripts/quickstart.sh first."
    exit 1
fi

# Start backend (the FULL app — same as `make backend`)
echo "Starting backend on :$BACKEND_PORT..."
cd backend
if [ -d "venv" ]; then
    source venv/bin/activate
fi
PYTHONPATH=..:. python -m uvicorn main_api_app:app --reload --port "$BACKEND_PORT" &
BACKEND_PID=$!
cd ..

# Start frontend
echo "Starting frontend on :$FRONTEND_PORT..."
cd frontend-nextjs
npm run dev -- -p "$FRONTEND_PORT" &
FRONTEND_PID=$!
cd ..

echo ""
echo "✅ Atom is running!"
echo "   Frontend: http://localhost:$FRONTEND_PORT"
echo "   Backend:  http://localhost:$BACKEND_PORT"
echo "   Swagger:  http://localhost:$BACKEND_PORT/docs"
echo ""
echo "   Admin sign-in: admin@example.com (password in backend/logs/bootstrap_admin_password.txt)"
echo ""
echo "Press Ctrl+C to stop both."

# Trap Ctrl+C and kill both processes (and their children)
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" INT TERM
wait
