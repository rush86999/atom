"""
Shared fixtures for security property-based tests.

Provides test data and strategies for SQL injection, XSS, and CSRF testing.
"""

import pytest
from hypothesis import strategies as st
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

# Import shared fixtures from parent conftest to avoid duplication
from tests.property_tests.conftest import (
    db_session,
    client,
    DEFAULT_PROFILE,
    CI_PROFILE
)

# Import models needed for security tests
from core.models import AgentRegistry, AgentStatus


# ============================================================================
# HYPOTHESIS SETTINGS FOR SECURITY TESTS
# ============================================================================

from hypothesis import settings, HealthCheck

# STANDARD: Security invariants (SQL injection, XSS, CSRF)
HYPOTHESIS_SETTINGS_STANDARD = settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=list(HealthCheck)
)

# IO-BOUND: Security tests with database operations (SQL injection)
HYPOTHESIS_SETTINGS_IO = settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=list(HealthCheck)
)


# ============================================================================
# FIXTURES FOR SQL INJECTION TESTS
# ============================================================================

@pytest.fixture(scope="session")
def malicious_sql_inputs():
    """
    Strategy for generating SQL injection payloads.

    Returns a Hypothesis strategy that generates common SQL injection patterns:
    - Tautology attacks: ' OR '1'='1
    - Union-based: ' UNION SELECT * FROM users --
    - Comment-based: '; DROP TABLE users; --
    - Generic patterns with text
    """
    return st.one_of(
        st.just("' OR '1'='1"),
        st.just("'; DROP TABLE users; --"),
        st.just("1' UNION SELECT * FROM users --"),
        st.just("' OR '1'='1' --"),
        st.just("' OR '1'='1'/*"),
        st.just("admin' --"),
        st.just("admin' /*"),
        st.just("' OR 1=1#"),
        st.just("' OR 1=1--"),
        st.text().map(lambda x: f"'{x}' OR '1'='1")
    )


@pytest.fixture(scope="session")
def sql_metacharacter_patterns():
    """
    Strategy for generating SQL metacharacter patterns for filter clause testing.

    Returns a Hypothesis strategy that generates text with SQL metacharacters.
    """
    return st.lists(
        st.text().filter(lambda x: "'" in x or ";" in x or "--" in x or "/*" in x),
        min_size=1,
        max_size=10
    )


# ============================================================================
# FIXTURES FOR XSS PREVENTION TESTS
# ============================================================================

@pytest.fixture(scope="session")
def xss_payloads():
    """
    Strategy for generating XSS attack payloads.

    Returns a Hypothesis strategy that generates common XSS patterns:
    - Script tag injection: <script>alert('XSS')</script>
    - Image tag with onerror: <img src=x onerror=alert('XSS')>
    - JavaScript protocol: javascript:alert('XSS')
    - Generic patterns with text
    """
    return st.one_of(
        st.just("<script>alert('XSS')</script>"),
        st.just("<img src=x onerror=alert('XSS')>"),
        st.just("javascript:alert('XSS')"),
        st.just("<iframe src='javascript:alert(XSS)'>"),
        st.just("<body onload=alert('XSS')>"),
        st.just("<input onfocus=alert('XSS') autofocus>"),
        st.just("<select onfocus=alert('XSS') autofocus>"),
        st.just("<textarea onfocus=alert('XSS') autofocus>"),
        st.just("<marquee onstart=alert('XSS')>"),
        st.text().map(lambda x: f"<script>{x}</script>")
    )


@pytest.fixture(scope="session")
def xss_field_names():
    """
    Strategy for generating field names for XSS testing.

    Returns a Hypothesis strategy that samples common user-generated content fields.
    """
    return st.sampled_from(["name", "description", "content", "title", "body", "comment"])


@pytest.fixture(scope="session")
def xss_dictionary_payloads():
    """
    Strategy for generating dictionaries with XSS payloads for testing.

    Returns a Hypothesis strategy that generates dictionaries with field names and XSS payloads.
    """
    return st.dictionaries(
        st.sampled_from(["title", "content", "name", "description"]),
        st.just("<script>alert('XSS')</script>")
    )


# ============================================================================
# FIXTURES FOR CSRF PROTECTION TESTS
# ============================================================================

@pytest.fixture(scope="session")
def state_changing_methods():
    """
    Strategy for generating HTTP methods that change state (require CSRF protection).

    Returns a Hypothesis strategy that samples state-changing HTTP methods.
    """
    return st.sampled_from(["POST", "DELETE", "PUT", "PATCH"])


@pytest.fixture(scope="session")
def safe_methods():
    """
    Strategy for generating HTTP methods that are safe (don't require CSRF protection).

    Returns a Hypothesis strategy that samples safe HTTP methods.
    """
    return st.sampled_from(["GET", "HEAD", "OPTIONS"])


@pytest.fixture(scope="session")
def invalid_csrf_tokens():
    """
    Strategy for generating invalid CSRF tokens.

    Returns a Hypothesis strategy that generates various invalid token formats:
    - Empty string
    - Literal "invalid"
    - Literal "null"
    - Random 32-character strings (not valid tokens)
    """
    return st.one_of(
        st.just(""),
        st.just("invalid"),
        st.just("null"),
        st.text(min_size=32, max_size=32).filter(lambda x: x != "valid_token_format")
    )


@pytest.fixture(scope="function")
def csrf_test_client(db_session: Session):
    """
    Create a FastAPI TestClient without CSRF token for testing CSRF protection.

    This client simulates a request without proper CSRF token to test rejection.
    """
    from core.database import get_db
    from main_api_app import app

    # Override the database dependency
    def _get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _get_db

    with TestClient(app) as test_client:
        # Don't set CSRF token header to test rejection
        yield test_client

    # Clean up
    app.dependency_overrides.clear()
