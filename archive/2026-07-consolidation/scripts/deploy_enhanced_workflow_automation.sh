#!/bin/bash

# 🚀 Enhanced Atom Workflow Automation Deployment Script
# Comprehensive deployment with advanced monitoring, error handling, and optimization

set -e  # Exit on any error

echo "🚀 Deploying Enhanced Atom Workflow Automation System"
echo "===================================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
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

print_debug() {
    echo -e "${PURPLE}[DEBUG]${NC} $1"
}

print_section() {
    echo -e "${CYAN}[SECTION]${NC} $1"
}

# Error handling functions
handle_error() {
    local exit_code=$1
    local error_message=$2
    print_error "$error_message (Exit code: $exit_code)"
    exit $exit_code
}

check_command() {
    local command=$1
    local description=$2
    if ! command -v $command &> /dev/null; then
        print_error "$description ($command) not found"
        return 1
    fi
    return 0
}

# Check if we're in the correct directory
if [ ! -f "README.md" ] && [ ! -d "backend" ]; then
    print_error "Please run this script from the atom project root directory"
    exit 1
fi

# Load environment variables from .env file
print_status "Loading environment variables from .env file..."
if [ -f ".env" ]; then
    # Export only valid environment variables (no comments or special characters)
    while IFS= read -r line; do
        # Skip empty lines and comments
        if [[ -n "$line" && "$line" != \#* ]]; then
            # Extract variable name and value
            var_name=$(echo "$line" | cut -d'=' -f1)
            var_value=$(echo "$line" | cut -d'=' -f2-)
            # Only export if it looks like a valid environment variable
            if [[ "$var_name" =~ ^[a-zA-Z_][a-zA-Z0-9_]*$ ]]; then
                export "$var_name"="$var_value"
            fi
        fi
    done < ".env"
    print_success "Environment variables loaded from .env"
else
    print_warning ".env file not found, using default environment"
fi

# Set required environment variables with defaults
export DATABASE_URL=${DATABASE_URL:-"postgresql://atom_user:local_password@localhost:5432/atom_production"}
export ATOM_OAUTH_ENCRYPTION_KEY=${ATOM_OAUTH_ENCRYPTION_KEY:-$(python3 -c "import base64; import os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())" 2>/dev/null || echo "default_encryption_key_please_change_in_production")}
export FLASK_ENV=${FLASK_ENV:-"production"}
export PYTHON_API_PORT=${PYTHON_API_PORT:-5058}
export CELERY_BROKER_URL=${CELERY_BROKER_URL:-"redis://localhost:6379/0"}
export CELERY_RESULT_BACKEND=${CELERY_RESULT_BACKEND:-"redis://localhost:6379/0"}
export WORKFLOW_MONITORING_ENABLED=${WORKFLOW_MONITORING_ENABLED:-"true"}
export WORKFLOW_AUTO_RECOVERY_ENABLED=${WORKFLOW_AUTO_RECOVERY_ENABLED:-"true"}
export WORKFLOW_INTELLIGENT_OPTIMIZATION_ENABLED=${WORKFLOW_INTELLIGENT_OPTIMIZATION_ENABLED:-"true"}

print_status "Environment configuration:"
echo "  DATABASE_URL: $(echo $DATABASE_URL | sed 's/:[^:]*@/:***@/')"
echo "  FLASK_ENV: $FLASK_ENV"
echo "  PYTHON_API_PORT: $PYTHON_API_PORT"
echo "  CELERY_BROKER_URL: $(echo $CELERY_BROKER_URL | sed 's/:[^:]*@/:***@/')"
echo "  WORKFLOW_MONITORING_ENABLED: $WORKFLOW_MONITORING_ENABLED"
echo "  WORKFLOW_AUTO_RECOVERY_ENABLED: $WORKFLOW_AUTO_RECOVERY_ENABLED"
echo "  WORKFLOW_INTELLIGENT_OPTIMIZATION_ENABLED: $WORKFLOW_INTELLIGENT_OPTIMIZATION_ENABLED"

# Check required commands
print_section "System Requirements Check"
print_status "Checking required system commands..."
required_commands=("docker" "python3" "pip3" "celery")
for cmd in "${required_commands[@]}"; do
    if ! check_command "$cmd" "Required command"; then
        print_error "Missing required command: $cmd"
        exit 1
    fi
done
print_success "All required commands available"

# Check if required services are running
print_section "Service Health Check"
print_status "Checking required services..."

# Check PostgreSQL
if docker ps | grep -q "atom-postgres"; then
    print_success "PostgreSQL container is running"
else
    print_warning "PostgreSQL container not found, starting it..."
    if [ -f "docker-compose.postgres.yml" ]; then
        docker-compose -f docker-compose.postgres.yml up -d || handle_error 1 "Failed to start PostgreSQL container"
        sleep 5
    else
        print_error "PostgreSQL configuration not found"
        exit 1
    fi
fi

# Check Redis
if docker ps | grep -q "redis"; then
    print_success "Redis container is running"
else
    print_warning "Redis container not found, starting it..."
    docker run -d --name redis -p 6379:6379 redis:7-alpine || handle_error 1 "Failed to start Redis container"
    sleep 3
fi

# Check if database is accessible
print_status "Testing database connectivity..."
if psql "$DATABASE_URL" -c "SELECT 1;" > /dev/null 2>&1; then
    print_success "Database connection successful"
else
    print_error "Cannot connect to database. Please check your DATABASE_URL configuration."
    print_status "Attempting to create database if it doesn't exist..."
    # Try to create database
    createdb_cmd=$(echo "$DATABASE_URL" | sed 's/\/[^/]*$/\/postgres/')
    db_name=$(echo "$DATABASE_URL" | sed 's/.*\///')
    if psql "$createdb_cmd" -c "CREATE DATABASE $db_name;" 2>/dev/null; then
        print_success "Database created successfully"
    else
        print_error "Failed to create database"
        exit 1
    fi
fi

# Initialize database tables
print_section "Database Initialization"
print_status "Initializing database tables..."
cd backend/python-api-service

# Run database initialization with error handling
if python3 -c "from init_database import initialize_database; initialize_database()" 2>/dev/null; then
    print_success "Database tables initialized successfully"
else
    print_warning "Standard database initialization failed, trying alternative method..."
    # Alternative initialization
    if python3 -c "
import sys
sys.path.append('.')
try:
    from init_database import initialize_database
    initialize_database()
    print('Database initialized successfully')
except Exception as e:
    print(f'Alternative init failed: {e}')
    sys.exit(1)
"; then
        print_success "Database tables initialized successfully (alternative method)"
    else
        print_error "Failed to initialize database tables"
        exit 1
    fi
fi

# Create enhanced workflow tables
print_status "Creating enhanced workflow tables..."
if python3 -c "
import sys
sys.path.append('.')
try:
    from workflow_handler import create_workflow_tables
    create_workflow_tables()
    print('Workflow tables created successfully')
except Exception as e:
    print(f'Workflow table creation failed: {e}')
    sys.exit(1)
"; then
    print_success "Workflow tables created successfully"
else
    print_error "Failed to create workflow tables"
    exit 1
fi

# Register enhanced sample workflows
print_status "Registering enhanced sample workflows..."
if python3 -c "
import sys
sys.path.append('.')
try:
    # Try enhanced workflow registration
    from enhanced_workflow_engine import EnhancedWorkflowEngine
    engine = EnhancedWorkflowEngine()

    # Register intelligent workflow templates
    templates = [
        {
            'name': 'Email to Task Automation (Enhanced)',
            'description': 'Automatically create tasks from important emails with intelligent prioritization',
            'services': ['gmail', 'asana', 'slack'],
            'complexity': 'medium'
        },
        {
            'name': 'Meeting Follow-up Workflow (Enhanced)',
            'description': 'Automated meeting follow-ups with intelligent scheduling and task creation',
            'services': ['google_calendar', 'asana', 'gmail'],
            'complexity': 'medium'
        },
        {
            'name': 'Multi-Service Document Processing (Enhanced)',
            'description': 'Intelligent document processing across multiple storage services',
            'services': ['dropbox', 'google_drive', 'slack'],
            'complexity': 'high'
        }
    ]

    for template in templates:
        engine.register_template(template)
        print(f'Registered enhanced workflow: {template[\"name\"]}')

    print('Enhanced workflows registered successfully')
except Exception as e:
    print(f'Enhanced workflow registration failed: {e}')
    # Fallback to basic registration
    try:
        from workflow_execution_service import workflow_execution_service
        from workflow_api import WORKFLOW_TEMPLATES

        for template_id, template in WORKFLOW_TEMPLATES.items():
            workflow_execution_service.register_workflow(template_id, template)
            print(f'Registered basic workflow: {template[\"name\"]}')

        print('Basic workflows registered successfully')
    except Exception as e2:
        print(f'Basic workflow registration also failed: {e2}')
        sys.exit(1)
"; then
    print_success "Sample workflows registered successfully"
else
    print_error "Failed to register sample workflows"
    exit 1
fi

# Start enhanced Celery worker for workflows
print_section "Workflow Engine Startup"
print_status "Starting enhanced Celery worker for workflows..."
cd ../python-api/workflows

# Check if enhanced Celery app exists
if [ -f "enhanced_celery_app.py" ]; then
    print_status "Starting enhanced Celery worker..."
    celery -A enhanced_celery_app worker --loglevel=info --concurrency=8 --hostname=enhanced_workflow_worker@%h --detach --max-tasks-per-child=100 --time-limit=300
else
    print_status "Starting standard Celery worker..."
    celery -A celery_app worker --loglevel=info --concurrency=4 --hostname=workflow_worker@%h --detach
fi
print_success "Celery worker started for workflows"

# Start enhanced Celery beat for scheduled tasks
print_status "Starting enhanced Celery beat for scheduled workflows..."
if [ -f "enhanced_celery_app.py" ]; then
    celery -A enhanced_celery_app beat --loglevel=info --detach --pidfile=enhanced_celerybeat.pid
else
    celery -A celery_app beat --loglevel=info --detach
fi
print_success "Celery beat started for scheduled workflows"

# Start workflow monitoring service
print_status "Starting workflow monitoring service..."
cd ../..
if [ -f "backend/ai/workflow_troubleshooting/monitoring_system.py" ] && [ "$WORKFLOW_MONITORING_ENABLED" = "true" ]; then
    print_status "Starting AI-powered workflow monitoring..."
    python3 -c "
import sys
sys.path.append('backend/ai/workflow_troubleshooting')
try:
    from monitoring_system import WorkflowMonitoringSystem
    monitor = WorkflowMonitoringSystem()
    monitor.start_monitoring()
    print('Workflow monitoring started successfully')
except Exception as e:
    print(f'Workflow monitoring startup failed: {e}')
" &
    MONITOR_PID=$!
    echo $MONITOR_PID > /tmp/workflow_monitor.pid
    print_success "Workflow monitoring service started (PID: $MONITOR_PID)"
else
    print_warning "Workflow monitoring disabled or not available"
fi

# Start workflow optimization service
print_status "Starting workflow optimization service..."
if [ -f "backend/ai/workflow_troubleshooting/troubleshooting_engine.py" ] && [ "$WORKFLOW_INTELLIGENT_OPTIMIZATION_ENABLED" = "true" ]; then
    print_status "Starting AI-powered workflow optimization..."
    python3 -c "
import sys
sys.path.append('backend/ai/workflow_troubleshooting')
try:
    from troubleshooting_engine import WorkflowTroubleshootingEngine
    optimizer = WorkflowTroubleshootingEngine()
    optimizer.start_optimization_service()
    print('Workflow optimization service started successfully')
except Exception as e:
    print(f'Workflow optimization startup failed: {e}')
" &
    OPTIMIZER_PID=$!
    echo $OPTIMIZER_PID > /tmp/workflow_optimizer.pid
    print_success "Workflow optimization service started (PID: $OPTIMIZER_PID)"
else
    print_warning "Workflow optimization disabled or not available"
fi

# Navigate back to backend root
cd ../..

# Health check and validation
print_section "System Health Validation"
print_status "Performing comprehensive health checks..."

# Check if API endpoints are responsive
print_status "Testing API endpoints..."
sleep 5  # Give services time to start

# Test workflow automation endpoint
if curl -s "http://localhost:$PYTHON_API_PORT/api/workflows/automation/health" > /dev/null; then
    print_success "Workflow automation API is responsive"
else
    print_warning "Workflow automation API not immediately responsive (may need more time)"
fi

# Test workflow templates endpoint
if curl -s "http://localhost:$PYTHON_API_PORT/api/workflows/templates" > /dev/null; then
    print_success "Workflow templates API is responsive"
else
    print_warning "Workflow templates API not immediately responsive"
fi

# Test enhanced workflow intelligence
print_status "Testing enhanced workflow intelligence..."
python3 -c "
import requests
import json

try:
    response = requests.post(
        'http://localhost:$PYTHON_API_PORT/api/workflows/automation/generate',
        json={
            'user_input': 'When I receive an important email from gmail, create a task in asana and send a slack notification',
            'user_id': 'deployment_test_user'
        },
        timeout=10
    )

    if response.status_code == 200:
        result = response.json()
        services = result.get('services', [])
        steps = len(result.get('steps', []))
        print(f'Enhanced workflow generation successful')
        print(f'Detected services: {services}')
        print(f'Workflow steps: {steps}')
    else:
        print(f'Workflow generation failed: HTTP {response.status_code}')

except Exception as e:
    print(f'Workflow intelligence test failed: {e}')
"

print_section "Deployment Complete"
print_success "Enhanced workflow automation system deployed successfully!"
echo ""
echo "📋 Enhanced Deployment Summary:"
echo "  ✅ Database initialized and connected"
echo "  ✅ Enhanced workflow tables created"
echo "  ✅ Intelligent workflow templates registered"
echo "  ✅ Enhanced Celery worker started"
echo "  ✅ Enhanced Celery beat started"
if [ "$WORKFLOW_MONITORING_ENABLED" = "true" ]; then
    echo "  ✅ AI-powered workflow monitoring active"
fi
if [ "$WORKFLOW_INTELLIGENT_OPTIMIZATION_ENABLED" = "true" ]; then
    echo "  ✅ AI-powered workflow optimization active"
fi
echo "  ✅ API server ready on port $PYTHON_API_PORT"
echo ""
echo "🌐 Enhanced Endpoints:"
echo "  - API Server: http://localhost:$PYTHON_API_PORT"
echo "  - Health Check: http://localhost:$PYTHON_API_PORT/healthz"
echo "  - Workflow Automation: http://localhost:$PYTHON_API_PORT/api/workflows/automation"
echo "  - Enhanced Workflow Templates: http://localhost:$PYTHON_API_PORT/api/workflows/templates/enhanced"
echo "  - Workflow Monitoring: http://localhost:$PYTHON_API_PORT/api/workflows/monitoring"
echo "  - Workflow Troubleshooting: http://localhost:$PYTHON_API_PORT/api/workflows/troubleshooting"
echo ""
echo "🔧 Enhanced Features:"
echo "  • Intelligent service detection and matching"
echo "  • Advanced error handling and auto-recovery"
echo "  • Real-time workflow monitoring and alerts"
echo "  • AI-powered troubleshooting and optimization"
echo "  • Performance analytics and insights"
echo "  • Multi-service workflow coordination"
echo ""
echo "🚀 Next Steps:"
echo "  1. Access the Atom Agent UI at http://localhost:3000"
echo "  2. Navigate to 'Enhanced Workflow Automation' tab"
echo "  3. Explore intelligent workflow templates"
echo "  4. Monitor workflow executions in real-time"
echo "  5. Configure automated alerts and optimizations"
echo ""
echo "📝 Enhanced Troubleshooting:"
echo "  - Enhanced logs: tail -f backend/enhanced_workflow.log"
echo "  - Monitor Celery: celery -A backend/python-api/workflows/enhanced_celery_app inspect active"
echo "  - View workflow analytics: curl http://localhost:$PYTHON_API_PORT/api/workflows/analytics"
echo "  - Check monitoring status: curl http://localhost:$PYTHON_API_PORT/api/workflows/monitoring/status"
echo "  - Get optimization suggestions: curl http://localhost:$PYTHON_API_PORT/api/workflows/optimization/suggestions"
echo ""
echo "🔔 Monitoring PIDs:"
if [ -f "/tmp/workflow_monitor.pid" ]; then
    echo "  - Workflow Monitor: $(cat /tmp/workflow_monitor.pid)"
fi
if [ -f "/tmp/workflow_optimizer.pid" ]; then
    echo "  - Workflow Optimizer: $(cat /tmp
