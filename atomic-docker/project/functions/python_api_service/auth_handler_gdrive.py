import os
import logging
from flask import Blueprint, request, redirect, url_for, session, current_app
from google_auth_oauthlib.flow import Flow
from .db_oauth_gdrive import save_token
from .crypto_utils import encrypt_token

logger = logging.getLogger(__name__)

gdrive_auth_bp = Blueprint('gdrive_auth_bp', __name__)

# Ensure you have these environment variables set
# GOOGLE_CLIENT_SECRETS_FILE: Path to your client_secret.json
# FLASK_SECRET_KEY: A secret key for Flask session management
# BASE_URL: The base URL of your application (e.g., http://localhost:5058)

@gdrive_auth_bp.route('/api/auth/gdrive/authorize')
def authorize():
    """
    Starts the Google Drive OAuth 2.0 authorization flow.
    """
    user_id = request.args.get('user_id')
    if not user_id:
        return "User ID is required.", 400

    session['gdrive_oauth_user_id'] = user_id

    flow = Flow.from_client_secrets_file(
        os.environ.get("GOOGLE_CLIENT_SECRETS_FILE"),
        scopes=['https://www.googleapis.com/auth/drive.readonly'],
        redirect_uri=url_for('gdrive_auth_bp.oauth2callback', _external=True)
    )

    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true'
    )
    session['gdrive_oauth_state'] = state

    return redirect(authorization_url)

@gdrive_auth_bp.route('/api/auth/gdrive/oauth2callback')
async def oauth2callback():
    """
    Handles the OAuth 2.0 callback from Google.
    """
    state = session.get('gdrive_oauth_state')
    if not state or state != request.args.get('state'):
        return "State mismatch error.", 400

    user_id = session.get('gdrive_oauth_user_id')
    if not user_id:
        return "User ID not found in session.", 400

    flow = Flow.from_client_secrets_file(
        os.environ.get("GOOGLE_CLIENT_SECRETS_FILE"),
        scopes=['https://www.googleapis.com/auth/drive.readonly'],
        state=state,
        redirect_uri=url_for('gdrive_auth_bp.oauth2callback', _external=True)
    )

    flow.fetch_token(authorization_response=request.url)

    credentials = flow.credentials

    # Convert credentials to a JSON string for storing
    creds_json = credentials.to_json()

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return "Database connection not available.", 500

    try:
        await save_token(db_conn_pool, user_id, creds_json)
        return "Google Drive account connected successfully!", 200
    except Exception as e:
        logger.error(f"Failed to save Google Drive token for user {user_id}: {e}", exc_info=True)
        return "Failed to save token.", 500
