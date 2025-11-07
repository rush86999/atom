"""
OneDrive OAuth 2.0 Authentication Handler

This module provides OAuth 2.0 authentication for Microsoft OneDrive integration
using Microsoft Graph API and Azure AD authentication.
"""

import os
import logging
import secrets
import asyncio
from typing import Dict, Any, Optional
from urllib.parse import urlencode
from flask import Blueprint, request, redirect, session, jsonify, url_for
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

# Create blueprint for OneDrive authentication
onedrive_auth_bp = Blueprint("onedrive_auth", __name__)

# Microsoft Graph API configuration
MICROSOFT_AUTHORITY = "https://login.microsoftonline.com/common"
MICROSOFT_AUTH_ENDPOINT = f"{MICROSOFT_AUTHORITY}/oauth2/v2.0/authorize"
MICROSOFT_TOKEN_ENDPOINT = f"{MICROSOFT_AUTHORITY}/oauth2/v2.0/token"
MICROSOFT_GRAPH_SCOPE = (
    "https://graph.microsoft.com/Files.ReadWrite.All offline_access User.Read"
)

# OAuth configuration from environment
ONEDRIVE_CLIENT_ID = os.getenv("ONEDRIVE_CLIENT_ID")
ONEDRIVE_CLIENT_SECRET = os.getenv("ONEDRIVE_CLIENT_SECRET")
ONEDRIVE_REDIRECT_URI = os.getenv(
    "ONEDRIVE_REDIRECT_URI", "http://localhost:5058/api/auth/onedrive/callback"
)

# In-memory storage for OAuth state (in production, use database)
_oauth_states = {}


class OneDriveAuthService:
    """Service for handling OneDrive OAuth authentication"""

    def __init__(self):
        self.client_id = ONEDRIVE_CLIENT_ID
        self.client_secret = ONEDRIVE_CLIENT_SECRET
        self.redirect_uri = ONEDRIVE_REDIRECT_URI

    def generate_auth_url(self, state: str) -> str:
        """Generate Microsoft OAuth authorization URL"""
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": self.redirect_uri,
            "scope": MICROSOFT_GRAPH_SCOPE,
            "state": state,
            "response_mode": "query",
        }

        return f"{MICROSOFT_AUTH_ENDPOINT}?{urlencode(params)}"

    async def exchange_code_for_tokens(self, code: str) -> Dict[str, Any]:
        """Exchange authorization code for access and refresh tokens"""
        try:
            data = {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "code": code,
                "redirect_uri": self.redirect_uri,
                "grant_type": "authorization_code",
            }

            headers = {"Content-Type": "application/x-www-form-urlencoded"}

            response = requests.post(
                MICROSOFT_TOKEN_ENDPOINT, data=data, headers=headers
            )
            response.raise_for_status()

            token_data = response.json()

            return {
                "access_token": token_data.get("access_token"),
                "refresh_token": token_data.get("refresh_token"),
                "expires_in": token_data.get("expires_in"),
                "scope": token_data.get("scope"),
                "token_type": token_data.get("token_type"),
            }

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to exchange code for tokens: {e}")
            raise

    async def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        """Refresh access token using refresh token"""
        try:
            data = {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            }

            headers = {"Content-Type": "application/x-www-form-urlencoded"}

            response = requests.post(
                MICROSOFT_TOKEN_ENDPOINT, data=data, headers=headers
            )
            response.raise_for_status()

            token_data = response.json()

            return {
                "access_token": token_data.get("access_token"),
                "refresh_token": token_data.get("refresh_token", refresh_token),
                "expires_in": token_data.get("expires_in"),
                "scope": token_data.get("scope"),
                "token_type": token_data.get("token_type"),
            }

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to refresh access token: {e}")
            raise

    async def get_user_info(self, access_token: str) -> Dict[str, Any]:
        """Get user information from Microsoft Graph API"""
        try:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            }

            # Get user profile
            user_response = requests.get(
                "https://graph.microsoft.com/v1.0/me", headers=headers
            )
            user_response.raise_for_status()
            user_data = user_response.json()

            # Get drive information
            drive_response = requests.get(
                "https://graph.microsoft.com/v1.0/me/drive", headers=headers
            )
            drive_data = (
                drive_response.json() if drive_response.status_code == 200 else {}
            )

            return {
                "user_id": user_data.get("id"),
                "email": user_data.get("mail") or user_data.get("userPrincipalName"),
                "display_name": user_data.get("displayName"),
                "drive_id": drive_data.get("id"),
                "drive_type": drive_data.get("driveType"),
                "quota": drive_data.get("quota", {}),
            }

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get user info: {e}")
            raise


