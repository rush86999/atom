"""
Stripe OAuth Handler
Complete Stripe OAuth 2.0 authentication flow implementation
"""

import os
import json
import secrets
import hashlib
import base64
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, redirect, session
from loguru import logger

# Import database handler
try:
    from db_oauth_stripe import (
        get_tokens,
        save_tokens,
        delete_tokens,
        get_user_stripe_data,
        save_stripe_data,
    )

    STRIPE_DB_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Stripe database handler not available: {e}")
    STRIPE_DB_AVAILABLE = False

auth_stripe_bp = Blueprint("auth_stripe_bp", __name__)

# Stripe OAuth configuration
STRIPE_CLIENT_ID = os.getenv("STRIPE_CLIENT_ID", "ca_mock_client_id")
STRIPE_CLIENT_SECRET = os.getenv("STRIPE_CLIENT_SECRET", "sk_test_mock_secret")
STRIPE_REDIRECT_URI = os.getenv(
    "STRIPE_REDIRECT_URI", "http://localhost:3000/auth/stripe/callback"
)
STRIPE_AUTH_URL = "https://connect.stripe.com/oauth/authorize"
STRIPE_TOKEN_URL = "https://connect.stripe.com/oauth/token"
STRIPE_API_BASE_URL = "https://api.stripe.com/v1"

# Stripe OAuth scopes
STRIPE_SCOPES = [
    "read_write",  # Full read/write access
    "charges",
    "customers",
    "subscriptions",
    "invoices",
    "payment_intents",
    "payment_methods",
    "products",
    "prices",
    "coupons",
    "balance",
    "events",
    "webhooks",
]

# In-memory state storage for OAuth flow (in production, use Redis or database)
oauth_states = {}


def generate_state_parameter() -> str:
    """Generate secure state parameter for OAuth flow"""
    state = secrets.token_urlsafe(32)
    oauth_states[state] = {"created_at": datetime.utcnow(), "used": False}
    return state


def validate_state_parameter(state: str) -> bool:
    """Validate state parameter for security"""
    if state not in oauth_states:
        return False

    state_data = oauth_states[state]

    # Check if state is already used
    if state_data["used"]:
        return False

    # Check if state is expired (5 minutes)
    if datetime.utcnow() - state_data["created_at"] > timedelta(minutes=5):
        del oauth_states[state]
        return False

    # Mark state as used
    state_data["used"] = True
    return True


def cleanup_expired_states():
    """Clean up expired OAuth states"""
    current_time = datetime.utcnow()
    expired_states = [
        state
        for state, data in oauth_states.items()
        if current_time - data["created_at"] > timedelta(minutes=10)
    ]

    for state in expired_states:
        del oauth_states[state]

    if expired_states:
        logger.info(f"Cleaned up {len(expired_states)} expired OAuth states")


@auth_stripe_bp.route("/auth/stripe", methods=["GET"])
def stripe_auth_start():
    """Initiate Stripe OAuth flow"""
    try:
        # Generate state parameter for security
        state = generate_state_parameter()

        # Build authorization URL
        auth_params = {
            "response_type": "code",
            "client_id": STRIPE_CLIENT_ID,
            "scope": "read_write",
            "redirect_uri": STRIPE_REDIRECT_URI,
            "state": state,
            "stripe_landing": "login",  # Show Stripe login page
            "always_prompt": "true",  # Always show consent screen
        }

        auth_url = f"{STRIPE_AUTH_URL}?{'&'.join([f'{k}={v}' for k, v in auth_params.items()])}"

        logger.info(f"Stripe OAuth flow initiated with state: {state}")

        return jsonify(
            {
                "ok": True,
                "auth_url": auth_url,
                "state": state,
                "service": "stripe",
                "scopes": STRIPE_SCOPES,
            }
        )

    except Exception as e:
        logger.error(f"Error initiating Stripe OAuth flow: {e}")
        return jsonify(
            {
                "ok": False,
                "error": {
                    "code": "AUTH_INIT_FAILED",
                    "message": f"Failed to initiate Stripe authentication: {str(e)}",
                },
            }
        ), 500


