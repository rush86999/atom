import os
import logging
from flask import Blueprint, request, redirect, session, jsonify, url_for
from datetime import datetime, timedelta, timezone
from boxsdk import OAuth2

logger = logging.getLogger(__name__)

box_auth_bp = Blueprint('box_auth_bp', __name__)

BOX_CLIENT_ID = os.getenv("BOX_CLIENT_ID")
BOX_CLIENT_SECRET = os.getenv("BOX_CLIENT_SECRET")
CSRF_TOKEN_SESSION_KEY = 'box-auth-csrf-token'
FRONTEND_REDIRECT_URL = os.getenv("APP_CLIENT_URL", "http://localhost:3000") + "/settings"

def get_box_oauth_flow():
    return OAuth2(
        client_id=BOX_CLIENT_ID,
        client_secret=BOX_CLIENT_SECRET,
        store_tokens=None,
    )

@box_auth_bp.route('/api/auth/box/initiate')
def initiate_box_auth():
    if not BOX_CLIENT_ID or not BOX_CLIENT_SECRET:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Box integration is not configured correctly on the server."}}), 500

    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id is required."}}), 400

    session['box_auth_user_id'] = user_id

    oauth = get_box_oauth_flow()
    auth_url, csrf_token = oauth.get_authorization_url(url_for('box_auth_bp.oauth2callback', _external=True))
    session[CSRF_TOKEN_SESSION_KEY] = csrf_token

    logger.info(f"Initiating Box auth for user {user_id}. Redirecting to Box.")
    return redirect(auth_url)

@box_auth_bp.route('/api/auth/box/callback')
async def oauth2callback():
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

    try:
        oauth = get_box_oauth_flow()
        access_token, refresh_token = oauth.authenticate(request.args.get('code'))

        # For Box, the token object itself doesn't have expiry, but you can calculate it.
        # This is a simplified example.
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

        from . import crypto_utils, db_oauth_box
        encrypted_access_token = crypto_utils.encrypt_message(access_token)
        encrypted_refresh_token = crypto_utils.encrypt_message(refresh_token) if refresh_token else None

        await db_oauth_box.save_tokens(
            db_conn_pool=db_conn_pool,
            user_id=user_id,
            encrypted_access_token=encrypted_access_token,
            encrypted_refresh_token=encrypted_refresh_token,
            expires_at=expires_at,
            scope="" # Box SDK doesn't readily provide scope in the response
        )

        logger.info(f"Successfully completed Box OAuth and saved tokens for user {user_id}.")
        return redirect(f"{FRONTEND_REDIRECT_URL}?box_status=success")

    except Exception as e:
        logger.error(f"An unexpected error occurred during Box OAuth callback for user {user_id}: {e}", exc_info=True)
        return "An unexpected server error occurred.", 500
    finally:
        session.pop('box_auth_user_id', None)
