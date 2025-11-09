"""
User API Key Management Routes

This module provides Flask routes for managing user-specific API keys
for the BYOK (Bring Your Own Keys) system.
"""

import logging
from flask import Blueprint, request, jsonify
from typing import Dict, Any, List

from user_api_key_service import get_user_api_key_service

logger = logging.getLogger(__name__)

# Create blueprint for user API key routes
user_api_key_bp = Blueprint("user_api_keys", __name__, url_prefix="/api/user/api-keys")

# Available AI providers for BYOK system
AVAILABLE_AI_PROVIDERS = {
    "openai": {
        "name": "OpenAI",
        "description": "GPT models for chat, embeddings, and moderation",
        "acquisition_url": "https://platform.openai.com/api-keys",
        "expected_format": "sk-...",
        "capabilities": ["chat", "embeddings", "moderation"],
        "models": ["gpt-4", "gpt-4-turbo", "gpt-3.5-turbo", "gpt-4o"],
    },
    "deepseek": {
        "name": "DeepSeek AI",
        "description": "DeepSeek models for chat and embeddings with competitive pricing",
        "acquisition_url": "https://platform.deepseek.com/api_keys",
        "expected_format": "sk-...",
        "capabilities": ["chat", "embeddings"],
        "models": ["deepseek-chat", "deepseek-coder", "deepseek-reasoner"],
    },
    "anthropic": {
        "name": "Anthropic Claude",
        "description": "Claude models for advanced reasoning and long context",
        "acquisition_url": "https://console.anthropic.com/",
        "expected_format": "sk-ant-...",
        "capabilities": ["chat"],
        "models": ["claude-3-opus", "claude-3-sonnet", "claude-3-haiku"],
    },
    "google_gemini": {
        "name": "Google Gemini",
        "description": "Gemini models for multimodal understanding",
        "acquisition_url": "https://makersuite.google.com/app/apikey",
        "expected_format": "AIza...",
        "capabilities": ["chat", "embeddings"],
        "models": ["gemini-2.0-flash", "gemini-2.0-pro", "text-embedding-004"],
    },
    "azure_openai": {
        "name": "Azure OpenAI",
        "description": "OpenAI models through Azure cloud",
        "acquisition_url": "https://portal.azure.com/",
        "expected_format": "Azure API key + endpoint",
        "capabilities": ["chat", "embeddings"],
        "models": ["gpt-4", "gpt-35-turbo"],
    },
    "glm_4_6": {
        "name": "GLM-4.6 (Zhipu AI)",
        "description": "Advanced Chinese language model with multilingual capabilities",
        "acquisition_url": "https://open.bigmodel.cn/dev/api#model_list",
        "expected_format": "glm-...",
        "capabilities": ["chat", "embeddings", "function_calling"],
        "models": ["glm-4.6", "glm-4", "glm-4-0520", "glm-4-air"],
    },
    "kimi_k2": {
        "name": "Kimi K2 (Moonshot AI)",
        "description": "Long-context reasoning model with 200K context window",
        "acquisition_url": "https://platform.moonshot.cn/console/api-keys",
        "expected_format": "sk-...",
        "capabilities": ["chat", "long_context", "reasoning"],
        "models": ["moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"],
    },
}


@user_api_key_bp.route("/providers", methods=["GET"])
def get_available_providers():
    """
    Get list of available AI providers that support BYOK
    """
    try:
        return jsonify({"success": True, "providers": AVAILABLE_AI_PROVIDERS})
    except Exception as e:
        logger.error(f"Failed to get available providers: {e}")
        return jsonify(
            {"success": False, "error": f"Failed to get available providers: {str(e)}"}
        ), 500


@user_api_key_bp.route("/<user_id>/keys", methods=["GET"])
def get_user_api_keys(user_id: str):
    """
    Get all API keys for a specific user
    """
    try:
        service = get_user_api_key_service()
        user_keys = service.get_all_user_keys(user_id)

        # Return masked keys for security
        masked_keys = {}
        for service_name, key in user_keys.items():
            if key:
                # Mask the key (show first 4 and last 4 characters)
                masked_key = f"{key[:4]}...{key[-4:]}" if len(key) > 8 else "***"
                masked_keys[service_name] = masked_key

        return jsonify(
            {
                "success": True,
                "user_id": user_id,
                "api_keys": masked_keys,
                "configured_services": list(user_keys.keys()),
            }
        )
    except Exception as e:
        logger.error(f"Failed to get API keys for user {user_id}: {e}")
        return jsonify(
            {"success": False, "error": f"Failed to get API keys: {str(e)}"}
        ), 500


