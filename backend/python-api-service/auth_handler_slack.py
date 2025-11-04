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

# Create Slack auth blueprint
auth_slack_bp = Blueprint("auth_slack_bp", __name__)

# Slack OAuth configuration
SLACK_CLIENT_ID = os.getenv("SLACK_CLIENT_ID")
SLACK_CLIENT_SECRET = os.getenv("SLACK_CLIENT_SECRET")
SLACK_REDIRECT_URI = os.getenv(
    "SLACK_REDIRECT_URI", "http://localhost:5058/api/auth/slack/callback"
)

# Slack API endpoints
SLACK_AUTH_URL = "https://slack.com/oauth/v2/authorize"
SLACK_TOKEN_URL = "https://slack.com/api/oauth.v2.access"

# Slack API scopes
SLACK_SCOPES = [
    "channels:read",
    "channels:history",
    "groups:read",
    "groups:history",
    "im:read",
    "im:history",
    "mpim:read",
    "mpim:history",
    "chat:write",
    "chat:write.public",
    "users:read",
    "users:read.email",
    "team:read",
]

# CSRF protection
CSRF_TOKEN_SESSION_KEY = "slack_auth_csrf_token"


@auth_slack_bp.route("/api/auth/slack/authorize", methods=["GET"])
def slack_auth_initiate():
    """Initiate Slack OAuth flow"""
    try:
        import secrets
        import urllib.parse

        user_id = request.args.get("user_id")
        if not user_id:
            return jsonify({"error": "user_id parameter is required"}), 400

        # Generate CSRF token
        csrf_token = secrets.token_urlsafe(32)
        session[CSRF_TOKEN_SESSION_KEY] = csrf_token
        session["slack_auth_user_id"] = user_id

        # Build authorization URL
        auth_params = {
            "client_id": SLACK_CLIENT_ID,
            "redirect_uri": SLACK_REDIRECT_URI,
            "scope": ",".join(SLACK_SCOPES),
            "state": csrf_token,
            "user_scope": "chat:write,users:read",
        }

        auth_url = f"{SLACK_AUTH_URL}?{urllib.parse.urlencode(auth_params)}"

        logger.info(f"Slack OAuth initiated for user {user_id}")
        return jsonify(
            {"auth_url": auth_url, "user_id": user_id, "csrf_token": csrf_token}
        )

    except Exception as e:
        logger.error(f"Slack OAuth initiation failed: {e}")
        return jsonify({"error": f"OAuth initiation failed: {str(e)}"}), 500


@auth_slack_bp.route("/api/auth/slack/callback", methods=["GET"])
async def slack_auth_callback():
    """Handle Slack OAuth callback"""
    try:
        from flask import current_app
        import requests
        import urllib.parse

        # Get database connection
        db_conn_pool = getattr(current_app, "db_pool", None) or current_app.config.get("DB_CONNECTION_POOL", None)
        if not db_conn_pool:
            return "Error: Database connection pool is not available.", 500

        user_id = session.get("slack_auth_user_id")
        if not user_id:
            return (
                "Error: No user_id found in session. Please try the connection process again.",
                400,
            )

        state = session.pop(CSRF_TOKEN_SESSION_KEY, None)
        code = request.args.get("code")
        error = request.args.get("error")

        if error:
            logger.error(f"Slack OAuth callback error: {error}")
            return f"OAuth error: {error}", 400

        if not code:
            return "Error: No authorization code received.", 400

        if not state or state != request.args.get("state"):
            return (
                "Error: Invalid CSRF token. Please try the connection process again.",
                400,
            )

        # Exchange authorization code for tokens
        token_data = {
            "client_id": SLACK_CLIENT_ID,
            "client_secret": SLACK_CLIENT_SECRET,
            "code": code,
            "redirect_uri": SLACK_REDIRECT_URI,
        }

        token_response = requests.post(SLACK_TOKEN_URL, data=token_data)
        token_data = token_response.json()

        if not token_data.get("ok"):
            logger.error(f"Slack token exchange failed: {token_data}")
            return (
                f"Token exchange failed: {token_data.get('error', 'Unknown error')}",
                400,
            )

        access_token = token_data["access_token"]
        refresh_token = token_data.get("refresh_token")
        expires_in = token_data.get("expires_in", 3600)
        team_id = token_data.get("team", {}).get("id")
        team_name = token_data.get("team", {}).get("name")
        authed_user = token_data.get("authed_user", {})

        # Calculate expiration time
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

        # Store tokens in database
        try:
            from db_oauth_gdrive import store_tokens

            await store_tokens(
                db_conn_pool=db_conn_pool,
                user_id=user_id,
                service_name="slack",
                access_token=access_token,
                refresh_token=refresh_token,
                expires_at=expires_at,
                scope=",".join(SLACK_SCOPES),
                metadata=json.dumps(
                    {
                        "team_id": team_id,
                        "team_name": team_name,
                        "authed_user": authed_user,
                    }
                ),
            )

            logger.info(
                f"Slack OAuth completed successfully for user {user_id} (Team: {team_name})"
            )

            # Redirect to success page
            success_url = f"/settings?service=slack&status=connected"
            return redirect(success_url)

        except Exception as db_error:
            logger.error(f"Failed to store Slack tokens: {db_error}")
            return "Error: Failed to store authentication tokens.", 500

    except Exception as e:
        logger.error(f"Slack OAuth callback failed: {e}")
        return f"OAuth callback failed: {str(e)}", 500


