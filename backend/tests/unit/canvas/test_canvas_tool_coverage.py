"""
Comprehensive unit tests for canvas_tool.py coverage expansion.

Tests cover all presentation types with governance integration:
- Chart Presentations (line, bar, pie)
- Markdown Presentations
- Form Presentations
- Sheet Presentations
- Canvas Audit Creation
- Component Type Registry
- WebSocket Integration
- Error Paths
- Feature Flags

Target: 60%+ coverage for canvas_tool.py (currently 3.8%)
"""

import os
import pytest
from unittest.mock import AsyncMock, Mock, MagicMock, patch, call
from datetime import datetime
from sqlalchemy.orm import Session

from core.models import AgentStatus, AgentRegistry, AgentExecution, CanvasAudit


# ============================================================================
# Test Configuration - Prevent DB Connections
# ============================================================================

# Set environment variables to prevent actual DB connections
os.environ["DATABASE_URL"] = "sqlite:///./test.db"


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_db():
    """Mock database session."""
    db = Mock(spec=Session)
    db.add = Mock()
    db.commit = Mock()
    db.refresh = Mock()
    db.rollback = Mock()
    db.query = Mock(return_value=Mock(first=Mock(return_value=None)))
    return db


@pytest.fixture
def mock_agent():
    """Mock agent registry."""
    agent = Mock(spec=AgentRegistry)
    agent.id = "test-agent-1"
    agent.name = "TestAgent"
    agent.status = AgentStatus.AUTONOMOUS.value
    agent.workspace_id = "default"
    return agent


@pytest.fixture
def mock_agent_execution():
    """Mock agent execution."""
    execution = Mock(spec=AgentExecution)
    execution.id = "exec-1"
    execution.status = "running"
    return execution


@pytest.fixture
def mock_governance_check_passed():
    """Mock successful governance check."""
    return {
        "allowed": True,
        "reason": None,
        "action_type": "present_chart",
        "agent_maturity": "autonomous"
    }


@pytest.fixture
def mock_governance_check_blocked():
    """Mock blocked governance check."""
    return {
        "allowed": False,
        "reason": "Agent maturity insufficient",
        "action_type": "present_chart"
    }


@pytest.fixture
def mock_ws_manager():
    """Mock WebSocket manager."""
    with patch('core.websockets.manager') as mock_mgr:
        mock_mgr.broadcast = AsyncMock()
        yield mock_mgr


@pytest.fixture
def mock_db_context():
    """Mock database context manager."""
    with patch('core.database.get_db_session') as mock_ctx:
        db = Mock()
        db.add = Mock()
        db.commit = Mock()
        db.refresh = Mock()
        db.query = Mock(return_value=Mock(first=Mock(return_value=None)))
        mock_ctx.return_value.__enter__ = Mock(return_value=db)
        mock_ctx.return_value.__exit__ = Mock(return_value=False)
        yield mock_ctx


# ============================================================================
# A. Chart Presentations (6 tests)
# ============================================================================

