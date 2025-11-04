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

# Create Asana auth blueprint
auth_asana_bp = Blueprint("auth_asana_bp", __name__)

# Asana OAuth configuration
ASANA_CLIENT_ID = os.getenv("ASANA_CLIENT_ID")
ASANA_CLIENT_SECRET = os.getenv("ASANA_CLIENT_SECRET")
ASANA_REDIRECT_URI = os.getenv(
    "ASANA_REDIRECT_URI", "http://localhost:5058/api/auth/asana/callback"
)

# Asana API scopes
ASANA_SCOPES = [
    "default",
    "tasks:read",
    "tasks:write",
    "projects:read",
    "projects:write",
    "workspaces:read",
    "users:read",
]

# CSRF protection
CSRF_TOKEN_SESSION_KEY = "asana_auth_csrf_token"


@auth_asana_bp.route("/api/auth/asana/authorize", methods=["GET"])
def asana_auth_initiate():
    """Initiate Asana OAuth flow"""
    try:
        import secrets
        import urllib.parse

        user_id = request.args.get("user_id")
        if not user_id:
            return jsonify({"error": "user_id parameter is required"}), 400

        # Generate CSRF token
        csrf_token = secrets.token_urlsafe(32)
        session[CSRF_TOKEN_SESSION_KEY] = csrf_token
        session["asana_auth_user_id"] = user_id

        # Build authorization URL
        auth_params = {
            "client_id": ASANA_CLIENT_ID,
            "redirect_uri": ASANA_REDIRECT_URI,
            "response_type": "code",
            "state": csrf_token,
            "scope": " ".join(ASANA_SCOPES),
        }

        auth_url = f"https://app.asana.com/-/oauth_authorize?{urllib.parse.urlencode(auth_params)}"

        logger.info(f"Asana OAuth initiated for user {user_id}")
        return jsonify(
            {"auth_url": auth_url, "user_id": user_id, "csrf_token": csrf_token}
        )

    except Exception as e:
        logger.error(f"Asana OAuth initiation failed: {e}")
        return jsonify({"error": f"OAuth initiation failed: {str(e)}"}), 500


@auth_asana_bp.route("/api/auth/asana/callback", methods=["GET"])
async def asana_auth_callback():
    """Handle Asana OAuth callback"""
    try:
        from flask import current_app
        import requests
        import urllib.parse

        # Get database connection
        db_conn_pool = getattr(current_app, "db_pool", None) or current_app.config.get(
            "DB_CONNECTION_POOL", None
        )
        if not db_conn_pool:
            return "Error: Database connection pool is not available.", 500

        user_id = session.get("asana_auth_user_id")
        if not user_id:
            return (
                "Error: No user_id found in session. Please try the connection process again.",
                400,
            )

        state = session.pop(CSRF_TOKEN_SESSION_KEY, None)
        code = request.args.get("code")
        error = request.args.get("error")

        if error:
            logger.error(f"Asana OAuth callback error: {error}")
            return f"OAuth error: {error}", 400

        if not code:
            return "Error: No authorization code received.", 400

        if not state or state != request.args.get("state"):
            return (
                "Error: Invalid CSRF token. Please try the connection process again.",
                400,
            )

        # Exchange authorization code for tokens
        token_url = "https://app.asana.com/-/oauth_token"
        token_data = {
            "grant_type": "authorization_code",
            "client_id": ASANA_CLIENT_ID,
            "client_secret": ASANA_CLIENT_SECRET,
            "code": code,
            "redirect_uri": ASANA_REDIRECT_URI,
        }

        token_response = requests.post(token_url, data=token_data)
        token_data = token_response.json()

        if token_response.status_code != 200:
            logger.error(f"Asana token exchange failed: {token_data}")
            return (
                f"Token exchange failed: {token_data.get('error_description', 'Unknown error')}",
                400,
            )

        access_token = token_data["access_token"]
        refresh_token = token_data.get("refresh_token")
        expires_in = token_data.get("expires_in", 3600)

        # Calculate expiration time
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

        # Store tokens in database
        try:
            from db_oauth_asana import store_tokens

            await store_tokens(
                db_conn_pool=db_conn_pool,
                user_id=user_id,
                service_name="asana",
                access_token=access_token,
                refresh_token=refresh_token,
                expires_at=expires_at,
                scope=",".join(ASANA_SCOPES),
            )

            logger.info(f"Asana OAuth completed successfully for user {user_id}")

            # Redirect to success page
            success_url = f"/settings?service=asana&status=connected"
            return redirect(success_url)

        except Exception as db_error:
            logger.error(f"Failed to store Asana tokens: {db_error}")
            return "Error: Failed to store authentication tokens.", 500

    except Exception as e:
        logger.error(f"Asana OAuth callback failed: {e}")
        return f"OAuth callback failed: {str(e)}", 500


