"""
Integration tests for tools (canvas, browser, device).

Tests tool execution with mock dependencies while testing real tool logic.
Mock UI component rendering (WebSocket, frontend) to test core tool behavior.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.orm import Session

from tools.canvas_tool import (
    present_chart,
    present_markdown,
    present_form,
    present_status_panel,
    update_canvas,
    close_canvas
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_db_session():
    """Mock database session."""
    db = MagicMock(spec=Session)
    return db


@pytest.fixture
def mock_websocket_manager():
    """Mock WebSocket manager for canvas broadcast."""
    with patch("tools.canvas_tool.ws_manager") as mock_mgr:
        mock_mgr.broadcast = AsyncMock()
        yield mock_mgr


@pytest.fixture
def mock_governance_service():
    """Mock governance service."""
    with patch("tools.canvas_tool.ServiceFactory") as mock_factory:
        service = MagicMock()
        service.can_perform_action.return_value = {"allowed": True, "reason": ""}
        mock_factory.get_governance_service.return_value = service
        yield service


@pytest.fixture
def mock_agent_context():
    """Mock agent context resolver."""
    with patch("tools.canvas_tool.AgentContextResolver") as mock_resolver:
        agent = MagicMock()
        agent.id = "test-agent-id"
        agent.name = "TestAgent"
        agent.status = "autonomous"

        mock_resolver.return_value.resolve_agent_for_request = AsyncMock(
            return_value=(agent, {})
        )
        yield mock_resolver


# ============================================================================
# Canvas Chart Presentation Tests
# ============================================================================

@pytest.mark.integration
async def test_canvas_chart_presentation_success(
    mock_websocket_manager
):
    """Test canvas chart presentation succeeds with valid data."""
    with patch("tools.canvas_tool.FeatureFlags") as mock_flags:
        mock_flags.should_enforce_governance.return_value = False

        result = await present_chart(
            user_id="test-user",
            chart_type="line_chart",
            data=[{"x": 1, "y": 2}, {"x": 2, "y": 4}],
            title="Test Chart"
        )

        assert result["success"] == True
        assert result["chart_type"] == "line_chart"
        assert "canvas_id" in result
        assert mock_websocket_manager.broadcast.called


@pytest.mark.integration
@pytest.mark.parametrize("chart_type", [
    "line_chart",
    "bar_chart",
    "pie_chart",
    "scatter_chart"
])
async def test_canvas_chart_types(chart_type, mock_websocket_manager):
    """Parametrized test for all chart types."""
    # Disable governance for simple test
    with patch("tools.canvas_tool.FeatureFlags") as mock_flags:
        mock_flags.should_enforce_governance.return_value = False

        result = await present_chart(
            user_id="test-user",
            chart_type=chart_type,
            data=[{"x": 1, "y": 2}],
            title=f"{chart_type} Test"
        )

        assert result["success"] == True
        assert result["chart_type"] == chart_type
        assert mock_websocket_manager.broadcast.called


@pytest.mark.integration
async def test_canvas_chart_with_session_id(mock_websocket_manager):
    """Test canvas chart with session isolation."""
    with patch("tools.canvas_tool.FeatureFlags") as mock_flags:
        mock_flags.should_enforce_governance.return_value = False

        result = await present_chart(
            user_id="test-user",
            chart_type="line_chart",
            data=[{"x": 1, "y": 2}],
            title="Session Test",
            session_id="test-session-123"
        )

        assert result["success"] == True
        assert mock_websocket_manager.broadcast.called

        # Verify session-specific channel was used
        call_args = mock_websocket_manager.broadcast.call_args
        channel = call_args[0][0]
        assert "session:test-session-123" in channel


@pytest.mark.integration
async def test_canvas_chart_empty_data(mock_websocket_manager):
    """Test canvas chart handles empty data gracefully."""
    with patch("tools.canvas_tool.FeatureFlags") as mock_flags:
        mock_flags.should_enforce_governance.return_value = False

        result = await present_chart(
            user_id="test-user",
            chart_type="line_chart",
            data=[],
            title="Empty Data Test"
        )

        # Should still succeed - empty data is not an error
        assert result["success"] == True


# ============================================================================
# Canvas Markdown Presentation Tests
# ============================================================================

@pytest.mark.integration
async def test_canvas_markdown_presentation(mock_websocket_manager):
    """Test canvas markdown presentation."""
    with patch("tools.canvas_tool.FeatureFlags") as mock_flags:
        mock_flags.should_enforce_governance.return_value = False

        result = await present_markdown(
            user_id="test-user",
            content="# Test Markdown\n\nThis is **bold** text.",
            title="Test Document"
        )

        assert result["success"] == True
        assert "canvas_id" in result
        assert mock_websocket_manager.broadcast.called


@pytest.mark.integration
async def test_canvas_markdown_multiline(mock_websocket_manager):
    """Test canvas markdown with multiline content."""
    with patch("tools.canvas_tool.FeatureFlags") as mock_flags:
        mock_flags.should_enforce_governance.return_value = False

        long_content = """