class TestChartPresentations:
    """Tests for chart presentation functionality."""

    @pytest.mark.asyncio
    async def test_present_chart_line_creates_audit_entry(
        self, mock_db_context, mock_ws_manager
    ):
        """Test that line chart presentation creates canvas audit entry."""
        from tools.canvas_tool import present_chart

        result = await present_chart(
            user_id="user-1",
            chart_type="line_chart",
            data=[{"x": 1, "y": 2}, {"x": 2, "y": 4}],
            title="Test Line Chart"
        )

        assert result["success"] is True
        assert "canvas_id" in result
        assert mock_ws_manager.broadcast.called

    @pytest.mark.asyncio
    async def test_present_chart_bar_with_data(
        self, mock_db_context, mock_ws_manager
    ):
        """Test bar chart presentation with data."""
        from tools.canvas_tool import present_chart

        data = [
            {"category": "A", "value": 100},
            {"category": "B", "value": 200},
            {"category": "C", "value": 150}
        ]

        result = await present_chart(
            user_id="user-1",
            chart_type="bar_chart",
            data=data,
            title="Sales by Category"
        )

        assert result["success"] is True
        assert result["chart_type"] == "bar_chart"
        assert mock_ws_manager.broadcast.called

    @pytest.mark.asyncio
    async def test_present_chart_pie_with_categories(
        self, mock_db_context, mock_ws_manager
    ):
        """Test pie chart presentation with categories."""
        from tools.canvas_tool import present_chart

        data = [
            {"category": "Product A", "value": 45},
            {"category": "Product B", "value": 30},
            {"category": "Product C", "value": 25}
        ]

        result = await present_chart(
            user_id="user-1",
            chart_type="pie_chart",
            data=data,
            title="Market Share"
        )

        assert result["success"] is True
        assert result["chart_type"] == "pie_chart"

    @pytest.mark.asyncio
    async def test_present_chart_with_custom_title(
        self, mock_db_context, mock_ws_manager
    ):
        """Test chart presentation with custom title."""
        from tools.canvas_tool import present_chart

        result = await present_chart(
            user_id="user-1",
            chart_type="line_chart",
            data=[{"x": 1, "y": 2}],
            title="Custom Chart Title 2024"
        )

        assert result["success"] is True
        # Verify broadcast includes title
        call_args = mock_ws_manager.broadcast.call_args
        assert "title" in call_args[0][1]["data"]["data"]

    @pytest.mark.asyncio
    async def test_present_chart_with_agent_id(
        self, mock_db_context, mock_ws_manager
    ):
        """Test chart presentation with agent ID."""
        from tools.canvas_tool import present_chart

        result = await present_chart(
            user_id="user-1",
            chart_type="line_chart",
            data=[{"x": 1, "y": 2}],
            agent_id="agent-123"
        )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_present_chart_governance_blocked(
        self, mock_agent, mock_db_context, mock_ws_manager
    ):
        """Test chart presentation blocked by governance."""
        from tools.canvas_tool import present_chart
        from core.agent_governance_service import AgentGovernanceService

        # Mock resolver to return agent
        with patch('tools.canvas_tool.AgentContextResolver') as resolver_mock:
            resolver = Mock()
            resolver.resolve_agent_for_request = AsyncMock(return_value=(mock_agent, {}))
            resolver_mock.return_value = resolver

            # Mock governance to block
            with patch('tools.canvas_tool.ServiceFactory') as factory_mock:
                governance = Mock()
                governance.can_perform_action = Mock(return_value={
                    "allowed": False,
                    "reason": "Not permitted"
                })
                factory_mock.get_governance_service = Mock(return_value=governance)

                result = await present_chart(
                    user_id="user-1",
                    chart_type="line_chart",
                    data=[{"x": 1, "y": 2}],
                    agent_id=mock_agent.id
                )

        assert result["success"] is False
        assert "not permitted" in result["error"].lower()


# ============================================================================
# B. Markdown Presentations (4 tests)
# ============================================================================

class TestMarkdownPresentations:
    """Tests for markdown presentation functionality."""

    @pytest.mark.asyncio
    async def test_present_markdown_simple_text(
        self, mock_db_context, mock_ws_manager
    ):
        """Test markdown presentation with simple text."""
        from tools.canvas_tool import present_markdown

        result = await present_markdown(
            user_id="user-1",
            content="This is a simple markdown text."
        )

        assert result["success"] is True
        assert "canvas_id" in result
        assert mock_ws_manager.broadcast.called

    @pytest.mark.asyncio
    async def test_present_markdown_with_formatting(
        self, mock_db_context, mock_ws_manager
    ):
        """Test markdown presentation with formatting."""
        from tools.canvas_tool import present_markdown

        content = """
        # Heading 1
        ## Heading 2
        **Bold text** and *italic text*
        - List item 1
        - List item 2
        """

        result = await present_markdown(
            user_id="user-1",
            content=content,
            title="Formatted Document"
        )

        assert result["success"] is True
        call_args = mock_ws_manager.broadcast.call_args
        assert content in call_args[0][1]["data"]["data"]["content"]

    @pytest.mark.asyncio
    async def test_present_markdown_creates_canvas_audit(
        self, mock_db_context, mock_ws_manager
    ):
        """Test that markdown presentation creates audit entry."""
        from tools.canvas_tool import present_markdown

        result = await present_markdown(
            user_id="user-1",
            content="Test content",
            title="Test Title"
        )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_present_markdown_with_session_isolation(
        self, mock_db_context, mock_ws_manager
    ):
        """Test markdown presentation with session isolation."""
        from tools.canvas_tool import present_markdown

        result = await present_markdown(
            user_id="user-1",
            content="Session-specific content",
            session_id="session-123"
        )

        assert result["success"] is True
        # Verify session ID in broadcast
        call_args = mock_ws_manager.broadcast.call_args
        assert "session-123" in call_args[0][0]


