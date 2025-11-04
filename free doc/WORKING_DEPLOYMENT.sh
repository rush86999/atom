#!/bin/bash

# 🚀 ATOM Platform - Working Deployment Script
# Deploys the platform using current working configuration

set -e  # Exit on any error

echo "🚀 ATOM Platform - Working Deployment"
echo "====================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to log with colors
log_info() { echo -e "${BLUE}ℹ️ $1${NC}"; }
log_success() { echo -e "${GREEN}✅ $1${NC}"; }
log_warning() { echo -e "${YELLOW}⚠️ $1${NC}"; }
log_error() { echo -e "${RED}❌ $1${NC}"; }

# Stop existing services
log_info "Stopping existing services..."
pkill -f "python.*main_api_app.py" 2>/dev/null || true
pkill -f "improved_oauth_server.py" 2>/dev/null || true
pkill -f "next" 2>/dev/null || true
sleep 2

# Start Backend (Port 5058 - proven working)
log_info "Starting Backend API on port 5058..."
cd backend/python-api-service
python main_api_app.py > ../../backend_deployment.log 2>&1 &
BACKEND_PID=$!
echo $BACKEND_PID > ../../backend.pid
cd ../..

# Wait for backend to start
log_info "Waiting for backend to start..."
for i in {1..20}; do
    if curl -s http://localhost:5058/healthz > /dev/null 2>&1; then
        log_success "Backend API is running on port 5058"
        break
    fi
    sleep 1
    if [ $i -eq 20 ]; then
        log_error "Backend failed to start within 20 seconds"
        exit 1
    fi
done

# Start Frontend (Port 3000)
log_info "Starting Frontend..."
cd frontend-nextjs
npm run dev > ../frontend_deployment.log 2>&1 &
FRONTEND_PID=$!
echo $FRONTEND_PID > ../frontend.pid
cd ..

# Wait for frontend to start
log_info "Waiting for frontend to start..."
for i in {1..15}; do
    if curl -s http://localhost:3000 > /dev/null 2>&1; then
        log_success "Frontend is running on port 3000"
        break
    fi
    sleep 1
    if [ $i -eq 15 ]; then
        log_warning "Frontend is slow to start, continuing..."
        break
    fi
done

# Run comprehensive validation
log_info "Running system validation..."
echo ""
echo "🔍 SYSTEM VALIDATION"
echo "===================="

# Test core endpoints
ENDPOINTS=(
    "http://localhost:5058/healthz:Backend Health"
    "http://localhost:3000:Frontend Health"
    "http://localhost:5058/api/services:Service Registry"
    "http://localhost:5058/api/tasks:Task Management"
    "http://localhost:5058/api/calendar/events:Calendar Integration"
    "http://localhost:5058/api/messages:Message System"
    "http://localhost:5058/api/workflows:Workflow Automation"
    "http://localhost:5058/api/user-api-keys:BYOK System"
)

for endpoint_info in "${ENDPOINTS[@]}"; do
    IFS=':' read -r url description <<< "$endpoint_info"
    if curl -s "$url" > /dev/null; then
        log_success "$description"
    else
        log_error "$description"
    fi
done

# Get system information
log_info "Gathering system information..."
BACKEND_INFO=$(curl -s http://localhost:5058/healthz)
BLUEPRINT_COUNT=$(echo "$BACKEND_INFO" | jq -r '.total_blueprints // 0')
SERVICE_COUNT=$(curl -s http://localhost:5058/api/services | jq -r '.total_services // 0')

# Create monitoring script
log_info "Creating monitoring tools..."
cat > MONITOR_SYSTEM.sh << 'EOF'
#!/bin/bash
echo "🔍 ATOM Platform - System Monitor"
echo "=================================="
echo "Backend API:  http://localhost:5058"
echo "Frontend UI:  http://localhost:3000"
echo ""
echo "Health Status:"
curl -s http://localhost:5058/healthz | jq '.status' 2>/dev/null || echo "Backend health check failed"
echo ""
echo "Service Count:"
curl -s http://localhost:5058/api/services | jq '.total_services' 2>/dev/null || echo "Service registry unavailable"
echo ""
echo "Active Processes:"
ps aux | grep -E "(python.*main_api_app.py|next)" | grep -v grep | wc -l
echo ""
echo "Log Files:"
echo "Backend:  tail -f backend_deployment.log"
echo "Frontend: tail -f frontend_deployment.log"
EOF
chmod +x MONITOR_SYSTEM.sh

# Create quick test script
cat > TEST_SYSTEM.sh << 'EOF'
#!/bin/bash
echo "🧪 ATOM Platform - Quick Test"
echo "============================="
echo "Testing core functionality..."
echo ""
echo "1. Backend Health:"
curl -s http://localhost:5058/healthz | jq '.status'
echo ""
echo "2. Service Registry:"
curl -s http://localhost:5058/api/services | jq '.total_services'
echo ""
echo "3. Task Management:"
curl -s http://localhost:5058/api/tasks | jq '.success'
echo ""
echo "4. Frontend Access:"
curl -s -I http://localhost:3000 | head -1
echo ""
echo "✅ Quick test completed"
EOF
chmod +x TEST_SYSTEM.sh

# Final deployment summary
echo ""
echo "🎉 ATOM PLATFORM DEPLOYMENT COMPLETE!"
echo "====================================="
echo ""
echo "📊 DEPLOYMENT SUMMARY:"
echo "   Backend API:  http://localhost:5058"
echo "   Frontend UI:  http://localhost:3000"
echo "   Blueprints:   $BLUEPRINT_COUNT loaded"
echo "   Services:     $SERVICE_COUNT integrated"
echo ""
echo "🔧 MANAGEMENT TOOLS:"
echo "   Monitor:      ./MONITOR_SYSTEM.sh"
echo "   Test:         ./TEST_SYSTEM.sh"
echo "   Backend Log:  tail -f backend_deployment.log"
echo "   Frontend Log: tail -f frontend_deployment.log"
echo ""
echo "🚀 IMMEDIATE ACTIONS:"
echo "   1. Access http://localhost:3000"
echo "   2. Run ./TEST_SYSTEM.sh to verify functionality"
echo "   3. Check README_USER_JOURNEY_VALIDATION.md for persona guides"
echo "   4. Review REAL_WORLD_READINESS_REPORT.md for production status"
echo ""
echo "📞 SUPPORT:"
echo "   - Backend issues: Check backend_deployment.log"
echo "   - Frontend issues: Check frontend_deployment.log"
echo "   - Service issues: Run ./MONITOR_SYSTEM.sh"
echo ""
log_success "Deployment completed successfully!"

# Save deployment information
cat > deployment_info.txt << EOF
ATOM Platform Deployment Information
====================================
Deployment Time: $(date)
Backend PID: $BACKEND_PID
Frontend PID: $FRONTEND_PID
Backend Port: 5058
Frontend Port: 3000
Blueprints: $BLUEPRINT_COUNT
Services: $SERVICE_COUNT
Backend Log: backend_deployment.log
Frontend Log: frontend_deployment.log
Monitor Script: ./MONITOR_SYSTEM.sh
Test Script: ./TEST_SYSTEM.sh
EOF

log_success "Deployment information saved to deployment_info.txt"
