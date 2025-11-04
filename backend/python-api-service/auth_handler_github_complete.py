"""
GitHub OAuth Authentication Handler
Complete OAuth 2.0 implementation for GitHub integration
"""

import os
import logging
import sys
import base64
import json
import requests
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional

# Mock Flask for local testing
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
        return f"http://localhost:5000/{endpoint}"

    def jsonify(data):
        return json.dumps(data)

logger = logging.getLogger(__name__)

# GitHub OAuth Configuration
GITHUB_CLIENT_ID = os.getenv('GITHUB_CLIENT_ID', 'mock_github_client_id')
GITHUB_CLIENT_SECRET = os.getenv('GITHUB_CLIENT_SECRET', 'mock_github_client_secret')
GITHUB_REDIRECT_URI = os.getenv('GITHUB_REDIRECT_URI', 'http://localhost:3000/integrations/github/callback')
GITHUB_SCOPE = os.getenv('GITHUB_SCOPE', 'repo user:email read:org')

# GitHub OAuth URLs
GITHUB_OAUTH_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_OAUTH_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_API_BASE_URL = "https://api.github.com"

# Security configuration
ATOM_OAUTH_ENCRYPTION_KEY = os.getenv('ATOM_OAUTH_ENCRYPTION_KEY', 'default-oauth-key-change-in-production')

# Import encryption utilities
try:
    from atom_encryption import decrypt_data, encrypt_data
    ENCRYPTION_AVAILABLE = True
except ImportError:
    ENCRYPTION_AVAILABLE = False
    logger.warning("atom_encryption not available, tokens will be stored in plaintext")

# Import database operations
try:
    from db_oauth_github_complete import (
        save_tokens, get_tokens, delete_tokens, save_user_github_tokens,
        get_user_github_tokens, delete_user_github_tokens, save_github_user,
        get_github_user, is_token_expired
    )
    GITHUB_DB_AVAILABLE = True
except ImportError as e:
    logger.warning(f"GitHub database operations not available: {e}")
    GITHUB_DB_AVAILABLE = False

# Create Flask blueprint
auth_github_bp = Blueprint("auth_github_bp", __name__)

