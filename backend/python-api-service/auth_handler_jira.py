import os
import logging
import requests
import json
from flask import Blueprint, request, jsonify, session, current_app
import urllib.parse
import secrets
from datetime import datetime, timezone, timedelta
import db_oauth_jira
import crypto_utils

logger = logging.getLogger(__name__)

jira_auth_bp = Blueprint("jira_auth_bp", __name__)

# Atlassian OAuth Configuration
ATLASSIAN_CLIENT_ID = os.getenv("ATLASSIAN_CLIENT_ID") or os.getenv("JIRA_CLIENT_ID")
ATLASSIAN_CLIENT_SECRET = os.getenv("ATLASSIAN_CLIENT_SECRET") or os.getenv("JIRA_CLIENT_SECRET")
ATLASSIAN_REDIRECT_URI = os.getenv(
    "ATLASSIAN_REDIRECT_URI", "http://localhost:8000/api/auth/jira/callback"
) or os.getenv("JIRA_REDIRECT_URI", "http://localhost:8000/api/auth/jira/callback")


@jira_auth_bp.route("/api/auth/jira/start")
async def jira_auth_start():
    """Start Atlassian OAuth 2.0 flow for Jira"""
    try:
        user_id = request.args.get("user_id")
        if not user_id:
            return jsonify({"ok": False, "error": "user_id required"}), 400

        if not ATLASSIAN_CLIENT_ID or not ATLASSIAN_CLIENT_SECRET:
            logger.error(
                "Atlassian OAuth not configured - missing CLIENT_ID or CLIENT_SECRET"
            )
            return jsonify({"ok": False, "error": "Jira OAuth not configured"}), 500

        # Generate state and store in session
        state = secrets.token_urlsafe(32)
        session["jira_oauth_state"] = state
        session["jira_oauth_user_id"] = user_id

        # Build authorization URL with required scopes for Jira
        auth_url = "https://auth.atlassian.com/authorize"
        scopes = [
            "read:jira-work",
            "read:jira-user",
            "write:jira-work",
            "offline_access",
        ]

        params = {
            "audience": "api.atlassian.com",
            "client_id": ATLASSIAN_CLIENT_ID,
            "scope": " ".join(scopes),
            "redirect_uri": ATLASSIAN_REDIRECT_URI,
            "state": state,
            "response_type": "code",
            "prompt": "consent",
        }

        auth_url_with_params = f"{auth_url}?{urllib.parse.urlencode(params)}"
        logger.info(f"Starting Jira OAuth for user {user_id}")
        return jsonify({"ok": True, "auth_url": auth_url_with_params})

    except Exception as e:
        logger.error(f"Error starting Jira OAuth: {e}", exc_info=True)
        return jsonify({"ok": False, "error": str(e)}), 500


