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
    mock_db.refresh.side_effect = lambda comp: setattr(comp, "created_at", datetime.now())
    return mock_db


@pytest.fixture
def test_user():
    """Mock test user"""
    return User(
        id=uuid4(),
        email="test@example.com", first_name="Test", last_name="User", role="member", status="active"
    )


@pytest.fixture
def component_service(db_session):
    """CustomComponentsService instance"""
    return CustomComponentsService(db_session)


def _chain_mock(db_session, leaf="first", value=None):
    """Wire the query()->filter()->...()->leaf() mock chain."""
    q = db_session.query.return_value
    f = q.filter.return_value
    f.filter.return_value = f
    f.order_by.return_value = f
    f.limit.return_value = f
    getattr(f, leaf).return_value = value
    return f


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

        _chain_mock(db_session, "first", None)

        # AUTONOMOUS agent for JS governance check, then None for duplicate/slug checks
        agent_mock = Mock(status="AUTONOMOUS")
        f = db_session.query.return_value.filter.return_value
        f.first.side_effect = [agent_mock, None, None]

        result = component_service.create_component(
            test_user.id,
            component_data["name"],
            component_data["html_content"],
            component_data["css_content"],
            component_data["js_content"],
            component_data["description"],
            category=component_data["component_type"],
            agent_id="test_agent"
        )

        # Verify component was registered
        assert result is not None or db_session.add.called

    def test_register_component_duplicate_name(self, component_service, db_session, test_user):
        """Test registering a component with duplicate name"""
        existing_component = Mock()
        existing_component.id = uuid4()
        existing_component.name = "test_chart"

        _chain_mock(db_session, "first", existing_component)

        with pytest.raises(ValueError) as exc_info:
            component_service.create_component(
                test_user.id,
                "test_chart",
                "<div>Test</div>",
                ".test { }",
                "",
                None
            )

        # Verify error message
        assert "already exists" in str(exc_info.value).lower()

    def test_register_component_invalid_schema(self, component_service, db_session, test_user):
        """Test registering component with invalid schema"""
        _chain_mock(db_session, "first", None)

        # Test with invalid HTML (script tags)
        with pytest.raises(ComponentSecurityError):
            component_service.create_component(
                test_user.id,
                "malicious_component",
                "<script>alert('xss')</script>",
                "",
                "",
                None
            )

    def test_list_registered_components(self, component_service, db_session, test_user):
        """Test listing all registered components"""
        mock_components = [
            Mock(id=uuid4(), name="component1", display_name="Component 1", is_active=True),
            Mock(id=uuid4(), name="component2", display_name="Component 2", is_active=True),
        ]

        _chain_mock(db_session, "all", mock_components)

        result = component_service.list_components(user_id=test_user.id)

        # Verify components are returned
        assert result["total"] == 2


# Component Retrieval Tests
class TestComponentExecution:
    """Test component retrieval"""

    def test_get_component_success(self, component_service, db_session, test_user):
        """Test successful component retrieval"""
        component_id = uuid4()

        mock_component = Mock()
        mock_component.id = component_id
        mock_component.name = "test_chart"
        mock_component.created_by = str(test_user.id)
        mock_component.html_content = "<div>{{ value }}</div>"
        mock_component.js_content = ""
        mock_component.is_active = True

        _chain_mock(db_session, "first", mock_component)

        result = component_service.get_component(str(component_id), user_id=str(test_user.id))

        # Verify retrieval result
        assert result is not None
        assert result["name"] == "test_chart"

    def test_get_component_with_slug(self, component_service, db_session, test_user):
        """Test component retrieval by slug"""
        component_id = uuid4()

        mock_component = Mock()
        mock_component.id = component_id
        mock_component.name = "chart_with_params"
        mock_component.created_by = str(test_user.id)
        mock_component.html_content = "<h1>{{ title }}</h1>"
        mock_component.js_content = ""
        mock_component.is_active = True

        _chain_mock(db_session, "first", mock_component)

        result = component_service.get_component(slug="chart_with_params", user_id=str(test_user.id))

        # Verify retrieval
        assert result is not None

    def test_get_component_failure_handling(self, component_service, db_session, test_user):
        """Test component retrieval failure handling"""
        component_id = uuid4()

        # Component not found
        _chain_mock(db_session, "first", None)

        result = component_service.get_component(str(component_id), user_id=str(test_user.id))

        assert result["error"] == "Component not found"


