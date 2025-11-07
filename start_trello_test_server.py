#!/usr/bin/env python3
"""
Simple Trello Test Server

This script starts a minimal Flask backend with Trello integration
for testing the complete Trello integration functionality.
"""

import logging
import os
import sys
import threading
import time

from flask import Flask, jsonify, request

# Add backend modules to Python path
backend_path = os.path.join(os.path.dirname(__file__), "backend", "python-api-service")
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def create_trello_test_server():
    """Create a simple Flask app with Trello integration"""

    # Set basic environment
    os.environ.setdefault("FLASK_ENV", "development")
    os.environ.setdefault("FLASK_SECRET_KEY", "dev-secret-key-change-in-production")
    os.environ.setdefault("DATABASE_URL", "sqlite:///./data/atom_development.db")

    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY")

    # Basic health endpoint
    @app.route("/health")
    def health():
        return jsonify(
            {
                "status": "ok",
                "service": "atom-trello-test-server",
                "version": "1.0.0",
                "timestamp": time.time(),
            }
        )

    # Root endpoint
    @app.route("/")
    def root():
        return jsonify(
            {
                "name": "ATOM Trello Test Server",
                "status": "running",
                "version": "1.0.0",
                "integrations": ["trello"],
                "endpoints": {
                    "health": "/health",
                    "trello_health": "/api/integrations/trello/health",
                    "trello_info": "/api/integrations/trello/info",
                    "trello_oauth": "/api/auth/trello/authorize",
                },
            }
        )

    # Try to register Trello integration
    try:
        from auth_handler_trello import auth_trello_bp
        from trello_routes import router as trello_router

        # Register Trello routes
        app.register_blueprint(trello_router, url_prefix="")
        app.register_blueprint(auth_trello_bp, url_prefix="")

        logger.info("✅ Trello integration registered successfully")
        logger.info("   - API endpoints: /api/integrations/trello/*")
        logger.info("   - OAuth endpoints: /api/auth/trello/*")

    except ImportError as e:
        logger.error(f"❌ Failed to register Trello integration: {e}")
        logger.info("   Creating mock endpoints for testing...")

        # Create mock Trello endpoints
        @app.route("/api/integrations/trello/health")
        def mock_trello_health():
            return jsonify(
                {
                    "status": "healthy",
                    "service": "trello",
                    "timestamp": time.time(),
                    "service_available": True,
                    "database_available": False,
                    "api_key_configured": bool(os.getenv("TRELLO_API_KEY")),
                    "oauth_token_configured": bool(os.getenv("TRELLO_API_SECRET")),
                    "message": "Trello integration is operational (mock mode)",
                }
            )

        @app.route("/api/integrations/trello/info")
        def mock_trello_info():
            return jsonify(
                {
                    "ok": True,
                    "data": {
                        "service": "trello",
                        "version": "1.0.0",
                        "status": "mock",
                        "capabilities": [
                            "boards",
                            "cards",
                            "lists",
                            "members",
                            "search",
                            "create_cards",
                            "update_cards",
                            "workflows",
                            "actions",
                        ],
                        "api_endpoints": [
                            "/api/integrations/trello/boards/list",
                            "/api/integrations/trello/cards/list",
                            "/api/integrations/trello/lists/list",
                            "/api/integrations/trello/members/list",
                            "/api/integrations/trello/workflows/list",
                            "/api/integrations/trello/actions/list",
                        ],
                    },
                }
            )

        @app.route("/api/auth/trello/health")
        def mock_trello_oauth_health():
            return jsonify(
                {
                    "service": "trello-oauth",
                    "status": "mock",
                    "components": {
                        "oauth": {"status": "mock"},
                        "api": {"status": "mock"},
                    },
                }
            )

        @app.route("/api/auth/trello/authorize", methods=["POST"])
        def mock_trello_authorize():
            data = request.get_json() or {}
            user_id = data.get("user_id", "test-user")

            return jsonify(
                {
                    "ok": True,
                    "oauth_url": "https://trello.com/1/OAuthAuthorizeToken?oauth_token=mock_token&name=ATOM+Integration",
                    "user_id": user_id,
                    "message": "Mock OAuth flow - configure TRELLO_API_KEY and TRELLO_API_SECRET for real integration",
                }
            )

        # Mock Trello API endpoints
        @app.route("/api/integrations/trello/boards/list", methods=["POST"])
        def mock_boards_list():
            return jsonify(
                {
                    "ok": True,
                    "data": {
                        "boards": [
                            {
                                "id": "mock_board_1",
                                "name": "Development Board",
                                "desc": "Mock development board",
                                "url": "https://trello.com/b/mock_board_1",
                                "closed": False,
                            },
                            {
                                "id": "mock_board_2",
                                "name": "Product Roadmap",
                                "desc": "Mock product roadmap board",
                                "url": "https://trello.com/b/mock_board_2",
                                "closed": False,
                            },
                        ]
                    },
                }
            )

        @app.route("/api/integrations/trello/cards/list", methods=["POST"])
        def mock_cards_list():
            return jsonify(
                {
                    "ok": True,
                    "data": {
                        "cards": [
                            {
                                "id": "mock_card_1",
                                "name": "Implement Trello Integration",
                                "desc": "Complete the Trello integration with OAuth",
                                "url": "https://trello.com/c/mock_card_1",
                                "due_date": None,
                                "labels": ["backend", "integration"],
                                "list_name": "In Progress",
                            },
                            {
                                "id": "mock_card_2",
                                "name": "Test OAuth Flow",
                                "desc": "Test the complete OAuth authorization flow",
                                "url": "https://trello.com/c/mock_card_2",
                                "due_date": None,
                                "labels": ["testing", "oauth"],
                                "list_name": "To Do",
                            },
                        ]
                    },
                }
            )

        @app.route("/api/integrations/trello/lists/list", methods=["POST"])
        def mock_lists_list():
            return jsonify(
                {
                    "ok": True,
                    "data": {
                        "lists": [
                            {"id": "list_1", "name": "To Do", "closed": False},
                            {"id": "list_2", "name": "In Progress", "closed": False},
                            {"id": "list_3", "name": "Done", "closed": False},
                        ]
                    },
                }
            )

        @app.route("/api/integrations/trello/members/list", methods=["POST"])
        def mock_members_list():
            return jsonify(
                {
                    "ok": True,
                    "data": {
                        "members": [
                            {
                                "id": "member_1",
                                "fullName": "Test User",
                                "username": "testuser",
                                "avatarUrl": None,
                            }
                        ]
                    },
                }
            )

        @app.route("/api/integrations/trello/workflows/list", methods=["POST"])
        def mock_workflows_list():
            return jsonify(
                {
                    "ok": True,
                    "data": {
                        "workflows": [
                            {
                                "id": "workflow_1",
                                "name": "Development Workflow",
                                "description": "Mock development workflow",
                            }
                        ]
                    },
                }
            )

        @app.route("/api/integrations/trello/actions/list", methods=["POST"])
        def mock_actions_list():
            return jsonify(
                {
                    "ok": True,
                    "data": {
                        "actions": [
                            {
                                "id": "action_1",
                                "type": "createCard",
                                "date": time.time(),
                                "data": {"card": {"name": "Test Card"}},
                            }
                        ]
                    },
                }
            )

    except Exception as e:
        logger.error(f"❌ Error registering Trello integration: {e}")

    return app


