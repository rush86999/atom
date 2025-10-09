import os
import logging
import base64
import json
from flask import Blueprint, request, jsonify, session, redirect
from typing import Dict, Any, Optional
import requests

logger = logging.getLogger(__name__)

notion_auth_bp = Blueprint("notion_auth_bp", __name__)

# Notion OAuth Configuration
NOTION_CLIENT_ID = os.getenv("NOTION_CLIENT_ID")
NOTION_CLIENT_SECRET = os.getenv("NOTION_CLIENT_SECRET")
NOTION_REDIRECT_URI = os.getenv(
    "NOTION_REDIRECT_URI", "http://localhost:3000/auth/notion/callback"
)
NOTION_AUTH_URL = "https://api.notion.com/v1/oauth/authorize"
NOTION_TOKEN_URL = "https://api.notion.com/v1/oauth/token"

# Import database utilities
try:
    from db_utils import get_db_pool
    from db_oauth_notion import save_tokens, get_tokens, delete_tokens, update_tokens

    DB_AVAILABLE = True
except ImportError:
    logger.warning("Database utilities not available - using session storage")
    DB_AVAILABLE = False


@notion_auth_bp.route("/api/auth/notion/initiate", methods=["GET"])
def initiate_notion_auth():
    """Initiate Notion OAuth2 flow"""
    if not NOTION_CLIENT_ID or not NOTION_CLIENT_SECRET:
        return jsonify(
            {
                "ok": False,
                "error": {
                    "code": "CONFIG_ERROR",
                    "message": "Notion integration is not configured correctly on the server.",
                },
            }
        ), 500

    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify(
            {
                "ok": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "user_id is required.",
                },
            }
        ), 400

    # Store user_id in session for callback
    session["notion_auth_user_id"] = user_id

    # Build authorization URL
    auth_params = {
        "client_id": NOTION_CLIENT_ID,
        "redirect_uri": NOTION_REDIRECT_URI,
        "response_type": "code",
        "owner": "user",
    }

    auth_url = f"{NOTION_AUTH_URL}?{requests.compat.urlencode(auth_params)}"

    logger.info(f"Initiating Notion OAuth for user {user_id}")
    return jsonify({"ok": True, "auth_url": auth_url, "user_id": user_id})


@notion_auth_bp.route("/api/auth/notion/callback", methods=["GET"])
def notion_auth_callback():
    """Handle Notion OAuth callback"""
    try:
        code = request.args.get("code")
        error = request.args.get("error")
        user_id = session.get("notion_auth_user_id")

        if error:
            logger.error(f"Notion OAuth callback error: {error}")
            return jsonify(
                {
                    "ok": False,
                    "error": {
                        "code": "OAUTH_ERROR",
                        "message": f"Authorization failed: {error}",
                    },
                }
            ), 400

        if not code:
            return jsonify(
                {
                    "ok": False,
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "Authorization code is required.",
                    },
                }
            ), 400

        if not user_id:
            return jsonify(
                {
                    "ok": False,
                    "error": {
                        "code": "SESSION_ERROR",
                        "message": "User session not found. Please restart the authorization flow.",
                    },
                }
            ), 400

        logger.info(f"Exchanging Notion authorization code for user {user_id}")

        # Exchange code for access token
        token_response = exchange_code_for_token(code)

        if not token_response.get("ok"):
            return jsonify(token_response), 500

        token_data = token_response["data"]

        # Store tokens in database
        store_result = store_notion_tokens(user_id, token_data)

        if not store_result.get("ok"):
            return jsonify(store_result), 500

        # Clear session
        session.pop("notion_auth_user_id", None)

        logger.info(f"Successfully completed Notion OAuth for user {user_id}")

        return jsonify(
            {
                "ok": True,
                "data": {
                    "user_id": user_id,
                    "status": "connected",
                    "message": "Notion account connected successfully",
                    "workspace_name": token_data.get("workspace_name"),
                    "workspace_id": token_data.get("workspace_id"),
                    "bot_id": token_data.get("bot_id"),
                },
            }
        )

    except Exception as e:
        logger.error(f"Error in Notion OAuth callback: {e}", exc_info=True)
        return jsonify(
            {
                "ok": False,
                "error": {
                    "code": "CALLBACK_ERROR",
                    "message": f"OAuth callback failed: {str(e)}",
                },
            }
        ), 500