# Component Validation Tests
class TestComponentValidation:
    """Test component validation"""

    def test_validate_component_schema_success(self, component_service, db_session, test_user):
        """Test component creation with valid content"""
        _chain_mock(db_session, "first", None)

        agent_mock = Mock(status="AUTONOMOUS")
        f = db_session.query.return_value.filter.return_value
        f.first.side_effect = [agent_mock, None, None]

        # Should not raise exception
        result = component_service.create_component(
            test_user.id,
            "valid_component",
            "<div class='safe'>Content</div>",
            ".safe { color: blue; }",
            "console.log('safe');",
            None,
            agent_id="test_agent"
        )

        assert result is not None

    def test_validate_component_invalid_type(self, component_service, db_session, test_user):
        """Test component creation with invalid JS type"""
        _chain_mock(db_session, "first", None)

        agent_mock = Mock(status="AUTONOMOUS")
        db_session.query.return_value.filter.return_value.first.return_value = agent_mock

        with pytest.raises(ComponentSecurityError):
            component_service.create_component(
                test_user.id,
                "bad_js_component",
                "<div>Content</div>",
                ".safe { }",
                "eval(malicious_code)"  # eval should be blocked
            )

    def test_validate_component_missing_required_fields(self, component_service, db_session, test_user):
        """Test component creation with empty content succeeds"""
        _chain_mock(db_session, "first", None)

        result = component_service.create_component(
            test_user.id,
            "empty_component",
            "",  # Empty HTML
            "",
            ""
        )

        assert result is not None

    def test_validate_xss_injection(self, component_service, db_session, test_user):
        """Test that XSS injection is blocked"""
        _chain_mock(db_session, "first", None)

        with pytest.raises(ComponentSecurityError):
            component_service.create_component(
                test_user.id,
                "xss_component",
                "<img src=x onerror=alert('xss')>",
                "",
                ""
            )

    def test_validate_css_injection(self, component_service, db_session, test_user):
        """Test that CSS injection is blocked"""
        _chain_mock(db_session, "first", None)

        with pytest.raises(ComponentSecurityError):
            component_service.create_component(
                test_user.id,
                "css_component",
                "<div>",
                "body { background: javascript:alert('xss'); }",
                ""
            )

    def test_validate_js_injection(self, component_service, db_session, test_user):
        """Test that dangerous JavaScript is blocked"""
        _chain_mock(db_session, "first", None)

        agent_mock = Mock(status="AUTONOMOUS")
        db_session.query.return_value.filter.return_value.first.return_value = agent_mock

        with pytest.raises(ComponentSecurityError):
            component_service.create_component(
                test_user.id,
                "js_component",
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
        mock_component.created_by = str(test_user.id)
        mock_component.html_content = "<div>Old content</div>"
        mock_component.js_content = ""
        mock_component.current_version = 1

        _chain_mock(db_session, "first", mock_component)

        result = component_service.update_component(
            str(component_id),
            str(test_user.id),
            html_content=new_html,
            css_content="",
            js_content=""
        )

        # Verify version was created
        assert result is not None or db_session.add.called

    def test_get_component_version_history(self, component_service, db_session, test_user):
        """Test retrieving component version history"""
        component_id = uuid4()

        mock_component = Mock()
        mock_component.id = component_id
        mock_component.created_by = str(test_user.id)
        mock_component.current_version = 2

        mock_versions = [
            Mock(id=uuid4(), version_number=1, created_at=datetime.now()),
            Mock(id=uuid4(), version_number=2, created_at=datetime.now()),
        ]

        q = db_session.query.return_value
        f = q.filter.return_value
        f.filter.return_value = f
        f.first.return_value = mock_component
        f.order_by.return_value.all.return_value = mock_versions

        result = component_service.get_component_versions(str(component_id), str(test_user.id))

        # Verify versions are returned
        assert result["total_versions"] == 2

    def test_rollback_to_version(self, component_service, db_session, test_user):
        """Test rolling back component to previous version"""
        component_id = uuid4()

        mock_component = Mock()
        mock_component.id = component_id
        mock_component.created_by = str(test_user.id)
        mock_component.html_content = "<div>Current</div>"
        mock_component.css_content = ""
        mock_component.js_content = ""
        mock_component.current_version = 2

        mock_version = Mock()
        mock_version.id = uuid4()
        mock_version.html_content = "<div>Previous</div>"
        mock_version.css_content = ""
        mock_version.js_content = ""

        q = db_session.query.return_value
        f = q.filter.return_value
        f.first.return_value = mock_component
        f.filter.return_value.first.return_value = mock_version

        result = component_service.rollback_component(str(component_id), 1, str(test_user.id))

        # Verify rollback
        assert result is not None
        assert result["status"] == "rolled_back"


# Component Usage Tests
class TestComponentUsage:
    """Test component usage tracking"""

    def test_track_component_usage(self, component_service, db_session, test_user):
        """Test tracking component usage"""
        component_id = uuid4()
        canvas_id = uuid4()

        _chain_mock(db_session, "first", None)

        component_service.record_component_usage(
            str(component_id),
            str(canvas_id),
            str(test_user.id)
        )

        # Verify usage was tracked
        assert db_session.add.called

    def test_get_component_usage_stats(self, component_service, db_session, test_user):
        """Test getting component usage statistics"""
        component_id = uuid4()

        mock_component = Mock()
        mock_component.id = component_id
        mock_component.created_by = str(test_user.id)

        mock_usage = [
            Mock(canvas_id=uuid4(), executed_at=datetime.now(), execution_context=None),
            Mock(canvas_id=uuid4(), executed_at=datetime.now(), execution_context=None),
        ]

        q = db_session.query.return_value
        f = q.filter.return_value
        f.first.return_value = mock_component
        f.all.return_value = mock_usage

        result = component_service.get_component_usage_stats(str(component_id), str(test_user.id))

        # Verify stats are returned
        assert result is not None
        assert result["total_renders"] == 2
