"""
Comprehensive tests for canvas_tool.py

Tests cover:
- present_chart() - 15 tests
- present_markdown() - 12 tests
- present_form() - 15 tests
- present_status_panel() - 10 tests
- update_canvas() - 12 tests
- close_canvas() - 8 tests
- canvas_execute_javascript() - 15 tests
- present_specialized_canvas() - 15 tests

Total: 100+ tests
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from datetime import datetime
from uuid import uuid4

from core.models import AgentRegistry, AgentStatus, AgentExecution, CanvasAudit
from core.database import get_db_session
from tools.canvas_tool import (
    present_chart,
    present_markdown,
    present_form,
    present_status_panel,
    update_canvas,
    close_canvas,
    canvas_execute_javascript,
    present_specialized_canvas,
    _create_canvas_audit
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_db():
    """Mock database session."""
    db = MagicMock()
    db.add = MagicMock()
    db.commit = MagicMock()
    db.refresh = MagicMock()
    db.query = MagicMock()
    db.rollback = MagicMock()
    return db


@pytest.fixture
def mock_ws_manager():
    """Mock WebSocket manager."""
    with patch('tools.canvas_tool.ws_manager') as mock:
        mock.broadcast = AsyncMock()
        yield mock


@pytest.fixture
def mock_agent_factory():
    """Create mock agent for testing."""
    agent = MagicMock(spec=AgentRegistry)
    agent.id = str(uuid4())
    agent.name = "TestAgent"
    agent.status = AgentStatus.INTERN.value
    agent.maturity_level = 1  # INTERN
    return agent


@pytest.fixture
def student_agent():
    """STUDENT maturity level agent."""
    agent = MagicMock(spec=AgentRegistry)
    agent.id = str(uuid4())
    agent.name = "StudentAgent"
    agent.status = AgentStatus.STUDENT.value
    agent.maturity_level = 0  # STUDENT
    return agent


@pytest.fixture
def autonomous_agent():
    """AUTONOMOUS maturity level agent."""
    agent = MagicMock(spec=AgentRegistry)
    agent.id = str(uuid4())
    agent.name = "AutonomousAgent"
    agent.status = AgentStatus.AUTONOMOUS.value
    agent.maturity_level = 3  # AUTONOMOUS
    return agent


@pytest.fixture
def mock_governance_service():
    """Mock governance service."""
    service = MagicMock()
    service.can_perform_action = MagicMock(return_value={
        "allowed": True,
        "reason": "Agent permitted"
    })
    service.record_outcome = AsyncMock()
    return service


@pytest.fixture
def mock_agent_context_resolver(mock_agent_factory):
    """Mock agent context resolver."""
    with patch('tools.canvas_tool.AgentContextResolver') as mock:
        resolver_instance = MagicMock()
        resolver_instance.resolve_agent_for_request = AsyncMock(return_value=(
            mock_agent_factory,
            {"context": "test"}
        ))
        mock.return_value = resolver_instance
        yield mock


@pytest.fixture
def mock_service_factory(mock_governance_service):
    """Mock service factory."""
    with patch('tools.canvas_tool.ServiceFactory') as mock:
        mock.get_governance_service = MagicMock(return_value=mock_governance_service)
        yield mock


# ============================================================================
# present_chart() Tests (15 tests)
# ============================================================================

class TestPresentChart:
    """Tests for present_chart() function."""

    @pytest.mark.asyncio
    async def test_present_chart_line_success(self, mock_ws_manager, mock_agent_context_resolver, mock_service_factory):
        """Test presenting a line chart successfully."""
        result = await present_chart(
            user_id="user-123",
            chart_type="line_chart",
            data=[{"x": "Jan", "y": 100}, {"x": "Feb", "y": 150}],
            title="Sales Trend"
        )

        assert result["success"] is True
        assert "canvas_id" in result
        assert result["chart_type"] == "line_chart"
        assert mock_ws_manager.broadcast.called

    @pytest.mark.asyncio
    async def test_present_chart_bar_success(self, mock_ws_manager, mock_agent_context_resolver, mock_service_factory):
        """Test presenting a bar chart successfully."""
        result = await present_chart(
            user_id="user-123",
            chart_type="bar_chart",
            data=[{"category": "A", "value": 10}, {"category": "B", "value": 20}],
            title="Category Comparison"
        )

        assert result["success"] is True
        assert result["chart_type"] == "bar_chart"

    @pytest.mark.asyncio
    async def test_present_chart_pie_success(self, mock_ws_manager, mock_agent_context_resolver, mock_service_factory):
        """Test presenting a pie chart successfully."""
        result = await present_chart(
            user_id="user-123",
            chart_type="pie_chart",
            data=[{"label": "Chrome", "value": 60}, {"label": "Firefox", "value": 40}],
            title="Browser Share"
        )

        assert result["success"] is True
        assert result["chart_type"] == "pie_chart"

    @pytest.mark.asyncio
    async def test_present_chart_with_session_isolation(self, mock_ws_manager, mock_agent_context_resolver, mock_service_factory):
        """Test chart presentation with session isolation."""
        session_id = "session-abc"

        result = await present_chart(
            user_id="user-123",
            chart_type="line_chart",
            data=[{"x": 1, "y": 10}],
            session_id=session_id
        )

        assert result["success"] is True

        # Verify WebSocket was called with session-specific channel
        call_args = mock_ws_manager.broadcast.call_args
        assert call_args is not None
        channel = call_args[0][0]
        assert f"session:{session_id}" in channel

    @pytest.mark.asyncio
    async def test_present_chart_empty_data(self, mock_ws_manager, mock_agent_context_resolver, mock_service_factory):
        """Test chart with empty data."""
        result = await present_chart(
            user_id="user-123",
            chart_type="line_chart",
            data=[],
            title="Empty Chart"
        )

        assert result["success"] is True
        assert mock_ws_manager.broadcast.called

    @pytest.mark.asyncio
    async def test_present_chart_large_dataset(self, mock_ws_manager, mock_agent_context_resolver, mock_service_factory):
        """Test chart with large dataset."""
        large_data = [{"x": i, "y": i * 10} for i in range(1000)]

        result = await present_chart(
            user_id="user-123",
            chart_type="line_chart",
            data=large_data,
            title="Large Dataset"
        )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_present_chart_governance_allowed(self, mock_ws_manager, mock_agent_context_resolver, mock_service_factory, mock_governance_service):
        """Test chart presentation with governance allowed."""
        result = await present_chart(
            user_id="user-123",
            chart_type="line_chart",
            data=[{"x": 1, "y": 10}],
            agent_id="agent-123"
        )

        assert result["success"] is True
        assert mock_governance_service.can_perform_action.called

    @pytest.mark.asyncio
    async def test_present_chart_governance_blocked(self, mock_ws_manager, mock_agent_context_resolver, mock_service_factory, student_agent, mock_governance_service):
        """Test chart presentation with governance blocked."""
        # Block governance check
        mock_governance_service.can_perform_action.return_value = {
            "allowed": False,
            "reason": "STUDENT agents not permitted"
        }

        # Override resolver to return student agent
        mock_agent_context_resolver.return_value.resolve_agent_for_request = AsyncMock(return_value=(
            student_agent,
            {}
        ))

        result = await present_chart(
            user_id="user-123",
            chart_type="line_chart",
            data=[{"x": 1, "y": 10}],
            agent_id="student-agent"
        )

        assert result["success"] is False
        assert "not permitted" in result["error"]

    @pytest.mark.asyncio
    async def test_present_chart_without_agent(self, mock_ws_manager):
        """Test chart presentation without agent (no governance)."""
        with patch('tools.canvas_tool.FeatureFlags.should_enforce_governance', return_value=False):
            result = await present_chart(
                user_id="user-123",
                chart_type="line_chart",
                data=[{"x": 1, "y": 10}]
            )

            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_present_chart_websocket_broadcast_called(self, mock_ws_manager, mock_agent_context_resolver, mock_service_factory):
        """Test that WebSocket broadcast is called with correct data."""
        await present_chart(
            user_id="user-123",
            chart_type="line_chart",
            data=[{"x": 1, "y": 10}],
            title="Test Chart"
        )

        assert mock_ws_manager.broadcast.called
        call_args = mock_ws_manager.broadcast.call_args[0][1]
        assert call_args["type"] == "canvas:update"
        assert call_args["data"]["action"] == "present"
        assert call_args["data"]["component"] == "line_chart"

    @pytest.mark.asyncio
    async def test_present_chart_audit_entry_created(self, mock_ws_manager, mock_agent_context_resolver, mock_service_factory, mock_db):
        """Test that canvas audit entry is created."""
        with patch('tools.canvas_tool.get_db_session', return_value=mock_db):
            with patch('tools.canvas_tool._create_canvas_audit', new_callable=AsyncMock) as mock_audit:
                mock_audit.return_value = MagicMock(id="audit-123")

                await present_chart(
                    user_id="user-123",
                    chart_type="line_chart",
                    data=[{"x": 1, "y": 10}],
                    agent_id="agent-123"
                )

                assert mock_audit.called
                audit_call_args = mock_audit.call_args[1]
                assert audit_call_args["canvas_type"] == "generic"
                assert audit_call_args["component_type"] == "chart"

    @pytest.mark.asyncio
    async def test_present_chart_agent_execution_tracking(self, mock_ws_manager, mock_agent_context_resolver, mock_service_factory, mock_db):
        """Test that agent execution is tracked."""
        with patch('tools.canvas_tool.get_db_session', return_value=mock_db):
            await present_chart(
                user_id="user-123",
                chart_type="line_chart",
                data=[{"x": 1, "y": 10}],
                agent_id="agent-123"
            )

            assert mock_db.add.called
            assert mock_db.commit.called

    @pytest.mark.asyncio
    async def test_present_chart_with_options(self, mock_ws_manager, mock_agent_context_resolver, mock_service_factory):
        """Test chart with additional options."""
        result = await present_chart(
            user_id="user-123",
            chart_type="line_chart",
            data=[{"x": 1, "y": 10}],
            title="Styled Chart",
            color="red",
            width=800
        )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_present_chart_failure_handling(self, mock_agent_context_resolver, mock_service_factory):
        """Test error handling in chart presentation."""
        with patch('tools.canvas_tool.ws_manager') as mock_ws:
            mock_ws.broadcast = AsyncMock(side_effect=Exception("WebSocket error"))

            result = await present_chart(
                user_id="user-123",
                chart_type="line_chart",
                data=[{"x": 1, "y": 10}]
            )

            assert result["success"] is False
            assert "error" in result

    @pytest.mark.asyncio
    async def test_present_chart_outcome_recorded(self, mock_ws_manager, mock_agent_context_resolver, mock_service_factory, mock_governance_service):
        """Test that positive outcome is recorded for governance."""
        result = await present_chart(
            user_id="user-123",
            chart_type="line_chart",
            data=[{"x": 1, "y": 10}],
            agent_id="agent-123"
        )

        assert result["success"] is True
        # Verify record_outcome was called
        assert mock_governance_service.record_outcome.called


# ============================================================================
# present_markdown() Tests (12 tests)
# ============================================================================

class TestPresentMarkdown:
    """Tests for present_markdown() function."""

    @pytest.mark.asyncio
    async def test_present_markdown_success(self, mock_ws_manager, mock_agent_context_resolver, mock_service_factory):
        """Test presenting markdown successfully."""
        result = await present_markdown(
            user_id="user-123",
            content="# Header\n\nThis is markdown content.",
            title="Test Document"
        )

        assert result["success"] is True
        assert "canvas_id" in result

    @pytest.mark.asyncio
    async def test_present_markdown_empty_content(self, mock_ws_manager, mock_agent_context_resolver, mock_service_factory):
        """Test markdown with empty content."""
        result = await present_markdown(
            user_id="user-123",
            content="",
            title="Empty"
        )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_present_markdown_long_content(self, mock_ws_manager, mock_agent_context_resolver, mock_service_factory):
        """Test markdown with long content."""
        long_content = "# Header\n\n" + "Paragraph text. " * 1000

        result = await present_markdown(
            user_id="user-123",
            content=long_content,
            title="Long Document"
        )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_present_markdown_special_characters(self, mock_ws_manager, mock_agent_context_resolver, mock_service_factory):
        """Test markdown with special characters."""
        content = "# Test\n\nCode: `var x = 1;`\n\nMath: E = mc^2\n\nSymbols: @#$%^&*()"

        result = await present_markdown(
            user_id="user-123",
            content=content
        )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_present_markdown_without_title(self, mock_ws_manager, mock_agent_context_resolver, mock_service_factory):
        """Test markdown without title."""
        result = await present_markdown(
            user_id="user-123",
            content="Just content"
        )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_present_markdown_governance_allowed(self, mock_ws_manager, mock_agent_context_resolver, mock_service_factory, mock_governance_service):
        """Test markdown with governance allowed."""
        result = await present_markdown(
            user_id="user-123",
            content="# Test",
            agent_id="agent-123"
        )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_present_markdown_governance_blocked(self, mock_ws_manager, mock_agent_context_resolver, mock_service_factory, student_agent, mock_governance_service):
        """Test markdown with governance blocked."""
        mock_governance_service.can_perform_action.return_value = {
            "allowed": False,
            "reason": "Not permitted"
        }
        mock_agent_context_resolver.return_value.resolve_agent_for_request = AsyncMock(return_value=(
            student_agent,
            {}
        ))

        result = await present_markdown(
            user_id="user-123",
            content="# Test",
            agent_id="student-agent"
        )

        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_present_markdown_with_session_isolation(self, mock_ws_manager, mock_agent_context_resolver, mock_service_factory):
        """Test markdown with session isolation."""
        session_id = "session-xyz"

        result = await present_markdown(
            user_id="user-123",
            content="# Test",
            session_id=session_id
        )

        assert result["success"] is True
        call_args = mock_ws_manager.broadcast.call_args[0][0]
        assert f"session:{session_id}" in call_args

    @pytest.mark.asyncio
    async def test_present_markdown_audit_entry(self, mock_ws_manager, mock_agent_context_resolver, mock_service_factory, mock_db):
        """Test markdown creates audit entry."""
        with patch('tools.canvas_tool.get_db_session', return_value=mock_db):
            with patch('tools.canvas_tool._create_canvas_audit', new_callable=AsyncMock) as mock_audit:
                mock_audit.return_value = MagicMock(id="audit-456")

                await present_markdown(
                    user_id="user-123",
                    content="# Test",
                    agent_id="agent-123"
                )

                assert mock_audit.called
                call_kwargs = mock_audit.call_args[1]
                assert call_kwargs["component_type"] == "markdown"

    @pytest.mark.asyncio
    async def test_present_markdown_execution_tracking(self, mock_ws_manager, mock_agent_context_resolver, mock_service_factory, mock_db):
        """Test markdown execution tracking."""
        with patch('tools.canvas_tool.get_db_session', return_value=mock_db):
            await present_markdown(
                user_id="user-123",
                content="# Test",
                agent_id="agent-123"
            )

            assert mock_db.add.called

    @pytest.mark.asyncio
    async def test_present_markdown_websocket_data(self, mock_ws_manager, mock_agent_context_resolver, mock_service_factory):
        """Test markdown WebSocket broadcast data."""
        await present_markdown(
            user_id="user-123",
            content="# Test",
            title="My Title"
        )

        call_args = mock_ws_manager.broadcast.call_args[0][1]
        assert call_args["data"]["component"] == "markdown"
        assert call_args["data"]["data"]["content"] == "# Test"
        assert call_args["data"]["data"]["title"] == "My Title"

    @pytest.mark.asyncio
    async def test_present_markdown_error_handling(self, mock_agent_context_resolver, mock_service_factory):
        """Test markdown error handling."""
        with patch('tools.canvas_tool.ws_manager') as mock_ws:
            mock_ws.broadcast = AsyncMock(side_effect=Exception("Broadcast failed"))

            result = await present_markdown(
                user_id="user-123",
                content="# Test"
            )

            assert result["success"] is False


# ============================================================================
# present_form() Tests (15 tests)
# ============================================================================

class TestPresentForm:
    """Tests for present_form() function."""

    @pytest.mark.asyncio
    async def test_present_form_success(self, mock_ws_manager, mock_agent_context_resolver, mock_service_factory):
        """Test presenting form successfully."""
        schema = {
            "fields": [
                {"name": "email", "type": "email", "required": True},
                {"name": "name", "type": "text", "required": False}
            ]
        }

        result = await present_form(
            user_id="user-123",
            form_schema=schema,
            title="Contact Form"
        )

        assert result["success"] is True
        assert "canvas_id" in result
        assert "agent_execution_id" in result

    @pytest.mark.asyncio
    async def test_present_form_complex_schema(self, mock_ws_manager, mock_agent_context_resolver, mock_service_factory):
        """Test form with complex schema."""
        schema = {
            "fields": [
                {"name": "email", "type": "email", "label": "Email Address", "required": True, "validation": {"pattern": "^[^@]+@[^@]+$"}},
                {"name": "age", "type": "number", "label": "Age", "min": 18, "max": 120},
                {"name": "bio", "type": "textarea", "label": "Bio", "maxlength": 500},
                {"name": "newsletter", "type": "checkbox", "label": "Subscribe", "default": False}
            ]
        }

        result = await present_form(
            user_id="user-123",
            form_schema=schema,
            title="Registration Form"
        )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_present_form_empty_fields(self, mock_ws_manager, mock_agent_context_resolver, mock_service_factory):
        """Test form with empty fields list."""
        schema = {"fields": []}

        result = await present_form(
            user_id="user-123",
            form_schema=schema,
            title="Empty Form"
        )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_present_form_no_schema(self, mock_ws_manager, mock_agent_context_resolver, mock_service_factory):
        """Test form without proper schema."""
        schema = {}

        result = await present_form(
            user_id="user-123",
            form_schema=schema
        )

        assert result["success"] is True  # Should still work

    @pytest.mark.asyncio
    async def test_present_form_governance_allowed_intern(self, mock_ws_manager, mock_agent_context_resolver, mock_service_factory, mock_governance_service):
        """Test form with INTERN agent allowed."""
        result = await present_form(
            user_id="user-123",
            form_schema={"fields": [{"name": "test", "type": "text"}]},
            agent_id="agent-123"
        )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_present_form_governance_blocked_student(self, mock_ws_manager, mock_agent_context_resolver, mock_service_factory, student_agent, mock_governance_service):
        """Test form with STUDENT agent blocked."""
        mock_governance_service.can_perform_action.return_value = {
            "allowed": False,
            "reason": "STUDENT cannot present forms"
        }
        mock_agent_context_resolver.return_value.resolve_agent_for_request = AsyncMock(return_value=(
            student_agent,
            {}
        ))

        result = await present_form(
            user_id="user-123",
            form_schema={"fields": []},
            agent_id="student-agent"
        )

        assert result["success"] is False
        assert "not permitted" in result["error"]

    @pytest.mark.asyncio
    async def test_present_form_with_session_isolation(self, mock_ws_manager, mock_agent_context_resolver, mock_service_factory):
        """Test form with session isolation."""
        session_id = "form-session"

        result = await present_form(
            user_id="user-123",
            form_schema={"fields": [{"name": "test", "type": "text"}]},
            session_id=session_id
        )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_present_form_websocket_data(self, mock_ws_manager, mock_agent_context_resolver, mock_service_factory):
        """Test form WebSocket broadcast data."""
        schema = {"fields": [{"name": "email", "type": "email"}]}

        await present_form(
            user_id="user-123",
            form_schema=schema,
            title="Email Form"
        )

        call_args = mock_ws_manager.broadcast.call_args[0][1]
        assert call_args["data"]["component"] == "form"
        assert call_args["data"]["data"]["schema"] == schema

    @pytest.mark.asyncio
    async def test_present_form_audit_entry(self, mock_ws_manager, mock_agent_context_resolver, mock_service_factory, mock_db):
        """Test form creates audit entry."""
        with patch('tools.canvas_tool.get_db_session', return_value=mock_db):
            with patch('tools.canvas_tool._create_canvas_audit', new_callable=AsyncMock) as mock_audit:
                mock_audit.return_value = MagicMock(id="audit-form")

                await present_form(
                    user_id="user-123",
                    form_schema={"fields": [{"name": "test", "type": "text"}]},
                    agent_id="agent-123"
                )

                assert mock_audit.called
                call_kwargs = mock_audit.call_args[1]
                assert call_kwargs["component_type"] == "form"

    @pytest.mark.asyncio
    async def test_present_form_execution_tracking(self, mock_ws_manager, mock_agent_context_resolver, mock_service_factory, mock_db):
        """Test form execution tracking."""
        with patch('tools.canvas_tool.get_db_session', return_value=mock_db):
            result = await present_form(
                user_id="user-123",
                form_schema={"fields": []},
                agent_id="agent-123"
            )

            assert "agent_execution_id" in result
            assert mock_db.add.called

    @pytest.mark.asyncio
    async def test_present_form_field_validation_types(self, mock_ws_manager, mock_agent_context_resolver, mock_service_factory):
        """Test form with various field types."""
        schema = {
            "fields": [
                {"name": "text", "type": "text"},
                {"name": "email", "type": "email"},
                {"name": "number", "type": "number"},
                {"name": "textarea", "type": "textarea"},
                {"name": "checkbox", "type": "checkbox"},
                {"name": "select", "type": "select", "options": ["A", "B", "C"]}
            ]
        }

        result = await present_form(
            user_id="user-123",
            form_schema=schema
        )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_present_form_field_validation_rules(self, mock_ws_manager, mock_agent_context_resolver, mock_service_factory):
        """Test form with field validation rules."""
        schema = {
            "fields": [
                {"name": "age", "type": "number", "required": True, "min": 18, "max": 100},
                {"name": "url", "type": "text", "pattern": "^https?://"},
                {"name": "length", "type": "text", "minlength": 5, "maxlength": 50}
            ]
        }

        result = await present_form(
            user_id="user-123",
            form_schema=schema
        )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_present_form_without_title(self, mock_ws_manager, mock_agent_context_resolver, mock_service_factory):
        """Test form without title."""
        result = await present_form(
            user_id="user-123",
            form_schema={"fields": [{"name": "test", "type": "text"}]}
        )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_present_form_error_handling(self, mock_agent_context_resolver, mock_service_factory):
        """Test form error handling."""
        with patch('tools.canvas_tool.ws_manager') as mock_ws:
            mock_ws.broadcast = AsyncMock(side_effect=Exception("Form broadcast failed"))

            result = await present_form(
                user_id="user-123",
                form_schema={"fields": []}
            )

            assert result["success"] is False

    @pytest.mark.asyncio
    async def test_present_form_outcome_recorded(self, mock_ws_manager, mock_agent_context_resolver, mock_service_factory, mock_governance_service):
        """Test form outcome recording."""
        result = await present_form(
            user_id="user-123",
            form_schema={"fields": []},
            agent_id="agent-123"
        )

        assert result["success"] is True
        assert mock_governance_service.record_outcome.called


# ============================================================================
# present_status_panel() Tests (10 tests)
# ============================================================================

class TestPresentStatusPanel:
    """Tests for present_status_panel() function."""

    @pytest.mark.asyncio
    async def test_present_status_panel_success(self, mock_ws_manager, mock_agent_context_resolver, mock_service_factory):
        """Test presenting status panel successfully."""
        items = [
            {"label": "CPU", "value": "45%", "trend": "up"},
            {"label": "Memory", "value": "2.1 GB", "trend": "stable"}
        ]

        result = await present_status_panel(
            user_id="user-123",
            items=items,
            title="System Status"
        )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_present_status_panel_empty_items(self, mock_ws_manager, mock_agent_context_resolver, mock_service_factory):
        """Test status panel with empty items."""
        result = await present_status_panel(
            user_id="user-123",
            items=[],
            title="Empty Status"
        )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_present_status_panel_multiple_items(self, mock_ws_manager, mock_agent_context_resolver, mock_service_factory):
        """Test status panel with many items."""
        items = [
            {"label": f"Metric {i}", "value": f"{i * 10}%", "trend": "up" if i % 2 == 0 else "down"}
            for i in range(20)
        ]

        result = await present_status_panel(
            user_id="user-123",
            items=items
        )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_present_status_panel_trend_display(self, mock_ws_manager, mock_agent_context_resolver, mock_service_factory):
        """Test status panel with trend data."""
        items = [
            {"label": "Sales", "value": "$10,000", "trend": "+15%"},
            {"label": "Users", "value": "1,234", "trend": "+5%"}
        ]

        result = await present_status_panel(
            user_id="user-123",
            items=items
        )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_present_status_panel_without_trend(self, mock_ws_manager, mock_agent_context_resolver, mock_service_factory):
        """Test status panel without trend data."""
        items = [
            {"label": "Status", "value": "Active"}
        ]

        result = await present_status_panel(
            user_id="user-123",
            items=items
        )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_present_status_panel_governance_allowed(self, mock_ws_manager, mock_agent_context_resolver, mock_service_factory, mock_governance_service):
        """Test status panel with governance allowed."""
        result = await present_status_panel(
            user_id="user-123",
            items=[{"label": "Test", "value": "OK"}],
            agent_id="agent-123"
        )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_present_status_panel_governance_blocked(self, mock_ws_manager, mock_agent_context_resolver, mock_service_factory, student_agent, mock_governance_service):
        """Test status panel with governance blocked."""
        mock_governance_service.can_perform_action.return_value = {
            "allowed": False,
            "reason": "Blocked"
        }
        mock_agent_context_resolver.return_value.resolve_agent_for_request = AsyncMock(return_value=(
            student_agent,
            {}
        ))

        result = await present_status_panel(
            user_id="user-123",
            items=[{"label": "Test", "value": "OK"}],
            agent_id="student-agent"
        )

        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_present_status_panel_session_isolation(self, mock_ws_manager, mock_agent_context_resolver, mock_service_factory):
        """Test status panel with session isolation."""
        result = await present_status_panel(
            user_id="user-123",
            items=[{"label": "Test", "value": "OK"}],
            session_id="status-session"
        )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_present_status_panel_websocket_data(self, mock_ws_manager, mock_agent_context_resolver, mock_service_factory):
        """Test status panel WebSocket data."""
        items = [{"label": "CPU", "value": "50%"}]

        await present_status_panel(
            user_id="user-123",
            items=items,
            title="Metrics"
        )

        call_args = mock_ws_manager.broadcast.call_args[0][1]
        assert call_args["data"]["component"] == "status_panel"
        assert call_args["data"]["data"]["items"] == items

    @pytest.mark.asyncio
    async def test_present_status_panel_error_handling(self, mock_agent_context_resolver, mock_service_factory):
        """Test status panel error handling."""
        with patch('tools.canvas_tool.ws_manager') as mock_ws:
            mock_ws.broadcast = AsyncMock(side_effect=Exception("Status broadcast failed"))

            result = await present_status_panel(
                user_id="user-123",
                items=[]
            )

            assert result["success"] is False


# ============================================================================
# update_canvas() Tests (12 tests)
# ============================================================================

class TestUpdateCanvas:
    """Tests for update_canvas() function."""

    @pytest.mark.asyncio
    async def test_update_canvas_success(self, mock_ws_manager, mock_agent_context_resolver, mock_service_factory):
        """Test updating canvas successfully."""
        result = await update_canvas(
            user_id="user-123",
            canvas_id="canvas-abc",
            updates={"data": [{"x": 1, "y": 20}, {"x": 2, "y": 30}]}
        )

        assert result["success"] is True
        assert result["canvas_id"] == "canvas-abc"
        assert "data" in result["updated_fields"]

    @pytest.mark.asyncio
    async def test_update_canvas_multiple_fields(self, mock_ws_manager, mock_agent_context_resolver, mock_service_factory):
        """Test updating multiple canvas fields."""
        result = await update_canvas(
            user_id="user-123",
            canvas_id="canvas-abc",
            updates={
                "title": "Updated Title",
                "data": [{"x": 1, "y": 100}],
                "color": "blue"
            }
        )

        assert result["success"] is True
        assert len(result["updated_fields"]) == 3

    @pytest.mark.asyncio
    async def test_update_canvas_governance_allowed(self, mock_ws_manager, mock_agent_context_resolver, mock_service_factory, mock_governance_service):
        """Test canvas update with governance allowed."""
        result = await update_canvas(
            user_id="user-123",
            canvas_id="canvas-abc",
            updates={"title": "New Title"},
            agent_id="agent-123"
        )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_update_canvas_governance_blocked(self, mock_ws_manager, mock_agent_context_resolver, mock_service_factory, student_agent, mock_governance_service):
        """Test canvas update with governance blocked."""
        mock_governance_service.can_perform_action.return_value = {
            "allowed": False,
            "reason": "Cannot update"
        }
        mock_agent_context_resolver.return_value.resolve_agent_for_request = AsyncMock(return_value=(
            student_agent,
            {}
        ))

        result = await update_canvas(
            user_id="user-123",
            canvas_id="canvas-abc",
            updates={"title": "New Title"},
            agent_id="student-agent"
        )

        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_update_canvas_with_session_isolation(self, mock_ws_manager, mock_agent_context_resolver, mock_service_factory):
        """Test canvas update with session isolation."""
        result = await update_canvas(
            user_id="user-123",
            canvas_id="canvas-abc",
            updates={"data": []},
            session_id="update-session"
        )

        assert result["success"] is True
        assert result["session_id"] == "update-session"

    @pytest.mark.asyncio
    async def test_update_canvas_websocket_action(self, mock_ws_manager, mock_agent_context_resolver, mock_service_factory):
        """Test canvas update WebSocket action."""
        await update_canvas(
            user_id="user-123",
            canvas_id="canvas-abc",
            updates={"title": "Updated"}
        )

        call_args = mock_ws_manager.broadcast.call_args[0][1]
        assert call_args["data"]["action"] == "update"
        assert call_args["data"]["canvas_id"] == "canvas-abc"

    @pytest.mark.asyncio
    async def test_update_canvas_audit_entry(self, mock_ws_manager, mock_agent_context_resolver, mock_service_factory, mock_db):
        """Test canvas update creates audit entry."""
        with patch('tools.canvas_tool.get_db_session', return_value=mock_db):
            with patch('tools.canvas_tool._create_canvas_audit', new_callable=AsyncMock) as mock_audit:
                mock_audit.return_value = MagicMock(id="audit-update")

                await update_canvas(
                    user_id="user-123",
                    canvas_id="canvas-abc",
                    updates={"title": "New"},
                    agent_id="agent-123"
                )

                assert mock_audit.called
                call_kwargs = mock_audit.call_args[1]
                assert call_kwargs["action"] == "update"

    @pytest.mark.asyncio
    async def test_update_canvas_execution_tracking(self, mock_ws_manager, mock_agent_context_resolver, mock_service_factory, mock_db):
        """Test canvas update execution tracking."""
        with patch('tools.canvas_tool.get_db_session', return_value=mock_db):
            result = await update_canvas(
                user_id="user-123",
                canvas_id="canvas-abc",
                updates={"data": []},
                agent_id="agent-123"
            )

            assert "agent_id" in result
            assert mock_db.add.called

    @pytest.mark.asyncio
    async def test_update_canvas_empty_updates(self, mock_ws_manager, mock_agent_context_resolver, mock_service_factory):
        """Test canvas update with empty updates."""
        result = await update_canvas(
            user_id="user-123",
            canvas_id="canvas-abc",
            updates={}
        )

        assert result["success"] is True
        assert result["updated_fields"] == []

    @pytest.mark.asyncio
    async def test_update_canvas_complex_data(self, mock_ws_manager, mock_agent_context_resolver, mock_service_factory):
        """Test canvas update with complex data structure."""
        updates = {
            "data": {
                "series": [
                    {"name": "A", "values": [1, 2, 3]},
                    {"name": "B", "values": [4, 5, 6]}
                ],
                "metadata": {"source": "API", "timestamp": "2024-01-01"}
            }
        }

        result = await update_canvas(
            user_id="user-123",
            canvas_id="canvas-abc",
            updates=updates
        )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_update_canvas_outcome_recorded(self, mock_ws_manager, mock_agent_context_resolver, mock_service_factory, mock_governance_service):
        """Test canvas update outcome recording."""
        result = await update_canvas(
            user_id="user-123",
            canvas_id="canvas-abc",
            updates={"title": "Updated"},
            agent_id="agent-123"
        )

        assert result["success"] is True
        assert mock_governance_service.record_outcome.called

    @pytest.mark.asyncio
    async def test_update_canvas_error_handling(self, mock_agent_context_resolver, mock_service_factory):
        """Test canvas update error handling."""
        with patch('tools.canvas_tool.ws_manager') as mock_ws:
            mock_ws.broadcast = AsyncMock(side_effect=Exception("Update failed"))

            result = await update_canvas(
                user_id="user-123",
                canvas_id="canvas-abc",
                updates={"title": "New"}
            )

            assert result["success"] is False


# ============================================================================
# close_canvas() Tests (8 tests)
# ============================================================================

class TestCloseCanvas:
    """Tests for close_canvas() function."""

    @pytest.mark.asyncio
    async def test_close_canvas_success(self, mock_ws_manager):
        """Test closing canvas successfully."""
        result = await close_canvas(
            user_id="user-123"
        )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_close_canvas_with_session(self, mock_ws_manager):
        """Test closing canvas with session isolation."""
        result = await close_canvas(
            user_id="user-123",
            session_id="close-session"
        )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_close_canvas_websocket_action(self, mock_ws_manager):
        """Test close canvas WebSocket action."""
        await close_canvas(user_id="user-123")

        call_args = mock_ws_manager.broadcast.call_args[0][1]
        assert call_args["data"]["action"] == "close"

    @pytest.mark.asyncio
    async def test_close_canvas_session_channel(self, mock_ws_manager):
        """Test close canvas uses session-specific channel."""
        session_id = "my-session"

        await close_canvas(
            user_id="user-123",
            session_id=session_id
        )

        call_args = mock_ws_manager.broadcast.call_args[0][0]
        assert f"session:{session_id}" in call_args

    @pytest.mark.asyncio
    async def test_close_canvas_without_session(self, mock_ws_manager):
        """Test close canvas without session uses user channel."""
        await close_canvas(user_id="user-123")

        call_args = mock_ws_manager.broadcast.call_args[0][0]
        assert "user:user-123" in call_args
        assert "session:" not in call_args

    @pytest.mark.asyncio
    async def test_close_canvas_error_handling(self):
        """Test close canvas error handling."""
        with patch('tools.canvas_tool.ws_manager') as mock_ws:
            mock_ws.broadcast = AsyncMock(side_effect=Exception("Close failed"))

            result = await close_canvas(user_id="user-123")

            assert result["success"] is False

    @pytest.mark.asyncio
    async def test_close_canvas_idempotent(self, mock_ws_manager):
        """Test close canvas is idempotent."""
        result1 = await close_canvas(user_id="user-123")
        result2 = await close_canvas(user_id="user-123")

        assert result1["success"] is True
        assert result2["success"] is True

    @pytest.mark.asyncio
    async def test_close_canvas_no_agent_required(self, mock_ws_manager):
        """Test close canvas doesn't require agent."""
        result = await close_canvas(user_id="user-123")

        assert result["success"] is True
        # No governance check needed for close