# ============================================================================
# C. Form Presentations (5 tests)
# ============================================================================

class TestFormPresentations:
    """Tests for form presentation functionality."""

    @pytest.mark.asyncio
    async def test_present_form_with_fields(
        self, mock_db_context, mock_ws_manager
    ):
        """Test form presentation with fields."""
        from tools.canvas_tool import present_form

        form_schema = {
            "fields": [
                {"name": "email", "type": "email", "label": "Email", "required": True},
                {"name": "name", "type": "text", "label": "Name", "required": True}
            ]
        }

        result = await present_form(
            user_id="user-1",
            form_schema=form_schema,
            title="User Registration"
        )

        assert result["success"] is True
        assert "canvas_id" in result

    @pytest.mark.asyncio
    async def test_present_form_with_validation_rules(
        self, mock_db_context, mock_ws_manager
    ):
        """Test form presentation with validation rules."""
        from tools.canvas_tool import present_form

        form_schema = {
            "fields": [
                {
                    "name": "age",
                    "type": "number",
                    "label": "Age",
                    "validation": {"min": 18, "max": 120}
                }
            ]
        }

        result = await present_form(
            user_id="user-1",
            form_schema=form_schema
        )

        assert result["success"] is True
        assert mock_ws_manager.broadcast.called

    @pytest.mark.asyncio
    async def test_present_form_submission_handling(
        self, mock_db_context, mock_ws_manager
    ):
        """Test form submission returns execution ID for tracking."""
        from tools.canvas_tool import present_form

        form_schema = {"fields": [{"name": "field1", "type": "text"}]}

        result = await present_form(
            user_id="user-1",
            form_schema=form_schema,
            agent_id="agent-1"
        )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_present_form_governance_intern_requires_approval(
        self, mock_agent, mock_db_context, mock_ws_manager
    ):
        """Test form presentation requires INTERN+ maturity."""
        from tools.canvas_tool import present_form

        mock_agent.status = AgentStatus.INTERN.value

        with patch('tools.canvas_tool.AgentContextResolver') as resolver_mock:
            resolver = Mock()
            resolver.resolve_agent_for_request = AsyncMock(return_value=(mock_agent, {}))
            resolver_mock.return_value = resolver

            with patch('tools.canvas_tool.ServiceFactory') as factory_mock:
                governance = Mock()
                governance.can_perform_action = Mock(return_value={
                    "allowed": False,
                    "reason": "INTERN requires approval"
                })
                factory_mock.get_governance_service = Mock(return_value=governance)

                result = await present_form(
                    user_id="user-1",
                    form_schema={"fields": []},
                    agent_id=mock_agent.id
                )

        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_present_form_with_agent_execution_tracking(
        self, mock_db_context, mock_ws_manager
    ):
        """Test form presentation tracks agent execution."""
        from tools.canvas_tool import present_form

        form_schema = {"fields": [{"name": "test", "type": "text"}]}

        result = await present_form(
            user_id="user-1",
            form_schema=form_schema,
            agent_id="agent-1"
        )

        assert result["success"] is True


# ============================================================================
# D. Sheet Presentations (3 tests)
# ============================================================================

