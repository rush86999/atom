"""
OAuth 2.0 Configuration for LLM Providers

Defines OAuth 2.0 endpoints and scopes for supported LLM providers:
- Google AI Studio (Gemini)
- OpenAI
- Anthropic (Claude)
- Hugging Face
"""

import os
from typing import Dict, List, Optional

# OAuth configuration for each LLM provider
LLM_OAUTH_CONFIGS: Dict[str, Dict[str, any]] = {
    "google": {
        "client_id_env": "GOOGLE_OAUTH_CLIENT_ID",
        "client_secret_env": "GOOGLE_OAUTH_CLIENT_SECRET",
        "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "scopes": [
            "https://www.googleapis.com/auth/cloud-platform",
            "https://www.googleapis.com/auth/generative_language.tuning"  # For fine-tuning access
        ],
        "token_type": "Bearer",
        "pkce": True,  # Google recommends PKCE for additional security
    },
    "openai": {
        "client_id_env": "OPENAI_OAUTH_CLIENT_ID",
        "client_secret_env": "OPENAI_OAUTH_CLIENT_SECRET",
        "auth_url": "https://platform.openai.com/oauth/authorize",
        "token_url": "https://api.openai.com/v1/oauth/token",
        "scopes": [
            "api:model:read",
            "api:model:write",
            "api:completion:read",
            "api:completion:write"
        ],
        "token_type": "Bearer",
        "pkce": False,
    },
    "anthropic": {
        "client_id_env": "ANTHROPIC_OAUTH_CLIENT_ID",
        "client_secret_env": "ANTHROPIC_OAUTH_CLIENT_SECRET",
        "auth_url": "https://oauth.anthropic.com/authorize",
        "token_url": "https://oauth.anthropic.com/token",
        "scopes": [
            "api:read",
            "api:write"
        ],
        "token_type": "Bearer",
        "pkce": False,
    },
    "huggingface": {
        "client_id_env": "HUGGINGFACE_OAUTH_CLIENT_ID",
        "client_secret_env": "HUGGINGFACE_OAUTH_CLIENT_SECRET",
        "auth_url": "https://huggingface.co/oauth/authorize",
        "token_url": "https://huggingface.co/oauth/token",
        "scopes": [
            "read-repos",
            "write-repos",
            "inference-api"
        ],
        "token_type": "Bearer",
        "pkce": False,
    }
}

# Provider display names
PROVIDER_DISPLAY_NAMES = {
    "google": "Google AI Studio",
    "openai": "OpenAI",
    "anthropic": "Anthropic",
    "huggingface": "Hugging Face"
}

# Default OAuth callback URL (can be overridden by environment variable)
DEFAULT_OAUTH_REDIRECT_URI = os.getenv(
    "LLM_OAUTH_REDIRECT_URI",
    "http://localhost:8000/api/v1/llm/oauth/callback"
)


def get_oauth_config(provider_id: str) -> Optional[Dict[str, any]]:
    """
    Get OAuth configuration for a specific provider.

    Args:
        provider_id: Provider identifier (google, openai, anthropic, huggingface)

    Returns:
        OAuth configuration dict or None if provider not found
    """
    return LLM_OAUTH_CONFIGS.get(provider_id)


def get_provider_client_id(provider_id: str) -> Optional[str]:
    """
    Get OAuth client ID for a provider from environment.

    Args:
        provider_id: Provider identifier

    Returns:
        Client ID or None if not configured
    """
    config = get_oauth_config(provider_id)
    if not config:
        return None

    return os.getenv(config["client_id_env"])


def get_provider_client_secret(provider_id: str) -> Optional[str]:
    """
    Get OAuth client secret for a provider from environment.

    Args:
        provider_id: Provider identifier

    Returns:
        Client secret or None if not configured
    """
    config = get_oauth_config(provider_id)
    if not config:
        return None

    return os.getenv(config["client_secret_env"])


def is_provider_oauth_configured(provider_id: str) -> bool:
    """
    Check if OAuth is properly configured for a provider.

    Args:
        provider_id: Provider identifier

    Returns:
        True if both client ID and secret are configured
    """
    client_id = get_provider_client_id(provider_id)
    client_secret = get_provider_client_secret(provider_id)

    return bool(client_id and client_secret)


def list_supported_providers() -> List[str]:
    """
    Get list of supported OAuth providers.

    Returns:
        List of provider IDs
    """
    return list(LLM_OAUTH_CONFIGS.keys())


def get_provider_display_name(provider_id: str) -> str:
    """
    Get display name for a provider.

    Args:
        provider_id: Provider identifier

    Returns:
        Display name or provider_id if not found
    """
    return PROVIDER_DISPLAY_NAMES.get(provider_id, provider_id)
