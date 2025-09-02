import os
import logging
import sys

# Mock Flask for local testing
try:
    from flask import Blueprint, request, redirect, url_for, session, current_app
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
        args = {'user_id': 'mock_user', 'state': 'mock_state'}
        url = 'http://localhost/callback?code=mock_code&state=mock_state'

    class MockSession(dict):
        pass

    class MockCurrentApp:
        config = {'DB_CONNECTION_POOL': None}

    request = MockRequest()
    session = MockSession()
    current_app = MockCurrentApp()

    def redirect(url):
        return f"Redirect to: {url}"

    def url_for(endpoint, **kwargs):
        return f"http://localhost/{endpoint}"

class MockCredentials:
    def __init__(self):
        self.token = 'mock_access_token'
        self.refresh_token = 'mock_refresh_token'
        self.token_uri = 'https://oauth2.googleapis.com/token'
        self.client_id = 'mock_client_id'
        self.client_secret = 'mock_client_secret'
        self.scopes = ['https://www.googleapis.com/auth/drive.readonly', 'https://www.googleapis.com/auth/userinfo.email']
        self.expiry = None

    def to_json(self):
        import json
        return json.dumps({
            'token': self.token,
            'refresh_token': self.refresh_token,
            'token_uri': self.token_uri,
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'scopes': self.scopes
        })

class MockFlow:
    def __init__(self, **kwargs):
        self.credentials = MockCredentials()

    @classmethod
    def from_client_secrets_file(cls, client_secrets_file, **kwargs):
        return cls(**kwargs)

    def authorization_url(self, **kwargs):
        return 'https://accounts.google.com/o/oauth2/v2/auth?mock=true', 'mock_state'

    def fetch_token(self, **kwargs):
        pass

def mock_build(service_name, version, credentials=None):
    if service_name == 'oauth2':
        class MockService:
            def userinfo(self):
                class MockUserInfo:
                    def get(self):
                        class MockGet:
                            def execute(self):
                                return {'email': 'mockuser@example.com'}
                        return MockGet()
                return MockUserInfo()
        return MockService()
    return None

try:
    from google_auth_oauthlib.flow import Flow
    from googleapiclient.discovery import build
except ImportError:
    Flow = MockFlow
    build = mock_build

from .db_oauth_gdrive import save_token
from .crypto_utils import encrypt_data as encrypt_token

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
        scopes=['https://www.googleapis.com/auth/drive.readonly', 'https://www.googleapis.com/auth/userinfo.email'],
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
        scopes=['https://www.googleapis.com/auth/drive.readonly', 'https://www.googleapis.com/auth/userinfo.email'],
        state=state,
        redirect_uri=url_for('gdrive_auth_bp.oauth2callback', _external=True)
    )

    flow.fetch_token(authorization_response=request.url)

    credentials = flow.credentials

    # Get user's email to store alongside tokens
    try:
        service = build('oauth2', 'v2', credentials=credentials)
        if not service:
            logger.error(f"Failed to build Google service for user {user_id}")
            return "Failed to build Google service.", 500
        user_info = service.userinfo().get().execute()
        gdrive_user_email = user_info.get('email')
        if not gdrive_user_email:
            raise ValueError("Email not found in Google profile.")
    except Exception as e:
        logger.error(f"Failed to retrieve user email for user {user_id}: {e}", exc_info=True)
        return "Failed to retrieve user email from Google.", 500

    # Convert credentials to a JSON string for storing
    creds_json = credentials.to_json()

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return "Database connection not available.", 500

    try:
        # Extract token data from credentials
        import json
        creds_data = json.loads(creds_json)

        # Encrypt tokens
        access_token = creds_data.get('token')
        if not access_token:
            logger.error(f"Access Token not found in Google credentials for user {user_id}")
            return "Access Token not found in Google credentials.", 500

        encrypted_access = encrypt_token(access_token)

        refresh_token = creds_data.get('refresh_token')
        # Refresh token is optional, so it can be None
        encrypted_refresh = encrypt_token(refresh_token) if refresh_token else None

        # Calculate expiry timestamp (mock for now)
        import time
        expiry_timestamp = int(time.time() * 1000) + (3600 * 1000)  # 1 hour from now

        # Save tokens with all required parameters
        save_token(
            db_conn_pool,
            user_id,
            gdrive_user_email,
            encrypted_access,
            encrypted_refresh,
            expiry_timestamp,
            ','.join(creds_data.get('scopes', []))
        )
        return "Google Drive account connected successfully!", 200
    except Exception as e:
        logger.error(f"Failed to save Google Drive token for user {user_id}: {e}", exc_info=True)
        return "Failed to save token.", 500
