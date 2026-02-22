"""
Conftest for API integration tests.

Provides database session fixture for API tests with enhanced
authenticated request factories and API test utilities.
"""

import pytest
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional
from fastapi.testclient import TestClient

from core.database import SessionLocal
from core.models import User, UserStatus
from main_api_app import app


@pytest.fixture
def db():
    """Create a test database session.

    Uses transaction rollback pattern to isolate test data.
    """
    db = SessionLocal()
    db.begin_nested()  # Begin transaction for test isolation

    try:
        yield db
        db.rollback()  # Rollback all changes, including committed data
    finally:
        db.close()


@pytest.fixture
def authenticated_client(db):
    """Create TestClient with pre-configured auth override.

    Provides ready-to-use client for authenticated requests.
    Mocks a super_admin user with all permissions.

    Usage:
        def test_authenticated_endpoint(authenticated_client):
            response = authenticated_client.get("/api/agents")
            assert response.status_code == 200
    """
    from core.auth import get_current_user

    # Create mock super_admin user
    mock_user = User(
        id="test-user-id",
        email="test@example.com",
        first_name="Test",
        last_name="User",
        role="super_admin",
        status=UserStatus.ACTIVE.value,
        email_verified=True
    )

    # Override get_current_user dependency
    app.dependency_overrides[get_current_user] = lambda: mock_user

    # Override database
    from core.database import get_db as original_get_db
    app.dependency_overrides[original_get_db] = lambda: db

    yield TestClient(app)

    # Clean up
    app.dependency_overrides.clear()


@pytest.fixture
def api_request_factory():
    """Factory for creating API request payloads.

    Provides helper methods to generate valid request data for common API endpoints.
    Ensures tests use properly structured payloads with all required fields.

    Usage:
        def test_create_agent(api_request_factory):
            agent_data = api_request_factory.create_agent_request(
                name="My Agent",
                category="automation"
            )
            response = client.post("/api/agents", json=agent_data)
    """

    class APIRequestFactory:
        """Factory for creating API request payloads."""

        @staticmethod
        def create_agent_request(
            name: str,
            category: str = "automation",
            status: str = "idle",
            confidence_score: float = 0.8,
            description: Optional[str] = None
        ) -> Dict[str, Any]:
            """Create valid agent creation request payload.

            Args:
                name: Agent name (required)
                category: Agent category (default: "automation")
                status: Agent status (default: "idle")
                confidence_score: Agent confidence (default: 0.8)
                description: Optional description

            Returns:
                Valid agent request dictionary
            """
            return {
                "name": name,
                "category": category,
                "module_path": "test.module",
                "class_name": "TestClass",
                "status": status,
                "confidence_score": confidence_score,
                "description": description or f"{name} agent for {category}"
            }

        @staticmethod
        def create_canvas_request(
            canvas_id: str,
            components: list,
            layout: Optional[Dict[str, Any]] = None,
            title: Optional[str] = None
        ) -> Dict[str, Any]:
            """Create valid canvas request payload.

            Args:
                canvas_id: Canvas ID (required)
                components: List of canvas components (required)
                layout: Optional layout configuration
                title: Optional canvas title

            Returns:
                Valid canvas request dictionary
            """
            return {
                "canvas_id": canvas_id,
                "title": title or f"Canvas {canvas_id}",
                "components": components,
                "layout": layout or {"type": "grid"}
            }

        @staticmethod
        def create_workflow_request(
            name: str,
            steps: list,
            description: Optional[str] = None,
            category: str = "automation",
            complexity: str = "intermediate"
        ) -> Dict[str, Any]:
            """Create valid workflow template request payload.

            Args:
                name: Workflow name (required)
                steps: List of workflow steps (required)
                description: Optional description
                category: Workflow category (default: "automation")
                complexity: Workflow complexity (default: "intermediate")

            Returns:
                Valid workflow request dictionary
            """
            return {
                "name": name,
                "description": description or f"{name} workflow",
                "category": category,
                "complexity": complexity,
                "tags": ["test", "automation"],
                "steps": steps
            }

        @staticmethod
        def create_project_request(
            name: str,
            description: Optional[str] = None,
            status: str = "active"
        ) -> Dict[str, Any]:
            """Create valid project request payload.

            Args:
                name: Project name (required)
                description: Optional description
                status: Project status (default: "active")

            Returns:
                Valid project request dictionary
            """
            return {
                "name": name,
                "description": description or f"{name} project",
                "status": status
            }

        @staticmethod
        def create_canvas_form_submission(
            canvas_id: str,
            form_data: Dict[str, Any],
            agent_id: Optional[str] = None
        ) -> Dict[str, Any]:
            """Create valid canvas form submission request.

            Args:
                canvas_id: Canvas ID (required)
                form_data: Form field data (required)
                agent_id: Optional agent ID submitting the form

            Returns:
                Valid form submission dictionary
            """
            return {
                "canvas_id": canvas_id,
                "form_data": form_data,
                "agent_id": agent_id
            }

    return APIRequestFactory()


