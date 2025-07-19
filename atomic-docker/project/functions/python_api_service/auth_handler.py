import os
import sys
import json
import requests
import logging
from datetime import datetime, timedelta, timezone
from flask import Blueprint, request, jsonify, redirect, current_app # Added current_app
from typing import Optional, Dict, Any

# --- Utility Imports ---
# Assuming these new files are in the same directory or python path is set correctly
try:
    from .crypto_utils import encrypt_data, decrypt_data, _initialize_cipher_suite as initialize_crypto
    CRYPTO_AVAILABLE = initialize_crypto() # Initialize cipher on module load
except ImportError as e_crypto:
    print(f"FATAL: Could not import crypto_utils or initialize cipher: {e_crypto}. OAuth token handling will fail.", file=sys.stderr)
    CRYPTO_AVAILABLE = False
    # Define dummy functions if crypto is not available to prevent NameError, but log critical issue
    def encrypt_data(data_str: str) -> Optional[str]: logger.critical("Crypto utils not loaded, encryption placeholder called."); return None
    def decrypt_data(encrypted_str: str) -> Optional[str]: logger.critical("Crypto utils not loaded, decryption placeholder called."); return None

try:
    from .db_oauth_gdrive import (
        save_or_update_gdrive_tokens,
        get_gdrive_oauth_details,
        update_gdrive_access_token,
        delete_gdrive_tokens # Added for disconnect
    )
    DB_UTILS_AVAILABLE = True
except ImportError as e_db:
    print(f"FATAL: Could not import db_oauth_gdrive: {e_db}. OAuth DB operations will fail.", file=sys.stderr)
    DB_UTILS_AVAILABLE = False
    # Define dummy functions
    def save_or_update_gdrive_tokens(*args, **kwargs) -> bool: logger.critical("DB utils not loaded, save_or_update_gdrive_tokens placeholder."); return False
    def get_gdrive_oauth_details(*args, **kwargs) -> Optional[Dict[str, Any]]: logger.critical("DB utils not loaded, get_gdrive_oauth_details placeholder."); return None
    def update_gdrive_access_token(*args, **kwargs) -> bool: logger.critical("DB utils not loaded, update_gdrive_access_token placeholder."); return False


# --- Flask Blueprint Setup ---
auth_bp = Blueprint('auth_api', __name__)
logger = logging.getLogger(__name__)
if not logger.hasHandlers(): # Ensure logger is configured
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# --- Conceptual DB Connection Pool ---
# In a real Flask app, this would be initialized with the app context.
# For psycopg2, this typically involves creating a connection pool when the app starts
# and making it accessible, often via `current_app.extensions` or a dedicated Flask extension.

# Attempt to import psycopg2 pool for type hinting, if available.
try:
    from psycopg2 import pool as psycopg2_pool
    PSYCOPG2_POOL_TYPE = psycopg2_pool.AbstractConnectionPool
except ImportError:
    PSYCOPG2_POOL_TYPE = Any # Fallback type if psycopg2 is not installed in this context

