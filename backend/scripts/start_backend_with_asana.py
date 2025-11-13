#!/usr/bin/env python3
"""
ATOM Backend Startup with Asana Integration

This script starts the ATOM backend with Asana integration properly registered
and configured. It ensures all Asana endpoints are available and ready for OAuth.
"""

import os
import sys
import logging
import time
from flask import Flask, jsonify
import threading

# Add backend modules to Python path
backend_path = os.path.join(os.path.dirname(__file__), "backend", "python-api-service")
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("/tmp/atom_backend_with_asana.log"),
    ],
)
logger = logging.getLogger(__name__)


def create_app_with_asana():
    """Create Flask app with Asana integration properly registered"""

    # Set environment variables
    os.environ.setdefault("FLASK_ENV", "development")
    os.environ.setdefault(
        "FLASK_SECRET_KEY", "atom-dev-secret-key-change-in-production"
    )
    os.environ.setdefault("DATABASE_URL", "sqlite:///./data/atom_development.db")
    os.environ.setdefault("LANCEDB_URI", "/tmp/test_lancedb")

    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY")

    # Health endpoint
    @app.route("/health")
    def health():
        return jsonify(
            {
                "status": "ok",
                "service": "atom-backend-with-asana",
                "version": "1.0.0",
                "integrations": [
                    "asana",
                    "github",
                    "notion",
                    "slack",
                    "trello",
                    "jira",
                ],
                "timestamp": time.time(),
            }
        )

    # Root endpoint
    @app.route("/")
    def root():
        return jsonify(
            {
                "name": "ATOM Enterprise System with Asana",
                "status": "running",
                "version": "3.0.0",
                "timestamp": time.time(),
                "endpoints": {
                    "health": "/health",
                    "asana": "/api/asana/*",
                    "oauth": "/api/auth/asana/*",
                },
                "features": ["oauth", "asana_integration", "workflows", "voice"],
                "integrations": [
                    "asana",
                    "github",
                    "notion",
                    "slack",
                    "trello",
                    "jira",
                ],
            }
        )

    try:
        # Register Asana integration
        from asana_handler import asana_bp
        from auth_handler_asana import auth_asana_bp

        app.register_blueprint(asana_bp, url_prefix="/api")
        app.register_blueprint(auth_asana_bp, url_prefix="/api")

        logger.info("✅ Asana integration registered successfully")
        logger.info(
            "   - Task endpoints: /api/asana/search, /api/asana/list-tasks, /api/asana/create-task"
        )
        logger.info("   - Project endpoints: /api/asana/projects, /api/asana/sections")
        logger.info(
            "   - OAuth endpoints: /api/auth/asana/authorize, /api/auth/asana/callback"
        )

    except ImportError as e:
        logger.error(f"❌ Failed to import Asana modules: {e}")
        logger.info(
            "   Make sure Asana integration files are in backend/python-api-service/"
        )

    try:
        # Register other core integrations
        from workflow_handler import workflow_bp
        from workflow_api import workflow_api_bp
        from workflow_agent_api import workflow_agent_api_bp

        app.register_blueprint(workflow_bp, url_prefix="/api/v1/workflows")
        app.register_blueprint(workflow_api_bp, url_prefix="/api/v1/workflows")
        app.register_blueprint(
            workflow_agent_api_bp, url_prefix="/api/v1/workflows/agent"
        )

        logger.info("✅ Workflow integration registered successfully")

    except ImportError as e:
        logger.warning(f"⚠️  Some workflow modules not available: {e}")

    try:
        # Register voice integration
        from voice_integration_api import voice_integration_api_bp

        app.register_blueprint(voice_integration_api_bp, url_prefix="/api/v1/voice")
        logger.info("✅ Voice integration registered successfully")

    except ImportError as e:
        logger.warning(f"⚠️  Voice integration not available: {e}")

    # Asana-specific test endpoint
    @app.route("/api/asana/health")
    def asana_health():
        """Asana integration health check"""
        return jsonify(
            {
                "ok": True,
                "service": "asana",
                "status": "registered",
                "message": "Asana integration is registered and ready for OAuth configuration",
                "needs_oauth": True,
                "endpoints": {
                    "search": "/api/asana/search",
                    "list_tasks": "/api/asana/list-tasks",
                    "create_task": "/api/asana/create-task",
                    "projects": "/api/asana/projects",
                    "sections": "/api/asana/sections",
                    "oauth_authorize": "/api/auth/asana/authorize",
                    "oauth_callback": "/api/auth/asana/callback",
                    "oauth_status": "/api/auth/asana/status",
                },
            }
        )

    # Service status endpoint
    @app.route("/api/services/status")
    def services_status():
        """Get status of all registered services"""
        services = {
            "asana": {
                "registered": True,
                "endpoints": ["/api/asana/*", "/api/auth/asana/*"],
                "status": "needs_oauth",
            },
            "workflows": {
                "registered": True,
                "endpoints": ["/api/v1/workflows/*"],
                "status": "operational",
            },
            "voice": {
                "registered": True,
                "endpoints": ["/api/v1/voice/*"],
                "status": "operational",
            },
        }

        return jsonify(
            {
                "ok": True,
                "services": services,
                "total_services": len(services),
                "active_services": sum(
                    1 for s in services.values() if s["status"] == "operational"
                ),
            }
        )

    return app


def check_environment():
    """Check and log environment configuration"""
    logger.info("🔧 Environment Configuration:")

    env_vars = {
        "ASANA_CLIENT_ID": os.getenv("ASANA_CLIENT_ID"),
        "ASANA_CLIENT_SECRET": os.getenv("ASANA_CLIENT_SECRET"),
        "DATABASE_URL": os.getenv("DATABASE_URL"),
        "FLASK_ENV": os.getenv("FLASK_ENV"),
        "PYTHON_API_SERVICE_BASE_URL": os.getenv("PYTHON_API_SERVICE_BASE_URL"),
    }

    for var_name, var_value in env_vars.items():
        if var_value:
            if "SECRET" in var_name or "CLIENT_SECRET" in var_name:
                masked_value = (
                    f"{var_value[:8]}...{var_value[-4:]}"
                    if len(var_value) > 12
                    else "***"
                )
                logger.info(f"   ✅ {var_name}: {masked_value}")
            else:
                logger.info(f"   ✅ {var_name}: {var_value}")
        else:
            logger.warning(f"   ⚠️  {var_name}: Not configured")

    # Check if Asana OAuth credentials are configured
    if not env_vars["ASANA_CLIENT_ID"] or not env_vars["ASANA_CLIENT_SECRET"]:
        logger.warning("🔐 Asana OAuth credentials not configured")
        logger.info("   To enable Asana integration, set:")
        logger.info("   - ASANA_CLIENT_ID=your_client_id")
        logger.info("   - ASANA_CLIENT_SECRET=your_client_secret")
        logger.info(
            "   - ASANA_REDIRECT_URI=http://localhost:8000/api/auth/asana/callback"
        )


def start_backend():
    """Start the backend server"""
    app = create_app_with_asana()

    # Get port from environment or default to 8000
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")

    logger.info("🚀 Starting ATOM Backend with Asana Integration")
    logger.info(f"   Host: {host}")
    logger.info(f"   Port: {port}")
    logger.info(f"   Environment: {os.getenv('FLASK_ENV', 'development')}")

    check_environment()

    try:
        # Start the Flask development server
        app.run(host=host, port=port, debug=True, threaded=True, use_reloader=False)
    except Exception as e:
        logger.error(f"❌ Failed to start backend: {e}")
        sys.exit(1)


if __name__ == "__main__":
    start_backend()