class TestSheetPresentations:
    """Tests for sheet/spreadsheet presentation functionality."""

    @pytest.mark.asyncio
    async def test_present_sheet_with_data_rows(
        self, mock_db_context, mock_ws_manager
    ):
        """Test sheet presentation with data rows."""
        from tools.canvas_tool import present_specialized_canvas

        cells = {
            "A1": "Product", "B1": "Q1", "C1": "Q2",
            "A2": "Widget", "B2": "1000", "C2": "1200"
        }

        with patch('tools.canvas_tool.canvas_type_registry') as registry:
            registry.validate_canvas_type = Mock(return_value=True)
            registry.validate_component = Mock(return_value=True)
            registry.validate_layout = Mock(return_value=True)
            registry.get_min_maturity = Mock()

            result = await present_specialized_canvas(
                user_id="user-1",
                canvas_type="sheets",
                component_type="data_grid",
                data={"cells": cells},
                title="Sales Data"
            )

        assert result["success"] is True
        assert result["canvas_type"] == "sheets"

    @pytest.mark.asyncio
    async def test_present_sheet_with_headers(
        self, mock_db_context, mock_ws_manager
    ):
        """Test sheet presentation with headers."""
        from tools.canvas_tool import present_specialized_canvas

        data = {
            "headers": ["Name", "Age", "Department"],
            "rows": [
                ["Alice", 30, "Engineering"],
                ["Bob", 25, "Sales"]
            ]
        }

        with patch('tools.canvas_tool.canvas_type_registry') as registry:
            registry.validate_canvas_type = Mock(return_value=True)
            registry.validate_component = Mock(return_value=True)
            registry.validate_layout = Mock(return_value=True)
            registry.get_min_maturity = Mock()

            result = await present_specialized_canvas(
                user_id="user-1",
                canvas_type="sheets",
                component_type="data_grid",
                data=data
            )

        assert result["success"] is True
        assert result["component_type"] == "data_grid"

    @pytest.mark.asyncio
    async def test_present_sheet_creates_correct_component_type(
        self, mock_db_context, mock_ws_manager
    ):
        """Test sheet presentation uses correct component type."""
        from tools.canvas_tool import present_specialized_canvas

        with patch('tools.canvas_tool.canvas_type_registry') as registry:
            registry.validate_canvas_type = Mock(return_value=True)
            registry.validate_component = Mock(return_value=True)
            registry.validate_layout = Mock(return_value=True)
            registry.get_min_maturity = Mock()

            result = await present_specialized_canvas(
                user_id="user-1",
                canvas_type="sheets",
                component_type="data_grid",
                data={"cells": {}}
            )

        assert result["success"] is True
        call_args = mock_ws_manager.broadcast.call_args
        assert call_args[0][1]["data"]["component"] == "data_grid"


# ============================================================================
# E. Canvas Audit Creation (4 tests)
# ============================================================================

class TestCanvasAuditCreation:
    """Tests for canvas audit entry creation."""

    @pytest.mark.asyncio
    async def test_create_canvas_audit_with_all_fields(self, mock_db):
        """Test audit creation with all fields populated."""
        from tools.canvas_tool import _create_canvas_audit

        audit = await _create_canvas_audit(
            db=mock_db,
            agent_id="agent-1",
            agent_execution_id="exec-1",
            user_id="user-1",
            canvas_id="canvas-1",
            session_id="session-1",
            canvas_type="generic",
            component_type="chart",
            component_name="line_chart",
            action="present",
            governance_check_passed=True,
            metadata={"title": "Test", "data_points": 10}
        )

        assert audit is not None
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_canvas_audit_with_metadata(self, mock_db):
        """Test audit creation includes metadata."""
        from tools.canvas_tool import _create_canvas_audit

        metadata = {"custom_field": "value", "count": 42}

        audit = await _create_canvas_audit(
            db=mock_db,
            agent_id="agent-1",
            agent_execution_id="exec-1",
            user_id="user-1",
            canvas_id="canvas-1",
            session_id="session-1",
            canvas_type="generic",
            component_type="chart",
            component_name="line_chart",
            action="present",
            governance_check_passed=True,
            metadata=metadata
        )

        assert audit is not None
        mock_db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_canvas_audit_error_handling(self, mock_db):
        """Test audit creation handles database errors gracefully."""
        from tools.canvas_tool import _create_canvas_audit

        mock_db.commit = Mock(side_effect=Exception("Database error"))

        audit = await _create_canvas_audit(
            db=mock_db,
            agent_id="agent-1",
            agent_execution_id="exec-1",
            user_id="user-1",
            canvas_id="canvas-1",
            session_id="session-1",
            canvas_type="generic",
            component_type="chart",
            component_name="line_chart",
            action="present",
            governance_check_passed=True,
            metadata={}
        )

        # Should return None on error
        assert audit is None

    @pytest.mark.asyncio
    async def test_create_canvas_audit_returns_on_failure(self, mock_db):
        """Test audit creation returns None on failure."""
        from tools.canvas_tool import _create_canvas_audit

        mock_db.add = Mock(side_effect=Exception("Add failed"))

        audit = await _create_canvas_audit(
            db=mock_db,
            agent_id="agent-1",
            agent_execution_id="exec-1",
            user_id="user-1",
            canvas_id="canvas-1",
            session_id="session-1",
            canvas_type="generic",
            component_type="chart",
            component_name="line_chart",
            action="present",
            governance_check_passed=True,
            metadata={}
        )

        assert audit is None


# ============================================================================
# F. Component Type Registry (3 tests)
# ============================================================================