def get_db_connection_pool() -> Optional[PSYCOPG2_POOL_TYPE]:
    """
    Conceptual function to retrieve the database connection pool.
    In a real Flask application, the psycopg2 connection pool
    (e.g., `psycopg2.pool.SimpleConnectionPool` or `ThreadedConnectionPool`)
    should be initialized once when the Flask application starts, typically within
    the application factory function (often named `create_app`).

    The initialized pool is then made accessible to blueprints and request handlers,
    commonly by storing it in `current_app.extensions['db_pool']`. This `get_db_connection_pool`
    function is a utility to retrieve this pre-initialized pool.

    Database Connection Configuration:
    ----------------------------------
    The database connection string (DSN) or individual parameters (host, port, user,
    password, dbname) should be configured securely, typically via environment
    variables (e.g., `DATABASE_URL` for a DSN, or `DB_HOST`, `DB_USER`, etc.).
    NEVER hardcode credentials in the source code.

    Example Initialization in Flask App Factory (`create_app`):
    ----------------------------------------------------------
    ```python
    # In your main Flask app file (e.g., app.py or factory.py)
    import os
    import atexit
    from flask import Flask
    from psycopg2 import pool

    def create_app():
        app = Flask(__name__)

        # Configure database connection pool
        try:
            db_url = os.environ.get('DATABASE_URL')
            if not db_url:
                app.logger.critical("DATABASE_URL environment variable is not set. DB pool cannot be initialized.")
                # Decide handling: raise error, or let app run without DB (parts will fail)
                app.extensions['db_pool'] = None
            else:
                # minconn: Minimum number of connections to keep open in the pool.
                # maxconn: Maximum number of connections the pool can manage.
                # Adjust these based on expected load and database server capacity.
                app.extensions['db_pool'] = pool.SimpleConnectionPool(
                    minconn=1,
                    maxconn=10,
                    dsn=db_url  # Example DSN: "postgresql://user:password@host:port/dbname"
                )
                app.logger.info("Database connection pool initialized successfully.")

                # Register a function to close the pool when the application exits
                @app.teardown_appcontext
                def close_pool_on_teardown(exception=None):
                    # This is for connections used within a request context.
                    # For the pool itself, atexit is more robust for app shutdown.
                    pass

                # More robust pool closing on app exit:
                def close_db_pool_on_exit():
                    db_pool_instance = app.extensions.get('db_pool')
                    if db_pool_instance:
                        app.logger.info("Closing database connection pool.")
                        db_pool_instance.closeall()
                atexit.register(close_db_pool_on_exit)

        except (pool.PoolError, KeyError, ValueError) as e:
            app.logger.critical(f"Failed to initialize database connection pool: {e}", exc_info=True)
            app.extensions['db_pool'] = None # Ensure it's None on failure

        # ... other app configurations (blueprints, etc.) ...
        # from .python_api_service.auth_handler import auth_bp # Example blueprint
        # app.register_blueprint(auth_bp)

        return app
    ```
    ----------------------------------------------------------
    This function (`get_db_connection_pool`) then simply retrieves this pool.
    """
    if not hasattr(current_app, 'extensions') or 'db_pool' not in current_app.extensions:
        logger.warning(
            "Database connection pool ('db_pool') not found in current_app.extensions. "
            "Database operations in db_oauth_gdrive.py will likely fail or use placeholders if psycopg2 is unavailable. "
            "Ensure the pool is initialized in your Flask app factory."
        )
        return None

    db_pool = current_app.extensions.get('db_pool')
    # Optional: Add a type check here if you want to be stricter,
    # though it might be problematic if the actual pool object is wrapped.
    # if not isinstance(db_pool, psycopg2_pool.AbstractConnectionPool):
    #     logger.error(f"Retrieved db_pool is not of the expected psycopg2 pool type. Type: {type(db_pool)}")
    #     return None

    return db_pool


# --- Google Drive OAuth Constants ---
ATOM_GDRIVE_CLIENT_ID = os.environ.get("ATOM_GDRIVE_CLIENT_ID")
ATOM_GDRIVE_CLIENT_SECRET = os.environ.get("ATOM_GDRIVE_CLIENT_SECRET")
ATOM_GDRIVE_REDIRECT_URI = os.environ.get("ATOM_GDRIVE_REDIRECT_URI")
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"
FRONTEND_OAUTH_SUCCESS_URL = os.environ.get("FRONTEND_OAUTH_SUCCESS_URL", "/settings/connections?gdrive_status=success")
FRONTEND_OAUTH_FAILURE_URL = os.environ.get("FRONTEND_OAUTH_FAILURE_URL", "/settings/connections?gdrive_status=failure")


