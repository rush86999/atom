#!/bin/bash

# 🚀 Atom Workflow Automation Deployment Script
# This script deploys the complete workflow automation system with all service integrations

set -e  # Exit on any error

echo "🚀 Deploying Atom Workflow Automation System"
echo "============================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if we're in the correct directory
if [ ! -f "README.md" ] && [ ! -d "backend" ]; then
    print_error "Please run this script from the atom project root directory"
    exit 1
fi

# Load environment variables from .env file
print_status "Loading environment variables from .env file..."
if [ -f ".env" ]; then
    # Export all variables from .env file
    export $(grep -v '^#' .env | xargs)
    print_success "Environment variables loaded from .env"
else
    print_warning ".env file not found, using default environment"
fi

# Set required environment variables with defaults
export DATABASE_URL=${DATABASE_URL:-"postgresql://atom_user:local_password@localhost:5432/atom_production"}
export ATOM_OAUTH_ENCRYPTION_KEY=${ATOM_OAUTH_ENCRYPTION_KEY:-$(python3 -c "import base64; import os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())")}
export FLASK_ENV=${FLASK_ENV:-"production"}
export PYTHON_API_PORT=${PYTHON_API_PORT:-5058}
export CELERY_BROKER_URL=${CELERY_BROKER_URL:-"redis://localhost:6379/0"}
export CELERY_RESULT_BACKEND=${CELERY_RESULT_BACKEND:-"redis://localhost:6379/0"}

print_status "Environment configuration:"
echo "  DATABASE_URL: $(echo $DATABASE_URL | sed 's/:[^:]*@/:***@/')"
echo "  FLASK_ENV: $FLASK_ENV"
echo "  PYTHON_API_PORT: $PYTHON_API_PORT"
echo "  CELERY_BROKER_URL: $(echo $CELERY_BROKER_URL | sed 's/:[^:]*@/:***@/')"
echo "  ATOM_OAUTH_ENCRYPTION_KEY: [set]"

# Check if required services are running
print_status "Checking required services..."

# Check PostgreSQL
if docker ps | grep -q "atom-postgres"; then
    print_success "PostgreSQL container is running"
else
    print_warning "PostgreSQL container not found, starting it..."
    docker-compose -f docker-compose.postgres.yml up -d
    sleep 5
fi

# Check Redis
if docker ps | grep -q "redis"; then
    print_success "Redis container is running"
else
    print_warning "Redis container not found, starting it..."
    docker run -d --name redis -p 6379:6379 redis:7-alpine
    sleep 3
fi

# Check if database is accessible
print_status "Testing database connectivity..."
if psql "$DATABASE_URL" -c "SELECT 1;" > /dev/null 2>&1; then
    print_success "Database connection successful"
else
    print_error "Cannot connect to database. Please check your DATABASE_URL configuration."
    exit 1
fi

# Initialize database tables
print_status "Initializing database tables..."
cd backend/python-api-service

# Run database initialization
if python3 -c "from init_database import initialize_database; initialize_database()"; then
    print_success "Database tables initialized successfully"
else
    print_error "Failed to initialize database tables"
    exit 1
fi

# Create workflow tables
print_status "Creating workflow tables..."
if python3 -c "from workflow_handler import create_workflow_tables; create_workflow_tables()"; then
    print_success "Workflow tables created successfully"
else
    print_error "Failed to create workflow tables"
    exit 1
fi

# Register sample workflows
print_status "Registering sample workflows..."
if python3 -c "
from workflow_execution_service import workflow_execution_service
from workflow_api import WORKFLOW_TEMPLATES

for template_id, template in WORKFLOW_TEMPLATES.items():
    workflow_execution_service.register_workflow(template_id, template)
    print(f'Registered workflow: {template[\"name\"]}')
"; then
    print_success "Sample workflows registered successfully"
else
    print_error "Failed to register sample workflows"
    exit 1
fi

# Start Celery worker for workflows
print_status "Starting Celery worker for workflows..."
cd ../python-api/workflows

# Start Celery worker in background
celery -A celery_app worker --loglevel=info --concurrency=4 --hostname=workflow_worker@%h --detach
print_success "Celery worker started for workflows"

# Start Celery beat for scheduled tasks
print_status "Starting Celery beat for scheduled workflows..."
celery -A celery_app beat --loglevel=info --detach
print_success "Celery beat started for scheduled workflows"

# Navigate back to backend root
cd ../..

# Start the main API server
print_status "Starting main API server..."
print_success "Workflow automation system deployed successfully!"
echo ""
echo "📋 Deployment Summary:"
echo "  ✅ Database initialized and connected"
echo "  ✅ Workflow tables created"
echo "  ✅ Sample workflows registered"
echo "  ✅ Celery worker started"
echo "  ✅ Celery beat started for scheduled workflows"
echo "  ✅ API server ready on port $PYTHON_API_PORT"
echo ""
echo "🌐 Available Endpoints:"
echo "  - API Server: http://localhost:$PYTHON_API_PORT"
echo "  - Health Check: http://localhost:$PYTHON_API_PORT/healthz"
echo "  - Workflow API: http://localhost:$PYTHON_API_PORT/api/workflows"
echo "  - Workflow Templates: http://localhost:$PYTHON_API_PORT/api/workflows/templates"
echo ""
echo "🔧 Next Steps:"
echo "  1. Access the Atom Agent UI at http://localhost:3000"
echo "  2. Navigate to the 'Workflow Automation' tab"
echo "  3. Explore available workflow templates"
echo "  4. Execute workflows and monitor executions"
echo "  5. Check service integrations in the 'Service Integrations' tab"
echo ""
echo "📝 For troubleshooting:"
echo "  - Check logs: tail -f backend/backend.log"
echo "  - Monitor Celery: celery -A backend/python-api/workflows/celery_app inspect active"
echo "  - View workflow executions: curl http://localhost:$PYTHON_API_PORT/api/workflows/executions"
echo ""

# Start the main API server
python3 main_api_app.py
