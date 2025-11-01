import os
import logging
import sys
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional

# Mock Flask for local testing
try:
    from flask import (
        Blueprint,
        request,
        redirect,
        url_for,
        session,
        jsonify,
        current_app,
    )
except ImportError:
    # Mock Flask classes
    class Blueprint:
        def __init__(self, name, import_name):
            self.name = name
            self.import_name = import_name
            self.routes = {}

        def route(self, rule, **options):
            def decorator(f):
                self.routes[rule] = f
                return f

            return decorator

    class MockRequest:
        args = {"user_id": "mock_user", "state": "mock_state"}
        url = "http://localhost/callback?code=mock_code&state=mock_state"

    class MockSession(dict):
        pass

    class MockCurrentApp:
        config = {"DB_CONNECTION_POOL": None}

    request = MockRequest()
    session = MockSession()
    current_app = MockCurrentApp()

    def redirect(url):
        return f"Redirect to: {url}"

    def url_for(endpoint, **kwargs):
        return f"http://localhost/{endpoint}"

    def jsonify(data):
        return data


logger = logging.getLogger(__name__)

# Create Trello auth blueprint
auth_trello_bp = Blueprint("auth_trello_bp", __name__)

# Trello OAuth configuration
TRELLO_API_KEY = os.getenv("TRELLO_API_KEY")
TRELLO_API_SECRET = os.getenv("TRELLO_API_SECRET")
TRELLO_REDIRECT_URI = os.getenv(
    "TRELLO_REDIRECT_URI", "http://localhost:5058/api/auth/trello/callback"
)

# Trello API scopes
TRELLO_SCOPES = [
    "read",
    "write",
    "account",
]

# CSRF protection
CSRF_TOKEN_SESSION_KEY = "trello_auth_csrf_token"


@auth_trello_bp.route("/api/auth/trello/authorize", methods=["GET"])
def trello_auth_initiate():
    """Initiate Trello OAuth flow"""
    try:
        import secrets
        import urllib.parse

        user_id = request.args.get("user_id")
        if not user_id:
            return jsonify({"error": "user_id parameter is required"}), 400

        # Generate CSRF token
        csrf_token = secrets.token_urlsafe(32)
        session[CSRF_TOKEN_SESSION_KEY] = csrf_token
        session["trello_auth_user_id"] = user_id

        # Build authorization URL
        auth_params = {
            "key": TRELLO_API_KEY,
            "return_url": TRELLO_REDIRECT_URI,
            "callback_method": "fragment",
            "scope": ",".join(TRELLO_SCOPES),
            "expiration": "never",
            "name": "ATOM Platform",
            "response_type": "token",
        }

        auth_url = (
            f"https://trello.com/1/authorize?{urllib.parse.urlencode(auth_params)}"
        )

        logger.info(f"Trello OAuth initiated for user {user_id}")
        return jsonify(
            {"auth_url": auth_url, "user_id": user_id, "csrf_token": csrf_token}
        )

    except Exception as e:
        logger.error(f"Trello OAuth initiation failed: {e}")
        return jsonify({"error": f"OAuth initiation failed: {str(e)}"}), 500


@auth_trello_bp.route("/api/auth/trello/callback", methods=["GET"])
async def trello_auth_callback():
    """Handle Trello OAuth callback"""
    try:
        from flask import current_app
        import requests
        import urllib.parse

        # Get database connection
        db_conn_pool = getattr(current_app, "db_pool", None) or current_app.config.get("DB_CONNECTION_POOL", None)
        if not db_conn_pool:
            return "Error: Database connection pool is not available.", 500

        user_id = session.get("trello_auth_user_id")
        if not user_id:
            return (
                "Error: No user_id found in session. Please try the connection process again.",
                400,
            )

        # Trello returns token in URL fragment
        fragment = request.args.get("fragment", "")
        if not fragment:
            return "Error: No authorization data received.", 400

        # Parse fragment parameters
        fragment_params = dict(urllib.parse.parse_qsl(fragment))
        access_token = fragment_params.get("token")
        expires_in = fragment_params.get("expires_in", "never")

        if not access_token:
            return "Error: No access token received.", 400

        # Calculate expiration time (Trello tokens can be "never" or number of seconds)
        expires_at = None
        if expires_in != "never":
            try:
                expires_at = datetime.now(timezone.utc) + timedelta(
                    seconds=int(expires_in)
                )
            except ValueError:
                # If expires_in is not a number, treat as permanent
                expires_at = None

        # Store tokens in database
        try:
            from db_oauth_gdrive import store_tokens

            await store_tokens(
                db_conn_pool=db_conn_pool,
                user_id=user_id,
                service_name="trello",
                access_token=access_token,
                refresh_token=None,  # Trello doesn't use refresh tokens
                expires_at=expires_at,
                scope=",".join(TRELLO_SCOPES),
            )

            logger.info(f"Trello OAuth completed successfully for user {user_id}")

            # Redirect to success page
            success_url = f"/settings?service=trello&status=connected"
            return redirect(success_url)

        except Exception as db_error:
            logger.error(f"Failed to store Trello tokens: {db_error}")
            return "Error: Failed to store authentication tokens.", 500

    except Exception as e:
        logger.error(f"Trello OAuth callback failed: {e}")
        return f"OAuth callback failed: {str(e)}", 500


