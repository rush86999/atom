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

# Create Teams auth blueprint
auth_teams_bp = Blueprint("auth_teams_bp", __name__)

# Teams OAuth configuration
TEAMS_CLIENT_ID = os.getenv("TEAMS_CLIENT_ID")
TEAMS_CLIENT_SECRET = os.getenv("TEAMS_CLIENT_SECRET")
TEAMS_TENANT_ID = os.getenv("TEAMS_TENANT_ID", "common")
TEAMS_REDIRECT_URI = os.getenv(
    "TEAMS_REDIRECT_URI", "http://localhost:5058/api/auth/teams/callback"
)

# Microsoft Graph API scopes for Teams
TEAMS_SCOPES = [
    "https://graph.microsoft.com/Team.ReadBasic.All",
    "https://graph.microsoft.com/Channel.ReadBasic.All",
    "https://graph.microsoft.com/ChannelMessage.Read",
    "https://graph.microsoft.com/ChannelMessage.Send",
    "https://graph.microsoft.com/Chat.Read",
    "https://graph.microsoft.com/Chat.ReadWrite",
    "https://graph.microsoft.com/User.Read",
    "https://graph.microsoft.com/offline_access",
]

# Microsoft Graph endpoints
MICROSOFT_AUTH_URL = "https://login.microsoftonline.com"
MICROSOFT_GRAPH_URL = "https://graph.microsoft.com/v1.0"

# CSRF protection
CSRF_TOKEN_SESSION_KEY = "teams_auth_csrf_token"


@auth_teams_bp.route("/api/auth/teams/authorize", methods=["GET"])
def teams_auth_initiate():
    """Initiate Teams OAuth flow"""
    try:
        import secrets
        import urllib.parse

        user_id = request.args.get("user_id")
        if not user_id:
            return jsonify({"error": "user_id parameter is required"}), 400

        # Generate CSRF token
        csrf_token = secrets.token_urlsafe(32)
        session[CSRF_TOKEN_SESSION_KEY] = csrf_token
        session["teams_auth_user_id"] = user_id

        # Build authorization URL
        auth_params = {
            "client_id": TEAMS_CLIENT_ID,
            "redirect_uri": TEAMS_REDIRECT_URI,
            "response_type": "code",
            "scope": " ".join(TEAMS_SCOPES),
            "state": csrf_token,
            "prompt": "consent",
        }

        auth_url = f"{MICROSOFT_AUTH_URL}/{TEAMS_TENANT_ID}/oauth2/v2.0/authorize?{urllib.parse.urlencode(auth_params)}"

        logger.info(f"Teams OAuth initiated for user {user_id}")
        return jsonify(
            {"auth_url": auth_url, "user_id": user_id, "csrf_token": csrf_token}
        )

    except Exception as e:
        logger.error(f"Teams OAuth initiation failed: {e}")
        return jsonify({"error": f"OAuth initiation failed: {str(e)}"}), 500


@auth_teams_bp.route("/api/auth/teams/callback", methods=["GET"])
async def teams_auth_callback():
    """Handle Teams OAuth callback"""
    try:
        from flask import current_app
        import requests
        import urllib.parse

        # Get database connection
        db_conn_pool = getattr(current_app, "db_pool", None) or current_app.config.get("DB_CONNECTION_POOL", None)
        if not db_conn_pool:
            return "Error: Database connection pool is not available.", 500

        user_id = session.get("teams_auth_user_id")
        if not user_id:
            return (
                "Error: No user_id found in session. Please try the connection process again.",
                400,
            )

        state = session.pop(CSRF_TOKEN_SESSION_KEY, None)
        code = request.args.get("code")
        error = request.args.get("error")

        if error:
            logger.error(f"Teams OAuth callback error: {error}")
            return f"OAuth error: {error}", 400

        if not code:
            return "Error: No authorization code received.", 400

        if not state or state != request.args.get("state"):
            return (
                "Error: Invalid CSRF token. Please try the connection process again.",
                400,
            )

        # Exchange authorization code for tokens
        token_url = f"{MICROSOFT_AUTH_URL}/{TEAMS_TENANT_ID}/oauth2/v2.0/token"
        token_data = {
            "client_id": TEAMS_CLIENT_ID,
            "client_secret": TEAMS_CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": TEAMS_REDIRECT_URI,
            "scope": " ".join(TEAMS_SCOPES),
        }

        token_response = requests.post(token_url, data=token_data)
        token_data = token_response.json()

        if token_response.status_code != 200:
            logger.error(f"Teams token exchange failed: {token_data}")
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
            from db_oauth_gdrive import store_tokens

            await store_tokens(
                db_conn_pool=db_conn_pool,
                user_id=user_id,
                service_name="teams",
                access_token=access_token,
                refresh_token=refresh_token,
                expires_at=expires_at,
                scope=" ".join(TEAMS_SCOPES),
            )

            logger.info(f"Teams OAuth completed successfully for user {user_id}")

            # Get user profile to verify connection
            profile_response = requests.get(
                f"{MICROSOFT_GRAPH_URL}/me",
                headers={"Authorization": f"Bearer {access_token}"},
            )

            if profile_response.status_code == 200:
                profile_data = profile_response.json()
                logger.info(
                    f"Teams user profile: {profile_data.get('displayName', 'Unknown')}"
                )

            # Redirect to success page
            success_url = f"/settings?service=teams&status=connected"
            return redirect(success_url)

        except Exception as db_error:
            logger.error(f"Failed to store Teams tokens: {db_error}")
            return "Error: Failed to store authentication tokens.", 500

    except Exception as e:
        logger.error(f"Teams OAuth callback failed: {e}")
        return f"OAuth callback failed: {str(e)}", 500


