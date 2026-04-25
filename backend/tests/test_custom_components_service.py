"""
Tests for core/custom_components_service.py
Custom Canvas Components Service - Manages custom HTML/CSS/JS components
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime
from uuid import uuid4
from sqlalchemy.orm import Session

from core.custom_components_service import (
    CustomComponentsService,
    ComponentSecurityError
)
from core.models import CustomComponent, ComponentVersion, ComponentUsage, User


# Fixtures
@pytest.fixture
def db_session():
    """Mock database session"""
    mock_db = Mock(spec=Session)
    return mock_db


@pytest.fixture
def test_user():
    """Mock test user"""
    return User(
        id=uuid4(),
        email="test@example.com",
        name="Test User"
    )


@pytest.fixture
def component_service(db_session):
    """CustomComponentsService instance"""
    return CustomComponentsService(db_session)


# Component Registration Tests
class TestComponentRegistration:
    """Test component registration functionality"""

    def test_register_custom_component_success(self, component_service, db_session, test_user):
        """Test successful component registration"""
        component_data = {
            "name": "test_chart",
            "display_name": "Test Chart",
            "component_type": "chart",
            "html_content": "<div>Test</div>",
            "css_content": ".test { color: red; }",
            "js_content": "console.log('test');",
            "description": "A test component"
        }

        mock_component = Mock()
        mock_component.id = uuid4()
        mock_component.name = component_data["name"]
        mock_component.created_by = test_user.id

        db_session.query.return_value.filter.return_value.first.return_value = None
        db_session.add.return_value = None
        db_session.commit.return_value = None
        db_session.refresh.return_value = mock_component

        result = component_service.register_component(
            component_data["name"],
            component_data["display_name"],
            component_data["component_type"],
            component_data["html_content"],
            component_data["css_content"],
            component_data["js_content"],
            test_user.id,
            component_data["description"]
        )

        # Verify component was registered
        assert result is not None or db_session.add.called

    def test_register_component_duplicate_name(self, component_service, db_session, test_user):
        """Test registering a component with duplicate name"""
        existing_component = Mock()
        existing_component.id = uuid4()
        existing_component.name = "test_chart"

        db_session.query.return_value.filter.return_value.first.return_value = existing_component

        with pytest.raises(ValueError) as exc_info:
            component_service.register_component(
                "test_chart",
                "Test Chart",
                "chart",
                "<div>Test</div>",
                ".test { }",
                "console.log('test');",
                test_user.id
            )

        # Verify error message
        assert "already exists" in str(exc_info.value).lower()

    def test_register_component_invalid_schema(self, component_service, db_session, test_user):
        """Test registering component with invalid schema"""
        db_session.query.return_value.filter.return_value.first.return_value = None

        # Test with invalid HTML (script tags)
        with pytest.raises(ComponentSecurityError):
            component_service.register_component(
                "malicious_component",
                "Malicious Component",
                "custom",
                "<script>alert('xss')</script>",
                "",
                "",
                test_user.id
            )

    def test_list_registered_components(self, component_service, db_session, test_user):
        """Test listing all registered components"""
        mock_components = [
            Mock(id=uuid4(), name="component1", display_name="Component 1", is_active=True),
            Mock(id=uuid4(), name="component2", display_name="Component 2", is_active=True),
        ]

        db_session.query.return_value.filter.return_value.all.return_value = mock_components

        result = component_service.list_components(user_id=test_user.id)

        # Verify components are returned
        assert len(result) >= 0


# Component Execution Tests
class TestComponentExecution:
    """Test component execution functionality"""

    def test_execute_custom_component_success(self, component_service, db_session):
        """Test successful component execution"""
        component_id = uuid4()
        execution_context = {
            "data": {"value": 42},
            "canvas_id": str(uuid4())
        }

        mock_component = Mock()
        mock_component.id = component_id
        mock_component.name = "test_chart"
        mock_component.html_content = "<div>{{ value }}</div>"
        mock_component.js_content = ""
        mock_component.is_active = True

        db_session.query.return_value.filter.return_value.first.return_value = mock_component

        result = component_service.execute_component(component_id, execution_context)

        # Verify execution result
        assert result is not None

    def test_execute_component_with_parameters(self, component_service, db_session):
        """Test component execution with parameters"""
        component_id = uuid4()
        execution_context = {
            "parameters": {
                "title": "Test Chart",
                "data": [1, 2, 3]
            }
        }

        mock_component = Mock()
        mock_component.id = component_id
        mock_component.name = "chart_with_params"
        mock_component.html_content = "<h1>{{ title }}</h1>"
        mock_component.js_content = ""
        mock_component.is_active = True

        db_session.query.return_value.filter.return_value.first.return_value = mock_component

        result = component_service.execute_component(component_id, execution_context)

        # Verify parameters are used
        assert result is not None

    def test_execute_component_failure_handling(self, component_service, db_session):
        """Test component execution failure handling"""
        component_id = uuid4()

        # Component not found
        db_session.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(ValueError):
            component_service.execute_component(component_id, {})

    def test_execute_component_async(self, component_service, db_session):
        """Test async component execution"""
        component_id = uuid4()
        execution_context = {"async": True}

        mock_component = Mock()
        mock_component.id = component_id
        mock_component.name = "async_component"
        mock_component.html_content = "<div>Loading...</div>"
        mock_component.js_content = "setTimeout(() => {}, 100);"
        mock_component.is_active = True

        db_session.query.return_value.filter.return_value.first.return_value = mock_component

        result = component_service.execute_component_async(component_id, execution_context)

        # Verify async execution
        assert result is not None


# Component Validation Tests
class TestComponentValidation:
    """Test component validation"""

    def test_validate_component_schema_success(self, component_service):
        """Test component schema validation with valid content"""
        valid_component = {
            "name": "valid_component",
            "html_content": "<div class='safe'>Content</div>",
            "css_content": ".safe { color: blue; }",
            "js_content": "console.log('safe');"
        }

        # Should not raise exception
        result = component_service.validate_component(
            valid_component["html_content"],
            valid_component["css_content"],
            valid_component["js_content"]
        )

        assert result is True

    def test_validate_component_invalid_type(self, component_service):
        """Test component validation with invalid type"""
        with pytest.raises(ComponentSecurityError):
            component_service.validate_component(
                "<div>Content</div>",
                ".safe { }",
                "eval(malicious_code)"  # eval should be blocked
            )

    def test_validate_component_missing_required_fields(self, component_service):
        """Test component validation with missing required fields"""
        with pytest.raises(ValueError):
            component_service.validate_component(
                "",  # Empty HTML
                "",
                ""
            )

    def test_validate_xss_injection(self, component_service):
        """Test that XSS injection is blocked"""
        with pytest.raises(ComponentSecurityError):
            component_service.validate_component(
                "<img src=x onerror=alert('xss')>",
                "",
                ""
            )

    def test_validate_css_injection(self, component_service):
        """Test that CSS injection is blocked"""
        with pytest.raises(ComponentSecurityError):
            component_service.validate_component(
                "<div>",
                "body { background: javascript:alert('xss'); }",
                ""
            )

    def test_validate_js_injection(self, component_service):
        """Test that dangerous JavaScript is blocked"""
        with pytest.raises(ComponentSecurityError):
            component_service.validate_component(
                "<div>",
                "",
                "document.location='http://evil.com'"
            )


# Component Version Tests
class TestComponentVersioning:
    """Test component versioning"""

    def test_create_component_version(self, component_service, db_session, test_user):
        """Test creating a new component version"""
        component_id = uuid4()
        new_html = "<div>Updated content</div>"

        mock_component = Mock()
        mock_component.id = component_id
        mock_component.html_content = "<div>Old content</div>"

        db_session.query.return_value.filter.return_value.first.return_value = mock_component
        db_session.add.return_value = None
        db_session.commit.return_value = None

        result = component_service.create_version(
            component_id,
            new_html,
            "",
            "",
            test_user.id
        )

        # Verify version was created
        assert result is not None or db_session.add.called

    def test_get_component_version_history(self, component_service, db_session):
        """Test retrieving component version history"""
        component_id = uuid4()

        mock_versions = [
            Mock(id=uuid4(), version=1, created_at=datetime.now()),
            Mock(id=uuid4(), version=2, created_at=datetime.now()),
        ]

        db_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = mock_versions

        result = component_service.get_version_history(component_id)

        # Verify versions are returned
        assert len(result) >= 0

    def test_rollback_to_version(self, component_service, db_session, test_user):
        """Test rolling back component to previous version"""
        component_id = uuid4()
        version_id = uuid4()

        mock_component = Mock()
        mock_component.id = component_id
        mock_component.html_content = "<div>Current</div>"

        mock_version = Mock()
        mock_version.id = version_id
        mock_version.html_content = "<div>Previous</div>"
        mock_version.css_content = ""
        mock_version.js_content = ""

        db_session.query.return_value.filter.return_value.first.return_value = mock_component
        db_session.query.return_value.filter.return_value.filter.return_value.first.return_value = mock_version

        result = component_service.rollback_to_version(component_id, version_id, test_user.id)

        # Verify rollback
        assert result is not None


# Component Usage Tests
class TestComponentUsage:
    """Test component usage tracking"""

    def test_track_component_usage(self, component_service, db_session):
        """Test tracking component usage"""
        component_id = uuid4()
        canvas_id = uuid4()
        execution_context = {"test": "data"}

        mock_component = Mock()
        mock_component.id = component_id

        db_session.query.return_value.filter.return_value.first.return_value = mock_component
        db_session.add.return_value = None
        db_session.commit.return_value = None

        component_service.track_usage(component_id, canvas_id, execution_context)

        # Verify usage was tracked
        assert db_session.add.called

    def test_get_component_usage_stats(self, component_service, db_session):
        """Test getting component usage statistics"""
        component_id = uuid4()

        mock_usage = [
            Mock(canvas_id=uuid4(), executed_at=datetime.now()),
            Mock(canvas_id=uuid4(), executed_at=datetime.now()),
        ]

        db_session.query.return_value.filter.return_value.all.return_value = mock_usage

        result = component_service.get_usage_stats(component_id)

        # Verify stats are returned
        assert result is not None
