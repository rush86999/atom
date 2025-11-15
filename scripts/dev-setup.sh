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
if [ ! -f "package.json" ]; then
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

# Install dependencies
print_status "Installing dependencies..."
npm install

if [ $? -eq 0 ]; then
    print_success "Dependencies installed successfully"
else
    print_error "Failed to install dependencies"
    exit 1
fi

# Build the project
print_status "Building the project..."
npm run build

if [ $? -eq 0 ]; then
    print_success "Project built successfully"
else
    print_error "Build failed"
    exit 1
fi

# Run tests
print_status "Running tests..."
npm test

if [ $? -eq 0 ]; then
    print_success "All tests passed"
else
    print_warning "Some tests failed - continuing setup"
fi

# Check for TypeScript compilation
print_status "Checking TypeScript compilation..."
npx tsc --noEmit

if [ $? -eq 0 ]; then
    print_success "TypeScript compilation successful"
else
    print_warning "TypeScript compilation issues found - please review"
fi

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

# Initialize the skill registry
print_status "Initializing skill registry..."
node -e "
const { registerAllSkills } = require('./dist/skills/index.js');
registerAllSkills().then(result => {
    console.log('Skill registration completed:');
    console.log('  - Registered:', result.registered);
    console.log('  - Failed:', result.failed);
    if (result.failed > 0) {
        console.log('  - Details:', result.details.join(', '));
    }
}).catch(console.error);
"

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
echo "1. Review the .env file and add any required API keys"
echo "2. Start the development server: npm run dev"
echo "3. Check out the documentation:"
echo "   - docs/QUICK_START_NEXT_STEPS.md"
echo "   - docs/NEXT_STEPS_IMPLEMENTATION.md"
echo ""
echo "Available commands:"
echo "  npm run dev          - Start development server"
echo "  npm run build        - Build the project"
echo "  npm test             - Run tests"
echo "  npm run lint         - Run linting"
echo "  npm run type-check   - TypeScript type checking"
echo ""
echo "Happy coding! 🚀"
