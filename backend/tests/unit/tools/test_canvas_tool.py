"""
Unit Tests for Canvas Tool Backend Helper

Tests cover all canvas presentation functions:
- Line charts, bar charts, pie charts
- Markdown presentations
- Forms (presentation, submission, validation)
- Status panels
- Canvas updates
- Specialized canvas types (docs, email, sheets, etc.)
- JavaScript execution (AUTONOMOUS only)
- Canvas closing
- Permission checks and governance integration
- Agent execution tracking
- Audit trail creation
- Session isolation

Target Coverage: 70%
Target Branch Coverage: 60%+
Tests: ~35
"""

import pytest
from unittest.mock import MagicMock, Mock, patch, AsyncMock
from datetime import datetime
import uuid
from sqlalchemy.orm import Session

from tools.canvas_tool import (
    present_chart,
    present_markdown,
    present_form,
    present_status_panel,
    update_canvas,
    present_to_canvas,
    close_canvas,
    canvas_execute_javascript,
    present_specialized_canvas,
    _create_canvas_audit,
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def mock_db():
    """Mock database session"""
    db = MagicMock(spec=Session)
    db.add = MagicMock()
    db.commit = MagicMock()
    db.rollback = MagicMock()
    db.refresh = MagicMock()
    db.query = MagicMock()
    return db


@pytest.fixture
def mock_agent():
    """Mock agent"""
    agent = MagicMock()
    agent.id = "agent_123"
    agent.name = "Test Agent"
    agent.status = "autonomous"
    return agent


@pytest.fixture
def mock_agent_execution():
    """Mock agent execution"""
    execution = MagicMock()
    execution.id = "exec_123"
    execution.agent_id = "agent_123"
    execution.status = "running"
    return execution


@pytest.fixture
def mock_governance_check():
    """Mock governance check result"""
    return {
        "allowed": True,
        "reason": None,
        "required_maturity": "intern"
    }


@pytest.fixture
def mock_ws_manager():
    """Mock WebSocket manager"""
    manager = MagicMock()
    manager.broadcast = AsyncMock()
    return manager


@pytest.fixture
def sample_chart_data():
    """Sample chart data"""
    return [
        {"x": "Jan", "y": 100},
        {"x": "Feb", "y": 200},
        {"x": "Mar", "y": 150}
    ]


@pytest.fixture
def sample_form_schema():
    """Sample form schema"""
    return {
        "fields": [
            {"name": "email", "type": "email", "label": "Email", "required": True},
            {"name": "message", "type": "text", "label": "Message", "required": True}
        ]
    }


# =============================================================================
# TEST CLASS: Line Charts
# =============================================================================

class TestLineCharts:
    """Tests for line chart presentation"""

    @pytest.mark.asyncio
    async def test_present_line_chart_success(self, mock_ws_manager):
        """Test successful line chart presentation"""
        with patch('tools.canvas_tool.ws_manager', mock_ws_manager), \
             patch('tools.canvas_tool.FeatureFlags.should_enforce_governance', return_value=False):

            result = await present_chart(
                user_id="user_123",
                chart_type="line_chart",
                data=[{"x": 1, "y": 100}, {"x": 2, "y": 200}],
                title="Sales Data"
            )

            assert result["success"] is True
            assert result["chart_type"] == "line_chart"
            assert "canvas_id" in result
            mock_ws_manager.broadcast.assert_called_once()

    @pytest.mark.asyncio
    async def test_present_line_chart_with_session_id(self, mock_ws_manager):
        """Test line chart with session isolation"""
        with patch('tools.canvas_tool.ws_manager', mock_ws_manager), \
             patch('tools.canvas_tool.FeatureFlags.should_enforce_governance', return_value=False):

            result = await present_chart(
                user_id="user_123",
                chart_type="line_chart",
                data=[{"x": 1, "y": 100}],
                title="Test",
                session_id="session_456"
            )

            assert result["success"] is True
            # Verify session channel used
            call_args = mock_ws_manager.broadcast.call_args
            assert "session:session_456" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_present_line_chart_with_agent(self, mock_ws_manager):
        """Test line chart presentation with agent"""
        with patch('tools.canvas_tool.ws_manager', mock_ws_manager), \
             patch('tools.canvas_tool.FeatureFlags.should_enforce_governance', return_value=True), \
             patch('core.database.get_db_session') as mock_get_db, \
             patch('tools.canvas_tool.AgentContextResolver') as mock_resolver_class, \
             patch('tools.canvas_tool.ServiceFactory') as mock_factory:

            # Setup mocks
            mock_db = MagicMock()
            mock_get_db.return_value.__enter__.return_value = mock_db
            mock_get_db.return_value.__exit__.return_value = None

            mock_agent = MagicMock()
            mock_agent.id = "agent_123"
            mock_agent_execution = MagicMock()
            mock_agent_execution.id = "exec_123"

            # Setup query mock for agent execution lookup
            mock_query = MagicMock()
            mock_execution = MagicMock()
            mock_execution.status = "running"
            mock_query.filter.return_value.first.return_value = mock_execution
            mock_db.query.return_value = mock_query

            mock_resolver = MagicMock()
            mock_resolver.resolve_agent_for_request = AsyncMock(return_value=(mock_agent, {}))
            mock_resolver_class.return_value = mock_resolver

            mock_governance = MagicMock()
            mock_governance.can_perform_action.return_value = {"allowed": True}
            mock_governance.record_outcome = AsyncMock()
            mock_factory.get_governance_service.return_value = mock_governance

            result = await present_chart(
                user_id="user_123",
                chart_type="line_chart",
                data=[{"x": 1, "y": 100}],
                agent_id="agent_123"
            )

            assert result["success"] is True
            assert result["agent_id"] == "agent_123"


# =============================================================================
# TEST CLASS: Bar Charts
# =============================================================================

class TestBarCharts:
    """Tests for bar chart presentation"""

    @pytest.mark.asyncio
    async def test_present_bar_chart_success(self, mock_ws_manager):
        """Test successful bar chart presentation"""
        with patch('tools.canvas_tool.ws_manager', mock_ws_manager), \
             patch('tools.canvas_tool.FeatureFlags.should_enforce_governance', return_value=False):

            result = await present_chart(
                user_id="user_123",
                chart_type="bar_chart",
                data=[
                    {"category": "A", "value": 100},
                    {"category": "B", "value": 200}
                ],
                title="Category Comparison"
            )

            assert result["success"] is True
            assert result["chart_type"] == "bar_chart"
            mock_ws_manager.broadcast.assert_called_once()

    @pytest.mark.asyncio
    async def test_present_bar_chart_with_custom_color(self, mock_ws_manager):
        """Test bar chart with custom color"""
        with patch('tools.canvas_tool.ws_manager', mock_ws_manager), \
             patch('tools.canvas_tool.FeatureFlags.should_enforce_governance', return_value=False):

            result = await present_chart(
                user_id="user_123",
                chart_type="bar_chart",
                data=[{"category": "A", "value": 100}],
                color="#FF5733"
            )

            assert result["success"] is True
            # Verify color passed through
            call_args = mock_ws_manager.broadcast.call_args
            assert "color" in call_args[0][1]["data"]["data"]


# =============================================================================
# TEST CLASS: Pie Charts
# =============================================================================

class TestPieCharts:
    """Tests for pie chart presentation"""

    @pytest.mark.asyncio
    async def test_present_pie_chart_success(self, mock_ws_manager):
        """Test successful pie chart presentation"""
        with patch('tools.canvas_tool.ws_manager', mock_ws_manager), \
             patch('tools.canvas_tool.FeatureFlags.should_enforce_governance', return_value=False):

            result = await present_chart(
                user_id="user_123",
                chart_type="pie_chart",
                data=[
                    {"label": "Category A", "value": 30},
                    {"label": "Category B", "value": 70}
                ],
                title="Distribution"
            )

            assert result["success"] is True
            assert result["chart_type"] == "pie_chart"
            mock_ws_manager.broadcast.assert_called_once()


# =============================================================================
# TEST CLASS: Markdown Presentations
# =============================================================================

class TestMarkdownPresentations:
    """Tests for markdown content presentation"""

    @pytest.mark.asyncio
    async def test_present_markdown_success(self, mock_ws_manager):
        """Test successful markdown presentation"""
        with patch('tools.canvas_tool.ws_manager', mock_ws_manager), \
             patch('tools.canvas_tool.FeatureFlags.should_enforce_governance', return_value=False):

            content = "# Hello World\n\nThis is **bold** text."
            result = await present_markdown(
                user_id="user_123",
                content=content,
                title="Documentation"
            )

            assert result["success"] is True
            assert "canvas_id" in result
            mock_ws_manager.broadcast.assert_called_once()

    @pytest.mark.asyncio
    async def test_present_markdown_with_session_isolation(self, mock_ws_manager):
        """Test markdown with session isolation"""
        with patch('tools.canvas_tool.ws_manager', mock_ws_manager), \
             patch('tools.canvas_tool.FeatureFlags.should_enforce_governance', return_value=False):

            result = await present_markdown(
                user_id="user_123",
                content="# Test",
                session_id="session_789"
            )

            assert result["success"] is True
            call_args = mock_ws_manager.broadcast.call_args
            assert "session:session_789" in call_args[0][0]


# =============================================================================
# TEST CLASS: Forms
# =============================================================================

class TestForms:
    """Tests for form presentation and submission"""

    @pytest.mark.asyncio
    async def test_present_form_success(self, mock_ws_manager, sample_form_schema):
        """Test successful form presentation"""
        with patch('tools.canvas_tool.ws_manager', mock_ws_manager), \
             patch('tools.canvas_tool.FeatureFlags.should_enforce_governance', return_value=False):

            result = await present_form(
                user_id="user_123",
                form_schema=sample_form_schema,
                title="Contact Form"
            )

            assert result["success"] is True
            assert "canvas_id" in result
            mock_ws_manager.broadcast.assert_called_once()

    @pytest.mark.asyncio
    async def test_present_form_with_multiple_fields(self, mock_ws_manager):
        """Test form with multiple field types"""
        with patch('tools.canvas_tool.ws_manager', mock_ws_manager), \
             patch('tools.canvas_tool.FeatureFlags.should_enforce_governance', return_value=False):

            form_schema = {
                "fields": [
                    {"name": "name", "type": "text", "label": "Name"},
                    {"name": "email", "type": "email", "label": "Email"},
                    {"name": "age", "type": "number", "label": "Age"},
                    {"name": "subscribe", "type": "checkbox", "label": "Subscribe"}
                ]
            }

            result = await present_form(
                user_id="user_123",
                form_schema=form_schema,
                title="User Profile"
            )

            assert result["success"] is True
            assert "canvas_id" in result

    @pytest.mark.asyncio
    async def test_present_form_with_validation_rules(self, mock_ws_manager):
        """Test form with validation rules"""
        with patch('tools.canvas_tool.ws_manager', mock_ws_manager), \
             patch('tools.canvas_tool.FeatureFlags.should_enforce_governance', return_value=False):

            form_schema = {
                "fields": [
                    {
                        "name": "email",
                        "type": "email",
                        "label": "Email",
                        "required": True,
                        "validation": {"pattern": "^[^@]+@[^@]+$"}
                    }
                ],
                "validation": {
                    "min_fields": 1
                }
            }

            result = await present_form(
                user_id="user_123",
                form_schema=form_schema
            )

            assert result["success"] is True


# =============================================================================
# TEST CLASS: Status Panels
# =============================================================================

class TestStatusPanels:
    """Tests for status panel presentation"""

    @pytest.mark.asyncio
    async def test_present_status_panel_success(self, mock_ws_manager):
        """Test successful status panel presentation"""
        with patch('tools.canvas_tool.ws_manager', mock_ws_manager), \
             patch('tools.canvas_tool.FeatureFlags.should_enforce_governance', return_value=False):

            items = [
                {"label": "Revenue", "value": "$100,000", "trend": "+5%"},
                {"label": "Users", "value": "1,234", "trend": "+2%"}
            ]

            result = await present_status_panel(
                user_id="user_123",
                items=items,
                title="Key Metrics"
            )

            assert result["success"] is True
            mock_ws_manager.broadcast.assert_called_once()

    @pytest.mark.asyncio
    async def test_present_status_panel_without_trends(self, mock_ws_manager):
        """Test status panel without trend data"""
        with patch('tools.canvas_tool.ws_manager', mock_ws_manager), \
             patch('tools.canvas_tool.FeatureFlags.should_enforce_governance', return_value=False):

            items = [
                {"label": "Status", "value": "Active"},
                {"label": "Version", "value": "1.0.0"}
            ]

            result = await present_status_panel(
                user_id="user_123",
                items=items
            )

            assert result["success"] is True


# =============================================================================
# TEST CLASS: Canvas Updates
# =============================================================================

class TestCanvasUpdates:
    """Tests for canvas update functionality"""

    @pytest.mark.asyncio
    async def test_update_canvas_success(self, mock_ws_manager):
        """Test successful canvas update"""
        with patch('tools.canvas_tool.ws_manager', mock_ws_manager), \
             patch('tools.canvas_tool.FeatureFlags.should_enforce_governance', return_value=False):

            updates = {"data": [{"x": 1, "y": 500}], "title": "Updated Data"}

            result = await update_canvas(
                user_id="user_123",
                canvas_id="canvas_123",
                updates=updates
            )

            assert result["success"] is True
            assert result["canvas_id"] == "canvas_123"
            assert "title" in result["updated_fields"]
            mock_ws_manager.broadcast.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_canvas_with_session_isolation(self, mock_ws_manager):
        """Test canvas update with session isolation"""
        with patch('tools.canvas_tool.ws_manager', mock_ws_manager), \
             patch('tools.canvas_tool.FeatureFlags.should_enforce_governance', return_value=False):

            result = await update_canvas(
                user_id="user_123",
                canvas_id="canvas_123",
                updates={"title": "New Title"},
                session_id="session_abc"
            )

            assert result["success"] is True
            assert result["session_id"] == "session_abc"


# =============================================================================
# TEST CLASS: Specialized Canvas Types
# =============================================================================

class TestSpecializedCanvasTypes:
    """Tests for specialized canvas types (docs, email, sheets, etc.)"""

    @pytest.mark.asyncio
    async def test_present_docs_canvas_success(self, mock_ws_manager):
        """Test documentation canvas presentation"""
        with patch('tools.canvas_tool.ws_manager', mock_ws_manager), \
             patch('tools.canvas_tool.FeatureFlags.should_enforce_governance', return_value=False), \
             patch('tools.canvas_tool.canvas_type_registry') as mock_registry:

            mock_registry.validate_canvas_type.return_value = True
            mock_registry.validate_component.return_value = True
            mock_registry.validate_layout.return_value = True
            mock_registry.get_min_maturity.return_value = MagicMock(value="intern")

            result = await present_specialized_canvas(
                user_id="user_123",
                canvas_type="docs",
                component_type="rich_editor",
                data={"content": "# API Reference"},
                title="API Docs"
            )

            assert result["success"] is True
            assert result["canvas_type"] == "docs"

    @pytest.mark.asyncio
    async def test_present_sheets_canvas_success(self, mock_ws_manager):
        """Test spreadsheet canvas presentation"""
        with patch('tools.canvas_tool.ws_manager', mock_ws_manager), \
             patch('tools.canvas_tool.FeatureFlags.should_enforce_governance', return_value=False), \
             patch('tools.canvas_tool.canvas_type_registry') as mock_registry:

            mock_registry.validate_canvas_type.return_value = True
            mock_registry.validate_component.return_value = True
            mock_registry.validate_layout.return_value = True
            mock_registry.get_min_maturity.return_value = MagicMock(value="intern")

            result = await present_specialized_canvas(
                user_id="user_123",
                canvas_type="sheets",
                component_type="data_grid",
                data={"cells": {"A1": "Value"}},
                layout="sheet"
            )

            assert result["success"] is True
            assert result["canvas_type"] == "sheets"

    @pytest.mark.asyncio
    async def test_present_specialized_canvas_invalid_type(self, mock_ws_manager):
        """Test specialized canvas with invalid type"""
        with patch('tools.canvas_tool.ws_manager', mock_ws_manager), \
             patch('tools.canvas_tool.canvas_type_registry') as mock_registry:

            mock_registry.validate_canvas_type.return_value = False
            mock_registry.get_all_types.return_value = {"docs": {}, "sheets": {}}

            result = await present_specialized_canvas(
                user_id="user_123",
                canvas_type="invalid_type",
                component_type="generic",
                data={}
            )

            assert result["success"] is False
            assert "Invalid canvas type" in result["error"]

    @pytest.mark.asyncio
    async def test_present_specialized_canvas_invalid_component(self, mock_ws_manager):
        """Test specialized canvas with invalid component for type"""
        with patch('tools.canvas_tool.ws_manager', mock_ws_manager), \
             patch('tools.canvas_tool.canvas_type_registry') as mock_registry:

            mock_registry.validate_canvas_type.return_value = True
            mock_registry.validate_component.return_value = False

            result = await present_specialized_canvas(
                user_id="user_123",
                canvas_type="docs",
                component_type="invalid_component",
                data={}
            )

            assert result["success"] is False
            assert "not supported" in result["error"]

    @pytest.mark.asyncio
    async def test_present_specialized_canvas_invalid_layout(self, mock_ws_manager):
        """Test specialized canvas with invalid layout"""
        with patch('tools.canvas_tool.ws_manager', mock_ws_manager), \
             patch('tools.canvas_tool.canvas_type_registry') as mock_registry:

            mock_registry.validate_canvas_type.return_value = True
            mock_registry.validate_component.return_value = True
            mock_registry.validate_layout.return_value = False

            result = await present_specialized_canvas(
                user_id="user_123",
                canvas_type="docs",
                component_type="rich_editor",
                data={},
                layout="invalid_layout"
            )

            assert result["success"] is False
            assert "not supported" in result["error"]


# =============================================================================
# TEST CLASS: Canvas Permissions
# =============================================================================

class TestCanvasPermissions:
    """Tests for canvas permission checks"""

    @pytest.mark.asyncio
    async def test_chart_present_blocked_by_governance(self, mock_ws_manager):
        """Test chart presentation blocked by governance"""
        with patch('tools.canvas_tool.ws_manager', mock_ws_manager), \
             patch('tools.canvas_tool.FeatureFlags.should_enforce_governance', return_value=True), \
             patch('core.database.get_db_session') as mock_get_db, \
             patch('tools.canvas_tool.AgentContextResolver') as mock_resolver_class, \
             patch('tools.canvas_tool.ServiceFactory') as mock_factory:

            # Setup mocks
            mock_db = MagicMock()
            mock_get_db.return_value.__enter__.return_value = mock_db
            mock_get_db.return_value.__exit__.return_value = None

            mock_agent = MagicMock()
            mock_agent.id = "agent_123"
            mock_resolver = MagicMock()
            mock_resolver.resolve_agent_for_request = AsyncMock(return_value=(mock_agent, {}))
            mock_resolver_class.return_value = mock_resolver

            mock_governance = MagicMock()
            mock_governance.can_perform_action.return_value = {
                "allowed": False,
                "reason": "Insufficient maturity"
            }
            mock_factory.get_governance_service.return_value = mock_governance

            result = await present_chart(
                user_id="user_123",
                chart_type="line_chart",
                data=[{"x": 1, "y": 100}]
            )

            assert result["success"] is False
            assert "not permitted" in result["error"]

    @pytest.mark.asyncio
    async def test_form_present_blocked_by_governance(self, mock_ws_manager):
        """Test form presentation blocked by governance"""
        with patch('tools.canvas_tool.ws_manager', mock_ws_manager), \
             patch('tools.canvas_tool.FeatureFlags.should_enforce_governance', return_value=True), \
             patch('core.database.get_db_session') as mock_get_db, \
             patch('tools.canvas_tool.AgentContextResolver') as mock_resolver_class, \
             patch('tools.canvas_tool.ServiceFactory') as mock_factory:

            # Setup mocks
            mock_db = MagicMock()
            mock_get_db.return_value.__enter__.return_value = mock_db
            mock_get_db.return_value.__exit__.return_value = None

            mock_agent = MagicMock()
            mock_agent.id = "agent_123"
            mock_resolver = MagicMock()
            mock_resolver.resolve_agent_for_request = AsyncMock(return_value=(mock_agent, {}))
            mock_resolver_class.return_value = mock_resolver

            mock_governance = MagicMock()
            mock_governance.can_perform_action.return_value = {
                "allowed": False,
                "reason": "INTERN maturity required"
            }
            mock_factory.get_governance_service.return_value = mock_governance

            result = await present_form(
                user_id="user_123",
                form_schema={"fields": []}
            )

            assert result["success"] is False
            assert "not permitted" in result["error"]


# =============================================================================
# TEST CLASS: JavaScript Execution
# =============================================================================

class TestJavaScriptExecution:
    """Tests for canvas JavaScript execution (AUTONOMOUS only)"""

    @pytest.mark.asyncio
    async def test_execute_javascript_success(self, mock_ws_manager):
        """Test successful JavaScript execution by AUTONOMOUS agent"""
        with patch('tools.canvas_tool.ws_manager', mock_ws_manager), \
             patch('tools.canvas_tool.FeatureFlags.should_enforce_governance', return_value=True), \
             patch('core.database.get_db_session') as mock_get_db, \
             patch('tools.canvas_tool.AgentContextResolver') as mock_resolver_class, \
             patch('tools.canvas_tool.AgentStatus') as mock_status, \
             patch('tools.canvas_tool.ServiceFactory') as mock_factory:

            # Setup mocks
            mock_db = MagicMock()
            mock_get_db.return_value.__enter__.return_value = mock_db
            mock_get_db.return_value.__exit__.return_value = None

            mock_agent = MagicMock()
            mock_agent.id = "agent_123"
            mock_agent.status = "autonomous"
            mock_resolver = MagicMock()
            mock_resolver.resolve_agent_for_request = AsyncMock(return_value=(mock_agent, {}))
            mock_resolver_class.return_value = mock_resolver

            # Setup query mock for agent execution lookup
            mock_query = MagicMock()
            mock_execution = MagicMock()
            mock_execution.status = "running"
            mock_query.filter.return_value.first.return_value = mock_execution
            mock_db.query.return_value = mock_query

            mock_governance = MagicMock()
            mock_governance.can_perform_action.return_value = {"allowed": True}
            mock_governance.record_outcome = AsyncMock()
            mock_factory.get_governance_service.return_value = mock_governance

            mock_status.AUTONOMOUS.value = "autonomous"

            result = await canvas_execute_javascript(
                user_id="user_123",
                canvas_id="canvas_123",
                javascript="document.title = 'Updated';",
                agent_id="agent_123"
            )

            assert result["success"] is True
            assert result["canvas_id"] == "canvas_123"

    @pytest.mark.asyncio
    async def test_execute_javascript_blocked_no_agent_id(self, mock_ws_manager):
        """Test JavaScript execution blocked without agent_id"""
        with patch('tools.canvas_tool.ws_manager', mock_ws_manager):

            result = await canvas_execute_javascript(
                user_id="user_123",
                canvas_id="canvas_123",
                javascript="document.title = 'Updated';",
                agent_id=None
            )

            assert result["success"] is False
            assert "requires an explicit agent_id" in result["error"]

    @pytest.mark.asyncio
    async def test_execute_javascript_blocked_dangerous_pattern(self, mock_ws_manager):
        """Test JavaScript execution blocked for dangerous patterns"""
        with patch('tools.canvas_tool.ws_manager', mock_ws_manager), \
             patch('tools.canvas_tool.FeatureFlags.should_enforce_governance', return_value=True), \
             patch('core.database.get_db_session') as mock_get_db, \
             patch('tools.canvas_tool.AgentContextResolver') as mock_resolver_class, \
             patch('tools.canvas_tool.AgentStatus') as mock_status, \
             patch('tools.canvas_tool.ServiceFactory') as mock_factory:

            # Setup mocks
            mock_db = MagicMock()
            mock_get_db.return_value.__enter__.return_value = mock_db
            mock_get_db.return_value.__exit__.return_value = None

            mock_agent = MagicMock()
            mock_agent.id = "agent_123"
            mock_agent.status = "autonomous"
            mock_resolver = MagicMock()
            mock_resolver.resolve_agent_for_request = AsyncMock(return_value=(mock_agent, {}))
            mock_resolver_class.return_value = mock_resolver

            mock_governance = MagicMock()
            mock_governance.can_perform_action.return_value = {"allowed": True}
            mock_factory.get_governance_service.return_value = mock_governance

            mock_status.AUTONOMOUS.value = "autonomous"

            result = await canvas_execute_javascript(
                user_id="user_123",
                canvas_id="canvas_123",
                javascript="eval('malicious code')",
                agent_id="agent_123"
            )

            assert result["success"] is False
            assert "dangerous pattern" in result["error"]

    @pytest.mark.asyncio
    async def test_execute_javascript_blocked_non_autonomous(self, mock_ws_manager):
        """Test JavaScript execution blocked for non-AUTONOMOUS agent"""
        with patch('tools.canvas_tool.ws_manager', mock_ws_manager), \
             patch('tools.canvas_tool.FeatureFlags.should_enforce_governance', return_value=True), \
             patch('core.database.get_db_session') as mock_get_db, \
             patch('tools.canvas_tool.AgentContextResolver') as mock_resolver_class, \
             patch('tools.canvas_tool.AgentStatus') as mock_status, \
             patch('tools.canvas_tool.ServiceFactory') as mock_factory:

            # Setup mocks
            mock_db = MagicMock()
            mock_get_db.return_value.__enter__.return_value = mock_db
            mock_get_db.return_value.__exit__.return_value = None

            mock_agent = MagicMock()
            mock_agent.id = "agent_123"
            mock_agent.status = "intern"  # Not AUTONOMOUS
            mock_resolver = MagicMock()
            mock_resolver.resolve_agent_for_request = AsyncMock(return_value=(mock_agent, {}))
            mock_resolver_class.return_value = mock_resolver

            mock_governance = MagicMock()
            mock_governance.can_perform_action.return_value = {"allowed": True}
            mock_factory.get_governance_service.return_value = mock_governance

            mock_status.AUTONOMOUS.value = "autonomous"

            result = await canvas_execute_javascript(
                user_id="user_123",
                canvas_id="canvas_123",
                javascript="document.title = 'Updated';",
                agent_id="agent_123"
            )

            assert result["success"] is False
            assert "AUTONOMOUS maturity level" in result["error"]

    @pytest.mark.asyncio
    async def test_execute_javascript_blocked_empty_code(self, mock_ws_manager):
        """Test JavaScript execution blocked for empty code"""
        with patch('tools.canvas_tool.ws_manager', mock_ws_manager):

            result = await canvas_execute_javascript(
                user_id="user_123",
                canvas_id="canvas_123",
                javascript="   ",
                agent_id="agent_123"
            )

            assert result["success"] is False
            assert "cannot be empty" in result["error"]


# =============================================================================
# TEST CLASS: Canvas Closing
# =============================================================================

class TestCanvasClosing:
    """Tests for canvas closing functionality"""

    @pytest.mark.asyncio
    async def test_close_canvas_success(self, mock_ws_manager):
        """Test successful canvas closing"""
        with patch('tools.canvas_tool.ws_manager', mock_ws_manager):

            result = await close_canvas(user_id="user_123")

            assert result["success"] is True
            mock_ws_manager.broadcast.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_canvas_with_session_id(self, mock_ws_manager):
        """Test closing canvas with session isolation"""
        with patch('tools.canvas_tool.ws_manager', mock_ws_manager):

            result = await close_canvas(
                user_id="user_123",
                session_id="session_xyz"
            )

            assert result["success"] is True
            # Verify session channel used
            call_args = mock_ws_manager.broadcast.call_args
            assert "session:session_xyz" in call_args[0][0]


# =============================================================================
# TEST CLASS: Generic Canvas Wrapper
# =============================================================================

class TestGenericCanvasWrapper:
    """Tests for present_to_canvas generic wrapper"""

    @pytest.mark.asyncio
    async def test_present_to_canvas_chart_type(self, mock_ws_manager):
        """Test generic wrapper routes to chart function"""
        with patch('tools.canvas_tool.present_chart', new_callable=AsyncMock) as mock_present_chart:

            mock_present_chart.return_value = {"success": True, "canvas_id": "canvas_123"}

            result = await present_to_canvas(
                db=MagicMock(),
                user_id="user_123",
                canvas_type="chart",
                content={"chart_type": "line_chart", "data": [{"x": 1, "y": 100}]},
                title="Test Chart"
            )

            assert result["success"] is True
            mock_present_chart.assert_called_once()

    @pytest.mark.asyncio
    async def test_present_to_canvas_form_type(self, mock_ws_manager):
        """Test generic wrapper routes to form function"""
        with patch('tools.canvas_tool.present_form', new_callable=AsyncMock) as mock_present_form:

            mock_present_form.return_value = {"success": True, "canvas_id": "canvas_456"}

            result = await present_to_canvas(
                db=MagicMock(),
                user_id="user_123",
                canvas_type="form",
                content={"fields": [{"name": "email", "type": "email"}]},
                title="Contact Form"
            )

            assert result["success"] is True
            mock_present_form.assert_called_once()

    @pytest.mark.asyncio
    async def test_present_to_canvas_markdown_type(self, mock_ws_manager):
        """Test generic wrapper routes to markdown function"""
        with patch('tools.canvas_tool.present_markdown', new_callable=AsyncMock) as mock_present_markdown:

            mock_present_markdown.return_value = {"success": True, "canvas_id": "canvas_789"}

            result = await present_to_canvas(
                db=MagicMock(),
                user_id="user_123",
                canvas_type="markdown",
                content={"content": "# Hello World"}
            )

            assert result["success"] is True
            mock_present_markdown.assert_called_once()

    @pytest.mark.asyncio
    async def test_present_to_canvas_status_panel_type(self):
        """Test generic wrapper routes to status panel function"""
        with patch('tools.canvas_tool.present_status_panel', new_callable=AsyncMock) as mock_present_status:

            mock_present_status.return_value = {"success": True}

            result = await present_to_canvas(
                db=MagicMock(),
                user_id="user_123",
                canvas_type="status_panel",
                content={"items": [{"label": "Test", "value": "Value"}]}
            )

            assert result["success"] is True
            mock_present_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_present_to_canvas_specialized_type(self):
        """Test generic wrapper routes to specialized canvas function"""
        with patch('tools.canvas_tool.present_specialized_canvas', new_callable=AsyncMock) as mock_present_special:

            mock_present_special.return_value = {"success": True, "canvas_id": "canvas_special"}

            result = await present_to_canvas(
                db=MagicMock(),
                user_id="user_123",
                canvas_type="docs",
                content={"component_type": "rich_editor", "content": "Test"}
            )

            assert result["success"] is True
            mock_present_special.assert_called_once()

    @pytest.mark.asyncio
    async def test_present_to_canvas_unknown_type(self):
        """Test generic wrapper with unknown canvas type"""
        result = await present_to_canvas(
            db=MagicMock(),
            user_id="user_123",
            canvas_type="unknown_type",
            content={}
        )

        assert result["success"] is False
        assert "Unknown canvas type" in result["error"]


# =============================================================================
# TEST CLASS: Error Handling
# =============================================================================

class TestErrorHandling:
    """Tests for error handling in canvas tool functions"""

    @pytest.mark.asyncio
    async def test_present_chart_handles_exceptions(self, mock_ws_manager):
        """Test present_chart handles exceptions gracefully"""
        with patch('tools.canvas_tool.ws_manager', mock_ws_manager), \
             patch('tools.canvas_tool.FeatureFlags.should_enforce_governance', side_effect=Exception("Unexpected error")):

            result = await present_chart(
                user_id="user_123",
                chart_type="line_chart",
                data=[{"x": 1, "y": 100}]
            )

            assert result["success"] is False
            assert "error" in result

    @pytest.mark.asyncio
    async def test_present_markdown_handles_exceptions(self, mock_ws_manager):
        """Test present_markdown handles exceptions gracefully"""
        with patch('tools.canvas_tool.ws_manager', mock_ws_manager), \
             patch('tools.canvas_tool.FeatureFlags.should_enforce_governance', side_effect=Exception("Service unavailable")):

            result = await present_markdown(
                user_id="user_123",
                content="# Test"
            )

            assert result["success"] is False
            assert "error" in result

    @pytest.mark.asyncio
    async def test_present_form_handles_exceptions(self, mock_ws_manager):
        """Test present_form handles exceptions gracefully"""
        with patch('tools.canvas_tool.ws_manager', mock_ws_manager), \
             patch('tools.canvas_tool.FeatureFlags.should_enforce_governance', side_effect=Exception("Database error")):

            result = await present_form(
                user_id="user_123",
                form_schema={"fields": []}
            )

            assert result["success"] is False
            assert "error" in result

    @pytest.mark.asyncio
    async def test_update_canvas_handles_exceptions(self, mock_ws_manager):
        """Test update_canvas handles exceptions gracefully"""
        with patch('tools.canvas_tool.ws_manager', mock_ws_manager), \
             patch('tools.canvas_tool.FeatureFlags.should_enforce_governance', side_effect=Exception("Update failed")):

            result = await update_canvas(
                user_id="user_123",
                canvas_id="canvas_123",
                updates={"title": "New Title"}
            )

            assert result["success"] is False
            assert "error" in result

    @pytest.mark.asyncio
    async def test_close_canvas_handles_exceptions(self, mock_ws_manager):
        """Test close_canvas handles exceptions gracefully"""
        mock_ws_manager.broadcast.side_effect = Exception("WebSocket error")

        with patch('tools.canvas_tool.ws_manager', mock_ws_manager):

            result = await close_canvas(user_id="user_123")

            assert result["success"] is False
            assert "error" in result

    @pytest.mark.asyncio
    async def test_present_specialized_canvas_handles_exceptions(self, mock_ws_manager):
        """Test present_specialized_canvas handles exceptions gracefully"""
        with patch('tools.canvas_tool.ws_manager', mock_ws_manager), \
             patch('tools.canvas_tool.FeatureFlags.should_enforce_governance', side_effect=Exception("Canvas error")):

            result = await present_specialized_canvas(
                user_id="user_123",
                canvas_type="docs",
                component_type="rich_editor",
                data={}
            )

            assert result["success"] is False
            assert "error" in result
