#!/usr/bin/env python3
"""
GitHub OAuth API Implementation
Follows established Jira integration pattern
"""

import os
import logging
import secrets
from flask import Blueprint, request, jsonify, session, current_app
from urllib.parse import urlencode
import httpx
import json
from datetime import datetime, timedelta
from crypto_utils import encrypt_message, decrypt_message
from db_oauth_github import save_tokens, get_tokens, delete_tokens

logger = logging.getLogger(__name__)

github_oauth_bp = Blueprint("github_oauth_bp", __name__)

# Configuration
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")
GITHUB_REDIRECT_URI = os.getenv(
    "GITHUB_REDIRECT_URI", "http://localhost:5059/api/auth/github/callback"
)
GITHUB_SCOPES = "repo,user,read:org,read:project"


@github_oauth_bp.route("/api/auth/github/start")
async def github_auth_start():
    """Start GitHub OAuth flow"""
    try:
        user_id = request.args.get("user_id")
        if not user_id:
            return jsonify({"ok": False, "error": "user_id required"}), 400

        # Generate state and store in session
        state = secrets.token_urlsafe(32)
        session["github_oauth_state"] = state
        session["github_oauth_user_id"] = user_id

        # Build authorization URL
        auth_params = {
            "client_id": GITHUB_CLIENT_ID,
            "redirect_uri": GITHUB_REDIRECT_URI,
            "scope": GITHUB_SCOPES,
            "state": state,
            "allow_signup": "false",
        }

        auth_url = f"https://github.com/oauth/authorize?{urlencode(auth_params)}"

        return jsonify({"ok": True, "auth_url": auth_url, "state": state})

    except Exception as e:
        logger.error(f"GitHub OAuth start error: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@github_oauth_bp.route("/api/auth/github/callback")
async def github_auth_callback():
    """Handle GitHub OAuth callback"""
    try:
        code = request.args.get("code")
        state = request.args.get("state")
        error = request.args.get("error")

        if error:
            logger.error(f"GitHub OAuth callback error: {error}")
            return jsonify({"ok": False, "error": f"OAuth error: {error}"}), 400

        if not code:
            return jsonify({"ok": False, "error": "Authorization code required"}), 400

        # Verify state
        if state != session.get("github_oauth_state"):
            return jsonify({"ok": False, "error": "Invalid state parameter"}), 400

        user_id = session.get("github_oauth_user_id")
        if not user_id:
            return jsonify({"ok": False, "error": "No user_id found in session"}), 400

        # Exchange code for access token
        token_url = "https://github.com/oauth/access_token"
        token_data = {
            "client_id": GITHUB_CLIENT_ID,
            "client_secret": GITHUB_CLIENT_SECRET,
            "code": code,
            "redirect_uri": GITHUB_REDIRECT_URI,
        }

        headers = {"Accept": "application/json", "Content-Type": "application/json"}

        async with httpx.AsyncClient() as client:
            response = await client.post(token_url, json=token_data, headers=headers)

            if response.status_code != 200:
                logger.error(f"GitHub token exchange failed: {response.text}")
                return jsonify({"ok": False, "error": "Token exchange failed"}), 400

            token_response = response.json()
            access_token = token_response.get("access_token")

            if not access_token:
                return jsonify({"ok": False, "error": "No access token received"}), 400

            # Get user info to verify connection
            user_info = await get_github_user_info(access_token)

            # Encrypt and store tokens
            encrypted_token = encrypt_message(access_token)
            expires_at = datetime.now() + timedelta(
                days=30
            )  # GitHub tokens don't expire by default

            await save_tokens(
                db_conn_pool=current_app.config["DB_CONNECTION_POOL"],
                user_id=user_id,
                encrypted_access_token=encrypted_token,
                encrypted_refresh_token=None,  # GitHub doesn't use refresh tokens
                expires_at=expires_at,
                scope=GITHUB_SCOPES,
            )

            # Clear session
            session.pop("github_oauth_state", None)
            session.pop("github_oauth_user_id", None)

            logger.info(f"GitHub OAuth completed successfully for user {user_id}")

            return jsonify(
                {
                    "ok": True,
                    "message": "GitHub connected successfully",
                    "user_info": user_info,
                }
            )

    except Exception as e:
        logger.error(f"GitHub OAuth callback error: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


async def get_github_user_info(access_token: str):
    """Get GitHub user information"""
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/vnd.github.v3+json",
    }

    async with httpx.AsyncClient() as client:
        response = await client.get("https://api.github.com/user", headers=headers)
        if response.status_code == 200:
            return response.json()
        return {}


@github_oauth_bp.route("/api/auth/github/status", methods=["POST"])
async def github_auth_status():
    """Check GitHub connection status"""
    try:
        data = request.get_json()
        user_id = data.get("user_id")

        if not user_id:
            return jsonify({"ok": False, "error": "user_id required"}), 400

        # Check if tokens exist and are valid
        tokens = await get_tokens(
            db_conn_pool=current_app.config["DB_CONNECTION_POOL"], user_id=user_id
        )

        if not tokens:
            return jsonify(
                {"ok": True, "connected": False, "message": "Not connected to GitHub"}
            )

        # Verify token is still valid
        encrypted_token, _, expires_at = tokens
        access_token = decrypt_message(encrypted_token)

        if expires_at and expires_at < datetime.now():
            return jsonify(
                {"ok": True, "connected": False, "message": "GitHub token expired"}
            )

        # Test token with API call
        user_info = await get_github_user_info(access_token)
        if user_info:
            return jsonify(
                {
                    "ok": True,
                    "connected": True,
                    "user_info": user_info,
                    "message": "Connected to GitHub",
                }
            )
        else:
            return jsonify(
                {"ok": True, "connected": False, "message": "GitHub token invalid"}
            )

    except Exception as e:
        logger.error(f"GitHub status check error: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@github_oauth_bp.route("/api/auth/github/disconnect", methods=["POST"])
async def github_auth_disconnect():
    """Disconnect GitHub integration"""
    try:
        data = request.get_json()
        user_id = data.get("user_id")

        if not user_id:
            return jsonify({"ok": False, "error": "user_id required"}), 400

        await delete_tokens(
            db_conn_pool=current_app.config["DB_CONNECTION_POOL"], user_id=user_id
        )

        return jsonify({"ok": True, "message": "GitHub disconnected successfully"})

    except Exception as e:
        logger.error(f"GitHub disconnect error: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@github_oauth_bp.route("/api/auth/github/health", methods=["GET"])
async def github_oauth_health():
    """GitHub OAuth health check"""
    try:
        # Check configuration
        config_ok = all([GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET, GITHUB_REDIRECT_URI])

        # Test GitHub connectivity
        async with httpx.AsyncClient() as client:
            response = await client.get("https://github.com", timeout=10.0)
            github_reachable = response.status_code == 200

        return jsonify(
            {
                "status": "healthy" if config_ok and github_reachable else "unhealthy",
                "config_ok": config_ok,
                "github_reachable": github_reachable,
                "client_id_configured": bool(GITHUB_CLIENT_ID),
                "client_secret_configured": bool(GITHUB_CLIENT_SECRET),
                "redirect_uri": GITHUB_REDIRECT_URI,
            }
        )

    except Exception as e:
        logger.error(f"GitHub OAuth health check failed: {e}")
        return jsonify({"status": "unhealthy", "error": str(e)}), 500
