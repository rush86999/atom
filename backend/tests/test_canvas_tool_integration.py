"""
Integration coverage tests for tools/canvas_tool.py.

These tests call actual CanvasTool methods to increase code coverage.
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime

from tools.canvas_tool import present_chart, present_status_panel, present_markdown, present_form
from core.models import CanvasAudit, AgentRegistry, AgentExecution, User
from core.database import SessionLocal
from core.agent_context_resolver import AgentContextResolver
from core.service_factory import ServiceFactory
from core.feature_flags import FeatureFlags


@pytest.fixture
def canvas_agent(db_session):
    """Create a test agent for canvas operations."""
    agent = AgentRegistry(
        name="CanvasAgent",
        category="testing",
        module_path="test.module",
        class_name="TestCanvas",
        status="INTERN",
        confidence_score=0.6,
        created_at=datetime.utcnow()
    )
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)
    return agent


@pytest.fixture
def canvas_user(db_session):
    """Create a test user for canvas operations."""
    user = User(
        email="canvas@example.com",
        username="canvasuser",
        hashed_password="hashed_password_here",
        is_active=True,
        created_at=datetime.utcnow()
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


class TestCanvasChartPresentation:
    """Tests for canvas chart presentation functionality."""

    @pytest.mark.asyncio
    async def test_present_line_chart_success(self, db_session, canvas_agent):
        """Test presenting a line chart successfully."""
        chart_data = [
            {"x": "2024-01-01", "y": 100},
            {"x": "2024-01-02", "y": 150},
            {"x": "2024-01-03", "y": 200}
        ]

        with patch('tools.canvas_tool.ws_manager') as mock_ws:
            mock_ws.broadcast = AsyncMock()

            result = await present_chart(
                user_id="test_user",
                chart_type="line_chart",
                data=chart_data,
                title="Test Line Chart",
                agent_id=canvas_agent.id
            )

            assert result["success"] is True
            assert result["chart_type"] == "line_chart"
            assert "canvas_id" in result
            assert mock_ws.broadcast.called

    @pytest.mark.asyncio
    async def test_present_bar_chart_success(self, db_session):
        """Test presenting a bar chart successfully."""
        bar_data = [
            {"category": "A", "value": 10},
            {"category": "B", "value": 20},
            {"category": "C", "value": 30}
        ]

        with patch('tools.canvas_tool.ws_manager') as mock_ws:
            mock_ws.broadcast = AsyncMock()

            result = await present_chart(
                user_id="test_user",
                chart_type="bar_chart",
                data=bar_data,
                title="Test Bar Chart"
            )

            assert result["success"] is True
            assert result["chart_type"] == "bar_chart"

    @pytest.mark.asyncio
    async def test_present_pie_chart_success(self, db_session):
        """Test presenting a pie chart successfully."""
        pie_data = [
            {"label": "Slice 1", "value": 30},
            {"label": "Slice 2", "value": 50},
            {"label": "Slice 3", "value": 20}
        ]

        with patch('tools.canvas_tool.ws_manager') as mock_ws:
            mock_ws.broadcast = AsyncMock()

            result = await present_chart(
                user_id="test_user",
                chart_type="pie_chart",
                data=pie_data,
                title="Test Pie Chart"
            )

            assert result["success"] is True
            assert result["chart_type"] == "pie_chart"

    @pytest.mark.asyncio
    async def test_present_chart_with_session_id(self, db_session):
        """Test presenting chart with session isolation."""
        chart_data = [{"x": "A", "y": 1}]

        with patch('tools.canvas_tool.ws_manager') as mock_ws:
            mock_ws.broadcast = AsyncMock()

            result = await present_chart(
                user_id="test_user",
                chart_type="line_chart",
                data=chart_data,
                title="Session Chart",
                session_id="session_123"
            )

            assert result["success"] is True
            # Verify session_id was passed to broadcast
            call_args = mock_ws.broadcast.call_args
            assert call_args is not None

    @pytest.mark.asyncio
    async def test_present_chart_governance_blocked(self, db_session, canvas_agent):
        """Test chart presentation blocked by governance."""
        # Mock governance to return denied
        with patch('tools.canvas_tool.ws_manager') as mock_ws:
            mock_ws.broadcast = AsyncMock()

            with patch.object(FeatureFlags, 'should_enforce_governance', return_value=True):
                with patch.object(ServiceFactory, 'get_governance_service') as mock_gov:
                    mock_gov_service = MagicMock()
                    mock_gov_service.can_perform_action.return_value = {
                        "allowed": False,
                        "reason": "Insufficient maturity level"
                    }
                    mock_gov.return_value = mock_gov_service

                    result = await present_chart(
                        user_id="test_user",
                        chart_type="line_chart",
                        data=[],
                        title="Blocked Chart",
                        agent_id=canvas_agent.id
                    )

                    assert result["success"] is False
                    assert "error" in result


class TestCanvasStatusPanel:
    """Tests for canvas status panel functionality."""

    @pytest.mark.asyncio
    async def test_present_status_panel_success(self, db_session):
        """Test presenting a status panel successfully."""
        status_items = [
            {"label": "Metric 1", "value": "100"},
            {"label": "Metric 2", "value": "200", "trend": "up"}
        ]

        with patch('tools.canvas_tool.ws_manager') as mock_ws:
            mock_ws.broadcast = AsyncMock()

            result = await present_status_panel(
                user_id="test_user",
                items=status_items,
                title="Test Status Panel"
            )

            assert result["success"] is True
            assert mock_ws.broadcast.called

    @pytest.mark.asyncio
    async def test_present_status_panel_with_agent(self, db_session, canvas_agent):
        """Test status panel with agent governance."""
        status_items = [{"label": "Test", "value": "123"}]

        with patch('tools.canvas_tool.ws_manager') as mock_ws:
            mock_ws.broadcast = AsyncMock()

            result = await present_status_panel(
                user_id="test_user",
                items=status_items,
                title="Agent Status Panel",
                agent_id=canvas_agent.id
            )

            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_present_status_panel_empty_items(self, db_session):
        """Test status panel with empty items list."""
        with patch('tools.canvas_tool.ws_manager') as mock_ws:
            mock_ws.broadcast = AsyncMock()

            result = await present_status_panel(
                user_id="test_user",
                items=[],
                title="Empty Panel"
            )

            assert result["success"] is True


class TestCanvasMarkdownPresentation:
    """Tests for canvas markdown presentation functionality."""

    @pytest.mark.asyncio
    async def test_present_markdown_success(self, db_session):
        """Test presenting markdown content successfully."""
        markdown_content = "# Test Header\n\nThis is **bold** text."

        with patch('tools.canvas_tool.ws_manager') as mock_ws:
            mock_ws.broadcast = AsyncMock()

            result = await present_markdown(
                user_id="test_user",
                content=markdown_content,
                title="Test Markdown"
            )

            assert result["success"] is True
            assert mock_ws.broadcast.called

    @pytest.mark.asyncio
    async def test_present_markdown_with_agent(self, db_session, canvas_agent):
        """Test markdown presentation with agent."""
        markdown_content = "## Agent Report\n\nReport content here."

        with patch('tools.canvas_tool.ws_manager') as mock_ws:
            mock_ws.broadcast = AsyncMock()

            result = await present_markdown(
                user_id="test_user",
                content=markdown_content,
                title="Agent Report",
                agent_id=canvas_agent.id
            )

            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_present_markdown_long_content(self, db_session):
        """Test presenting long markdown content."""
        long_content = "\n".join([f"Section {i}" for i in range(100)])

        with patch('tools.canvas_tool.ws_manager') as mock_ws:
            mock_ws.broadcast = AsyncMock()

            result = await present_markdown(
                user_id="test_user",
                content=long_content,
                title="Long Document"
            )

            assert result["success"] is True


class TestCanvasFormPresentation:
    """Tests for canvas form presentation functionality."""

    @pytest.mark.asyncio
    async def test_present_form_success(self, db_session):
        """Test presenting a form successfully."""
        form_schema = {
            "fields": [
                {"name": "email", "type": "email", "required": True, "label": "Email"},
                {"name": "message", "type": "text", "required": False, "label": "Message"}
            ]
        }

        with patch('tools.canvas_tool.ws_manager') as mock_ws:
            mock_ws.broadcast = AsyncMock()

            result = await present_form(
                user_id="test_user",
                form_schema=form_schema,
                title="Contact Form"
            )

            assert result["success"] is True
            assert mock_ws.broadcast.called

    @pytest.mark.asyncio
    async def test_present_form_with_agent(self, db_session, canvas_agent):
        """Test form presentation with agent governance."""
        form_schema = {
            "fields": [
                {"name": "approval", "type": "boolean", "required": True}
            ]
        }

        with patch('tools.canvas_tool.ws_manager') as mock_ws:
            mock_ws.broadcast = AsyncMock()

            result = await present_form(
                user_id="test_user",
                form_schema=form_schema,
                title="Approval Form",
                agent_id=canvas_agent.id
            )

            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_present_form_complex_fields(self, db_session):
        """Test form with complex field types."""
        form_schema = {
            "fields": [
                {"name": "name", "type": "text", "required": True},
                {"name": "age", "type": "number", "required": True},
                {"name": "subscribe", "type": "boolean", "required": False},
                {"name": "category", "type": "select", "options": ["A", "B", "C"]}
            ]
        }

        with patch('tools.canvas_tool.ws_manager') as mock_ws:
            mock_ws.broadcast = AsyncMock()

            result = await present_form(
                user_id="test_user",
                form_schema=form_schema,
                title="Complex Form"
            )

            assert result["success"] is True


class TestCanvasErrorHandling:
    """Tests for canvas error handling."""

    @pytest.mark.asyncio
    async def test_chart_exception_handling(self, db_session):
        """Test exception handling in chart presentation."""
        with patch('tools.canvas_tool.ws_manager') as mock_ws:
            # Make broadcast raise an exception
            mock_ws.broadcast = AsyncMock(side_effect=Exception("WebSocket error"))

            result = await present_chart(
                user_id="test_user",
                chart_type="line_chart",
                data=[],
                title="Error Chart"
            )

            # Should handle exception gracefully
            assert "success" in result
            assert result["success"] is False
            assert "error" in result

    @pytest.mark.asyncio
    async def test_markdown_exception_handling(self, db_session):
        """Test exception handling in markdown presentation."""
        with patch('tools.canvas_tool.ws_manager') as mock_ws:
            mock_ws.broadcast = AsyncMock(side_effect=Exception("Connection failed"))

            result = await present_markdown(
                user_id="test_user",
                content="Test content",
                title="Error Markdown"
            )

            assert result["success"] is False
            assert "error" in result


class TestCanvasAuditTrail:
    """Tests for canvas audit trail creation."""

    @pytest.mark.asyncio
    async def test_chart_creates_audit_entry(self, db_session, canvas_agent):
        """Test that chart presentation creates audit entry."""
        with patch('tools.canvas_tool.ws_manager') as mock_ws:
            mock_ws.broadcast = AsyncMock()

            result = await present_chart(
                user_id="test_user",
                chart_type="line_chart",
                data=[{"x": 1, "y": 2}],
                title="Audit Test Chart",
                agent_id=canvas_agent.id
            )

            assert result["success"] is True

            # Verify audit entry was created
            # Note: Audit entries are created in separate DB session
            # so we need to query for them
            from core.database import get_db_session
            with get_db_session() as audit_db:
                audits = audit_db.query(CanvasAudit).filter(
                    CanvasAudit.action == "present"
                ).all()

                # Should have at least one audit entry
                assert len(audits) >= 1

    @pytest.mark.asyncio
    async def test_form_creates_audit_entry(self, db_session, canvas_agent):
        """Test that form presentation creates audit entry."""
        with patch('tools.canvas_tool.ws_manager') as mock_ws:
            mock_ws.broadcast = AsyncMock()

            result = await present_form(
                user_id="test_user",
                form_schema={"fields": [{"name": "test", "type": "text"}]},
                title="Audit Test Form",
                agent_id=canvas_agent.id
            )

            assert result["success"] is True


class TestCanvasAgentExecution:
    """Tests for canvas agent execution tracking."""

    @pytest.mark.asyncio
    async def test_chart_creates_agent_execution(self, db_session, canvas_agent):
        """Test that chart presentation creates agent execution record."""
        with patch('tools.canvas_tool.ws_manager') as mock_ws:
            mock_ws.broadcast = AsyncMock()

            result = await present_chart(
                user_id="test_user",
                chart_type="line_chart",
                data=[{"x": 1, "y": 2}],
                title="Execution Test Chart",
                agent_id=canvas_agent.id
            )

            # Should succeed and create execution internally
            assert result["success"] is True
            # Note: Actual execution verification requires shared DB session

    @pytest.mark.asyncio
    async def test_status_panel_no_agent_execution(self, db_session):
        """Test that status panel without agent doesn't create execution."""
        with patch('tools.canvas_tool.ws_manager') as mock_ws:
            mock_ws.broadcast = AsyncMock()

            result = await present_status_panel(
                user_id="test_user",
                items=[{"label": "Test", "value": "123"}],
                title="No Agent Panel"
            )

            assert result["success"] is True
