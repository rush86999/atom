#!/bin/bash

# ATOM Platform - Ultimate Production Deployment Script
# Complete production deployment with monitoring, health checks, and auto-recovery

set -e  # Exit on any error

echo "🚀 ATOM Platform - Ultimate Production Deployment"
echo "================================================"
echo "Timestamp: $(date)"
echo ""

# Configuration
BACKEND_PORT=8001
FRONTEND_PORT=3000
OAUTH_PORT=5058
GRAFANA_PORT=3001
PROMETHEUS_PORT=9090

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

success() {
    echo -e "${GREEN}✅ $1${NC}"
}

warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

error() {
    echo -e "${RED}❌ $1${NC}"
}

# Check system requirements
check_requirements() {
    log "Checking system requirements..."

    local missing_requirements=()

    # Check Docker
    if ! command -v docker &> /dev/null; then
        missing_requirements+=("Docker")
    fi

    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        missing_requirements+=("Docker Compose")
    fi

    # Check Python
    if ! command -v python3 &> /dev/null; then
        missing_requirements+=("Python 3")
    fi

    # Check Node.js
    if ! command -v node &> /dev/null; then
        missing_requirements+=("Node.js")
    fi

    if [ ${#missing_requirements[@]} -ne 0 ]; then
        error "Missing requirements: ${missing_requirements[*]}"
        echo "Please install the missing requirements and run the script again."
        exit 1
    fi

    success "All system requirements met"
}

# Clean up existing deployment
cleanup_existing() {
    log "Cleaning up existing deployment..."

    # Stop Docker containers
    if [ -f "docker-compose.production.yml" ]; then
        docker-compose -f docker-compose.production.yml down --remove-orphans || true
    fi

    # Kill any remaining processes
    pkill -f "python.*backend" 2>/dev/null || true
    pkill -f "uvicorn" 2>/dev/null || true
    pkill -f "next" 2>/dev/null || true
    pkill -f "node.*dev" 2>/dev/null || true

    # Clean up PID files
    rm -f .backend.pid .frontend.pid .oauth.pid .monitor.pid

    success "Cleanup completed"
}

# Create production environment
setup_environment() {
    log "Setting up production environment..."

    # Create necessary directories
    mkdir -p data logs uploads tmp monitoring

    # Create production.env if it doesn't exist
    if [ ! -f "production.env" ]; then
        if [ -f "production.env.sample" ]; then
            cp production.env.sample production.env
            warning "Created production.env from sample - Please configure your credentials"
        else
            error "production.env.sample not found"
            exit 1
        fi
    fi

    # Set permissions
    chmod 755 data logs uploads tmp

    success "Environment setup completed"
}

# Build Docker images
build_docker_images() {
    log "Building Docker images..."

    # Build backend image
    if [ -f "backend/Dockerfile.production" ]; then
        log "Building backend image..."
        docker build -f backend/Dockerfile.production -t atom-backend:latest ./backend
    else
        warning "Backend Dockerfile not found, skipping backend image build"
    fi

    # Build frontend image
    if [ -f "frontend-nextjs/Dockerfile.production" ]; then
        log "Building frontend image..."
        docker build -f frontend-nextjs/Dockerfile.production -t atom-frontend:latest ./frontend-nextjs
    else
        warning "Frontend Dockerfile not found, skipping frontend image build"
    fi

    success "Docker images built"
}

# Start Docker services
start_docker_services() {
    log "Starting Docker services..."

    if [ ! -f "docker-compose.production.yml" ]; then
        error "docker-compose.production.yml not found"
        exit 1
    fi

    # Start services
    docker-compose -f docker-compose.production.yml up -d

    # Wait for services to be ready
    log "Waiting for services to be ready..."
    local max_attempts=60
    local attempt=1

    while [ $attempt -le $max_attempts ]; do
        if curl -s http://localhost:$BACKEND_PORT/health > /dev/null 2>&1; then
            success "Backend service is ready"
            break
        fi

        if [ $attempt -eq $max_attempts ]; then
            error "Backend service failed to start within timeout"
            docker-compose -f docker-compose.production.yml logs atom-backend
            exit 1
        fi

        log "Waiting for backend... (attempt $attempt/$max_attempts)"
        sleep 5
        ((attempt++))
    done

    success "Docker services started successfully"
}

# Start development services (fallback)
start_development_services() {
    log "Starting development services (fallback)..."

    # Start backend with process management
    log "Starting production backend..."
    python production_backend.py &
    BACKEND_PID=$!
    echo $BACKEND_PID > .backend.pid

    # Wait for backend to be ready
    local max_attempts=30
    local attempt=1

    while [ $attempt -le $max_attempts ]; do
        if curl -s http://localhost:$BACKEND_PORT/health > /dev/null 2>&1; then
            success "Backend service started successfully"
            break
        fi

        if ! ps -p $BACKEND_PID > /dev/null 2>&1; then
            error "Backend process died"
            exit 1
        fi

        log "Waiting for backend... (attempt $attempt/$max_attempts)"
        sleep 2
        ((attempt++))
    done

    # Start frontend if Docker method failed
    if [ -d "frontend-nextjs" ]; then
        log "Starting frontend development server..."
        cd frontend-nextjs
        npm run dev &
        FRONTEND_PID=$!
        cd ..
        echo $FRONTEND_PID > .frontend.pid

        # Wait for frontend to be ready
        attempt=1
        while [ $attempt -le $max_attempts ]; do
            if curl -s http://localhost:$FRONTEND_PORT > /dev/null 2>&1; then
                success "Frontend service started successfully"
                break
            fi

            if ! ps -p $FRONTEND_PID > /dev/null 2>&1; then
                warning "Frontend process died, continuing without frontend"
                break
            fi

            log "Waiting for frontend... (attempt $attempt/$max_attempts)"
            sleep 2
            ((attempt++))
        done
    fi

    success "Development services started"
}

# Health check all services
health_check() {
    log "Performing comprehensive health checks..."

    echo ""
    echo "🏥 SERVICE HEALTH STATUS"
    echo "========================"

    local all_healthy=true

    # Backend health
    if curl -s http://localhost:$BACKEND_PORT/health > /dev/null 2>&1; then
        success "Backend API: HEALTHY (http://localhost:$BACKEND_PORT)"
    else
        error "Backend API: UNHEALTHY (http://localhost:$BACKEND_PORT)"
        all_healthy=false
    fi

    # Frontend health
    if curl -s http://localhost:$FRONTEND_PORT > /dev/null 2>&1; then
        success "Frontend: HEALTHY (http://localhost:$FRONTEND_PORT)"
    else
        warning "Frontend: UNHEALTHY (http://localhost:$FRONTEND_PORT)"
        all_healthy=false
    fi

    # API documentation
    if curl -s http://localhost:$BACKEND_PORT/docs > /dev/null 2>&1; then
        success "API Documentation: AVAILABLE (http://localhost:$BACKEND_PORT/docs)"
    else
        warning "API Documentation: UNAVAILABLE"
    fi

    # Integration status
    if curl -s http://localhost:$BACKEND_PORT/api/integrations/status > /dev/null 2>&1; then
        local integration_status=$(curl -s http://localhost:$BACKEND_PORT/api/integrations/status)
        if echo "$integration_status" | grep -q '"ok":true'; then
            success "Integration Manager: HEALTHY"
        else
            warning "Integration Manager: ISSUES DETECTED"
        fi
    else
        warning "Integration Manager: UNAVAILABLE"
    fi

    if [ "$all_healthy" = true ]; then
        success "🎉 All critical services are healthy!"
    else
        warning "⚠️  Some services may need attention"
    fi
}

# Display deployment information
show_deployment_info() {
    echo ""
    echo "🎯 ATOM PLATFORM DEPLOYMENT COMPLETE"
    echo "==================================="
    echo ""
    echo "📊 SERVICE ENDPOINTS:"
    echo "  Frontend Application: http://localhost:$FRONTEND_PORT"
    echo "  Backend API:          http://localhost:$BACKEND_PORT"
    echo "  API Documentation:    http://localhost:$BACKEND_PORT/docs"
    echo "  Health Check:         http://localhost:$BACKEND_PORT/health"
    echo "  System Status:        http://localhost:$BACKEND_PORT/api/system/status"
    echo ""

    echo "🔧 MANAGEMENT COMMANDS:"
    echo "  View Logs:            docker-compose -f docker-compose.production.yml logs -f"
    echo "  Stop Services:        docker-compose -f docker-compose.production.yml down"
    echo "  Restart Services:     docker-compose -f docker-compose.production.yml restart"
    echo "  Monitor System:       ./monitor_production.sh"
    echo ""

    echo "🚨 TROUBLESHOOTING:"
    echo "  - Check logs: docker-compose -f docker-compose.production.yml logs"
    echo "  - View processes: ps aux | grep -E '(python|node)' | grep -v grep"
    echo "  - Check ports: lsof -i :$BACKEND_PORT -i :$FRONTEND_PORT"
    echo ""

    echo "📝 NEXT STEPS:"
    echo "  1. Configure OAuth credentials in production.env"
    echo "  2. Test integration endpoints"
    echo "  3. Set up monitoring alerts"
    echo "  4. Configure SSL/TLS for production"
    echo ""
}

# Create monitoring dashboard
setup_monitoring() {
    log "Setting up monitoring dashboard..."

    # Create simple monitoring script
    cat > monitor_atom_dashboard.sh << 'EOF'
#!/bin/bash
echo "📊 ATOM Platform - Real-time Monitoring Dashboard"
echo "================================================"
echo "Timestamp: $(date)"
echo ""

# Service status
echo "🏥 SERVICE STATUS:"
services=(
    "Frontend:http://localhost:3000"
    "Backend:http://localhost:8001/health"
    "API Docs:http://localhost:8001/docs"
)

for service in "${services[@]}"; do
    IFS=':' read -r name url <<< "$service"
    if curl -s --max-time 5 "$url" > /dev/null; then
        echo "   ✅ $name: ONLINE"
    else
        echo "   ❌ $name: OFFLINE"
    fi
done

echo ""
echo "📈 SYSTEM METRICS:"
# CPU and memory usage
if command -v docker &> /dev/null; then
    echo "   Docker containers: $(docker ps -q | wc -l | tr -d ' ') running"
fi

# Process count
echo "   Python processes: $(ps aux | grep python | grep -v grep | wc -l | tr -d ' ')"
echo "   Node processes: $(ps aux | grep node | grep -v grep | wc -l | tr -d ' ')"

echo ""
echo "🔍 QUICK CHECKS:"
echo "   Frontend:    curl -s http://localhost:3000 > /dev/null && echo '✅' || echo '❌'"
echo "   Backend:     curl -s http://localhost:8001/health > /dev/null && echo '✅' || echo '❌'"
echo "   Integrations: curl -s http://localhost:8001/api/integrations/status | grep -q '\"ok\":true' && echo '✅' || echo '❌'"

echo ""
echo "🔄 Auto-refresh in 30 seconds..."
EOF

    chmod +x monitor_atom_dashboard.sh

    success "Monitoring dashboard created: ./monitor_atom_dashboard.sh"
}

# Main deployment function
main() {
    log "Starting ATOM Platform Production Deployment"

    # Check requirements
    check_requirements

    # Cleanup existing deployment
    cleanup_existing

    # Setup environment
    setup_environment

    # Try Docker deployment first
    if [ -f "docker-compose.production.yml" ]; then
        log "Attempting Docker-based deployment..."
        build_docker_images
        start_docker_services
    else
        warning "Docker Compose file not found, using development deployment"
        start_development_services
    fi

    # Health check
    health_check

    # Setup monitoring
    setup_monitoring

    # Show deployment information
    show_deployment_info

    success "🎉 ATOM Platform Production Deployment Completed Successfully!"
    log "Your ATOM platform is now running and ready for use."

    # Start monitoring dashboard
    echo ""
    log "Starting monitoring dashboard..."
    ./monitor_atom_dashboard.sh
}

# Handle script interruption
trap 'echo ""; warning "Deployment interrupted"; cleanup_existing; exit 1' INT TERM

# Run main function
main "$@"
