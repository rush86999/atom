"""
Shared fixtures for API contract property-based tests.

Provides API clients and Hypothesis strategies for testing:
- Malformed JSON generation
- Oversized payload strategies
- API client wrapper with authenticated requests
- Response validation helpers

Fixture reuse: Imports authenticated_client from e2e_ui fixtures
(10-100x faster than UI login) per FIXTURE_REUSE_GUIDE.md.
"""

import pytest
from hypothesis import strategies as st
from hypothesis import settings, HealthCheck


# ============================================================================
# HYPOTHESIS SETTINGS FOR API CONTRACT TESTS
# ============================================================================
#
# Uses tiered settings based on test criticality and IO cost:
# - CRITICAL: max_examples=200 (response validation, schema conformance)
# - STANDARD: max_examples=100 (malformed JSON, input validation)
# - IO_BOUND: max_examples=50 (oversized payloads, network operations)
#
# Per INVARIANTS.md guidelines for API contract testing.
# ============================================================================

HYPOTHESIS_SETTINGS_CRITICAL = {
    "suppress_health_check": [HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
    "max_examples": 200,  # Critical invariants (response validation)
    "deadline": None  # No timeout for critical tests
}

HYPOTHESIS_SETTINGS_STANDARD = {
    "suppress_health_check": [HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
    "max_examples": 100,  # Standard invariants (malformed JSON)
    "deadline": 10000  # 10 seconds per test
}

HYPOTHESIS_SETTINGS_IO = {
    "suppress_health_check": [HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
    "max_examples": 50,  # IO-bound operations (oversized payloads)
    "deadline": 30000  # 30 seconds per test
}


# ============================================================================
# API CLIENT FIXTURES (reuse from e2e_ui)
# ============================================================================
#
# Per FIXTURE_REUSE_GUIDE.md lines 117-174, we MUST import and reuse
# existing auth fixtures from tests.e2e_ui.fixtures.auth_fixtures.
#
# DO NOT create new auth fixtures - reuse authenticated_user for
# 10-100x faster authentication vs UI login.
# ============================================================================

import sys
from pathlib import Path

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from tests.e2e_ui.fixtures.auth_fixtures import authenticated_user


@pytest.fixture(scope="function")
def api_auth_client(authenticated_user):
    """
    Create an API client with authentication headers pre-configured.

    Reuses authenticated_user fixture from e2e_ui for 10-100x faster
    authentication (JWT token in headers vs UI login flow).

    Args:
        authenticated_user: Tuple[User, JWT token] from e2e_ui fixtures

    Returns:
        dict: Client config with headers and base URL

    Example:
        def test_api_call(api_auth_client):
            headers = api_auth_client["headers"]
            response = client.post("/api/v1/agents/execute",
                                  headers=headers,
                                  json={"test": "data"})
    """
    from fastapi.testclient import TestClient
    from main_api_app import app

    user, token = authenticated_user

    # Create TestClient with auth headers
    client_config = {
        "client": TestClient(app),
        "headers": {"Authorization": f"Bearer {token}"},
        "user_id": str(user.id),
        "token": token
    }

    return client_config


# ============================================================================
# MALFORMED JSON STRATEGIES
# ============================================================================
#
# Generates malformed JSON inputs for fuzzing API endpoints.
# Tests invariant: Malformed JSON returns 400/422 (not 500)
# ============================================================================

@pytest.fixture(scope="session")
def malformed_json_strategy():
    """
    Strategy for generating malformed JSON inputs.

    Returns:
        st.SearchStrategy: Strategy generating various malformed JSON patterns

    Patterns:
    - Random text (not valid JSON)
    - Dict with None values (invalid JSON serialization)
    - Specifically malformed JSON strings
    - Empty/null values
    - Truncated JSON

    RADII: 100 examples covers common malformed patterns (text, None,
    incomplete JSON, empty payloads) without exhaustively testing all
    possible malformed inputs.
    """
    return st.one_of(
        # Random text (not valid JSON)
        st.text(min_size=0, max_size=10000),

        # Dict with None values (invalid JSON)
        st.dictionaries(st.text(), st.none()),

        # Specifically malformed JSON strings
        st.just('{"invalid": json}'),
        st.just('{"unterminated":'),
        st.just('{"extra": "comma",}'),

        # Empty/null payloads
        st.just(''),
        st.just('null'),
        st.just('[]'),
        st.just('{}'),

        # Invalid UTF-8 sequences
        st.binary().filter(lambda b: b.decode('utf-8', errors='ignore') != b.decode('utf-8', errors='replace'))
    )


@pytest.fixture(scope="session")
def injection_payload_strategy():
    """
    Strategy for generating injection attempt payloads.

    Returns:
        st.SearchStrategy: Strategy generating SQL/injection patterns

    Tests invariant: Injection attempts are sanitized (not 500 crash)

    RADII: 100 examples covers common SQL injection and XSS patterns.
    """
    injection_patterns = [
        # SQL injection
        "'; DROP TABLE users; --",
        "1' OR '1'='1",
        "admin'--",
        "' UNION SELECT * FROM users--",

        # XSS attempts
        "<script>alert('xss')</script>",
        "javascript:alert('xss')",
        "<img src=x onerror=alert('xss')>",

        # Command injection
        "; rm -rf /",
        "| cat /etc/passwd",
        "$(whoami)",

        # Path traversal
        "../../../etc/passwd",
        "..\\..\\..\\..\\windows\\system32\\",
    ]

    return st.one_of(
        st.sampled_from(injection_patterns),
        st.text().map(lambda s: s + "\x00")  # Null bytes
    )


# ============================================================================
# OVERSIZED PAYLOAD STRATEGIES
# ============================================================================
#
# Generates oversized payloads for testing 413 responses.
# Tests invariant: Oversized payloads return 413 (not OOM/crash)
# ============================================================================

@pytest.fixture(scope="session")
def oversized_payload_strategy():
    """
    Strategy for generating oversized payload sizes.

    Returns:
        st.SearchStrategy: Strategy generating payload sizes (1MB to 100MB)

    RADII: 50 examples covers size range from 1MB to 100MB (tests OOM
    protection without exhausting test machine memory).
    """
    return st.integers(min_value=1_000_000, max_value=100_000_000)


@pytest.fixture(scope="session")
def oversized_json_strategy():
    """
    Strategy for generating oversized JSON payloads.

    Returns:
        st.SearchStrategy: Strategy generating oversized JSON dictionaries

    RADII: 50 examples covers various oversized structures (deep nesting,
    wide objects, large strings) without excessive test time.
    """
    return st.one_of(
        # Large string value
        st.dictionaries(
            st.just("data"),
            st.text(min_size=1_000_000, max_size=10_000_000)
        ),

        # Deeply nested structure (stack overflow protection)
        st.recursive(
            st.just({}),
            lambda s: st.dictionaries(st.text(), s),
            max_leaves=50
        ),

        # Wide object (many keys)
        st.dictionaries(
            st.text(min_size=5, max_size=20),
            st.text(min_size=100, max_size=1000),
            min_size=1000,
            max_size=10000
        )
    )


# ============================================================================
# RESPONSE VALIDATION HELPERS
# ============================================================================

@pytest.fixture(scope="function")
def assert_client_error():
    """
    Assertion helper for client error responses (not server errors).

    Args:
        response: FastAPI/requests Response object

    Raises:
        AssertionError: If response is 500 (server error) or 2xx (success)

    Example:
        def test_malformed_json(api_auth_client, assert_client_error):
            response = api_auth_client["client"].post(
                "/api/v1/agents/execute",
                headers=api_auth_client["headers"],
                json={"invalid": "json"}
            )
            assert_client_error(response)  # Must be 4xx, not 500
    """
    def _assert(response):
        # Must be client error (4xx), not server error (5xx)
        assert 400 <= response.status_code < 500, \
            f"Expected client error (4xx), got {response.status_code}: {response.text[:200]}"

        # Specifically NOT 500 Internal Server Error
        assert response.status_code != 500, \
            f"API returned 500 Internal Server Error (invariant violation): {response.text[:200]}"

        # Must not be 2xx success
        assert not (200 <= response.status_code < 300), \
            f"Expected client error, got success {response.status_code}: {response.text[:200]}"

    return _assert


@pytest.fixture(scope="function")
def assert_payload_too_large():
    """
    Assertion helper for oversized payload responses (413).

    Args:
        response: FastAPI/requests Response object

    Raises:
        AssertionError: If response is not 413 or is 500

    Example:
        def test_oversized_payload(api_auth_client, assert_payload_too_large):
            large_data = {"data": "x" * 50_000_000}
            response = api_auth_client["client"].post(
                "/api/v1/agents/execute",
                headers=api_auth_client["headers"],
                json=large_data
            )
            assert_payload_too_large(response)  # Must be 413
    """
    def _assert(response):
        # Must be 413 Payload Too Large or 400 Bad Request
        assert response.status_code in [400, 413], \
            f"Expected 413 Payload Too Large or 400, got {response.status_code}: {response.text[:200]}"

        # Specifically NOT 500 Internal Server Error
        assert response.status_code != 500, \
            f"API returned 500 Internal Server Error (invariant violation): {response.text[:200]}"

    return _assert


@pytest.fixture(scope="function")
def assert_response_schema():
    """
    Assertion helper for response schema validation.

    Args:
        response: FastAPI/requests Response object
        required_fields: List of required field names

    Raises:
        AssertionError: If response missing required fields or invalid content-type

    Example:
        def test_response_schema(api_auth_client, assert_response_schema):
            response = api_auth_client["client"].get(
                "/api/v1/agents",
                headers=api_auth_client["headers"]
            )
            assert_response_schema(response, required_fields=["agents", "total"])
    """
    def _assert(response, required_fields=None):
        # Check content-type is JSON
        assert "application/json" in response.headers.get("content-type", ""), \
            f"Response content-type must be JSON, got: {response.headers.get('content-type')}"

        # Check response can be parsed as JSON
        try:
            data = response.json()
        except Exception as e:
            raise AssertionError(f"Response body is not valid JSON: {e}")

        # Check required fields present
        if required_fields:
            missing_fields = [f for f in required_fields if f not in data]
            assert len(missing_fields) == 0, \
                f"Response missing required fields: {missing_fields}. Got keys: {list(data.keys())}"

    return _assert