# Heading 1

## Heading 2

- Item 1
- Item 2
- Item 3

```python
def hello():
    print("Hello, world!")
```
        """

        result = await present_markdown(
            user_id="test-user",
            content=long_content,
            title="Long Document"
        )

        assert result["success"] == True
        assert mock_websocket_manager.broadcast.called


@pytest.mark.integration
async def test_canvas_markdown_empty_content(mock_websocket_manager):
    """Test canvas markdown with empty content."""
    with patch("tools.canvas_tool.FeatureFlags") as mock_flags:
        mock_flags.should_enforce_governance.return_value = False

        result = await present_markdown(
            user_id="test-user",
            content="",
            title="Empty"
        )

        assert result["success"] == True


# ============================================================================
# Canvas Form Presentation Tests
# ============================================================================

@pytest.mark.integration
async def test_canvas_form_presentation(mock_websocket_manager):
    """Test canvas form presentation."""
    with patch("tools.canvas_tool.FeatureFlags") as mock_flags:
        mock_flags.should_enforce_governance.return_value = False

        form_schema = {
            "fields": [
                {"name": "email", "type": "email", "label": "Email", "required": True},
                {"name": "message", "type": "textarea", "label": "Message"}
            ],
            "validation": {
                "email": {"format": "email"}
            }
        }

        result = await present_form(
            user_id="test-user",
            form_schema=form_schema,
            title="Contact Form"
        )

        assert result["success"] == True
        assert "canvas_id" in result
        assert mock_websocket_manager.broadcast.called


@pytest.mark.integration
async def test_canvas_form_complex_schema(mock_websocket_manager):
    """Test canvas form with complex field types."""
    with patch("tools.canvas_tool.FeatureFlags") as mock_flags:
        mock_flags.should_enforce_governance.return_value = False

        form_schema = {
            "fields": [
                {"name": "name", "type": "text", "label": "Name"},
                {"name": "age", "type": "number", "label": "Age", "min": 0, "max": 120},
                {"name": "subscribe", "type": "checkbox", "label": "Subscribe"},
                {"name": "country", "type": "select", "label": "Country", "options": ["US", "UK", "CA"]}
            ]
        }

        result = await present_form(
            user_id="test-user",
            form_schema=form_schema,
            title="Complex Form"
        )

        assert result["success"] == True


# ============================================================================
# Canvas Status Panel Tests
# ============================================================================

@pytest.mark.integration
async def test_canvas_status_panel(mock_websocket_manager):
    """Test canvas status panel presentation."""
    with patch("tools.canvas_tool.FeatureFlags") as mock_flags:
        mock_flags.should_enforce_governance.return_value = False

        items = [
            {"label": "Total Users", "value": "1,234", "trend": "+12%"},
            {"label": "Revenue", "value": "$45,678", "trend": "+5%"},
            {"label": "Active Sessions", "value": "89"}
        ]

        result = await present_status_panel(
            user_id="test-user",
            items=items,
            title="Dashboard Metrics"
        )

        assert result["success"] == True
        assert mock_websocket_manager.broadcast.called


@pytest.mark.integration
async def test_canvas_status_panel_empty_items(mock_websocket_manager):
    """Test canvas status panel with no items."""
    with patch("tools.canvas_tool.FeatureFlags") as mock_flags:
        mock_flags.should_enforce_governance.return_value = False

        result = await present_status_panel(
            user_id="test-user",
            items=[],
            title="Empty Panel"
        )

        assert result["success"] == True


# ============================================================================
# Canvas Update Tests
# ============================================================================

@pytest.mark.integration
async def test_canvas_update_success(mock_websocket_manager):
    """Test canvas update with valid data."""
    with patch("tools.canvas_tool.FeatureFlags") as mock_flags:
        mock_flags.should_enforce_governance.return_value = False

        updates = {
            "data": [{"x": 1, "y": 10}, {"x": 2, "y": 20}],
            "title": "Updated Chart"
        }

        result = await update_canvas(
            user_id="test-user",
            canvas_id="canvas-123",
            updates=updates
        )

        assert result["success"] == True
        assert result["canvas_id"] == "canvas-123"
        assert result["updated_fields"] == ["data", "title"]


@pytest.mark.integration
async def test_canvas_update_with_session(mock_websocket_manager):
    """Test canvas update with session isolation."""
    with patch("tools.canvas_tool.FeatureFlags") as mock_flags:
        mock_flags.should_enforce_governance.return_value = False

        result = await update_canvas(
            user_id="test-user",
            canvas_id="canvas-123",
            updates={"title": "New Title"},
            session_id="session-456"
        )

        assert result["success"] == True
        assert result["session_id"] == "session-456"


@pytest.mark.integration
async def test_canvas_update_empty_updates(mock_websocket_manager):
    """Test canvas update with empty updates dict."""
    with patch("tools.canvas_tool.FeatureFlags") as mock_flags:
        mock_flags.should_enforce_governance.return_value = False

        result = await update_canvas(
            user_id="test-user",
            canvas_id="canvas-123",
            updates={}
        )

        assert result["success"] == True
        assert result["updated_fields"] == []


# ============================================================================
# Canvas Close Tests
# ============================================================================

@pytest.mark.integration
async def test_canvas_close_success(mock_websocket_manager):
    """Test canvas close succeeds."""
    result = await close_canvas(user_id="test-user")

    assert result["success"] == True
    assert mock_websocket_manager.broadcast.called


@pytest.mark.integration
async def test_canvas_close_with_session(mock_websocket_manager):
    """Test canvas close with session isolation."""
    result = await close_canvas(
        user_id="test-user",
        session_id="session-789"
    )

    assert result["success"] == True

    # Verify session-specific channel was used
    call_args = mock_websocket_manager.broadcast.call_args
    channel = call_args[0][0]
    assert "session:session-789" in channel


# ============================================================================
# Governance Blocking Tests
# ============================================================================

@pytest.mark.integration
async def test_canvas_governance_blocks_student_agent(mock_websocket_manager):
    """Test that STUDENT agents are blocked from canvas presentation."""
    with patch("tools.canvas_tool.FeatureFlags") as mock_flags:
        mock_flags.should_enforce_governance.return_value = True

        with patch("tools.canvas_tool.AgentContextResolver") as mock_resolver:
            agent = MagicMock()
            agent.id = "student-agent"
            agent.name = "StudentAgent"
            agent.status = "student"

            mock_resolver.return_value.resolve_agent_for_request = AsyncMock(
                return_value=(agent, {})
            )

            with patch("tools.canvas_tool.ServiceFactory") as mock_factory:
                service = MagicMock()
                service.can_perform_action.return_value = {
                    "allowed": False,
                    "reason": "STUDENT agents not permitted for canvas operations"
                }
                mock_factory.get_governance_service.return_value = service

                result = await present_chart(
                    user_id="test-user",
                    chart_type="line_chart",
                    data=[{"x": 1, "y": 2}],
                    title="Blocked Chart",
                    agent_id="student-agent"
                )

                assert result["success"] == False
                assert "not permitted" in result["error"]


# ============================================================================
# Error Handling Tests
# ============================================================================

@pytest.mark.integration
async def test_canvas_exception_handling():
    """Test canvas handles WebSocket exceptions gracefully."""
    with patch("tools.canvas_tool.ws_manager") as mock_mgr:
        # Make broadcast raise an exception
        mock_mgr.broadcast = AsyncMock(side_effect=Exception("WebSocket error"))

        with patch("tools.canvas_tool.FeatureFlags") as mock_flags:
            mock_flags.should_enforce_governance.return_value = False

            result = await present_chart(
                user_id="test-user",
                chart_type="line_chart",
                data=[{"x": 1, "y": 2}],
                title="Error Test"
            )

            assert result["success"] == False
            assert "error" in result
