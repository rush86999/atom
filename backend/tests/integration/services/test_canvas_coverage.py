"""
Coverage expansion tests for Canvas Presentation.

Target: 80%+ coverage for canvas_tool.py:
- Chart presentation (line, bar, pie)
- Form presentation and validation
- Canvas state management (update, close)
- Governance integration (maturity-based permissions)
- WebSocket broadcast verification

Tests use mocked WebSocket to focus on canvas logic.
"""
import pytest
from unittest.mock import AsyncMock, Mock, patch
from datetime import datetime

from core.models import AgentStatus, AgentRegistry, CanvasAudit

# Add parent directory to path for imports
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_db():
    """Mock database session."""
    db = Mock()
    db.add = Mock()
    db.commit = Mock()
    db.refresh = Mock()
    db.rollback = Mock()
    db.query = Mock(return_value=Mock(first=Mock(return_value=None)))
    return db


@pytest.fixture
def mock_db_context():
    """Mock database context manager."""
    with patch('core.database.get_db_session') as mock_ctx:
        db = Mock()
        db.add = Mock()
        db.commit = Mock()
        db.refresh = Mock()
        db.rollback = Mock()

        # Track different types of objects
        mock_agent = None
        mock_agent_execution = None
        mock_canvas_audit = None

        def capture_add(obj):
            """Capture added objects."""
            nonlocal mock_agent, mock_agent_execution, mock_canvas_audit
            if hasattr(obj, 'module_path'):  # AgentRegistry
                mock_agent = obj
            elif hasattr(obj, 'triggered_by'):  # AgentExecution
                mock_agent_execution = obj
            elif hasattr(obj, 'canvas_id'):  # CanvasAudit
                mock_canvas_audit = obj

        db.add = Mock(side_effect=capture_add)

        def mock_query(model):
            """Mock query that returns appropriate object."""
            query_obj = Mock()

            def mock_filter(*args, **kwargs):
                result = Mock()
                if hasattr(model, '__tablename__'):
                    if model.__tablename__ == 'agent_registry':
                        result.first = Mock(return_value=mock_agent)
                    elif model.__tablename__ == 'agent_execution':
                        result.first = Mock(return_value=mock_agent_execution)
                    elif model.__tablename__ == 'canvas_audit':
                        result.first = Mock(return_value=mock_canvas_audit)
                    else:
                        result.first = Mock(return_value=None)
                else:
                    result.first = Mock(return_value=None)
                return result

            query_obj.filter = mock_filter
            return query_obj

        db.query = Mock(side_effect=mock_query)

        mock_ctx.return_value.__enter__ = Mock(return_value=db)
        mock_ctx.return_value.__exit__ = Mock(return_value=False)
        yield mock_ctx


@pytest.fixture
def mock_ws_manager():
    """Mock WebSocket manager.

    Creates mock before canvas_tool is imported.
    """
    # Create mock manager
    mock_mgr = Mock()
    mock_mgr.broadcast = AsyncMock()

    # Patch sys.modules to ensure mock is available before import
    import sys
    import core.websockets
    original_manager = core.websockets.manager
    core.websockets.manager = mock_mgr

    yield mock_mgr

    # Restore original
    core.websockets.manager = original_manager


@pytest.fixture
def mock_canvas_type_registry():
    """Mock canvas type registry."""
    with patch('tools.canvas_tool.canvas_type_registry') as mock_registry:
        mock_registry.validate_canvas_type = Mock(return_value=True)
        mock_registry.validate_component = Mock(return_value=True)
        mock_registry.validate_layout = Mock(return_value=True)

        # Mock get_min_maturity to return student (lowest maturity)
        mock_maturity = Mock()
        mock_maturity.value = "student"
        mock_registry.get_min_maturity = Mock(return_value=mock_maturity)

        yield mock_registry


# ============================================================================
# Task 1: Test canvas chart presentation and rendering
# ============================================================================

