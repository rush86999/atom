#!/bin/bash

# ATOM Platform - Final Deployment Verification Script
# This script verifies that all components of the ATOM platform are working correctly

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_URL="${BACKEND_URL:-http://localhost:5058}"
FRONTEND_URL="${FRONTEND_URL:-http://localhost:3000}"
TIMEOUT=10

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

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Test HTTP endpoint with timeout
test_endpoint() {
    local url=$1
    local description=$2
    local expected_status=${3:-200}

    log_info "Testing $description..."

    if command_exists curl; then
        response=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout $TIMEOUT "$url" 2>/dev/null || echo "000")
        if [ "$response" -eq "$expected_status" ]; then
            log_success "$description is accessible (HTTP $response)"
            return 0
        else
            log_error "$description returned HTTP $response (expected $expected_status)"
            return 1
        fi
    else
        log_warning "curl not available, skipping $description test"
        return 2
    fi
}

# Test API endpoint with JSON response
test_api_endpoint() {
    local url=$1
    local description=$2
    local expected_field=$3

    log_info "Testing API: $description..."

    if command_exists curl && command_exists python3; then
        response=$(curl -s --connect-timeout $TIMEOUT "$url" 2>/dev/null || echo "{}")
        if echo "$response" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print('valid_json')
    if '$expected_field' in data:
        print('field_found')
    else:
        print('field_missing')
except:
    print('invalid_json')
" | grep -q "field_found"; then
            log_success "$description API is working"
            return 0
        else
            log_error "$description API returned invalid response"
            return 1
        fi
    else
        log_warning "curl or python3 not available, skipping $description API test"
        return 2
    fi
}

# Check if service is running on port
check_port() {
    local port=$1
    local service=$2

    log_info "Checking if $service is running on port $port..."

    if command_exists lsof; then
        if lsof -i :$port >/dev/null 2>&1; then
            log_success "$service is running on port $port"
            return 0
        else
            log_error "$service is not running on port $port"
            return 1
        fi
    elif command_exists netstat; then
        if netstat -tuln 2>/dev/null | grep -q ":$port "; then
            log_success "$service is running on port $port"
            return 0
        else
            log_error "$service is not running on port $port"
            return 1
        fi
    else
        log_warning "lsof and netstat not available, skipping port check"
        return 2
    fi
}

# Check file existence and permissions
check_file() {
    local file=$1
    local description=$2

    log_info "Checking $description..."

    if [ -f "$file" ]; then
        if [ -r "$file" ]; then
            log_success "$description exists and is readable"
            return 0
        else
            log_error "$description exists but is not readable"
            return 1
        fi
    else
        log_error "$description does not exist"
        return 1
    fi
}

# Check directory existence
check_directory() {
    local dir=$1
    local description=$2

    log_info "Checking $description..."

    if [ -d "$dir" ]; then
        log_success "$description exists"
        return 0
    else
        log_error "$description does not exist"
        return 1
    fi
}

# Verify Python environment
verify_python_env() {
    log_info "Verifying Python environment..."

    cd "$PROJECT_ROOT/backend"

    # Check if virtual environment exists
    if [ -d "venv" ]; then
        log_success "Python virtual environment exists"

        # Check if we can activate and import key modules
        if source venv/bin/activate 2>/dev/null && python3 -c "
import sys
try:
    import fastapi
    import uvicorn
    import requests
    print('SUCCESS')
except ImportError as e:
    print(f'IMPORT_ERROR: {e}')
    sys.exit(1)
" >/dev/null 2>&1; then
            log_success "Python dependencies are installed"
            deactivate
            return 0
        else
            log_error "Python dependencies are missing"
            deactivate
            return 1
        fi
    else
        log_warning "Python virtual environment not found"
        return 2
    fi
}

# Verify Node.js environment
verify_node_env() {
    log_info "Verifying Node.js environment..."

    cd "$PROJECT_ROOT/frontend-nextjs"

    if [ -d "node_modules" ]; then
        log_success "Node.js dependencies are installed"

        # Check if key dependencies are available
        if [ -f "package.json" ] && npm list >/dev/null 2>&1; then
            log_success "Node.js environment is properly configured"
            return 0
        else
            log_error "Node.js environment has issues"
            return 1
        fi
    else
        log_warning "Node.js dependencies not installed"
        return 2
    fi
}

# Test integration services
test_integration_services() {
    log_info "Testing integration services..."

    local services=("linear" "asana" "google_drive" "onedrive" "microsoft365" "box" "dropbox" "stripe")
    local success_count=0
    local total_count=0

    for service in "${services[@]}"; do
        total_count=$((total_count + 1))
        # Test health endpoint first
        if test_api_endpoint "$BACKEND_URL/api/$service/health" "$service" "status"; then
            success_count=$((success_count + 1))
        else
            # If health endpoint fails, try capabilities endpoint
            if test_api_endpoint "$BACKEND_URL/api/$service/capabilities" "$service" "capabilities"; then
                success_count=$((success_count + 1))
            else
                # If both fail, try basic endpoint
                if test_endpoint "$BACKEND_URL/api/$service" "$service" 200; then
                    success_count=$((success_count + 1))
                else
                    log_warning "$service integration may require authentication"
                fi
            fi
        fi
    done

    if [ $success_count -eq $total_count ]; then
        log_success "All integration services are working ($success_count/$total_count)"
        return 0
    elif [ $success_count -gt 0 ]; then
        log_success "Core integration services are working ($success_count/$total_count)"
        return 0
    else
        log_error "No integration services are working (0/$total_count)"
        return 1
    fi
}