@auth_bp.route('/api/auth/gdrive/initiate', methods=['GET'])
def gdrive_auth_initiate():
    atom_user_id = request.args.get('user_id')
    if not atom_user_id:
        return jsonify({"ok": False, "error": {"code": "AUTH_BAD_REQUEST", "message": "user_id is required to initiate OAuth flow."}}), 400

    if not all([ATOM_GDRIVE_CLIENT_ID, ATOM_GDRIVE_REDIRECT_URI]):
        logger.error("GDrive OAuth client ID or redirect URI not configured on server.")
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Google Drive integration is not configured on the server."}}), 500

    scopes = ["https://www.googleapis.com/auth/drive.readonly", "https://www.googleapis.com/auth/userinfo.email"]
    auth_url_params = {
        "client_id": ATOM_GDRIVE_CLIENT_ID, "redirect_uri": ATOM_GDRIVE_REDIRECT_URI,
        "response_type": "code", "scope": " ".join(scopes),
        "access_type": "offline", "prompt": "consent", "state": atom_user_id
    }
    google_auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{requests.compat.urlencode(auth_url_params)}"
    return redirect(google_auth_url, code=302)


@auth_bp.route('/api/auth/gdrive/callback', methods=['GET'])
def gdrive_auth_callback():
    if not CRYPTO_AVAILABLE or not DB_UTILS_AVAILABLE:
        logger.critical("OAuth callback cannot proceed: crypto or DB utils are not available.")
        return redirect(f"{FRONTEND_OAUTH_FAILURE_URL}&error=server_setup_error_critical", code=302)

    auth_code = request.args.get('code')
    atom_user_id = request.args.get('state')

    if not auth_code: return redirect(f"{FRONTEND_OAUTH_FAILURE_URL}&error=no_auth_code", code=302)
    if not atom_user_id: return redirect(f"{FRONTEND_OAUTH_FAILURE_URL}&error=missing_state_userid", code=302)

    if not all([ATOM_GDRIVE_CLIENT_ID, ATOM_GDRIVE_CLIENT_SECRET, ATOM_GDRIVE_REDIRECT_URI]):
        logger.error("GDrive OAuth client config missing for token exchange.")
        return redirect(f"{FRONTEND_OAUTH_FAILURE_URL}&error=server_config_error_exchange", code=302)

    token_payload = {
        'code': auth_code, 'client_id': ATOM_GDRIVE_CLIENT_ID,
        'client_secret': ATOM_GDRIVE_CLIENT_SECRET, 'redirect_uri': ATOM_GDRIVE_REDIRECT_URI,
        'grant_type': 'authorization_code'
    }

    try:
        token_response = requests.post(GOOGLE_TOKEN_URL, data=token_payload, timeout=10)
        token_response.raise_for_status()
        tokens = token_response.json()

        access_token = tokens.get('access_token')
        refresh_token = tokens.get('refresh_token')
        expires_in_seconds = tokens.get('expires_in')
        granted_scopes = tokens.get('scope')

        if not access_token:
            logger.error(f"GDrive token exchange failed (no access_token) for user {atom_user_id}. Response: {tokens}")
            return redirect(f"{FRONTEND_OAUTH_FAILURE_URL}&error=no_access_token", code=302)

        expiry_timestamp_ms = int((datetime.now(timezone.utc) + timedelta(seconds=expires_in_seconds)).timestamp() * 1000)

        userinfo_headers = {'Authorization': f'Bearer {access_token}'}
        userinfo_response = requests.get(GOOGLE_USERINFO_URL, headers=userinfo_headers, timeout=10)
        userinfo_response.raise_for_status()
        gdrive_user_info = userinfo_response.json()
        gdrive_email = gdrive_user_info.get('email')

        if not gdrive_email:
            logger.error(f"GDrive userinfo fetch failed (no email) for user {atom_user_id}. {gdrive_user_info}")
            return redirect(f"{FRONTEND_OAUTH_FAILURE_URL}&error=no_gdrive_email", code=302)

        encrypted_at = encrypt_data(access_token)
        encrypted_rt = encrypt_data(refresh_token) if refresh_token else None

        if encrypted_at is None or (refresh_token and encrypted_rt is None):
            logger.critical(f"Failed to encrypt tokens for user {atom_user_id}. Aborting save.")
            return redirect(f"{FRONTEND_OAUTH_FAILURE_URL}&error=token_encryption_failed", code=302)

        db_pool = get_db_connection_pool() # Conceptual
        save_ok = save_or_update_gdrive_tokens(
            db_pool, atom_user_id, gdrive_email, encrypted_at,
            encrypted_rt, expiry_timestamp_ms, granted_scopes
        )

        if save_ok:
            logger.info(f"Successfully stored GDrive tokens for user {atom_user_id}, email {gdrive_email}")
            return redirect(FRONTEND_OAUTH_SUCCESS_URL, code=302)
        else:
            logger.error(f"Failed to save GDrive tokens to DB for user {atom_user_id}")
            return redirect(f"{FRONTEND_OAUTH_FAILURE_URL}&error=db_save_failed", code=302)

    except requests.exceptions.RequestException as e:
        logger.error(f"GDrive token exchange network error for user {atom_user_id}: {e}", exc_info=True)
        return redirect(f"{FRONTEND_OAUTH_FAILURE_URL}&error=token_exchange_network_error", code=302)
    except Exception as e:
        logger.error(f"Unexpected error in GDrive OAuth callback for user {atom_user_id}: {e}", exc_info=True)
        return redirect(f"{FRONTEND_OAUTH_FAILURE_URL}&error=unknown_callback_error", code=302)