@auth_trello_bp.route("/api/auth/trello/refresh", methods=["POST"])
async def refresh_trello_token():
    """Refresh Trello access token - Trello doesn't support refresh tokens"""
    try:
        from flask import current_app

        db_conn_pool = getattr(current_app, "db_pool", None) or current_app.config.get("DB_CONNECTION_POOL", None)
        if not db_conn_pool:
            return jsonify(
                {
                    "ok": False,
                    "error": {
                        "code": "CONFIG_ERROR",
                        "message": "Database connection pool is not available.",
                    },
                }
            ), 500

        data = request.get_json()
        user_id = data.get("user_id")
        if not user_id:
            return jsonify(
                {
                    "ok": False,
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "user_id is required.",
                    },
                }
            ), 400

        # Trello doesn't support refresh tokens - return error
        return jsonify(
            {
                "ok": False,
                "error": {
                    "code": "REFRESH_NOT_SUPPORTED",
                    "message": "Trello OAuth does not support token refresh. Re-authentication required.",
                },
            }
        ), 400

    except Exception as e:
        logger.error(f"Trello token refresh endpoint failed: {e}")
        return jsonify(
            {"ok": False, "error": {"code": "SERVER_ERROR", "message": str(e)}}
        ), 500


@auth_trello_bp.route("/api/auth/trello/disconnect", methods=["POST"])
async def trello_auth_disconnect():
    """Disconnect Trello integration"""
    try:
        from flask import current_app

        db_conn_pool = getattr(current_app, "db_pool", None) or current_app.config.get("DB_CONNECTION_POOL", None)
        if not db_conn_pool:
            return jsonify(
                {
                    "ok": False,
                    "error": {
                        "code": "CONFIG_ERROR",
                        "message": "Database connection pool is not available.",
                    },
                }
            ), 500

        data = request.get_json()
        user_id = data.get("user_id")
        if not user_id:
            return jsonify(
                {
                    "ok": False,
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "user_id is required.",
                    },
                }
            ), 400

        try:
            from db_oauth_gdrive import delete_tokens

            # Delete tokens from database
            await delete_tokens(db_conn_pool, user_id, "trello")

            logger.info(f"Trello integration disconnected for user {user_id}")
            return jsonify(
                {"ok": True, "message": "Trello integration disconnected successfully"}
            )

        except Exception as db_error:
            logger.error(f"Failed to disconnect Trello: {db_error}")
            return jsonify(
                {
                    "ok": False,
                    "error": {"code": "DISCONNECT_ERROR", "message": str(db_error)},
                }
            ), 500

    except Exception as e:
        logger.error(f"Trello disconnect endpoint failed: {e}")
        return jsonify(
            {"ok": False, "error": {"code": "SERVER_ERROR", "message": str(e)}}
        ), 500


@auth_trello_bp.route("/api/auth/trello/status", methods=["GET"])
async def trello_auth_status():
    """Get Trello OAuth status"""
    try:
        from flask import current_app

        db_conn_pool = getattr(current_app, "db_pool", None) or current_app.config.get("DB_CONNECTION_POOL", None)
        if not db_conn_pool:
            return jsonify(
                {
                    "ok": False,
                    "error": {
                        "code": "CONFIG_ERROR",
                        "message": "Database connection pool is not available.",
                    },
                }
            ), 500

        user_id = request.args.get("user_id")
        if not user_id:
            return jsonify(
                {
                    "ok": False,
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "user_id is required.",
                    },
                }
            ), 400

        try:
            from db_oauth_gdrive import get_tokens

            tokens = await get_tokens(db_conn_pool, user_id, "trello")
            if tokens and tokens.get("access_token"):
                # Check if token is expired (Trello tokens can be permanent)
                is_expired = False
                if tokens.get("expires_at"):
                    is_expired = tokens["expires_at"] < datetime.now(timezone.utc)

                return jsonify(
                    {
                        "ok": True,
                        "connected": True,
                        "expired": is_expired,
                        "scopes": tokens.get("scope", "").split(",")
                        if tokens.get("scope")
                        else [],
                    }
                )
            else:
                return jsonify(
                    {"ok": True, "connected": False, "expired": False, "scopes": []}
                )

        except Exception as db_error:
            logger.error(f"Failed to get Trello status: {db_error}")
            return jsonify(
                {
                    "ok": False,
                    "error": {"code": "STATUS_ERROR", "message": str(db_error)},
                }
            ), 500

    except Exception as e:
        logger.error(f"Trello status endpoint failed: {e}")
        return jsonify(
            {"ok": False, "error": {"code": "SERVER_ERROR", "message": str(e)}}
        ), 500


# Mock implementation for development/testing
class MockTrelloService:
    def __init__(self):
        self.connected = False

    def connect(self, access_token):
        self.connected = True
        return True

    def get_boards(self, limit=10):
        if not self.connected:
            return []

        return [
            {
                "id": f"mock_board_{i}",
                "name": f"Mock Board {i}",
                "description": f"This is a mock Trello board {i}",
                "url": f"https://trello.com/b/mock_board_{i}",
                "last_activity": datetime.now().isoformat(),
            }
            for i in range(limit)
        ]


# For local testing
if __name__ == "__main__":
    print("Trello OAuth Handler - Testing mode")
    print(f"API Key: {TRELLO_API_KEY}")
    print(f"Redirect URI: {TRELLO_REDIRECT_URI}")
    print(f"Scopes: {TRELLO_SCOPES}")
