"""
E2E Test Fixtures Package.

This package provides reusable test data factories and fixtures for end-to-end testing
with real services (databases, APIs, external integrations).
"""
from .service_mock_fixtures import (
    mock_tavily_search,
    mock_tavily_error,
    mock_slack_webhook,
    mock_slack_api,
    mock_shopify_api,
    mock_shopify_webhook,
    mock_whatsapp_api,
    mock_whatsapp_webhook,
    mock_rate_limit,
    mock_rate_limit_recovery,
    real_tavily_client,
    real_slack_webhook,
    real_shopify_credentials,
    real_whatsapp_credentials,
    mock_atom_saas_marketplace,
    mock_httpx_client,
)

__all__ = [
    "mock_tavily_search",
    "mock_tavily_error",
    "mock_slack_webhook",
    "mock_slack_api",
    "mock_shopify_api",
    "mock_shopify_webhook",
    "mock_whatsapp_api",
    "mock_whatsapp_webhook",
    "mock_rate_limit",
    "mock_rate_limit_recovery",
    "real_tavily_client",
    "real_slack_webhook",
    "real_shopify_credentials",
    "real_whatsapp_credentials",
    "mock_atom_saas_marketplace",
    "mock_httpx_client",
]
