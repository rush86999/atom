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

# Create GitHub auth blueprint
auth_github_bp = Blueprint("auth_github_bp", __name__)

# GitHub OAuth configuration
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")
GITHUB_REDIRECT_URI = os.getenv(
    "GITHUB_REDIRECT_URI", "http://localhost:5058/api/auth/github/callback"
)

# GitHub API scopes
GITHUB_SCOPES = [
    "repo",
    "read:org",
    "user:email",
    "read:user",
    "notifications",
    "gist",
]

# CSRF protection
CSRF_TOKEN_SESSION_KEY = "github_auth_csrf_token"


@auth_github_bp.route("/api/auth/github/authorize", methods=["GET"])
def github_auth_initiate():
    """Initiate GitHub OAuth flow"""
    try:
        import secrets
        import urllib.parse

        user_id = request.args.get("user_id")
        if not user_id:
            return jsonify({"error": "user_id parameter is required"}), 400

        # Generate CSRF token
        csrf_token = secrets.token_urlsafe(32)
        session[CSRF_TOKEN_SESSION_KEY] = csrf_token
        session["github_auth_user_id"] = user_id

        # Build authorization URL
        auth_params = {
            "client_id": GITHUB_CLIENT_ID,
            "redirect_uri": GITHUB_REDIRECT_URI,
            "scope": " ".join(GITHUB_SCOPES),
            "state": csrf_token,
            "allow_signup": "false",
        }

        auth_url = f"https://github.com/login/oauth/authorize?{urllib.parse.urlencode(auth_params)}"

        logger.info(f"GitHub OAuth initiated for user {user_id}")
        return jsonify(
            {"auth_url": auth_url, "user_id": user_id, "csrf_token": csrf_token}
        )

    except Exception as e:
        logger.error(f"GitHub OAuth initiation failed: {e}")
        return jsonify({"error": f"OAuth initiation failed: {str(e)}"}), 500


@auth_github_bp.route("/api/auth/github/callback", methods=["GET"])
async def github_auth_callback():
    """Handle GitHub OAuth callback"""
    try:
        from flask import current_app
        import requests
        import urllib.parse

        # Get database connection
        db_conn_pool = getattr(current_app, "db_pool", None) or current_app.config.get("DB_CONNECTION_POOL", None)
        if not db_conn_pool:
            return "Error: Database connection pool is not available.", 500

        user_id = session.get("github_auth_user_id")
        if not user_id:
            return (
                "Error: No user_id found in session. Please try the connection process again.",
                400,
            )

        state = session.pop(CSRF_TOKEN_SESSION_KEY, None)
        code = request.args.get("code")
        error = request.args.get("error")

        if error:
            logger.error(f"GitHub OAuth callback error: {error}")
            return f"OAuth error: {error}", 400

        if not code:
            return "Error: No authorization code received.", 400

        if not state or state != request.args.get("state"):
            return (
                "Error: Invalid CSRF token. Please try the connection process again.",
                400,
            )

        # Exchange authorization code for tokens
        token_url = "https://github.com/login/oauth/access_token"
        token_data = {
            "client_id": GITHUB_CLIENT_ID,
            "client_secret": GITHUB_CLIENT_SECRET,
            "code": code,
            "redirect_uri": GITHUB_REDIRECT_URI,
        }

        token_headers = {
            "Accept": "application/json",
        }

        token_response = requests.post(
            token_url, data=token_data, headers=token_headers
        )
        token_data = token_response.json()

        if token_response.status_code != 200:
            logger.error(f"GitHub token exchange failed: {token_data}")
            return (
                f"Token exchange failed: {token_data.get('error_description', 'Unknown error')}",
                400,
            )

        access_token = token_data["access_token"]
        refresh_token = token_data.get("refresh_token")
        expires_in = token_data.get("expires_in", 28800)  # 8 hours default

        # Calculate expiration time
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

        # Store tokens in database
        try:
            from db_oauth_gdrive import store_tokens

            await store_tokens(
                db_conn_pool=db_conn_pool,
                user_id=user_id,
                service_name="github",
                access_token=access_token,
                refresh_token=refresh_token,
                expires_at=expires_at,
                scope=" ".join(GITHUB_SCOPES),
            )

            logger.info(f"GitHub OAuth completed successfully for user {user_id}")

            # Redirect to success page
            success_url = f"/settings?service=github&status=connected"
            return redirect(success_url)

        except Exception as db_error:
            logger.error(f"Failed to store GitHub tokens: {db_error}")
            return "Error: Failed to store authentication tokens.", 500

    except Exception as e:
        logger.error(f"GitHub OAuth callback failed: {e}")
        return f"OAuth callback failed: {str(e)}", 500


