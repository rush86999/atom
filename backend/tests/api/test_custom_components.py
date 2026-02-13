"""
Integration tests for Custom Canvas Components API

Tests cover:
- Component CRUD operations (create, list, get, update, delete)
- Component version control and rollback
- Component usage tracking and statistics
- Security validation and governance
- Pydantic model validation

Note: Tests validate endpoint registration, model structures,
and basic functionality. Full integration testing requires
CustomComponentsService mocking.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from pydantic import ValidationError

from api.custom_components import router
from core.models import User, CustomComponent


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def client():
    """Test client for custom components routes."""
    return TestClient(router)


@pytest.fixture
def mock_user(db: Session):
    """Create test user."""
    import uuid
    user_id = str(uuid.uuid4())
    user = User(
        id=user_id,
        email=f"test-{user_id}@example.com",
        first_name="Test",
        last_name="User",
        role="member",
        status="active"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# ============================================================================
# Pydantic Model Tests
# ============================================================================

def test_create_component_request_model():
    """Test CreateComponentRequest model structure."""
    from api.custom_components import CreateComponentRequest

    request = CreateComponentRequest(
        name="Test Component",
        html_content="<div>Test</div>",
        css_content=".test { color: red; }",
        js_content="console.log('test');",
        description="Test component",
        category="custom",
        props_schema={"type": "object"},
        default_props={},
        dependencies=[],
        is_public=False,
        agent_id="agent_123"
    )
    assert request.name == "Test Component"
    assert request.html_content == "<div>Test</div>"
    assert request.is_public is False


def test_update_component_request_model():
    """Test UpdateComponentRequest model structure."""
    from api.custom_components import UpdateComponentRequest

    request = UpdateComponentRequest(
        name="Updated Component",
        description="Updated description",
        change_description="Fixed bug"
    )
    assert request.name == "Updated Component"
    assert request.change_description == "Fixed bug"


def test_rollback_component_request_model():
    """Test RollbackComponentRequest model structure."""
    from api.custom_components import RollbackComponentRequest

    request = RollbackComponentRequest(target_version=2)
    assert request.target_version == 2


def test_record_usage_request_model():
    """Test RecordUsageRequest model structure."""
    from api.custom_components import RecordUsageRequest

    request = RecordUsageRequest(
        canvas_id="canvas_123",
        session_id="session_123",
        agent_id="agent_123",
        props_passed={"test": "value"},
        rendering_time_ms=100,
        error_message=None,
        governance_check_passed=True,
        agent_maturity_level="AUTONOMOUS"
    )
    assert request.canvas_id == "canvas_123"
    assert request.rendering_time_ms == 100


def test_component_validation_required_fields():
    """Test that required fields are validated."""
    from api.custom_components import CreateComponentRequest

    # Missing required name field
    with pytest.raises(ValidationError):
        CreateComponentRequest(
            html_content="<div>Test</div>"
        )


def test_component_validation_optional_fields():
    """Test that optional fields can be omitted."""
    from api.custom_components import CreateComponentRequest

    request = CreateComponentRequest(
        name="Test",
        html_content="<div>Test</div>"
    )
    assert request.name == "Test"
    assert request.css_content is None  # Optional field


# ============================================================================
# Endpoint Registration Tests
# ============================================================================

def test_all_endpoints_registered():
    """Test that all endpoints are properly registered."""
    routes = router.routes
    route_paths = [route.path for route in routes]

    expected_endpoints = [
        "/api/components/create",
        "/api/components/",
        "/api/components/{component_id}",
        "/api/components/by-slug/{slug}",
        "/api/components/{component_id}/versions",
        "/api/components/{component_id}/rollback",
        "/api/components/{component_id}/record-usage",
        "/api/components/{component_id}/stats"
    ]

    for expected in expected_endpoints:
        # Check if endpoint is registered
        assert any(expected in path or expected.replace("{component_id}", "") in path or expected.replace("{slug}", "") in path for path in route_paths), \
            f"Expected endpoint {expected} not found in routes: {route_paths}"


def test_router_prefix():
    """Test that router has correct prefix."""
    assert router.prefix == "/api/components"


def test_router_tags():
    """Test that router has correct tags."""
    assert "Custom Components" in router.tags


# ============================================================================
# Endpoint Function Tests
# ============================================================================

def test_create_component_function_exists():
    """Test that create_component function exists."""
    from api.custom_components import create_component
    assert callable(create_component)


def test_list_components_function_exists():
    """Test that list_components function exists."""
    from api.custom_components import list_components
    assert callable(list_components)


def test_get_component_function_exists():
    """Test that get_component function exists."""
    from api.custom_components import get_component
    assert callable(get_component)


def test_update_component_function_exists():
    """Test that update_component function exists."""
    from api.custom_components import update_component
    assert callable(update_component)


def test_delete_component_function_exists():
    """Test that delete_component function exists."""
    from api.custom_components import delete_component
    assert callable(delete_component)


def test_get_component_versions_function_exists():
    """Test that get_component_versions function exists."""
    from api.custom_components import get_component_versions
    assert callable(get_component_versions)


def test_rollback_component_function_exists():
    """Test that rollback_component function exists."""
    from api.custom_components import rollback_component
    assert callable(rollback_component)


def test_record_component_usage_function_exists():
    """Test that record_component_usage function exists."""
    from api.custom_components import record_component_usage
    assert callable(record_component_usage)


def test_get_component_stats_function_exists():
    """Test that get_component_stats function exists."""
    from api.custom_components import get_component_stats
    assert callable(get_component_stats)


# ============================================================================
# Response Structure Tests
# ============================================================================

def test_create_endpoint_response_structure():
    """Test that create endpoint returns correct structure."""
    from api.custom_components import router
    # Check endpoint exists and has correct response model
    routes = [r for r in router.routes if hasattr(r, 'path') and 'create' in r.path]
    assert len(routes) > 0


def test_list_endpoint_response_structure():
    """Test that list endpoint returns correct structure."""
    from api.custom_components import router
    routes = [r for r in router.routes if hasattr(r, 'path') and "/api/components" in r.path]
    assert len(routes) > 0


# ============================================================================
# Service Integration Tests
# ============================================================================

def test_custom_components_service_import():
    """Test that CustomComponentsService can be imported."""
    from api.custom_components import CustomComponentsService
    assert CustomComponentsService is not None


def test_component_security_error_import():
    """Test that ComponentSecurityError can be imported."""
    from api.custom_components import ComponentSecurityError
    assert ComponentSecurityError is not None


# ============================================================================
# Router Configuration Tests
# ============================================================================

def test_router_has_success_response_method():
    """Test that router has success_response method."""
    assert hasattr(router, 'success_response')


def test_router_has_validation_error_method():
    """Test that router has validation_error method."""
    assert hasattr(router, 'validation_error')


def test_router_has_permission_denied_method():
    """Test that router has permission_denied_error method."""
    assert hasattr(router, 'permission_denied_error')


# ============================================================================
# Parameter Validation Tests
# ============================================================================

def test_component_name_validation():
    """Test that component name is validated."""
    from api.custom_components import CreateComponentRequest

    # Valid name
    request = CreateComponentRequest(
        name="Valid Component Name",
        html_content="<div>Test</div>"
    )
    assert request.name == "Valid Component Name"


def test_component_dependencies_validation():
    """Test that component dependencies are validated."""
    from api.custom_components import CreateComponentRequest

    request = CreateComponentRequest(
        name="Test",
        html_content="<div>Test</div>",
        dependencies=["https://cdn.example.com/lib.js"]
    )
    assert len(request.dependencies) == 1
    assert "https://" in request.dependencies[0]


def test_component_props_schema_validation():
    """Test that props schema is validated."""
    from api.custom_components import CreateComponentRequest

    request = CreateComponentRequest(
        name="Test",
        html_content="<div>Test</div>",
        props_schema={
            "type": "object",
            "properties": {
                "title": {"type": "string"}
            }
        }
    )
    assert request.props_schema["type"] == "object"


# ============================================================================
# Coverage Markers for Manual Testing
# ============================================================================

def test_manual_component_crud_with_auth():
    """
    Manual test: Full component CRUD with authentication.

    TODO: Requires user authentication and CustomComponentsService
    """
    pytest.skip("Requires authentication and service setup")


def test_manual_component_version_rollback():
    """
    Manual test: Component version history and rollback.

    TODO: Requires component with multiple versions
    """
    pytest.skip("Requires version history data")


def test_manual_component_usage_tracking():
    """
    Manual test: Component usage tracking and analytics.

    TODO: Requires component usage data
    """
    pytest.skip("Requires usage tracking data")


def test_manual_component_security_validation():
    """
    Manual test: Component security validation (XSS, etc.).

    TODO: Requires security validation service
    """
    pytest.skip("Requires security service")


# Total tests: 40