def refresh_gdrive_access_token_internal(user_id: str) -> Optional[str]:
    if not CRYPTO_AVAILABLE or not DB_UTILS_AVAILABLE:
        logger.error(f"Token refresh cannot proceed for user {user_id}: crypto or DB utils not available.")
        return None

    if not all([ATOM_GDRIVE_CLIENT_ID, ATOM_GDRIVE_CLIENT_SECRET]):
        logger.error("GDrive client ID or secret not configured for token refresh.")
        return None

    db_pool = get_db_connection_pool() # Conceptual
    token_db_details = get_gdrive_oauth_details(db_pool, user_id)

    if not token_db_details or not token_db_details.get('refresh_token_encrypted'):
        logger.warn(f"No GDrive refresh token found in DB for user {user_id} to attempt refresh.")
        return None

    encrypted_refresh_token = token_db_details['refresh_token_encrypted']
    decrypted_refresh_token = decrypt_data(encrypted_refresh_token)

    if not decrypted_refresh_token:
        logger.error(f"Failed to decrypt refresh token for user {user_id}. Token may be corrupted or key changed.")
        return None

    refresh_payload = {
        'client_id': ATOM_GDRIVE_CLIENT_ID, 'client_secret': ATOM_GDRIVE_CLIENT_SECRET,
        'refresh_token': decrypted_refresh_token, 'grant_type': 'refresh_token'
    }
    try:
        logger.info(f"Attempting GDrive access token refresh for user {user_id}")
        response = requests.post(GOOGLE_TOKEN_URL, data=refresh_payload, timeout=10)
        response.raise_for_status()
        new_tokens = response.json()

        new_access_token = new_tokens.get('access_token')
        new_expires_in = new_tokens.get('expires_in')

        if not new_access_token or not new_expires_in:
            logger.error(f"GDrive token refresh for user {user_id} did not return new access_token/expires_in. Response: {new_tokens}")
            return None

        new_expiry_timestamp_ms = int((datetime.now(timezone.utc) + timedelta(seconds=new_expires_in)).timestamp() * 1000)
        encrypted_new_access_token = encrypt_data(new_access_token)

        if not encrypted_new_access_token:
            logger.critical(f"Failed to encrypt new access token for user {user_id} after refresh.")
            return None

        update_ok = update_gdrive_access_token(
            db_pool, user_id, encrypted_new_access_token, new_expiry_timestamp_ms
        )

        if update_ok:
            logger.info(f"GDrive token refreshed and DB updated successfully for user {user_id}")
            return new_access_token # Return plain new access token
        else:
            logger.error(f"Failed to update GDrive token in DB after refresh for user {user_id}")
            return None

    except requests.exceptions.RequestException as e:
        logger.error(f"GDrive token refresh network error for user {user_id}: {e}", exc_info=True)
        if hasattr(e, 'response') and e.response is not None and e.response.status_code in [400, 401]:
            logger.warn(f"GDrive refresh token for user {user_id} may be invalid (HTTP {e.response.status_code}). Details: {e.response.text}. User may need to re-authenticate.")
            # TODO: Consider deleting or marking the invalid refresh token in DB.
        return None
    except Exception as e:
        logger.error(f"Unexpected error in GDrive token refresh for user {user_id}: {e}", exc_info=True)
        return None


