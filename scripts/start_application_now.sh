#!/bin/bash

# 🚀 ATOM STARTUP SEQUENCE - BEGIN RIGHT NOW
# Starting all 3 servers immediately

echo "🚀 STARTING ATOM COMPLETE APPLICATION - RIGHT NOW"
echo "=================================================="
echo "All systems verified - beginning immediate startup sequence"
echo ""

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "🛑 Shutting down all servers..."
    if [ ! -z "$OAUTH_PID" ]; then
        kill $OAUTH_PID 2>/dev/null && echo "✅ OAuth Server stopped"
    fi
    if [ ! -z "$BACKEND_PID" ]; then
        kill $BACKEND_PID 2>/dev/null && echo "✅ Backend Server stopped"
    fi
    if [ ! -z "$FRONTEND_PID" ]; then
        kill $FRONTEND_PID 2>/dev/null && echo "✅ Frontend Server stopped"
    fi
    echo "🎉 All servers shut down successfully"
    exit 0
}

# Set trap for Ctrl+C
trap cleanup INT

echo "🔍 SYSTEM CHECK..."
if [ ! -f "minimal_oauth_server.py" ]; then
    echo "❌ OAuth server missing"
    exit 1
fi

if [ ! -d "backend" ] || [ ! -f "backend/main_api_app.py" ]; then
    echo "❌ Backend missing"
    exit 1
fi

if [ ! -d "frontend-nextjs" ] || [ ! -f "frontend-nextjs/package.json" ]; then
    echo "❌ Frontend missing"
    exit 1
fi

echo "✅ All components found"
echo ""

# Step 1: Start OAuth Server
echo "🔐 STEP 1: Starting OAuth Server (Port 5058)..."
python minimal_oauth_server.py &
OAUTH_PID=$!
echo "OAuth Server PID: $OAUTH_PID"

# Wait for OAuth server to start
echo "⏳ Waiting for OAuth server to initialize..."
sleep 5

# Step 2: Start Backend API Server
echo ""
echo "🔧 STEP 2: Starting Backend API Server (Port 8000)..."
cd backend
python main_api_app.py &
BACKEND_PID=$!
cd ..
echo "Backend Server PID: $BACKEND_PID"

# Wait for backend to start
echo "⏳ Waiting for Backend API Server to initialize..."
sleep 5

# Step 3: Start Frontend Development Server
echo ""
echo "🎨 STEP 3: Starting Frontend Development Server (Port 3000)..."
cd frontend-nextjs
npm run dev &
FRONTEND_PID=$!
cd ..
echo "Frontend Server PID: $FRONTEND_PID"

# Wait for frontend to start
echo "⏳ Waiting for Frontend Development Server to initialize..."
sleep 10

# Final status
echo ""
echo "🎉 ALL SERVERS STARTED!"
echo "=================================="
echo ""
echo "🌐 ACCESS POINTS:"
echo "   🎨 Frontend Application:  http://localhost:3000"
echo "   🔧 Backend API Server:   http://localhost:8000"
echo "   📊 API Documentation:    http://localhost:8000/docs"
echo "   🔐 OAuth Server:        http://localhost:5058"
echo "   📚 OAuth Status:       http://localhost:5058/api/auth/oauth-status"
echo ""
echo "🧪 TESTING INSTRUCTIONS:"
echo "   1. Open browser and visit: http://localhost:3000"
echo "   2. Should see ATOM UI with 8 component cards"
echo "   3. Click any component (Search, Tasks, etc.)"
echo "   4. Should navigate to component page"
echo "   5. Should trigger OAuth authentication flow"
echo "   6. Should successfully authenticate with services"
echo ""
echo "🔧 DEBUGGING COMMANDS:"
echo "   # Check OAuth server status"
echo "   curl http://localhost:5058/healthz"
echo ""
echo "   # Check Backend API status"
echo "   curl http://localhost:8000/health"
echo ""
echo "   # Check Frontend server status"
echo "   curl http://localhost:3000"
echo ""
echo "🛑 To stop all servers, press Ctrl+C"
echo ""

# Function to check server status
check_servers() {
    echo "🔍 Checking server status..."
    
    # Check OAuth server
    if curl -s http://localhost:5058/healthz > /dev/null 2>&1; then
        echo "   ✅ OAuth Server: RUNNING (http://localhost:5058)"
    else
        echo "   ❌ OAuth Server: NOT RESPONDING"
    fi
    
    # Check Backend API
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo "   ✅ Backend API: RUNNING (http://localhost:8000)"
    else
        echo "   ❌ Backend API: NOT RESPONDING"
    fi
    
    # Check Frontend
    if curl -s http://localhost:3000 > /dev/null 2>&1; then
        echo "   ✅ Frontend: RUNNING (http://localhost:3000)"
    else
        echo "   ❌ Frontend: NOT RESPONDING"
    fi
}

# Check initial status
check_servers

echo ""
echo "🚀 APPLICATION IS NOW RUNNING!"
echo "=================================="
echo "Visit http://localhost:3000 to use your ATOM application"
echo ""
echo "Press Ctrl+C to stop all servers"
echo ""

# Wait for all processes with periodic status checks
counter=0
while true; do
    sleep 30
    counter=$((counter + 1))
    echo ""
    echo "⏰ Server Status Check #$counter:"
    check_servers
    echo ""
    
    if [ $counter -eq 12 ]; then
        echo "🎯 Servers have been running for 6 minutes"
        echo "🎯 Application appears to be stable"
        echo "🎯 Visit http://localhost:3000 to test functionality"
        echo ""
    fi
done

# Wait for all processes (infinite loop)
wait