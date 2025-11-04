#!/bin/bash

# 🚀 ATOM External Service Configuration Validator
# Validates and tests external service configurations for production deployment

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

# Print banner
print_banner() {
    echo -e "${BLUE}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║              ATOM EXTERNAL SERVICE VALIDATOR                ║"
    echo "║                    Configuration Check                      ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."

    # Check if environment file exists
    if [ ! -f ".env.production" ]; then
        log_error ".env.production file not found"
        log_info "Please create it from .env.production.template"
        exit 1
    fi

    # Check if backend is running
    if ! curl -s http://localhost:5059/healthz > /dev/null; then
        log_warning "Backend server not running on port 5059"
        log_info "Please start the backend server first"
        exit 1
    fi

    log_success "All prerequisites satisfied"
}

# Load and validate environment variables
load_environment() {
    log_info "Loading environment variables..."

    # Source the production environment file
    set -a  # Automatically export all variables
    source .env.production
    set +a

    log_success "Environment variables loaded from .env.production"
}

# Validate individual service configurations
validate_openai() {
    log_info "Validating OpenAI configuration..."

    if [ -z "$OPENAI_API_KEY" ] || [ "$OPENAI_API_KEY" = "sk-your-production-openai-api-key-here" ]; then
        log_error "OpenAI API Key not configured"
        return 1
    fi

    # Test OpenAI key format (basic validation)
    if [[ "$OPENAI_API_KEY" =~ ^sk-[a-zA-Z0-9]+$ ]]; then
        log_success "OpenAI API Key: Valid format"
        return 0
    else
        log_error "OpenAI API Key: Invalid format"
        return 1
    fi
}

