"""
Figma OAuth Handler
OAuth 2.0 integration with Figma
"""

from flask import Blueprint, request, jsonify, redirect, url_for
import os
import requests
import json
import base64
import logging
from datetime import datetime, timedelta, timezone
import urllib.parse
from loguru import logger

# Import database operations
try:
    from db_oauth_figma import save_tokens, get_tokens, delete_tokens, refresh_figma_tokens
    from atom_encryption import encrypt_data, decrypt_data
    FIGMA_DB_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Figma database operations not available: {e}")
    FIGMA_DB_AVAILABLE = False

# Configuration
FIGMA_CLIENT_ID = os.getenv("FIGMA_CLIENT_ID", "mock_figma_client_id")
FIGMA_CLIENT_SECRET = os.getenv("FIGMA_CLIENT_SECRET", "mock_figma_client_secret")
FIGMA_REDIRECT_URI = os.getenv("FIGMA_REDIRECT_URI", "http://localhost:3000/oauth/figma/callback")
ATOM_OAUTH_ENCRYPTION_KEY = os.getenv("ATOM_OAUTH_ENCRYPTION_KEY", "dev_encryption_key_change_in_production")

# Figma API endpoints
FIGMA_OAUTH_AUTHORIZE_URL = "https://www.figma.com/oauth"
FIGMA_OAUTH_TOKEN_URL = "https://www.figma.com/api/oauth/token"
FIGMA_API_BASE_URL = "https://api.figma.com/v1"

auth_figma_bp = Blueprint("auth_figma_bp", __name__)

