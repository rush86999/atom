#!/bin/bash

# Outlook Integration Deployment Script
# Automates testing, building, and deployment of Outlook integration

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="$PROJECT_DIR/dist"
LOG_FILE="$PROJECT_DIR/deployment.log"

echo -e "${BLUE}🚀 Starting Outlook Integration Deployment${NC}"
echo "Project directory: $PROJECT_DIR"
echo "Build directory: $BUILD_DIR"
echo "Log file: $LOG_FILE"

# Create log file
touch "$LOG_FILE"

# Function to log with timestamp
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Function to check command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to show status
status() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# Function to show success
success() {
    echo -e "${GREEN}✅ $1${NC}"
}

# Function to show warning
warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

# Function to show error
error() {
    echo -e "${RED}❌ $1${NC}"
}

# Check prerequisites
check_prerequisites() {
    log "Checking prerequisites..."
    
    local missing=()
    
    if ! command_exists node; then
        missing+=("Node.js")
    fi
    
    if ! command_exists npm; then
        missing+=("npm")
    fi
    
    if ! command_exists cargo; then
        missing+=("Rust/Cargo")
    fi
    
    if ! command_exists yarn; then
        warning "yarn not found, using npm instead"
    fi
    
    if [ ${#missing[@]} -ne 0 ]; then
        error "Missing prerequisites: ${missing[*]}"
        echo "Please install the missing prerequisites and try again."
        exit 1
    fi
    
    success "All prerequisites found"
}

# Run tests
run_tests() {
    log "Running test suite..."
    
    # Change to project directory
    cd "$PROJECT_DIR"
    
    # Install dependencies
    if command_exists yarn; then
        yarn install --frozen-lockfile
    else
        npm ci
    fi
    
    # Run unit tests
    status "Running unit tests..."
    if command_exists yarn; then
        yarn test --coverage --watchAll=false
    else
        npm test -- --coverage --watchAll=false
    fi
    
    if [ $? -eq 0 ]; then
        success "Unit tests passed"
    else
        error "Unit tests failed"
        exit 1
    fi
    
    # Run integration tests
    status "Running integration tests..."
    if command_exists yarn; then
        yarn test --testPathPattern=integration --watchAll=false
    else
        npm run test:integration -- --watchAll=false
    fi
    
    if [ $? -eq 0 ]; then
        success "Integration tests passed"
    else
        error "Integration tests failed"
        exit 1
    fi
    
    success "All tests passed"
}

# Build Tauri application
build_tauri() {
    log "Building Tauri application..."
    
    cd "$PROJECT_DIR"
    
    # Build frontend
    status "Building frontend..."
    if command_exists yarn; then
        yarn build
    else
        npm run build
    fi
    
    if [ $? -eq 0 ]; then
        success "Frontend built successfully"
    else
        error "Frontend build failed"
        exit 1
    fi
    
    # Build Tauri app
    status "Building Tauri application..."
    
    # Detect OS
    case "$(uname -s)" in
        Darwin*)    TARGET="darwin";;
        Linux*)     TARGET="linux";;
        CYGWIN*|MINGW*|MSYS*) TARGET="windows";;
        *)          TARGET="unknown";;
    esac
    
    if [ "$TARGET" = "unknown" ]; then
        error "Unsupported OS for building"
        exit 1
    fi
    
    cargo tauri build --target "$TARGET"
    
    if [ $? -eq 0 ]; then
        success "Tauri application built successfully"
    else
        error "Tauri build failed"
        exit 1
    fi
}

