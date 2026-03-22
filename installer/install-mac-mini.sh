#!/bin/bash

################################################################################
# Atom Personal Edition - Interactive Mac mini Installer
################################################################################
# This script automates the installation of Atom on Mac mini with:
#   - Prerequisite checking (Docker, Git, etc.)
#   - Interactive configuration
#   - Automatic encryption key generation
#   - Service startup and verification
#   - Built-in troubleshooting tools
#
# Usage: bash install-mac-mini.sh
################################################################################

set -e  # Exit on error

# ==============================================================================
# COLORS AND FORMATTING
# ==============================================================================
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# ==============================================================================
# FUNCTIONS
# ==============================================================================

print_header() {
    echo -e "\n${CYAN}=============================================================================${NC}"
    echo -e "${CYAN}$1${NC}"
    echo -e "${CYAN}=============================================================================${NC}\n"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

print_step() {
    echo -e "\n${BOLD}→ $1${NC}"
}

# ==============================================================================
# SYSTEM CHECKS
# ==============================================================================

check_macos() {
    print_step "Checking macOS version..."

    if [[ "$OSTYPE" != "darwin"* ]]; then
        print_error "This script is designed for macOS only"
        print_info "Your OS: $OSTYPE"
        exit 1
    fi

    MACOS_VERSION=$(sw_vers -productVersion)
    print_success "macOS $MACOS_VERSION detected"

    # Check if macOS version is supported (Monterrey 12.x or later)
    MAJOR_VERSION=$(echo "$MACOS_VERSION" | cut -d. -f1)
    if [ "$MAJOR_VERSION" -lt 12 ]; then
        print_warning "macOS $MACOS_VERSION may not be fully supported"
        print_info "Recommended: macOS Monterey (12.x) or later"
        read -p "Continue anyway? (y/n): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
}

check_architecture() {
    print_step "Checking Mac architecture..."

    ARCH=$(uname -m)
    if [ "$ARCH" = "arm64" ]; then
        print_success "Apple Silicon (M1/M2/M3/M4) detected"
        RECOMMENDED_DOCKER="Docker Desktop for Mac (Apple Silicon)"
    else
        print_success "Intel-based Mac detected"
        RECOMMENDED_DOCKER="Docker Desktop for Mac (Intel Chip)"
    fi
}

check_docker() {
    print_step "Checking Docker installation..."

    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed"
        echo -e "\n${BOLD}Docker Installation Required${NC}"
        echo "1. Download Docker Desktop for Mac"
        echo "   URL: https://www.docker.com/products/docker-desktop/"
        echo "   Architecture: $RECOMMENDED_DOCKER"
        echo "\n2. Install and start Docker Desktop from Applications"
        echo "3. Wait for 'Docker is running' in menu bar"
        echo "4. Run this script again"
        echo ""
        read -p "Press Enter to open Docker download page, or Ctrl+C to exit..."
        open "https://www.docker.com/products/docker-desktop/"
        exit 1
    fi

    DOCKER_VERSION=$(docker --version | awk '{print $3}' | tr -d ',')
    print_success "Docker $DOCKER_VERSION installed"

    # Check if Docker is running
    if ! docker info &> /dev/null; then
        print_error "Docker is not running"
        echo -e "\n${BOLD}Please start Docker:${NC}"
        echo "1. Open Docker Desktop from Applications"
        echo "2. Wait for Docker icon in menu bar to show 'Docker is running'"
        echo "3. Run this script again"
        echo ""
        read -p "Press Enter after starting Docker, or Ctrl+C to exit..."
        if ! docker info &> /dev/null; then
            print_error "Docker still not running. Please check Docker Desktop."
            exit 1
        fi
    fi

    print_success "Docker is running"
}

check_git() {
    print_step "Checking Git installation..."

    if ! command -v git &> /dev/null; then
        print_error "Git is not installed"
        print_info "Installing Git via Xcode Command Line Tools..."

        xcode-select --install 2>&1 | grep installed || true

        print_warning "Please wait for Xcode Command Line Tools to install..."
        print_info "A dialog window should have appeared. Follow the prompts."
        read -p "Press Enter after installation completes..."
    fi

    GIT_VERSION=$(git --version | awk '{print $3}')
    print_success "Git $GIT_VERSION installed"
}

check_disk_space() {
    print_step "Checking disk space..."

    AVAILABLE_GB=$(df -BG . | awk 'NR==2 {print $4}' | tr -d 'G')

    if [ "$AVAILABLE_GB" -lt 10 ]; then
        print_warning "Low disk space: ${AVAILABLE_GB}GB available"
        print_info "Recommended: 10GB free space"
        read -p "Continue anyway? (y/n): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    else
        print_success "$AVAILABLE_GB"GB disk space available"
    fi
}

check_ports() {
    print_step "Checking port availability..."

    PORTS_IN_USE=()

    for PORT in 3000 8000 6379 3001; do
        if lsof -i :$PORT &> /dev/null; then
            PROCESS=$(lsof -i :$PORT | tail -n 1 | awk '{print $1}')
            PORTS_IN_USE+=("$PORT ($PROCESS)")
        fi
    done

    if [ ${#PORTS_IN_USE[@]} -gt 0 ]; then
        print_warning "The following ports are already in use:"
        for PORT_INFO in "${PORTS_IN_USE[@]}"; do
            echo "  - Port $PORT_INFO"
        done

        echo ""
        print_info "You can:"
        echo "  1) Stop the conflicting applications"
        echo "  2) Change ports in docker-compose-personal.yml after installation"
        echo "  3) Continue and let the script try to use different ports"
        echo ""

        read -p "Continue with installation? (y/n): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    else
        print_success "All required ports are available"
    fi
}

# ==============================================================================
# INSTALLATION
# ==============================================================================

clone_repository() {
    print_step "Cloning Atom repository..."

    # Get installation directory
    echo ""
    print_info "Where would you like to install Atom?"
    echo "  1) ~/Documents/atom (default)"
    echo "  2) ~/Desktop/atom"
    echo "  3) ~/Projects/atom"
    echo "  4) Custom location"
    echo ""
    read -p "Choose option [1-4]: " -n 1 -r
    echo

    case $REPLY in
        1)
            INSTALL_DIR="$HOME/Documents/atom"
            ;;
        2)
            INSTALL_DIR="$HOME/Desktop/atom"
            ;;
        3)
            INSTALL_DIR="$HOME/Projects/atom"
            ;;
        4)
            read -p "Enter full path: " INSTALL_DIR
            ;;
        *)
            print_warning "Invalid option. Using default: ~/Documents/atom"
            INSTALL_DIR="$HOME/Documents/atom"
            ;;
    esac

    # Create parent directory if needed
    PARENT_DIR=$(dirname "$INSTALL_DIR")
    if [ ! -d "$PARENT_DIR" ]; then
        mkdir -p "$PARENT_DIR"
        print_success "Created directory: $PARENT_DIR"
    fi

    # Check if directory already exists
    if [ -d "$INSTALL_DIR" ]; then
        print_warning "Directory already exists: $INSTALL_DIR"
        read -p "Remove existing directory and clone fresh? (y/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rm -rf "$INSTALL_DIR"
        else
            print_info "Using existing directory"
            cd "$INSTALL_DIR"
            return
        fi
    fi

    git clone https://github.com/rush86999/atom.git "$INSTALL_DIR"
    cd "$INSTALL_DIR"
    print_success "Repository cloned to: $INSTALL_DIR"
}