# --- Internal Utility for Access Token Retrieval & Refresh ---
def get_mcp_credentials(user_id: str, provider: str = 'gdrive') -> Optional[Any]:
    if provider == 'gdrive':
        token = _get_valid_gdrive_access_token(user_id)
        if token:
            class MockCreds:
                def __init__(self, token, provider='gdrive'):
                    self.token = token
                    self.provider = provider
            return MockCreds(token)
    # Add other providers here
    return None

def get_mcp_provider(creds: Any) -> str:
    return getattr(creds, 'provider', 'gdrive')

def _get_valid_gdrive_access_token(user_id: str) -> Optional[str]:
    """
    Internal utility to get a valid GDrive access token for a user.
    Handles fetching, checking expiry, and refreshing if necessary.
    Returns the plain access token or None if not available/error.
    """
    if not CRYPTO_AVAILABLE or not DB_UTILS_AVAILABLE:
        logger.error(f"Cannot get access token for user {user_id}: crypto or DB utils are not available.")
        return None

    db_pool = get_db_connection_pool() # Conceptual
    token_db_details = get_gdrive_oauth_details(db_pool, user_id)

    if not token_db_details or not token_db_details.get("access_token_encrypted") or not token_db_details.get("expiry_timestamp_ms"):
        logger.info(f"No GDrive token found in DB for user {user_id} or token details incomplete.")
        return None

    current_time_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    buffer_seconds = 5 * 60 # 5 minutes buffer

    if current_time_ms >= (token_db_details["expiry_timestamp_ms"] - (buffer_seconds * 1000)):
        logger.info(f"GDrive access token for user {user_id} expired or nearing expiry. Attempting refresh.")
        refreshed_plain_access_token = refresh_gdrive_access_token_internal(user_id)
        if refreshed_plain_access_token:
            return refreshed_plain_access_token
        else:
            logger.error(f"GDrive token refresh failed for user {user_id}. User may need to re-authenticate.")
            return None
    else:
        decrypted_access_token = decrypt_data(token_db_details["access_token_encrypted"])
        if not decrypted_access_token:
            logger.error(f"Failed to decrypt stored access token for user {user_id}. Token data might be corrupted or key changed.")
            return None
        logger.debug(f"Returning existing valid GDrive access token for user {user_id}.")
        return decrypted_access_token


@auth_bp.route('/api/auth/gdrive/get-access-token', methods=['GET'])
def get_gdrive_access_token_route():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id is required."}}), 400

    # Placeholder: In a real app, verify that the requester (e.g. other backend service) is authorized
    # if the user_id in the token/session does not match the user_id in the query.

    access_token = _get_valid_gdrive_access_token(user_id)

    if access_token:
        return jsonify({"ok": True, "data": {"access_token": access_token}}), 200
    elif not CRYPTO_AVAILABLE or not DB_UTILS_AVAILABLE: # Check if failure was due to setup
         return jsonify({"ok": False, "error": {"code": "SERVER_SETUP_ERROR_CRITICAL", "message": "Auth components not available."}}), 503
    else: # General failure to get or refresh token
        # Check if token_db_details were found at all to differentiate "no token" vs "refresh failed"
        db_pool = get_db_connection_pool()
        token_db_details = get_gdrive_oauth_details(db_pool, user_id) # Re-fetch to check existence
        if not token_db_details:
            return jsonify({"ok": False, "error": {"code": "NO_TOKEN_FOUND", "message": "No GDrive token found for user. Please authenticate."}}), 401
        else:
            return jsonify({"ok": False, "error": {"code": "TOKEN_RETRIEVAL_FAILED", "message": "Failed to retrieve or refresh GDrive access token. Please re-authenticate."}}), 401


