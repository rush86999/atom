import os
import logging
from flask import Blueprint, request, redirect, session, jsonify, url_for
from requests_oauthlib import OAuth1Session

logger = logging.getLogger(__name__)

trello_auth_bp = Blueprint('trello_auth_bp', __name__)

TRELLO_API_KEY = os.getenv("TRELLO_API_KEY")
TRELLO_API_SECRET = os.getenv("TRELLO_API_SECRET")
FRONTEND_REDIRECT_URL = os.getenv("APP_CLIENT_URL", "http://localhost:3000") + "/settings"

REQUEST_TOKEN_URL = "https://trello.com/1/OAuthGetRequestToken"
AUTHORIZE_URL = "https://trello.com/1/OAuthAuthorizeToken"
ACCESS_TOKEN_URL = "https://trello.com/1/OAuthGetAccessToken"

@trello_auth_bp.route('/api/auth/trello/initiate')
def initiate_trello_auth():
    if not TRELLO_API_KEY or not TRELLO_API_SECRET:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Trello integration is not configured correctly on the server."}}), 500

    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id is required."}}), 400

    session['trello_auth_user_id'] = user_id

    try:
        oauth = OAuth1Session(TRELLO_API_KEY, client_secret=TRELLO_API_SECRET, callback_uri=url_for('trello_auth_bp.oauth1callback', _external=True))
        fetch_response = oauth.fetch_request_token(REQUEST_TOKEN_URL)
        session['trello_request_token'] = fetch_response
        authorization_url = oauth.authorization_url(AUTHORIZE_URL)
        return redirect(authorization_url)
    except Exception as e:
        logger.error(f"Error initiating Trello auth for user {user_id}: {e}", exc_info=True)
        return "Error initiating Trello auth.", 500

@trello_auth_bp.route('/api/auth/trello/callback')
async def oauth1callback():
    from flask import current_app
    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL', None)
    if not db_conn_pool:
         return "Error: Database connection pool is not available.", 500

    user_id = session.get('trello_auth_user_id')
    if not user_id:
        return "Error: No user_id found in session. Please try the connection process again.", 400

    request_token = session.pop('trello_request_token', None)
    if not request_token:
        return "Error: No request token found in session.", 400

    try:
        oauth = OAuth1Session(TRELLO_API_KEY, client_secret=TRELLO_API_SECRET,
                              resource_owner_key=request_token['oauth_token'],
                              resource_owner_secret=request_token['oauth_token_secret'],
                              verifier=request.args.get('oauth_verifier'))

        access_token_data = oauth.fetch_access_token(ACCESS_TOKEN_URL)

        access_token = access_token_data.get('oauth_token')
        access_token_secret = access_token_data.get('oauth_token_secret')

        from . import crypto_utils, db_oauth_trello
        encrypted_access_token = crypto_utils.encrypt_message(access_token)
        encrypted_refresh_token = crypto_utils.encrypt_message(access_token_secret) # Storing secret as refresh token

        await db_oauth_trello.save_tokens(
            db_conn_pool=db_conn_pool,
            user_id=user_id,
            encrypted_access_token=encrypted_access_token,
            encrypted_refresh_token=encrypted_refresh_token,
            expires_at=None,
            scope=""
        )

        logger.info(f"Successfully completed Trello OAuth and saved tokens for user {user_id}.")
        return redirect(f"{FRONTEND_REDIRECT_URL}?trello_status=success")

    except Exception as e:
        logger.error(f"An unexpected error occurred during Trello OAuth callback for user {user_id}: {e}", exc_info=True)
        return "An unexpected server error occurred.", 500
    finally:
        session.pop('trello_auth_user_id', None)