# ==============================================================================
# CONFIGURATION
# ==============================================================================

configure_environment() {
    print_step "Configuring Atom environment..."

    # Check if .env already exists
    if [ -f .env ]; then
        print_warning ".env file already exists"
        read -p "Overwrite existing configuration? (y/n): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_info "Keeping existing .env file"
            return
        fi
    fi

    # Copy template
    cp .env.personal .env
    print_success "Created .env from template"

    echo ""
    print_header "AI Provider Configuration"
    print_info "Atom requires at least one AI provider API key to function."
    echo ""

    # Configure AI providers
    configure_ai_providers

    # Generate encryption keys
    generate_encryption_keys

    # Optional configuration
    configure_optional_settings

    print_success "Environment configured successfully"
}

configure_ai_providers() {
    echo -e "${BOLD}Select your AI provider:${NC}"
    echo "  1) OpenAI (Recommended - GPT-4, GPT-3.5)"
    echo "  2) Anthropic (Best for complex tasks - Claude 3.5 Sonnet)"
    echo "  3) DeepSeek (Affordable alternative)"
    echo "  4) Enter multiple keys"
    echo ""

    read -p "Choose option [1-4]: " -n 1 -r
    echo

    case $REPLY in
        1)
            configure_openai
            ;;
        2)
            configure_anthropic
            ;;
        3)
            configure_deepseek
            ;;
        4)
            configure_openai
            configure_anthropic
            configure_deepseek
            ;;
        *)
            print_error "Invalid option"
            configure_ai_providers
            ;;
    esac
}

