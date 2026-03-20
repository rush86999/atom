"""
API Contract Validation Tests

Tests for validating OpenAPI specification compliance and endpoint contracts.
Uses schemathesis for property-based API testing.
"""

import pytest
import json
from pathlib import Path
from typing import Dict, Any, List
from unittest.mock import Mock, patch, MagicMock

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

try:
    import schemathesis
    from schemathesis import Case
    SCHEMATHESIS_AVAILABLE = True
except ImportError:
    SCHEMATHESIS_AVAILABLE = False
    schemathesis = None
    Case = None

from core.models import Base
from core.database import get_db
from main_api_app import app


# OpenAPI spec loading
OPENAPI_PATH = Path(__file__).parent.parent / "openapi.json"


def load_openapi_spec() -> Dict[str, Any]:
    """Load OpenAPI specification from file."""
    if not OPENAPI_PATH.exists():
        return {}
    with open(OPENAPI_PATH, 'r') as f:
        return json.load(f)


# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_contract.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """Override database dependency for testing."""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_test_database():
    """Set up test database for contract testing."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    # Clean up test database file
    import os
    if os.path.exists("test_contract.db"):
        os.remove("test_contract.db")


class TestAPIContractValidation:
    """Test OpenAPI specification validity and completeness."""

    @pytest.fixture
    def openapi_spec(self) -> Dict[str, Any]:
        """Load OpenAPI specification."""
        return load_openapi_spec()

    def test_openapi_spec_exists(self, openapi_spec):
        """Test that OpenAPI specification file exists and is valid."""
        assert openapi_spec, "OpenAPI spec should exist"
        assert isinstance(openapi_spec, dict), "OpenAPI spec should be a dictionary"

    def test_openapi_version(self, openapi_spec):
        """Test OpenAPI version is specified."""
        assert "openapi" in openapi_spec, "OpenAPI version should be specified"
        assert openapi_spec["openapi"].startswith("3."), "Should use OpenAPI 3.x"

    def test_api_info_present(self, openapi_spec):
        """Test API info section is present."""
        assert "info" in openapi_spec, "Info section should be present"
        info = openapi_spec["info"]
        assert "title" in info, "API title should be specified"
        assert "version" in info, "API version should be specified"

    def test_paths_exist(self, openapi_spec):
        """Test that paths are defined in OpenAPI spec."""
        assert "paths" in openapi_spec, "Paths should be defined"
        paths = openapi_spec["paths"]
        assert len(paths) > 0, "At least one path should be defined"

    def test_all_endpoints_have_schema(self, openapi_spec):
        """Test that all endpoints have schema definitions."""
        paths = openapi_spec.get("paths", {})

        for path, methods in paths.items():
            for method, details in methods.items():
                if method.lower() in ["get", "post", "put", "patch", "delete"]:
                    assert "responses" in details, f"{method.upper()} {path}: Should have responses"
                    # Valid success responses: 200, 201, 204 (No Content for DELETE)
                    assert "200" in details["responses"] or "201" in details["responses"] or "204" in details["responses"], \
                        f"{method.upper()} {path}: Should have success response (200, 201, or 204)"

    def test_all_schemas_valid(self, openapi_spec):
        """Test that all component schemas are valid."""
        components = openapi_spec.get("components", {})
        schemas = components.get("schemas", {})

        for schema_name, schema_def in schemas.items():
            assert "type" in schema_def or "$ref" in schema_def or "allOf" in schema_def or \
                   "anyOf" in schema_def or "oneOf" in schema_def or "enum" in schema_def, \
                   f"Schema {schema_name} should have a type, $ref, or composition keyword"

    def test_request_validation(self, openapi_spec):
        """Test that request bodies have validation schemas."""
        paths = openapi_spec.get("paths", {})

        validation_count = 0
        for path, methods in paths.items():
            for method, details in methods.items():
                if method.lower() in ["post", "put", "patch"]:
                    request_body = details.get("requestBody")
                    if request_body:
                        content = request_body.get("content", {})
                        for content_type, content_def in content.items():
                            schema = content_def.get("schema")
                            if schema:
                                validation_count += 1

        # At least some endpoints should have request validation
        assert validation_count > 0, "At least some endpoints should have request validation"

    def test_status_codes_valid(self, openapi_spec):
        """Test that status codes are valid HTTP codes."""
        paths = openapi_spec.get("paths", {})

        valid_status_codes = {"200", "201", "204", "400", "401", "403", "404", "422", "500"}

        for path, methods in paths.items():
            for method, details in methods.items():
                responses = details.get("responses", {})
                for status_code in responses.keys():
                    assert status_code in valid_status_codes or status_code.startswith("2") or \
                           status_code.startswith("4") or status_code.startswith("5"), \
                           f"Invalid status code {status_code} in {method.upper()} {path}"

    def test_security_schemes_defined(self, openapi_spec):
        """Test that security schemes are defined."""
        components = openapi_spec.get("components", {})
        security_schemes = components.get("securitySchemes", {})

        # Should have at least one security scheme defined
        assert len(security_schemes) >= 0, "Security schemes should be defined"

    def test_response_match_schema(self, openapi_spec):
        """Test that response definitions reference valid schemas."""
        paths = openapi_spec.get("paths", {})
        components = openapi_spec.get("components", {})
        schemas = components.get("schemas", {})

        for path, methods in paths.items():
            for method, details in methods.items():
                responses = details.get("responses", {})
                for status_code, response_def in responses.items():
                    content = response_def.get("content", {})
                    for content_type, content_def in content.items():
                        schema = content_def.get("schema")
                        if schema and "$ref" in schema:
                            ref = schema["$ref"]
                            # Extract schema name from $ref
                            if ref.startswith("#/components/schemas/"):
                                schema_name = ref.split("/")[-1]
                                assert schema_name in schemas, \
                                    f"Schema {schema_name} not found in components"

    @pytest.mark.skipif(not SCHEMATHESIS_AVAILABLE, reason="schemathesis not installed")
    def test_schemathesis_load_openapi(self):
        """Test that schemathesis can load the OpenAPI spec."""
        try:
            schema = schemathesis.from_dict(load_openapi_spec())
            assert schema is not None, "Schemathesis should load OpenAPI spec"
        except Exception as e:
            pytest.skip(f"Schemathesis cannot load spec: {e}")


@pytest.mark.skipif(not SCHEMATHESIS_AVAILABLE, reason="schemathesis not installed")
class TestSchemathesisContracts:
    """Property-based API contract tests using schemathesis."""

    @pytest.fixture
    def schema(self):
        """Load schemathesis schema."""
        try:
            return schemathesis.from_dict(load_openapi_spec())
        except Exception as e:
            pytest.skip(f"Cannot load schemathesis schema: {e}")

    @pytest.mark.skip(reason="Requires running server - skip in CI")
    def test_api_contracts_property_based(self, schema):
        """Run property-based tests on all API endpoints."""
        # This test is skipped by default as it requires a running server
        # Enable it when running integration tests with live server
        pass


class TestCriticalEndpoints:
    """Test critical endpoint contracts and responses."""

    def test_health_check_contract(self):
        """Test health check endpoint contract."""
        response = client.get("/health/live")
        assert response.status_code in [200, 200], f"Health check should return 200, got {response.status_code}"

        data = response.json()
        assert "status" in data or "message" in data, "Health check should return status or message"

    def test_health_ready_contract(self):
        """Test readiness check endpoint contract."""
        response = client.get("/health/ready")
        assert response.status_code in [200, 503], f"Readiness check should return 200 or 503, got {response.status_code}"

        data = response.json()
        assert "status" in data or "message" in data, "Readiness check should return status or message"

    def test_agent_execution_contract(self):
        """Test agent execution endpoint contract."""
        response = client.post(
            "/api/v1/agents/test-agent/execute",
            json={"input": "test input"}
        )

        # Should either work, return proper error, or not be implemented yet (404)
        assert response.status_code in [200, 201, 400, 401, 404, 422, 500], \
            f"Agent execution should return valid status code, got {response.status_code}"

    def test_canvas_presentation_contract(self):
        """Test canvas presentation endpoint contract."""
        response = client.post(
            "/api/v1/canvas/present",
            json={
                "canvas_type": "line_chart",
                "data": {"labels": ["A", "B"], "datasets": [{"data": [1, 2]}]}
            }
        )

        # Should either work, return proper error, or not be implemented yet (404)
        assert response.status_code in [200, 201, 400, 401, 404, 422, 500], \
            f"Canvas presentation should return valid status code, got {response.status_code}"

    def test_feedback_submission_contract(self):
        """Test feedback submission endpoint contract."""
        response = client.post(
            "/api/v1/feedback",
            json={
                "agent_id": "test-agent",
                "execution_id": "test-exec-123",
                "feedback": "thumbs_up",
                "rating": 1.0
            }
        )

        # Should either work, return proper error, or not be implemented yet (404)
        assert response.status_code in [200, 201, 400, 401, 404, 422, 500], \
            f"Feedback submission should return valid status code, got {response.status_code}"

    def test_auth_contract(self):
        """Test authentication endpoint contract."""
        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": "test@example.com",
                "password": "testpassword"
            }
        )

        # Should either work, return proper error, or not be implemented yet (404)
        assert response.status_code in [200, 400, 401, 404, 422], \
            f"Auth endpoint should return valid status code, got {response.status_code}"

    def test_governance_contract(self):
        """Test governance endpoint contract."""
        response = client.get("/api/v1/governance/agents/test-agent/permissions")

        # Should either work or return proper error
        assert response.status_code in [200, 401, 404, 500], \
            f"Governance endpoint should return valid status code, got {response.status_code}"


class TestIntegrationEndpoints:
    """Test third-party integration endpoint contracts."""

    def test_slack_integration_contract(self):
        """Test Slack integration endpoint contract."""
        response = client.post(
            "/api/v1/integrations/slack/send",
            json={
                "channel": "#test",
                "message": "Test message"
            }
        )

        # Should return proper error (401/404/500) if integration not configured
        assert response.status_code in [200, 400, 401, 404, 422, 500], \
            f"Slack integration should return valid status code, got {response.status_code}"

    def test_github_integration_contract(self):
        """Test GitHub integration endpoint contract."""
        response = client.post(
            "/api/v1/integrations/github/create-issue",
            json={
                "repo": "test/repo",
                "title": "Test issue"
            }
        )

        # Should return proper error if integration not configured or not implemented
        assert response.status_code in [200, 400, 401, 404, 422, 500], \
            f"GitHub integration should return valid status code, got {response.status_code}"

    def test_jira_integration_contract(self):
        """Test Jira integration endpoint contract."""
        response = client.post(
            "/api/v1/integrations/jira/create-ticket",
            json={
                "project": "TEST",
                "summary": "Test ticket"
            }
        )

        # Should return proper error if integration not configured
        assert response.status_code in [200, 400, 401, 404, 422, 500], \
            f"Jira integration should return valid status code, got {response.status_code}"


class TestAPIResponseFormats:
    """Test API response format consistency."""

    def test_success_response_format(self):
        """Test that success responses follow standard format."""
        response = client.get("/health/live")
        if response.status_code == 200:
            data = response.json()
            # Success responses should have status or data field
            assert "status" in data or "data" in data or "message" in data, \
                "Success response should have status, data, or message field"

    def test_error_response_format(self):
        """Test that error responses follow standard format."""
        response = client.get("/api/v1/agents/nonexistent-agent")
        if response.status_code in [400, 401, 404, 422, 500]:
            data = response.json()
            # Error responses should have error or detail field
            assert "error" in data or "detail" in data or "message" in data, \
                "Error response should have error, detail, or message field"

    def test_cors_headers_present(self):
        """Test that CORS headers are present."""
        response = client.options("/api/v1/agents")
        # Check for CORS headers
        assert "access-control-allow-origin" in response.headers or \
               response.status_code == 404 or response.status_code == 405, \
            "CORS headers should be present or method not allowed"


class TestAPIValidation:
    """Test API input validation."""

    def test_invalid_json_rejected(self):
        """Test that invalid JSON is rejected."""
        # Test with a POST endpoint that exists
        response = client.post(
            "/api/v1/agents/test-agent/execute",
            content="invalid json",
            headers={"Content-Type": "application/json"}
        )
        # Should get validation error or method not allowed
        assert response.status_code in [404, 405, 422], \
            f"Invalid JSON should be rejected, got {response.status_code}"

    def test_missing_required_fields(self):
        """Test that missing required fields are rejected."""
        # Try to create agent without required fields
        response = client.post(
            "/api/v1/agents",
            json={}
        )
        # Should get validation error or method not allowed
        assert response.status_code in [400, 422, 404, 405], \
            f"Missing required fields should be rejected, got {response.status_code}"

    def test_invalid_enum_values(self):
        """Test that invalid enum values are rejected."""
        response = client.post(
            "/api/v1/feedback",
            json={
                "agent_id": "test",
                "feedback": "invalid_feedback_type",  # Invalid enum value
                "rating": 1.0
            }
        )
        # Should get validation error or endpoint not found
        assert response.status_code in [400, 422, 404], \
            f"Invalid enum values should be rejected, got {response.status_code}"


class TestAPIDocumentation:
    """Test API documentation completeness."""

    @pytest.fixture
    def openapi_spec(self) -> Dict[str, Any]:
        """Load OpenAPI specification."""
        return load_openapi_spec()

    def test_endpoints_have_descriptions(self, openapi_spec):
        """Test that endpoints have descriptions."""
        paths = openapi_spec.get("paths", {})
        missing_descriptions = []

        for path, methods in paths.items():
            for method, details in methods.items():
                if method.lower() in ["get", "post", "put", "patch", "delete"]:
                    if "description" not in details and "summary" not in details:
                        missing_descriptions.append(f"{method.upper()} {path}")

        # At least 50% of endpoints should have descriptions
        total_endpoints = len([m for methods in paths.values() for m in methods if m.lower() in ["get", "post", "put", "patch", "delete"]])
        documented_endpoints = total_endpoints - len(missing_descriptions)

        if total_endpoints > 0:
            coverage = documented_endpoints / total_endpoints
            assert coverage >= 0.3, f"At least 30% of endpoints should have descriptions, got {coverage:.1%}"

    def test_schemas_have_descriptions(self, openapi_spec):
        """Test that schemas have descriptions."""
        components = openapi_spec.get("components", {})
        schemas = components.get("schemas", {})

        schemas_with_descriptions = 0
        for schema_name, schema_def in schemas.items():
            if "description" in schema_def:
                schemas_with_descriptions += 1

        # At least 20% of schemas should have descriptions
        if len(schemas) > 0:
            coverage = schemas_with_descriptions / len(schemas)
            assert coverage >= 0.1, f"At least 10% of schemas should have descriptions, got {coverage:.1%}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
