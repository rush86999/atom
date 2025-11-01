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

# Create Notion auth blueprint
auth_notion_bp = Blueprint("auth_notion_bp", __name__)

# Notion OAuth configuration
NOTION_CLIENT_ID = os.getenv("NOTION_CLIENT_ID")
NOTION_CLIENT_SECRET = os.getenv("NOTION_CLIENT_SECRET")
NOTION_REDIRECT_URI = os.getenv(
    "NOTION_REDIRECT_URI", "http://localhost:5058/api/auth/notion/callback"
)

# Notion API scopes
NOTION_SCOPES = []

# CSRF protection
CSRF_TOKEN_SESSION_KEY = "notion_auth_csrf_token"


@auth_notion_bp.route("/api/auth/notion/authorize", methods=["GET"])
def notion_auth_initiate():
    """Initiate Notion OAuth flow"""
    try:
        import secrets
        import urllib.parse

        user_id = request.args.get("user_id")
        if not user_id:
            return jsonify({"error": "user_id parameter is required"}), 400

        # Generate CSRF token
        csrf_token = secrets.token_urlsafe(32)
        session[CSRF_TOKEN_SESSION_KEY] = csrf_token
        session["notion_auth_user_id"] = user_id

        # Build authorization URL
        auth_params = {
            "client_id": NOTION_CLIENT_ID,
            "redirect_uri": NOTION_REDIRECT_URI,
            "response_type": "code",
            "owner": "user",
            "state": csrf_token,
        }

        auth_url = f"https://api.notion.com/v1/oauth/authorize?{urllib.parse.urlencode(auth_params)}"

        logger.info(f"Notion OAuth initiated for user {user_id}")
        return jsonify(
            {"auth_url": auth_url, "user_id": user_id, "csrf_token": csrf_token}
        )

    except Exception as e:
        logger.error(f"Notion OAuth initiation failed: {e}")
        return jsonify({"error": f"OAuth initiation failed: {str(e)}"}), 500


@auth_notion_bp.route("/api/auth/notion/callback", methods=["GET"])
async def notion_auth_callback():
    """Handle Notion OAuth callback"""
    try:
        from flask import current_app
        import requests
        import urllib.parse

        # Get database connection
        db_conn_pool = getattr(current_app, "db_pool", None) or current_app.config.get("DB_CONNECTION_POOL", None)
        if not db_conn_pool:
            return "Error: Database connection pool is not available.", 500

        user_id = session.get("notion_auth_user_id")
        if not user_id:
            return (
                "Error: No user_id found in session. Please try the connection process again.",
                400,
            )

        state = session.pop(CSRF_TOKEN_SESSION_KEY, None)
        code = request.args.get("code")
        error = request.args.get("error")

        if error:
            logger.error(f"Notion OAuth callback error: {error}")
            return f"OAuth error: {error}", 400

        if not code:
            return "Error: No authorization code received.", 400

        if not state or state != request.args.get("state"):
            return (
                "Error: Invalid CSRF token. Please try the connection process again.",
                400,
            )

        # Exchange authorization code for tokens
        token_url = "https://api.notion.com/v1/oauth/token"
        token_data = {
            "grant_type": "authorization_code",
            "client_id": NOTION_CLIENT_ID,
            "client_secret": NOTION_CLIENT_SECRET,
            "code": code,
            "redirect_uri": NOTION_REDIRECT_URI,
        }

        token_headers = {
            "Content-Type": "application/json",
            "Authorization": f"Basic {os.getenv('NOTION_API_KEY', '')}",
        }

        token_response = requests.post(
            token_url, json=token_data, headers=token_headers
        )
        token_data = token_response.json()

        if token_response.status_code != 200:
            logger.error(f"Notion token exchange failed: {token_data}")
            return (
                f"Token exchange failed: {token_data.get('error_description', 'Unknown error')}",
                400,
            )

        access_token = token_data["access_token"]
        bot_id = token_data.get("bot_id")
        workspace_name = token_data.get("workspace_name")
        workspace_icon = token_data.get("workspace_icon")
        workspace_id = token_data.get("workspace_id")
        duplicated_template_id = token_data.get("duplicated_template_id")

        # Notion tokens don't expire, but we'll set a long expiration
        expires_at = datetime.now(timezone.utc) + timedelta(days=365)

        # Store tokens in database
        try:
            from db_oauth_gdrive import store_tokens

            await store_tokens(
                db_conn_pool=db_conn_pool,
                user_id=user_id,
                service_name="notion",
                access_token=access_token,
                refresh_token=None,  # Notion doesn't use refresh tokens
                expires_at=expires_at,
                scope=",".join(NOTION_SCOPES),
                metadata={
                    "bot_id": bot_id,
                    "workspace_name": workspace_name,
                    "workspace_icon": workspace_icon,
                    "workspace_id": workspace_id,
                    "duplicated_template_id": duplicated_template_id,
                },
            )

            logger.info(f"Notion OAuth completed successfully for user {user_id}")

            # Redirect to success page
            success_url = f"/settings?service=notion&status=connected"
            return redirect(success_url)

        except Exception as db_error:
            logger.error(f"Failed to store Notion tokens: {db_error}")
            return "Error: Failed to store authentication tokens.", 500

    except Exception as e:
        logger.error(f"Notion OAuth callback failed: {e}")
        return f"OAuth callback failed: {str(e)}", 500


