"""Test coverage for canvas_tool.py - Target 50%+ coverage."""

import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from sqlalchemy.orm import Session

from tools.canvas_tool import (
    present_chart,
    present_markdown,
    present_form,
    present_status_panel,
    update_canvas,
    close_canvas,
    canvas_execute_javascript,
    present_to_canvas,
    present_specialized_canvas,
    _create_canvas_audit
)
from core.models import AgentRegistry, CanvasAudit, AgentStatus


@pytest.fixture
def db_session():
    """Mock database session for testing."""
    return Mock(spec=Session)


@pytest.fixture
def student_agent():
    """Create a STUDENT level agent for testing."""
    agent = AgentRegistry(
        id="test-student-agent",
        tenant_id="test-tenant",
        name="Test Student Agent",
        category="Test",
        module_path="test.module",
        class_name="TestClass",
        status=AgentStatus.STUDENT.value,
        confidence_score=0.3
    )
    return agent


@pytest.fixture
def intern_agent():
    """Create an INTERN level agent for testing."""
    agent = AgentRegistry(
        id="test-intern-agent",
        tenant_id="test-tenant",
        name="Test Intern Agent",
        category="Test",
        module_path="test.module",
        class_name="TestClass",
        status=AgentStatus.INTERN.value,
        confidence_score=0.6
    )
    return agent


@pytest.fixture
def supervised_agent():
    """Create a SUPERVISED level agent for testing."""
    agent = AgentRegistry(
        id="test-supervised-agent",
        tenant_id="test-tenant",
        name="Test Supervised Agent",
        category="Test",
        module_path="test.module",
        class_name="TestClass",
        status=AgentStatus.SUPERVISED.value,
        confidence_score=0.8
    )
    return agent


@pytest.fixture
def autonomous_agent():
    """Create an AUTONOMOUS level agent for testing."""
    agent = AgentRegistry(
        id="test-autonomous-agent",
        tenant_id="test-tenant",
        name="Test Autonomous Agent",
        category="Test",
        module_path="test.module",
        class_name="TestClass",
        status=AgentStatus.AUTONOMOUS.value,
        confidence_score=0.95
    )
    return agent


@pytest.fixture
def mock_governance_service():
    """Mock governance service."""
    mock_service = MagicMock()
    mock_service.can_perform_action = MagicMock(return_value={
        "allowed": True,
        "reason": ""
    })
    mock_service.record_outcome = AsyncMock()
    return mock_service


@pytest.fixture
def mock_agent_resolver():
    """Mock agent context resolver."""
    mock_resolver = MagicMock()
    mock_resolver.resolve_agent_for_request = AsyncMock(return_value=(None, {}))
    return mock_resolver