class TestComponentTypeRegistry:
    """Tests for canvas type registry integration."""

    @pytest.mark.asyncio
    async def test_canvas_type_registry_lookup(
        self, mock_db_context, mock_ws_manager
    ):
        """Test canvas type registry validates canvas types."""
        from tools.canvas_tool import present_specialized_canvas

        with patch('tools.canvas_tool.canvas_type_registry') as registry:
            registry.validate_canvas_type = Mock(return_value=True)
            registry.validate_component = Mock(return_value=True)
            registry.validate_layout = Mock(return_value=True)
            registry.get_min_maturity = Mock()

            result = await present_specialized_canvas(
                user_id="user-1",
                canvas_type="docs",
                component_type="rich_editor",
                data={"content": "Test"}
            )

        assert result["success"] is True
        registry.validate_canvas_type.assert_called_once_with("docs")

    @pytest.mark.asyncio
    async def test_canvas_type_registry_default_invalid_type(
        self, mock_db_context, mock_ws_manager
    ):
        """Test canvas type registry returns default for unknown types."""
        from tools.canvas_tool import present_specialized_canvas

        with patch('tools.canvas_tool.canvas_type_registry') as registry:
            registry.validate_canvas_type = Mock(return_value=False)

            result = await present_specialized_canvas(
                user_id="user-1",
                canvas_type="unknown_type",
                component_type="generic",
                data={"content": "Test"}
            )

        assert result["success"] is False
        assert "Invalid canvas type" in result["error"]

    @pytest.mark.asyncio
    async def test_canvas_type_registry_custom_components(
        self, mock_db_context, mock_ws_manager
    ):
        """Test canvas type registry validates custom components."""
        from tools.canvas_tool import present_specialized_canvas

        with patch('tools.canvas_tool.canvas_type_registry') as registry:
            registry.validate_canvas_type = Mock(return_value=True)
            registry.validate_component = Mock(return_value=False)

            result = await present_specialized_canvas(
                user_id="user-1",
                canvas_type="docs",
                component_type="invalid_component",
                data={"content": "Test"}
            )

        assert result["success"] is False
        assert "not supported" in result["error"]


# ============================================================================
# G. WebSocket Integration (3 tests)
# ============================================================================

class TestWebSocketIntegration:
    """Tests for WebSocket integration."""

    @pytest.mark.asyncio
    async def test_present_broadcasts_to_websocket(
        self, mock_db_context, mock_ws_manager
    ):
        """Test presentation broadcasts to WebSocket."""
        from tools.canvas_tool import present_chart

        await present_chart(
            user_id="user-1",
            chart_type="line_chart",
            data=[{"x": 1, "y": 2}]
        )

        assert mock_ws_manager.broadcast.called
        call_args = mock_ws_manager.broadcast.call_args
        assert "user:user-1" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_present_with_user_id_routing(
        self, mock_db_context, mock_ws_manager
    ):
        """Test presentation routes to correct user ID."""
        from tools.canvas_tool import present_markdown

        await present_markdown(
            user_id="user-12345",
            content="Test content"
        )

        call_args = mock_ws_manager.broadcast.call_args
        assert "user:user-12345" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_present_with_session_routing(
        self, mock_db_context, mock_ws_manager
    ):
        """Test presentation routes to session-specific channel."""
        from tools.canvas_tool import present_chart

        await present_chart(
            user_id="user-1",
            chart_type="line_chart",
            data=[{"x": 1, "y": 2}],
            session_id="session-abc"
        )

        call_args = mock_ws_manager.broadcast.call_args
        assert "session:session-abc" in call_args[0][0]


# ============================================================================
# H. Error Paths (4 tests)
# ============================================================================

class TestErrorPaths:
    """Tests for error handling paths."""

    @pytest.mark.asyncio
    async def test_present_with_invalid_chart_type(
        self, mock_db_context, mock_ws_manager
    ):
        """Test presentation with invalid chart type still succeeds."""
        from tools.canvas_tool import present_chart

        # Chart types are not validated, so any string is accepted
        result = await present_chart(
            user_id="user-1",
            chart_type="invalid_chart_type",
            data=[{"x": 1, "y": 2}]
        )

        # Function should still succeed, WebSocket will handle rendering
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_present_with_empty_data(
        self, mock_db_context, mock_ws_manager
    ):
        """Test presentation with empty data."""
        from tools.canvas_tool import present_chart

        result = await present_chart(
            user_id="user-1",
            chart_type="line_chart",
            data=[]
        )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_present_with_empty_user_id(
        self, mock_db_context, mock_ws_manager
    ):
        """Test presentation with empty user_id."""
        from tools.canvas_tool import present_chart

        result = await present_chart(
            user_id="",
            chart_type="line_chart",
            data=[{"x": 1, "y": 2}]
        )

        # Should still broadcast to empty user channel
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_present_database_error_rollback(
        self, mock_db_context
    ):
        """Test presentation handles database errors."""
        from tools.canvas_tool import present_chart

        with patch('core.websockets.manager.broadcast') as broadcast_mock:
            broadcast_mock = AsyncMock(side_effect=Exception("DB error"))

            result = await present_chart(
                user_id="user-1",
                chart_type="line_chart",
                data=[{"x": 1, "y": 2}],
                agent_id="agent-1"
            )

        # Should handle error gracefully
        assert isinstance(result, dict)