# ============================================================================
# canvas_execute_javascript() Tests (15 tests)
# ============================================================================

class TestCanvasExecuteJavaScript:
    """Tests for canvas_execute_javascript() function."""

    @pytest.mark.asyncio
    async def test_execute_javascript_success(self, mock_ws_manager, mock_agent_context_resolver, mock_service_factory, autonomous_agent):
        """Test JavaScript execution successfully."""
        mock_agent_context_resolver.return_value.resolve_agent_for_request = AsyncMock(return_value=(
            autonomous_agent,
            {}
        ))

        result = await canvas_execute_javascript(
            user_id="user-123",
            canvas_id="canvas-abc",
            javascript="document.title = 'New Title';",
            agent_id="autonomous-agent"
        )

        assert result["success"] is True
        assert result["canvas_id"] == "canvas-abc"

    @pytest.mark.asyncio
    async def test_execute_javascript_autonomous_only(self, mock_ws_manager, mock_agent_context_resolver, mock_service_factory):
        """Test only AUTONOMOUS agents can execute JavaScript."""
        intern_agent = MagicMock(spec=AgentRegistry)
        intern_agent.id = "intern-123"
        intern_agent.name = "InternAgent"
        intern_agent.status = AgentStatus.INTERN.value
        intern_agent.maturity_level = 1

        mock_agent_context_resolver.return_value.resolve_agent_for_request = AsyncMock(return_value=(
            intern_agent,
            {}
        ))

        result = await canvas_execute_javascript(
            user_id="user-123",
            canvas_id="canvas-abc",
            javascript="document.title = 'Test';",
            agent_id="intern-agent"
        )

        assert result["success"] is False
        assert "AUTONOMOUS" in result["error"]

    @pytest.mark.asyncio
    async def test_execute_javascript_no_agent_id(self, mock_ws_manager, mock_agent_context_resolver, mock_service_factory):
        """Test JavaScript execution requires agent_id."""
        result = await canvas_execute_javascript(
            user_id="user-123",
            canvas_id="canvas-abc",
            javascript="document.title = 'Test';",
            agent_id=None
        )

        assert result["success"] is False
        assert "requires an explicit agent_id" in result["error"]

    @pytest.mark.asyncio
    async def test_execute_javascript_empty_code(self, mock_ws_manager, mock_agent_context_resolver, mock_service_factory, autonomous_agent):
        """Test empty JavaScript code is rejected."""
        mock_agent_context_resolver.return_value.resolve_agent_for_request = AsyncMock(return_value=(
            autonomous_agent,
            {}
        ))

        result = await canvas_execute_javascript(
            user_id="user-123",
            canvas_id="canvas-abc",
            javascript="",
            agent_id="autonomous-agent"
        )

        assert result["success"] is False
        assert "cannot be empty" in result["error"]

    @pytest.mark.asyncio
    async def test_execute_javascript_whitespace_only(self, mock_ws_manager, mock_agent_context_resolver, mock_service_factory, autonomous_agent):
        """Test whitespace-only JavaScript is rejected."""
        mock_agent_context_resolver.return_value.resolve_agent_for_request = AsyncMock(return_value=(
            autonomous_agent,
            {}
        ))

        result = await canvas_execute_javascript(
            user_id="user-123",
            canvas_id="canvas-abc",
            javascript="   \n\t   ",
            agent_id="autonomous-agent"
        )

        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_execute_javascript_dangerous_eval(self, mock_ws_manager, mock_agent_context_resolver, mock_service_factory, autonomous_agent):
        """Test eval() is blocked."""
        mock_agent_context_resolver.return_value.resolve_agent_for_request = AsyncMock(return_value=(
            autonomous_agent,
            {}
        ))

        result = await canvas_execute_javascript(
            user_id="user-123",
            canvas_id="canvas-abc",
            javascript="eval('malicious code');",
            agent_id="autonomous-agent"
        )

        assert result["success"] is False
        assert "dangerous pattern" in result["error"]

    @pytest.mark.asyncio
    async def test_execute_javascript_dangerous_function(self, mock_ws_manager, mock_agent_context_resolver, mock_service_factory, autonomous_agent):
        """Test Function() constructor is blocked."""
        mock_agent_context_resolver.return_value.resolve_agent_for_request = AsyncMock(return_value=(
            autonomous_agent,
            {}
        ))

        result = await canvas_execute_javascript(
            user_id="user-123",
            canvas_id="canvas-abc",
            javascript="new Function('return 1');",
            agent_id="autonomous-agent"
        )

        assert result["success"] is False
        assert "dangerous pattern" in result["error"]

    @pytest.mark.asyncio
    async def test_execute_javascript_cookie_access(self, mock_ws_manager, mock_agent_context_resolver, mock_service_factory, autonomous_agent):
        """Test document.cookie access is blocked."""
        mock_agent_context_resolver.return_value.resolve_agent_for_request = AsyncMock(return_value=(
            autonomous_agent,
            {}
        ))

        result = await canvas_execute_javascript(
            user_id="user-123",
            canvas_id="canvas-abc",
            javascript="document.cookie;",
            agent_id="autonomous-agent"
        )

        assert result["success"] is False
        assert "dangerous pattern" in result["error"]

    @pytest.mark.asyncio
    async def test_execute_javascript_localstorage(self, mock_ws_manager, mock_agent_context_resolver, mock_service_factory, autonomous_agent):
        """Test localStorage access is blocked."""
        mock_agent_context_resolver.return_value.resolve_agent_for_request = AsyncMock(return_value=(
            autonomous_agent,
            {}
        ))

        result = await canvas_execute_javascript(
            user_id="user-123",
            canvas_id="canvas-abc",
            javascript="localStorage.getItem('token');",
            agent_id="autonomous-agent"
        )

        assert result["success"] is False
        assert "dangerous pattern" in result["error"]

    @pytest.mark.asyncio
    async def test_execute_javascript_location_manipulation(self, mock_ws_manager, mock_agent_context_resolver, mock_service_factory, autonomous_agent):
        """Test window.location manipulation is blocked."""
        mock_agent_context_resolver.return_value.resolve_agent_for_request = AsyncMock(return_value=(
            autonomous_agent,
            {}
        ))

        result = await canvas_execute_javascript(
            user_id="user-123",
            canvas_id="canvas-abc",
            javascript="window.location='https://evil.com';",
            agent_id="autonomous-agent"
        )

        assert result["success"] is False
        assert "dangerous pattern" in result["error"]

    @pytest.mark.asyncio
    async def test_execute_javascript_timeout(self, mock_ws_manager, mock_agent_context_resolver, mock_service_factory, autonomous_agent):
        """Test setTimeout is blocked."""
        mock_agent_context_resolver.return_value.resolve_agent_for_request = AsyncMock(return_value=(
            autonomous_agent,
            {}
        ))

        result = await canvas_execute_javascript(
            user_id="user-123",
            canvas_id="canvas-abc",
            javascript="setTimeout(() => {}, 1000);",
            agent_id="autonomous-agent"
        )

        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_execute_javascript_with_session_isolation(self, mock_ws_manager, mock_agent_context_resolver, mock_service_factory, autonomous_agent):
        """Test JavaScript execution with session isolation."""
        mock_agent_context_resolver.return_value.resolve_agent_for_request = AsyncMock(return_value=(
            autonomous_agent,
            {}
        ))

        result = await canvas_execute_javascript(
            user_id="user-123",
            canvas_id="canvas-abc",
            javascript="document.title = 'Test';",
            agent_id="autonomous-agent",
            session_id="js-session"
        )

        assert result["success"] is True
        assert result["session_id"] == "js-session"

    @pytest.mark.asyncio
    async def test_execute_javascript_audit_entry(self, mock_ws_manager, mock_agent_context_resolver, mock_service_factory, autonomous_agent, mock_db):
        """Test JavaScript execution creates audit entry."""
        mock_agent_context_resolver.return_value.resolve_agent_for_request = AsyncMock(return_value=(
            autonomous_agent,
            {}
        ))

        with patch('tools.canvas_tool.get_db_session', return_value=mock_db):
            with patch('tools.canvas_tool._create_canvas_audit', new_callable=AsyncMock) as mock_audit:
                mock_audit.return_value = MagicMock(id="audit-js")

                await canvas_execute_javascript(
                    user_id="user-123",
                    canvas_id="canvas-abc",
                    javascript="document.title = 'Test';",
                    agent_id="autonomous-agent"
                )

                assert mock_audit.called
                call_kwargs = mock_audit.call_args[1]
                assert call_kwargs["component_type"] == "javascript_execution"
                assert call_kwargs["action"] == "execute"

    @pytest.mark.asyncio
    async def test_execute_javascript_audit_contains_code(self, mock_ws_manager, mock_agent_context_resolver, mock_service_factory, autonomous_agent, mock_db):
        """Test JavaScript code is stored in audit metadata."""
        mock_agent_context_resolver.return_value.resolve_agent_for_request = AsyncMock(return_value=(
            autonomous_agent,
            {}
        ))

        with patch('tools.canvas_tool.get_db_session', return_value=mock_db):
            with patch('tools.canvas_tool._create_canvas_audit', new_callable=AsyncMock) as mock_audit:
                mock_audit.return_value = MagicMock(id="audit-js")

                js_code = "document.title = 'Test';"
                await canvas_execute_javascript(
                    user_id="user-123",
                    canvas_id="canvas-abc",
                    javascript=js_code,
                    agent_id="autonomous-agent"
                )

                call_kwargs = mock_audit.call_args[1]
                assert call_kwargs["metadata"]["javascript"] == js_code

    @pytest.mark.asyncio
    async def test_execute_javascript_custom_timeout(self, mock_ws_manager, mock_agent_context_resolver, mock_service_factory, autonomous_agent):
        """Test JavaScript execution with custom timeout."""
        mock_agent_context_resolver.return_value.resolve_agent_for_request = AsyncMock(return_value=(
            autonomous_agent,
            {}
        ))

        await canvas_execute_javascript(
            user_id="user-123",
            canvas_id="canvas-abc",
            javascript="document.title = 'Test';",
            agent_id="autonomous-agent",
            timeout_ms=10000
        )

        call_args = mock_ws_manager.broadcast.call_args[0][1]
        assert call_args["data"]["timeout_ms"] == 10000

    @pytest.mark.asyncio
    async def test_execute_javascript_error_handling(self, mock_agent_context_resolver, mock_service_factory, autonomous_agent):
        """Test JavaScript execution error handling."""
        mock_agent_context_resolver.return_value.resolve_agent_for_request = AsyncMock(return_value=(
            autonomous_agent,
            {}
        ))

        with patch('tools.canvas_tool.ws_manager') as mock_ws:
            mock_ws.broadcast = AsyncMock(side_effect=Exception("JS execution failed"))

            result = await canvas_execute_javascript(
                user_id="user-123",
                canvas_id="canvas-abc",
                javascript="document.title = 'Test';",
                agent_id="autonomous-agent"
            )

            assert result["success"] is False


