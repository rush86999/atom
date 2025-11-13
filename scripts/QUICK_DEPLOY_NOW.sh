#!/bin/bash

# 🚀 ATOM Platform - Quick Deployment Script
# Gets core systems running in under 5 minutes

set -e  # Exit on any error

echo "🚀 Starting ATOM Platform Quick Deployment..."
echo "=============================================="

# Kill any existing processes
echo "🛑 Stopping existing processes..."
pkill -f "python.*main_api_app.py" || true
pkill -f "improved_oauth_server.py" || true
pkill -f "next" || true
sleep 2

# Start Backend (Port 5058)
echo "🔧 Starting Backend API..."
cd backend/python-api-service
python main_api_app.py > ../backend.log 2>&1 &
BACKEND_PID=$!
echo $BACKEND_PID > ../backend.pid

# Wait for backend to start
echo "⏳ Waiting for backend to start..."
sleep 10

# Check backend health
echo "🔍 Checking backend health..."
if curl -s http://localhost:5058/healthz > /dev/null; then
    echo "✅ Backend is running on port 5058"
else
    echo "❌ Backend failed to start. Check backend.log for details."
    exit 1
fi

# Start Frontend (Port 3000)
echo "🎨 Starting Frontend..."
cd ../frontend-nextjs
npm run dev > ../frontend.log 2>&1 &
FRONTEND_PID=$!
echo $FRONTEND_PID > ../frontend.pid

# Wait for frontend to start
echo "⏳ Waiting for frontend to start..."
sleep 15

# Check frontend health
echo "🔍 Checking frontend health..."
if curl -s http://localhost:3000 > /dev/null; then
    echo "✅ Frontend is running on port 3000"
else
    echo "⚠️ Frontend may be starting slowly. Check frontend.log for details."
fi

# Test Core Endpoints
echo "🧪 Testing core endpoints..."
echo "----------------------------------------"

ENDPOINTS=(
    "/api/services"
    "/api/tasks"
    "/api/calendar/events"
    "/api/messages"
    "/api/workflows"
)

for endpoint in "${ENDPOINTS[@]}"; do
    if curl -s "http://localhost:5058${endpoint}" > /dev/null; then
        echo "✅ $endpoint - ACCESSIBLE"
    else
        echo "❌ $endpoint - NOT ACCESSIBLE"
    fi
done

# Show Service Status
echo ""
echo "📊 SERVICE STATUS:"
echo "----------------------------------------"
echo "Backend API:  http://localhost:5058"
echo "Frontend UI:  http://localhost:3000"
echo "Health Check: http://localhost:5058/healthz"
echo "Services:     http://localhost:5058/api/services"

# Save deployment info
echo ""
echo "📄 Deployment Information:"
echo "Backend PID: $BACKEND_PID"
echo "Frontend PID: $FRONTEND_PID"
echo "Backend Log: backend/backend.log"
echo "Frontend Log: frontend-nextjs/frontend.log"

echo ""
echo "🎉 Quick Deployment Complete!"
echo "Access your ATOM platform at: http://localhost:3000"
echo "=============================================="