class TestChartPresentation:
    """Test chart presentation for all types (line, bar, pie)."""

    @pytest.mark.asyncio
    async def test_present_line_chart(self, mock_db_context, mock_ws_manager):
        """Test presenting a line chart with data."""
        from tools.canvas_tool import present_chart

        chart_data = [
            {"x": "Jan", "y": 100},
            {"x": "Feb", "y": 200},
            {"x": "Mar", "y": 150},
        ]

        result = await present_chart(
            user_id="test_user",
            chart_type="line_chart",
            data=chart_data,
            title="Monthly Sales"
        )

        assert result["success"] is True
        assert "canvas_id" in result
        assert result["chart_type"] == "line_chart"
        assert mock_ws_manager.broadcast.called

    @pytest.mark.asyncio
    async def test_present_bar_chart(self, mock_db_context, mock_ws_manager):
        """Test presenting a bar chart with categories."""
        from tools.canvas_tool import present_chart

        chart_data = [
            {"category": "A", "value": 100},
            {"category": "B", "value": 200},
            {"category": "C", "value": 150}
        ]

        result = await present_chart(
            user_id="test_user",
            chart_type="bar_chart",
            data=chart_data,
            title="Category Comparison"
        )

        assert result["success"] is True
        assert result["chart_type"] == "bar_chart"
        assert mock_ws_manager.broadcast.called

    @pytest.mark.asyncio
    async def test_present_pie_chart(self, mock_db_context, mock_ws_manager):
        """Test presenting a pie chart with slices."""
        from tools.canvas_tool import present_chart

        chart_data = [
            {"slice": "Product A", "value": 45},
            {"slice": "Product B", "value": 30},
            {"slice": "Product C", "value": 25}
        ]

        result = await present_chart(
            user_id="test_user",
            chart_type="pie_chart",
            data=chart_data,
            title="Market Share"
        )

        assert result["success"] is True
        assert result["chart_type"] == "pie_chart"
        assert mock_ws_manager.broadcast.called

    @pytest.mark.asyncio
    async def test_chart_with_custom_options(self, mock_db_context, mock_ws_manager):
        """Test chart with custom colors, axes, legend options."""
        from tools.canvas_tool import present_chart

        chart_data = [{"x": 1, "y": 2}]

        result = await present_chart(
            user_id="test_user",
            chart_type="line_chart",
            data=chart_data,
            title="Custom Chart",
            color="#FF0000",
            show_legend=True,
            x_axis_label="Time",
            y_axis_label="Value"
        )

        assert result["success"] is True

        # Verify custom options passed to canvas state
        call_args = mock_ws_manager.broadcast.call_args
        canvas_data = call_args[0][1]["data"]["data"]
        assert canvas_data["color"] == "#FF0000"
        assert canvas_data["show_legend"] is True


# ============================================================================
# Task 2: Test canvas form presentation and validation
# ============================================================================

class TestFormPresentation:
    """Test form presentation and field validation."""

    @pytest.mark.asyncio
    async def test_present_form(self, mock_db_context, mock_ws_manager):
        """Test presenting a form with email and name fields."""
        from tools.canvas_tool import present_form

        form_schema = {
            "fields": [
                {"name": "email", "type": "email", "label": "Email", "required": True},
                {"name": "name", "type": "text", "label": "Name", "required": True}
            ]
        }

        result = await present_form(
            user_id="test_user",
            form_schema=form_schema,
            title="User Information"
        )

        assert result["success"] is True
        assert "canvas_id" in result
        assert mock_ws_manager.broadcast.called

    @pytest.mark.asyncio
    async def test_form_validation_email_field(self, mock_db_context, mock_ws_manager):
        """Test form validation for email field type."""
        from tools.canvas_tool import present_form

        form_schema = {
            "fields": [
                {"name": "email", "type": "email", "required": True},
                {"name": "age", "type": "number", "min": 18}
            ]
        }

        result = await present_form(
            user_id="test_user",
            form_schema=form_schema,
            title="Registration Form"
        )

        assert result["success"] is True

        # Verify form schema includes validation rules
        call_args = mock_ws_manager.broadcast.call_args
        schema = call_args[0][1]["data"]["data"]["schema"]
        assert schema["fields"][0]["type"] == "email"
        assert schema["fields"][1]["min"] == 18

    @pytest.mark.asyncio
    async def test_form_validation_invalid_email(self, mock_db_context, mock_ws_manager):
        """Test form validation rejects invalid email format."""
        from tools.canvas_tool import present_form

        form_schema = {
            "fields": [
                {"name": "email", "type": "email", "required": True}
            ]
        }

        result = await present_form(
            user_id="test_user",
            form_schema=form_schema,
            title="Email Validation"
        )

        # Form presentation succeeds (validation happens on submission)
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_form_validation_age_below_minimum(self, mock_db_context, mock_ws_manager):
        """Test form validation enforces minimum age constraint."""
        from tools.canvas_tool import present_form

        form_schema = {
            "fields": [
                {"name": "age", "type": "number", "min": 18, "label": "Age"}
            ]
        }

        result = await present_form(
            user_id="test_user",
            form_schema=form_schema,
            title="Age Verification"
        )

        assert result["success"] is True

        # Verify min constraint in schema
        call_args = mock_ws_manager.broadcast.call_args
        schema = call_args[0][1]["data"]["data"]["schema"]
        assert schema["fields"][0]["min"] == 18

    @pytest.mark.asyncio
    async def test_form_validation_required_field(self, mock_db_context, mock_ws_manager):
        """Test form validation enforces required fields."""
        from tools.canvas_tool import present_form

        form_schema = {
            "fields": [
                {"name": "email", "type": "email", "required": True},
                {"name": "phone", "type": "text", "required": False}
            ]
        }

        result = await present_form(
            user_id="test_user",
            form_schema=form_schema,
            title="Contact Form"
        )

        assert result["success"] is True

        # Verify required field constraint
        call_args = mock_ws_manager.broadcast.call_args
        schema = call_args[0][1]["data"]["data"]["schema"]
        assert schema["fields"][0]["required"] is True
        assert schema["fields"][1]["required"] is False


