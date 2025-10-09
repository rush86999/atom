import os
import logging
from flask import Blueprint, request, jsonify
from trello import TrelloClient

logger = logging.getLogger(__name__)

trello_auth_bp = Blueprint("trello_auth_bp", __name__)


@trello_auth_bp.route("/api/auth/trello/validate", methods=["POST"])
def validate_trello_credentials():
    """
    Validate Trello API key and token provided by frontend
    This replaces the OAuth flow with simple API key validation
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

        api_key = data.get("api_key")
        api_token = data.get("api_token")
        user_id = data.get("user_id")

        if not api_key or not api_token:
            return jsonify(
                {
                    "ok": False,
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "api_key and api_token are required",
                    },
                }
            ), 400

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

        logger.info(f"Validating Trello credentials for user {user_id}")

        # Test the credentials by making a simple API call
        try:
            client = TrelloClient(api_key=api_key, token=api_token)

            # Test connectivity by getting user info
            me = client.get_member("me")

            return jsonify(
                {
                    "ok": True,
                    "data": {
                        "user_id": user_id,
                        "trello_user": me.full_name
                        if hasattr(me, "full_name")
                        else me.username,
                        "trello_username": me.username,
                        "status": "connected",
                        "message": "Trello credentials validated successfully",
                    },
                }
            )

        except Exception as api_error:
            logger.error(
                f"Trello API validation failed for user {user_id}: {api_error}"
            )
            return jsonify(
                {
                    "ok": False,
                    "error": {
                        "code": "AUTH_ERROR",
                        "message": f"Invalid Trello credentials: {str(api_error)}",
                    },
                }
            ), 401

    except Exception as e:
        logger.error(f"Error validating Trello credentials: {e}", exc_info=True)
        return jsonify(
            {
                "ok": False,
                "error": {
                    "code": "VALIDATION_FAILED",
                    "message": f"Credential validation failed: {str(e)}",
                },
            }
        ), 500


@trello_auth_bp.route("/api/auth/trello/status", methods=["GET"])
def get_trello_status():
    """
    Get current Trello integration status for a user
    This checks if valid API keys are provided in headers
    """
    try:
        api_key = request.headers.get("X-Trello-API-Key")
        api_token = request.headers.get("X-Trello-API-Token")
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

        if not api_key or not api_token:
            return jsonify(
                {
                    "ok": True,
                    "service": "trello",
                    "status": "disconnected",
                    "message": "Trello API keys not provided in headers",
                    "available": False,
                    "mock_data": False,
                }
            )

        # Test the credentials
        try:
            client = TrelloClient(api_key=api_key, token=api_token)
            me = client.get_member("me")

            return jsonify(
                {
                    "ok": True,
                    "service": "trello",
                    "status": "connected",
                    "message": "Trello service connected successfully",
                    "available": True,
                    "mock_data": False,
                    "user": me.full_name if hasattr(me, "full_name") else me.username,
                }
            )

        except Exception as api_error:
            logger.error(f"Trello status check failed for user {user_id}: {api_error}")
            return jsonify(
                {
                    "ok": True,
                    "service": "trello",
                    "status": "disconnected",
                    "message": f"Trello connection failed: {str(api_error)}",
                    "available": False,
                    "mock_data": False,
                }
            )

    except Exception as e:
        logger.error(f"Error checking Trello status: {e}")
        return jsonify(
            {
                "ok": False,
                "service": "trello",
                "status": "error",
                "message": f"Status check failed: {str(e)}",
            }
        ), 500


@trello_auth_bp.route("/api/auth/trello/instructions", methods=["GET"])
def get_trello_instructions():
    """
    Provide instructions for users to get their Trello API key and token
    """
    return jsonify(
        {
            "ok": True,
            "data": {
                "service": "trello",
                "instructions": {
                    "title": "Connect Your Trello Account",
                    "description": "Trello uses API keys and tokens for authentication. Each user needs their own API token.",
                    "steps": [
                        {
                            "step": 1,
                            "title": "Get Your API Key",
                            "description": "Go to https://trello.com/power-ups/admin and generate a new API key for your Power-Up",
                        },
                        {
                            "step": 2,
                            "title": "Generate Your Token",
                            "description": "On the same page, click the 'Token' link next to your API key to generate a token",
                        },
                        {
                            "step": 3,
                            "title": "Enter Credentials",
                            "description": "Enter your API key and token in the ATOM settings page",
                        },
                        {
                            "step": 4,
                            "title": "Validate Connection",
                            "description": "Click 'Validate' to test your connection to Trello",
                        },
                    ],
                    "note": "Your API key identifies the application, while your token grants access to your specific Trello account. Keep your token secure!",
                },
            },
        }
    )
