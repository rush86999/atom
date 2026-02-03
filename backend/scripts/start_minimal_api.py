#!/usr/bin/env python3
"""
Minimal startup script for Atom API service.
This script starts only the essential components for testing core functionality.
"""

import logging
import os
import sys
from flask import Flask

# Add backend modules to Python path
backend_path = os.path.join(os.path.dirname(__file__), "backend", "python-api-service")
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def create_minimal_app():
    """Create a minimal Flask app with only essential components"""

    # Set environment variables
    os.environ.setdefault(
        "DATABASE_URL",
        "postgresql://atom_user:atom_secure_2024@localhost:5432/atom_production",
    )
    os.environ.setdefault("FLASK_ENV", "development")
    os.environ.setdefault("LANCEDB_URI", "/tmp/test_lancedb")
    os.environ.setdefault("FLASK_SECRET_KEY", "test-secret-key-change-in-production")
    os.environ.setdefault("PLAID_CLIENT_ID", "test-client-id")
    os.environ.setdefault("PLAID_SECRET", "test-secret")
    os.environ.setdefault("PLAID_ENV", "sandbox")

    app = Flask(__name__)
    app.config["TESTING"] = True

    # Initialize database connection
    try:
        from db_utils import init_db_pool

        db_pool = init_db_pool()
        if db_pool:
            app.config["DB_CONNECTION_POOL"] = db_pool
            logger.info("Database connection pool initialized successfully")
        else:
            logger.warning("Database connection pool initialization failed")
            app.config["DB_CONNECTION_POOL"] = None
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        app.config["DB_CONNECTION_POOL"] = None

    # Register only essential blueprints
    try:
        from search_routes import search_routes_bp

        app.register_blueprint(search_routes_bp)
        logger.info("Registered search_routes blueprint")
    except Exception as e:
        logger.error(f"Failed to register search_routes: {e}")

    try:
        from calendar_handler import calendar_bp

        app.register_blueprint(calendar_bp)
        logger.info("Registered calendar blueprint")
    except Exception as e:
        logger.error(f"Failed to register calendar: {e}")

    try:
        from task_handler import task_bp

        app.register_blueprint(task_bp)
        logger.info("Registered task blueprint")
    except Exception as e:
        logger.error(f"Failed to register task: {e}")

    try:
        from message_handler import message_bp

        app.register_blueprint(message_bp)
        logger.info("Registered message blueprint")
    except Exception as e:
        logger.error(f"Failed to register message: {e}")

    # Register user authentication blueprint
    try:
        from user_auth_api import user_auth_bp

        app.register_blueprint(user_auth_bp)
        logger.info("Registered user_auth blueprint")
    except Exception as e:
        logger.error(f"Failed to register user_auth: {e}")

    # Health endpoint
    @app.route("/healthz")
    def healthz():
        db_status = "healthy" if app.config.get("DB_CONNECTION_POOL") else "unhealthy"
        return {
            "status": "ok",
            "database": db_status,
            "version": "1.0.0",
            "minimal": True,
        }, 200

    # Test LanceDB endpoint
    @app.route("/api/test/lancedb", methods=["GET"])
    def test_lancedb():
        try:
            import asyncio
            from lancedb_handler import (
                create_generic_document_tables_if_not_exist,
                get_lancedb_connection,
            )

            async def test():
                db_conn = await get_lancedb_connection()
                if db_conn:
                    tables_created = await create_generic_document_tables_if_not_exist(
                        db_conn
                    )
                    return {
                        "status": "success",
                        "lancedb_available": True,
                        "tables_created": tables_created,
                    }
                return {"status": "success", "lancedb_available": False}

            result = asyncio.run(test())
            return result, 200
        except Exception as e:
            return {"status": "error", "message": str(e)}, 500

    logger.info("Minimal Flask app created successfully")
    return app


def main():
    """Main function to start the minimal API server"""
    print("🚀 Starting Minimal Atom API Server")
    print("=" * 50)

    try:
        app = create_minimal_app()

        # Start the server
        port = int(os.environ.get("PYTHON_API_PORT", 5058))
        print(f"🌐 Server starting on http://0.0.0.0:{port}")
        print("📋 Available endpoints:")
        print(f"  - GET  /healthz")
        print(f"  - GET  /api/test/lancedb")
        print(f"  - POST /semantic_search_meetings")
        print(f"  - POST /hybrid_search_notes")
        print(f"  - POST /add_document")
        print(f"  - POST /api/auth/register")
        print(f"  - POST /api/auth/login")
        print(f"  - GET  /api/auth/profile")
        print(f"  - PUT  /api/auth/profile")
        print(f"  - POST /api/auth/change-password")
        print(f"  - POST /api/auth/verify-token")
        print(f"  - GET  /api/auth/health")
        print("=" * 50)

        app.run(host="0.0.0.0", port=port, debug=False)

    except Exception as e:
        print(f"❌ Failed to start server: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
