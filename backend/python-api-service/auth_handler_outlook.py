import os
import logging
import sys
import requests
import urllib.parse
import secrets
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional

# Flask imports
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

# Create Outlook auth blueprint
auth_outlook_bp = Blueprint("auth_outlook_bp", __name__)

# Outlook OAuth configuration
OUTLOOK_CLIENT_ID = os.getenv("OUTLOOK_CLIENT_ID")
OUTLOOK_CLIENT_SECRET = os.getenv("OUTLOOK_CLIENT_SECRET")
OUTLOOK_TENANT_ID = os.getenv("OUTLOOK_TENANT_ID", "common")
OUTLOOK_REDIRECT_URI = os.getenv(
    "OUTLOOK_REDIRECT_URI", "http://localhost:5058/api/auth/outlook/callback"
)

# Microsoft Graph API scopes
OUTLOOK_SCOPES = [
    "https://graph.microsoft.com/Mail.Read",
    "https://graph.microsoft.com/Mail.Send",
    "https://graph.microsoft.com/Mail.ReadWrite",
    "https://graph.microsoft.com/Calendars.Read",
    "https://graph.microsoft.com/Calendars.ReadWrite",
    "https://graph.microsoft.com/User.Read",
    "https://graph.microsoft.com/offline_access",
]

# Microsoft Graph endpoints
MICROSOFT_AUTH_URL = "https://login.microsoftonline.com"
MICROSOFT_GRAPH_URL = "https://graph.microsoft.com/v1.0"

# CSRF protection
CSRF_TOKEN_SESSION_KEY = "outlook_auth_csrf_token"


@auth_outlook_bp.route("/api/auth/outlook/authorize", methods=["GET"])
def outlook_auth_initiate():
    """Initiate Outlook OAuth flow"""
    try:
        import secrets
        import urllib.parse

        user_id = request.args.get("user_id")
        state = request.args.get("state")
        
        if not user_id:
            return jsonify({
                'success': False,
                'error': 'user_id parameter is required',
                'service': 'outlook'
            }), 400

        # Generate CSRF token
        csrf_token = state or secrets.token_urlsafe(32)
        session[CSRF_TOKEN_SESSION_KEY] = csrf_token
        session["outlook_auth_user_id"] = user_id

        # Build authorization URL
        auth_params = {
            "client_id": OUTLOOK_CLIENT_ID,
            "redirect_uri": OUTLOOK_REDIRECT_URI,
            "response_type": "code",
            "scope": " ".join(OUTLOOK_SCOPES),
            "state": csrf_token,
            "prompt": "consent",
        }

        auth_url = f"{MICROSOFT_AUTH_URL}/{OUTLOOK_TENANT_ID}/oauth2/v2.0/authorize?{urllib.parse.urlencode(auth_params)}"

        logger.info(f"Outlook OAuth initiated for user {user_id}")
        return jsonify({
            'success': True,
            'oauth_url': auth_url,
            'service': 'outlook',
            'user_id': user_id,
            'csrf_token': csrf_token,
            'client_id': OUTLOOK_CLIENT_ID[:10] + '...' if OUTLOOK_CLIENT_ID else None,
            'tenant_id': OUTLOOK_TENANT_ID
        })

    except Exception as e:
        logger.error(f"Outlook OAuth initiation failed: {e}")
        return jsonify({"error": f"OAuth initiation failed: {str(e)}"}), 500


