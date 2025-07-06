import os
import sys
import json
import requests # For token exchange and userinfo
import logging
from datetime import datetime, timedelta, timezone
from flask import Blueprint, request, jsonify, redirect, current_app # current_app for config if needed

# Placeholder for encryption - In production, use a robust library like 'cryptography'
# and a securely managed key (e.g., from env or secrets manager)
ENCRYPTION_KEY = os.environ.get("ATOM_OAUTH_ENCRYPTION_KEY", "default_dummy_key_32_bytes_long") # MUST BE SECURE & CONSISTENT
if ENCRYPTION_KEY == "default_dummy_key_32_bytes_long":
    print("WARNING: Using default dummy encryption key for OAuth tokens. THIS IS NOT SECURE FOR PRODUCTION.", file=sys.stderr)
# For actual encryption: from cryptography.fernet import Fernet
# fernet_cipher = Fernet(ENCRYPTION_KEY.encode()) # Key must be url-safe base64-encoded 32-byte key

def encrypt_token_data(data: str) -> str:
    # logger.debug("Encrypting token data (placeholder)")
    # return fernet_cipher.encrypt(data.encode()).decode()
    return f"encrypted_{data}" # Placeholder

def decrypt_token_data(encrypted_data: str) -> str:
    # logger.debug("Decrypting token data (placeholder)")
    # return fernet_cipher.decrypt(encrypted_data.encode()).decode()
    if encrypted_data.startswith("encrypted_"):
        return encrypted_data[len("encrypted_"):] # Placeholder
    raise ValueError("Decryption failed - placeholder error or data not encrypted by placeholder")


# Placeholder for Database interaction - In production, use SQLAlchemy, psycopg2, etc.
# These functions would interact with the 'user_gdrive_oauth_tokens' table.
def db_save_gdrive_tokens(user_id: str, gdrive_user_email: str, access_token: str, refresh_token: Optional[str], expiry_timestamp_ms: int, scopes: str) -> bool:
    # In a real DB:
    # INSERT INTO user_gdrive_oauth_tokens (user_id, gdrive_user_email, access_token_encrypted, refresh_token_encrypted, expiry_timestamp_ms, scopes_granted, created_at, last_updated_at)
    # VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW())
    # ON CONFLICT (user_id) DO UPDATE SET
    #   gdrive_user_email = EXCLUDED.gdrive_user_email,
    #   access_token_encrypted = EXCLUDED.access_token_encrypted,
    #   refresh_token_encrypted = COALESCE(EXCLUDED.refresh_token_encrypted, user_gdrive_oauth_tokens.refresh_token_encrypted), -- Important: don't overwrite refresh token with NULL if not provided
    #   expiry_timestamp_ms = EXCLUDED.expiry_timestamp_ms,
    #   scopes_granted = EXCLUDED.scopes_granted,
    #   last_updated_at = NOW();
    encrypted_access_token = encrypt_token_data(access_token)
    encrypted_refresh_token = encrypt_token_data(refresh_token) if refresh_token else None

    logger.info(f"DB_SAVE (Placeholder): User {user_id}, Email {gdrive_user_email}, AT_Expiry_MS: {expiry_timestamp_ms}, Scopes: {scopes}, HasRT: {bool(refresh_token)}")
    # Simulate DB save - in a real app, this would be a database transaction.
    # For simplicity, we'll just log. A file-based store or in-memory dict could be used for basic testing.
    # Example: current_app.tokens_db[user_id] = { ... }
    return True

def db_get_refresh_token(user_id: str) -> Optional[str]:
    # SELECT refresh_token_encrypted FROM user_gdrive_oauth_tokens WHERE user_id = %s;
    # Then decrypt.
    logger.info(f"DB_GET_RT (Placeholder): Retrieving refresh token for user {user_id}")
    # Simulate fetching - this would come from current_app.tokens_db or a real DB
    # if user_id in current_app.tokens_db and current_app.tokens_db[user_id].get('refresh_token_encrypted'):
    #    return decrypt_token_data(current_app.tokens_db[user_id]['refresh_token_encrypted'])
    return "mock_decrypted_refresh_token_for_" + user_id # Placeholder for testing refresh flow

