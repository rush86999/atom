#!/bin/bash
# ATOM Platform Complete Startup Script
# Starts all components: Backend, Frontend, and Desktop

echo "🌟 ATOM Platform Complete Startup"
echo "=================================="
echo ""

# Configuration
BACKEND_PORT=${BACKEND_PORT:-5058}
FRONTEND_PORT=${FRONTEND_PORT:-3000}
START_BACKEND=${START_BACKEND:-true}
START_FRONTEND=${START_FRONTEND:-true}
START_DESKTOP=${START_DESKTOP:-false}

echo "⚙️  Configuration:"
echo "   Backend Port: $BACKEND_PORT"
echo "   Frontend Port: $FRONTEND_PORT"
echo "   Start Backend: $START_BACKEND"
echo "   Start Frontend: $START_FRONTEND"
echo "   Start Desktop: $START_DESKTOP"
echo ""

# Function to check if port is in use
check_port() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo "⚠️  Port $port is already in use"
        return 1
    fi
    return 0
}

# Function to wait for backend to start
wait_for_backend() {
    echo "⏳ Waiting for backend to start..."
    local max_attempts=30
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if curl -s http://localhost:$BACKEND_PORT/health > /dev/null 2>&1; then
            echo "✅ Backend is ready"
            return 0
        fi
        echo "   Attempt $attempt/$max_attempts..."
        sleep 2
        ((attempt++))
    done
    
    echo "❌ Backend failed to start within $max_attempts attempts"
    return 1
}

# Check dependencies
echo "🔍 Checking dependencies..."

# Check Node.js
if ! command -v node &> /dev/null; then
    echo "❌ Node.js is not installed"
    exit 1
fi
echo "✅ Node.js: $(node --version)"

# Check Python
if ! command -v python3 &> /dev/null && ! command -v python &> /dev/null; then
    echo "❌ Python is not installed"
    exit 1
fi

if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
else
    PYTHON_CMD="python"
fi
echo "✅ Python: $($PYTHON_CMD --version)"

# Check Rust (for desktop)
if [ "$START_DESKTOP" = "true" ]; then
    if ! command -v rustc &> /dev/null; then
        echo "❌ Rust is not installed (required for desktop)"
        exit 1
    fi
    echo "✅ Rust: $(rustc --version)"
fi

# Check ports
if [ "$START_BACKEND" = "true" ]; then
    if ! check_port $BACKEND_PORT; then
        echo "⚠️  Backend port $BACKEND_PORT is in use"
        echo "   You can set BACKEND_PORT environment variable"
        read -p "   Continue anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
fi

if [ "$START_FRONTEND" = "true" ]; then
    if ! check_port $FRONTEND_PORT; then
        echo "⚠️  Frontend port $FRONTEND_PORT is in use"
        echo "   You can set FRONTEND_PORT environment variable"
        read -p "   Continue anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
fi

# Start processes
echo ""
echo "🚀 Starting ATOM Platform components..."

# Create logs directory
mkdir -p logs

# Start backend
if [ "$START_BACKEND" = "true" ]; then
    echo "📡 Starting backend server..."
    
    # Check if backend startup script exists
    if [ ! -f "start_backend.py" ]; then
        echo "❌ Backend startup script not found"
        exit 1
    fi
    
    # Start backend in background
    $PYTHON_CMD start_backend.py > logs/backend.log 2>&1 &
    BACKEND_PID=$!
    echo "✅ Backend started (PID: $BACKEND_PID)"
    
    # Wait for backend to be ready
    if ! wait_for_backend; then
        echo "❌ Backend failed to start. Check logs/backend.log"
        kill $BACKEND_PID 2>/dev/null
        exit 1
    fi
fi

