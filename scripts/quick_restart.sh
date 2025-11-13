#!/bin/bash

# 🚀 ATOM QUICK RESTART SCRIPT
# Clean restart of all services for immediate testing

echo "🔄 ATOM QUICK RESTART"
echo "======================"
echo "Stopping all services and starting fresh..."
echo ""

# Stop all running services
echo "🛑 Stopping all services..."
pkill -f "start_simple_oauth_server.py" 2>/dev/null && echo "✅ OAuth Server stopped"
pkill -f "main_api_app.py" 2>/dev/null && echo "✅ Backend API stopped"
pkill -f "fixed_main_api_app.py" 2>/dev/null && echo "✅ Fixed Backend API stopped"
pkill -f "next dev" 2>/dev/null && echo "✅ Frontend stopped"

# Wait a moment
sleep 2

# Start OAuth Server
echo ""
echo "🔐 Starting OAuth Server..."
python start_simple_oauth_server.py &
OAUTH_PID=$!
echo "OAuth Server PID: $OAUTH_PID"
sleep 3

# Start Backend API
echo ""
echo "🔧 Starting Backend API..."
cd backend
python main_api_app.py &
BACKEND_PID=$!
cd ..
echo "Backend API PID: $BACKEND_PID"
sleep 3

# Start Frontend
echo ""
echo "🎨 Starting Frontend..."
cd frontend-nextjs
npm run dev &
FRONTEND_PID=$!
cd ..
echo "Frontend PID: $FRONTEND_PID"
sleep 5

# Verify services
echo ""
echo "🔍 Verifying services..."
curl -s http://localhost:5058/healthz >/dev/null && echo "✅ OAuth Server responding" || echo "❌ OAuth Server not responding"
curl -s http://localhost:8000/health >/dev/null && echo "✅ Backend API responding" || echo "❌ Backend API not responding"
curl -s http://localhost:3000 >/dev/null && echo "✅ Frontend responding" || echo "❌ Frontend not responding"

echo ""
echo "🎉 QUICK RESTART COMPLETE!"
echo "=========================="
echo ""
echo "🌐 Access Points:"
echo "   Frontend: http://localhost:3000"
echo "   API Docs: http://localhost:8000/docs"
echo "   OAuth:    http://localhost:5058"
echo ""
echo "🚀 Ready for immediate testing!"
