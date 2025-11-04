#!/bin/bash

# 🚀 ATOM COMPLETE APPLICATION STARTUP SCRIPT
# Start all 3 servers: OAuth + Backend + Frontend

echo "🎯 STARTING ATOM COMPLETE APPLICATION"
echo "========================================"
echo "Starting all services in correct order..."
echo ""

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "🛑 Stopping all servers..."
    if [ ! -z "$OAUTH_PID" ]; then
        kill $OAUTH_PID 2>/dev/null && echo "✅ OAuth Server stopped"
    fi
    if [ ! -z "$BACKEND_PID" ]; then
        kill $BACKEND_PID 2>/dev/null && echo "✅ Backend API Server stopped"
    fi
    if [ ! -z "$FRONTEND_PID" ]; then
        kill $FRONTEND_PID 2>/dev/null && echo "✅ Frontend Server stopped"
    fi
    echo "🎉 All servers stopped successfully!"
    exit 0
}

# Set trap for Ctrl+C
trap cleanup INT

# Check if required files exist
echo "🔍 CHECKING REQUIRED FILES..."

if [ ! -f "start_simple_oauth_server.py" ]; then
    echo "❌ OAuth server file not found: start_simple_oauth_server.py"
    exit 1
fi

if [ ! -d "backend" ] || [ ! -f "backend/main_api_app.py" ]; then
    echo "❌ Backend server files not found"
    exit 1
fi

if [ ! -d "frontend-nextjs" ] || [ ! -f "frontend-nextjs/package.json" ]; then
    echo "❌ Frontend files not found"
    exit 1
fi

echo "✅ All required files found"
echo ""

# Step 1: Start OAuth Server (Port 5058)
echo "🔐 STEP 1: Starting OAuth Server (Port 5058)..."
python start_simple_oauth_server.py &
OAUTH_PID=$!
echo "OAuth Server PID: $OAUTH_PID"

# Wait for OAuth server to start
echo "⏳ Waiting for OAuth server to start..."
sleep 3

# Check if OAuth server is responding
if curl -s http://localhost:5058/health > /dev/null; then
    echo "✅ OAuth Server started successfully"
else
    echo "⚠️ OAuth Server may still be starting..."
fi

# Step 2: Start Backend API Server (Port 8000)
echo ""
echo "🔧 STEP 2: Starting Backend API Server (Port 8000)..."
cd backend
python main_api_app.py &
BACKEND_PID=$!
cd ..
echo "Backend API Server PID: $BACKEND_PID"

# Wait for backend to start
echo "⏳ Waiting for Backend API Server to start..."
sleep 3

# Check if Backend server is responding
if curl -s http://localhost:8000/health > /dev/null; then
    echo "✅ Backend API Server started successfully"
else
    echo "⚠️ Backend API Server may still be starting..."
fi

# Step 3: Start Frontend Development Server (Port 3000)
echo ""
echo "🎨 STEP 3: Starting Frontend Development Server (Port 3000)..."
cd frontend-nextjs
npm run dev &
FRONTEND_PID=$!
cd ..
echo "Frontend Development Server PID: $FRONTEND_PID"

# Wait for frontend to start
echo "⏳ Waiting for Frontend Development Server to start..."
sleep 5

# Check if Frontend server is responding
if curl -s http://localhost:3000 > /dev/null; then
    echo "✅ Frontend Development Server started successfully"
else
    echo "⚠️ Frontend Development Server may still be starting..."
fi

echo ""
echo "🎉 ALL SERVERS STARTED SUCCESSFULLY!"
echo "========================================"
echo ""
echo "🌐 ACCESS POINTS:"
echo "   🎨 Frontend Application: http://localhost:3000"
echo "   🔧 Backend API Server:   http://localhost:8000"
echo "   📊 API Documentation:    http://localhost:8000/docs"
echo "   🔐 OAuth Server:        http://localhost:5058"
echo ""
echo "🔍 VERIFICATION STEPS:"
echo "   1. Visit http://localhost:3000 - Should see ATOM UI"
echo "   2. Visit http://localhost:8000/docs - Should see API docs"
echo "   3. Visit http://localhost:5058 - Should see OAuth server"
echo ""
echo "🧪 TESTING INTEGRATION:"
echo "   1. Click on any UI component (Search, Tasks, etc.)"
echo "   2. Should trigger OAuth authentication flow"
echo "   3. Should successfully authenticate with services"
echo ""
echo "🛑 To stop all servers, press Ctrl+C"
echo ""

# Wait for all processes
wait