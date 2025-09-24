import os
import logging
from flask import Blueprint, request, redirect, session, jsonify, url_for
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
import requests
from box_sdk_gen import OAuthConfig, BoxOAuth

logger = logging.getLogger(__name__)

box_auth_bp = Blueprint('box_auth_bp', __name__)

BOX_CLIENT_ID = os.getenv("BOX_CLIENT_ID")
BOX_CLIENT_SECRET = os.getenv("BOX_CLIENT_SECRET")
CSRF_TOKEN_SESSION_KEY = 'box-auth-csrf-token'
FRONTEND_REDIRECT_URL = os.getenv("APP_CLIENT_URL", "http://localhost:3000") + "/settings"

# Box OAuth2 endpoints
BOX_AUTHORIZE_URL = "https://account.box.com/api/oauth2/authorize"
BOX_TOKEN_URL = "https://api.box.com/oauth2/token"

def get_box_oauth_config():
    """Get Box OAuth configuration"""
    return OAuthConfig(
        client_id=BOX_CLIENT_ID,
        client_secret=BOX_CLIENT_SECRET
    )

@box_auth_bp.route('/api/auth/box/initiate')
def initiate_box_auth():
    """Initiate Box OAuth2 flow"""
    if not BOX_CLIENT_ID or not BOX_CLIENT_SECRET:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Box integration is not configured correctly on the server."}}), 500

    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id is required."}}), 400

    session['box_auth_user_id'] = user_id

    # Generate state parameter for CSRF protection
    import secrets
    csrf_token = secrets.token_urlsafe(32)
    session[CSRF_TOKEN_SESSION_KEY] = csrf_token

    # Build authorization URL
    auth_params = {
        'response_type': 'code',
        'client_id': BOX_CLIENT_ID,
        'redirect_uri': url_for('box_auth_bp.oauth2callback', _external=True),
        'state': csrf_token
    }

    auth_url = f"{BOX_AUTHORIZE_URL}?{urlencode(auth_params)}"

    logger.info(f"Initiating Box auth for user {user_id}. Redirecting to Box.")
    return redirect(auth_url)

@box_auth_bp.route('/api/auth/box/callback')
async def oauth2callback():
    """Handle Box OAuth2 callback"""
    from flask import current_app
    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL', None)
    if not db_conn_pool:
         return "Error: Database connection pool is not available.", 500

    user_id = session.get('box_auth_user_id')
    if not user_id:
        return "Error: No user_id found in session. Please try the connection process again.", 400

    csrf_token = session.pop(CSRF_TOKEN_SESSION_KEY, None)
    if not csrf_token or csrf_token != request.args.get('state'):
        return "Error: CSRF token mismatch. Authorization denied.", 403

    authorization_code = request.args.get('code')
    if not authorization_code:
        return "Error: No authorization code received from Box.", 400

    try:
        # Exchange authorization code for access token
        token_data = {
            'grant_type': 'authorization_code',
            'code': authorization_code,
            'client_id': BOX_CLIENT_ID,
            'client_secret': BOX_CLIENT_SECRET,
            'redirect_uri': url_for('box_auth_bp.oauth2callback', _external=True)
        }

        response = requests.post(BOX_TOKEN_URL, data=token_data)
        response.raise_for_status()

        token_response = response.json()
        access_token = token_response['access_token']
        refresh_token = token_response.get('refresh_token')
        expires_in = token_response.get('expires_in', 3600)

        # Calculate expiration time
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

        import crypto_utils, db_oauth_box
        encrypted_access_token = crypto_utils.encrypt_message(access_token)
        encrypted_refresh_token = crypto_utils.encrypt_message(refresh_token) if refresh_token else None

        await db_oauth_box.save_tokens(
            db_conn_pool=db_conn_pool,
            user_id=user_id,
            encrypted_access_token=encrypted_access_token,
            encrypted_refresh_token=encrypted_refresh_token,
            expires_at=expires_at,
            scope=token_response.get('scope', '')
        )

        logger.info(f"Successfully completed Box OAuth and saved tokens for user {user_id}.")
        return redirect(f"{FRONTEND_REDIRECT_URL}?box_status=success")

    except requests.exceptions.RequestException as e:
        logger.error(f"Box OAuth token exchange failed for user {user_id}: {e}", exc_info=True)
        return "Error: Failed to exchange authorization code for access token.", 500
    except Exception as e:
        logger.error(f"An unexpected error occurred during Box OAuth callback for user {user_id}: {e}", exc_info=True)
        return "An unexpected server error occurred.", 500
    finally:
        session.pop('box_auth_user_id', None)

@box_auth_bp.route('/api/auth/box/refresh', methods=['POST'])
async def refresh_box_token():
    """Refresh Box access token using refresh token"""
    from flask import current_app
    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL', None)
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection pool is not available."}}), 500

    data = request.get_json()
    user_id = data.get('user_id')
    if not user_id:
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id is required."}}), 400

    try:
        # Get current tokens from database
        tokens = await db_oauth_box.get_tokens(db_conn_pool, user_id)
        if not tokens or not tokens[1]:  # tokens[1] is refresh token
            return jsonify({"ok": False, "error": {"code": "AUTH_ERROR", "message": "No refresh token available for user."}}), 401

        refresh_token = crypto_utils.decrypt_message(tokens[1])

        # Refresh the token
        refresh_data = {
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token,
            'client_id': BOX_CLIENT_ID,
            'client_secret': BOX_CLIENT_SECRET
        }

        response = requests.post(BOX_TOKEN_URL, data=refresh_data)
        response.raise_for_status()

        token_response = response.json()
        new_access_token = token_response['access_token']
        new_refresh_token = token_response.get('refresh_token', refresh_token)  # Use new refresh token if provided, else keep old
        expires_in = token_response.get('expires_in', 3600)

        # Calculate new expiration time
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

        import crypto_utils
        encrypted_access_token = crypto_utils.encrypt_message(new_access_token)
        encrypted_refresh_token = crypto_utils.encrypt_message(new_refresh_token)

        await db_oauth_box.save_tokens(
            db_conn_pool=db_conn_pool,
            user_id=user_id,
            encrypted_access_token=encrypted_access_token,
            encrypted_refresh_token=encrypted_refresh_token,
            expires_at=expires_at,
            scope=token_response.get('scope', '')
        )

        return jsonify({
            "ok": True,
            "message": "Token refreshed successfully",
            "expires_at": expires_at.isoformat()
        })

    except requests.exceptions.RequestException as e:
        logger.error(f"Box token refresh failed for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "REFRESH_FAILED", "message": "Failed to refresh access token."}}), 500
    except Exception as e:
        logger.error(f"An unexpected error occurred during Box token refresh for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "SERVER_ERROR", "message": "An unexpected server error occurred."}}), 500