configure_openai() {
    echo ""
    print_info "OpenAI API Key"
    echo "Get your key at: https://platform.openai.com/api-keys"
    echo ""

    read -p "Enter your OpenAI API key (or press Enter to skip): " OPENAI_KEY

    if [ -n "$OPENAI_KEY" ]; then
        # Validate key format
        if [[ ! $OPENAI_KEY =~ ^sk- ]]; then
            print_warning "OpenAI API key usually starts with 'sk-'"
            read -p "Continue anyway? (y/n): " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                configure_openai
                return
            fi
        fi

        # Update .env file
        sed -i '' "s/OPENAI_API_KEY=.*/OPENAI_API_KEY=$OPENAI_KEY/" .env
        print_success "OpenAI API key configured"
    fi
}

configure_anthropic() {
    echo ""
    print_info "Anthropic API Key"
    echo "Get your key at: https://console.anthropic.com/"
    echo ""

    read -p "Enter your Anthropic API key (or press Enter to skip): " ANTHROPIC_KEY

    if [ -n "$ANTHROPIC_KEY" ]; then
        # Validate key format
        if [[ ! $ANTHROPIC_KEY =~ ^sk-ant- ]]; then
            print_warning "Anthropic API key usually starts with 'sk-ant-'"
            read -p "Continue anyway? (y/n): " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                configure_anthropic
                return
            fi
        fi

        sed -i '' "s/ANTHROPIC_API_KEY=.*/ANTHROPIC_API_KEY=$ANTHROPIC_KEY/" .env
        print_success "Anthropic API key configured"
    fi
}

configure_deepseek() {
    echo ""
    print_info "DeepSeek API Key"
    echo "Get your key at: https://platform.deepseek.com/"
    echo ""

    read -p "Enter your DeepSeek API key (or press Enter to skip): " DEEPSEEK_KEY

    if [ -n "$DEEPSEEK_KEY" ]; then
        sed -i '' "s/DEEPSEEK_API_KEY=.*/DEEPSEEK_API_KEY=$DEEPSEEK_KEY/" .env
        print_success "DeepSeek API key configured"
    fi
}

generate_encryption_keys() {
    echo ""
    print_header "Encryption Key Generation"
    print_info "Generating secure encryption keys..."

    # Generate BYOK_ENCRYPTION_KEY
    BYOK_KEY=$(openssl rand -base64 32)
    sed -i '' "s/BYOK_ENCRYPTION_KEY=.*/BYOK_ENCRYPTION_KEY=$BYOK_KEY/" .env
    print_success "BYOK_ENCRYPTION_KEY generated"

    # Generate JWT_SECRET_KEY
    JWT_KEY=$(openssl rand -base64 32)
    sed -i '' "s/JWT_SECRET_KEY=.*/JWT_SECRET_KEY=$JWT_KEY/" .env
    print_success "JWT_SECRET_KEY generated"

    print_info "Keys stored in .env file"
}