# Create release package
create_release_package() {
    log "Creating release package..."
    
    local PACKAGE_NAME="atom-outlook-integration-$(date +%Y%m%d-%H%M%S)"
    local RELEASE_DIR="$PROJECT_DIR/release"
    
    mkdir -p "$RELEASE_DIR"
    mkdir -p "$RELEASE_DIR/$PACKAGE_NAME"
    
    # Copy built application
    cp -r "$PROJECT_DIR/src-tauri/target"/* "$RELEASE_DIR/$PACKAGE_NAME/" 2>/dev/null || true
    
    # Copy documentation
    cp -r "$PROJECT_DIR/docs" "$RELEASE_DIR/$PACKAGE_NAME/" 2>/dev/null || true
    
    # Copy configuration files
    cp "$PROJECT_DIR/package.json" "$RELEASE_DIR/$PACKAGE_NAME/" 2>/dev/null || true
    cp "$PROJECT_DIR/Cargo.toml" "$RELEASE_DIR/$PACKAGE_NAME/" 2>/dev/null || true
    cp "$PROJECT_DIR/tauri.conf.json" "$RELEASE_DIR/$PACKAGE_NAME/" 2>/dev/null || true
    
    # Create README for release
    cat > "$RELEASE_DIR/$PACKAGE_NAME/README.txt" << EOF
ATOM Outlook Integration
======================

Installation:
1. Run the appropriate installer for your OS:
   - Windows: atom-outlook-integration.exe
   - macOS: atom-outlook-integration.app
   - Linux: atom-outlook-integration.AppImage

2. Configure OAuth environment variables:
   - OUTLOOK_CLIENT_ID
   - OUTLOOK_CLIENT_SECRET
   - OUTLOOK_TENANT_ID
   - OUTLOOK_REDIRECT_URI

3. Launch the application and connect your Outlook account.

Documentation:
- See docs/OUTLOOK_INTEGRATION.md for complete documentation
- Visit https://atom.ai/support for help

Built on: $(date)
EOF
    
    # Create archive
    cd "$RELEASE_DIR"
    tar -czf "$PACKAGE_NAME.tar.gz" "$PACKAGE_NAME"
    
    success "Release package created: $RELEASE_DIR/$PACKAGE_NAME.tar.gz"
    log "Package size: $(du -h "$RELEASE_DIR/$PACKAGE_NAME.tar.gz" | cut -f1)"
}

# Run security checks
run_security_checks() {
    log "Running security checks..."
    
    cd "$PROJECT_DIR"
    
    # Check for vulnerable dependencies
    status "Checking for vulnerable dependencies..."
    if command_exists yarn; then
        yarn audit --level moderate
    else
        npm audit --audit-level moderate
    fi
    
    # Basic code security check
    status "Running basic security checks..."
    
    # Check for hardcoded secrets (basic pattern)
    if grep -r "password\|secret\|token\|key" "$PROJECT_DIR/src" --exclude-dir=node_modules | grep -v "logger\|console\|TODO\|FIXME"; then
        warning "Potential hardcoded secrets found - review before deployment"
    fi
    
    success "Security checks completed"
}

# Verify Outlook integration
verify_outlook_integration() {
    log "Verifying Outlook integration..."
    
    cd "$PROJECT_DIR"
    
    # Check if required files exist
    local required_files=(
        "src/skills/outlookSkills.ts"
        "src/components/services/outlook/OutlookDesktopManagerNew.tsx"
        "src-tauri/outlook_commands.rs"
        "src-tauri/outlook_enhanced_commands.rs"
        "src/services/nlpService.ts"
        "src/utils/EventBus.ts"
        "src/utils/Logger.ts"
        "src/EnhancedChat.tsx"
        "docs/OUTLOOK_INTEGRATION.md"
    )
    
    for file in "${required_files[@]}"; do
        if [ -f "$PROJECT_DIR/$file" ]; then
            success "Found: $file"
        else
            error "Missing required file: $file"
            exit 1
        fi
    done
    
    success "All required files present"
}

# Main deployment function
main() {
    log "Starting Outlook integration deployment process"
    
    # Clean up previous builds
    rm -rf "$BUILD_DIR" "$PROJECT_DIR/release"
    mkdir -p "$BUILD_DIR" "$PROJECT_DIR/release"
    
    # Execute deployment steps
    check_prerequisites
    verify_outlook_integration
    run_tests
    run_security_checks
    build_tauri
    create_release_package
    
    success "🎉 Outlook integration deployment completed successfully!"
    log "Deployment completed at: $(date)"
    
    echo
    echo -e "${GREEN}Deployment Summary:${NC}"
    echo -e "  • All tests passed"
    echo -e "  • Security checks completed"
    echo -e "  • Application built successfully"
    echo -e "  • Release package created"
    echo
    echo -e "${BLUE}Next Steps:${NC}"
    echo -e "  1. Review test results in the log file: $LOG_FILE"
    echo -e "  2. Verify release package: $PROJECT_DIR/release/"
    echo -e "  3. Test the built application"
    echo -e "  4. Deploy to staging/production environment"
    echo
    echo -e "${BLUE}Release Package:${NC}"
    echo -e "  Location: $PROJECT_DIR/release/"
    echo -e "  Package: $(ls -t "$PROJECT_DIR/release/"*.tar.gz | head -1)"
    echo
}

# Run main function
main "$@"