@auth_notion_bp.route("/api/auth/notion/refresh", methods=["POST"])
async def refresh_notion_token():
    """Refresh Notion access token - Notion doesn't support refresh tokens"""
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

        # Notion doesn't support refresh tokens - return error
        return jsonify(
            {
                "ok": False,
                "error": {
                    "code": "REFRESH_NOT_SUPPORTED",
                    "message": "Notion OAuth does not support token refresh. Re-authentication required.",
                },
            }
        ), 400

    except Exception as e:
        logger.error(f"Notion token refresh endpoint failed: {e}")
        return jsonify(
            {"ok": False, "error": {"code": "SERVER_ERROR", "message": str(e)}}
        ), 500


@auth_notion_bp.route("/api/auth/notion/disconnect", methods=["POST"])
async def notion_auth_disconnect():
    """Disconnect Notion integration"""
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
            await delete_tokens(db_conn_pool, user_id, "notion")

            logger.info(f"Notion integration disconnected for user {user_id}")
            return jsonify(
                {"ok": True, "message": "Notion integration disconnected successfully"}
            )

        except Exception as db_error:
            logger.error(f"Failed to disconnect Notion: {db_error}")
            return jsonify(
                {
                    "ok": False,
                    "error": {"code": "DISCONNECT_ERROR", "message": str(db_error)},
                }
            ), 500

    except Exception as e:
        logger.error(f"Notion disconnect endpoint failed: {e}")
        return jsonify(
            {"ok": False, "error": {"code": "SERVER_ERROR", "message": str(e)}}
        ), 500


@auth_notion_bp.route("/api/auth/notion/status", methods=["GET"])
async def notion_auth_status():
    """Get Notion OAuth status"""
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

            tokens = await get_tokens(db_conn_pool, user_id, "notion")
            if tokens and tokens.get("access_token"):
                # Notion tokens don't expire, but we check anyway
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
                        "metadata": tokens.get("metadata", {}),
                    }
                )
            else:
                return jsonify(
                    {"ok": True, "connected": False, "expired": False, "scopes": []}
                )

        except Exception as db_error:
            logger.error(f"Failed to get Notion status: {db_error}")
            return jsonify(
                {
                    "ok": False,
                    "error": {"code": "STATUS_ERROR", "message": str(db_error)},
                }
            ), 500

    except Exception as e:
        logger.error(f"Notion status endpoint failed: {e}")
        return jsonify(
            {"ok": False, "error": {"code": "SERVER_ERROR", "message": str(e)}}
        ), 500


# Mock implementation for development/testing
class MockNotionService:
    def __init__(self):
        self.connected = False

    def connect(self, access_token):
        self.connected = True
        return True

    def get_pages(self, limit=10):
        if not self.connected:
            return []

        return [
            {
                "id": f"mock_page_{i}",
                "title": f"Mock Page {i}",
                "description": f"This is a mock Notion page {i}",
                "created_time": datetime.now().isoformat(),
                "last_edited_time": datetime.now().isoformat(),
            }
            for i in range(limit)
        ]


# For local testing
if __name__ == "__main__":
    print("Notion OAuth Handler - Testing mode")
    print(f"Client ID: {NOTION_CLIENT_ID}")
    print(f"Redirect URI: {NOTION_REDIRECT_URI}")
    print(f"Scopes: {NOTION_SCOPES}")