@auth_stripe_bp.route("/auth/stripe/callback", methods=["GET"])
def stripe_auth_callback():
    """Handle Stripe OAuth callback"""
    try:
        # Get parameters from callback
        code = request.args.get("code")
        state = request.args.get("state")
        error = request.args.get("error")
        error_description = request.args.get("error_description")

        # Check for errors
        if error:
            logger.error(f"Stripe OAuth error: {error} - {error_description}")
            return jsonify(
                {
                    "ok": False,
                    "error": {
                        "code": "OAUTH_ERROR",
                        "message": error_description or error,
                        "stripe_error": error,
                    },
                }
            ), 400

        # Validate state parameter
        if not state or not validate_state_parameter(state):
            logger.error(f"Invalid or expired state parameter: {state}")
            return jsonify(
                {
                    "ok": False,
                    "error": {
                        "code": "INVALID_STATE",
                        "message": "Invalid or expired state parameter",
                    },
                }
            ), 400

        if not code:
            logger.error("No authorization code received")
            return jsonify(
                {
                    "ok": False,
                    "error": {
                        "code": "NO_AUTH_CODE",
                        "message": "No authorization code received",
                    },
                }
            ), 400

        # Exchange authorization code for access token
        token_data = exchange_code_for_token(code)

        if not token_data:
            logger.error("Failed to exchange authorization code for token")
            return jsonify(
                {
                    "ok": False,
                    "error": {
                        "code": "TOKEN_EXCHANGE_FAILED",
                        "message": "Failed to exchange authorization code for access token",
                    },
                }
            ), 400

        # Get user info from Stripe
        user_info = get_stripe_user_info(token_data["access_token"])

        if not user_info:
            logger.error("Failed to get user info from Stripe")
            return jsonify(
                {
                    "ok": False,
                    "error": {
                        "code": "USER_INFO_FAILED",
                        "message": "Failed to get user information from Stripe",
                    },
                }
            ), 400

        # Combine token and user data
        combined_data = {**token_data, "user_info": user_info}

        logger.info(
            f"Stripe OAuth completed successfully for account: {user_info.get('id')}"
        )

        return jsonify(
            {
                "ok": True,
                "message": "Stripe authentication successful",
                "data": combined_data,
                "service": "stripe",
            }
        )

    except Exception as e:
        logger.error(f"Error handling Stripe OAuth callback: {e}")
        return jsonify(
            {
                "ok": False,
                "error": {
                    "code": "CALLBACK_ERROR",
                    "message": f"Error handling OAuth callback: {str(e)}",
                },
            }
        ), 500


def exchange_code_for_token(authorization_code: str) -> Optional[Dict[str, Any]]:
    """Exchange authorization code for access token"""
    try:
        import requests

        token_data = {
            "grant_type": "authorization_code",
            "client_id": STRIPE_CLIENT_ID,
            "client_secret": STRIPE_CLIENT_SECRET,
            "code": authorization_code,
            "redirect_uri": STRIPE_REDIRECT_URI,
        }

        response = requests.post(
            STRIPE_TOKEN_URL,
            data=token_data,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "ATOM-Agent/1.0",
            },
            timeout=30,
        )

        response.raise_for_status()
        token_response = response.json()

        # Format token data
        formatted_data = {
            "access_token": token_response.get("access_token"),
            "refresh_token": token_response.get("refresh_token"),
            "token_type": token_response.get("token_type", "bearer"),
            "stripe_publishable_key": token_response.get("stripe_publishable_key"),
            "stripe_user_id": token_response.get("stripe_user_id"),
            "scope": token_response.get("scope"),
            "livemode": token_response.get("livemode", False),
        }

        logger.info(
            f"Successfully exchanged code for Stripe token for user: {token_response.get('stripe_user_id')}"
        )
        return formatted_data

    except Exception as e:
        logger.error(f"Error exchanging Stripe authorization code: {e}")
        return None


def get_stripe_user_info(access_token: str) -> Optional[Dict[str, Any]]:
    """Get user information from Stripe"""
    try:
        import requests

        # Get account information
        account_response = requests.get(
            f"{STRIPE_API_BASE_URL}/account",
            headers={
                "Authorization": f"Bearer {access_token}",
                "User-Agent": "ATOM-Agent/1.0",
            },
            timeout=30,
        )

        account_response.raise_for_status()
        account_data = account_response.json()

        # Get balance information
        balance_response = requests.get(
            f"{STRIPE_API_BASE_URL}/balance",
            headers={
                "Authorization": f"Bearer {access_token}",
                "User-Agent": "ATOM-Agent/1.0",
            },
            timeout=30,
        )

        balance_data = {}
        if balance_response.status_code == 200:
            balance_data = balance_response.json()

        # Format user info
        user_info = {
            "id": account_data.get("id"),
            "email": account_data.get("email"),
            "business_name": account_data.get("business_profile", {}).get("name"),
            "display_name": account_data.get("display_name"),
            "country": account_data.get("country"),
            "currency": account_data.get("default_currency", "usd"),
            "mcc": account_data.get("business_profile", {}).get("mcc"),
            "balance": balance_data,
            "created_utc": account_data.get("created"),
            "metadata": account_data.get("metadata", {}),
        }

        logger.info(f"Retrieved Stripe user info for account: {user_info.get('id')}")
        return user_info

    except Exception as e:
        logger.error(f"Error getting Stripe user info: {e}")
        return None


