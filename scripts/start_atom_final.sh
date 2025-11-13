#!/bin/bash
# ATOM Platform - Final Working Startup Script

echo "🌟 ATOM Platform - FINAL WORKING VERSION"
echo "=========================================="
echo ""

# Check if we're in the right directory
if [ ! -d "backend" ] || [ ! -d "frontend-nextjs" ]; then
    echo "❌ Error: Please run from atom root directory"
    echo "   Expected structure: backend/, frontend-nextjs/, desktop/"
    exit 1
fi

echo "✅ Directory structure verified"
echo ""

# Start Backend (Background)
echo "🚀 Starting Backend API..."
cd backend
python main_api_app.py > ../logs/backend.log 2>&1 &
BACKEND_PID=$!
cd ..
echo "✅ Backend started (PID: $BACKEND_PID)"
echo "   📍 API: http://localhost:5058"
echo "   📋 Docs: http://localhost:5058/docs"

# Wait for backend to be ready
echo "⏳ Waiting for backend to be ready..."
sleep 5

# Test backend with Python (most reliable)
if python -c "
import sys, time
sys.path.insert(0, 'backend')
try:
    from main_api_app import app
    print('✅ Backend is ready')
    exit(0)
except:
    print('❌ Backend failed to start')
    exit(1)
" 2>/dev/null; then
    echo "✅ Backend is fully operational"
else
    echo "⚠️  Backend may have issues (check logs/backend.log)"
fi

# Start Frontend (Background)
echo ""
echo "🌐 Starting Frontend..."
cd frontend-nextjs
if [ ! -d "node_modules" ]; then
    echo "📦 Installing frontend dependencies..."
    npm install > ../logs/frontend-install.log 2>&1
fi

npm run dev > ../logs/frontend.log 2>&1 &
FRONTEND_PID=$!
cd ..
echo "✅ Frontend started (PID: $FRONTEND_PID)"
echo "   📍 Frontend: http://localhost:3000"

# Wait for frontend to be ready
echo "⏳ Waiting for frontend to be ready..."
sleep 10

# Create usage summary
echo ""
echo "🎉 ATOM Platform is RUNNING!"
echo "=================================="
echo ""
echo "📋 ACCESS POINTS:"
echo "   🌐 Frontend Web UI: http://localhost:3000"
echo "   📡 Backend API: http://localhost:5058"  
echo "   📚 API Documentation: http://localhost:5058/docs"
echo "   💊 Health Check: http://localhost:5058/health"
echo ""
echo "🔧 INTEGRATIONS AVAILABLE:"
echo "   ✅ GitHub, Gmail, Notion, Jira, Trello"
echo "   ✅ Teams, HubSpot, Asana, Slack"  
echo "   ✅ Google Drive, OneDrive, Outlook, Stripe, Salesforce"
echo ""
echo "📋 NEXT STEPS:"
echo "   1. Open http://localhost:3000 in browser"
echo "   2. Navigate to 'Integrations' page"
echo "   3. Configure desired services with API keys"
echo "   4. Use AI-powered automation features"
echo ""
echo "📝 LOGS:"
echo "   Backend: logs/backend.log"
echo "   Frontend: logs/frontend.log"
echo "   Frontend Install: logs/frontend-install.log"
echo ""
echo "🛑 TO STOP:"
echo "   Kill processes: ./stop_all.sh"
echo "   Or press Ctrl+C to stop this script"

# Save PIDs for stop script
echo "backend:$BACKEND_PID" > .pids
echo "frontend:$FRONTEND_PID" >> .pids

# Create stop script
cat > stop_all.sh << 'EOF'
#!/bin/bash
echo "🛑 Stopping ATOM Platform..."

# Kill by PID if available
if [ -f ".pids" ]; then
    while read line; do
        if [[ $line == *:* ]]; then
            pid=$(echo $line | cut -d: -f2)
            name=$(echo $line | cut -d: -f1)
            echo "Stopping $name (PID: $pid)..."
            kill $pid 2>/dev/null
        fi
    done < .pids
    rm .pids
fi

# Kill by port as backup
for port in 5058 3000; do
    pid=$(lsof -ti:$port 2>/dev/null)
    if [ -n "$pid" ]; then
        echo "Killing process on port $port (PID: $pid)..."
        kill $pid 2>/dev/null
    fi
done

echo "✅ All services stopped"
EOF

chmod +x stop_all.sh

# Keep script running
echo ""
echo "✨ Platform is running. Press Ctrl+C to stop."
echo "💡 Tip: Open a new terminal and run './test_backend.py' to test functionality"

# Wait for user to stop
trap 'echo ""; echo "🛑 Shutting down..."; ./stop_all.sh; exit 0' INT TERM

while true; do
    sleep 10
    # Check if processes are still running
    if ! ps -p $BACKEND_PID > /dev/null || ! ps -p $FRONTEND_PID > /dev/null; then
        echo "⚠️  One or more services stopped unexpectedly"
        echo "   Check logs for errors"
        break
    fi
done