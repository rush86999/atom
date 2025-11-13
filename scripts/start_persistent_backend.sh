#!/bin/bash

# ATOM Platform - Persistent Backend Startup Script
# This script ensures the backend runs continuously with auto-restart

echo "🚀 Starting ATOM Backend with Persistent Mode"
echo "============================================="

# Kill any existing backend processes
echo "🔄 Cleaning up existing backend processes..."
pkill -f "python.*backend" || true
pkill -f "uvicorn" || true
sleep 2

# Set environment variables
export FLASK_ENV=development
export FLASK_SECRET_KEY=dev-secret-key-change-in-production
export DATABASE_URL=sqlite:///./data/atom_development.db
export PORT=8001

# Create necessary directories
mkdir -p data logs

# Start backend with auto-restart
echo "🔄 Starting backend on port 8001..."
while true; do
    echo "$(date): Starting backend server..."

    # Try to start the FastAPI backend first
    if [ -f "backend/fixed_main_api_app.py" ]; then
        python backend/fixed_main_api_app.py &
        BACKEND_PID=$!
        echo "Backend started with PID: $BACKEND_PID"
    else
        # Fallback to simple backend
        python start_simple_backend.py &
        BACKEND_PID=$!
        echo "Backend started with PID: $BACKEND_PID"
    fi

    # Wait for backend to be ready
    sleep 5

    # Check if backend is responding
    if curl -s http://localhost:8001/health > /dev/null; then
        echo "✅ Backend is healthy and responding"
        echo "📊 Backend running on: http://localhost:8001"
        echo "📚 API Docs available at: http://localhost:8001/docs"
        echo "🔍 Health check: http://localhost:8001/health"

        # Monitor the backend process
        wait $BACKEND_PID
        EXIT_CODE=$?
        echo "⚠️ Backend process exited with code: $EXIT_CODE"
        echo "🔄 Restarting backend in 3 seconds..."
        sleep 3
    else
        echo "❌ Backend failed to start properly"
        kill $BACKEND_PID 2>/dev/null || true
        echo "🔄 Retrying in 5 seconds..."
        sleep 5
    fi
done