# ============================================================================
# present_specialized_canvas() Tests (15 tests)
# ============================================================================

class TestPresentSpecializedCanvas:
    """Tests for present_specialized_canvas() function."""

    @pytest.mark.asyncio
    async def test_present_docs_canvas_success(self, mock_ws_manager, mock_agent_context_resolver, mock_service_factory):
        """Test presenting docs canvas successfully."""
        result = await present_specialized_canvas(
            user_id="user-123",
            canvas_type="docs",
            component_type="rich_editor",
            data={"content": "# Documentation\n\nAPI reference..."},
            title="API Docs"
        )

        assert result["success"] is True
        assert result["canvas_type"] == "docs"
        assert result["component_type"] == "rich_editor"

    @pytest.mark.asyncio
    async def test_present_email_canvas_success(self, mock_ws_manager, mock_agent_context_resolver, mock_service_factory):
        """Test presenting email canvas successfully."""
        result = await present_specialized_canvas(
            user_id="user-123",
            canvas_type="email",
            component_type="thread_view",
            data={"messages": [{"from": "a@b.com", "subject": "Test"}]},
            title="Inbox"
        )

        assert result["success"] is True
        assert result["canvas_type"] == "email"

    @pytest.mark.asyncio
    async def test_present_sheets_canvas_success(self, mock_ws_manager, mock_agent_context_resolver, mock_service_factory):
        """Test presenting sheets canvas successfully."""
        result = await present_specialized_canvas(
            user_id="user-123",
            canvas_type="sheets",
            component_type="data_grid",
            data={"cells": {"A1": "Name", "B1": "Value"}},
            layout="sheet"
        )

        assert result["success"] is True
        assert result["canvas_type"] == "sheets"

    @pytest.mark.asyncio
    async def test_present_invalid_canvas_type(self, mock_ws_manager, mock_agent_context_resolver, mock_service_factory):
        """Test invalid canvas type is rejected."""
        with patch('tools.canvas_tool.canvas_type_registry') as mock_registry:
            mock_registry.validate_canvas_type.return_value = False

            result = await present_specialized_canvas(
                user_id="user-123",
                canvas_type="invalid_type",
                component_type="any_component",
                data={}
            )

            assert result["success"] is False
            assert "Invalid canvas type" in result["error"]

    @pytest.mark.asyncio
    async def test_present_invalid_component_type(self, mock_ws_manager, mock_agent_context_resolver, mock_service_factory):
        """Test invalid component type is rejected."""
        with patch('tools.canvas_tool.canvas_type_registry') as mock_registry:
            mock_registry.validate_canvas_type.return_value = True
            mock_registry.validate_component.return_value = False

            result = await present_specialized_canvas(
                user_id="user-123",
                canvas_type="docs",
                component_type="invalid_component",
                data={}
            )

            assert result["success"] is False
            assert "not supported" in result["error"]

    @pytest.mark.asyncio
    async def test_present_invalid_layout(self, mock_ws_manager, mock_agent_context_resolver, mock_service_factory):
        """Test invalid layout is rejected."""
        with patch('tools.canvas_tool.canvas_type_registry') as mock_registry:
            mock_registry.validate_canvas_type.return_value = True
            mock_registry.validate_component.return_value = True
            mock_registry.validate_layout.return_value = False

            result = await present_specialized_canvas(
                user_id="user-123",
                canvas_type="sheets",
                component_type="data_grid",
                data={},
                layout="invalid_layout"
            )

            assert result["success"] is False
            assert "Layout" in result["error"]

    @pytest.mark.asyncio
    async def test_present_orchestration_canvas(self, mock_ws_manager, mock_agent_context_resolver, mock_service_factory):
        """Test presenting orchestration canvas."""
        result = await present_specialized_canvas(
            user_id="user-123",
            canvas_type="orchestration",
            component_type="kanban_board",
            data={"columns": ["Todo", "In Progress", "Done"]},
            layout="board"
        )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_present_terminal_canvas(self, mock_ws_manager, mock_agent_context_resolver, mock_service_factory):
        """Test presenting terminal canvas."""
        result = await present_specialized_canvas(
            user_id="user-123",
            canvas_type="terminal",
            component_type="command_output",
            data={"output": "Command completed successfully"}
        )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_present_coding_canvas(self, mock_ws_manager, mock_agent_context_resolver, mock_service_factory):
        """Test presenting coding canvas."""
        result = await present_specialized_canvas(
            user_id="user-123",
            canvas_type="coding",
            component_type="code_editor",
            data={"code": "function test() { return true; }", "language": "javascript"}
        )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_present_specialized_canvas_governance_allowed(self, mock_ws_manager, mock_agent_context_resolver, mock_service_factory, mock_governance_service):
        """Test specialized canvas with governance allowed."""
        result = await present_specialized_canvas(
            user_id="user-123",
            canvas_type="docs",
            component_type="rich_editor",
            data={},
            agent_id="agent-123"
        )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_present_specialized_canvas_governance_blocked(self, mock_ws_manager, mock_agent_context_resolver, mock_service_factory, student_agent, mock_governance_service):
        """Test specialized canvas with governance blocked."""
        mock_governance_service.can_perform_action.return_value = {
            "allowed": False,
            "reason": "Blocked"
        }
        mock_agent_context_resolver.return_value.resolve_agent_for_request = AsyncMock(return_value=(
            student_agent,
            {}
        ))

        result = await present_specialized_canvas(
            user_id="user-123",
            canvas_type="docs",
            component_type="rich_editor",
            data={},
            agent_id="student-agent"
        )

        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_present_specialized_canvas_maturity_check(self, mock_ws_manager, mock_agent_context_resolver, mock_service_factory):
        """Test maturity requirement is enforced."""
        with patch('tools.canvas_tool.canvas_type_registry') as mock_registry:
            mock_registry.validate_canvas_type.return_value = True
            mock_registry.validate_component.return_value = True
            mock_registry.get_min_maturity.return_value = MagicMock(value=3)  # SUPERVISED

            student_agent = MagicMock(spec=AgentRegistry)
            student_agent.id = "student-123"
            student_agent.status = AgentStatus.STUDENT.value
            student_agent.maturity_level = 0

            mock_agent_context_resolver.return_value.resolve_agent_for_request = AsyncMock(return_value=(
                student_agent,
                {}
            ))

            result = await present_specialized_canvas(
                user_id="user-123",
                canvas_type="orchestration",
                component_type="kanban_board",
                data={},
                agent_id="student-agent"
            )

            assert result["success"] is False
            assert "maturity" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_present_specialized_canvas_session_isolation(self, mock_ws_manager, mock_agent_context_resolver, mock_service_factory):
        """Test specialized canvas with session isolation."""
        with patch('tools.canvas_tool.canvas_type_registry') as mock_registry:
            mock_registry.validate_canvas_type.return_value = True
            mock_registry.validate_component.return_value = True

            result = await present_specialized_canvas(
                user_id="user-123",
                canvas_type="docs",
                component_type="rich_editor",
                data={},
                session_id="specialized-session"
            )

            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_present_specialized_canvas_audit_entry(self, mock_ws_manager, mock_agent_context_resolver, mock_service_factory, mock_db):
        """Test specialized canvas creates audit entry."""
        with patch('tools.canvas_tool.canvas_type_registry') as mock_registry:
            mock_registry.validate_canvas_type.return_value = True
            mock_registry.validate_component.return_value = True

            with patch('tools.canvas_tool.get_db_session', return_value=mock_db):
                with patch('tools.canvas_tool._create_canvas_audit', new_callable=AsyncMock) as mock_audit:
                    mock_audit.return_value = MagicMock(id="audit-special")

                    await present_specialized_canvas(
                        user_id="user-123",
                        canvas_type="docs",
                        component_type="rich_editor",
                        data={"content": "Test"},
                        agent_id="agent-123"
                    )

                    assert mock_audit.called
                    call_kwargs = mock_audit.call_args[1]
                    assert call_kwargs["canvas_type"] == "docs"
                    assert call_kwargs["component_type"] == "rich_editor"

    @pytest.mark.asyncio
    async def test_present_specialized_canvas_execution_tracking(self, mock_ws_manager, mock_agent_context_resolver, mock_service_factory, mock_db):
        """Test specialized canvas execution tracking."""
        with patch('tools.canvas_tool.canvas_type_registry') as mock_registry:
            mock_registry.validate_canvas_type.return_value = True
            mock_registry.validate_component.return_value = True

            with patch('tools.canvas_tool.get_db_session', return_value=mock_db):
                result = await present_specialized_canvas(
                    user_id="user-123",
                    canvas_type="docs",
                    component_type="rich_editor",
                    data={},
                    agent_id="agent-123"
                )

                assert "agent_id" in result
                assert mock_db.add.called

    @pytest.mark.asyncio
    async def test_present_specialized_canvas_error_handling(self, mock_agent_context_resolver, mock_service_factory):
        """Test specialized canvas error handling."""
        with patch('tools.canvas_tool.canvas_type_registry') as mock_registry:
            mock_registry.validate_canvas_type.return_value = True
            mock_registry.validate_component.return_value = True

            with patch('tools.canvas_tool.ws_manager') as mock_ws:
                mock_ws.broadcast = AsyncMock(side_effect=Exception("Specialized canvas failed"))

                result = await present_specialized_canvas(
                    user_id="user-123",
                    canvas_type="docs",
                    component_type="rich_editor",
                    data={}
                )

                assert result["success"] is False