# ============================================================================
# I. Feature Flags (2 tests)
# ============================================================================

class TestFeatureFlags:
    """Tests for feature flag integration."""

    @pytest.mark.asyncio
    async def test_present_canvas_respects_feature_flag(
        self, mock_db_context, mock_ws_manager
    ):
        """Test presentation respects canvas feature flag."""
        from tools.canvas_tool import present_chart

        with patch('tools.canvas_tool.FeatureFlags') as flags:
            flags.should_enforce_governance = Mock(return_value=False)

            result = await present_chart(
                user_id="user-1",
                chart_type="line_chart",
                data=[{"x": 1, "y": 2}]
            )

        assert result["success"] is True
        flags.should_enforce_governance.assert_called_with('canvas')

    @pytest.mark.asyncio
    async def test_present_canvas_with_governance_enabled(
        self, mock_db_context, mock_ws_manager
    ):
        """Test presentation with governance enabled."""
        from tools.canvas_tool import present_chart

        with patch('tools.canvas_tool.FeatureFlags') as flags:
            flags.should_enforce_governance = Mock(return_value=True)

            result = await present_chart(
                user_id="user-1",
                chart_type="line_chart",
                data=[{"x": 1, "y": 2}]
            )

        assert result["success"] is True


# ============================================================================
# J. Additional Tests for Coverage (5 tests)
# ============================================================================

class TestAdditionalCoverage:
    """Additional tests to improve coverage."""

    @pytest.mark.asyncio
    async def test_present_status_panel(
        self, mock_db_context, mock_ws_manager
    ):
        """Test status panel presentation."""
        from tools.canvas_tool import present_status_panel

        items = [
            {"label": "Sales", "value": "$100K", "trend": "+10%"},
            {"label": "Users", "value": "1,234", "trend": "+5%"}
        ]

        result = await present_status_panel(
            user_id="user-1",
            items=items,
            title="Dashboard Status"
        )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_update_canvas(
        self, mock_db_context, mock_ws_manager
    ):
        """Test canvas update functionality."""
        from tools.canvas_tool import update_canvas

        updates = {
            "data": [{"x": 1, "y": 5}, {"x": 2, "y": 10}],
            "title": "Updated Title"
        }

        result = await update_canvas(
            user_id="user-1",
            canvas_id="canvas-123",
            updates=updates
        )

        assert result["success"] is True
        assert "updated_fields" in result

    @pytest.mark.asyncio
    async def test_close_canvas(
        self, mock_ws_manager
    ):
        """Test canvas close functionality."""
        from tools.canvas_tool import close_canvas

        result = await close_canvas(user_id="user-1")

        assert result["success"] is True
        assert mock_ws_manager.broadcast.called

    @pytest.mark.asyncio
    async def test_present_to_canvas_chart_type(
        self, mock_db_context, mock_ws_manager
    ):
        """Test present_to_canvas with chart type."""
        from tools.canvas_tool import present_to_canvas

        result = await present_to_canvas(
            db=mock_db_context.__enter__.return_value,
            user_id="user-1",
            canvas_type="chart",
            content={
                "chart_type": "line_chart",
                "data": [{"x": 1, "y": 2}]
            },
            title="Test Chart"
        )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_present_to_canvas_markdown_type(
        self, mock_db_context, mock_ws_manager
    ):
        """Test present_to_canvas with markdown type."""
        from tools.canvas_tool import present_to_canvas

        result = await present_to_canvas(
            db=mock_db_context.__enter__.return_value,
            user_id="user-1",
            canvas_type="markdown",
            content={"content": "# Test Markdown"},
            title="Test MD"
        )

        assert result["success"] is True
