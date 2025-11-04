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

# Create Gmail auth blueprint
auth_gmail_bp = Blueprint("auth_gmail_bp", __name__)

# Gmail OAuth configuration
GMAIL_CLIENT_ID = os.getenv("GMAIL_CLIENT_ID") or os.getenv("GOOGLE_CLIENT_ID")
GMAIL_CLIENT_SECRET = os.getenv("GMAIL_CLIENT_SECRET") or os.getenv(
    "GOOGLE_CLIENT_SECRET"
)
GMAIL_REDIRECT_URI = os.getenv(
    "GMAIL_REDIRECT_URI", "http://localhost:5058/api/auth/gmail/callback"
)

# Gmail API scopes
GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.labels",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]

# CSRF protection
CSRF_TOKEN_SESSION_KEY = "gmail_auth_csrf_token"


@auth_gmail_bp.route("/api/auth/gmail/authorize", methods=["GET"])
def gmail_auth_initiate():
    """Initiate Gmail OAuth flow"""
    try:
        import secrets
        import urllib.parse

        user_id = request.args.get("user_id")
        if not user_id:
            return jsonify({"error": "user_id parameter is required"}), 400

        # Generate CSRF token
        csrf_token = secrets.token_urlsafe(32)
        session[CSRF_TOKEN_SESSION_KEY] = csrf_token
        session["gmail_auth_user_id"] = user_id

        # Build authorization URL
        auth_params = {
            "client_id": GMAIL_CLIENT_ID,
            "redirect_uri": GMAIL_REDIRECT_URI,
            "response_type": "code",
            "scope": " ".join(GMAIL_SCOPES),
            "access_type": "offline",
            "state": csrf_token,
            "prompt": "consent",
        }

        auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urllib.parse.urlencode(auth_params)}"

        logger.info(f"Gmail OAuth initiated for user {user_id}")
        return jsonify(
            {"auth_url": auth_url, "user_id": user_id, "csrf_token": csrf_token}
        )

    except Exception as e:
        logger.error(f"Gmail OAuth initiation failed: {e}")
        return jsonify({"error": f"OAuth initiation failed: {str(e)}"}), 500


@auth_gmail_bp.route("/api/auth/gmail/callback", methods=["GET"])
async def gmail_auth_callback():
    """Handle Gmail OAuth callback"""
    try:
        from flask import current_app
        import requests
        import urllib.parse

        # Get database connection
        db_conn_pool = getattr(current_app, "db_pool", None) or current_app.config.get("DB_CONNECTION_POOL", None)
        if not db_conn_pool:
            return "Error: Database connection pool is not available.", 500

        user_id = session.get("gmail_auth_user_id")
        if not user_id:
            return (
                "Error: No user_id found in session. Please try the connection process again.",
                400,
            )

        state = session.pop(CSRF_TOKEN_SESSION_KEY, None)
        code = request.args.get("code")
        error = request.args.get("error")

        if error:
            logger.error(f"Gmail OAuth callback error: {error}")
            return f"OAuth error: {error}", 400

        if not code:
            return "Error: No authorization code received.", 400

        if not state or state != request.args.get("state"):
            return (
                "Error: Invalid CSRF token. Please try the connection process again.",
                400,
            )

        # Exchange authorization code for tokens
        token_url = "https://oauth2.googleapis.com/token"
        token_data = {
            "client_id": GMAIL_CLIENT_ID,
            "client_secret": GMAIL_CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": GMAIL_REDIRECT_URI,
        }

        token_response = requests.post(token_url, data=token_data)
        token_data = token_response.json()

        if token_response.status_code != 200:
            logger.error(f"Gmail token exchange failed: {token_data}")
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
            from db_oauth_gdrive import store_tokens  # Reuse Google Drive token storage

            await store_tokens(
                db_conn_pool=db_conn_pool,
                user_id=user_id,
                service_name="gmail",
                access_token=access_token,
                refresh_token=refresh_token,
                expires_at=expires_at,
                scope=" ".join(GMAIL_SCOPES),
            )

            logger.info(f"Gmail OAuth completed successfully for user {user_id}")

            # Redirect to success page
            success_url = f"/settings?service=gmail&status=connected"
            return redirect(success_url)

        except Exception as db_error:
            logger.error(f"Failed to store Gmail tokens: {db_error}")
            return "Error: Failed to store authentication tokens.", 500

    except Exception as e:
        logger.error(f"Gmail OAuth callback failed: {e}")
        return f"OAuth callback failed: {str(e)}", 500