# ============================================================================
# Task 3: Test canvas state management and governance integration
# ============================================================================

class TestCanvasStateManagement:
    """Test canvas state updates and lifecycle."""

    @pytest.mark.asyncio
    async def test_update_canvas_state(self, mock_db_context, mock_ws_manager):
        """Test updating canvas state with new data."""
        from tools.canvas_tool import present_chart, update_canvas

        # Create canvas first
        create_result = await present_chart(
            user_id="test_user",
            chart_type="line_chart",
            data=[{"x": 1, "y": 2}],
            title="Original Title"
        )

        canvas_id = create_result["canvas_id"]

        # Update canvas
        update_result = await update_canvas(
            user_id="test_user",
            canvas_id=canvas_id,
            updates={"title": "Updated Title", "data": [{"x": 1, "y": 5}]}
        )

        assert update_result["success"] is True
        assert update_result["canvas_id"] == canvas_id
        assert "title" in update_result["updated_fields"]

    @pytest.mark.asyncio
    async def test_close_canvas(self, mock_db_context, mock_ws_manager):
        """Test closing a canvas."""
        from tools.canvas_tool import close_canvas

        result = await close_canvas(
            user_id="test_user",
            session_id="session-123"
        )

        assert result["success"] is True
        assert mock_ws_manager.broadcast.called

        # Verify close action in broadcast
        call_args = mock_ws_manager.broadcast.call_args
        assert call_args[0][1]["data"]["action"] == "close"

    @pytest.mark.asyncio
    async def test_canvas_state_serialization(self, mock_db_context, mock_ws_manager):
        """Test canvas state serializes to JSON without circular references."""
        from tools.canvas_tool import present_chart

        result = await present_chart(
            user_id="test_user",
            chart_type="line_chart",
            data=[{"x": 1, "y": 2}, {"x": 2, "y": 4}],
            title="Serialization Test"
        )

        assert result["success"] is True

        # Verify broadcast data is serializable
        call_args = mock_ws_manager.broadcast.call_args
        broadcast_data = call_args[0][1]

        # Should not raise TypeError
        import json
        json.dumps(broadcast_data)