@jira_auth_bp.route("/api/auth/jira/callback")
async def jira_auth_callback():
    """Handle Atlassian OAuth callback and discover user's Jira resources"""
    try:
        code = request.args.get("code")
        state = request.args.get("state")
        error = request.args.get("error")

        if error:
            logger.error(f"OAuth callback error: {error}")
            return jsonify({"ok": False, "error": f"OAuth error: {error}"}), 400

        if not code or not state:
            logger.error("Missing code or state in OAuth callback")
            return jsonify({"ok": False, "error": "Missing code or state"}), 400

        # Verify state
        if state != session.get("jira_oauth_state"):
            logger.error(
                f"State mismatch: expected {session.get('jira_oauth_state')}, got {state}"
            )
            return jsonify({"ok": False, "error": "Invalid state parameter"}), 400

        user_id = session.get("jira_oauth_user_id")
        if not user_id:
            logger.error("No user_id found in session")
            return jsonify({"ok": False, "error": "User session expired"}), 400

        # Exchange code for access token
        token_url = "https://auth.atlassian.com/oauth/token"
        token_data = {
            "grant_type": "authorization_code",
            "client_id": ATLASSIAN_CLIENT_ID,
            "client_secret": ATLASSIAN_CLIENT_SECRET,
            "code": code,
            "redirect_uri": ATLASSIAN_REDIRECT_URI,
        }

        logger.info("Exchanging authorization code for access token")
        response = requests.post(token_url, data=token_data)
        if response.status_code != 200:
            logger.error(
                f"Token exchange failed: {response.status_code} - {response.text}"
            )
            return jsonify({"ok": False, "error": "Token exchange failed"}), 400

        token_response = response.json()
        access_token = token_response.get("access_token")
        refresh_token = token_response.get("refresh_token")
        expires_in = token_response.get("expires_in", 3600)

        if not access_token:
            logger.error("No access token received in token response")
            return jsonify({"ok": False, "error": "No access token received"}), 400

        # Discover user's Jira resources (cloud instances)
        resources_url = "https://api.atlassian.com/oauth/token/accessible-resources"
        headers = {"Authorization": f"Bearer {access_token}"}
        logger.info("Discovering accessible Jira resources")
        resources_response = requests.get(resources_url, headers=headers)

        if resources_response.status_code != 200:
            logger.error(
                f"Resource discovery failed: {resources_response.status_code} - {resources_response.text}"
            )
            return jsonify(
                {"ok": False, "error": "Failed to discover Jira resources"}
            ), 400

        resources = resources_response.json()
        if not resources:
            logger.error("No Jira resources found for authenticated user")
            return jsonify(
                {"ok": False, "error": "No Jira resources found for this account"}
            ), 400

        # Store all accessible resources, use the first one as primary
        jira_resource = resources[0]
        cloud_id = jira_resource["id"]
        jira_url = jira_resource["url"]
        site_name = jira_resource.get("name", "Unknown")

        logger.info(
            f"Discovered Jira resource: {site_name} (ID: {cloud_id}, URL: {jira_url})"
        )

        # Calculate expiration time
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

        # Store tokens and resource info
        token_data = {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "cloud_id": cloud_id,
            "jira_url": jira_url,
            "site_name": site_name,
            "resources": resources,
            "expires_at": expires_at.isoformat(),
        }

        encrypted_token_data = crypto_utils.encrypt_message(json.dumps(token_data))

        # Save to database
        await db_oauth_jira.save_tokens(
            db_conn_pool=current_app.config["DB_CONNECTION_POOL"],
            user_id=user_id,
            encrypted_access_token=encrypted_token_data,
            encrypted_refresh_token=None,  # Store everything in access_token field
            expires_at=expires_at,
            scope=token_response.get("scope", ""),
        )

        # Clear session
        session.pop("jira_oauth_state", None)
        session.pop("jira_oauth_user_id", None)

        logger.info(f"Jira OAuth completed successfully for user {user_id}")
        return jsonify(
            {
                "ok": True,
                "message": "Jira connected successfully",
                "jira_url": jira_url,
                "cloud_id": cloud_id,
                "site_name": site_name,
                "resources_count": len(resources),
            }
        )

    except Exception as e:
        logger.error(f"Error in Jira OAuth callback: {e}", exc_info=True)
        return jsonify({"ok": False, "error": str(e)}), 500


@jira_auth_bp.route("/api/auth/jira/disconnect", methods=["POST"])
async def jira_auth_disconnect():
    """Disconnect Jira integration for a user"""
    try:
        data = request.get_json()
        user_id = data.get("user_id")

        if not user_id:
            return jsonify({"ok": False, "error": "user_id required"}), 400

        await db_oauth_jira.delete_tokens(
            db_conn_pool=current_app.config["DB_CONNECTION_POOL"], user_id=user_id
        )

        logger.info(f"Jira disconnected for user {user_id}")
        return jsonify({"ok": True, "message": "Jira disconnected successfully"})

    except Exception as e:
        logger.error(f"Error disconnecting Jira: {e}", exc_info=True)
        return jsonify({"ok": False, "error": str(e)}), 500