@auth_bp.route('/api/auth/gdrive/disconnect', methods=['POST'])
def gdrive_auth_disconnect():
    if not DB_UTILS_AVAILABLE: # Crypto not strictly needed for delete, but DB is
        logger.error("Cannot disconnect GDrive: DB utils are not available.")
        return jsonify({"ok": False, "error": {"code": "SERVER_SETUP_ERROR_CRITICAL", "message": "Database components not available."}}), 503

    data = request.get_json()
    if not data or 'user_id' not in data:
        return jsonify({"ok": False, "error": {"code": "INVALID_PAYLOAD", "message": "Request must be JSON and include user_id."}}), 400

    user_id = data['user_id']

    # Placeholder: In a real app, verify that the requester is authorized to disconnect this user_id.

    db_pool = get_db_connection_pool()

    # TODO: Future enhancement - Attempt to revoke token with Google before deleting from DB.
    # This would involve fetching the token (if it exists), decrypting it,
    # then making a call to https://oauth2.googleapis.com/revoke?token=<token>.
    # Requires careful handling if only refresh token is stored or if access token is expired.
    # For now, we prioritize deleting the local record.
    # Example:
    # token_details = get_gdrive_oauth_details(db_pool, user_id)
    # if token_details and token_details.get('refresh_token_encrypted'):
    #     rt = decrypt_data(token_details['refresh_token_encrypted'])
    #     if rt: requests.post('https://oauth2.googleapis.com/revoke', params={'token': rt}) # Best effort
    # elif token_details and token_details.get('access_token_encrypted'):
    #     at = decrypt_data(token_details['access_token_encrypted'])
    #     if at: requests.post('https://oauth2.googleapis.com/revoke', params={'token': at}) # Best effort


    deleted_ok = delete_gdrive_tokens(db_pool, user_id)

    if deleted_ok:
        logger.info(f"GDrive tokens deleted from DB for user {user_id}.")
        return jsonify({"ok": True, "message": "Google Drive account disconnected successfully."}), 200
    else:
        # This could be because the user had no tokens, or a DB error occurred.
        # db_oauth_gdrive.delete_gdrive_tokens logs details.
        logger.warning(f"GDrive token deletion for user {user_id} reported as not OK (may be no tokens or DB error).")
        # To provide a more specific error, one might check if tokens existed before attempting delete.
        # For now, a generic message is okay as the outcome is tokens are gone or were never there.
        return jsonify({"ok": False, "error": {"code": "DISCONNECT_FAILED", "message": "Could not complete GDrive disconnection. Tokens may not have existed or a database error occurred."}}), 500


# For standalone running and registration with a main app
# This part would typically be in the main app.py or similar of the python_api_service
# For example:
# from .auth_handler import auth_bp
# app.register_blueprint(auth_bp)

if __name__ == '__main__':
    # This allows running this handler standalone for basic testing of routes.
    # Note: `get_db_connection_pool()` would need to be meaningful or mocked.
    # And Flask's `current_app` context won't be fully set up as in a real app.
    def create_dev_app():
        app = Flask(__name__)
        app.extensions['db_pool'] = "mock_db_pool_for_dev_run" # Mock pool for standalone
        app.register_blueprint(auth_bp)
        return app

    dev_app = create_dev_app()
    flask_port = int(os.environ.get("AUTH_HANDLER_PORT", 5058))
    dev_app.run(host='0.0.0.0', port=flask_port, debug=True)