def start_trello_test_server():
    """Start the Trello test server"""
    app = create_trello_test_server()

    port = int(os.getenv("PORT", 5058))
    host = os.getenv("HOST", "0.0.0.0")

    logger.info("🚀 Starting ATOM Trello Test Server")
    logger.info(f"   Host: {host}")
    logger.info(f"   Port: {port}")
    logger.info(f"   Environment: {os.getenv('FLASK_ENV', 'development')}")

    # Check environment configuration
    trello_api_key = os.getenv("TRELLO_API_KEY")
    trello_api_secret = os.getenv("TRELLO_API_SECRET")

    if not trello_api_key or not trello_api_secret:
        logger.warning("🔐 Trello API credentials not configured")
        logger.info("   To enable real Trello integration, set:")
        logger.info("   - TRELLO_API_KEY=your_api_key")
        logger.info("   - TRELLO_API_SECRET=your_api_token")
        logger.info(
            "   - TRELLO_REDIRECT_URI=http://localhost:3000/oauth/trello/callback"
        )
        logger.info("   Server will run in mock mode for testing")
    else:
        logger.info("✅ Trello API credentials configured")

    try:
        app.run(host=host, port=port, debug=False, use_reloader=False)
    except Exception as e:
        logger.error(f"❌ Failed to start Trello test server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    start_trello_test_server()
