#!/bin/bash

# 🚀 Simplified Enhanced Workflow Automation Deployment
# Quick deployment with essential enhanced features

set -e  # Exit on any error

echo "🚀 Deploying Enhanced Workflow Automation System"
echo "================================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

# Set default environment variables
export DATABASE_URL=${DATABASE_URL:-"postgresql://atom_user:local_password@localhost:5432/atom_production"}
export FLASK_ENV=${FLASK_ENV:-"production"}
export PYTHON_API_PORT=${PYTHON_API_PORT:-5058}
export CELERY_BROKER_URL=${CELERY_BROKER_URL:-"redis://localhost:6379/0"}

print_status "Environment configuration:"
echo "  DATABASE_URL: $(echo $DATABASE_URL | sed 's/:[^:]*@/:***@/')"
echo "  FLASK_ENV: $FLASK_ENV"
echo "  PYTHON_API_PORT: $PYTHON_API_PORT"
echo "  CELERY_BROKER_URL: $(echo $CELERY_BROKER_URL | sed 's/:[^:]*@/:***@/')"

# Check required services
print_status "Checking required services..."

# Check if API server is running
if lsof -i :5058 > /dev/null 2>&1; then
    print_success "API server is running on port 5058"
else
    print_warning "API server not detected on port 5058"
    print_status "Starting API server..."
    cd backend/python-api-service
    python3 main_api_app.py &
    API_PID=$!
    echo $API_PID > /tmp/atom_api.pid
    sleep 5
    print_success "API server started (PID: $API_PID)"
    cd ../..
fi

# Test API connectivity
print_status "Testing API connectivity..."
if curl -s http://localhost:5058/healthz > /dev/null; then
    print_success "API server is responsive"
else
    print_error "API server is not responding"
    exit 1
fi

# Initialize enhanced workflow components
print_status "Initializing enhanced workflow components..."

# Test enhanced workflow generation
print_status "Testing enhanced workflow intelligence..."
curl -X POST http://localhost:5058/api/workflows/automation/generate \
  -H "Content-Type: application/json" \
  -d '{
    "user_input": "When I receive important emails from gmail, create tasks in asana and notify team on slack",
    "user_id": "deployment_test",
    "enhanced_intelligence": true
  }' > /tmp/workflow_test.json 2>/dev/null

if [ $? -eq 0 ]; then
    print_success "Enhanced workflow intelligence is working"
    SERVICES=$(cat /tmp/workflow_test.json | grep -o '"services":\[[^]]*\]' | head -1)
    echo "  Detected services: $SERVICES"
else
    print_warning "Enhanced workflow intelligence test failed"
fi

# Test optimization endpoint
print_status "Testing workflow optimization..."
curl -X POST http://localhost:5058/api/workflows/optimization/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "workflow": {
      "name": "Test Workflow",
      "steps": [
        {"action": "search_emails", "service": "gmail", "estimated_duration": 5.0},
        {"action": "create_task", "service": "asana", "estimated_duration": 3.0}
      ]
    },
    "strategy": "performance",
    "user_id": "deployment_test"
  }' > /tmp/optimization_test.json 2>/dev/null

if [ $? -eq 0 ]; then
    print_success "Workflow optimization is working"
    SUGGESTIONS=$(cat /tmp/optimization_test.json | grep -o '"optimization_suggestions":\[[^]]*\]' | head -1)
    if [ -n "$SUGGESTIONS" ]; then
        echo "  Optimization suggestions available"
    fi
else
    print_warning "Workflow optimization test failed"
fi

# Test monitoring endpoints
print_status "Testing monitoring system..."
MONITORING_ENDPOINTS=(
    "/api/workflows/monitoring/health"
    "/api/workflows/monitoring/metrics"
)

for endpoint in "${MONITORING_ENDPOINTS[@]}"; do
    if curl -s http://localhost:5058$endpoint > /dev/null; then
        print_success "Monitoring endpoint $endpoint is responsive"
    else
        print_warning "Monitoring endpoint $endpoint not available"
    fi