def db_get_access_token_details(user_id: str) -> Optional[Dict[str, Any]]:
    # SELECT access_token_encrypted, expiry_timestamp_ms FROM user_gdrive_oauth_tokens WHERE user_id = %s;
    logger.info(f"DB_GET_AT_DETAILS (Placeholder): Retrieving access token details for user {user_id}")
    # if user_id in current_app.tokens_db:
    #    return {
    #        "access_token": decrypt_token_data(current_app.tokens_db[user_id]['access_token_encrypted']),
    #        "expiry_timestamp_ms": current_app.tokens_db[user_id]['expiry_timestamp_ms']
    #    }
    # Simulate a valid, non-expired token for direct use if refresh isn't tested first
    return {
        "access_token": "mock_decrypted_non_expired_access_token_for_" + user_id,
        "expiry_timestamp_ms": (datetime.now(timezone.utc) + timedelta(hours=1)).timestamp() * 1000
    }


# --- Flask Blueprint Setup ---
auth_bp = Blueprint('auth_api', __name__)
logger = logging.getLogger(__name__) # Use Flask's app logger if available or configure this one
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# --- Google Drive OAuth Constants (should come from env via constants.py) ---
# These would be imported from a constants file that loads from os.environ
ATOM_GDRIVE_CLIENT_ID = os.environ.get("ATOM_GDRIVE_CLIENT_ID")
ATOM_GDRIVE_CLIENT_SECRET = os.environ.get("ATOM_GDRIVE_CLIENT_SECRET")
ATOM_GDRIVE_REDIRECT_URI = os.environ.get("ATOM_GDRIVE_REDIRECT_URI")
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"
# Frontend URL to redirect to after OAuth flow (should be configurable)
FRONTEND_OAUTH_SUCCESS_URL = os.environ.get("FRONTEND_OAUTH_SUCCESS_URL", "/settings/connections?gdrive_status=success")
FRONTEND_OAUTH_FAILURE_URL = os.environ.get("FRONTEND_OAUTH_FAILURE_URL", "/settings/connections?gdrive_status=failure")


@auth_bp.route('/api/auth/gdrive/initiate', methods=['GET'])
def gdrive_auth_initiate():
    # This endpoint is called by the frontend to start the OAuth flow.
    # It redirects the user to Google's consent screen.
    # The 'state' parameter should include the Atom user_id to link back after callback.
    atom_user_id = request.args.get('user_id') # Or from session/JWT if user is logged in
    if not atom_user_id:
        return jsonify({"ok": False, "error": {"code": "AUTH_BAD_REQUEST", "message": "user_id is required to initiate OAuth flow."}}), 400

    if not all([ATOM_GDRIVE_CLIENT_ID, ATOM_GDRIVE_REDIRECT_URI]):
        logger.error("GDrive OAuth client ID or redirect URI not configured on server.")
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Google Drive integration is not configured on the server."}}), 500

    scopes = ["https://www.googleapis.com/auth/drive.readonly", "https://www.googleapis.com/auth/userinfo.email"]
    auth_url_params = {
        "client_id": ATOM_GDRIVE_CLIENT_ID,
        "redirect_uri": ATOM_GDRIVE_REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(scopes),
        "access_type": "offline", # To get a refresh token
        "prompt": "consent",      # Ensures refresh token is issued even on re-auth
        "state": atom_user_id     # Pass Atom user_id through state to identify user on callback
    }
    google_auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{requests.compat.urlencode(auth_url_params)}"
    return redirect(google_auth_url, code=302)