# Start frontend
if [ "$START_FRONTEND" = "true" ]; then
    echo "🌐 Starting frontend server..."
    
    # Check if frontend directory exists
    if [ ! -d "frontend-nextjs" ]; then
        echo "❌ Frontend directory not found"
        [ "$BACKEND_PID" ] && kill $BACKEND_PID 2>/dev/null
        exit 1
    fi
    
    # Start frontend in background
    cd frontend-nextjs && npm run dev > ../logs/frontend.log 2>&1 &
    FRONTEND_PID=$!
    cd ..
    echo "✅ Frontend started (PID: $FRONTEND_PID)"
    
    # Wait a moment for frontend to start
    sleep 5
fi

# Start desktop
if [ "$START_DESKTOP" = "true" ]; then
    echo "🖥️  Starting desktop app..."
    
    # Check if desktop directory exists
    if [ ! -d "desktop/tauri" ]; then
        echo "❌ Desktop directory not found"
        [ "$BACKEND_PID" ] && kill $BACKEND_PID 2>/dev/null
        [ "$FRONTEND_PID" ] && kill $FRONTEND_PID 2>/dev/null
        exit 1
    fi
    
    # Start desktop (in foreground since it's the main app)
    cd desktop/tauri
    npm run tauri:dev > ../../logs/desktop.log 2>&1 &
    DESKTOP_PID=$!
    cd ..
    echo "✅ Desktop app started (PID: $DESKTOP_PID)"
fi

# Show startup information
echo ""
echo "🎉 ATOM Platform Started Successfully!"
echo "===================================="

if [ "$START_BACKEND" = "true" ]; then
    echo "📡 Backend API: http://localhost:$BACKEND_PORT"
    echo "   API Docs: http://localhost:$BACKEND_PORT/docs"
    echo "   Health Check: http://localhost:$BACKEND_PORT/health"
fi

if [ "$START_FRONTEND" = "true" ]; then
    echo "🌐 Frontend: http://localhost:$FRONTEND_PORT"
fi

if [ "$START_DESKTOP" = "true" ]; then
    echo "🖥️  Desktop App: Running in separate window"
fi

echo ""
echo "📋 Process Information:"
echo "   Backend PID: $BACKEND_PID"
echo "   Frontend PID: $FRONTEND_PID"
echo "   Desktop PID: $DESKTOP_PID"

echo ""
echo "📝 Logs:"
echo "   Backend: logs/backend.log"
echo "   Frontend: logs/frontend.log"
echo "   Desktop: logs/desktop.log"

echo ""
echo "🛑 To stop all services, run: ./stop_all.sh"
echo "   Or press Ctrl+C to stop the main process"

# Create stop script
cat > stop_all.sh << 'EOF'
#!/bin/bash
echo "🛑 Stopping ATOM Platform services..."

# Kill processes by PID if stored
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

# Kill by port
for port in 5058 3000; do
    pid=$(lsof -ti:$port 2>/dev/null)
    if [ -n "$pid" ]; then
        echo "Killing process on port $port (PID: $pid)..."
        kill $pid 2>/dev/null
    fi
done

# Kill by name
echo "Killing remaining processes..."
pkill -f "start_backend.py" 2>/dev/null
pkill -f "next dev" 2>/dev/null
pkill -f "tauri dev" 2>/dev/null

echo "✅ All services stopped"
EOF

chmod +x stop_all.sh

# Save PIDs for stopping
if [ "$BACKEND_PID" ] || [ "$FRONTEND_PID" ] || [ "$DESKTOP_PID" ]; then
    echo "backend:$BACKEND_PID" > .pids
    echo "frontend:$FRONTEND_PID" >> .pids
    echo "desktop:$DESKTOP_PID" >> .pids
fi

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "🛑 Shutting down ATOM Platform..."
    ./stop_all.sh
    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM

# Wait for user to stop
echo ""
echo "✨ Platform is running. Press Ctrl+C to stop."
echo ""

# Keep script running
if [ "$START_DESKTOP" = "false" ]; then
    while true; do
        sleep 1
    done
fi

# If desktop was started, the script will exit when desktop stops