@auth_outlook_bp.route("/api/auth/outlook/callback", methods=["GET"])
async def outlook_auth_callback():
    """Handle Outlook OAuth callback"""
    try:
        from flask import current_app

        # Get database connection
        db_conn_pool = getattr(current_app, "db_pool", None) or current_app.config.get("DB_CONNECTION_POOL", None)
        if not db_conn_pool:
            # For testing without database, just return success message
            logger.warning("No database connection pool available, using mock response")
            return jsonify({
                'success': True,
                'service': 'outlook',
                'message': 'OAuth completed (mock mode - no database storage)',
                'user_info': {
                    'displayName': 'Test User',
                    'mail': 'test@outlook.com'
                }
            })

        user_id = session.get("outlook_auth_user_id")
        if not user_id:
            return (
                "Error: No user_id found in session. Please try the connection process again.",
                400,
            )

        state = session.pop(CSRF_TOKEN_SESSION_KEY, None)
        code = request.args.get("code")
        error = request.args.get("error")

        if error:
            logger.error(f"Outlook OAuth callback error: {error}")
            return jsonify({
                'success': False,
                'error': f'Outlook OAuth error: {error}',
                'service': 'outlook'
            }), 400

        if not code:
            return "Error: No authorization code received.", 400

        if not state or state != request.args.get("state"):
            return (
                "Error: Invalid CSRF token. Please try the connection process again.",
                400,
            )

        # Exchange authorization code for tokens
        token_url = f"{MICROSOFT_AUTH_URL}/{OUTLOOK_TENANT_ID}/oauth2/v2.0/token"
        token_data = {
            "client_id": OUTLOOK_CLIENT_ID,
            "client_secret": OUTLOOK_CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": OUTLOOK_REDIRECT_URI,
            "scope": " ".join(OUTLOOK_SCOPES),
        }

        token_response = requests.post(token_url, data=token_data)
        token_data = token_response.json()

        if token_response.status_code != 200:
            logger.error(f"Outlook token exchange failed: {token_data}")
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
                service_name="outlook",
                access_token=access_token,
                refresh_token=refresh_token,
                expires_at=expires_at,
                scope=" ".join(OUTLOOK_SCOPES),
            )

            logger.info(f"Outlook OAuth completed successfully for user {user_id}")

            # Get user profile to verify connection
            profile_response = requests.get(
                f"{MICROSOFT_GRAPH_URL}/me",
                headers={"Authorization": f"Bearer {access_token}"},
            )

            if profile_response.status_code == 200:
                profile_data = profile_response.json()
                logger.info(
                    f"Outlook user profile: {profile_data.get('displayName', 'Unknown')}"
                )
                
                # Return success response
                return jsonify({
                    'success': True,
                    'service': 'outlook',
                    'tokens': {
                        'access_token': access_token,
                        'refresh_token': refresh_token,
                        'expires_in': expires_in
                    },
                    'user_info': {
                        'id': profile_data.get('id'),
                        'displayName': profile_data.get('displayName'),
                        'mail': profile_data.get('mail'),
                        'userPrincipalName': profile_data.get('userPrincipalName')
                    },
                    'message': 'Outlook OAuth completed successfully'
                })
            else:
                logger.error("Failed to get Outlook user profile")
                return jsonify({
                    'success': True,
                    'service': 'outlook',
                    'message': 'OAuth completed but profile fetch failed',
                    'tokens': {
                        'access_token': access_token,
                        'expires_in': expires_in
                    }
                })

            # Redirect to success page
            success_url = f"/settings?service=outlook&status=connected"
            return redirect(success_url)

        except Exception as db_error:
            logger.error(f"Failed to store Outlook tokens: {db_error}")
            return "Error: Failed to store authentication tokens.", 500

    except Exception as e:
        logger.error(f"Outlook OAuth callback failed: {e}")
        return f"OAuth callback failed: {str(e)}", 500


