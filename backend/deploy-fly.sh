#!/bin/bash
# Fly.io Deployment Script for Python Backend

set -e

echo "========================================"
echo "Deploying Atom Python Backend to Fly.io"
echo "========================================"

cd "$(dirname "$0")"

# Check if fly CLI is installed
if ! command -v fly &> /dev/null; then
    echo "Error: fly CLI not installed"
    echo "Install with: curl -L https://fly.io/install.sh | sh"
    exit 1
fi

# Check if logged in
if ! fly auth whoami &> /dev/null; then
    echo "Please login to Fly.io first:"
    fly auth login
fi

# Deploy API
echo ""
echo "Deploying FastAPI backend..."
fly deploy --config fly.api.toml

# Deploy Worker
echo ""
echo "Deploying Celery worker..."
fly deploy --config fly.worker.toml

echo ""
echo "========================================"
echo "Deployment Complete!"
echo "========================================"

# Show app URLs
echo ""
echo "API URL: https://atom-python-api.fly.dev"
echo "Worker: Running as background process"
echo ""
echo "Set secrets with:"
echo "  fly secrets set DATABASE_URL=postgres://... -a atom-python-api"
echo "  fly secrets set REDIS_URL=rediss://... -a atom-python-api"
echo "  fly secrets set OPENAI_API_KEY=sk-... -a atom-python-api"