# Global auth service instance
_auth_service = OneDriveAuthService()


@onedrive_auth_bp.route("/onedrive/authorize")
async def start_auth():
    """Initiate OneDrive OAuth flow"""
    try:
        # Generate state parameter for CSRF protection
        state = secrets.token_urlsafe(32)
        _oauth_states[state] = True

        # Generate authorization URL
        auth_url = _auth_service.generate_auth_url(state)

        return redirect(auth_url)

    except Exception as e:
        logger.error(f"Error starting OneDrive auth: {e}")
        return jsonify(
            {"error": "Failed to initiate OneDrive authentication", "message": str(e)}
        ), 500


@onedrive_auth_bp.route("/onedrive/callback")
async def complete_auth():
    """Handle OAuth callback from Microsoft"""
    try:
        # Get parameters from callback
        code = request.args.get("code")
        state = request.args.get("state")
        error = request.args.get("error")

        # Check for errors
        if error:
            error_description = request.args.get("error_description", "Unknown error")
            logger.error(f"OneDrive OAuth error: {error} - {error_description}")
            return jsonify(
                {
                    "error": "OneDrive authentication failed",
                    "message": error_description,
                }
            ), 400

        # Validate state parameter
        if not state or state not in _oauth_states:
            logger.error("Invalid or missing state parameter")
            return jsonify(
                {
                    "error": "Invalid authentication state",
                    "message": "Security validation failed",
                }
            ), 400

        # Remove used state
        del _oauth_states[state]

        if not code:
            logger.error("Missing authorization code")
            return jsonify(
                {
                    "error": "Missing authorization code",
                    "message": "No authorization code received",
                }
            ), 400

        # Exchange code for tokens
        tokens = await _auth_service.exchange_code_for_tokens(code)

        # Get user information
        user_info = await _auth_service.get_user_info(tokens["access_token"])

        # Store tokens and user info (in production, store in database)
        # For now, we'll return them in the response
        auth_result = {
            "status": "success",
            "message": "OneDrive connected successfully",
            "user": user_info,
            "tokens": {
                "access_token": tokens["access_token"],
                "refresh_token": tokens["refresh_token"],
                "expires_in": tokens["expires_in"],
                "scope": tokens["scope"],
            },
        }

        logger.info(
            f"OneDrive authentication successful for user: {user_info.get('email')}"
        )

        # In a real implementation, you would:
        # 1. Store tokens in database associated with user
        # 2. Create session or return JWT
        # 3. Redirect to frontend with success message

        return jsonify(auth_result)

    except Exception as e:
        logger.error(f"Error completing OneDrive auth: {e}")
        return jsonify(
            {"error": "Failed to complete OneDrive authentication", "message": str(e)}
        ), 500


@onedrive_auth_bp.route("/onedrive/disconnect", methods=["POST"])
async def disconnect():
    """Disconnect OneDrive integration"""
    try:
        # In a real implementation, you would:
        # 1. Remove tokens from database
        # 2. Revoke tokens with Microsoft
        # 3. Clean up any related data

        logger.info("OneDrive integration disconnected")

        return jsonify(
            {"status": "success", "message": "OneDrive disconnected successfully"}
        )

    except Exception as e:
        logger.error(f"Error disconnecting OneDrive: {e}")
        return jsonify(
            {"error": "Failed to disconnect OneDrive", "message": str(e)}
        ), 500


@onedrive_auth_bp.route("/onedrive/status")
async def get_status():
    """Get OneDrive connection status"""
    try:
        # In a real implementation, you would:
        # 1. Check if tokens exist in database
        # 2. Validate tokens with Microsoft
        # 3. Return connection status

        # For now, return not connected status
        return jsonify({"is_connected": False, "message": "OneDrive not connected"})

    except Exception as e:
        logger.error(f"Error getting OneDrive status: {e}")
        return jsonify(
            {"error": "Failed to get OneDrive status", "message": str(e)}
        ), 500


def init_onedrive_oauth_table():
    """Initialize OneDrive OAuth database table (placeholder for future implementation)"""
    # This would create the necessary database tables for storing OAuth tokens
    # For now, it's a placeholder
    logger.info("OneDrive OAuth table initialization would happen here")
    return True

