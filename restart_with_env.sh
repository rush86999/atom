#!/bin/bash

# 🚀 ATOM Personal Assistant - Environment Loader & Server Restart
# This script loads environment variables from .env and restarts the API server

set -e  # Exit on any error

echo "🚀 Loading environment and restarting ATOM API server"
echo "====================================================="

# Check if we're in the correct directory
if [ ! -f "README.md" ] && [ ! -d "backend" ]; then
    echo "❌ Please run this script from the atom project root directory"
    exit 1
fi

# Load environment variables from .env file
echo "📁 Loading environment variables from .env file..."
if [ -f ".env" ]; then
    # Export all variables from .env file (excluding comments and empty lines)
    set -a  # Automatically export all variables
    source .env
    set +a
    echo "✅ Environment variables loaded from .env"
else
    echo "❌ .env file not found"
    exit 1
fi

# Set required environment variables with defaults
export DATABASE_URL=${DATABASE_URL:-"postgresql://atom_user:local_password@localhost:5432/atom_production"}
export ATOM_OAUTH_ENCRYPTION_KEY=${ATOM_OAUTH_ENCRYPTION_KEY:-$(python3 -c "import base64; import os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())")}

echo "🔧 Environment configuration:"
echo "  DATABASE_URL: $(echo $DATABASE_URL | sed 's/:[^:]*@/:***@/')"
echo "  OPENAI_API_KEY: $(echo $OPENAI_API_KEY | cut -c1-10)..."
echo "  GOOGLE_CLIENT_ID: $(echo $GOOGLE_CLIENT_ID | cut -c1-10)..."
echo "  DROPBOX_APP_KEY: $(echo $DROPBOX_APP_KEY | cut -c1-10)..."

# Stop any running server
echo "🛑 Stopping any running API server..."
pkill -f "python.*main_api_app" || true
sleep 2

# Check if database is accessible
echo "🗄️  Checking database connectivity..."
if docker ps | grep -q "atom-postgres"; then
    echo "✅ PostgreSQL container is running"
else
    echo "⚠️  Starting PostgreSQL container..."
    docker-compose -f docker-compose.postgres.yml up -d
    sleep 5
fi

# Navigate to backend directory
cd backend/python-api-service

# Start the application with environment variables
echo "🚀 Starting ATOM API server..."
echo "  Server will be available at: http://localhost:5058"
echo "  Health endpoint: http://localhost:5058/healthz"
echo "  Dashboard endpoint: http://localhost:5058/api/dashboard"
echo ""
echo "📋 Loaded API keys:"
echo "  - OpenAI: $(echo $OPENAI_API_KEY | cut -c1-10)..."
echo "  - Google OAuth: $(echo $GOOGLE_CLIENT_ID | cut -c1-10)..."
echo "  - Dropbox OAuth: $(echo $DROPBOX_APP_KEY | cut -c1-10)..."
echo "  - Trello: $(echo $TRELLO_API_KEY | cut -c1-10)..."
echo "  - Asana: $(echo $ASANA_CLIENT_ID | cut -c1-10)..."
echo ""
echo "⚠️  Press Ctrl+C to stop the server"
echo ""

# Start the application
python3 main_api_app.py
