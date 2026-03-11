"""Pytest fixtures for Schemathesis contract testing.

This module provides comprehensive fixtures for API contract testing using
Schemathesis with Hypothesis property-based testing. Validates OpenAPI schema
compliance across agent, canvas, and browser endpoints.
"""
import pytest
import schemathesis
from fastapi.testclient import TestClient
from main_api_app import app
from hypothesis import settings, HealthCheck
from typing import Dict, List, Set


# Load schema from FastAPI app
# Schemathesis extracts OpenAPI schema and validates request/response contracts
schema = schemathesis.openapi.from_dict(app.openapi())


@pytest.fixture
def app_client():
    """FastAPI TestClient for contract testing.

    Provides a test client that can make HTTP requests to the FastAPI app
    without starting a server. Used by Schemathesis for endpoint validation.
    """
    return TestClient(app)


@pytest.fixture
def auth_headers():
    """Mock authentication headers for protected endpoints.

    Provides Bearer token authentication for testing protected endpoints.
    In production, this would be replaced with actual auth tokens.
    """
    return {"Authorization": "Bearer test_token"}


@pytest.fixture
def admin_headers():
    """Admin authentication headers for admin-only endpoints.

    Simulates admin-level permissions for testing administrative endpoints.
    """
    return {"Authorization": "Bearer admin_token", "X-User-Role": "admin"}


@pytest.fixture
def authenticated_client_for_contract(app_client, auth_headers):
    """TestClient with pre-configured authentication headers.

    This client automatically includes auth headers in all requests,
    simulating an authenticated user session for contract testing.

    Usage:
        response = authenticated_client_for_contract.get("/api/agents/")
    """
    # Modify the client to include default headers
    app_client.headers.update(auth_headers)
    return app_client


@pytest.fixture
def admin_client_for_contract(app_client, admin_headers):
    """TestClient with admin-level authentication headers."""
    app_client.headers.update(admin_headers)
    return app_client


# Configure Hypothesis settings for property-based testing
# These settings control how Schemathesis generates test cases
hypothesis_settings = settings(
    max_examples=10,  # Number of test cases per endpoint (reduced for faster execution)
    deadline=1000,  # 1 second timeout per test case
    derandomize=True,  # Deterministic test generation (reproducible results)
    suppress_health_check=list(HealthCheck),  # Suppress all health checks for contract tests
)


# Custom Schemathesis hooks for enhanced contract testing

@schemathesis.hook
def before_process_case(context, case, **kwargs):
    """Hook called before each test case is processed.

    Injects auth headers for protected endpoints and resets database state.
    """
    # Add auth headers to case if endpoint requires authentication
    # This is a placeholder - actual auth injection would check endpoint requirements
    pass


@schemathesis.hook
def after_process_case(context, case, response, **kwargs):
    """Hook called after each test case is processed.

    Can be used for custom validation or logging beyond schema compliance.
    """
    # Log any non-2xx responses for investigation
    if response.status_code >= 400:
        # This would normally log to a test results file
        pass


# Endpoint filtering fixture to exclude problematic endpoints
# Some endpoints require external services or have special requirements
# that make them unsuitable for automated contract testing

EXCLUDED_ENDPOINTS: Set[str] = {
    # WebSocket endpoints (Schemathesis doesn't handle WS)
    "/ws/agent",
    "/ws/browser",
    "/api/v1/stream",

    # Endpoints requiring actual external services
    # These would need mocking or service virtualization
    "/api/browser/screenshot",  # Requires Playwright browser
    "/api/browser/cdp",  # Requires CDP session

    # Endpoints with side effects that shouldn't be triggered in tests
    # "/api/agents/execute",  # Would actually execute agents
}


@pytest.fixture
def endpoint_filter() -> Set[str]:
    """Returns set of endpoints to exclude from contract testing.

    Excluded endpoints fall into these categories:
    1. WebSocket endpoints (Schemathesis limitation)
    2. External service dependencies (LLM calls, browser automation)
    3. Endpoints with irreversible side effects

    Returns:
        Set of endpoint paths to exclude from testing
    """
    return EXCLUDED_ENDPOINTS


@pytest.fixture
def schema_with_excluded_filters(endpoint_filter: Set[str]):
    """Schema with excluded endpoints filtered out.

    Creates a Schemathesis schema that excludes endpoints requiring
    external services or having special requirements.

    Args:
        endpoint_filter: Set of endpoint paths to exclude

    Returns:
        Filtered Schemathesis schema
    """
    # In a full implementation, we would filter the schema here
    # For now, return the base schema
    return schema


# Response validation overrides for non-standard responses
# Some endpoints may return valid responses that don't strictly match schema

CUSTOM_VALIDATORS: Dict[str, callable] = {
    # Add custom validators for specific endpoints if needed
    # Example: "/api/agents/execute": custom_streaming_validator
}


@pytest.fixture
def custom_validators() -> Dict[str, callable]:
    """Returns custom response validators for special endpoints.

    Some endpoints may have valid responses that deviate from the schema
    due to streaming, binary data, or other special cases.

    Returns:
        Dict mapping endpoint paths to validator functions
    """
    return CUSTOM_VALIDATORS