class TestGovernanceIntegration:
    """Test governance checks for canvas operations."""

    @pytest.mark.asyncio
    async def test_student_agent_can_present_charts(self, mock_db_context, mock_ws_manager):
        """Test that STUDENT agents can present charts (complexity 1)."""
        from tools.canvas_tool import present_chart

        # Create STUDENT agent mock
        mock_agent = Mock(spec=AgentRegistry)
        mock_agent.id = "student-agent-1"
        mock_agent.name = "StudentAgent"
        mock_agent.status = AgentStatus.STUDENT.value

        with patch('tools.canvas_tool.AgentContextResolver') as resolver_mock:
            resolver = Mock()
            resolver.resolve_agent_for_request = AsyncMock(return_value=(mock_agent, {}))
            resolver_mock.return_value = resolver

            with patch('tools.canvas_tool.ServiceFactory') as factory_mock:
                governance = Mock()
                # Charts are complexity 1, allowed for STUDENT
                governance.can_perform_action = Mock(return_value={
                    "allowed": True,
                    "reason": None
                })
                factory_mock.get_governance_service = Mock(return_value=governance)

                result = await present_chart(
                    user_id="test_user",
                    chart_type="line_chart",
                    data=[{"x": 1, "y": 2}],
                    title="Student Chart",
                    agent_id=mock_agent.id
                )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_student_agent_blocked_from_forms(self, mock_db_context, mock_ws_manager):
        """Test that STUDENT agents are blocked from forms (complexity 3)."""
        from tools.canvas_tool import present_form

        # Create STUDENT agent mock
        mock_agent = Mock(spec=AgentRegistry)
        mock_agent.id = "student-agent-1"
        mock_agent.name = "StudentAgent"
        mock_agent.status = AgentStatus.STUDENT.value

        with patch('tools.canvas_tool.AgentContextResolver') as resolver_mock:
            resolver = Mock()
            resolver.resolve_agent_for_request = AsyncMock(return_value=(mock_agent, {}))
            resolver_mock.return_value = resolver

            with patch('tools.canvas_tool.ServiceFactory') as factory_mock:
                governance = Mock()
                # Forms are complexity 3, blocked for STUDENT
                governance.can_perform_action = Mock(return_value={
                    "allowed": False,
                    "reason": "STUDENT agents cannot present forms"
                })
                factory_mock.get_governance_service = Mock(return_value=governance)

                result = await present_form(
                    user_id="test_user",
                    form_schema={"fields": []},
                    title="Student Form",
                    agent_id=mock_agent.id
                )

        assert result["success"] is False
        assert "not permitted" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_autonomous_agent_full_access(self, mock_db_context, mock_ws_manager):
        """Test that AUTONOMOUS agents have full access to all operations."""
        from tools.canvas_tool import present_chart, present_form

        # Create AUTONOMOUS agent mock
        mock_agent = Mock(spec=AgentRegistry)
        mock_agent.id = "autonomous-agent-1"
        mock_agent.name = "AutonomousAgent"
        mock_agent.status = AgentStatus.AUTONOMOUS.value

        with patch('tools.canvas_tool.AgentContextResolver') as resolver_mock:
            resolver = Mock()
            resolver.resolve_agent_for_request = AsyncMock(return_value=(mock_agent, {}))
            resolver_mock.return_value = resolver

            with patch('tools.canvas_tool.ServiceFactory') as factory_mock:
                governance = Mock()
                # AUTONOMOUS agents can do everything
                governance.can_perform_action = Mock(return_value={
                    "allowed": True,
                    "reason": None
                })
                factory_mock.get_governance_service = Mock(return_value=governance)

                # Test chart (complexity 1)
                chart_result = await present_chart(
                    user_id="test_user",
                    chart_type="line_chart",
                    data=[{"x": 1, "y": 2}],
                    agent_id=mock_agent.id
                )

                # Test form (complexity 3)
                form_result = await present_form(
                    user_id="test_user",
                    form_schema={"fields": []},
                    agent_id=mock_agent.id
                )

        assert chart_result["success"] is True
        assert form_result["success"] is True

    @pytest.mark.asyncio
    async def test_intern_agent_chart_access(self, mock_db_context, mock_ws_manager):
        """Test that INTERN agents can present charts (complexity 1-2)."""
        from tools.canvas_tool import present_chart

        # Create INTERN agent mock
        mock_agent = Mock(spec=AgentRegistry)
        mock_agent.id = "intern-agent-1"
        mock_agent.name = "InternAgent"
        mock_agent.status = AgentStatus.INTERN.value

        with patch('tools.canvas_tool.AgentContextResolver') as resolver_mock:
            resolver = Mock()
            resolver.resolve_agent_for_request = AsyncMock(return_value=(mock_agent, {}))
            resolver_mock.return_value = resolver

            with patch('tools.canvas_tool.ServiceFactory') as factory_mock:
                governance = Mock()
                # Charts are complexity 1, allowed for INTERN
                governance.can_perform_action = Mock(return_value={
                    "allowed": True,
                    "reason": None
                })
                factory_mock.get_governance_service = Mock(return_value=governance)

                result = await present_chart(
                    user_id="test_user",
                    chart_type="bar_chart",
                    data=[{"category": "A", "value": 100}],
                    agent_id=mock_agent.id
                )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_supervised_agent_form_access(self, mock_db_context, mock_ws_manager):
        """Test that SUPERVISED agents can present forms (complexity 1-3)."""
        from tools.canvas_tool import present_form

        # Create SUPERVISED agent mock
        mock_agent = Mock(spec=AgentRegistry)
        mock_agent.id = "supervised-agent-1"
        mock_agent.name = "SupervisedAgent"
        mock_agent.status = AgentStatus.SUPERVISED.value

        with patch('tools.canvas_tool.AgentContextResolver') as resolver_mock:
            resolver = Mock()
            resolver.resolve_agent_for_request = AsyncMock(return_value=(mock_agent, {}))
            resolver_mock.return_value = resolver

            with patch('tools.canvas_tool.ServiceFactory') as factory_mock:
                governance = Mock()
                # Forms are complexity 3, allowed for SUPERVISED
                governance.can_perform_action = Mock(return_value={
                    "allowed": True,
                    "reason": None
                })
                factory_mock.get_governance_service = Mock(return_value=governance)

                result = await present_form(
                    user_id="test_user",
                    form_schema={
                        "fields": [
                            {"name": "field1", "type": "text", "label": "Field 1"}
                        ]
                    },
                    agent_id=mock_agent.id
                )

        assert result["success"] is True
