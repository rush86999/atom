"""Pytest fixtures for Schemathesis contract testing."""
import pytest
import schemathesis
from fastapi.testclient import TestClient
from main_api_app import app
from hypothesis import settings, HealthCheck

# Load schema from FastAPI app using TestClient wrapper
schema = schemathesis.openapi.from_dict(app.openapi())

@pytest.fixture
def app_client():
    """FastAPI TestClient for contract testing."""
    return TestClient(app)

@pytest.fixture
def auth_headers():
    """Mock authentication headers for protected endpoints."""
    return {"Authorization": "Bearer test_token"}

@pytest.fixture
def schema_with_auth(auth_headers):
    """Schema configured with authentication headers."""
    return schemathesis.openapi.from_dict(
        app.openapi(),
        headers=auth_headers
    )

# Configure Hypothesis settings for Schemathesis
hypothesis_settings = settings(
    max_examples=50,
    deadline=1000,  # 1 second timeout per test
    derandomize=True,  # Deterministic test generation
    suppress_health_check=list(HealthCheck)
)