@auth_asana_bp.route("/api/auth/asana/refresh", methods=["POST"])
async def refresh_asana_token():
    """Refresh Asana access token"""
    try:
        from flask import current_app
        import requests

        db_conn_pool = getattr(current_app, "db_pool", None) or current_app.config.get(
            "DB_CONNECTION_POOL", None
        )
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
            from db_oauth_asana import get_tokens, update_tokens

            # Get current tokens
            tokens = await get_tokens(db_conn_pool, user_id, "asana")
            if not tokens or not tokens.get("refresh_token"):
                return jsonify(
                    {
                        "ok": False,
                        "error": {
                            "code": "TOKEN_ERROR",
                            "message": "No refresh token available.",
                        },
                    }
                ), 400

            # Refresh token
            token_url = "https://app.asana.com/-/oauth_token"
            refresh_data = {
                "grant_type": "refresh_token",
                "client_id": ASANA_CLIENT_ID,
                "client_secret": ASANA_CLIENT_SECRET,
                "refresh_token": tokens["refresh_token"],
            }

            refresh_response = requests.post(token_url, data=refresh_data)
            refresh_data = refresh_response.json()

            if refresh_response.status_code != 200:
                logger.error(f"Asana token refresh failed: {refresh_data}")
                return jsonify(
                    {
                        "ok": False,
                        "error": {
                            "code": "REFRESH_ERROR",
                            "message": refresh_data.get(
                                "error_description", "Token refresh failed"
                            ),
                        },
                    }
                ), 400

            access_token = refresh_data["access_token"]
            expires_in = refresh_data.get("expires_in", 3600)
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

            # Update tokens in database
            await update_tokens(
                db_conn_pool=db_conn_pool,
                user_id=user_id,
                service_name="asana",
                access_token=access_token,
                expires_at=expires_at,
            )

            logger.info(f"Asana token refreshed successfully for user {user_id}")
            return jsonify(
                {
                    "ok": True,
                    "access_token": access_token,
                    "expires_at": expires_at.isoformat(),
                }
            )

        except Exception as token_error:
            logger.error(f"Asana token refresh failed: {token_error}")
            return jsonify(
                {
                    "ok": False,
                    "error": {"code": "REFRESH_ERROR", "message": str(token_error)},
                }
            ), 500

    except Exception as e:
        logger.error(f"Asana token refresh endpoint failed: {e}")
        return jsonify(
            {"ok": False, "error": {"code": "SERVER_ERROR", "message": str(e)}}
        ), 500


@auth_asana_bp.route("/api/auth/asana/disconnect", methods=["POST"])
async def asana_auth_disconnect():
    """Disconnect Asana integration"""
    try:
        from flask import current_app

        db_conn_pool = getattr(current_app, "db_pool", None) or current_app.config.get(
            "DB_CONNECTION_POOL", None
        )
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
            from db_oauth_asana import delete_tokens

            # Delete tokens from database
            await delete_tokens(db_conn_pool, user_id, "asana")

            logger.info(f"Asana integration disconnected for user {user_id}")
            return jsonify(
                {"ok": True, "message": "Asana integration disconnected successfully"}
            )

        except Exception as db_error:
            logger.error(f"Failed to disconnect Asana: {db_error}")
            return jsonify(
                {
                    "ok": False,
                    "error": {"code": "DISCONNECT_ERROR", "message": str(db_error)},
                }
            ), 500

    except Exception as e:
        logger.error(f"Asana disconnect endpoint failed: {e}")
        return jsonify(
            {"ok": False, "error": {"code": "SERVER_ERROR", "message": str(e)}}
        ), 500


@auth_asana_bp.route("/api/auth/asana/status", methods=["GET"])
async def asana_auth_status():
    """Get Asana OAuth status"""
    try:
        from flask import current_app

        db_conn_pool = getattr(current_app, "db_pool", None) or current_app.config.get(
            "DB_CONNECTION_POOL", None
        )
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
            from db_oauth_asana import get_tokens

            tokens = await get_tokens(db_conn_pool, user_id, "asana")
            if tokens and tokens.get("access_token"):
                is_expired = tokens.get("expires_at") and tokens[
                    "expires_at"
                ] < datetime.now(timezone.utc)

                return jsonify(
                    {
                        "ok": True,
                        "connected": True,
                        "expired": is_expired,
                        "scopes": tokens.get("scope", "").split(",")
                        if tokens.get("scope")
                        else [],
                        "user_id": user_id,
                    }
                )
            else:
                return jsonify(
                    {
                        "ok": True,
                        "connected": False,
                        "expired": False,
                        "scopes": [],
                        "user_id": user_id,
                    }
                )

        except Exception as db_error:
            logger.error(f"Failed to get Asana status: {db_error}")
            return jsonify(
                {
                    "ok": False,
                    "error": {"code": "STATUS_ERROR", "message": str(db_error)},
                }
            ), 500

    except Exception as e:
        logger.error(f"Asana status endpoint failed: {e}")
        return jsonify(
            {"ok": False, "error": {"code": "SERVER_ERROR", "message": str(e)}}
        ), 500


# Mock implementation for development/testing
class MockAsanaService:
    def __init__(self):
        self.connected = False

    def connect(self, access_token):
        self.connected = True
        return True

    def get_projects(self, limit=10):
        if not self.connected:
            return []

        return [
            {
                "id": f"mock_project_{i}",
                "name": f"Mock Project {i}",
                "description": f"This is a mock Asana project {i}",
                "created_at": datetime.now().isoformat(),
                "modified_at": datetime.now().isoformat(),
            }
            for i in range(limit)
        ]


# For local testing
if __name__ == "__main__":
    print("Asana OAuth Handler - Testing mode")
    print(f"Client ID: {ASANA_CLIENT_ID}")
    print(f"Redirect URI: {ASANA_REDIRECT_URI}")
    print(f"Scopes: {ASANA_SCOPES}")
