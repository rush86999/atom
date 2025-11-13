#!/usr/bin/env python3
"""
Simple ATOM Backend Starter with Asana Integration

This script starts a minimal Flask backend with Asana integration
properly registered and ready for OAuth configuration.
"""

import os
import sys
import logging
from flask import Flask, jsonify
import threading
import time

# Add backend modules to Python path
backend_path = os.path.join(os.path.dirname(__file__), "backend", "python-api-service")
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def create_simple_backend():
    """Create a simple Flask app with Asana integration"""

    # Set basic environment
    os.environ.setdefault("FLASK_ENV", "development")
    os.environ.setdefault("FLASK_SECRET_KEY", "dev-secret-key-change-in-production")
    os.environ.setdefault("DATABASE_URL", "sqlite:///./data/atom_development.db")
    os.environ.setdefault(
        "ATOM_OAUTH_ENCRYPTION_KEY", "nCsfAph2Gln5Ag0uuEeqUVOvSEPtl7OLGT_jKsyzP84="
    )

    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY")

    # Basic health endpoint
    @app.route("/health")
    def health():
        return jsonify(
            {
                "status": "ok",
                "service": "atom-simple-backend",
                "version": "1.0.0",
                "timestamp": time.time(),
            }
        )

    # Root endpoint
    @app.route("/")
    def root():
        return jsonify(
            {
                "name": "ATOM Simple Backend",
                "status": "running",
                "version": "1.0.0",
                "integrations": ["asana"],
                "endpoints": {"health": "/health", "asana_health": "/api/asana/health"},
            }
        )

    # Try to register Asana integration
    try:
        from asana_handler import asana_bp
        from auth_handler_asana import auth_asana_bp

        app.register_blueprint(asana_bp, url_prefix="/api")
        app.register_blueprint(auth_asana_bp, url_prefix="/api")

        logger.info("✅ Asana integration registered successfully")
        logger.info("   - Task endpoints: /api/asana/search, /api/asana/list-tasks")
        logger.info(
            "   - OAuth endpoints: /api/auth/asana/authorize, /api/auth/asana/callback"
        )

    except ImportError as e:
        logger.error(f"❌ Failed to register Asana integration: {e}")
        logger.info("   Make sure Asana files are in backend/python-api-service/")

    except Exception as e:
        logger.error(f"❌ Error registering Asana integration: {e}")

    # Asana health endpoint (always available)
    @app.route("/api/asana/health")
    def asana_health():
        return jsonify(
            {
                "ok": True,
                "service": "asana",
                "status": "registered",
                "message": "Asana integration is ready for OAuth configuration",
                "needs_oauth": True,
                "endpoints": {
                    "search": "/api/asana/search",
                    "list_tasks": "/api/asana/list-tasks",
                    "create_task": "/api/asana/create-task",
                    "oauth_authorize": "/api/auth/asana/authorize",
                    "oauth_callback": "/api/auth/asana/callback",
                },
            }
        )

    # Asana OAuth authorization endpoint
    @app.route("/api/auth/asana/authorize")
    def asana_authorize():
        user_id = request.args.get("user_id", "unknown")
        return jsonify(
            {
                "ok": True,
                "auth_url": "https://app.asana.com/-/oauth_authorize?client_id=configure_me&redirect_uri=http://localhost:8000/api/auth/asana/callback&response_type=code&state=test",
                "user_id": user_id,
                "message": "Configure ASANA_CLIENT_ID environment variable for real OAuth flow",
            }
        )

    # Asana OAuth status endpoint
    @app.route("/api/auth/asana/status")
    def asana_status():
        user_id = request.args.get("user_id", "unknown")
        return jsonify(
            {
                "ok": True,
                "connected": False,
                "expired": False,
                "user_id": user_id,
                "message": "OAuth not configured - set ASANA_CLIENT_ID and ASANA_CLIENT_SECRET",
            }
        )

    # Mock Asana search endpoint
    @app.route("/api/asana/search", methods=["POST"])
    def asana_search():
        return jsonify(
            {
                "ok": False,
                "error": {
                    "code": "AUTH_ERROR",
                    "message": "Asana OAuth not configured. Set ASANA_CLIENT_ID and ASANA_CLIENT_SECRET environment variables.",
                },
            }
        )

    # Mock Asana list tasks endpoint
    @app.route("/api/asana/list-tasks", methods=["POST"])
    def asana_list_tasks():
        return jsonify(
            {
                "ok": False,
                "error": {
                    "code": "AUTH_ERROR",
                    "message": "Asana OAuth not configured. Set ASANA_CLIENT_ID and ASANA_CLIENT_SECRET environment variables.",
                },
            }
        )

    # Service status endpoint
    @app.route("/api/services/status")
    def services_status():
        return jsonify(
            {
                "ok": True,
                "services": {
                    "asana": {
                        "registered": True,
                        "status": "needs_oauth_configuration",
                        "endpoints": ["/api/asana/*", "/api/auth/asana/*"],
                    }
                },
                "total_services": 1,
                "active_services": 0,
            }
        )

    return app


def start_backend():
    """Start the simple backend server"""
    app = create_simple_backend()

    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")

    logger.info("🚀 Starting ATOM Simple Backend with Asana Integration")
    logger.info(f"   Host: {host}")
    logger.info(f"   Port: {port}")
    logger.info(f"   Environment: {os.getenv('FLASK_ENV', 'development')}")

    # Check environment configuration
    asana_client_id = os.getenv("ASANA_CLIENT_ID")
    asana_client_secret = os.getenv("ASANA_CLIENT_SECRET")

    if not asana_client_id or not asana_client_secret:
        logger.warning("🔐 Asana OAuth credentials not configured")
        logger.info("   To enable full Asana integration, set:")
        logger.info("   - ASANA_CLIENT_ID=your_client_id")
        logger.info("   - ASANA_CLIENT_SECRET=your_client_secret")
        logger.info(
            "   - ASANA_REDIRECT_URI=http://localhost:8000/api/auth/asana/callback"
        )
    else:
        logger.info("✅ Asana OAuth credentials configured")

    try:
        app.run(host=host, port=port, debug=False, use_reloader=False)
    except Exception as e:
        logger.error(f"❌ Failed to start backend: {e}")
        sys.exit(1)


if __name__ == "__main__":
    # Import request here to avoid circular imports
    from flask import request

    start_backend()