validate_google_oauth() {
    log_info "Validating Google OAuth configuration..."

    local missing_vars=()

    if [ -z "$ATOM_GDRIVE_CLIENT_ID" ] || [ "$ATOM_GDRIVE_CLIENT_ID" = "your-google-client-id.apps.googleusercontent.com" ]; then
        missing_vars+=("ATOM_GDRIVE_CLIENT_ID")
    fi

    if [ -z "$ATOM_GDRIVE_CLIENT_SECRET" ] || [ "$ATOM_GDRIVE_CLIENT_SECRET" = "your-google-client-secret" ]; then
        missing_vars+=("ATOM_GDRIVE_CLIENT_SECRET")
    fi

    if [ -z "$ATOM_GDRIVE_REDIRECT_URI" ]; then
        missing_vars+=("ATOM_GDRIVE_REDIRECT_URI")
    fi

    if [ ${#missing_vars[@]} -eq 0 ]; then
        log_success "Google OAuth: All variables configured"
        return 0
    else
        log_error "Google OAuth: Missing variables: ${missing_vars[*]}"
        return 1
    fi
}

validate_notion() {
    log_info "Validating Notion configuration..."

    local missing_vars=()

    if [ -z "$NOTION_CLIENT_ID" ] || [ "$NOTION_CLIENT_ID" = "your-notion-client-id" ]; then
        missing_vars+=("NOTION_CLIENT_ID")
    fi

    if [ -z "$NOTION_CLIENT_SECRET" ] || [ "$NOTION_CLIENT_SECRET" = "your-notion-client-secret" ]; then
        missing_vars+=("NOTION_CLIENT_SECRET")
    fi

    if [ ${#missing_vars[@]} -eq 0 ]; then
        log_success "Notion Integration: All variables configured"
        return 0
    else
        log_warning "Notion Integration: Missing variables: ${missing_vars[*]}"
        return 1
    fi
}

validate_trello() {
    log_info "Validating Trello configuration..."

    local missing_vars=()

    if [ -z "$TRELLO_API_KEY" ] || [ "$TRELLO_API_KEY" = "your-trello-api-key" ]; then
        missing_vars+=("TRELLO_API_KEY")
    fi

    if [ -z "$TRELLO_API_TOKEN" ] || [ "$TRELLO_API_TOKEN" = "your-trello-api-token" ]; then
        missing_vars+=("TRELLO_API_TOKEN")
    fi

    if [ ${#missing_vars[@]} -eq 0 ]; then
        log_success "Trello Integration: All variables configured"
        return 0
    else
        log_warning "Trello Integration: Missing variables: ${missing_vars[*]}"
        return 1
    fi
}

validate_dropbox() {
    log_info "Validating Dropbox configuration..."

    local missing_vars=()

    if [ -z "$DROPBOX_CLIENT_ID" ] || [ "$DROPBOX_CLIENT_ID" = "your-dropbox-client-id" ]; then
        missing_vars+=("DROPBOX_CLIENT_ID")
    fi

    if [ -z "$DROPBOX_CLIENT_SECRET" ] || [ "$DROPBOX_CLIENT_SECRET" = "your-dropbox-client-secret" ]; then
        missing_vars+=("DROPBOX_CLIENT_SECRET")
    fi

    if [ ${#missing_vars[@]} -eq 0 ]; then
        log_success "Dropbox Integration: All variables configured"
        return 0
    else
        log_warning "Dropbox Integration: Missing variables: ${missing_vars[*]}"
        return 1
    fi
}

validate_asana() {
    log_info "Validating Asana configuration..."

    local missing_vars=()

    if [ -z "$ASANA_CLIENT_ID" ] || [ "$ASANA_CLIENT_ID" = "your-asana-client-id" ]; then
        missing_vars+=("ASANA_CLIENT_ID")
    fi

    if [ -z "$ASANA_CLIENT_SECRET" ] || [ "$ASANA_CLIENT_SECRET" = "your-asana-client-secret" ]; then
        missing_vars+=("ASANA_CLIENT_SECRET")
    fi

    if [ ${#missing_vars[@]} -eq 0 ]; then
        log_success "Asana Integration: All variables configured"
        return 0
    else
        log_warning "Asana Integration: Missing variables: ${missing_vars[*]}"
        return 1
    fi
}

validate_plaid() {
    log_info "Validating Plaid configuration..."

    local missing_vars=()

    if [ -z "$PLAID_CLIENT_ID" ] || [ "$PLAID_CLIENT_ID" = "your-plaid-client-id" ]; then
        missing_vars+=("PLAID_CLIENT_ID")
    fi

    if [ -z "$PLAID_SECRET" ] || [ "$PLAID_SECRET" = "your-plaid-secret" ]; then
        missing_vars+=("PLAID_SECRET")
    fi

    if [ ${#missing_vars[@]} -eq 0 ]; then
        log_success "Plaid Integration: All variables configured"
        return 0
    else
        log_warning "Plaid Integration: Missing variables: ${missing_vars[*]}"
        return 1
    fi
}

# Test service connectivity
test_backend_connectivity() {
    log_info "Testing backend connectivity..."

    if curl -s http://localhost:5059/healthz | grep -q '"status":"ok"'; then
        log_success "Backend connectivity: PASS"
        return 0
    else
        log_error "Backend connectivity: FAIL"
        return 1
    fi
}

test_openai_connectivity() {
    log_info "Testing OpenAI connectivity..."

    # This would require actual API call, but we'll just validate configuration
    if validate_openai; then
        log_success "OpenAI configuration: READY FOR TESTING"
        return 0
    else
        return 1
    fi
}

test_oauth_endpoints() {
    log_info "Testing OAuth endpoints..."

    local endpoints=(
        "/api/auth/gdrive/initiate"
        "/api/auth/dropbox/initiate"
        "/api/auth/notion/initiate"
        "/api/auth/asana/initiate"
    )

    local all_working=true

    for endpoint in "${endpoints[@]}"; do
        if curl -s "http://localhost:5059${endpoint}?user_id=test" > /dev/null; then
            log_success "Endpoint $endpoint: RESPONSIVE"
        else
            log_warning "Endpoint $endpoint: UNRESPONSIVE"
            all_working=false
        fi
    done

    if $all_working; then
        return 0
    else
        return 1
    fi
}

# Generate configuration summary
generate_summary() {
    echo -e "${GREEN}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                  CONFIGURATION SUMMARY                      ║"
    echo "╠══════════════════════════════════════════════════════════════╣"
    echo "║                                                              ║"

    # OpenAI status
    if validate_openai > /dev/null; then
        echo "║  ✅ OpenAI API:          Configured and ready                ║"
    else
        echo "║  ❌ OpenAI API:          Not configured                     ║"
    fi

    # Google OAuth status
    if validate_google_oauth > /dev/null; then
        echo "║  ✅ Google OAuth:        Configured and ready                ║"
    else
        echo "║  ❌ Google OAuth:        Not configured                     ║"
    fi

    # Notion status
    if validate_notion > /dev/null; then
        echo "║  ✅ Notion Integration:  Configured and ready                ║"
    else
        echo "║  ⚠️  Notion Integration:  Partially configured               ║"
    fi

    # Trello status
    if validate_trello > /dev/null; then
        echo "║  ✅ Trello Integration:  Configured and ready                ║"
    else
        echo "║  ⚠️  Trello Integration:  Partially configured               ║"
    fi

    # Dropbox status
    if validate_dropbox > /dev/null; then
        echo "║  ✅ Dropbox Integration: Configured and ready                ║"
    else
        echo "║  ⚠️  Dropbox Integration: Partially configured               ║"
    fi

    # Asana status
    if validate_asana > /dev/null; then
        echo "║  ✅ Asana Integration:   Configured and ready                ║"
    else
        echo "║  ⚠️  Asana Integration:   Partially configured               ║"
    fi

    # Plaid status
    if validate_plaid > /dev/null; then
        echo "║  ✅ Plaid Integration:   Configured and ready                ║"
    else
        echo "║  ⚠️  Plaid Integration:   Partially configured               ║"
    fi

    echo "║                                                              ║"
    echo "║  Next Steps:                                                 ║"
    echo "║  1. Configure missing service credentials                    ║"
    echo "║  2. Restart backend after configuration changes              ║"
    echo "║  3. Test individual integrations with real data              ║"
    echo "║  4. Monitor application logs for errors                      ║"
    echo "║                                                              ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

# Main execution function
main() {
    print_banner

    # Execute validation steps
    check_prerequisites
    load_environment

    echo ""
    log_info "Starting service configuration validation..."
    echo ""

    # Validate individual services
    validate_openai
    validate_google_oauth
    validate_notion
    validate_trello
    validate_dropbox
    validate_asana
    validate_plaid

    echo ""
    log_info "Starting connectivity tests..."
    echo ""

    # Test connectivity
    test_backend_connectivity
    test_openai_connectivity
    test_oauth_endpoints

    echo ""
    generate_summary

    log_info "Configuration validation completed"
}

# Help function
show_help() {
    echo "ATOM External Service Configuration Validator"
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -h, --help    Show this help message"
    echo "  -q, --quick   Quick validation only (skip connectivity tests)"
    echo ""
    echo "Description:"
    echo "  Validates external service configurations for ATOM production deployment"
    echo "  Checks environment variables, service connectivity, and OAuth endpoints"
    echo ""
    echo "Prerequisites:"
    echo "  - Backend server running on port 5059"
    echo "  - .env.production file with service credentials"
    echo ""
    echo "Examples:"
    echo "  $0              # Full validation"
    echo "  $0 --quick      # Quick configuration check only"
}

# Parse command line arguments
case "${1:-}" in
    -h|--help)
        show_help
        exit 0
        ;;
    -q|--quick)
        # Quick validation mode
        check_prerequisites
        load_environment
        validate_openai
        validate_google_oauth
        validate_notion
        validate_trello
        validate_dropbox
        validate_asana
        validate_plaid
        generate_summary
        ;;
    *)
        main
        ;;
esac