@notion_auth_bp.route("/api/auth/notion/validate", methods=["POST"])
def validate_notion_credentials():
    """
    Validate Notion OAuth credentials stored for user
    This checks if valid OAuth tokens are available for the user
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify(
                {
                    "ok": False,
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "JSON data is required",
                    },
                }
            ), 400

        user_id = data.get("user_id")

        if not user_id:
            return jsonify(
                {
                    "ok": False,
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "user_id is required",
                    },
                }
            ), 400

        logger.info(f"Validating Notion credentials for user {user_id}")

        # Get stored tokens for user
        tokens = get_notion_tokens(user_id)

        if not tokens or not tokens.get("access_token"):
            return jsonify(
                {
                    "ok": False,
                    "error": {
                        "code": "AUTH_ERROR",
                        "message": "No Notion credentials found for user",
                    },
                }
            ), 401

        # Test the credentials by making a simple API call
        try:
            headers = {
                "Authorization": f"Bearer {tokens['access_token']}",
                "Notion-Version": "2022-06-28",
            }

            response = requests.get(
                "https://api.notion.com/v1/users/me", headers=headers, timeout=10
            )

            if response.status_code == 200:
                user_data = response.json()
                return jsonify(
                    {
                        "ok": True,
                        "data": {
                            "user_id": user_id,
                            "status": "connected",
                            "message": "Notion credentials validated successfully",
                            "workspace_name": tokens.get("workspace_name"),
                            "workspace_id": tokens.get("workspace_id"),
                            "bot_id": tokens.get("bot_id"),
                        },
                    }
                )
            else:
                # Token might be expired, try to refresh
                refresh_result = refresh_notion_token(
                    user_id, tokens.get("refresh_token")
                )
                if refresh_result.get("ok"):
                    return jsonify(
                        {
                            "ok": True,
                            "data": {
                                "user_id": user_id,
                                "status": "connected",
                                "message": "Notion credentials refreshed and validated",
                                "workspace_name": refresh_result["data"].get(
                                    "workspace_name"
                                ),
                                "workspace_id": refresh_result["data"].get(
                                    "workspace_id"
                                ),
                            },
                        }
                    )
                else:
                    return jsonify(
                        {
                            "ok": False,
                            "error": {
                                "code": "AUTH_ERROR",
                                "message": f"Invalid Notion credentials: {response.text}",
                            },
                        }
                    ), 401

        except Exception as api_error:
            logger.error(
                f"Notion API validation failed for user {user_id}: {api_error}"
            )
            return jsonify(
                {
                    "ok": False,
                    "error": {
                        "code": "AUTH_ERROR",
                        "message": f"Invalid Notion credentials: {str(api_error)}",
                    },
                }
            ), 401

    except Exception as e:
        logger.error(f"Error validating Notion credentials: {e}", exc_info=True)
        return jsonify(
            {
                "ok": False,
                "error": {
                    "code": "VALIDATION_FAILED",
                    "message": f"Credential validation failed: {str(e)}",
                },
            }
        ), 500


@notion_auth_bp.route("/api/auth/notion/status", methods=["GET"])
def get_notion_status():
    """
    Get current Notion integration status for a user
    This checks if valid OAuth tokens are available
    """
    try:
        user_id = request.args.get("user_id")

        if not user_id:
            return jsonify(
                {
                    "ok": False,
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "user_id is required",
                    },
                }
            ), 400

        # Get stored tokens for user
        tokens = get_notion_tokens(user_id)

        if not tokens or not tokens.get("access_token"):
            return jsonify(
                {
                    "ok": True,
                    "service": "notion",
                    "status": "disconnected",
                    "message": "Notion account not connected",
                    "available": False,
                    "mock_data": False,
                }
            )

        # Test the credentials
        try:
            headers = {
                "Authorization": f"Bearer {tokens['access_token']}",
                "Notion-Version": "2022-06-28",
            }

            response = requests.get(
                "https://api.notion.com/v1/users/me", headers=headers, timeout=10
            )

            if response.status_code == 200:
                return jsonify(
                    {
                        "ok": True,
                        "service": "notion",
                        "status": "connected",
                        "message": "Notion service connected successfully",
                        "available": True,
                        "mock_data": False,
                        "user": {
                            "workspace_name": tokens.get("workspace_name"),
                            "workspace_id": tokens.get("workspace_id"),
                            "bot_id": tokens.get("bot_id"),
                        },
                    }
                )
            else:
                return jsonify(
                    {
                        "ok": True,
                        "service": "notion",
                        "status": "disconnected",
                        "message": f"Notion connection failed: {response.text}",
                        "available": False,
                        "mock_data": False,
                    }
                )

        except Exception as api_error:
            logger.error(f"Notion status check failed for user {user_id}: {api_error}")
            return jsonify(
                {
                    "ok": True,
                    "service": "notion",
                    "status": "disconnected",
                    "message": f"Notion connection failed: {str(api_error)}",
                    "available": False,
                    "mock_data": False,
                }
            )

    except Exception as e:
        logger.error(f"Error checking Notion status: {e}")
        return jsonify(
            {
                "ok": False,
                "service": "notion",
                "status": "error",
                "message": f"Status check failed: {str(e)}",
            }
        ), 500


@notion_auth_bp.route("/api/auth/notion/disconnect", methods=["POST"])
def disconnect_notion():
    """Disconnect Notion integration for a user"""
    try:
        data = request.get_json()
        if not data:
            return jsonify(
                {
                    "ok": False,
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "JSON data is required",
                    },
                }
            ), 400

        user_id = data.get("user_id")

        if not user_id:
            return jsonify(
                {
                    "ok": False,
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "user_id is required",
                    },
                }
            ), 400

        logger.info(f"Disconnecting Notion for user {user_id}")

        # Remove stored tokens for user
        delete_result = delete_notion_tokens(user_id)

        if not delete_result.get("ok"):
            return jsonify(delete_result), 500

        return jsonify(
            {
                "ok": True,
                "data": {
                    "user_id": user_id,
                    "status": "disconnected",
                    "message": "Notion account disconnected successfully",
                },
            }
        )

    except Exception as e:
        logger.error(f"Error disconnecting Notion: {e}", exc_info=True)
        return jsonify(
            {
                "ok": False,
                "error": {
                    "code": "DISCONNECT_FAILED",
                    "message": f"Disconnect failed: {str(e)}",
                },
            }
        ), 500


@notion_auth_bp.route("/api/auth/notion/instructions", methods=["GET"])
def get_notion_instructions():
    """
    Provide instructions for users to connect their Notion account via OAuth
    """
    return jsonify(
        {
            "ok": True,
            "data": {
                "service": "notion",
                "instructions": {
                    "title": "Connect Your Notion Account",
                    "description": "Notion uses OAuth 2.0 for secure authentication. Click the connect button to authorize ATOM to access your Notion workspace.",
                    "steps": [
                        {
                            "step": 1,
                            "title": "Click Connect",
                            "description": "Click the 'Connect Notion' button to start the authorization process",
                        },
                        {
                            "step": 2,
                            "title": "Authorize Access",
                            "description": "You'll be redirected to Notion to authorize ATOM to access your workspace",
                        },
                        {
                            "step": 3,
                            "title": "Select Pages",
                            "description": "Choose which pages and databases you want ATOM to have access to",
                        },
                        {
                            "step": 4,
                            "title": "Complete Setup",
                            "description": "You'll be redirected back to ATOM and your connection will be established",
                        },
                    ],
                    "note": "ATOM will only access the specific pages and databases you authorize. You can revoke access at any time from your Notion settings.",
                },
                "oauth_flow": True,
            },
        }
    )


def exchange_code_for_token(code: str) -> Dict[str, Any]:
    """Exchange authorization code for access token"""
    try:
        # Prepare Basic Auth header
        credentials = f"{NOTION_CLIENT_ID}:{NOTION_CLIENT_SECRET}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()

        headers = {
            "Authorization": f"Basic {encoded_credentials}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        payload = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": NOTION_REDIRECT_URI,
        }

        response = requests.post(
            NOTION_TOKEN_URL, headers=headers, json=payload, timeout=30
        )

        if response.status_code == 200:
            token_data = response.json()
            logger.info("Successfully exchanged Notion authorization code for tokens")
            return {
                "ok": True,
                "data": {
                    "access_token": token_data.get("access_token"),
                    "refresh_token": token_data.get("refresh_token"),
                    "bot_id": token_data.get("bot_id"),
                    "workspace_name": token_data.get("workspace_name"),
                    "workspace_id": token_data.get("workspace_id"),
                    "workspace_icon": token_data.get("workspace_icon"),
                    "owner": token_data.get("owner"),
                    "duplicated_template_id": token_data.get("duplicated_template_id"),
                },
            }
        else:
            error_text = response.text
            logger.error(
                f"Failed to exchange Notion code: {response.status_code} - {error_text}"
            )
            return {
                "ok": False,
                "error": {
                    "code": "TOKEN_EXCHANGE_FAILED",
                    "message": f"Token exchange failed: {error_text}",
                },
            }

    except Exception as e:
        logger.error(f"Error exchanging Notion code for token: {e}")
        return {
            "ok": False,
            "error": {
                "code": "TOKEN_EXCHANGE_ERROR",
                "message": f"Token exchange error: {str(e)}",
            },
        }


def refresh_notion_token(user_id: str, refresh_token: str) -> Dict[str, Any]:
    """Refresh Notion access token using refresh token"""
    try:
        if not refresh_token:
            return {
                "ok": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Refresh token is required",
                },
            }

        # Prepare Basic Auth header
        credentials = f"{NOTION_CLIENT_ID}:{NOTION_CLIENT_SECRET}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()

        headers = {
            "Authorization": f"Basic {encoded_credentials}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        payload = {"grant_type": "refresh_token", "refresh_token": refresh_token}

        response = requests.post(
            NOTION_TOKEN_URL, headers=headers, json=payload, timeout=30
        )

        if response.status_code == 200:
            token_data = response.json()
            logger.info(f"Successfully refreshed Notion token for user {user_id}")

            # Update stored tokens
            update_data = {
                "access_token": token_data.get("access_token"),
                "refresh_token": token_data.get("refresh_token"),
                "bot_id": token_data.get("bot_id"),
                "workspace_name": token_data.get("workspace_name"),
                "workspace_id": token_data.get("workspace_id"),
            }

            store_notion_tokens(user_id, update_data)

            return {"ok": True, "data": update_data}
        else:
            error_text = response.text
            logger.error(
                f"Failed to refresh Notion token: {response.status_code} - {error_text}"
            )
            return {
                "ok": False,
                "error": {
                    "code": "TOKEN_REFRESH_FAILED",
                    "message": f"Token refresh failed: {error_text}",
                },
            }

    except Exception as e:
        logger.error(f"Error refreshing Notion token: {e}")
        return {
            "ok": False,
            "error": {
                "code": "TOKEN_REFRESH_ERROR",
                "message": f"Token refresh error: {str(e)}",
            },
        }


def store_notion_tokens(user_id: str, token_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Store Notion OAuth tokens for a user
    """
    if not DB_AVAILABLE:
        logger.warning(
            "Database not available - using session storage for Notion tokens"
        )
        # Store in session (temporary solution)
        session[f"notion_tokens_{user_id}"] = token_data
        return {"ok": True, "message": "Tokens stored in session"}

    try:
        db_pool = get_db_pool()
        if not db_pool:
            return {
                "ok": False,
                "error": {
                    "code": "DB_UNAVAILABLE",
                    "message": "Database connection pool not available",
                },
            }

        result = save_tokens(
            db_pool,
            user_id,
            token_data.get("access_token"),
            token_data.get("refresh_token"),
            token_data.get("bot_id"),
            token_data.get("workspace_name"),
            token_data.get("workspace_id"),
            token_data.get("workspace_icon"),
            token_data.get("owner"),
            token_data.get("duplicated_template_id"),
        )

        return result

    except Exception as e:
        logger.error(f"Error storing Notion tokens for user {user_id}: {e}")
        return {
            "ok": False,
            "error": {
                "code": "STORAGE_ERROR",
                "message": f"Failed to store tokens: {str(e)}",
            },
        }


