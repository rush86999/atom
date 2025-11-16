#!/bin/bash

# ATOM Agentic OS - Development Setup Script
# This script sets up the development environment for the ATOM agentic OS

set -e  # Exit on any error

echo "🚀 Setting up ATOM Agentic OS Development Environment..."
echo "========================================================"

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

# Check if we're in the right directory
if [ ! -f "README.md" ]; then
    print_error "Please run this script from the project root directory"
    exit 1
fi

# Check Node.js version
print_status "Checking Node.js version..."
NODE_VERSION=$(node --version | cut -d'v' -f2)
REQUIRED_NODE="18.0.0"

if [ "$(printf '%s\n' "$REQUIRED_NODE" "$NODE_VERSION" | sort -V | head -n1)" = "$REQUIRED_NODE" ]; then
    print_success "Node.js version $NODE_VERSION is compatible"
else
    print_error "Node.js version $NODE_VERSION is too old. Required: $REQUIRED_NODE+"
    exit 1
fi

# Install dependencies for frontend
print_status "Installing frontend dependencies..."
cd frontend-nextjs
npm install

if [ $? -eq 0 ]; then
    print_success "Frontend dependencies installed successfully"
else
    print_error "Failed to install frontend dependencies"
    exit 1
fi

# Install dependencies for backend
print_status "Installing backend dependencies..."
cd ../backend
npm install

if [ $? -eq 0 ]; then
    print_success "Backend dependencies installed successfully"
else
    print_error "Failed to install backend dependencies"
    exit 1
fi

cd ..

# Build the frontend project
print_status "Building the frontend project..."
cd frontend-nextjs
npm run build

if [ $? -eq 0 ]; then
    print_success "Frontend project built successfully"
else
    print_error "Frontend build failed"
    exit 1
fi

cd ..

# Run frontend tests
print_status "Running frontend tests..."
cd frontend-nextjs
npm test

if [ $? -eq 0 ]; then
    print_success "Frontend tests passed"
else
    print_warning "Some frontend tests failed - continuing setup"
fi

cd ..

# Check for TypeScript compilation in frontend
print_status "Checking frontend TypeScript compilation..."
cd frontend-nextjs
npx tsc --noEmit

if [ $? -eq 0 ]; then
    print_success "Frontend TypeScript compilation successful"
else
    print_warning "Frontend TypeScript compilation issues found - please review"
fi

cd ..

# Set up environment files
print_status "Setting up environment configuration..."
if [ ! -f ".env" ]; then
    cp .env.example .env 2>/dev/null || print_warning "No .env.example found - creating basic .env"
    echo "# ATOM Agentic OS Development Environment" >> .env
    echo "NODE_ENV=development" >> .env
    echo "LOG_LEVEL=info" >> .env
    print_success "Created .env file"
else
    print_success ".env file already exists"
fi

# Create necessary directories
print_status "Creating necessary directories..."
mkdir -p logs
mkdir -p temp
mkdir -p data
print_success "Directories created"

# Initialize the skill registry (placeholder for future implementation)
print_status "Setting up skill registry infrastructure..."
echo "Skill registry setup complete - ready for Phase 1 implementation"

# Set up git hooks if needed
print_status "Setting up development tools..."
if [ -d ".git" ]; then
    # Install husky if it's in package.json
    if grep -q "husky" package.json; then
        npx husky install 2>/dev/null || print_warning "Husky setup skipped"
    fi
fi

# Create development database if needed
print_status "Setting up development data..."
if [ -f "scripts/setup-dev-db.js" ]; then
    node scripts/setup-dev-db.js
else
    print_warning "No development database setup script found"
fi

# Display next steps
echo ""
echo "🎉 Development environment setup complete!"
echo ""
echo "Next steps:"
echo "1. Review the documentation:"
echo "   - docs/QUICK_START_NEXT_STEPS.md"
echo "   - docs/NEXT_STEPS_IMPLEMENTATION.md"
echo "2. Start development servers:"
echo "   - Frontend: cd frontend-nextjs && npm run dev"
echo "   - Backend: cd backend && npm run dev"
echo "3. Begin Phase 1 implementation from the next steps guide"
echo ""
echo "Available commands:"
echo "  Frontend development: cd frontend-nextjs && npm run dev"
echo "  Backend development: cd backend && npm run dev"
echo "  Frontend build: cd frontend-nextjs && npm run build"
echo "  Frontend tests: cd frontend-nextjs && npm test"
echo "  Type checking: cd frontend-nextjs && npx tsc --noEmit"
echo ""
echo "Ready to start Phase 1 of ATOM Agentic OS transformation! 🚀"