@auth_teams_bp.route("/api/auth/teams/refresh", methods=["POST"])
async def refresh_teams_token():
    """Refresh Teams access token"""
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
            tokens = await get_tokens(db_conn_pool, user_id, "teams")
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
            token_url = f"{MICROSOFT_AUTH_URL}/{TEAMS_TENANT_ID}/oauth2/v2.0/token"
            refresh_data = {
                "client_id": TEAMS_CLIENT_ID,
                "client_secret": TEAMS_CLIENT_SECRET,
                "refresh_token": tokens["refresh_token"],
                "grant_type": "refresh_token",
                "scope": " ".join(TEAMS_SCOPES),
            }

            refresh_response = requests.post(token_url, data=refresh_data)
            refresh_data = refresh_response.json()

            if refresh_response.status_code != 200:
                logger.error(f"Teams token refresh failed: {refresh_data}")
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
                service_name="teams",
                access_token=access_token,
                expires_at=expires_at,
            )

            logger.info(f"Teams token refreshed successfully for user {user_id}")
            return jsonify(
                {
                    "ok": True,
                    "access_token": access_token,
                    "expires_at": expires_at.isoformat(),
                }
            )

        except Exception as token_error:
            logger.error(f"Teams token refresh failed: {token_error}")
            return jsonify(
                {
                    "ok": False,
                    "error": {"code": "REFRESH_ERROR", "message": str(token_error)},
                }
            ), 500

    except Exception as e:
        logger.error(f"Teams token refresh endpoint failed: {e}")
        return jsonify(
            {"ok": False, "error": {"code": "SERVER_ERROR", "message": str(e)}}
        ), 500


@auth_teams_bp.route("/api/auth/teams/disconnect", methods=["POST"])
async def teams_auth_disconnect():
    """Disconnect Teams integration"""
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
            await delete_tokens(db_conn_pool, user_id, "teams")

            logger.info(f"Teams integration disconnected for user {user_id}")
            return jsonify(
                {"ok": True, "message": "Teams integration disconnected successfully"}
            )

        except Exception as db_error:
            logger.error(f"Failed to disconnect Teams: {db_error}")
            return jsonify(
                {
                    "ok": False,
                    "error": {"code": "DISCONNECT_ERROR", "message": str(db_error)},
                }
            ), 500

    except Exception as e:
        logger.error(f"Teams disconnect endpoint failed: {e}")
        return jsonify(
            {"ok": False, "error": {"code": "SERVER_ERROR", "message": str(e)}}
        ), 500


@auth_teams_bp.route("/api/auth/teams/status", methods=["GET"])
async def teams_auth_status():
    """Get Teams OAuth status"""
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

            tokens = await get_tokens(db_conn_pool, user_id, "teams")
            if tokens and tokens.get("access_token"):
                is_expired = tokens.get("expires_at") and tokens[
                    "expires_at"
                ] < datetime.now(timezone.utc)

                return jsonify(
                    {
                        "ok": True,
                        "connected": True,
                        "expired": is_expired,
                        "scopes": tokens.get("scope", "").split(" ")
                        if tokens.get("scope")
                        else [],
                    }
                )
            else:
                return jsonify(
                    {"ok": True, "connected": False, "expired": False, "scopes": []}
                )

        except Exception as db_error:
            logger.error(f"Failed to get Teams status: {db_error}")
            return jsonify(
                {
                    "ok": False,
                    "error": {"code": "STATUS_ERROR", "message": str(db_error)},
                }
            ), 500

    except Exception as e:
        logger.error(f"Teams status endpoint failed: {e}")
        return jsonify(
            {"ok": False, "error": {"code": "SERVER_ERROR", "message": str(e)}}
        ), 500


# Mock implementation for development/testing
class MockTeamsService:
    def __init__(self):
        self.connected = False

    def connect(self, access_token):
        self.connected = True
        return True

    def get_teams(self):
        if not self.connected:
            return []

        return [
            {
                "id": f"mock_team_{i}",
                "displayName": f"Mock Team {i}",
                "description": f"This is a mock team {i}",
            }
            for i in range(3)
        ]

    def get_channels(self, team_id):
        if not self.connected:
            return []

        return [
            {
                "id": f"mock_channel_{i}",
                "displayName": f"General {i}",
                "description": f"Mock channel for team {team_id}",
            }
            for i in range(2)
        ]


# For local testing
if __name__ == "__main__":
    print("Teams OAuth Handler - Testing mode")
    print(f"Client ID: {TEAMS_CLIENT_ID}")
    print(f"Tenant ID: {TEAMS_TENANT_ID}")
    print(f"Redirect URI: {TEAMS_REDIRECT_URI}")
    print(f"Scopes: {TEAMS_SCOPES}")
