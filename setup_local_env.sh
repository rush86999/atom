#!/bin/bash

# Atom Project Local Environment Setup Script
# This script sets up the local development environment with mock services

echo "============================================"
echo "Atom Project Local Environment Setup"
echo "============================================"
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

# Check if we're in the right directory
if [ ! -f "package.json" ]; then
    print_error "Please run this script from the atom directory"
    exit 1
fi

# Create .env file with mock defaults
echo ""
echo "1. Creating .env file with mock defaults..."
echo "-------------------------------------------"

cat > .env << 'EOF'
# Atom Local Development Environment Configuration
# All services use mock implementations - no real API calls

# General
NODE_ENV=development
PORT=3000

# OpenAI (Mock)
OPENAI_API_KEY=mock-openai-api-key

# Google APIs (Mock)
GOOGLE_CLIENT_ID=mock-google-client-id
GOOGLE_CLIENT_SECRET=mock-google-client-secret
GOOGLE_CLIENT_SECRETS_FILE=./mock-google-secrets.json

# AWS (Mock)
S3_ACCESS_KEY=mock-s3-access-key
S3_SECRET_KEY=mock-s3-secret-key
S3_ENDPOINT=http://localhost:9000
S3_BUCKET_NAME=mock-bucket

# Database (Mock)
LANCEDB_URI=/tmp/mock_lancedb
DATABASE_URL=postgresql://mock:mock@localhost:5432/mockdb

# Notion (Mock)
NOTION_API_TOKEN=mock-notion-token
NOTION_NOTES_DATABASE_ID=mock-notion-db-id

# QuickBooks (Mock)
QUICKBOOKS_CLIENT_ID=mock-qb-client-id
QUICKBOOKS_CLIENT_SECRET=mock-qb-client-secret
QUICKBOOKS_ACCESS_TOKEN=mock-qb-access-token
QUICKBOOKS_REFRESH_TOKEN=mock-qb-refresh-token
QUICKBOOKS_REALM_ID=mock-realm-id

# Twitter (Mock)
TWITTER_CONSUMER_KEY=mock-twitter-consumer-key
TWITTER_CONSUMER_SECRET=mock-twitter-consumer-secret
TWITTER_ACCESS_TOKEN=mock-twitter-access-token
TWITTER_ACCESS_TOKEN_SECRET=mock-twitter-access-token-secret

# LinkedIn (Mock)
LINKEDIN_CONSUMER_KEY=mock-linkedin-consumer-key
LINKEDIN_CONSUMER_SECRET=mock-linkedin-consumer-secret
LINKEDIN_USER_TOKEN=mock-linkedin-user-token
LINKEDIN_USER_SECRET=mock-linkedin-user-secret

# Kafka (Mock)
KAFKA_BROKERS=localhost:9092
KAFKA_CLIENT_ID=atom-mock-client

# OpenSearch (Mock)
OPENSEARCH_NODE=http://localhost:9200
OPENSEARCH_USERNAME=mock-user
OPENSEARCH_PASSWORD=mock-pass

# Encryption (Mock)
ATOM_OAUTH_ENCRYPTION_KEY=bW9ja19lbmNyeXB0aW9uX2tleV9mb3JfdGVzdGluZ19vbmx5XzMyYnl0ZXM=

# Flask
FLASK_SECRET_KEY=mock-flask-secret-key-for-testing

# Hasura (Mock)
HASURA_GRAPHQL_ENDPOINT=http://localhost:8080/v1/graphql
HASURA_ADMIN_SECRET=mock-hasura-admin-secret
EOF

if [ -f ".env" ]; then
    print_success ".env file created with mock defaults"
else
    print_error "Failed to create .env file"
fi

# Create mock Google secrets file
echo ""
echo "2. Creating mock Google secrets file..."
echo "---------------------------------------"

cat > mock-google-secrets.json << 'EOF'
{
  "installed": {
    "client_id": "mock-google-client-id",
    "project_id": "mock-project",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_secret": "mock-google-client-secret",
    "redirect_uris": ["http://localhost:3000/auth/callback"]
  }
}
EOF

if [ -f "mock-google-secrets.json" ]; then
    print_success "mock-google-secrets.json created"
else
    print_error "Failed to create mock-google-secrets.json"
fi

# Create necessary directories
echo ""
echo "3. Creating necessary directories..."
echo "------------------------------------"

directories=(
    "/tmp/mock_lancedb"
    "logs"
    "data/mock"
    "atomic-docker/project/functions/_cache"
)

for dir in "${directories[@]}"; do
    mkdir -p "$dir"
    if [ -d "$dir" ]; then
        print_success "Created directory: $dir"
    else
        print_error "Failed to create directory: $dir"
    fi