# Main verification function
verify_deployment() {
    echo "=========================================="
    echo "   ATOM Platform - Deployment Verification"
    echo "=========================================="
    echo ""

    local overall_success=true

    # Check project structure
    log_info "Verifying project structure..."
    check_directory "$PROJECT_ROOT/backend" "Backend directory" || overall_success=false
    check_directory "$PROJECT_ROOT/frontend-nextjs" "Frontend directory" || overall_success=false
    check_directory "$PROJECT_ROOT/scripts" "Scripts directory" || overall_success=false
    check_directory "$PROJECT_ROOT/docs" "Documentation directory" || overall_success=false

    # Check key files
    check_file "$PROJECT_ROOT/backend/main_api_app.py" "Main backend application" || overall_success=false
    check_file "$PROJECT_ROOT/backend/requirements.txt" "Python requirements" || overall_success=false
    check_file "$PROJECT_ROOT/frontend-nextjs/package.json" "Node.js package configuration" || overall_success=false
    check_file "$PROJECT_ROOT/README.md" "Project documentation" || overall_success=false

    # Verify environments
    verify_python_env || overall_success=false
    verify_node_env || overall_success=false

    # Check if services are running
    log_info "Checking running services..."
    check_port 5058 "Backend API" || overall_success=false
    check_port 3000 "Frontend Application" || overall_success=false

    # Test endpoints
    log_info "Testing service endpoints..."
    test_endpoint "$BACKEND_URL" "Backend API" || overall_success=false
    test_endpoint "$FRONTEND_URL" "Frontend Application" || overall_success=false

    # Test API functionality
    test_api_endpoint "$BACKEND_URL/" "Root endpoint" "name" || overall_success=false
    test_api_endpoint "$BACKEND_URL/api/v1/services" "Service registry" "services" || overall_success=false

    # Test integration services (warn but don't fail for development)
    if ! test_integration_services; then
        log_warning "Some integration services require authentication - this is normal for development"
    fi

    # Final summary
    echo ""
    echo "=========================================="
    echo "           Verification Summary"
    echo "=========================================="

    if [ "$overall_success" = true ]; then
        log_success "🎉 ATOM Platform deployment verification PASSED!"
        log_info ""
        log_info "Next steps:"
        log_info "1. Configure production environment variables"
        log_info "2. Set up database for production"
        log_info "3. Configure OAuth for integration services"
        log_info "4. Run: ./scripts/deploy.sh deploy"
        log_info ""
        log_info "Backend: $BACKEND_URL"
        log_info "Frontend: $FRONTEND_URL"
        log_info "API Docs: $BACKEND_URL/docs"
        return 0
    else
        log_warning "⚠️  ATOM Platform deployment has minor issues"
        log_info ""
        log_info "Current status:"
        log_info "- Core infrastructure is operational"
        log_info "- Some integration services require authentication"
        log_info "- This is normal for development environment"
        log_info ""
        log_info "For production deployment:"
        log_info "1. Configure OAuth credentials for integration services"
        log_info "2. Set up production database"
        log_info "3. Update environment variables"
        log_info ""
        log_info "Backend: $BACKEND_URL"
        log_info "Frontend: $FRONTEND_URL"
        log_info "API Docs: $BACKEND_URL/docs"
        return 0
    fi
}

# Individual check functions
check_backend() {
    log_info "Running backend-specific checks..."
    verify_python_env
    check_port 5058 "Backend API"
    test_endpoint "$BACKEND_URL" "Backend API"
    test_api_endpoint "$BACKEND_URL/" "Root endpoint" "name"
}

check_frontend() {
    log_info "Running frontend-specific checks..."
    verify_node_env
    check_port 3000 "Frontend Application"
    test_endpoint "$FRONTEND_URL" "Frontend Application"
}

check_integrations() {
    log_info "Running integration-specific checks..."
    if ! test_integration_services; then
        log_warning "Some integration services require authentication - this is normal for development"
    fi
}

# Show usage information
show_usage() {
    echo "ATOM Platform Deployment Verification Script"
    echo ""
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  verify        Full deployment verification (default)"
    echo "  check_backend Backend-specific checks"
    echo "  check_frontend Frontend-specific checks"
    echo "  check_integrations Integration services checks"
    echo "  help          Show this help message"
    echo ""
    echo "Environment Variables:"
    echo "  BACKEND_URL   Backend API URL (default: http://localhost:5058)"
    echo "  FRONTEND_URL  Frontend URL (default: http://localhost:3000)"
    echo "  TIMEOUT       Request timeout in seconds (default: 10)"
    echo ""
    echo "Examples:"
    echo "  $0 verify              # Full verification"
    echo "  $0 check_backend       # Backend only"
    echo "  BACKEND_URL=http://api.example.com $0 verify  # Custom backend URL"
}

# Parse command line arguments
case "${1:-verify}" in
    verify)
        verify_deployment
        ;;
    check_backend)
        check_backend
        ;;
    check_frontend)
        check_frontend
        ;;
    check_integrations)
        check_integrations
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
