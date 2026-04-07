#!/bin/bash
# ==========================================
# ATOM Platform - Dual-App Startup Manager
# ==========================================
# This script launches both the Next.js frontend and FastAPI backend 
# and ensures signal propagation for a clean shutdown.

# Fail if any command exits with a non-zero status
set -e

# Logging function
log() {
    echo -e "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# 1. Start Python Backend (Uvicorn)
log "🚀 Starting Python Backend on Port 8000..."
# Navigate to backend directory and start
cd /app/backend
# Use gunicorn with uvicorn workers for production stability
# OR uvicorn directly if gunicorn is not in requirements
python -m uvicorn main_api_app:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
log "✓ Backend PID: $BACKEND_PID"

# 2. Wait for Backend to initialize (optional brief sleep)
sleep 2

# 3. Start Next.js Frontend (Standalone Server)
log "🚀 Starting Next.js Frontend on Port 3000..."
# Standalone Next.js creates its own server.js
cd /app/frontend-nextjs
node server.js &
FRONTEND_PID=$!
log "✓ Frontend PID: $FRONTEND_PID"

# Capture Interrupt/Terminate signals
trap "kill -TERM $BACKEND_PID $FRONTEND_PID" SIGINT SIGTERM

# Wait for any process to exit
wait -n

# If one crashes, kill the other and exit
log "⚠️  One of the processes exited. Shutting down..."
kill -TERM $BACKEND_PID $FRONTEND_PID
exit 1
