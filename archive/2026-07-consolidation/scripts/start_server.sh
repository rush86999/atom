#!/bin/bash

# 🚀 ATOM Personal Assistant - Production Server Startup Script
# This script starts the ATOM API server with proper environment configuration

set -e  # Exit on any error

echo "🚀 Starting ATOM Production Server"
echo "=================================="

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

print_status "Environment configuration:"
echo "  DATABASE_URL: $(echo $DATABASE_URL | sed 's/:[^:]*@/:***@/')"
echo "  FLASK_ENV: $FLASK_ENV"
echo "  ATOM_OAUTH_ENCRYPTION_KEY: [set]"

# Check if database is accessible
print_status "Checking database connectivity..."
if docker ps | grep -q "atom-postgres"; then
    print_success "PostgreSQL container is running"
else
    print_warning "PostgreSQL container not found, starting it..."
    docker-compose -f docker-compose.postgres.yml up -d
    sleep 5
fi

# Navigate to backend directory
cd backend/python-api-service

print_status "Starting ATOM API server..."
echo "  Server will be available at: http://localhost:5058"
echo "  Health endpoint: http://localhost:5058/healthz"
echo "  Dashboard endpoint: http://localhost:5058/api/dashboard"
echo ""
print_warning "Press Ctrl+C to stop the server"
echo ""

# Start the application with environment variables
python3 main_api_app.py