class GitHubAuthManager:
    """GitHub Authentication Manager"""
    
    def __init__(self):
        self.client_id = GITHUB_CLIENT_ID
        self.client_secret = GITHUB_CLIENT_SECRET
        self.redirect_uri = GITHUB_REDIRECT_URI
        self.scope = GITHUB_SCOPE
        self.token_url = GITHUB_OAUTH_TOKEN_URL
        self.authorize_url = GITHUB_OAUTH_AUTHORIZE_URL
        self.api_base_url = GITHUB_API_BASE_URL
    
    def get_authorization_url(self, user_id: str, scopes: list = None, redirect_uri: str = None) -> str:
        """
        Generate GitHub OAuth authorization URL
        """
        try:
            # Use provided parameters or defaults
            scopes_list = scopes or self.scope.split()
            callback_uri = redirect_uri or self.redirect_uri
            
            # Generate state parameter for security
            state_data = {
                "user_id": user_id,
                "timestamp": int(datetime.utcnow().timestamp()),
                "random": os.urandom(8).hex()
            }
            state_json = json.dumps(state_data)
            state_encoded = base64.urlsafe_b64encode(state_json.encode()).decode()
            
            # Build authorization URL
            auth_url = (
                f"{self.authorize_url}?"
                f"response_type=code&"
                f"client_id={self.client_id}&"
                f"redirect_uri={redirect_uri}&"
                f"scope={' '.join(scopes_list)}&"
                f"state={state_encoded}&"
                f"allow_signup=true"
            )
            
            return auth_url
            
        except Exception as e:
            logger.error(f"Error generating GitHub authorization URL: {e}")
            raise
    
    async def exchange_code_for_token(self, code: str) -> Dict[str, Any]:
        """
        Exchange authorization code for access token
        """
        try:
            token_data = {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "code": code,
                "redirect_uri": self.redirect_uri
            }
            
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded"
            }
            
            response = requests.post(
                self.token_url,
                data=token_data,
                headers=headers,
                timeout=30
            )
            response.raise_for_status()
            
            token_response = response.json()
            
            if "error" in token_response:
                raise Exception(f"GitHub OAuth error: {token_response.get('error_description', token_response.get('error'))}")
            
            # Calculate expiration time
            expires_at = datetime.utcnow() + timedelta(hours=8)
            
            return {
                "access_token": token_response.get("access_token"),
                "token_type": token_response.get("token_type", "bearer"),
                "scope": token_response.get("scope", self.scope),
                "refresh_token": None,  # GitHub doesn't use refresh tokens
                "expires_at": expires_at.isoformat()
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error exchanging code for token: {e}")
            raise Exception(f"Token exchange failed: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error in token exchange: {e}")
            raise
    
    async def get_github_user_info(self, access_token: str) -> Dict[str, Any]:
        """
        Get authenticated GitHub user information
        """
        try:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github.v3+json",
                "X-GitHub-Api-Version": "2022-11-28"
            }
            
            # Get user profile
            response = requests.get(f"{self.api_base_url}/user", headers=headers, timeout=30)
            response.raise_for_status()
            
            user_data = response.json()
            
            # Get user emails (GitHub requires separate API call for primary email)
            email_response = requests.get(f"{self.api_base_url}/user/emails", headers=headers, timeout=30)
            email_response.raise_for_status()
            emails_data = email_response.json()
            
            # Find primary email
            primary_email = None
            for email_info in emails_data:
                if email_info.get("primary", False):
                    primary_email = email_info.get("email")
                    break
            
            # Combine user data
            return {
                "id": user_data.get("id"),
                "login": user_data.get("login"),
                "name": user_data.get("name"),
                "email": primary_email or user_data.get("email"),
                "avatar_url": user_data.get("avatar_url"),
                "bio": user_data.get("bio"),
                "company": user_data.get("company"),
                "location": user_data.get("location"),
                "blog": user_data.get("blog"),
                "html_url": user_data.get("html_url"),
                "followers": user_data.get("followers", 0),
                "following": user_data.get("following", 0),
                "public_repos": user_data.get("public_repos", 0),
                "created_at": user_data.get("created_at"),
                "updated_at": user_data.get("updated_at"),
                "site_admin": user_data.get("site_admin", False),
                "hireable": user_data.get("hireable"),
                "twitter_username": user_data.get("twitter_username")
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error getting GitHub user info: {e}")
            raise Exception(f"Failed to get user info: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error getting GitHub user info: {e}")
            raise
    
    async def refresh_token(self, refresh_token: str) -> Dict[str, Any]:
        """
        Refresh GitHub access token (GitHub doesn't support refresh tokens)
        This method is included for compatibility but will always require re-authentication
        """
        logger.warning("GitHub doesn't support token refresh - re-authentication required")
        raise Exception("GitHub doesn't support token refresh. Please re-authenticate.")

# Create GitHub auth manager instance
github_auth_manager = GitHubAuthManager()

@auth_github_bp.route("/api/auth/github/authorize", methods=["POST"])
async def authorize():
    """Start GitHub OAuth 2.0 flow"""
    try:
        data = request.get_json()
        user_id = data.get("user_id")
        scopes = data.get("scopes", ["repo", "user:email", "read:org"])
        redirect_uri = data.get("redirect_uri", GITHUB_REDIRECT_URI)
        
        if not user_id:
            return jsonify({
                "ok": False,
                "error": "User ID is required"
            }), 400
        
        # Generate state parameter
        state_data = {
            "user_id": user_id,
            "timestamp": int(datetime.utcnow().timestamp()),
            "random": os.urandom(8).hex()
        }
        state_json = json.dumps(state_data)
        state_encoded = base64.urlsafe_b64encode(state_json.encode()).decode()
        
        # Build authorization URL
        auth_url = (
            f"{GITHUB_OAUTH_AUTHORIZE_URL}?"
            f"response_type=code&"
            f"client_id={GITHUB_CLIENT_ID}&"
            f"redirect_uri={redirect_uri}&"
            f"scope={' '.join(scopes)}&"
            f"state={state_encoded}&"
            f"allow_signup=true"
        )
        
        logger.info(f"GitHub OAuth authorization started for user {user_id}")
        
        return jsonify({
            "ok": True,
            "authorization_url": auth_url,
            "client_id": GITHUB_CLIENT_ID,
            "redirect_uri": redirect_uri,
            "scopes": scopes,
            "state": state_encoded
        })
        
    except Exception as e:
        logger.error(f"GitHub OAuth authorize error: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@auth_github_bp.route("/api/auth/github/callback", methods=["POST"])
async def callback():
    """Handle GitHub OAuth 2.0 callback"""
    try:
        data = request.get_json()
        code = data.get("code")
        state = data.get("state")
        
        if not code:
            return jsonify({
                "ok": False,
                "error": "Authorization code is required"
            }), 400
        
        # Decode and verify state
        if state:
            try:
                state_decoded = base64.urlsafe_b64decode(state.encode()).decode()
                state_data = json.loads(state_decoded)
                user_id = state_data.get("user_id")
                
                if not user_id:
                    return jsonify({
                        "ok": False,
                        "error": "Invalid state parameter"
                    }), 400
                
                # Verify state timestamp (prevent replay attacks)
                state_timestamp = state_data.get("timestamp", 0)
                current_timestamp = int(datetime.utcnow().timestamp())
                if current_timestamp - state_timestamp > 600:  # 10 minutes
                    return jsonify({
                        "ok": False,
                        "error": "State parameter expired"
                    }), 400
                    
            except Exception as e:
                logger.error(f"State decode error: {e}")
                return jsonify({
                    "ok": False,
                    "error": "Invalid state parameter"
                }), 400
        else:
            user_id = "default_user"  # Fallback for testing
        
        # Exchange authorization code for access token
        token_data = {
            "client_id": GITHUB_CLIENT_ID,
            "client_secret": GITHUB_CLIENT_SECRET,
            "code": code,
            "redirect_uri": GITHUB_REDIRECT_URI
        }
        
        headers = {
            "Accept": "application/json"
        }
        
        response = requests.post(GITHUB_OAUTH_TOKEN_URL, data=token_data, headers=headers, timeout=30)
        response.raise_for_status()
        
        token_response = response.json()
        
        if "error" in token_response:
            return jsonify({
                "ok": False,
                "error": token_response.get("error_description", token_response.get("error"))
            }), 400
        
        # Get user information from GitHub
        access_token = token_response.get("access_token")
        user_info = await github_auth_manager.get_github_user_info(access_token)
        
        if not user_info:
            return jsonify({
                "ok": False,
                "error": "Failed to retrieve user information"
            }), 400
        
        # Calculate expiration time (GitHub tokens typically don't expire, but we set a reasonable limit)
        expires_at = datetime.now(timezone.utc) + timedelta(hours=8)
        
        # Encrypt tokens
        encrypted_access_token = encrypt_data(
            access_token, 
            ATOM_OAUTH_ENCRYPTION_KEY
        )
        
        # Save tokens and user info to database
        if GITHUB_DB_AVAILABLE:
            await save_user_github_tokens(
                None,  # db_conn_pool - will be passed in production
                user_id,
                {
                    'access_token': encrypted_access_token,
                    'token_type': token_response.get("token_type", "bearer"),
                    'scope': token_response.get("scope"),
                    'expires_at': expires_at.isoformat(),
                    'user_info': user_info
                }
            )
        
        logger.info(f"GitHub OAuth completed successfully for user {user_id}")
        
        return jsonify({
            "ok": True,
            "message": "GitHub authentication successful",
            "user": {
                "id": user_info.get("id"),
                "login": user_info.get("login"),
                "name": user_info.get("name"),
                "email": user_info.get("email"),
                "avatar_url": user_info.get("avatar_url")
            },
            "token_info": {
                "scope": token_response.get("scope"),
                "token_type": token_response.get("token_type"),
                "expires_at": expires_at.isoformat()
            }
        })
        
    except Exception as e:
        logger.error(f"GitHub OAuth callback error: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@auth_github_bp.route("/api/auth/github/refresh", methods=["POST"])
async def refresh():
    """Refresh GitHub OAuth tokens (not supported by GitHub)"""
    try:
        data = request.get_json()
        user_id = data.get("user_id")
        refresh_token = data.get("refresh_token")
        
        if not user_id:
            return jsonify({
                "ok": False,
                "error": "User ID is required"
            }), 400
        
        if not refresh_token:
            return jsonify({
                "ok": False,
                "error": "Refresh token is required"
            }), 400
        
        # GitHub doesn't support refresh tokens
        return jsonify({
            "ok": False,
            "error": "GitHub doesn't support token refresh. Please re-authenticate.",
            "requires_reauth": True
        }), 400
        
    except Exception as e:
        logger.error(f"GitHub OAuth refresh error: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@auth_github_bp.route("/api/auth/github/disconnect", methods=["POST"])
async def disconnect():
    """Disconnect GitHub integration"""
    try:
        data = request.get_json()
        user_id = data.get("user_id")
        
        if not user_id:
            return jsonify({
                "ok": False,
                "error": "User ID is required"
            }), 400
        
        # Delete tokens from database
        if GITHUB_DB_AVAILABLE:
            await delete_tokens(None, user_id)  # db_conn_pool - will be passed in production
        
        logger.info(f"GitHub disconnected for user {user_id}")
        
        return jsonify({
            "ok": True,
            "message": "GitHub integration disconnected successfully"
        })
        
    except Exception as e:
        logger.error(f"GitHub OAuth disconnect error: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@auth_github_bp.route("/api/auth/github/webhook/<webhook_id>", methods=["POST"])
async def webhook_handler(webhook_id):
    """Handle GitHub webhooks"""
    try:
        data = request.get_json()
        logger.info(f"GitHub webhook {webhook_id} received: {data}")
        
        # Process webhook events
        event_type = request.headers.get('X-GitHub-Event')
        delivery = request.headers.get('X-GitHub-Delivery')
        
        if not event_type:
            return jsonify({
                "ok": False,
                "error": "Missing X-GitHub-Event header"
            }), 400
        
        # Handle different event types
        if event_type == "push":
            await handle_push_event(data, webhook_id)
        elif event_type == "pull_request":
            await handle_pull_request_event(data, webhook_id)
        elif event_type == "issues":
            await handle_issues_event(data, webhook_id)
        elif event_type == "ping":
            logger.info(f"GitHub webhook ping received for {webhook_id}")
            return jsonify({
                "ok": True,
                "message": "Webhook ping received",
                "delivery": delivery
            })
        else:
            logger.info(f"Unhandled GitHub webhook event: {event_type}")
        
        return jsonify({
            "ok": True,
            "message": f"Webhook event {event_type} processed",
            "delivery": delivery
        })
        
    except Exception as e:
        logger.error(f"GitHub webhook error: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

async def handle_push_event(data: Dict[str, Any], webhook_id: str):
    """Handle GitHub push event"""
    try:
        repository = data.get("repository", {})
        pusher = data.get("pusher", {})
        ref = data.get("ref", "")
        commits = data.get("commits", [])
        
        logger.info(f"GitHub push event: {pusher.get('name')} pushed {len(commits)} commits to {ref}")
        
        # Process push event logic here
        # e.g., trigger CI/CD, update database, send notifications
        
    except Exception as e:
        logger.error(f"Error handling push event: {e}")

async def handle_pull_request_event(data: Dict[str, Any], webhook_id: str):
    """Handle GitHub pull request event"""
    try:
        action = data.get("action", "")
        pull_request = data.get("pull_request", {})
        repository = data.get("repository", {})
        
        logger.info(f"GitHub pull request event: {action} on PR #{pull_request.get('number')}")
        
        # Process pull request event logic here
        # e.g., update Linear issues, notify reviewers, etc.
        
    except Exception as e:
        logger.error(f"Error handling pull request event: {e}")

async def handle_issues_event(data: Dict[str, Any], webhook_id: str):
    """Handle GitHub issues event"""
    try:
        action = data.get("action", "")
        issue = data.get("issue", {})
        repository = data.get("repository", {})
        
        logger.info(f"GitHub issues event: {action} on issue #{issue.get('number')}")
        
        # Process issues event logic here
        # e.g., sync with Linear issues, create notifications, etc.
        
    except Exception as e:
        logger.error(f"Error handling issues event: {e}")

@auth_github_bp.route("/api/auth/github/status", methods=["GET"])
async def status():
    """Get GitHub OAuth status"""
    try:
        return jsonify({
            "ok": True,
            "status": "available",
            "client_id": GITHUB_CLIENT_ID,
            "redirect_uri": GITHUB_REDIRECT_URI,
            "scope": GITHUB_SCOPE,
            "database_available": GITHUB_DB_AVAILABLE,
            "encryption_available": ENCRYPTION_AVAILABLE
        })
        
    except Exception as e:
        logger.error(f"GitHub OAuth status error: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

# Utility functions
async def get_validated_tokens(user_id: str) -> Optional[Dict[str, Any]]:
    """
    Get and validate GitHub tokens for user
    """
    try:
        if not GITHUB_DB_AVAILABLE:
            return None
        
        tokens = await get_tokens(None, user_id)  # db_conn_pool - will be passed in production
        
        if not tokens:
            return None
        
        # Check if token is expired
        expires_at = tokens.get('expires_at')
        if expires_at and is_token_expired(expires_at):
            logger.warning(f"GitHub tokens expired for user {user_id}")
            return None
        
        return tokens
        
    except Exception as e:
        logger.error(f"Error validating GitHub tokens for user {user_id}: {e}")
        return None

async def ensure_valid_tokens(user_id: str) -> Optional[str]:
    """
    Ensure user has valid GitHub tokens, return access token
    """
    try:
        tokens = await get_validated_tokens(user_id)
        
        if not tokens:
            return None
        
        # Decrypt access token if needed
        access_token = tokens.get('access_token')
        if ENCRYPTION_AVAILABLE and isinstance(access_token, bytes):
            access_token = decrypt_data(access_token, ATOM_OAUTH_ENCRYPTION_KEY)
        
        return access_token
        
    except Exception as e:
        logger.error(f"Error ensuring valid GitHub tokens for user {user_id}: {e}")
        return None

# Export for use in other modules
__all__ = [
    'github_auth_manager',
    'auth_github_bp',
    'get_validated_tokens',
    'ensure_valid_tokens'
]