@user_api_key_bp.route("/<user_id>/keys/<service_name>", methods=["POST"])
def save_user_api_key(user_id: str, service_name: str):
    """
    Save or update an API key for a specific user and service
    """
    try:
        data = request.get_json()
        if not data or "api_key" not in data:
            return jsonify({"success": False, "error": "API key is required"}), 400

        api_key = data["api_key"].strip()
        if not api_key:
            return jsonify({"success": False, "error": "API key cannot be empty"}), 400

        # Validate service name
        if service_name not in AVAILABLE_AI_PROVIDERS:
            return jsonify(
                {
                    "success": False,
                    "error": f"Service '{service_name}' is not supported",
                }
            ), 400

        service = get_user_api_key_service()
        success = service.save_api_key(user_id, service_name, api_key)

        if success:
            logger.info(
                f"Successfully saved API key for user {user_id}, service {service_name}"
            )
            return jsonify(
                {
                    "success": True,
                    "message": f"API key for {service_name} saved successfully",
                }
            )
        else:
            return jsonify(
                {
                    "success": False,
                    "error": f"Failed to save API key for {service_name}",
                }
            ), 500

    except Exception as e:
        logger.error(
            f"Failed to save API key for user {user_id}, service {service_name}: {e}"
        )
        return jsonify(
            {"success": False, "error": f"Failed to save API key: {str(e)}"}
        ), 500


@user_api_key_bp.route("/<user_id>/keys/<service_name>", methods=["DELETE"])
def delete_user_api_key(user_id: str, service_name: str):
    """
    Delete an API key for a specific user and service
    """
    try:
        service = get_user_api_key_service()
        success = service.delete_api_key(user_id, service_name)

        if success:
            logger.info(
                f"Successfully deleted API key for user {user_id}, service {service_name}"
            )
            return jsonify(
                {
                    "success": True,
                    "message": f"API key for {service_name} deleted successfully",
                }
            )
        else:
            return jsonify(
                {
                    "success": False,
                    "error": f"Failed to delete API key for {service_name}",
                }
            ), 500

    except Exception as e:
        logger.error(
            f"Failed to delete API key for user {user_id}, service {service_name}: {e}"
        )
        return jsonify(
            {"success": False, "error": f"Failed to delete API key: {str(e)}"}
        ), 500


@user_api_key_bp.route("/<user_id>/keys/<service_name>/test", methods=["POST"])
def test_user_api_key(user_id: str, service_name: str):
    """
    Test if a user's API key is valid by making a simple API call
    """
    try:
        service = get_user_api_key_service()
        test_result = service.test_api_key(user_id, service_name)

        return jsonify({"success": True, "test_result": test_result})

    except Exception as e:
        logger.error(
            f"Failed to test API key for user {user_id}, service {service_name}: {e}"
        )
        return jsonify(
            {"success": False, "error": f"Failed to test API key: {str(e)}"}
        ), 500


@user_api_key_bp.route("/<user_id>/services", methods=["GET"])
def get_user_configured_services(user_id: str):
    """
    Get list of services for which a user has configured API keys
    """
    try:
        service = get_user_api_key_service()
        configured_services = service.list_user_services(user_id)

        # Add provider details for each configured service
        services_with_details = []
        for service_name in configured_services:
            if service_name in AVAILABLE_AI_PROVIDERS:
                provider_info = AVAILABLE_AI_PROVIDERS[service_name].copy()
                provider_info["service_name"] = service_name
                services_with_details.append(provider_info)

        return jsonify(
            {
                "success": True,
                "user_id": user_id,
                "configured_services": services_with_details,
                "total_configured": len(configured_services),
            }
        )

    except Exception as e:
        logger.error(f"Failed to get configured services for user {user_id}: {e}")
        return jsonify(
            {"success": False, "error": f"Failed to get configured services: {str(e)}"}
        ), 500


@user_api_key_bp.route("/<user_id>/status", methods=["GET"])
def get_user_api_key_status(user_id: str):
    """
    Get comprehensive status of all user API keys
    """
    try:
        service = get_user_api_key_service()
        configured_services = service.list_user_services(user_id)

        # Test each configured service
        status_results = {}
        for service_name in configured_services:
            test_result = service.test_api_key(user_id, service_name)
            status_results[service_name] = {
                "configured": True,
                "test_result": test_result,
                "provider_info": AVAILABLE_AI_PROVIDERS.get(service_name, {}),
            }

        # Add available but not configured services
        for service_name, provider_info in AVAILABLE_AI_PROVIDERS.items():
            if service_name not in configured_services:
                status_results[service_name] = {
                    "configured": False,
                    "test_result": {"success": False, "message": "Not configured"},
                    "provider_info": provider_info,
                }

        return jsonify(
            {
                "success": True,
                "user_id": user_id,
                "status": status_results,
                "summary": {
                    "total_available": len(AVAILABLE_AI_PROVIDERS),
                    "total_configured": len(configured_services),
                    "total_working": sum(
                        1
                        for s in status_results.values()
                        if s.get("test_result", {}).get("success", False)
                    ),
                },
            }
        )

    except Exception as e:
        logger.error(f"Failed to get API key status for user {user_id}: {e}")
        return jsonify(
            {"success": False, "error": f"Failed to get API key status: {str(e)}"}
        ), 500
