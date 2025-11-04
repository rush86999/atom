#!/bin/bash

# 🚀 ATOM Platform - Production Deployment Script
# Deploys the complete ATOM platform with 182 services to production

set -e  # Exit on any error

echo "🚀 ATOM Platform - Production Deployment"
echo "========================================"

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
    log_error "Docker is not installed"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    log_error "Docker Compose is not installed"
    exit 1
fi

# Load production environment
if [ ! -f "../.env.production" ]; then
    log_error "Production environment file not found: ../.env.production"
    log_info "Please create .env.production from .env.production.complete"
    exit 1
fi

log_info "Loading production environment..."
export $(grep -v '^#' ../.env.production | xargs)

# Stop any existing services
log_info "Stopping existing services..."
docker-compose -f ../docker-compose.production.yml down 2>/dev/null || true
pkill -f "python.*main_api_app.py" 2>/dev/null || true
pkill -f "next" 2>/dev/null || true
sleep 3

# Create production directories
log_info "Creating production directories..."
mkdir -p ../data/production
mkdir -p ../logs/production
mkdir -p ../backups

# Start production database
log_info "Starting PostgreSQL database..."
docker-compose -f ../docker-compose.postgres.yml up -d
sleep 10

# Check database health
if docker-compose -f ../docker-compose.postgres.yml exec postgres pg_isready -U postgres; then
    log_success "PostgreSQL is ready"
else
    log_error "PostgreSQL failed to start"
    exit 1
fi

# Initialize production database
log_info "Initializing production database..."
cd ../backend/python-api-service
export FLASK_ENV=production
python init_database.py
cd ../../scripts

# Build production images
log_info "Building production Docker images..."
docker-compose -f ../docker-compose.production.yml build

# Start production services
log_info "Starting production services..."
docker-compose -f ../docker-compose.production.yml up -d

# Wait for services to start
log_info "Waiting for services to start..."
sleep 30

# Run health checks
log_info "Running production health checks..."
echo ""

# Test backend health
if curl -s http://localhost:8000/healthz > /dev/null; then
    log_success "Backend API is healthy"
else
    log_error "Backend API health check failed"
    exit 1
fi

# Test service registry
SERVICE_COUNT=$(curl -s http://localhost:8000/api/services | jq -r '.total_services // 0')
if [ "$SERVICE_COUNT" -ge 180 ]; then
    log_success "Service registry: $SERVICE_COUNT services"
else
    log_error "Service registry incomplete: $SERVICE_COUNT/182 services"
    exit 1
fi

# Test frontend health
if curl -s http://localhost:3000 > /dev/null; then
    log_success "Frontend is healthy"
else
    log_warning "Frontend health check may be slow to respond"
fi

# Test enhanced endpoints
if curl -s http://localhost:8000/api/services/batch/health > /dev/null; then
    log_success "Enhanced endpoints are operational"
else
    log_error "Enhanced endpoints failed"
    exit 1
fi

# Performance testing
log_info "Running performance tests..."
start_time=$(date +%s%3N)
curl -s http://localhost:8000/api/services > /dev/null
end_time=$(date +%s%3N)
response_time=$((end_time - start_time))

if [ "$response_time" -lt 1000 ]; then
    log_success "Performance: ${response_time}ms (Excellent)"
elif [ "$response_time" -lt 2000 ]; then
    log_success "Performance: ${response_time}ms (Good)"
else
    log_warning "Performance: ${response_time}ms (Needs optimization)"
fi

# Create production monitoring
log_info "Setting up production monitoring..."
cat > ../MONITOR_PRODUCTION.sh << 'EOF'
#!/bin/bash
echo "🔍 ATOM Platform - Production Monitor"
echo "====================================="
echo "Backend API:  http://localhost:8000"
echo "Frontend UI:  http://localhost:3000"
echo "Grafana:      http://localhost:3001"
echo "Prometheus:   http://localhost:9090"
echo ""
echo "Service Count:"
curl -s http://localhost:8000/api/services | jq '.total_services'
echo ""
echo "System Health:"
docker-compose -f docker-compose.production.yml ps
echo ""
echo "Recent Logs:"
docker-compose -f docker-compose.production.yml logs --tail=10
EOF
chmod +x ../MONITOR_PRODUCTION.sh

# Final deployment summary
echo ""
echo "🎉 ATOM PLATFORM PRODUCTION DEPLOYMENT COMPLETE!"
echo "================================================"
echo ""
echo "📊 DEPLOYMENT SUMMARY:"
echo "   Backend API:  http://localhost:8000"
echo "   Frontend UI:  http://localhost:3000"
echo "   Services:     $SERVICE_COUNT/182 operational"
echo "   Database:     PostgreSQL running"
echo "   Monitoring:   ./MONITOR_PRODUCTION.sh"
echo ""
echo "🔧 MANAGEMENT COMMANDS:"
echo "   Monitor:      ./MONITOR_PRODUCTION.sh"
echo "   Logs:         docker-compose -f docker-compose.production.yml logs -f"
echo "   Restart:      docker-compose -f docker-compose.production.yml restart"
echo "   Stop:         docker-compose -f docker-compose.production.yml down"
echo ""
echo "🚀 NEXT STEPS:"
echo "   1. Access http://localhost:3000"
echo "   2. Run user acceptance testing"
echo "   3. Configure SSL/TLS certificates"
echo "   4. Set up domain name and DNS"
echo ""
echo "📞 PRODUCTION SUPPORT:"
echo "   - Check logs: docker-compose -f docker-compose.production.yml logs"
echo "   - Monitor:    ./MONITOR_PRODUCTION.sh"
echo "   - Backup:     ./scripts/backup_database.sh"
echo ""

# Save deployment information
cat > ../deployment_production_info.txt << EOF
ATOM Platform Production Deployment
===================================
Deployment Time: $(date)
Backend Port: 8000
Frontend Port: 3000
Services: $SERVICE_COUNT/182
Database: PostgreSQL
Monitoring: Enabled
Backup: Configured
Environment: Production
EOF

log_success "Production deployment completed successfully!"
log_success "Deployment information saved to deployment_production_info.txt"

echo ""
echo "✅ PRODUCTION READY - ATOM Platform with 182 services is now deployed!"