@pytest.fixture
def validation_error_test_data():
    """Provide invalid request payloads for validation testing.

    Returns a dictionary of test cases that should trigger validation errors.
    Useful for testing API error handling and Pydantic validation.

    Usage:
        def test_validation_errors(validation_error_test_data):
            # Test missing required field
            response = client.post(
                "/api/agents",
                json=validation_error_test_data["missing_required_field"]
            )
            assert response.status_code == 422
    """
    return {
        # Missing required fields
        "missing_required_field": {
            "description": "Missing the 'name' field"
            # Actual payload depends on endpoint being tested
        },

        # Invalid data types
        "invalid_type_string_instead_of_int": {
            "field": "should_be_int",
            "value": "not_an_integer"
        },

        "invalid_type_string_instead_of_bool": {
            "field": "should_be_bool",
            "value": "not_a_boolean"
        },

        # Empty strings where not allowed
        "empty_string_name": {
            "name": "",
            "category": "testing"
        },

        "empty_string_email": {
            "email": "",
            "name": "Test User"
        },

        # Negative values for positive-only fields
        "negative_confidence_score": {
            "name": "Test",
            "confidence_score": -0.5  # Should be 0-1
        },

        "negative_count": {
            "name": "Test",
            "count": -1  # Should be >= 0
        },

        # Out-of-range values
        "confidence_score_too_high": {
            "name": "Test",
            "confidence_score": 1.5  # Should be <= 1.0
        },

        "negative_duration": {
            "name": "Test",
            "duration_seconds": -10  # Should be >= 0
        },

        # Malformed data structures
        "malformed_json_array": {
            "name": "Test",
            "tags": "not_an_array"  # Should be array
        },

        "malformed_json_object": {
            "name": "Test",
            "metadata": "not_an_object"  # Should be object
        },

        # SQL injection attempts
        "sql_injection_single_quote": {
            "name": "'; DROP TABLE agents; --",
            "category": "testing"
        },

        "sql_injection_union_select": {
            "name": "Test' UNION SELECT * FROM users --",
            "category": "testing"
        },

        # XSS payloads
        "xss_script_tag": {
            "name": "<script>alert('xss')</script>",
            "category": "testing"
        },

        "xss_onclick": {
            "name": "<div onclick='alert(1)'>Click me</div>",
            "category": "testing"
        },

        # Invalid UUID format
        "invalid_uuid_string": {
            "agent_id": "not-a-valid-uuid"
        },

        "invalid_uuid_empty": {
            "agent_id": ""
        },

        # Extra fields (should be ignored by Pydantic)
        "extra_field_allowed": {
            "name": "Test",
            "category": "testing",
            "extra_field_not_in_model": "should_be_ignored"
        }
    }
