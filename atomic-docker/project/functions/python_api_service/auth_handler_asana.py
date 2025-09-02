import os
import logging
from flask import Blueprint, request, redirect, session, jsonify, url_for
from datetime import datetime, timedelta, timezone
import requests

logger = logging.getLogger(__name__)

asana_auth_bp = Blueprint('asana_auth_bp', __name__)

ASANA_CLIENT_ID = os.getenv("ASANA_CLIENT_ID")
ASANA_CLIENT_SECRET = os.getenv("ASANA_CLIENT_SECRET")
CSRF_TOKEN_SESSION_KEY = 'asana-auth-csrf-token'
FRONTEND_REDIRECT_URL = os.getenv("APP_CLIENT_URL", "http://localhost:3000") + "/settings"

def get_asana_auth_url():
    redirect_uri = url_for('asana_auth_bp.oauth2callback', _external=True)
    state = os.urandom(16).hex()
    session[CSRF_TOKEN_SESSION_KEY] = state
    return (f"https://app.asana.com/-/oauth_authorize?client_id={ASANA_CLIENT_ID}"
            f"&redirect_uri={redirect_uri}&response_type=code&state={state}"
            "&scope=default")

@asana_auth_bp.route('/api/auth/asana/initiate')
def initiate_asana_auth():
    if not ASANA_CLIENT_ID or not ASANA_CLIENT_SECRET:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Asana integration is not configured correctly on the server."}}), 500

    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id is required."}}), 400

    session['asana_auth_user_id'] = user_id
    auth_url = get_asana_auth_url()

    logger.info(f"Initiating Asana auth for user {user_id}. Redirecting to Asana.")
    return redirect(auth_url)

@asana_auth_bp.route('/api/auth/asana/callback')
async def oauth2callback():
    from flask import current_app
    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL', None)
    if not db_conn_pool:
         return "Error: Database connection pool is not available.", 500

    user_id = session.get('asana_auth_user_id')
    if not user_id:
        return "Error: No user_id found in session. Please try the connection process again.", 400

    state = session.pop(CSRF_TOKEN_SESSION_KEY, None)
    if not state or state != request.args.get('state'):
        return "Error: CSRF token mismatch. Authorization denied.", 403

    code = request.args.get('code')
    if not code:
        return "Error: No authorization code provided.", 400

    try:
        token_url = "https://app.asana.com/-/oauth_token"
        redirect_uri = url_for('asana_auth_bp.oauth2callback', _external=True)
        payload = {
            'grant_type': 'authorization_code',
            'client_id': ASANA_CLIENT_ID,
            'client_secret': ASANA_CLIENT_SECRET,
            'redirect_uri': redirect_uri,
            'code': code
        }
        response = requests.post(token_url, data=payload)
        response.raise_for_status()
        token_data = response.json()

        access_token = token_data['access_token']
        refresh_token = token_data.get('refresh_token')
        expires_in = token_data.get('expires_in')
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in) if expires_in else None

        from . import crypto_utils, db_oauth_asana
        encrypted_access_token = crypto_utils.encrypt_message(access_token)
        encrypted_refresh_token = crypto_utils.encrypt_message(refresh_token) if refresh_token else None

        await db_oauth_asana.save_tokens(
            db_conn_pool=db_conn_pool,
            user_id=user_id,
            encrypted_access_token=encrypted_access_token,
            encrypted_refresh_token=encrypted_refresh_token,
            expires_at=expires_at,
            scope="" # Asana doesn't provide scope in the response
        )

        logger.info(f"Successfully completed Asana OAuth and saved tokens for user {user_id}.")
        return redirect(f"{FRONTEND_REDIRECT_URL}?asana_status=success")

    except Exception as e:
        logger.error(f"An unexpected error occurred during Asana OAuth callback for user {user_id}: {e}", exc_info=True)
        return "An unexpected server error occurred.", 500
    finally:
        session.pop('asana_auth_user_id', None)
