#!/usr/bin/env bash
set -euo pipefail

# Atom Dev Launcher
# Run: ./scripts/dev.sh
# Starts backend + frontend in one command.

cd "$(dirname "$0")/.."

echo "🚀 Starting Atom (backend + frontend)"
echo "====================================="

# Check .env exists
if [ ! -f "backend/.env" ]; then
    echo "❌ backend/.env not found. Run ./scripts/quickstart.sh first."
    exit 1
fi

# Start backend
echo "Starting backend on :8000..."
cd backend
if [ -d "venv" ]; then
    source venv/bin/activate
fi
# NOTE: this launches the MINIMAL app (~125 routes, fast smoke bootstrap).
# For the full app (all features), use `make backend` or run main_api_app:app.
PYTHONPATH=..:. python -m uvicorn minimal_app:app --reload --port 8000 &
BACKEND_PID=$!
cd ..

# Start frontend
echo "Starting frontend on :3000..."
cd frontend-nextjs
npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo "✅ Atom is running!"
echo "   Frontend: http://localhost:3000"
echo "   Backend:  http://localhost:8000"
echo "   Swagger:  http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop both."

# Trap Ctrl+C and kill both processes
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" INT TERM
wait