def get_notion_tokens(user_id: str) -> Optional[Dict[str, Any]]:
    """Get Notion OAuth tokens for a user"""
    if not DB_AVAILABLE:
        # Get from session (temporary solution)
        return session.get(f"notion_tokens_{user_id}")

    try:
        db_pool = get_db_pool()
        if not db_pool:
            logger.error("Database connection pool not available")
            return None

        tokens = get_tokens(db_pool, user_id)
        return tokens

    except Exception as e:
        logger.error(f"Error getting Notion tokens for user {user_id}: {e}")
        return None


def delete_notion_tokens(user_id: str) -> Dict[str, Any]:
    """Delete Notion OAuth tokens for a user"""
    if not DB_AVAILABLE:
        # Remove from session (temporary solution)
        session.pop(f"notion_tokens_{user_id}", None)
        return {"ok": True, "message": "Tokens deleted from session"}

    try:
        db_pool = get_db_pool()
        if not db_pool:
            return {
                "ok": False,
                "error": {
                    "code": "DB_UNAVAILABLE",
                    "message": "Database connection pool not available",
                },
            }

        result = delete_tokens(db_pool, user_id)
        return result

    except Exception as e:
        logger.error(f"Error deleting Notion tokens for user {user_id}: {e}")
        return {
            "ok": False,
            "error": {
                "code": "DELETE_ERROR",
                "message": f"Failed to delete tokens: {str(e)}",
            },
        }


