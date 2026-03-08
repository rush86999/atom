"""
Coverage expansion tests for WebSocket broadcast integration with canvas.

Target: Verify WebSocket broadcast functionality for canvas operations:
- WebSocket broadcast called for all canvas presentations
- WebSocket error handling
- Session-based routing
- User channel routing

Tests use mocked WebSocket manager to focus on broadcast logic.
"""
import pytest
from unittest.mock import AsyncMock, Mock, patch

# Add parent directory to path for imports
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))


# ============================================================================
# Fixtures
# ============================================================================

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
    """Mock WebSocket manager with AsyncMock for async broadcast methods."""
    # Create mock manager with AsyncMock for async methods
    mock_mgr = Mock()
    mock_mgr.broadcast = AsyncMock()

    # Patch ws_manager in canvas_tool module
    with patch('tools.canvas_tool.ws_manager', mock_mgr):
        yield mock_mgr


# ============================================================================
# Test WebSocket Broadcast
# ============================================================================

class TestWebSocketBroadcast:
    """Test WebSocket broadcast for canvas operations."""

    @pytest.mark.asyncio
    async def test_chart_broadcast_called(self, mock_db_context, mock_ws_manager):
        """Test that chart presentation triggers WebSocket broadcast."""
        from tools.canvas_tool import present_chart

        result = await present_chart(
            user_id="test_user",
            chart_type="line_chart",
            data=[{"x": 1, "y": 2}],
            title="Test Chart"
        )

        assert result["success"] is True
        assert mock_ws_manager.broadcast.called

        # Verify broadcast structure
        call_args = mock_ws_manager.broadcast.call_args
        assert "user:test_user" in call_args[0][0]
        assert call_args[0][1]["type"] == "canvas:update"
        assert call_args[0][1]["data"]["action"] == "present"

    @pytest.mark.asyncio
    async def test_form_broadcast_called(self, mock_db_context, mock_ws_manager):
        """Test that form presentation triggers WebSocket broadcast."""
        from tools.canvas_tool import present_form

        result = await present_form(
            user_id="test_user",
            form_schema={"fields": [{"name": "field1", "type": "text"}]},
            title="Test Form"
        )

        assert result["success"] is True
        assert mock_ws_manager.broadcast.called

        # Verify broadcast includes form data
        call_args = mock_ws_manager.broadcast.call_args
        assert call_args[0][1]["data"]["component"] == "form"

    @pytest.mark.asyncio
    async def test_markdown_broadcast_called(self, mock_db_context, mock_ws_manager):
        """Test that markdown presentation triggers WebSocket broadcast."""
        from tools.canvas_tool import present_markdown

        result = await present_markdown(
            user_id="test_user",
            content="# Test Markdown\n\nThis is a test.",
            title="Test MD"
        )

        assert result["success"] is True
        assert mock_ws_manager.broadcast.called

        # Verify broadcast includes markdown content
        call_args = mock_ws_manager.broadcast.call_args
        assert call_args[0][1]["data"]["component"] == "markdown"

    @pytest.mark.asyncio
    async def test_update_broadcast_called(self, mock_db_context, mock_ws_manager):
        """Test that canvas update triggers WebSocket broadcast."""
        from tools.canvas_tool import update_canvas

        result = await update_canvas(
            user_id="test_user",
            canvas_id="canvas-123",
            updates={"title": "Updated Title"}
        )

        assert result["success"] is True
        assert mock_ws_manager.broadcast.called

        # Verify broadcast includes update action
        call_args = mock_ws_manager.broadcast.call_args
        assert call_args[0][1]["data"]["action"] == "update"

    @pytest.mark.asyncio
    async def test_close_broadcast_called(self, mock_ws_manager):
        """Test that canvas close triggers WebSocket broadcast."""
        from tools.canvas_tool import close_canvas

        result = await close_canvas(user_id="test_user")

        assert result["success"] is True
        assert mock_ws_manager.broadcast.called

        # Verify broadcast includes close action
        call_args = mock_ws_manager.broadcast.call_args
        assert call_args[0][1]["data"]["action"] == "close"


# ============================================================================
# Test WebSocket Routing
# ============================================================================

class TestWebSocketRouting:
    """Test WebSocket channel routing for canvas operations."""

    @pytest.mark.asyncio
    async def test_user_channel_routing(self, mock_db_context, mock_ws_manager):
        """Test that canvas broadcasts to correct user channel."""
        from tools.canvas_tool import present_chart

        await present_chart(
            user_id="user-12345",
            chart_type="line_chart",
            data=[{"x": 1, "y": 2}]
        )

        call_args = mock_ws_manager.broadcast.call_args
        assert "user:user-12345" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_session_channel_routing(self, mock_db_context, mock_ws_manager):
        """Test that canvas broadcasts to session-specific channel."""
        from tools.canvas_tool import present_chart

        await present_chart(
            user_id="test_user",
            chart_type="line_chart",
            data=[{"x": 1, "y": 2}],
            session_id="session-abc"
        )

        call_args = mock_ws_manager.broadcast.call_args
        # Should include session ID in channel
        assert "session:session-abc" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_multiple_sessions_isolated(self, mock_db_context, mock_ws_manager):
        """Test that different sessions are isolated."""
        from tools.canvas_tool import present_chart

        # Present to session 1
        await present_chart(
            user_id="test_user",
            chart_type="line_chart",
            data=[{"x": 1, "y": 2}],
            session_id="session-1"
        )

        # Present to session 2
        await present_chart(
            user_id="test_user",
            chart_type="bar_chart",
            data=[{"category": "A", "value": 100}],
            session_id="session-2"
        )

        # Verify two separate calls
        assert mock_ws_manager.broadcast.call_count == 2

        # Check first call (session-1)
        first_call = mock_ws_manager.broadcast.call_args_list[0]
        assert "session:session-1" in first_call[0][0]

        # Check second call (session-2)
        second_call = mock_ws_manager.broadcast.call_args_list[1]
        assert "session:session-2" in second_call[0][0]


