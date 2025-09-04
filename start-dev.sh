#!/bin/bash
# Atom Development Startup Script
# This script starts all the necessary services for development

set -e  # Exit on error

echo "🚀 Starting Atom Development Environment..."
echo "==========================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to check if port is available
check_port() {
    if lsof -Pi :$1 -sTCP:LISTEN -t >/dev/null ; then
        echo -e "${GREEN}✓ Port $1 is available${NC}"
        return 0
    else
        echo -e "${RED}✗ Port $1 is already in use${NC}"
        return 1
    fi
}

# Function to start service with error handling
start_service() {
    local service_name=$1
    local command=$2
    local port=$3

    echo -e "${BLUE}Starting $service_name...${NC}"

    if [ -n "$port" ] && ! check_port $port; then
        echo -e "${YELLOW}Warning: $service_name may not start properly${NC}"
    fi

    # Run the command in background
    eval "$command" &
    local pid=$!

    # Store PID for later cleanup
    echo $pid >> /tmp/atom_pids.txt
    echo -e "${GREEN}✓ $service_name started (PID: $pid)${NC}"
}

# Cleanup function
cleanup() {
    echo -e "${YELLOW}Shutting down Atom services...${NC}"
    if [ -f /tmp/atom_pids.txt ]; then
        while read pid; do
            if kill -0 $pid 2>/dev/null; then
                kill $pid
                echo "Stopped process $pid"
            fi
        done < /tmp/atom_pids.txt
        rm /tmp/atom_pids.txt
    fi
    echo -e "${GREEN}All services stopped${NC}"
    exit 0
}

# Set up cleanup on script exit
trap cleanup EXIT INT TERM

# Remove old PID file if exists
rm -f /tmp/atom_pids.txt

echo -e "${BLUE}Checking required ports...${NC}"

# Check if required ports are available
check_port 3000  # Frontend
check_port 5058  # Python API
check_port 8003  # Workflows API
check_port 5000  # GraphQL (if used)

echo -e "${BLUE}Starting services...${NC}"

# 1. Start Frontend (Next.js)
cd frontend-nextjs
start_service "Frontend (Next.js)" "npm run dev" 3000
cd ..

# 2. Start Python API Service
cd backend/python-api-service
source venv/bin/activate
start_service "Python API" "python minimal_app.py" 5058
cd ../..

# 3. Start Workflows Service (development version)
cd backend/python-api/workflows
source venv/bin/activate
start_service "Workflows API" "python dev_server.py" 8003
cd ../../..

# 4. Start Functions Service (if needed)
cd frontend-nextjs/project/functions
start_service "Functions Service" "npm run dev" 3001
cd ../../..

echo -e "${GREEN}===========================================${NC}"
echo -e "${GREEN}🎉 Atom Development Environment Started!${NC}"
echo -e "${GREEN}===========================================${NC}"
echo ""
echo -e "${BLUE}Services running:${NC}"
echo -e "• Frontend:       ${GREEN}http://localhost:3000${NC}"
echo -e "• Python API:     ${GREEN}http://localhost:5058${NC}"
echo -e "• Workflows API:  ${GREEN}http://localhost:8003${NC}"
echo -e "• Dashboard API:  ${GREEN}http://localhost:3000/api/dashboard-dev${NC}"
echo ""
echo -e "${BLUE}Development Pages:${NC}"
echo -e "• Main App:       ${GREEN}http://localhost:3000/index-dev${NC}"
echo -e "• Login:          ${GREEN}http://localhost:3000/User/Login/UserLogin${NC}"
echo -e "• Automations:    ${GREEN}http://localhost:3000/Automations${NC}"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop all services${NC}"
echo ""

# Wait for all background processes
wait