configure_optional_settings() {
    echo ""
    print_header "Optional Configuration"

    # Local-only mode
    echo ""
    read -p "Enable local-only mode? (Blocks Spotify, Notion, etc.) (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        sed -i '' 's/ATOM_LOCAL_ONLY=.*/ATOM_LOCAL_ONLY=true/' .env
        print_success "Local-only mode enabled"
    fi

    # Log level
    echo ""
    print_info "Log level options:"
    echo "  1) INFO (default - recommended)"
    echo "  2) DEBUG (verbose logging)"
    echo "  3) WARNING (less logging)"
    echo ""
    read -p "Choose log level [1-3]: " -n 1 -r
    echo

    case $REPLY in
        1)
            sed -i '' 's/LOG_LEVEL=.*/LOG_LEVEL=INFO/' .env
            ;;
        2)
            sed -i '' 's/LOG_LEVEL=.*/LOG_LEVEL=DEBUG/' .env
            ;;
        3)
            sed -i '' 's/LOG_LEVEL=.*/LOG_LEVEL=WARNING/' .env
            ;;
        *)
            print_info "Using default: INFO"
            ;;
    esac
}

# ==============================================================================
# SERVICE MANAGEMENT
# ==============================================================================

start_services() {
    print_step "Starting Atom services..."

    # Create data directory
    mkdir -p data
    print_success "Created data directory"

    # Start services
    print_info "Starting Docker containers..."
    docker-compose -f docker-compose-personal.yml up -d

    print_success "Docker containers started"
}

wait_for_services() {
    print_step "Waiting for services to be healthy..."

    MAX_WAIT=120
    WAIT_TIME=0
    INTERVAL=5

    while [ $WAIT_TIME -lt $MAX_WAIT ]; do
        sleep $INTERVAL
        WAIT_TIME=$((WAIT_TIME + INTERVAL))

        # Check if backend is healthy
        if curl -sf http://localhost:8000/health/live > /dev/null 2>&1; then
            print_success "All services are healthy"
            return 0
        fi

        echo -n "."
    done

    echo ""
    print_warning "Services are taking longer than expected to start"
    print_info "Check logs with: docker-compose -f docker-compose-personal.yml logs"
    return 1
}

verify_installation() {
    print_step "Verifying installation..."

    # Check service status
    echo ""
    print_info "Service Status:"
    docker-compose -f docker-compose-personal.yml ps

    # Check backend health
    echo ""
    if curl -sf http://localhost:8000/health/live > /dev/null 2>&1; then
        print_success "Backend health check passed"
    else
        print_error "Backend health check failed"
        return 1
    fi

    # Check frontend
    if curl -sf http://localhost:3000 > /dev/null 2>&1; then
        print_success "Frontend is accessible"
    else
        print_warning "Frontend may still be starting"
    fi

    return 0
}

# ==============================================================================
# TROUBLESHOOTING
# ==============================================================================

troubleshoot_menu() {
    echo ""
    print_header "TROUBLESHOOTING MENU"
    echo "  1) Check service status"
    echo "  2) View service logs"
    echo "  3) Restart services"
    echo "  4) Check port conflicts"
    echo "  5) Verify .env configuration"
    echo "  6) Test API connectivity"
    echo "  7) Reset installation (clean slate)"
    echo "  8) Docker diagnostics"
    echo "  9) Exit troubleshooting"
    echo ""

    read -p "Choose option [1-9]: " -n 1 -r
    echo ""

    case $REPLY in
        1)
            check_service_status
            troubleshoot_menu
            ;;
        2)
            view_logs
            troubleshoot_menu
            ;;
        3)
            restart_services
            troubleshoot_menu
            ;;
        4)
            check_port_conflicts
            troubleshoot_menu
            ;;
        5)
            verify_env_config
            troubleshoot_menu
            ;;
        6)
            test_api_connectivity
            troubleshoot_menu
            ;;
        7)
            reset_installation
            ;;
        8)
            docker_diagnostics
            troubleshoot_menu
            ;;
        9)
            print_info "Exiting troubleshooting"
            return 0
            ;;
        *)
            print_error "Invalid option"
            troubleshoot_menu
            ;;
    esac
}

