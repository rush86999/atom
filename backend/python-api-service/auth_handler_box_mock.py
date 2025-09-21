import os
import logging
from flask import Blueprint, request, redirect, session, jsonify, url_for
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

box_auth_bp = Blueprint('box_auth_bp', __name__)

# Mock OAuth2 class for development
class MockOAuth2:
    """Mock OAuth2 class for Box authentication"""
    def __init__(self, client_id: str = "mock_client_id", client_secret: str = "mock_client_secret"):
        self.client_id = client_id
        self.client_secret = client_secret
        logger.warning("Using mock Box OAuth2 - real Box authentication disabled")

    def get_authorization_url(self, redirect_url: str) -> str:
        """Mock authorization URL generation"""
        return f"https://mock-box.com/oauth2/authorize?client_id={self.client_id}&response_type=code&redirect_uri={redirect_url}"

    def authenticate(self, authorization_code: str) -> Dict[str, Any]:
        """Mock authentication"""
        return {
            "access_token": "mock_box_access_token_123",
            "refresh_token": "mock_box_refresh_token_456",
            "expires_in": 3600,
            "token_type": "bearer"
        }

    def refresh(self, refresh_token: str) -> Dict[str, Any]:
        """Mock token refresh"""
        return {
            "access_token": "refreshed_mock_access_token_789",
            "refresh_token": "refreshed_mock_refresh_token_012",
            "expires_in": 3600,
            "token_type": "bearer"
        }

# Mock database functions for development
def mock_save_box_tokens(user_id: str, access_token: str, refresh_token: str, expires_at: int) -> bool:
    """Mock token saving"""
    logger.info(f"Mock saving Box tokens for user {user_id}")
    return True

def mock_get_box_tokens(user_id: str) -> Optional[Dict[str, Any]]:
    """Mock token retrieval"""
    logger.info(f"Mock retrieving Box tokens for user {user_id}")
    return {
        "access_token": "mock_stored_access_token",
        "refresh_token": "mock_stored_refresh_token",
        "expires_at": int(datetime.now(timezone.utc).timestamp()) + 3600
    }

def mock_delete_box_tokens(user_id: str) -> bool:
    """Mock token deletion"""
    logger.info(f"Mock deleting Box tokens for user {user_id}")
    return True

@box_auth_bp.route('/auth/box/url', methods=['GET'])
def get_box_auth_url():
    """Get Box OAuth2 authorization URL"""
    try:
        redirect_uri = request.args.get('redirect_uri', 'http://localhost:3000/auth/callback/box')
        client_id = os.getenv('BOX_CLIENT_ID', 'mock_client_id')
        client_secret = os.getenv('BOX_CLIENT_SECRET', 'mock_client_secret')

        oauth = MockOAuth2(client_id, client_secret)
        auth_url = oauth.get_authorization_url(redirect_uri)

        return jsonify({
            "success": True,
            "auth_url": auth_url,
            "is_mock": True,
            "message": "Box authentication running in mock mode"
        })

    except Exception as e:
        logger.error(f"Error generating Box auth URL: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
            "is_mock": True
        }), 500

@box_auth_bp.route('/auth/box/callback', methods=['GET'])
def box_oauth_callback():
    """Handle Box OAuth2 callback"""
    try:
        code = request.args.get('code')
        state = request.args.get('state')

        if not code:
            return jsonify({
                "success": False,
                "error": "Authorization code not provided",
                "is_mock": True
            }), 400

        # Mock authentication
        oauth = MockOAuth2()
        tokens = oauth.authenticate(code)

        # In a real implementation, you would get the user ID from the session or JWT
        user_id = "mock_user_id"

        # Calculate expiration time
        expires_at = int(datetime.now(timezone.utc).timestamp()) + tokens['expires_in']

        # Save tokens (mock implementation)
        success = mock_save_box_tokens(
            user_id=user_id,
            access_token=tokens['access_token'],
            refresh_token=tokens['refresh_token'],
            expires_at=expires_at
        )

        if success:
            return jsonify({
                "success": True,
                "message": "Box authentication successful",
                "user_id": user_id,
                "access_token": tokens['access_token'],
                "expires_in": tokens['expires_in'],
                "is_mock": True
            })
        else:
            return jsonify({
                "success": False,
                "error": "Failed to save authentication tokens",
                "is_mock": True
            }), 500

    except Exception as e:
        logger.error(f"Error in Box OAuth callback: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
            "is_mock": True
        }), 500

@box_auth_bp.route('/auth/box/tokens', methods=['GET'])
def get_box_tokens():
    """Get stored Box tokens for current user"""
    try:
        # In a real implementation, you would get the user ID from the session or JWT
        user_id = "mock_user_id"

        tokens = mock_get_box_tokens(user_id)

        if tokens:
            return jsonify({
                "success": True,
                "data": tokens,
                "is_mock": True
            })
        else:
            return jsonify({
                "success": False,
                "error": "No Box tokens found for user",
                "is_mock": True
            }), 404

    except Exception as e:
        logger.error(f"Error getting Box tokens: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
            "is_mock": True
        }), 500

@box_auth_bp.route('/auth/box/disconnect', methods=['POST'])
def disconnect_box():
    """Disconnect Box integration"""
    try:
        # In a real implementation, you would get the user ID from the session or JWT
        user_id = "mock_user_id"

        success = mock_delete_box_tokens(user_id)

        if success:
            return jsonify({
                "success": True,
                "message": "Box integration disconnected successfully",
                "is_mock": True
            })
        else:
            return jsonify({
                "success": False,
                "error": "Failed to disconnect Box integration",
                "is_mock": True
            }), 500

    except Exception as e:
        logger.error(f"Error disconnecting Box: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
            "is_mock": True
        }), 500

@box_auth_bp.route('/auth/box/status', methods=['GET'])
def get_box_auth_status():
    """Get Box authentication status"""
    try:
        # In a real implementation, you would get the user ID from the session or JWT
        user_id = "mock_user_id"

        tokens = mock_get_box_tokens(user_id)
        is_connected = tokens is not None

        return jsonify({
            "success": True,
            "connected": is_connected,
            "is_mock": True,
            "message": "Box authentication status check completed"
        })

    except Exception as e:
        logger.error(f"Error checking Box auth status: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
            "is_mock": True
        }), 500

logger.info("Box mock auth handler initialized successfully")