def refresh_notion_token(user_id: str, refresh_token: str) -> Dict[str, Any]:
    """Refresh Notion access token using refresh token"""
    try:
        # Prepare Basic Auth header
        credentials = f"{NOTION_CLIENT_ID}:{NOTION_CLIENT_SECRET}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()

        headers = {
            "Authorization": f"Basic {encoded_credentials}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        payload = {"grant_type": "refresh_token", "refresh_token": refresh_token}

        response = requests.post(
            NOTION_TOKEN_URL, headers=headers, json=payload, timeout=30
        )

        if response.status_code == 200:
            token_data = response.json()
            logger.info(
                f"Successfully refreshed Notion access token for user {user_id}"
            )

            # Update stored tokens
            update_data = {
                "access_token": token_data.get("access_token"),
                "refresh_token": token_data.get("refresh_token"),
                "bot_id": token_data.get("bot_id"),
                "workspace_name": token_data.get("workspace_name"),
                "workspace_id": token_data.get("workspace_id"),
                "workspace_icon": token_data.get("workspace_icon"),
                "owner": token_data.get("owner"),
                "duplicated_template_id": token_data.get("duplicated_template_id"),
            }

            # Store the updated tokens
            store_result = store_notion_tokens(user_id, update_data)
            if store_result.get("ok"):
                return {"ok": True, "data": update_data}
            else:
                return store_result

        else:
            error_text = response.text
            logger.error(
                f"Failed to refresh Notion token: {response.status_code} - {error_text}"
            )
            return {
                "ok": False,
                "error": {
                    "code": "TOKEN_REFRESH_FAILED",
                    "message": f"Token refresh failed: {error_text}",
                },
            }

    except Exception as e:
        logger.error(f"Error refreshing Notion access token: {e}")
        return {
            "ok": False,
            "error": {
                "code": "TOKEN_REFRESH_ERROR",
                "message": f"Token refresh error: {str(e)}",
            },
        }
