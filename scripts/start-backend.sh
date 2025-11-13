#!/bin/bash

# ATOM Backend Startup Script
# This script starts the ATOM backend service with the correct Python environment

# Kill any existing backend processes
echo "Stopping any existing backend processes..."
pkill -f "python.*start_app" 2>/dev/null || true
pkill -f "python.*main_api_app" 2>/dev/null || true

# Kill processes on port 5059
echo "Clearing port 5059..."
lsof -ti:5059 | xargs kill -9 2>/dev/null || true

# Set environment variables
export DATABASE_URL="sqlite:///tmp/atom_dev.db"
export ATOM_OAUTH_ENCRYPTION_KEY="nCsfAph2Gln5Ag0uuEeqUVOvSEPtl7OLGT_jKsyzP84="
export FLASK_ENV="development"
export PYTHON_API_PORT="5059"

# Change to backend directory
cd backend/python-api-service

# Use the correct Python from the virtual environment
PYTHON_PATH="/home/developer/projects/atom/atom/ai-coding-orchestrator/venv/bin/python"

echo "Starting ATOM Backend Service..."
echo "Using Python: $PYTHON_PATH"
echo "Environment:"
echo "  DATABASE_URL: $DATABASE_URL"
echo "  PORT: $PYTHON_API_PORT"

# Start the backend service
$PYTHON_PATH start_app.py

# If the script reaches here, the backend has stopped
echo "Backend service has stopped."