@auth_gmail_bp.route("/api/auth/gmail/refresh", methods=["POST"])
async def refresh_gmail_token():
    """Refresh Gmail access token"""
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
            tokens = await get_tokens(db_conn_pool, user_id, "gmail")
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
            token_url = "https://oauth2.googleapis.com/token"
            refresh_data = {
                "client_id": GMAIL_CLIENT_ID,
                "client_secret": GMAIL_CLIENT_SECRET,
                "refresh_token": tokens["refresh_token"],
                "grant_type": "refresh_token",
            }

            refresh_response = requests.post(token_url, data=refresh_data)
            refresh_data = refresh_response.json()

            if refresh_response.status_code != 200:
                logger.error(f"Gmail token refresh failed: {refresh_data}")
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
                service_name="gmail",
                access_token=access_token,
                expires_at=expires_at,
            )

            logger.info(f"Gmail token refreshed successfully for user {user_id}")
            return jsonify(
                {
                    "ok": True,
                    "access_token": access_token,
                    "expires_at": expires_at.isoformat(),
                }
            )

        except Exception as token_error:
            logger.error(f"Gmail token refresh failed: {token_error}")
            return jsonify(
                {
                    "ok": False,
                    "error": {"code": "REFRESH_ERROR", "message": str(token_error)},
                }
            ), 500

    except Exception as e:
        logger.error(f"Gmail token refresh endpoint failed: {e}")
        return jsonify(
            {"ok": False, "error": {"code": "SERVER_ERROR", "message": str(e)}}
        ), 500


@auth_gmail_bp.route("/api/auth/gmail/disconnect", methods=["POST"])
async def gmail_auth_disconnect():
    """Disconnect Gmail integration"""
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
            await delete_tokens(db_conn_pool, user_id, "gmail")

            logger.info(f"Gmail integration disconnected for user {user_id}")
            return jsonify(
                {"ok": True, "message": "Gmail integration disconnected successfully"}
            )

        except Exception as db_error:
            logger.error(f"Failed to disconnect Gmail: {db_error}")
            return jsonify(
                {
                    "ok": False,
                    "error": {"code": "DISCONNECT_ERROR", "message": str(db_error)},
                }
            ), 500

    except Exception as e:
        logger.error(f"Gmail disconnect endpoint failed: {e}")
        return jsonify(
            {"ok": False, "error": {"code": "SERVER_ERROR", "message": str(e)}}
        ), 500


@auth_gmail_bp.route("/api/auth/gmail/status", methods=["GET"])
async def gmail_auth_status():
    """Get Gmail OAuth status"""
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

            tokens = await get_tokens(db_conn_pool, user_id, "gmail")
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
            logger.error(f"Failed to get Gmail status: {db_error}")
            return jsonify(
                {
                    "ok": False,
                    "error": {"code": "STATUS_ERROR", "message": str(db_error)},
                }
            ), 500

    except Exception as e:
        logger.error(f"Gmail status endpoint failed: {e}")
        return jsonify(
            {"ok": False, "error": {"code": "SERVER_ERROR", "message": str(e)}}
        ), 500


# Mock implementation for development/testing
class MockGmailService:
    def __init__(self):
        self.connected = False

    def connect(self, access_token):
        self.connected = True
        return True

    def get_emails(self, limit=10):
        if not self.connected:
            return []

        return [
            {
                "id": f"mock_email_{i}",
                "subject": f"Mock Email Subject {i}",
                "from": f"sender{i}@example.com",
                "snippet": f"This is a mock email snippet for email {i}",
                "date": datetime.now().isoformat(),
            }
            for i in range(limit)
        ]


# For local testing
if __name__ == "__main__":
    print("Gmail OAuth Handler - Testing mode")
    print(f"Client ID: {GMAIL_CLIENT_ID}")
    print(f"Redirect URI: {GMAIL_REDIRECT_URI}")
    print(f"Scopes: {GMAIL_SCOPES}")
