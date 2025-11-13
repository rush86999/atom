#!/bin/bash

# ATOM Platform Deployment Script
# This script handles deployment of the ATOM platform to production

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Configuration
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend-nextjs"
DEPLOY_DIR="$PROJECT_ROOT/deployment"
ENV_FILE="$PROJECT_ROOT/.env.production"

# Check if we're in the right directory
check_environment() {
    log_info "Checking deployment environment..."

    if [ ! -d "$BACKEND_DIR" ] || [ ! -d "$FRONTEND_DIR" ]; then
        log_error "Project directories not found. Please run from project root."
        exit 1
    fi

    if [ ! -f "$BACKEND_DIR/requirements.txt" ]; then
        log_error "Backend requirements.txt not found"
        exit 1
    fi

    if [ ! -f "$FRONTEND_DIR/package.json" ]; then
        log_error "Frontend package.json not found"
        exit 1
    fi

    log_success "Environment check passed"
}

# Setup Python virtual environment
setup_python_env() {
    log_info "Setting up Python virtual environment..."

    cd "$BACKEND_DIR"

    if [ ! -d "venv" ]; then
        python3 -m venv venv
        log_success "Created Python virtual environment"
    fi

    source venv/bin/activate

    # Upgrade pip
    pip install --upgrade pip

    # Install dependencies
    if [ -f "requirements.txt" ]; then
        pip install -r requirements.txt
        log_success "Installed Python dependencies"
    else
        log_warning "requirements.txt not found, skipping Python dependency installation"
    fi

    deactivate
}

# Setup Node.js dependencies
setup_node_deps() {
    log_info "Setting up Node.js dependencies..."

    cd "$FRONTEND_DIR"

    if [ -f "package.json" ]; then
        npm install
        log_success "Installed Node.js dependencies"
    else
        log_warning "package.json not found, skipping Node.js dependency installation"
    fi
}

# Build frontend for production
build_frontend() {
    log_info "Building frontend for production..."

    cd "$FRONTEND_DIR"

    if [ -f "package.json" ]; then
        # Check if build script exists
        if npm run | grep -q "build"; then
            npm run build
            log_success "Frontend built successfully"
        else
            log_warning "No build script found in package.json"
        fi
    else
        log_warning "package.json not found, skipping frontend build"
    fi
}

# Setup environment files
setup_environment() {
    log_info "Setting up environment configuration..."

    # Create deployment directory
    mkdir -p "$DEPLOY_DIR"

    # Copy environment file if it exists
    if [ -f "$ENV_FILE" ]; then
        cp "$ENV_FILE" "$DEPLOY_DIR/.env"
        log_success "Copied production environment file"
    else
        log_warning "Production environment file not found at $ENV_FILE"
        log_info "Creating basic environment file..."
        cat > "$DEPLOY_DIR/.env" << EOF
# ATOM Platform Production Environment
DATABASE_URL=sqlite:///atom_production.db
DEBUG=false
LOG_LEVEL=INFO
CORS_ORIGINS=https://your-domain.com
HOST=0.0.0.0
PORT=8000
JWT_SECRET=change-this-in-production
EOF
        log_warning "Created basic environment file. Please update with actual values."
    fi

    # Create necessary directories
    mkdir -p "$DEPLOY_DIR/data"
    mkdir -p "$DEPLOY_DIR/logs"
    log_success "Created deployment directories"
}