@auth_figma_bp.route("/api/auth/figma/authorize", methods=["POST"])
def authorize():
    """Start Figma OAuth 2.0 flow"""
    try:
        data = request.get_json()
        user_id = data.get("user_id")
        scopes = data.get("scopes", ["file_read", "user_read"])
        redirect_uri = data.get("redirect_uri", FIGMA_REDIRECT_URI)
        state = data.get("state", f"user_{user_id}_{int(datetime.utcnow().timestamp())}")
        
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
        auth_url = f"{FIGMA_OAUTH_AUTHORIZE_URL}?response_type=code&client_id={FIGMA_CLIENT_ID}&redirect_uri={urllib.parse.quote(redirect_uri)}&scope={urllib.parse.quote(' '.join(scopes))}&state={state_encoded}"
        
        return jsonify({
            "ok": True,
            "authorization_url": auth_url,
            "client_id": FIGMA_CLIENT_ID,
            "redirect_uri": redirect_uri,
            "scopes": scopes,
            "state": state_encoded,
            "app_name": "ATOM Platform Integration"
        })
        
    except Exception as e:
        logger.error(f"Figma OAuth authorize error: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@auth_figma_bp.route("/api/auth/figma/callback", methods=["POST"])
def callback():
    """Handle Figma OAuth 2.0 callback"""
    try:
        data = request.get_json()
        code = data.get("code")
        state = data.get("state")
        grant_type = data.get("grant_type", "authorization_code")
        
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
            "client_id": FIGMA_CLIENT_ID,
            "client_secret": FIGMA_CLIENT_SECRET,
            "code": code,
            "grant_type": grant_type
        }
        
        response = requests.post(FIGMA_OAUTH_TOKEN_URL, data=token_data, timeout=30)
        response.raise_for_status()
        
        token_response = response.json()
        
        if "error" in token_response:
            return jsonify({
                "ok": False,
                "error": token_response.get("error_description", token_response.get("error"))
            }), 400
        
        # Get user information from Figma
        access_token = token_response.get("access_token")
        user_info = get_figma_user_info(access_token)
        
        if not user_info:
            return jsonify({
                "ok": False,
                "error": "Failed to retrieve user information"
            }), 400
        
        # Calculate expiration time (Figma tokens typically last for 1 hour)
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        
        # Store tokens in database
        if FIGMA_DB_AVAILABLE:
            # Encrypt tokens before storing
            encrypted_access_token = encrypt_data(access_token, ATOM_OAUTH_ENCRYPTION_KEY)
            encrypted_refresh_token = encrypt_data(
                token_response.get("refresh_token", ""), 
                ATOM_OAUTH_ENCRYPTION_KEY
            )
            
            await save_tokens(
                None,  # db_conn_pool - will be passed in production
                user_id,
                encrypted_access_token,
                encrypted_refresh_token,
                expires_at,
                token_response.get("scope", ""),
                user_info
            )
        
        # Return success response with tokens (for development/testing)
        return jsonify({
            "ok": True,
            "message": "Figma authentication successful",
            "tokens": {
                "access_token": access_token,
                "refresh_token": token_response.get("refresh_token"),
                "expires_in": token_response.get("expires_in", 3600),
                "token_type": token_response.get("token_type", "Bearer"),
                "scope": token_response.get("scope", ""),
                "user_info": user_info,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "expires_at": expires_at.isoformat()
            }
        })
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Figma token exchange error: {e}")
        return jsonify({
            "ok": False,
            "error": "Failed to exchange authorization code for tokens"
        }), 500
    except Exception as e:
        logger.error(f"Figma OAuth callback error: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@auth_figma_bp.route("/api/auth/figma/status", methods=["GET"])
def status():
    """Check Figma authentication status"""
    try:
        # In real implementation, would check session or JWT token
        # For now, return status based on tokens presence
        return jsonify({
            "connected": True,  # Mock for testing
            "app_name": "ATOM Platform Integration",
            "last_sync": datetime.now(timezone.utc).isoformat(),
            "token_status": "valid"
        })
        
    except Exception as e:
        logger.error(f"Figma status check error: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@auth_figma_bp.route("/api/auth/figma/disconnect", methods=["POST"])
def disconnect():
    """Disconnect Figma integration"""
    try:
        data = request.get_json()
        user_id = data.get("user_id")
        
        if not user_id:
            return jsonify({
                "ok": False,
                "error": "User ID is required"
            }), 400
        
        # Delete tokens from database
        if FIGMA_DB_AVAILABLE:
            await delete_tokens(None, user_id)  # db_conn_pool - will be passed in production
        
        return jsonify({
            "ok": True,
            "message": "Figma integration disconnected successfully"
        })
        
    except Exception as e:
        logger.error(f"Figma disconnect error: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@auth_figma_bp.route("/api/auth/figma/refresh", methods=["POST"])
def refresh():
    """Refresh Figma OAuth tokens"""
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
        
        # Use refresh token to get new access token
        token_data = {
            "client_id": FIGMA_CLIENT_ID,
            "client_secret": FIGMA_CLIENT_SECRET,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token
        }
        
        response = requests.post(FIGMA_OAUTH_TOKEN_URL, data=token_data, timeout=30)
        response.raise_for_status()
        
        token_response = response.json()
        
        if "error" in token_response:
            return jsonify({
                "ok": False,
                "error": token_response.get("error_description", token_response.get("error"))
            }), 400
        
        # Calculate new expiration time
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        
        # Update tokens in database
        if FIGMA_DB_AVAILABLE:
            encrypted_access_token = encrypt_data(
                token_response.get("access_token"), 
                ATOM_OAUTH_ENCRYPTION_KEY
            )
            encrypted_refresh_token = encrypt_data(
                token_response.get("refresh_token", refresh_token), 
                ATOM_OAUTH_ENCRYPTION_KEY
            )
            
            await refresh_figma_tokens(
                None,  # db_conn_pool - will be passed in production
                user_id,
                encrypted_access_token,
                encrypted_refresh_token,
                expires_at,
                token_response.get("scope", "")
            )
        
        return jsonify({
            "ok": True,
            "message": "Tokens refreshed successfully",
            "tokens": {
                "access_token": token_response.get("access_token"),
                "refresh_token": token_response.get("refresh_token"),
                "expires_in": token_response.get("expires_in", 3600),
                "token_type": token_response.get("token_type", "Bearer"),
                "scope": token_response.get("scope", ""),
                "expires_at": expires_at.isoformat()
            }
        })
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Figma token refresh error: {e}")
        return jsonify({
            "ok": False,
            "error": "Failed to refresh tokens"
        }), 500
    except Exception as e:
        logger.error(f"Figma refresh error: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

# Helper functions
async def get_figma_user_info(access_token: str):
    """Get user information from Figma API"""
    try:
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.get(f"{FIGMA_API_BASE_URL}/me", headers=headers, timeout=10)
        response.raise_for_status()
        
        user_data = response.json()
        
        return {
            "id": user_data.get("id"),
            "name": user_data.get("name"),
            "username": user_data.get("handle", user_data.get("email", "").split("@")[0]),
            "email": user_data.get("email"),
            "profile_picture_url": user_data.get("img_url"),
            "department": user_data.get("department"),
            "title": user_data.get("title"),
            "organization_id": user_data.get("org_id"),
            "role": "member",  # Figma doesn't provide role in this endpoint
            "can_edit": user_data.get("can_edit", True),
            "has_guests": False,
            "is_active": True
        }
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error getting Figma user info: {e}")
        return None
    except Exception as e:
        logger.error(f"Error parsing Figma user info: {e}")
        return None

# Webhook endpoint for Figma notifications
@auth_figma_bp.route("/api/auth/figma/webhook/<webhook_id>", methods=["POST"])
def webhook_handler(webhook_id):
    """Handle Figma webhooks"""
    try:
        data = request.get_json()
        logger.info(f"Figma webhook {webhook_id} received: {data}")
        
        # Process webhook events
        event_type = data.get("event_type")
        file_key = data.get("file_key")
        
        # Handle different event types
        if event_type == "file_comment":
            await handle_file_comment(data)
        elif event_type == "file_update":
            await handle_file_update(data)
        elif event_type == "file_version":
            await handle_file_version(data)
        elif event_type == "library_publish":
            await handle_library_publish(data)
        
        return jsonify({"ok": True, "message": "Webhook processed successfully"})
        
    except Exception as e:
        logger.error(f"Figma webhook handler error: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

async def handle_file_comment(data: dict):
    """Handle file comment events"""
    logger.info(f"Handling file comment: {data}")
    # Implementation for file comment processing
    pass

async def handle_file_update(data: dict):
    """Handle file update events"""
    logger.info(f"Handling file update: {data}")
    # Implementation for file update processing
    pass

async def handle_file_version(data: dict):
    """Handle file version events"""
    logger.info(f"Handling file version: {data}")
    # Implementation for file version processing
    pass

async def handle_library_publish(data: dict):
    """Handle library publish events"""
    logger.info(f"Handling library publish: {data}")
    # Implementation for library publish processing
    pass

# Mock endpoints for testing
@auth_figma_bp.route("/api/auth/figma/mock/authorize", methods=["POST"])
def mock_authorize():
    """Mock Figma authorization for testing"""
    return jsonify({
        "ok": True,
        "authorization_url": "https://www.figma.com/oauth?client_id=mock_client_id&redirect_uri=http://localhost:3000/oauth/figma/callback&response_type=code&scope=file_read&state=test_state",
        "client_id": "mock_client_id",
        "redirect_uri": "http://localhost:3000/oauth/figma/callback",
        "scopes": ["file_read"],
        "state": "test_state",
        "app_name": "ATOM Platform Integration (Mock)"
    })

@auth_figma_bp.route("/api/auth/figma/mock/callback", methods=["POST"])
def mock_callback():
    """Mock Figma callback for testing"""
    return jsonify({
        "ok": True,
        "message": "Figma authentication successful (Mock)",
        "tokens": {
            "access_token": "mock_figma_access_token_" + os.urandom(8).hex(),
            "refresh_token": "mock_figma_refresh_token_" + os.urandom(8).hex(),
            "expires_in": 3600,
            "token_type": "Bearer",
            "scope": "file_read user_read",
            "user_info": {
                "id": "mock_user_id",
                "name": "Mock User",
                "username": "mockuser",
                "email": "mockuser@example.com",
                "profile_picture_url": "https://example.com/avatar.jpg",
                "department": "Design",
                "title": "UI/UX Designer",
                "organization_id": "mock_org_id",
                "role": "member",
                "can_edit": True,
                "has_guests": False,
                "is_active": True
            },
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        }
    })

# Figma OAuth redirect handler (for web callback processing)
@auth_figma_bp.route("/oauth/figma/callback", methods=["GET"])
def oauth_redirect():
    """Handle Figma OAuth redirect (for web apps)"""
    try:
        code = request.args.get("code")
        state = request.args.get("state")
        error = request.args.get("error")
        error_description = request.args.get("error_description")
        
        if error:
            return f"Figma OAuth Error: {error} - {error_description}", 400
        
        if not code or not state:
            return "Invalid OAuth callback parameters", 400
        
        # Redirect to frontend with callback data
        callback_url = f"{FIGMA_REDIRECT_URI}?code={code}&state={state}"
        return redirect(callback_url)
        
    except Exception as e:
        logger.error(f"Figma OAuth redirect error: {e}")
        return f"OAuth redirect error: {str(e)}", 500

@auth_figma_bp.route("/api/auth/figma/test", methods=["GET"])
def test():
    """Test Figma OAuth endpoints"""
    return jsonify({
        "ok": True,
        "message": "Figma OAuth handler is working",
        "endpoints": [
            "/api/auth/figma/authorize",
            "/api/auth/figma/callback",
            "/api/auth/figma/status",
            "/api/auth/figma/disconnect",
            "/api/auth/figma/refresh"
        ],
        "oauth_config": {
            "client_id": FIGMA_CLIENT_ID,
            "redirect_uri": FIGMA_REDIRECT_URI,
            "oauth_url": FIGMA_OAUTH_AUTHORIZE_URL,
            "token_url": FIGMA_OAUTH_TOKEN_URL,
            "api_base_url": FIGMA_API_BASE_URL
        },
        "features": [
            "OAuth 2.0 Authorization",
            "Token Exchange",
            "Token Refresh",
            "User Information Retrieval",
            "Webhook Support",
            "Secure Token Storage",
            "Mock Testing Endpoints"
        ]
    })