@auth_stripe_bp.route("/auth/stripe/save", methods=["POST"])
async def save_stripe_auth():
    """Save Stripe authentication data for user"""
    try:
        data = request.get_json()
        user_id = data.get("user_id")
        auth_data = data.get("auth_data")

        if not user_id or not auth_data:
            return jsonify(
                {
                    "ok": False,
                    "error": {
                        "code": "MISSING_DATA",
                        "message": "user_id and auth_data are required",
                    },
                }
            ), 400

        if not STRIPE_DB_AVAILABLE:
            return jsonify(
                {
                    "ok": False,
                    "error": {
                        "code": "DB_UNAVAILABLE",
                        "message": "Stripe database handler not available",
                    },
                }
            ), 500

        # Save tokens and user data
        success = await save_tokens(user_id, auth_data)

        if not success:
            return jsonify(
                {
                    "ok": False,
                    "error": {
                        "code": "SAVE_FAILED",
                        "message": "Failed to save Stripe authentication data",
                    },
                }
            ), 500

        logger.info(
            f"Stripe authentication data saved successfully for user: {user_id}"
        )

        return jsonify(
            {
                "ok": True,
                "message": "Stripe authentication data saved successfully",
                "user_id": user_id,
                "service": "stripe",
            }
        )

    except Exception as e:
        logger.error(f"Error saving Stripe authentication data: {e}")
        return jsonify(
            {
                "ok": False,
                "error": {
                    "code": "SAVE_ERROR",
                    "message": f"Error saving authentication data: {str(e)}",
                },
            }
        ), 500


@auth_stripe_bp.route("/auth/stripe/status", methods=["POST"])
async def check_stripe_auth_status():
    """Check Stripe authentication status for user"""
    try:
        data = request.get_json()
        user_id = data.get("user_id")

        if not user_id:
            return jsonify(
                {
                    "ok": False,
                    "error": {
                        "code": "MISSING_USER_ID",
                        "message": "user_id is required",
                    },
                }
            ), 400

        if not STRIPE_DB_AVAILABLE:
            return jsonify(
                {
                    "ok": True,
                    "authenticated": False,
                    "message": "Database not available, using mock status",
                    "service": "stripe",
                }
            )

        # Get tokens from database
        tokens = await get_tokens(user_id)

        if tokens:
            return jsonify(
                {
                    "ok": True,
                    "authenticated": True,
                    "user_id": user_id,
                    "account_id": tokens.get("account_id"),
                    "service": "stripe",
                    "livemode": tokens.get("livemode", False),
                    "scope": tokens.get("scope"),
                }
            )
        else:
            return jsonify(
                {
                    "ok": True,
                    "authenticated": False,
                    "user_id": user_id,
                    "service": "stripe",
                    "message": "No Stripe authentication found",
                }
            )

    except Exception as e:
        logger.error(f"Error checking Stripe auth status: {e}")
        return jsonify(
            {
                "ok": False,
                "error": {
                    "code": "STATUS_CHECK_ERROR",
                    "message": f"Error checking authentication status: {str(e)}",
                },
            }
        ), 500


@auth_stripe_bp.route("/auth/stripe/revoke", methods=["POST"])
async def revoke_stripe_auth():
    """Revoke Stripe authentication for user"""
    try:
        data = request.get_json()
        user_id = data.get("user_id")

        if not user_id:
            return jsonify(
                {
                    "ok": False,
                    "error": {
                        "code": "MISSING_USER_ID",
                        "message": "user_id is required",
                    },
                }
            ), 400

        if not STRIPE_DB_AVAILABLE:
            return jsonify(
                {
                    "ok": False,
                    "error": {
                        "code": "DB_UNAVAILABLE",
                        "message": "Stripe database handler not available",
                    },
                }
            ), 500

        # Delete tokens from database
        success = await delete_tokens(user_id)

        if not success:
            return jsonify(
                {
                    "ok": False,
                    "error": {
                        "code": "REVOKE_FAILED",
                        "message": "Failed to revoke Stripe authentication",
                    },
                }
            ), 500

        logger.info(f"Stripe authentication revoked for user: {user_id}")

        return jsonify(
            {
                "ok": True,
                "message": "Stripe authentication revoked successfully",
                "user_id": user_id,
                "service": "stripe",
            }
        )

    except Exception as e:
        logger.error(f"Error revoking Stripe authentication: {e}")
        return jsonify(
            {
                "ok": False,
                "error": {
                    "code": "REVOKE_ERROR",
                    "message": f"Error revoking authentication: {str(e)}",
                },
            }
        ), 500


@auth_stripe_bp.route("/auth/stripe/config", methods=["GET"])
def get_stripe_config():
    """Get Stripe OAuth configuration"""
    return jsonify(
        {
            "ok": True,
            "service": "stripe",
            "config": {
                "client_id": STRIPE_CLIENT_ID,
                "redirect_uri": STRIPE_REDIRECT_URI,
                "auth_url": STRIPE_AUTH_URL,
                "scopes": STRIPE_SCOPES,
                "supports_refresh": True,
                "supports_revoke": True,
            },
        }
    )


# Clean up expired states periodically
def init_cleanup_scheduler():
    """Initialize periodic cleanup of expired OAuth states"""
    import threading
    import time

    def cleanup_worker():
        while True:
            try:
                cleanup_expired_states()
                time.sleep(300)  # Run every 5 minutes
            except Exception as e:
                logger.error(f"Error in OAuth state cleanup: {e}")
                time.sleep(60)  # Wait 1 minute on error

    # Start cleanup thread
    cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
    cleanup_thread.start()
    logger.info("Stripe OAuth state cleanup scheduler started")


# Initialize cleanup scheduler on module import
init_cleanup_scheduler()
