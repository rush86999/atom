#!/bin/bash

# ATOM Enhanced Development Build Script
# Fast development builds with hot reloading and debugging support
# Usage: ./dev-build.sh [platform] [options]

set -euo pipefail

# Default values
PLATFORM=${1:-"desktop"}
ENVIRONMENT=${2:-"development"}
WATCH_MODE=${3:-"false"}
DEBUG_MODE=${4:-"false"}
CLEAN_BUILD=${5:-"false"}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Print banner
print_banner() {
    echo -e "${BLUE}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                   ATOM Development Build                     ║"
    echo "║              Enhanced Development Environment                ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo "Platform: $PLATFORM"
    echo "Environment: $ENVIRONMENT"
    echo "Watch Mode: $WATCH_MODE"
    echo "Debug Mode: $DEBUG_MODE"
    echo "Clean Build: $CLEAN_BUILD"
    echo ""
}

# Check dependencies
check_dependencies() {
    log_info "Checking dependencies..."

    local missing_deps=()

    # Check Node.js
    if ! command -v node &> /dev/null; then
        missing_deps+=("Node.js")
    fi

    # Check npm
    if ! command -v npm &> /dev/null; then
        missing_deps+=("npm")
    fi

    # Check Rust (for desktop builds)
    if [[ "$PLATFORM" == "desktop" ]] && ! command -v cargo &> /dev/null; then
        missing_deps+=("Rust")
    fi

    if [[ ${#missing_deps[@]} -gt 0 ]]; then
        log_error "Missing dependencies: ${missing_deps[*]}"
        log_info "Please install the missing dependencies and try again."
        exit 1
    fi

    log_success "All dependencies are available"
}

# Clean build artifacts
clean_build() {
    log_info "Cleaning build artifacts..."

    # Clean frontend build
    if [[ -d "frontend-nextjs/.next" ]]; then
        rm -rf frontend-nextjs/.next
        log_success "Cleaned frontend build cache"
    fi

    # Clean Tauri target (if exists)
    if [[ -d "frontend-nextjs/src-tauri/target" ]]; then
        rm -rf frontend-nextjs/src-tauri/target
        log_success "Cleaned Rust build cache"
    fi

    # Clean distribution directory
    if [[ -d "dist" ]]; then
        rm -rf dist
        log_success "Cleaned distribution directory"
    fi

    # Clean node_modules (optional - only if explicitly requested)
    if [[ "$CLEAN_BUILD" == "true" ]]; then
        log_warning "Cleaning node_modules - this may take a while..."
        if [[ -d "frontend-nextjs/node_modules" ]]; then
            rm -rf frontend-nextjs/node_modules
            log_success "Cleaned frontend node_modules"
        fi
    fi
}

# Install dependencies
install_dependencies() {
    log_info "Installing dependencies..."

    # Frontend dependencies
    cd frontend-nextjs

    if [[ ! -d "node_modules" ]] || [[ "$CLEAN_BUILD" == "true" ]]; then
        log_info "Installing frontend dependencies..."
        npm ci --silent
        log_success "Frontend dependencies installed"
    else
        log_success "Frontend dependencies already installed"
    fi

    cd ..

    # Desktop dependencies (if building for desktop)
    if [[ "$PLATFORM" == "desktop" ]]; then
        cd frontend-nextjs/src-tauri

        if [[ ! -d "node_modules" ]] || [[ "$CLEAN_BUILD" == "true" ]]; then
            log_info "Installing desktop dependencies..."
            npm ci --silent
            log_success "Desktop dependencies installed"
        else
            log_success "Desktop dependencies already installed"
        fi

        cd ..
    fi
}

# Build frontend
build_frontend() {
    log_info "Building frontend application..."

    cd frontend-nextjs

    # Set environment
    export NODE_ENV="$ENVIRONMENT"

    if [[ "$DEBUG_MODE" == "true" ]]; then
        export DEBUG="atom:*"
        log_info "Debug mode enabled for frontend"
    fi

    if [[ "$WATCH_MODE" == "true" ]]; then
        log_info "Starting frontend in watch mode..."
        npm run dev &
        FRONTEND_PID=$!
        log_success "Frontend development server started (PID: $FRONTEND_PID)"
    else
        log_info "Building frontend for production..."
        npm run build
        log_success "Frontend built successfully"
    fi

    cd ..
}

# Build desktop application
build_desktop() {
    log_info "Building desktop application..."

    cd frontend-nextjs/src-tauri

    # Set environment variables
    export TAURI_ENV="$ENVIRONMENT"

    if [[ "$DEBUG_MODE" == "true" ]]; then
        export RUST_LOG="debug"
        log_info "Rust debug logging enabled"
    fi

    if [[ "$WATCH_MODE" == "true" ]]; then
        log_info "Starting desktop app in development mode..."
        npm run tauri dev &
        DESKTOP_PID=$!
        log_success "Desktop development server started (PID: $DESKTOP_PID)"
    else
        log_info "Building desktop app for production..."

        # Determine target based on platform
        local target=""
        case "$(uname -s)" in
            Darwin*)
                target="universal-apple-darwin"
                ;;
            Linux*)
                target="x86_64-unknown-linux-gnu"
                ;;
            MINGW*|CYGWIN*|MSYS*)
                target="x86_64-pc-windows-msvc"
                ;;
            *)
                target=""
                ;;
        esac

        if [[ -n "$target" ]]; then
            npm run tauri build -- --target "$target"
        else
            npm run tauri build
        fi

        log_success "Desktop app built successfully"
    fi

    cd ..
}

