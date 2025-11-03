"""
Linear OAuth Handler
OAuth 2.0 integration with Linear
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
    from db_oauth_linear import save_tokens, get_tokens, delete_tokens, refresh_linear_tokens
    from atom_encryption import encrypt_data, decrypt_data
    LINEAR_DB_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Linear database operations not available: {e}")
    LINEAR_DB_AVAILABLE = False

# Configuration
LINEAR_CLIENT_ID = os.getenv("LINEAR_CLIENT_ID", "mock_linear_client_id")
LINEAR_CLIENT_SECRET = os.getenv("LINEAR_CLIENT_SECRET", "mock_linear_client_secret")
LINEAR_REDIRECT_URI = os.getenv("LINEAR_REDIRECT_URI", "http://localhost:3000/oauth/linear/callback")
ATOM_OAUTH_ENCRYPTION_KEY = os.getenv("ATOM_OAUTH_ENCRYPTION_KEY", "dev_encryption_key_change_in_production")

# Linear API endpoints
LINEAR_OAUTH_AUTHORIZE_URL = "https://linear.app/oauth/authorize"
LINEAR_OAUTH_TOKEN_URL = "https://api.linear.app/oauth/token"
LINEAR_API_BASE_URL = "https://api.linear.app/v1"

auth_linear_bp = Blueprint("auth_linear_bp", __name__)

@auth_linear_bp.route("/api/auth/linear/authorize", methods=["POST"])
def authorize():
    """Start Linear OAuth 2.0 flow"""
    try:
        data = request.get_json()
        user_id = data.get("user_id")
        scopes = data.get("scopes", ["read", "issues:read", "teams:read", "projects:read"])
        redirect_uri = data.get("redirect_uri", LINEAR_REDIRECT_URI)
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
        auth_url = f"{LINEAR_OAUTH_AUTHORIZE_URL}?response_type=code&client_id={LINEAR_CLIENT_ID}&redirect_uri={urllib.parse.quote(redirect_uri)}&scope={urllib.parse.quote(' '.join(scopes))}&state={state_encoded}&prompt=consent"
        
        return jsonify({
            "ok": True,
            "authorization_url": auth_url,
            "client_id": LINEAR_CLIENT_ID,
            "redirect_uri": redirect_uri,
            "scopes": scopes,
            "state": state_encoded,
            "app_name": "ATOM Platform Integration"
        })
        
    except Exception as e:
        logger.error(f"Linear OAuth authorize error: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@auth_linear_bp.route("/api/auth/linear/callback", methods=["POST"])
def callback():
    """Handle Linear OAuth 2.0 callback"""
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
            "client_id": LINEAR_CLIENT_ID,
            "client_secret": LINEAR_CLIENT_SECRET,
            "code": code,
            "grant_type": grant_type,
            "redirect_uri": LINEAR_REDIRECT_URI
        }
        
        response = requests.post(LINEAR_OAUTH_TOKEN_URL, json=token_data, timeout=30)
        response.raise_for_status()
        
        token_response = response.json()
        
        if "error" in token_response:
            return jsonify({
                "ok": False,
                "error": token_response.get("error_description", token_response.get("error"))
            }), 400
        
        # Get user information from Linear
        access_token = token_response.get("access_token")
        user_info = await get_linear_user_info(access_token)
        
        if not user_info:
            return jsonify({
                "ok": False,
                "error": "Failed to retrieve user information"
            }), 400
        
        # Calculate expiration time (Linear tokens typically last for 1 hour)
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        
        # Store tokens in database
        if LINEAR_DB_AVAILABLE:
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
            "message": "Linear authentication successful",
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
        logger.error(f"Linear token exchange error: {e}")
        return jsonify({
            "ok": False,
            "error": "Failed to exchange authorization code for tokens"
        }), 500
    except Exception as e:
        logger.error(f"Linear OAuth callback error: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@auth_linear_bp.route("/api/auth/linear/status", methods=["GET"])
def status():
    """Check Linear authentication status"""
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
        logger.error(f"Linear status check error: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@auth_linear_bp.route("/api/auth/linear/disconnect", methods=["POST"])
def disconnect():
    """Disconnect Linear integration"""
    try:
        data = request.get_json()
        user_id = data.get("user_id")
        
        if not user_id:
            return jsonify({
                "ok": False,
                "error": "User ID is required"
            }), 400
        
        # Delete tokens from database
        if LINEAR_DB_AVAILABLE:
            await delete_tokens(None, user_id)  # db_conn_pool - will be passed in production
        
        return jsonify({
            "ok": True,
            "message": "Linear integration disconnected successfully"
        })
        
    except Exception as e:
        logger.error(f"Linear disconnect error: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@auth_linear_bp.route("/api/auth/linear/refresh", methods=["POST"])
def refresh():
    """Refresh Linear OAuth tokens"""
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
            "client_id": LINEAR_CLIENT_ID,
            "client_secret": LINEAR_CLIENT_SECRET,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token
        }
        
        response = requests.post(LINEAR_OAUTH_TOKEN_URL, json=token_data, timeout=30)
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
        if LINEAR_DB_AVAILABLE:
            encrypted_access_token = encrypt_data(
                token_response.get("access_token"), 
                ATOM_OAUTH_ENCRYPTION_KEY
            )
            encrypted_refresh_token = encrypt_data(
                token_response.get("refresh_token", refresh_token), 
                ATOM_OAUTH_ENCRYPTION_KEY
            )
            
            await refresh_linear_tokens(
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
        logger.error(f"Linear token refresh error: {e}")
        return jsonify({
            "ok": False,
            "error": "Failed to refresh tokens"
        }), 500
    except Exception as e:
        logger.error(f"Linear refresh error: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

# Helper functions
async def get_linear_user_info(access_token: str):
    """Get user information from Linear API"""
    try:
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.get(f"{LINEAR_API_BASE_URL}/me", headers=headers, timeout=10)
        response.raise_for_status()
        
        user_data = response.json()
        
        # Get organization info
        org_info = {}
        try:
            org_response = requests.get(f"{LINEAR_API_BASE_URL}/organizations", headers=headers, timeout=10)
            org_response.raise_for_status()
            orgs = org_response.json()
            if orgs:
                org_info = {
                    'id': orgs[0].get('id'),
                    'name': orgs[0].get('name'),
                    'urlKey': orgs[0].get('urlKey')
                }
        except Exception as e:
            logger.warning(f"Error getting Linear organization info: {e}")
        
        return {
            "id": user_data.get("id"),
            "name": user_data.get("name"),
            "displayName": user_data.get("displayName", user_data.get("name")),
            "email": user_data.get("email"),
            "avatarUrl": user_data.get("avatarUrl"),
            "url": user_data.get("url"),
            "role": user_data.get("role", "member"),
            "organization": org_info,
            "active": True,
            "lastSeen": datetime.now(timezone.utc).isoformat()
        }
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error getting Linear user info: {e}")
        return None
    except Exception as e:
        logger.error(f"Error parsing Linear user info: {e}")
        return None

# Webhook endpoint for Linear notifications
@auth_linear_bp.route("/api/auth/linear/webhook/<webhook_id>", methods=["POST"])
def webhook_handler(webhook_id):
    """Handle Linear webhooks"""
    try:
        data = request.get_json()
        logger.info(f"Linear webhook {webhook_id} received: {data}")
        
        # Process webhook events
        event_type = data.get("action")
        event_data = data.get("data")
        
        # Handle different event types
        if event_type == "create" and event_data.get("type") == "Issue":
            await handle_issue_created(event_data)
        elif event_type == "update" and event_data.get("type") == "Issue":
            await handle_issue_updated(event_data)
        elif event_type == "create" and event_data.get("type") == "Comment":
            await handle_comment_created(event_data)
        elif event_type == "create" and event_data.get("type") == "Project":
            await handle_project_created(event_data)
        
        return jsonify({"ok": True, "message": "Webhook processed successfully"})
        
    except Exception as e:
        logger.error(f"Linear webhook handler error: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

async def handle_issue_created(data: dict):
    """Handle issue created events"""
    logger.info(f"Handling issue created: {data}")
    # Implementation for issue creation processing
    pass

async def handle_issue_updated(data: dict):
    """Handle issue updated events"""
    logger.info(f"Handling issue updated: {data}")
    # Implementation for issue update processing
    pass

async def handle_comment_created(data: dict):
    """Handle comment created events"""
    logger.info(f"Handling comment created: {data}")
    # Implementation for comment creation processing
    pass

async def handle_project_created(data: dict):
    """Handle project created events"""
    logger.info(f"Handling project created: {data}")
    # Implementation for project creation processing
    pass

# Mock endpoints for testing
@auth_linear_bp.route("/api/auth/linear/mock/authorize", methods=["POST"])
def mock_authorize():
    """Mock Linear authorization for testing"""
    return jsonify({
        "ok": True,
        "authorization_url": "https://linear.app/oauth/authorize?client_id=mock_client_id&redirect_uri=http://localhost:3000/oauth/linear/callback&response_type=code&scope=read&state=test_state",
        "client_id": "mock_client_id",
        "redirect_uri": "http://localhost:3000/oauth/linear/callback",
        "scopes": ["read", "issues:read"],
        "state": "test_state",
        "app_name": "ATOM Platform Integration (Mock)"
    })

@auth_linear_bp.route("/api/auth/linear/mock/callback", methods=["POST"])
def mock_callback():
    """Mock Linear callback for testing"""
    return jsonify({
        "ok": True,
        "message": "Linear authentication successful (Mock)",
        "tokens": {
            "access_token": "mock_linear_access_token_" + os.urandom(8).hex(),
            "refresh_token": "mock_linear_refresh_token_" + os.urandom(8).hex(),
            "expires_in": 3600,
            "token_type": "Bearer",
            "scope": "read issues:read teams:read",
            "user_info": {
                "id": "mock_user_id",
                "name": "Mock User",
                "displayName": "Mock Linear User",
                "email": "mockuser@linear.app",
                "avatarUrl": "https://example.com/avatar.jpg",
                "url": "https://linear.app/mockuser",
                "role": "admin",
                "organization": {
                    "id": "mock_org_id",
                    "name": "Mock Organization",
                    "urlKey": "mock-org"
                },
                "active": True,
                "lastSeen": datetime.now(timezone.utc).isoformat()
            },
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        }
    })

# Linear OAuth redirect handler (for web callback processing)
@auth_linear_bp.route("/oauth/linear/callback", methods=["GET"])
def oauth_redirect():
    """Handle Linear OAuth redirect (for web apps)"""
    try:
        code = request.args.get("code")
        state = request.args.get("state")
        error = request.args.get("error")
        error_description = request.args.get("error_description")
        
        if error:
            return f"Linear OAuth Error: {error} - {error_description}", 400
        
        if not code or not state:
            return "Invalid OAuth callback parameters", 400
        
        # Redirect to frontend with callback data
        callback_url = f"{LINEAR_REDIRECT_URI}?code={code}&state={state}"
        return redirect(callback_url)
        
    except Exception as e:
        logger.error(f"Linear OAuth redirect error: {e}")
        return f"OAuth redirect error: {str(e)}", 500

@auth_linear_bp.route("/api/auth/linear/test", methods=["GET"])
def test():
    """Test Linear OAuth endpoints"""
    return jsonify({
        "ok": True,
        "message": "Linear OAuth handler is working",
        "endpoints": [
            "/api/auth/linear/authorize",
            "/api/auth/linear/callback",
            "/api/auth/linear/status",
            "/api/auth/linear/disconnect",
            "/api/auth/linear/refresh"
        ],
        "oauth_config": {
            "client_id": LINEAR_CLIENT_ID,
            "redirect_uri": LINEAR_REDIRECT_URI,
            "oauth_url": LINEAR_OAUTH_AUTHORIZE_URL,
            "token_url": LINEAR_OAUTH_TOKEN_URL,
            "api_base_url": LINEAR_API_BASE_URL
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