check_service_status() {
    print_step "Checking service status..."

    echo ""
    docker-compose -f docker-compose-personal.yml ps

    echo ""
    print_info "Detailed status:"

    # Check each service
    SERVICES=("atom-personal-backend" "atom-personal-frontend" "atom-personal-valkey" "atom-personal-browser")

    for SERVICE in "${SERVICES[@]}"; do
        STATUS=$(docker inspect --format='{{.State.Status}}' "$SERVICE" 2>/dev/null || echo "not-found")
        HEALTH=$(docker inspect --format='{{.State.Health.Status}}' "$SERVICE" 2>/dev/null || echo "no-healthcheck")

        if [ "$STATUS" = "running" ]; then
            if [ "$HEALTH" = "healthy" ] || [ "$HEALTH" = "no-healthcheck" ]; then
                print_success "$SERVICE: $STATUS ($HEALTH)"
            else
                print_warning "$SERVICE: $STATUS ($HEALTH)"
            fi
        else
            print_error "$SERVICE: $STATUS"
        fi
    done
}

view_logs() {
    print_step "Viewing service logs..."

    echo ""
    print_info "Select service to view logs:"
    echo "  1) Backend (atom-backend)"
    echo "  2) Frontend (atom-frontend)"
    echo "  3) Valkey (valkey)"
    echo "  4) Browser (browser-node)"
    echo "  5) All services"
    echo ""

    read -p "Choose option [1-5]: " -n 1 -r
    echo ""

    case $REPLY in
        1)
            echo ""
            print_info "Showing last 50 lines of backend logs..."
            echo ""
            docker-compose -f docker-compose-personal.yml logs --tail=50 atom-backend
            ;;
        2)
            echo ""
            print_info "Showing last 50 lines of frontend logs..."
            echo ""
            docker-compose -f docker-compose-personal.yml logs --tail=50 atom-frontend
            ;;
        3)
            echo ""
            print_info "Showing last 50 lines of Valkey logs..."
            echo ""
            docker-compose -f docker-compose-personal.yml logs --tail=50 valkey
            ;;
        4)
            echo ""
            print_info "Showing last 50 lines of browser logs..."
            echo ""
            docker-compose -f docker-compose-personal.yml logs --tail=50 browser-node
            ;;
        5)
            echo ""
            print_info "Showing last 50 lines of all logs..."
            echo ""
            docker-compose -f docker-compose-personal.yml logs --tail=50
            ;;
        *)
            print_error "Invalid option"
            ;;
    esac

    echo ""
    read -p "Press Enter to continue..."
}

restart_services() {
    print_step "Restarting services..."

    echo ""
    print_info "Select restart option:"
    echo "  1) Restart all services"
    echo "  2) Restart backend only"
    echo "  3) Restart frontend only"
    echo "  4) Restart Valkey only"
    echo ""

    read -p "Choose option [1-4]: " -n 1 -r
    echo ""

    case $REPLY in
        1)
            docker-compose -f docker-compose-personal.yml restart
            print_success "All services restarted"
            wait_for_services
            ;;
        2)
            docker-compose -f docker-compose-personal.yml restart atom-backend
            print_success "Backend restarted"
            sleep 10
            ;;
        3)
            docker-compose -f docker-compose-personal.yml restart atom-frontend
            print_success "Frontend restarted"
            sleep 5
            ;;
        4)
            docker-compose -f docker-compose-personal.yml restart valkey
            print_success "Valkey restarted"
            sleep 5
            ;;
        *)
            print_error "Invalid option"
            return
            ;;
    esac
}