@auth_github_bp.route("/api/auth/github/refresh", methods=["POST"])
async def refresh_github_token():
    """Refresh GitHub access token"""
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
            tokens = await get_tokens(db_conn_pool, user_id, "github")
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

            # Refresh token (GitHub doesn't support refresh tokens for most OAuth flows)
            # For now, we'll return an error since GitHub typically doesn't issue refresh tokens
            return jsonify(
                {
                    "ok": False,
                    "error": {
                        "code": "REFRESH_NOT_SUPPORTED",
                        "message": "GitHub OAuth does not support token refresh for this flow. Re-authentication required.",
                    },
                }
            ), 400

        except Exception as token_error:
            logger.error(f"GitHub token refresh failed: {token_error}")
            return jsonify(
                {
                    "ok": False,
                    "error": {"code": "REFRESH_ERROR", "message": str(token_error)},
                }
            ), 500

    except Exception as e:
        logger.error(f"GitHub token refresh endpoint failed: {e}")
        return jsonify(
            {"ok": False, "error": {"code": "SERVER_ERROR", "message": str(e)}}
        ), 500


@auth_github_bp.route("/api/auth/github/disconnect", methods=["POST"])
async def github_auth_disconnect():
    """Disconnect GitHub integration"""
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
            await delete_tokens(db_conn_pool, user_id, "github")

            logger.info(f"GitHub integration disconnected for user {user_id}")
            return jsonify(
                {"ok": True, "message": "GitHub integration disconnected successfully"}
            )

        except Exception as db_error:
            logger.error(f"Failed to disconnect GitHub: {db_error}")
            return jsonify(
                {
                    "ok": False,
                    "error": {"code": "DISCONNECT_ERROR", "message": str(db_error)},
                }
            ), 500

    except Exception as e:
        logger.error(f"GitHub disconnect endpoint failed: {e}")
        return jsonify(
            {"ok": False, "error": {"code": "SERVER_ERROR", "message": str(e)}}
        ), 500


@auth_github_bp.route("/api/auth/github/status", methods=["GET"])
async def github_auth_status():
    """Get GitHub OAuth status"""
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

            tokens = await get_tokens(db_conn_pool, user_id, "github")
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
            logger.error(f"Failed to get GitHub status: {db_error}")
            return jsonify(
                {
                    "ok": False,
                    "error": {"code": "STATUS_ERROR", "message": str(db_error)},
                }
            ), 500

    except Exception as e:
        logger.error(f"GitHub status endpoint failed: {e}")
        return jsonify(
            {"ok": False, "error": {"code": "SERVER_ERROR", "message": str(e)}}
        ), 500


# Mock implementation for development/testing
class MockGitHubService:
    def __init__(self):
        self.connected = False

    def connect(self, access_token):
        self.connected = True
        return True

    def get_repositories(self, limit=10):
        if not self.connected:
            return []

        return [
            {
                "id": i,
                "name": f"mock-repo-{i}",
                "full_name": f"user/mock-repo-{i}",
                "description": f"This is a mock repository {i}",
                "html_url": f"https://github.com/user/mock-repo-{i}",
                "updated_at": datetime.now().isoformat(),
            }
            for i in range(limit)
        ]


# For local testing
if __name__ == "__main__":
    print("GitHub OAuth Handler - Testing mode")
    print(f"Client ID: {GITHUB_CLIENT_ID}")
    print(f"Redirect URI: {GITHUB_REDIRECT_URI}")
    print(f"Scopes: {GITHUB_SCOPES}")