@jira_auth_bp.route("/api/auth/jira/status", methods=["POST"])
async def jira_auth_status():
    """Check Jira connection status for a user"""
    try:
        data = request.get_json()
        user_id = data.get("user_id")

        if not user_id:
            return jsonify({"ok": False, "error": "user_id required"}), 400

        # Check if tokens exist and are not expired
        tokens = await db_oauth_jira.get_tokens(
            current_app.config["DB_CONNECTION_POOL"], user_id
        )
        if not tokens:
            return jsonify(
                {"ok": True, "connected": False, "message": "Not connected to Jira"}
            )

        encrypted_token_data, _, expires_at = tokens

        # Check if token is expired
        if expires_at and expires_at < datetime.now(timezone.utc):
            logger.info(f"Jira token expired for user {user_id}")
            return jsonify(
                {"ok": True, "connected": False, "message": "Jira connection expired"}
            )

        # Decrypt token data to get resource info
        try:
            token_data_json = crypto_utils.decrypt_message(encrypted_token_data)
            token_data = json.loads(token_data_json)

            return jsonify(
                {
                    "ok": True,
                    "connected": True,
                    "jira_url": token_data.get("jira_url"),
                    "cloud_id": token_data.get("cloud_id"),
                    "site_name": token_data.get("site_name"),
                    "resources_count": len(token_data.get("resources", [])),
                }
            )
        except Exception as e:
            logger.error(f"Error decrypting Jira token data for user {user_id}: {e}")
            return jsonify(
                {"ok": True, "connected": False, "message": "Invalid token data"}
            )

    except Exception as e:
        logger.error(f"Error checking Jira status: {e}", exc_info=True)
        return jsonify({"ok": False, "error": str(e)}), 500


@jira_auth_bp.route("/api/auth/jira/refresh", methods=["POST"])
async def jira_auth_refresh():
    """Refresh expired Jira access token"""
    try:
        data = request.get_json()
        user_id = data.get("user_id")

        if not user_id:
            return jsonify({"ok": False, "error": "user_id required"}), 400

        # Get current tokens
        tokens = await db_oauth_jira.get_tokens(
            current_app.config["DB_CONNECTION_POOL"], user_id
        )
        if not tokens:
            return jsonify({"ok": False, "error": "No Jira connection found"}), 404

        encrypted_token_data, _, _ = tokens
        token_data_json = crypto_utils.decrypt_message(encrypted_token_data)
        token_data = json.loads(token_data_json)

        refresh_token = token_data.get("refresh_token")
        if not refresh_token:
            return jsonify({"ok": False, "error": "No refresh token available"}), 400

        # Exchange refresh token for new access token
        token_url = "https://auth.atlassian.com/oauth/token"
        refresh_data = {
            "grant_type": "refresh_token",
            "client_id": ATLASSIAN_CLIENT_ID,
            "client_secret": ATLASSIAN_CLIENT_SECRET,
            "refresh_token": refresh_token,
        }

        response = requests.post(token_url, data=refresh_data)
        if response.status_code != 200:
            logger.error(
                f"Token refresh failed: {response.status_code} - {response.text}"
            )
            return jsonify({"ok": False, "error": "Token refresh failed"}), 400

        refresh_response = response.json()
        new_access_token = refresh_response.get("access_token")
        new_refresh_token = refresh_response.get(
            "refresh_token", refresh_token
        )  # Use new if provided, else keep old
        expires_in = refresh_response.get("expires_in", 3600)

        if not new_access_token:
            return jsonify(
                {"ok": False, "error": "No access token received from refresh"}
            ), 400

        # Update token data
        token_data["access_token"] = new_access_token
        token_data["refresh_token"] = new_refresh_token
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        token_data["expires_at"] = expires_at.isoformat()

        # Re-encrypt and save
        encrypted_token_data = crypto_utils.encrypt_message(json.dumps(token_data))

        await db_oauth_jira.save_tokens(
            db_conn_pool=current_app.config["DB_CONNECTION_POOL"],
            user_id=user_id,
            encrypted_access_token=encrypted_token_data,
            encrypted_refresh_token=None,
            expires_at=expires_at,
            scope=refresh_response.get("scope", ""),
        )

        logger.info(f"Jira token refreshed successfully for user {user_id}")
        return jsonify({"ok": True, "message": "Jira token refreshed successfully"})

    except Exception as e:
        logger.error(f"Error refreshing Jira token: {e}", exc_info=True)
        return jsonify({"ok": False, "error": str(e)}), 500
