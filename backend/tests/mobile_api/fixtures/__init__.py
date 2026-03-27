"""
Mobile API test fixtures.

This package provides API-first authentication fixtures for mobile API testing.
Fixtures use FastAPI TestClient for in-memory API testing (no server startup needed).
"""

from .mobile_fixtures import (
    mobile_api_client,
    mobile_auth_token,
    mobile_auth_headers,
    mobile_test_user,
)

__all__ = [
    "mobile_api_client",
    "mobile_auth_token",
    "mobile_auth_headers",
    "mobile_test_user",
]