check_port_conflicts() {
    print_step "Checking for port conflicts..."

    echo ""
    PORTS=(3000 8000 6379 3001)
    CONFLICTS_FOUND=false

    for PORT in "${PORTS[@]}"; do
        if lsof -i :$PORT &> /dev/null; then
            PROCESS=$(lsof -i :$PORT | tail -n 1 | awk '{print $1}')
            PID=$(lsof -i :$PORT | tail -n 1 | awk '{print $2}')
            print_error "Port $PORT in use by $PROCESS (PID: $PID)"

            echo ""
            read -p "Kill process $PID? (y/n): " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                kill -9 $PID 2>/dev/null || sudo kill -9 $PID
                print_success "Process killed"
            fi

            CONFLICTS_FOUND=true
        else
            print_success "Port $PORT is available"
        fi
    done

    if [ "$CONFLICTS_FOUND" = false ]; then
        print_success "No port conflicts found"
    fi
}

verify_env_config() {
    print_step "Verifying .env configuration..."

    if [ ! -f .env ]; then
        print_error ".env file not found"
        return 1
    fi

    echo ""
    print_info "Checking .env file..."

    # Check for API keys
    if grep -q "OPENAI_API_KEY=sk-" .env || \
       grep -q "ANTHROPIC_API_KEY=sk-ant-" .env || \
       grep -q "DEEPSEEK_API_KEY=.*" .env; then
        print_success "At least one AI provider key is configured"
    else
        print_error "No AI provider API keys configured"
        print_info "Please run configuration again or edit .env file"
    fi

    # Check for encryption keys
    if grep -q "BYOK_ENCRYPTION_KEY=change-this" .env || \
       grep -q "JWT_SECRET_KEY=change-this" .env; then
        print_error "Default encryption keys detected (not secure)"
        print_info "Encryption keys should be changed"
    else
        print_success "Encryption keys are configured"
    fi

    # Check for syntax errors
    if grep -q "^[A-Z_]*=.*" .env; then
        print_success ".env file syntax looks correct"
    else
        print_warning "Possible syntax errors in .env file"
    fi

    echo ""
    print_info "Current .env configuration (sensitive values hidden):"
    echo ""
    grep -E "^[A-Z_]+(API|CLIENT|SECRET|KEY|TOKEN|URL|ENABLED|MODE|LEVEL)=" .env | \
        sed 's/=.*/=***HIDDEN***/' | \
        sed 's/^/  /'
}

test_api_connectivity() {
    print_step "Testing API connectivity..."

    echo ""
    print_info "Testing backend health endpoint..."

    if curl -sf http://localhost:8000/health/live; then
        echo ""
        print_success "Backend is responding"
    else
        echo ""
        print_error "Backend is not responding"
        print_info "Check if backend service is running"
        return 1
    fi

    echo ""
    print_info "Testing readiness endpoint..."

    if curl -sf http://localhost:8000/health/ready; then
        echo ""
        print_success "Backend is ready"
    else
        echo ""
        print_warning "Backend is not ready yet"
    fi

    echo ""
    print_info "Testing frontend..."

    if curl -sf http://localhost:3000 > /dev/null 2>&1; then
        print_success "Frontend is responding"
    else
        print_warning "Frontend is not responding yet"
    fi
}

reset_installation() {
    print_warning "This will stop all services and remove all data"
    echo ""
    read -p "Are you sure you want to reset? (yes/no): " -r
    echo

    if [ "$REPLY" != "yes" ]; then
        print_info "Reset cancelled"
        return
    fi

    print_step "Stopping services..."
    docker-compose -f docker-compose-personal.yml down

    print_step "Removing volumes..."
    docker-compose -f docker-compose-personal.yml down -v

    print_step "Removing data directory..."
    rm -rf data/

    print_step "Removing .env file..."
    rm -f .env

    print_success "Installation reset complete"
    print_info "Run this script again to reinstall Atom"
}