done

# Install Node.js dependencies
echo ""
echo "4. Installing Node.js dependencies..."
echo "-------------------------------------"

if command -v npm &> /dev/null; then
    npm install
    if [ $? -eq 0 ]; then
        print_success "Node.js dependencies installed"
    else
        print_warning "Some Node.js dependencies failed to install"
    fi
else
    print_error "npm not found. Please install Node.js first"
fi

# Set up Python virtual environment
echo ""
echo "5. Setting up Python virtual environment..."
echo "-------------------------------------------"

if command -v python3 &> /dev/null; then
    # Create virtual environment for atomic-docker
    if [ ! -d "atomic-docker/venv" ]; then
        python3 -m venv atomic-docker/venv
        print_success "Created Python virtual environment"
    else
        print_info "Python virtual environment already exists"
    fi

    # Create requirements.txt for mock dependencies
    cat > atomic-docker/requirements-mock.txt << 'EOF'
# Mock requirements for local testing
# These are lightweight alternatives that don't require real API keys

# Web framework
flask>=2.0.0
aiohttp>=3.8.0

# Database
psycopg2-binary>=2.9.0

# Utilities
python-dotenv>=0.19.0
pydantic>=1.9.0
pandas>=1.3.0

# Mock testing utilities
pytest>=6.2.0
pytest-asyncio>=0.18.0
pytest-mock>=3.6.0

# Basic cryptography (for mock encryption)
cryptography>=3.4.0

# Date/time handling
python-dateutil>=2.8.0

# HTTP client
httpx>=0.23.0
requests>=2.26.0

# Logging
python-json-logger>=2.0.0
EOF

    # Activate virtual environment and install dependencies
    print_info "To install Python dependencies, run:"
    print_info "  source atomic-docker/venv/bin/activate"
    print_info "  pip install -r atomic-docker/requirements-mock.txt"
else
    print_error "Python3 not found. Please install Python 3.8 or later"
fi

# Create run scripts
echo ""
echo "6. Creating run scripts..."
echo "--------------------------"

# Create mock server runner
cat > run_mock_server.sh << 'EOF'
#!/bin/bash
# Run the mock server for testing

echo "Starting Atom Mock Server..."

# Load environment variables
export $(cat .env | grep -v '^#' | xargs)

# Start TypeScript compilation in watch mode
echo "Starting TypeScript compiler in watch mode..."
npx tsc --watch --skipLibCheck &
TSC_PID=$!

# Start mock Python API service
echo "Starting mock Python API service..."
cd atomic-docker/project/functions/python_api_service
source ../../venv/bin/activate
python -m flask run --port 5058 &
FLASK_PID=$!

cd ../../../../

echo ""
echo "Mock services started:"
echo "- TypeScript compiler (PID: $TSC_PID)"
echo "- Python API service at http://localhost:5058 (PID: $FLASK_PID)"
echo ""
echo "Press Ctrl+C to stop all services"

# Wait for interrupt
trap "kill $TSC_PID $FLASK_PID; exit" INT
wait
EOF

chmod +x run_mock_server.sh
print_success "Created run_mock_server.sh"

# Create test runner
cat > run_tests.sh << 'EOF'
#!/bin/bash
# Run all tests with mock implementations

echo "Running Atom Tests with Mock Implementations..."

# Load environment variables
export $(cat .env | grep -v '^#' | xargs)

# Run TypeScript tests
echo ""
echo "Running TypeScript tests..."
npm test

# Run Python tests
echo ""
echo "Running Python tests..."
cd atomic-docker
source venv/bin/activate
python -m pytest project/functions/python_api_service/test_*.py -v
cd ..

echo ""
echo "All tests completed!"
EOF

chmod +x run_tests.sh
print_success "Created run_tests.sh"

# Summary
echo ""
echo "============================================"
echo "Setup Complete!"
echo "============================================"
echo ""
print_success "Environment configuration created (.env)"
print_success "Mock Google secrets created"
print_success "Required directories created"
print_success "Run scripts created"
echo ""
echo "Next steps:"
echo ""
echo "1. Install Python dependencies:"
print_info "   source atomic-docker/venv/bin/activate"
print_info "   pip install -r atomic-docker/requirements-mock.txt"
echo ""
echo "2. Run the mock server:"
print_info "   ./run_mock_server.sh"
echo ""
echo "3. Run tests:"
print_info "   ./run_tests.sh"
echo ""
echo "All services are configured to use mock implementations."
echo "No real API calls will be made during development/testing."
echo "============================================"