# Build web application
build_web() {
    log_info "Building web application..."

    cd frontend-nextjs

    if [[ "$WATCH_MODE" == "true" ]]; then
        log_info "Web watch mode - using frontend development server"
        # Frontend dev server is already running from build_frontend
    else
        log_info "Building web application for production..."
        npm run build
        npm run export

        # Create web distribution
        mkdir -p ../dist/web
        cp -r out/* ../dist/web/
        log_success "Web application exported to dist/web"
    fi

    cd ..
}

# Run health checks
run_health_checks() {
    log_info "Running health checks..."

    # Check if frontend is running (if in watch mode)
    if [[ "$WATCH_MODE" == "true" ]] && [[ "$PLATFORM" == "desktop" ]]; then
        sleep 5
        if curl -s http://localhost:3000 > /dev/null; then
            log_success "Frontend development server is healthy"
        else
            log_warning "Frontend development server may not be ready yet"
        fi
    fi

    # Check build artifacts
    if [[ "$WATCH_MODE" == "false" ]]; then
        case "$PLATFORM" in
            "desktop")
                if [[ -d "frontend-nextjs/src-tauri/target/release" ]]; then
                    log_success "Desktop build artifacts created successfully"
                fi
                ;;
            "web")
                if [[ -d "dist/web" ]]; then
                    log_success "Web build artifacts created successfully"
                fi
                ;;
            "all")
                if [[ -d "frontend-nextjs/src-tauri/target/release" ]] && [[ -d "dist/web" ]]; then
                    log_success "All build artifacts created successfully"
                fi
                ;;
        esac
    fi
}

# Print completion message
print_completion() {
    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗"
    echo -e "║                      BUILD COMPLETE!                         ║"
    echo -e "╚══════════════════════════════════════════════════════════════╗${NC}"
    echo ""

    case "$PLATFORM" in
        "desktop")
            if [[ "$WATCH_MODE" == "true" ]]; then
                log_info "Desktop app running in development mode"
                log_info "Frontend: http://localhost:3000"
                log_info "Press Ctrl+C to stop"
            else
                log_info "Desktop app built successfully"
                log_info "Output: frontend-nextjs/src-tauri/target/release/"
            fi
            ;;
        "web")
            if [[ "$WATCH_MODE" == "true" ]]; then
                log_info "Web app running in development mode"
                log_info "URL: http://localhost:3000"
                log_info "Press Ctrl+C to stop"
            else
                log_info "Web app built successfully"
                log_info "Output: dist/web/"
            fi
            ;;
        "all")
            log_info "All platforms built successfully"
            log_info "Desktop output: frontend-nextjs/src-tauri/target/release/"
            log_info "Web output: dist/web/"
            ;;
    esac

    echo ""
    log_info "Next steps:"
    case "$PLATFORM" in
        "desktop")
            if [[ "$WATCH_MODE" == "false" ]]; then
                echo "  • Run: ./frontend-nextjs/src-tauri/target/release/atom (Linux/Mac)"
                echo "  • Run: .\\src-tauri\\target\\release\\atom.exe (Windows)"
            fi
            ;;
        "web")
            if [[ "$WATCH_MODE" == "false" ]]; then
                echo "  • Serve: npx serve dist/web"
                echo "  • Deploy to your preferred hosting platform"
            fi
            ;;
    esac
}

# Main build function
main() {
    print_banner
    check_dependencies

    if [[ "$CLEAN_BUILD" == "true" ]]; then
        clean_build
    fi

    install_dependencies

    # Build based on platform
    case "$PLATFORM" in
        "desktop")
            build_frontend
            build_desktop
            ;;
        "web")
            build_frontend
            build_web
            ;;
        "all")
            build_frontend
            build_desktop
            build_web
            ;;
        *)
            log_error "Unknown platform: $PLATFORM"
            log_info "Available platforms: desktop, web, all"
            exit 1
            ;;
    esac

    run_health_checks
    print_completion

    # Wait for processes if in watch mode
    if [[ "$WATCH_MODE" == "true" ]]; then
        log_info "Development servers are running..."
        log_info "Press Ctrl+C to stop all processes"
        wait
    fi
}

# Handle script interruption
cleanup() {
    log_info "Cleaning up..."
    if [[ -n "$FRONTEND_PID" ]]; then
        kill $FRONTEND_PID 2>/dev/null || true
    fi
    if [[ -n "$DESKTOP_PID" ]]; then
        kill $DESKTOP_PID 2>/dev/null || true
    fi
    log_success "Cleanup complete"
    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM

# Run main function
main "$@"