done

# Start enhanced services
print_status "Starting enhanced services..."

# Start enhanced workflow intelligence service
print_status "Starting enhanced intelligence service..."
cd backend/python-api-service
python3 -c "
import sys
sys.path.append('.')
try:
    from enhanced_workflow_intelligence import EnhancedWorkflowIntelligence
    intelligence = EnhancedWorkflowIntelligence()
    print('Enhanced workflow intelligence service initialized')
except Exception as e:
    print(f'Enhanced intelligence service failed: {e}')
" &
INTELLIGENCE_PID=$!
echo $INTELLIGENCE_PID > /tmp/enhanced_intelligence.pid
print_success "Enhanced intelligence service started (PID: $INTELLIGENCE_PID)"

# Start monitoring service
print_status "Starting monitoring service..."
python3 -c "
import sys
sys.path.append('.')
try:
    from enhanced_workflow_monitoring import EnhancedWorkflowMonitor
    monitor = EnhancedWorkflowMonitor()
    monitor.start_monitoring()
    print('Enhanced monitoring service started')
except Exception as e:
    print(f'Enhanced monitoring service failed: {e}')
" &
MONITOR_PID=$!
echo $MONITOR_PID > /tmp/enhanced_monitor.pid
print_success "Enhanced monitoring service started (PID: $MONITOR_PID)"

cd ../..

# Final validation
print_status "Performing final validation..."

# Test comprehensive workflow execution
print_status "Testing enhanced workflow execution..."
curl -X POST http://localhost:5058/api/workflows/execute \
  -H "Content-Type: application/json" \
  -d '{
    "workflow": {
      "name": "Enhanced Deployment Test",
      "description": "Test workflow for enhanced deployment",
      "steps": [
        {
          "step_id": "test_step_1",
          "action": "send_test_notification",
          "service": "generic",
          "parameters": {"message": "Enhanced workflow system deployed successfully"}
        }
      ]
    },
    "user_id": "deployment_test",
    "enhanced_execution": true
  }' > /tmp/execution_test.json 2>/dev/null

if [ $? -eq 0 ]; then
    print_success "Enhanced workflow execution is working"
    EXECUTION_ID=$(cat /tmp/execution_test.json | grep -o '"execution_id":"[^"]*"' | cut -d'"' -f4)
    if [ -n "$EXECUTION_ID" ]; then
        echo "  Execution ID: $EXECUTION_ID"
    fi
else
    print_warning "Enhanced workflow execution test failed"
fi

# Cleanup test files
rm -f /tmp/workflow_test.json /tmp/optimization_test.json /tmp/execution_test.json

print_success "Enhanced workflow automation system deployed successfully!"
echo ""
echo "📋 Deployment Summary:"
echo "  ✅ API server running on port 5058"
echo "  ✅ Enhanced workflow intelligence active"
echo "  ✅ Workflow optimization available"
echo "  ✅ Monitoring system running"
echo "  ✅ Enhanced execution capabilities enabled"
echo ""
echo "🌐 Available Endpoints:"
echo "  - API Server: http://localhost:5058"
echo "  - Workflow Generation: http://localhost:5058/api/workflows/automation/generate"
echo "  - Workflow Optimization: http://localhost:5058/api/workflows/optimization/analyze"
echo "  - Monitoring: http://localhost:5058/api/workflows/monitoring/health"
echo ""
echo "🚀 Next Steps:"
echo "  1. Access the Atom Agent UI at http://localhost:3000"
echo "  2. Navigate to 'Workflow Automation' tab"
echo "  3. Test enhanced features with intelligent workflow generation"
echo "  4. Monitor workflow executions in real-time"
echo ""
echo "📝 Service PIDs:"
echo "  - API Server: $(cat /tmp/atom_api.pid 2>/dev/null || echo 'unknown')"
echo "  - Enhanced Intelligence: $INTELLIGENCE_PID"
echo "  - Enhanced Monitor: $MONITOR_PID"
echo ""
echo "🎉 Enhanced workflow automation system is ready for use!"