@auth_slack_bp.route("/api/auth/slack/refresh", methods=["POST"])
async def refresh_slack_token():
    """Refresh Slack access token"""
    try:
        from flask import current_app
        import requests

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
            from db_oauth_gdrive import get_tokens, update_tokens

            # Get current tokens
            tokens = await get_tokens(db_conn_pool, user_id, "slack")
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
            refresh_data = {
                "client_id": SLACK_CLIENT_ID,
                "client_secret": SLACK_CLIENT_SECRET,
                "refresh_token": tokens["refresh_token"],
                "grant_type": "refresh_token",
            }

            refresh_response = requests.post(SLACK_TOKEN_URL, data=refresh_data)
            refresh_data = refresh_response.json()

            if not refresh_data.get("ok"):
                logger.error(f"Slack token refresh failed: {refresh_data}")
                return jsonify(
                    {
                        "ok": False,
                        "error": {
                            "code": "REFRESH_ERROR",
                            "message": refresh_data.get(
                                "error", "Token refresh failed"
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
                service_name="slack",
                access_token=access_token,
                expires_at=expires_at,
            )

            logger.info(f"Slack token refreshed successfully for user {user_id}")
            return jsonify(
                {
                    "ok": True,
                    "access_token": access_token,
                    "expires_at": expires_at.isoformat(),
                }
            )

        except Exception as token_error:
            logger.error(f"Slack token refresh failed: {token_error}")
            return jsonify(
                {
                    "ok": False,
                    "error": {"code": "REFRESH_ERROR", "message": str(token_error)},
                }
            ), 500

    except Exception as e:
        logger.error(f"Slack token refresh endpoint failed: {e}")
        return jsonify(
            {"ok": False, "error": {"code": "SERVER_ERROR", "message": str(e)}}
        ), 500


@auth_slack_bp.route("/api/auth/slack/disconnect", methods=["POST"])
async def slack_auth_disconnect():
    """Disconnect Slack integration"""
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
            await delete_tokens(db_conn_pool, user_id, "slack")

            logger.info(f"Slack integration disconnected for user {user_id}")
            return jsonify(
                {"ok": True, "message": "Slack integration disconnected successfully"}
            )

        except Exception as db_error:
            logger.error(f"Failed to disconnect Slack: {db_error}")
            return jsonify(
                {
                    "ok": False,
                    "error": {"code": "DISCONNECT_ERROR", "message": str(db_error)},
                }
            ), 500

    except Exception as e:
        logger.error(f"Slack disconnect endpoint failed: {e}")
        return jsonify(
            {"ok": False, "error": {"code": "SERVER_ERROR", "message": str(e)}}
        ), 500


@auth_slack_bp.route("/api/auth/slack/status", methods=["GET"])
async def slack_auth_status():
    """Get Slack OAuth status"""
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

            tokens = await get_tokens(db_conn_pool, user_id, "slack")
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
                    }
                )
            else:
                return jsonify(
                    {"ok": True, "connected": False, "expired": False, "scopes": []}
                )

        except Exception as db_error:
            logger.error(f"Failed to get Slack status: {db_error}")
            return jsonify(
                {
                    "ok": False,
                    "error": {"code": "STATUS_ERROR", "message": str(db_error)},
                }
            ), 500

    except Exception as e:
        logger.error(f"Slack status endpoint failed: {e}")
        return jsonify(
            {"ok": False, "error": {"code": "SERVER_ERROR", "message": str(e)}}
        ), 500


# Mock implementation for development/testing
class MockSlackService:
    def __init__(self):
        self.connected = False

    def connect(self, access_token):
        self.connected = True
        return True

    def get_channels(self):
        if not self.connected:
            return []

        return [
            {
                "id": f"mock_channel_{i}",
                "name": f"mock-channel-{i}",
                "is_channel": True,
                "is_private": False,
            }
            for i in range(5)
        ]

    def send_message(self, channel, text):
        if not self.connected:
            return False

        logger.info(f"Mock Slack message sent to {channel}: {text}")
        return True


# For local testing
if __name__ == "__main__":
    print("Slack OAuth Handler - Testing mode")
    print(f"Client ID: {SLACK_CLIENT_ID}")
    print(f"Redirect URI: {SLACK_REDIRECT_URI}")
    print(f"Scopes: {SLACK_SCOPES}")