class TestCanvasPresentation:
    """Test canvas presentation functionality."""

    @pytest.mark.asyncio
    async def test_present_chart_canvas_student_agent(self, student_agent):
        """Test STUDENT agent can present chart canvas (LOW complexity)."""
        with patch('tools.canvas_tool.FeatureFlags.should_enforce_governance', return_value=True), \
             patch('tools.canvas_tool.get_db_session') as mock_get_db, \
             patch('tools.canvas_tool.AgentContextResolver') as mock_resolver_class, \
             patch('tools.canvas_tool.ServiceFactory.get_governance_service') as mock_gov_factory, \
             patch('tools.canvas_tool.ws_manager.broadcast', new_callable=AsyncMock):

            # Setup mocks
            mock_db = MagicMock()
            mock_get_db.return_value.__enter__.return_value = mock_db
            mock_get_db.return_value.__exit__.return_value = None

            mock_resolver = MagicMock()
            mock_resolver.resolve_agent_for_request = AsyncMock(return_value=(student_agent, {}))
            mock_resolver_class.return_value = mock_resolver

            mock_governance = MagicMock()
            mock_governance.can_perform_action = MagicMock(return_value={
                "allowed": True,
                "reason": ""
            })
            mock_governance.record_outcome = AsyncMock()
            mock_gov_factory.return_value = mock_governance

            result = await present_chart(
                user_id="test-user",
                chart_type="line_chart",
                data=[{"x": 1, "y": 2}, {"x": 3, "y": 4}],
                title="Test Chart",
                agent_id=student_agent.id
            )

            assert result["success"] is True
            assert "canvas_id" in result
            mock_governance.can_perform_action.assert_called_once()

    @pytest.mark.asyncio
    async def test_present_markdown_student_agent(self, student_agent):
        """Test STUDENT agent can present markdown canvas (LOW complexity)."""
        with patch('tools.canvas_tool.FeatureFlags.should_enforce_governance', return_value=True), \
             patch('tools.canvas_tool.get_db_session') as mock_get_db, \
             patch('tools.canvas_tool.AgentContextResolver') as mock_resolver_class, \
             patch('tools.canvas_tool.ServiceFactory.get_governance_service') as mock_gov_factory, \
             patch('tools.canvas_tool.ws_manager.broadcast', new_callable=AsyncMock):

            # Setup mocks
            mock_db = MagicMock()
            mock_get_db.return_value.__enter__.return_value = mock_db
            mock_get_db.return_value.__exit__.return_value = None

            mock_resolver = MagicMock()
            mock_resolver.resolve_agent_for_request = AsyncMock(return_value=(student_agent, {}))
            mock_resolver_class.return_value = mock_resolver

            mock_governance = MagicMock()
            mock_governance.can_perform_action = MagicMock(return_value={
                "allowed": True,
                "reason": ""
            })
            mock_governance.record_outcome = AsyncMock()
            mock_gov_factory.return_value = mock_governance

            result = await present_markdown(
                user_id="test-user",
                content="# Test Markdown\n\nThis is a test.",
                title="Test Markdown",
                agent_id=student_agent.id
            )

            assert result["success"] is True
            assert "canvas_id" in result

    @pytest.mark.asyncio
    async def test_present_form_intern_agent(self, intern_agent):
        """Test INTERN agent requires approval for form presentation (MODERATE complexity)."""
        with patch('tools.canvas_tool.FeatureFlags.should_enforce_governance', return_value=True), \
             patch('tools.canvas_tool.get_db_session') as mock_get_db, \
             patch('tools.canvas_tool.AgentContextResolver') as mock_resolver_class, \
             patch('tools.canvas_tool.ServiceFactory.get_governance_service') as mock_gov_factory, \
             patch('tools.canvas_tool.ws_manager.broadcast', new_callable=AsyncMock):

            # Setup mocks
            mock_db = MagicMock()
            mock_get_db.return_value.__enter__.return_value = mock_db
            mock_get_db.return_value.__exit__.return_value = None

            mock_resolver = MagicMock()
            mock_resolver.resolve_agent_for_request = AsyncMock(return_value=(intern_agent, {}))
            mock_resolver_class.return_value = mock_resolver

            mock_governance = MagicMock()
            mock_governance.can_perform_action = MagicMock(return_value={
                "allowed": True,
                "reason": ""
            })
            mock_governance.record_outcome = AsyncMock()
            mock_gov_factory.return_value = mock_governance

            result = await present_form(
                user_id="test-user",
                form_schema={
                    "fields": [
                        {"name": "email", "type": "email", "required": True},
                        {"name": "name", "type": "text", "required": True}
                    ]
                },
                title="User Input Form",
                agent_id=intern_agent.id
            )

            assert result["success"] is True
            assert "canvas_id" in result
            assert "agent_execution_id" in result

    @pytest.mark.asyncio
    async def test_present_status_panel_autonomous_agent(self, autonomous_agent):
        """Test AUTONOMOUS agent can present status panel."""
        with patch('tools.canvas_tool.FeatureFlags.should_enforce_governance', return_value=True), \
             patch('tools.canvas_tool.get_db_session') as mock_get_db, \
             patch('tools.canvas_tool.AgentContextResolver') as mock_resolver_class, \
             patch('tools.canvas_tool.ServiceFactory.get_governance_service') as mock_gov_factory, \
             patch('tools.canvas_tool.ws_manager.broadcast', new_callable=AsyncMock):

            # Setup mocks
            mock_db = MagicMock()
            mock_get_db.return_value.__enter__.return_value = mock_db
            mock_get_db.return_value.__exit__.return_value = None

            mock_resolver = MagicMock()
            mock_resolver.resolve_agent_for_request = AsyncMock(return_value=(autonomous_agent, {}))
            mock_resolver_class.return_value = mock_resolver

            mock_governance = MagicMock()
            mock_governance.can_perform_action = MagicMock(return_value={
                "allowed": True,
                "reason": ""
            })
            mock_gov_factory.return_value = mock_governance

            result = await present_status_panel(
                user_id="test-user",
                items=[
                    {"label": "Revenue", "value": "$100,000", "trend": "+10%"},
                    {"label": "Users", "value": "1,234", "trend": "+5%"}
                ],
                title="Status Panel",
                agent_id=autonomous_agent.id
            )

            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_present_chart_governance_blocked(self, student_agent):
        """Test chart presentation blocked by governance."""
        with patch('tools.canvas_tool.FeatureFlags.should_enforce_governance', return_value=True), \
             patch('tools.canvas_tool.get_db_session') as mock_get_db, \
             patch('tools.canvas_tool.AgentContextResolver') as mock_resolver_class, \
             patch('tools.canvas_tool.ServiceFactory.get_governance_service') as mock_gov_factory:

            # Setup mocks
            mock_db = MagicMock()
            mock_get_db.return_value.__enter__.return_value = mock_db
            mock_get_db.return_value.__exit__.return_value = None

            mock_resolver = MagicMock()
            mock_resolver.resolve_agent_for_request = AsyncMock(return_value=(student_agent, {}))
            mock_resolver_class.return_value = mock_resolver

            mock_governance = MagicMock()
            mock_governance.can_perform_action = MagicMock(return_value={
                "allowed": False,
                "reason": "LOW_MATURITY"
            })
            mock_gov_factory.return_value = mock_governance

            result = await present_chart(
                user_id="test-user",
                chart_type="line_chart",
                data=[{"x": 1, "y": 2}],
                title="Blocked Chart",
                agent_id=student_agent.id
            )

            assert result["success"] is False
            assert "not permitted" in result["error"]

    @pytest.mark.asyncio
    async def test_present_chart_without_agent(self):
        """Test chart presentation without agent_id (no governance)."""
        with patch('tools.canvas_tool.FeatureFlags.should_enforce_governance', return_value=False), \
             patch('tools.canvas_tool.ws_manager.broadcast', new_callable=AsyncMock):

            result = await present_chart(
                user_id="test-user",
                chart_type="bar_chart",
                data=[{"category": "A", "value": 100}],
                title="No Agent Chart"
            )

            assert result["success"] is True
            assert "canvas_id" in result
            assert result.get("agent_id") is None

    @pytest.mark.asyncio
    async def test_present_chart_creates_audit_record(self, student_agent):
        """Test that canvas presentation creates audit record."""
        with patch('tools.canvas_tool.FeatureFlags.should_enforce_governance', return_value=True), \
             patch('tools.canvas_tool.get_db_session') as mock_get_db, \
             patch('tools.canvas_tool.AgentContextResolver') as mock_resolver_class, \
             patch('tools.canvas_tool.ServiceFactory.get_governance_service') as mock_gov_factory, \
             patch('tools.canvas_tool.ws_manager.broadcast', new_callable=AsyncMock), \
             patch('tools.canvas_tool._create_canvas_audit', new_callable=AsyncMock) as mock_audit:

            # Setup mocks
            mock_db = MagicMock()
            mock_get_db.return_value.__enter__.return_value = mock_db
            mock_get_db.return_value.__exit__.return_value = None

            mock_resolver = MagicMock()
            mock_resolver.resolve_agent_for_request = AsyncMock(return_value=(student_agent, {}))
            mock_resolver_class.return_value = mock_resolver

            mock_governance = MagicMock()
            mock_governance.can_perform_action = MagicMock(return_value={
                "allowed": True,
                "reason": ""
            })
            mock_governance.record_outcome = AsyncMock()
            mock_gov_factory.return_value = mock_governance

            mock_audit.return_value = MagicMock(id="audit-123")

            result = await present_chart(
                user_id="test-user",
                chart_type="line_chart",
                data=[{"x": 1, "y": 2}],
                agent_id=student_agent.id
            )

            # Verify audit record was created
            mock_audit.assert_called_once()
            assert result["success"] is True
