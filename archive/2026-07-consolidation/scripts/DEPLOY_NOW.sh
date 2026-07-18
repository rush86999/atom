#!/bin/bash

# 🚀 ATOM Platform - Immediate Deployment Script
# Deploys production-ready system in under 10 minutes

set -e  # Exit on any error

echo "🚀 Starting ATOM Platform Immediate Deployment..."
echo "=================================================="

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

# Check prerequisites
log_info "Checking prerequisites..."
if ! command -v docker &> /dev/null; then
    log_error "Docker is not installed. Please install Docker first."
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    log_error "Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Stop any existing services
log_info "Stopping existing services..."
docker-compose down 2>/dev/null || true
pkill -f "python.*main_api_app.py" 2>/dev/null || true
pkill -f "next" 2>/dev/null || true
sleep 3

# Create production environment if needed
if [ ! -f ".env.production" ]; then
    log_warning "Creating production environment file..."
    cp .env.example .env.production
    log_warning "Please edit .env.production with your production settings"
fi

# Start PostgreSQL
log_info "Starting PostgreSQL database..."
docker-compose -f docker-compose.postgres.yml up -d
sleep 5

# Check if PostgreSQL is ready
if docker-compose -f docker-compose.postgres.yml exec postgres pg_isready -U postgres; then
    log_success "PostgreSQL is ready"
else
    log_error "PostgreSQL failed to start"
    exit 1
fi

# Initialize database
log_info "Initializing database..."
cd backend/python-api-service
python init_database.py
cd ../..

# Start backend with production settings
log_info "Starting backend API..."
cd backend/python-api-service
export FLASK_ENV=production
export PYTHON_API_PORT=8000
python main_api_app.py > ../../backend_production.log 2>&1 &
BACKEND_PID=$!
echo $BACKEND_PID > ../../backend_production.pid
cd ../..

# Wait for backend to start
log_info "Waiting for backend to start..."
sleep 15

# Check backend health
if curl -s http://localhost:8000/healthz > /dev/null; then
    log_success "Backend API is running on port 8000"
else
    log_error "Backend failed to start. Check backend_production.log"
    exit 1
fi

# Build and start frontend
log_info "Building frontend for production..."
cd frontend-nextjs
npm run build
NODE_ENV=production npm start > ../frontend_production.log 2>&1 &
FRONTEND_PID=$!
echo $FRONTEND_PID > ../frontend_production.pid
cd ..

# Wait for frontend to start
log_info "Waiting for frontend to start..."
sleep 10

# Check frontend health
if curl -s http://localhost:3000 > /dev/null; then
    log_success "Frontend is running on port 3000"
else
    log_warning "Frontend may be starting slowly. Check frontend_production.log"
fi

# Run comprehensive health checks
log_info "Running comprehensive health checks..."
echo "=================================================="

# Test core endpoints
ENDPOINTS=(
    "/healthz"
    "/api/services"
    "/api/tasks"
    "/api/calendar/events"
    "/api/messages"
    "/api/workflows"
    "/api/user-api-keys"
)

for endpoint in "${ENDPOINTS[@]}"; do
    if curl -s "http://localhost:8000${endpoint}" > /dev/null; then
        log_success "$endpoint - ACCESSIBLE"
    else
        log_error "$endpoint - NOT ACCESSIBLE"
    fi
done

# Check service registry
log_info "Checking service registry..."
SERVICE_COUNT=$(curl -s http://localhost:8000/api/services | grep -o '"total_services":[0-9]*' | cut -d: -f2)
if [ -n "$SERVICE_COUNT" ] && [ "$SERVICE_COUNT" -gt 0 ]; then
    log_success "Service registry: $SERVICE_COUNT services registered"
else
    log_warning "Service registry not accessible"
fi

# Check blueprints
log_info "Checking blueprints..."
BLUEPRINT_COUNT=$(curl -s http://localhost:8000/healthz | grep -o '"total_blueprints":[0-9]*' | cut -d: -f2)
if [ -n "$BLUEPRINT_COUNT" ] && [ "$BLUEPRINT_COUNT" -gt 0 ]; then
    log_success "Blueprints: $BLUEPRINT_COUNT blueprints loaded"
else
    log_warning "Blueprint count not available"
fi

# Create monitoring script
log_info "Creating monitoring script..."
cat > MONITOR_SYSTEM.sh << 'EOF'
#!/bin/bash
echo "🔍 ATOM Platform - System Monitor"
echo "=================================="
echo "Backend API:  http://localhost:8000"
echo "Frontend UI:  http://localhost:3000"
echo ""
echo "Health Checks:"
curl -s http://localhost:8000/healthz | jq '.status' 2>/dev/null || echo "Backend health check failed"
echo ""
echo "Service Status:"
curl -s http://localhost:8000/api/services | jq '.total_services' 2>/dev/null || echo "Service registry unavailable"
echo ""
echo "Active Processes:"
ps aux | grep -E "(python.*main_api_app.py|next)" | grep -v grep | wc -l
EOF
chmod +x MONITOR_SYSTEM.sh

# Final deployment summary
echo ""
echo "🎉 ATOM PLATFORM DEPLOYMENT COMPLETE!"
echo "=================================================="
echo ""
echo "📊 DEPLOYMENT SUMMARY:"
echo "   Backend API:  http://localhost:8000"
echo "   Frontend UI:  http://localhost:3000"
echo "   Health Check: http://localhost:8000/healthz"
echo "   Services:     http://localhost:8000/api/services"
echo ""
echo "🔧 MANAGEMENT COMMANDS:"
echo "   Monitor:      ./MONITOR_SYSTEM.sh"
echo "   Backend Log:  tail -f backend_production.log"
echo "   Frontend Log: tail -f frontend_production.log"
echo "   Stop All:     docker-compose down && pkill -f 'python.*main_api_app.py' && pkill -f 'next'"
echo ""
echo "🚀 NEXT STEPS:"
echo "   1. Access http://localhost:3000 to use the platform"
echo "   2. Configure OAuth services in .env.production"
echo "   3. Set up SSL/TLS for production deployment"
echo "   4. Configure monitoring and alerts"
echo ""
echo "📞 SUPPORT:"
echo "   Check README_USER_JOURNEY_VALIDATION.md for persona guides"
echo "   Check IMMEDIATE_PRODUCTION_DEPLOYMENT.md for production setup"
echo ""
echo "=================================================="
log_success "Deployment completed successfully!"

# Save deployment information
echo "Backend PID: $BACKEND_PID" > deployment_info.txt
echo "Frontend PID: $FRONTEND_PID" >> deployment_info.txt
echo "Deployment Time: $(date)" >> deployment_info.txt
echo "Backend Log: backend_production.log" >> deployment_info.txt
echo "Frontend Log: frontend_production.log" >> deployment_info.txt

log_success "Deployment information saved to deployment_info.txt"
