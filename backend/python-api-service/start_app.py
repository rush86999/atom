#!/usr/bin/env python3
"""
ATOM Application Startup Script

This script starts the ATOM Python API service with proper environment configuration.
It handles environment variable setup, dependency validation, and graceful startup.
"""

import os
import sys
import logging
import signal
import subprocess
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/tmp/atom_app.log')
    ]
)
logger = logging.getLogger(__name__)

def setup_environment():
    """Setup environment variables for development"""
    env_vars = {
        # Database configuration
        'DATABASE_URL': 'sqlite:///tmp/atom_dev.db',

        # Encryption key (32-byte base64 encoded)
        'ATOM_OAUTH_ENCRYPTION_KEY': 'nCsfAph2Gln5Ag0uuEeqUVOvSEPtl7OLGT_jKsyzP84=',

        # Flask configuration
        'FLASK_SECRET_KEY': 'dev-secret-key-change-in-production',
        'FLASK_ENV': 'development',
        'PYTHON_API_PORT': '5058',

        # Development flags
        'DEBUG': 'true',
        'ENABLE_MOCK_SERVICES': 'true',
        'USE_SQLITE_FALLBACK': 'true',

        # Logging
        'LOG_LEVEL': 'INFO',

        # Feature flags
        'ENABLE_GOALS': 'true',
        'ENABLE_CALENDAR': 'true',
        'ENABLE_TASKS': 'true',
        'ENABLE_MESSAGES': 'true'
    }

    for key, value in env_vars.items():
        os.environ[key] = value
        logger.info(f"Set {key}={value}")

def check_dependencies():
    """Check if required dependencies are installed"""
    try:
        import flask
        import psycopg2
        import requests
        import cryptography
        import aiohttp
        import pandas
        import lancedb

        logger.info("✅ Core dependencies are installed")
        return True

    except ImportError as e:
        logger.error(f"❌ Missing dependency: {e}")
        logger.error("Run: pip install flask psycopg2-binary requests cryptography aiohttp pandas lancedb")
        return False

def start_application():
    """Start the Flask application"""
    try:
        from main_api_app import create_app

        logger.info("🚀 Starting ATOM Python API Service...")

        # Create and configure the application
        app = create_app()

        # Get port from environment
        port = int(os.environ.get("PYTHON_API_PORT", 5058))
        host = os.environ.get("HOST", "0.0.0.0")

        logger.info(f"🌐 Server will run on {host}:{port}")
        logger.info("📋 Available endpoints:")
        logger.info("   • Health check: /healthz")
        logger.info("   • Goals API: /api/goals")
        logger.info("   • Dashboard: /api/dashboard")
        logger.info("   • Integrations: /api/integrations/status")

        # Start the application
        app.run(host=host, port=port, debug=True)

    except Exception as e:
        logger.error(f"❌ Failed to start application: {e}")
        logger.error("Traceback:", exc_info=True)
        return False

    return True

def signal_handler(sig, frame):
    """Handle shutdown signals gracefully"""
    logger.info("🛑 Shutdown signal received. Stopping application...")
    sys.exit(0)

def main():
    """Main application entry point"""
    # Setup signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    print("=" * 60)
    print("🚀 ATOM Personal Assistant - Backend Service")
    print("=" * 60)

    # Setup environment
    logger.info("Setting up environment...")
    setup_environment()

    # Check dependencies
    logger.info("Checking dependencies...")
    if not check_dependencies():
        logger.error("Dependency check failed. Exiting.")
        sys.exit(1)

    # Start the application
    success = start_application()

    if not success:
        logger.error("Application failed to start")
        sys.exit(1)

if __name__ == "__main__":
    main()