docker_diagnostics() {
    print_step "Running Docker diagnostics..."

    echo ""
    print_info "Docker Version:"
    docker --version
    echo ""

    print_info "Docker System Info:"
    docker info | grep -E "Server Version|Operating System|CPUs|Total Memory|Docker Root Dir"
    echo ""

    print_info "Docker Disk Usage:"
    docker system df
    echo ""

    print_info "Running Containers:"
    docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    echo ""

    print_info "Docker Health:"
    if docker info &> /dev/null; then
        print_success "Docker daemon is running"
    else
        print_error "Docker daemon is not running"
    fi

    echo ""
    print_info "Resource Limits:"
    print_info "Check Docker Desktop → Settings → Resources"
    print_info "Recommended: Memory 4GB+, CPUs 2+"

    echo ""
    read -p "Press Enter to continue..."
}

# ==============================================================================
# MAIN INSTALLATION FLOW
# ==============================================================================

main() {
    clear

    print_header "Atom Personal Edition - Mac mini Installer"
    echo "This script will guide you through installing Atom on your Mac mini."
    echo ""
    print_info "Installation steps:"
    echo "  1) System checks (macOS, Docker, Git, disk space)"
    echo "  2) Clone Atom repository"
    echo "  3) Configure environment (API keys, encryption)"
    echo "  4) Start services"
    echo "  5) Verify installation"
    echo ""

    read -p "Press Enter to start installation, or Ctrl+C to exit..."

    # System checks
    print_header "SYSTEM CHECKS"
    check_macos
    check_architecture
    check_docker
    check_git
    check_disk_space
    check_ports

    # Installation
    print_header "INSTALLATION"
    clone_repository

    # Configuration
    print_header "CONFIGURATION"
    configure_environment

    # Start services
    print_header "STARTING SERVICES"
    start_services
    wait_for_services

    # Verification
    print_header "VERIFICATION"
    if verify_installation; then
        print_success "Installation completed successfully!"
    else
        print_warning "Installation completed with warnings"
        echo ""
        read -p "Open troubleshooting menu? (y/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            troubleshoot_menu
        fi
    fi

    # Success message
    print_header "INSTALLATION COMPLETE"
    echo -e "${GREEN}Atom is now running on your Mac mini!${NC}"
    echo ""
    echo "Access Atom:"
    echo "  ${BOLD}Web Dashboard:${NC}  http://localhost:3000"
    echo "  ${BOLD}API Documentation:${NC} http://localhost:8000/docs"
    echo ""
    echo "Quick Commands:"
    echo "  ${BOLD}View logs:${NC}     docker-compose -f docker-compose-personal.yml logs -f"
    echo "  ${BOLD}Stop Atom:${NC}     docker-compose -f docker-compose-personal.yml down"
    echo "  ${BOLD}Restart Atom:${NC}  docker-compose -f docker-compose-personal.yml restart"
    echo ""
    echo "Installation Directory:"
    echo "  ${BOLD}$INSTALL_DIR${NC}"
    echo ""
    echo "Configuration File:"
    echo "  ${BOLD}$INSTALL_DIR/.env${NC}"
    echo ""
    echo "Data Location:"
    echo "  ${BOLD}$INSTALL_DIR/data/${NC}"
    echo ""

    # Offer to open dashboard
    read -p "Open Atom dashboard in browser? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        open "http://localhost:3000"
    fi

    # Troubleshooting offer
    echo ""
    read -p "Open troubleshooting menu? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        troubleshoot_menu
    fi

    print_success "Thank you for installing Atom!"
}

# Offer standalone troubleshooting mode
if [ "$1" = "--troubleshoot" ]; then
    print_header "ATOM TROUBLESHOOTING MODE"
    print_info "Current directory: $(pwd)"
    echo ""
    troubleshoot_menu
    exit 0
fi

# Run main installation
main
