import os
import logging
from flask import Blueprint, request, redirect, session, jsonify, url_for
from datetime import datetime, timedelta, timezone

# Dropbox SDK
try:
    import dropbox
    from dropbox.oauth import DropboxOAuth2Flow, BadRequestException, BadStateException, CsrfException, NotApprovedException, ProviderException
    DROPBOX_SDK_AVAILABLE = True
except ImportError:
    DROPBOX_SDK_AVAILABLE = False
    # Define dummy exceptions for type hinting if SDK is not present
    class DropboxOAuth2Flow: pass
    class BadRequestException(Exception): pass
    class BadStateException(Exception): pass
    class CsrfException(Exception): pass
    class NotApprovedException(Exception): pass
    class ProviderException(Exception): pass

# Internal imports
try:
    from . import db_oauth_dropbox
    from . import crypto_utils
except ImportError:
    import db_oauth_dropbox
    import crypto_utils

logger = logging.getLogger(__name__)

# --- Blueprint Setup ---
dropbox_auth_bp = Blueprint('dropbox_auth_bp', __name__)

# --- Config / Constants ---
# These should be loaded from environment variables
DROPBOX_APP_KEY = os.getenv("DROPBOX_APP_KEY")
DROPBOX_APP_SECRET = os.getenv("DROPBOX_APP_SECRET")
# The session key for storing the CSRF token
CSRF_TOKEN_SESSION_KEY = 'dropbox-auth-csrf-token'
# The frontend URL to redirect to on success/failure
FRONTEND_REDIRECT_URL = os.getenv("APP_CLIENT_URL", "http://localhost:3000") + "/settings" # Example redirect to settings page


def get_dropbox_oauth_flow(session_obj):
    """Helper to construct the DropboxOAuth2Flow object."""
    # The redirect URI must be registered in your Dropbox App Console
    redirect_uri = url_for('dropbox_auth_bp.oauth2callback', _external=True)

    return DropboxOAuth2Flow(
        consumer_key=DROPBOX_APP_KEY,
        consumer_secret=DROPBOX_APP_SECRET,
        redirect_uri=redirect_uri,
        session=session_obj,
        csrf_token_session_key=CSRF_TOKEN_SESSION_KEY,
        use_pkce=True,
        token_access_type='offline',
        scope=[
            "account_info.read",
            "files.metadata.read",
            "files.content.read",
            # Add other scopes as needed, e.g., "files.content.write"
        ]
    )

@dropbox_auth_bp.route('/api/auth/dropbox/initiate')
def initiate_dropbox_auth():
    """Starts the Dropbox OAuth2 flow."""
    if not DROPBOX_SDK_AVAILABLE or not DROPBOX_APP_KEY or not DROPBOX_APP_SECRET:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Dropbox integration is not configured correctly on the server."}}), 500

    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id is required."}}), 400

    # The user_id needs to be stored in the session to be retrieved in the callback
    session['dropbox_auth_user_id'] = user_id

    auth_flow = get_dropbox_oauth_flow(session)
    authorize_url = auth_flow.start()

    logger.info(f"Initiating Dropbox auth for user {user_id}. Redirecting to Dropbox.")
    return redirect(authorize_url)


@dropbox_auth_bp.route('/api/auth/dropbox/callback')
async def oauth2callback():
    """Callback endpoint for Dropbox OAuth2 flow."""
    if not DROPBOX_SDK_AVAILABLE:
        return "Error: Dropbox integration is not configured on the server.", 500

    # Get the db_conn_pool from the app context if available
    # This assumes the main app initializes it and makes it available, e.g., via app.config or a global
    from flask import current_app
    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL', None)
    if not db_conn_pool:
         return "Error: Database connection pool is not available.", 500

    user_id = session.get('dropbox_auth_user_id')
    if not user_id:
        return "Error: No user_id found in session. Please try the connection process again.", 400

    auth_flow = get_dropbox_oauth_flow(session)

    try:
        # Finish the flow to get the tokens
        oauth_result = auth_flow.finish(request.args)

        access_token = oauth_result.access_token
        refresh_token = oauth_result.refresh_token
        # expires_in is in seconds
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=oauth_result.expires_in) if oauth_result.expires_in else None
        scope = oauth_result.scope

        # Encrypt tokens before storing
        encrypted_access_token = crypto_utils.encrypt_message(access_token)
        encrypted_refresh_token = crypto_utils.encrypt_message(refresh_token) if refresh_token else None

        # Save to database
        await db_oauth_dropbox.save_tokens(
            db_conn_pool=db_conn_pool,
            user_id=user_id,
            encrypted_access_token=encrypted_access_token,
            encrypted_refresh_token=encrypted_refresh_token,
            expires_at=expires_at,
            scope=scope
        )

        logger.info(f"Successfully completed Dropbox OAuth and saved tokens for user {user_id}.")
        # Redirect to a success page on the frontend
        return redirect(f"{FRONTEND_REDIRECT_URL}?dropbox_status=success")

    except BadRequestException as e:
        logger.error(f"Dropbox OAuth BadRequestException for user {user_id}: {e}")
        return "Error: Bad request during Dropbox OAuth callback.", 400
    except BadStateException as e:
        logger.error(f"Dropbox OAuth BadStateException for user {user_id}: {e}. Session might be expired.")
        # It's recommended to restart the flow
        return redirect(url_for('dropbox_auth_bp.initiate_dropbox_auth', user_id=user_id))
    except CsrfException as e:
        logger.error(f"Dropbox OAuth CsrfException for user {user_id}: {e}")
        return "Error: CSRF token mismatch. Authorization denied.", 403
    except NotApprovedException as e:
        logger.info(f"User {user_id} did not approve the Dropbox connection.")
        return redirect(f"{FRONTEND_REDIRECT_URL}?dropbox_status=denied")
    except ProviderException as e:
        logger.error(f"Dropbox OAuth ProviderException for user {user_id}: {e}")
        return f"Error from Dropbox: {e}", 500
    except Exception as e:
        logger.error(f"An unexpected error occurred during Dropbox OAuth callback for user {user_id}: {e}", exc_info=True)
        return "An unexpected server error occurred.", 500
    finally:
        # Clean up the session keys
        session.pop('dropbox-auth-csrf-token', None)
        session.pop('dropbox_auth_user_id', None)