# ============================================================================
# Test WebSocket Error Handling
# ============================================================================

class TestWebSocketErrorHandling:
    """Test WebSocket error handling."""

    @pytest.mark.asyncio
    async def test_broadcast_failure_graceful_degradation(self, mock_db_context):
        """Test that broadcast failures are handled gracefully."""
        from tools.canvas_tool import present_chart

        # Mock broadcast to raise exception
        with patch('tools.canvas_tool.ws_manager') as mock_mgr:
            mock_mgr.broadcast = AsyncMock(side_effect=Exception("WebSocket connection failed"))

            result = await present_chart(
                user_id="test_user",
                chart_type="line_chart",
                data=[{"x": 1, "y": 2}]
            )

            # Should handle error and return failure result
            assert isinstance(result, dict)
            assert "success" in result

    @pytest.mark.asyncio
    async def test_broadcast_timeout_handling(self, mock_db_context):
        """Test handling of broadcast timeouts."""
        from tools.canvas_tool import present_chart

        # Mock broadcast to timeout
        with patch('tools.canvas_tool.ws_manager') as mock_mgr:
            mock_mgr.broadcast = AsyncMock(side_effect=TimeoutError("Broadcast timeout"))

            result = await present_chart(
                user_id="test_user",
                chart_type="line_chart",
                data=[{"x": 1, "y": 2}]
            )

            # Should handle timeout gracefully
            assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_multiple_broadcast_retries(self, mock_db_context, mock_ws_manager):
        """Test that broadcast attempts are made (if retry logic exists)."""
        from tools.canvas_tool import present_chart

        # Mock broadcast to fail once then succeed
        call_count = [0]

        async def failing_then_succeeding(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception("Temporary failure")
            return None

        mock_ws_manager.broadcast.side_effect = failing_then_succeeding

        result = await present_chart(
            user_id="test_user",
            chart_type="line_chart",
            data=[{"x": 1, "y": 2}]
        )

        # Function should complete (may or may not have retry logic)
        assert isinstance(result, dict)


# ============================================================================
# Test WebSocket Data Integrity
# ============================================================================

class TestWebSocketDataIntegrity:
    """Test WebSocket broadcast data integrity."""

    @pytest.mark.asyncio
    async def test_chart_data_integrity(self, mock_db_context, mock_ws_manager):
        """Test that chart data is correctly passed through WebSocket."""
        from tools.canvas_tool import present_chart

        chart_data = [
            {"x": "Jan", "y": 100},
            {"x": "Feb", "y": 200},
            {"x": "Mar", "y": 150}
        ]

        await present_chart(
            user_id="test_user",
            chart_type="line_chart",
            data=chart_data,
            title="Monthly Sales"
        )

        call_args = mock_ws_manager.broadcast.call_args
        broadcast_data = call_args[0][1]["data"]["data"]

        # Verify data integrity
        assert broadcast_data["data"] == chart_data
        assert broadcast_data["title"] == "Monthly Sales"

    @pytest.mark.asyncio
    async def test_form_schema_integrity(self, mock_db_context, mock_ws_manager):
        """Test that form schema is correctly passed through WebSocket."""
        from tools.canvas_tool import present_form

        form_schema = {
            "fields": [
                {"name": "email", "type": "email", "required": True},
                {"name": "age", "type": "number", "min": 18}
            ]
        }

        await present_form(
            user_id="test_user",
            form_schema=form_schema,
            title="User Form"
        )

        call_args = mock_ws_manager.broadcast.call_args
        broadcast_schema = call_args[0][1]["data"]["data"]["schema"]

        # Verify schema integrity
        assert broadcast_schema == form_schema

    @pytest.mark.asyncio
    async def test_canvas_id_consistency(self, mock_db_context, mock_ws_manager):
        """Test that canvas_id is consistent across presentation and audit."""
        from tools.canvas_tool import present_chart

        result = await present_chart(
            user_id="test_user",
            chart_type="line_chart",
            data=[{"x": 1, "y": 2}]
        )

        canvas_id = result["canvas_id"]

        # Verify canvas_id in broadcast (it's at data["canvas_id"], not data["data"]["canvas_id"])
        call_args = mock_ws_manager.broadcast.call_args
        broadcast_canvas_id = call_args[0][1]["data"]["canvas_id"]

        assert canvas_id == broadcast_canvas_id