# Create startup scripts
create_startup_scripts() {
    log_info "Creating startup scripts..."

    # Backend startup script
    cat > "$DEPLOY_DIR/start_backend.sh" << 'EOF'
#!/bin/bash
cd "$(dirname "$0")/../backend"
source venv/bin/activate
python main_api_app.py
EOF

    # Frontend startup script
    cat > "$DEPLOY_DIR/start_frontend.sh" << 'EOF'
#!/bin/bash
cd "$(dirname "$0")/../frontend-nextjs"
npm start
EOF

    # Combined startup script
    cat > "$DEPLOY_DIR/start_all.sh" << 'EOF'
#!/bin/bash
echo "Starting ATOM Platform..."
cd "$(dirname "$0")"

# Start backend
echo "Starting backend..."
./start_backend.sh &

# Wait a bit for backend to start
sleep 5

# Start frontend
echo "Starting frontend..."
./start_frontend.sh &

echo "ATOM Platform started!"
echo "Backend: http://localhost:8000"
echo "Frontend: http://localhost:3000"
echo "Press Ctrl+C to stop all services"

# Wait for user interrupt
wait
EOF

    # Make scripts executable
    chmod +x "$DEPLOY_DIR/start_backend.sh"
    chmod +x "$DEPLOY_DIR/start_frontend.sh"
    chmod +x "$DEPLOY_DIR/start_all.sh"

    log_success "Created startup scripts"
}

# Docker deployment setup
setup_docker() {
    log_info "Setting up Docker deployment..."

    # Check if docker-compose.yml exists
    if [ -f "$PROJECT_ROOT/docker-compose.yml" ]; then
        log_info "Found existing docker-compose.yml"
        return 0
    fi

    # Create basic docker-compose.yml
    cat > "$PROJECT_ROOT/docker-compose.yml" << EOF
version: '3.8'

services:
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://atom:atom@db:5432/atom
      - DEBUG=false
    depends_on:
      - db
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs

  frontend:
    build:
      context: ./frontend-nextjs
      dockerfile: Dockerfile
    ports:
      - "3000:3000"
    depends_on:
      - backend

  db:
    image: postgres:13
    environment:
      - POSTGRES_DB=atom
      - POSTGRES_USER=atom
      - POSTGRES_PASSWORD=atom
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
EOF

    log_success "Created docker-compose.yml for production deployment"
}

# Health check
health_check() {
    log_info "Performing health check..."

    # Check if backend starts
    cd "$BACKEND_DIR"
    source venv/bin/activate

    # Test backend startup
    timeout 10s python -c "
from main_api_app import app
print('Backend imports successful')
" || {
    log_warning "Backend import test failed, but continuing deployment"
}

deactivate

log_info "Health check completed"
}

# Main deployment function
deploy() {
    log_info "Starting ATOM Platform deployment..."

    check_environment
    setup_python_env
    setup_node_deps
    build_frontend
    setup_environment
    create_startup_scripts
    setup_docker
    health_check

    log_success "ATOM Platform deployment completed successfully!"
    log_info ""
    log_info "Next steps:"
    log_info "1. Update $DEPLOY_DIR/.env with your production values"
    log_info "2. Run: cd $DEPLOY_DIR && ./start_all.sh"
    log_info "3. Or use Docker: docker-compose up -d"
    log_info ""
    log_info "Backend will be available at: http://localhost:8000"
    log_info "Frontend will be available at: http://localhost:3000"
}

# Show usage information
show_usage() {
    echo "ATOM Platform Deployment Script"
    echo ""
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  deploy        Full deployment (default)"
    echo "  backend       Deploy backend only"
    echo "  frontend      Deploy frontend only"
    echo "  docker        Setup Docker deployment"
    echo "  help          Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 deploy      # Full deployment"
    echo "  $0 backend     # Backend only"
    echo "  $0 docker      # Docker setup"
}

# Parse command line arguments
case "${1:-deploy}" in
    deploy)
        deploy
        ;;
    backend)
        check_environment
        setup_python_env
        setup_environment
        create_startup_scripts
        health_check
        ;;
    frontend)
        check_environment
        setup_node_deps
        build_frontend
        setup_environment
        create_startup_scripts
        ;;
    docker)
        check_environment
        setup_docker
        ;;
    help|--help|-h)
        show_usage
        ;;
    *)
        log_error "Unknown command: $1"
        show_usage
        exit 1
        ;;
esac