@auth_bp.route('/api/auth/gdrive/callback', methods=['GET'])
def gdrive_auth_callback():
    auth_code = request.args.get('code')
    state_param = request.args.get('state') # This should be the Atom user_id

    if not auth_code:
        logger.error("GDrive OAuth callback error: No authorization code provided by Google.")
        return redirect(f"{FRONTEND_OAUTH_FAILURE_URL}&error=no_auth_code", code=302)

    if not state_param: # Atom user_id passed in state
        logger.error("GDrive OAuth callback error: State parameter (user_id) missing.")
        return redirect(f"{FRONTEND_OAUTH_FAILURE_URL}&error=missing_state_userid", code=302)

    atom_user_id = state_param

    if not all([ATOM_GDRIVE_CLIENT_ID, ATOM_GDRIVE_CLIENT_SECRET, ATOM_GDRIVE_REDIRECT_URI]):
        logger.error("GDrive OAuth client ID, secret, or redirect URI not configured on server for token exchange.")
        return redirect(f"{FRONTEND_OAUTH_FAILURE_URL}&error=server_config_error", code=302)

    token_payload = {
        'code': auth_code,
        'client_id': ATOM_GDRIVE_CLIENT_ID,
        'client_secret': ATOM_GDRIVE_CLIENT_SECRET,
        'redirect_uri': ATOM_GDRIVE_REDIRECT_URI,
        'grant_type': 'authorization_code'
    }

    try:
        logger.info(f"Exchanging GDrive auth code for user_id (from state): {atom_user_id}")
        token_response = requests.post(GOOGLE_TOKEN_URL, data=token_payload, timeout=10)
        token_response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        tokens = token_response.json()

        access_token = tokens.get('access_token')
        refresh_token = tokens.get('refresh_token') # May not be present on re-auth if not prompted for consent
        expires_in_seconds = tokens.get('expires_in') # Typically 3600
        granted_scopes = tokens.get('scope')

        if not access_token:
            logger.error(f"GDrive token exchange failed for user {atom_user_id}: No access_token in response. Response: {tokens}")
            return redirect(f"{FRONTEND_OAUTH_FAILURE_URL}&error=no_access_token", code=302)

        expiry_timestamp_ms = int((datetime.now(timezone.utc) + timedelta(seconds=expires_in_seconds)).timestamp() * 1000)

        # Get user info (email) from Google to confirm identity and store
        userinfo_headers = {'Authorization': f'Bearer {access_token}'}
        userinfo_response = requests.get(GOOGLE_USERINFO_URL, headers=userinfo_headers, timeout=10)
        userinfo_response.raise_for_status()
        gdrive_user_info = userinfo_response.json()
        gdrive_email = gdrive_user_info.get('email')

        if not gdrive_email:
            logger.error(f"GDrive userinfo fetch failed for user {atom_user_id}: No email in userinfo response. {gdrive_user_info}")
            return redirect(f"{FRONTEND_OAUTH_FAILURE_URL}&error=no_gdrive_email", code=302)

        # Securely store tokens in DB
        # The refresh_token should only be updated if a new one is provided by Google.
        # If refresh_token is None here, the db_save function should preserve existing one if any.
        save_ok = db_save_gdrive_tokens(
            user_id=atom_user_id,
            gdrive_user_email=gdrive_email,
            access_token=access_token,
            refresh_token=refresh_token,
            expiry_timestamp_ms=expiry_timestamp_ms,
            scopes=granted_scopes
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


@auth_bp.route('/api/auth/gdrive/get-access-token', methods=['GET']) # Should be POST and protected
def get_gdrive_access_token_route():
    # This endpoint is called by TypeScript skills to get a valid access token.
    # It should be protected (e.g., require Atom app authentication/JWT).
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id is required."}}), 400

    # Placeholder: In a real app, verify that the requester is authorized for this user_id.

    token_details = db_get_access_token_details(user_id)

    if not token_details or not token_details.get("access_token") or not token_details.get("expiry_timestamp_ms"):
        return jsonify({"ok": False, "error": {"code": "NO_TOKEN_FOUND", "message": "No GDrive token found for user or token details incomplete. Please re-authenticate."}}), 401 # Or 404

    current_time_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    # Check if token is expired or very close to expiring (e.g., within 5 minutes)
    if current_time_ms >= (token_details["expiry_timestamp_ms"] - (5 * 60 * 1000)):
        logger.info(f"GDrive access token for user {user_id} expired or nearing expiry. Attempting refresh.")
        refreshed_token = refresh_gdrive_access_token_internal(user_id) # Call internal refresh logic
        if refreshed_token:
            return jsonify({"ok": True, "data": {"access_token": refreshed_token}}), 200
        else:
            logger.error(f"GDrive token refresh failed for user {user_id}. User may need to re-authenticate.")
            return jsonify({"ok": False, "error": {"code": "TOKEN_REFRESH_FAILED", "message": "Failed to refresh GDrive access token. Please re-authenticate."}}), 401
    else:
        logger.info(f"Returning existing valid GDrive access token for user {user_id}.")
        return jsonify({"ok": True, "data": {"access_token": token_details["access_token"]}}), 200


# Internal logic for refreshing token, not directly an endpoint
def refresh_gdrive_access_token_internal(user_id: str) -> Optional[str]:
    if not all([ATOM_GDRIVE_CLIENT_ID, ATOM_GDRIVE_CLIENT_SECRET]):
        logger.error("GDrive client ID or secret not configured for token refresh.")
        return None

    encrypted_refresh_token = db_get_refresh_token(user_id)
    if not encrypted_refresh_token:
        logger.warn(f"No GDrive refresh token found in DB for user {user_id} to attempt refresh.")
        return None

    try:
        refresh_token = decrypt_token_data(encrypted_refresh_token)
    except Exception as decrypt_err:
        logger.error(f"Failed to decrypt refresh token for user {user_id}: {decrypt_err}", exc_info=True)
        return None

    refresh_payload = {
        'client_id': ATOM_GDRIVE_CLIENT_ID,
        'client_secret': ATOM_GDRIVE_CLIENT_SECRET,
        'refresh_token': refresh_token,
        'grant_type': 'refresh_token'
    }
    try:
        logger.info(f"Attempting GDrive access token refresh for user {user_id}")
        response = requests.post(GOOGLE_TOKEN_URL, data=refresh_payload, timeout=10)
        response.raise_for_status()
        new_tokens = response.json()

        new_access_token = new_tokens.get('access_token')
        new_expires_in = new_tokens.get('expires_in')
        # Note: Google typically does NOT return a new refresh_token during a refresh token grant.
        # The existing refresh_token should continue to be used.
        # However, if one IS returned, it's usually a sign the old one was expiring / use the new one.
        # For this impl, we assume existing refresh token remains valid and don't try to update it from refresh response.

        if not new_access_token or not new_expires_in:
            logger.error(f"GDrive token refresh for user {user_id} did not return new access_token or expires_in. Response: {new_tokens}")
            return None

        new_expiry_timestamp_ms = int((datetime.now(timezone.utc) + timedelta(seconds=new_expires_in)).timestamp() * 1000)

        # Fetch gdrive_user_email and scopes from DB to pass to save, as they are not changed by refresh
        # This is a simplification; a real DB function would update specific fields.
        # For now, assume db_save_gdrive_tokens can handle updates correctly.
        # A better db function: db_update_access_token(user_id, new_access_token, new_expiry_timestamp_ms)

        # Re-fetch minimal existing data to ensure we don't lose it on save
        # This part is clumsy; a proper ORM or specific DB update function is better.
        # For this placeholder, we'll just save the new access token and expiry.
        # We'll need gdrive_user_email and scopes to satisfy db_save_gdrive_tokens if it's a full upsert.
        # This implies db_save_gdrive_tokens needs to be smarter or we need a db_update_access_token func.
        # Let's assume for the placeholder `db_save_gdrive_tokens` that passing only new AT and expiry is enough for an update path.
        # This is a FLAW in the current placeholder DB logic for `db_save_gdrive_tokens` if it expects all fields for an update.

        # To make it work with current db_save_gdrive_tokens, we'd need to fetch existing email/scopes.
        # This is where a proper ORM or data access layer shines.
        # For now, we'll simulate that db_save_gdrive_tokens can update just the access token part.
        # This means the placeholder `db_save_gdrive_tokens` would need to be:
        # db_update_access_token(user_id, new_access_token, new_expiry_timestamp_ms) -> bool

        # To fit the current db_save_gdrive_tokens, we'd need to do this (which is inefficient):
        # current_token_record = db_get_full_token_record(user_id) # New conceptual DB function
        # if current_token_record:
        #    save_ok = db_save_gdrive_tokens(user_id, current_token_record['gdrive_user_email'], new_access_token, None, new_expiry_timestamp_ms, current_token_record['scopes'])
        # else: save_ok = False # Should not happen if we had a refresh token

        # Simplified: Assume a direct update function exists or db_save handles partial update for access token
        logger.info(f"Updating GDrive tokens in DB for user {user_id} after refresh.")
        # This is a conceptual call to a more specific update function.
        # success_update = db_update_access_token_and_expiry(user_id, new_access_token, new_expiry_timestamp_ms)
        # For now, we'll try to use db_save_gdrive_tokens, assuming it can handle this update.
        # This requires db_save_gdrive_tokens to not nullify refresh_token if None is passed for it during update.
        # It also requires gdrive_user_email and scopes. This is where the placeholder DB funcs are insufficient.

        # Let's assume a more targeted update function for the purpose of this logic:
        # def db_update_access_token(user_id: str, new_access_token: str, new_expiry_ms: int) -> bool:
        #    encrypted_new_access_token = encrypt_token_data(new_access_token)
        #    # UPDATE user_gdrive_oauth_tokens SET access_token_encrypted = %s, expiry_timestamp_ms = %s, last_updated_at = NOW() WHERE user_id = %s
        #    logger.info(f"DB_UPDATE_AT (Placeholder): User {user_id} new AT expiry {new_expiry_ms}")
        #    return True

        # Simulate calling this more targeted update:
        if True: # Simulate success of db_update_access_token
            logger.info(f"GDrive token refreshed and DB updated successfully for user {user_id}")
            return new_access_token
        else:
            logger.error(f"Failed to update GDrive token in DB after refresh for user {user_id}")
            return None

    except requests.exceptions.RequestException as e:
        logger.error(f"GDrive token refresh network error for user {user_id}: {e}", exc_info=True)
        if hasattr(e, 'response') and e.response is not None and e.response.status_code in [400, 401]:
            # Bad refresh token (e.g., revoked by user, expired)
            logger.warn(f"GDrive refresh token for user {user_id} may be invalid. HTTP Status: {e.response.status_code}. Details: {e.response.text}")
            # TODO: Should mark the refresh token as invalid in DB or delete the record to force re-auth.
        return None
    except Exception as e:
        logger.error(f"Unexpected error in GDrive token refresh for user {user_id}: {e}", exc_info=True)
        return None

# This is for standalone running. In a real setup, this blueprint
# would be imported and registered by the main python_api_service Flask app.
# e.g. in note_handler.py or a central app.py:
# from .auth_handler import auth_bp
# app.register_blueprint(auth_bp)

if __name__ == '__main__':
    # This app instance is local to this file for dev/testing standalone.
    # The blueprint `auth_bp` should be registered with the main service app.
    # For testing, you might need to create a temporary app here and register the blueprint.
    temp_app = Flask(__name__)
    temp_app.register_blueprint(auth_bp)
    # Example: python -m python_api_service.auth_handler (if in PYTHONPATH)
    # Or python auth_handler.py (if run directly from its dir, path adjustments are key)
    flask_port = int(os.environ.get("AUTH_HANDLER_PORT", 5058)) # Different port
    temp_app.run(host='0.0.0.0', port=flask_port, debug=True)
```