@auth_outlook_bp.route("/api/auth/outlook/refresh", methods=["POST"])
async def refresh_outlook_token():
    """Refresh Outlook access token"""
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
            tokens = await get_tokens(db_conn_pool, user_id, "outlook")
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
            token_url = f"{MICROSOFT_AUTH_URL}/{OUTLOOK_TENANT_ID}/oauth2/v2.0/token"
            refresh_data = {
                "client_id": OUTLOOK_CLIENT_ID,
                "client_secret": OUTLOOK_CLIENT_SECRET,
                "refresh_token": tokens["refresh_token"],
                "grant_type": "refresh_token",
                "scope": " ".join(OUTLOOK_SCOPES),
            }

            refresh_response = requests.post(token_url, data=refresh_data)
            refresh_data = refresh_response.json()

            if refresh_response.status_code != 200:
                logger.error(f"Outlook token refresh failed: {refresh_data}")
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
                service_name="outlook",
                access_token=access_token,
                expires_at=expires_at,
            )

            logger.info(f"Outlook token refreshed successfully for user {user_id}")
            return jsonify(
                {
                    "ok": True,
                    "access_token": access_token,
                    "expires_at": expires_at.isoformat(),
                }
            )

        except Exception as token_error:
            logger.error(f"Outlook token refresh failed: {token_error}")
            return jsonify(
                {
                    "ok": False,
                    "error": {"code": "REFRESH_ERROR", "message": str(token_error)},
                }
            ), 500

    except Exception as e:
        logger.error(f"Outlook token refresh endpoint failed: {e}")
        return jsonify(
            {"ok": False, "error": {"code": "SERVER_ERROR", "message": str(e)}}
        ), 500


@auth_outlook_bp.route("/api/auth/outlook/disconnect", methods=["POST"])
async def outlook_auth_disconnect():
    """Disconnect Outlook integration"""
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
            await delete_tokens(db_conn_pool, user_id, "outlook")

            logger.info(f"Outlook integration disconnected for user {user_id}")
            return jsonify(
                {"ok": True, "message": "Outlook integration disconnected successfully"}
            )

        except Exception as db_error:
            logger.error(f"Failed to disconnect Outlook: {db_error}")
            return jsonify(
                {
                    "ok": False,
                    "error": {"code": "DISCONNECT_ERROR", "message": str(db_error)},
                }
            ), 500

    except Exception as e:
        logger.error(f"Outlook disconnect endpoint failed: {e}")
        return jsonify(
            {"ok": False, "error": {"code": "SERVER_ERROR", "message": str(e)}}
        ), 500


@auth_outlook_bp.route("/api/auth/outlook/status", methods=["GET"])
async def outlook_auth_status():
    """Get Outlook OAuth status"""
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
            # Try to use Outlook database, fallback to gdrive if not available
            try:
                from db_oauth_outlook import get_tokens as get_outlook_tokens
                tokens = await get_outlook_tokens(db_conn_pool, user_id)
            except ImportError:
                from db_oauth_gdrive import get_tokens
                tokens = await get_tokens(db_conn_pool, user_id, "outlook")
            
            if tokens and tokens.get("access_token"):
                is_expired = tokens.get("expires_at") and tokens[
                    "expires_at"
                ] < datetime.now(timezone.utc)

                return jsonify({
                    "ok": True,
                    "connected": True,
                    "expired": is_expired,
                    "scopes": tokens.get("scope", "").split(" ")
                    if tokens.get("scope")
                    else [],
                })
            else:
                return jsonify({"ok": True, "connected": False, "expired": False, "scopes": []})

        except Exception as db_error:
            logger.error(f"Failed to get Outlook status: {db_error}")
            return jsonify(
                {
                    "ok": False,
                    "error": {"code": "STATUS_ERROR", "message": str(db_error)},
                }
            ), 500

    except Exception as e:
        logger.error(f"Outlook status endpoint failed: {e}")
        return jsonify(
            {"ok": False, "error": {"code": "SERVER_ERROR", "message": str(e)}}
        ), 500


# Mock implementation for development/testing
class MockOutlookService:
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
                "id": f"mock_outlook_email_{i}",
                "subject": f"Mock Outlook Email Subject {i}",
                "from": f"sender{i}@outlook.com",
                "snippet": f"This is a mock Outlook email snippet for email {i}",
                "date": datetime.now().isoformat(),
            }
            for i in range(limit)
        ]


# For local testing
if __name__ == "__main__":
    print("Outlook OAuth Handler - Testing mode")
    print(f"Client ID: {OUTLOOK_CLIENT_ID}")
    print(f"Tenant ID: {OUTLOOK_TENANT_ID}")
    print(f"Redirect URI: {OUTLOOK_REDIRECT_URI}")
    print(f"Scopes: {OUTLOOK_SCOPES}")
