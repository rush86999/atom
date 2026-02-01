"""
Deep Link System Tests

Comprehensive test suite for deep link functionality including:
- URL parsing and validation
- Agent/Workflow/Canvas/Tool deep link execution
- Governance checks
- Audit trail creation
- REST API endpoints
"""

import pytest
import uuid
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy.orm import Session

from core.deeplinks import (
    parse_deep_link,
    execute_deep_link,
    execute_agent_deep_link,
    execute_workflow_deep_link,
    execute_canvas_deep_link,
    execute_tool_deep_link,
    generate_deep_link,
    DeepLink,
    DeepLinkParseException,
    DeepLinkSecurityException
)
from core.models import (
    AgentRegistry,
    AgentExecution,
    DeepLinkAudit,
    BrowserSession
)
from core.database import SessionLocal


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def db():
    """Create a test database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def test_agent(db):
    """Create a test agent."""
    agent = AgentRegistry(
        id=f"test-agent-{uuid.uuid4()}",
        name="Test Agent",
        category="Operations",
        module_path="agents.test_agent",
        class_name="TestAgent",
        status="INTERN",
        confidence_score=0.7,
        capabilities=["stream_chat", "present_chart"]
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    yield agent
    # Cleanup
    db.query(AgentExecution).filter(AgentExecution.agent_id == agent.id).delete()
    db.query(DeepLinkAudit).filter(DeepLinkAudit.agent_id == agent.id).delete()
    db.delete(agent)
    db.commit()


@pytest.fixture
def autonomous_agent(db):
    """Create an autonomous test agent for JavaScript execution."""
    agent = AgentRegistry(
        id=f"autonomous-agent-{uuid.uuid4()}",
        name="Autonomous Agent",
        category="Operations",
        module_path="agents.autonomous_agent",
        class_name="AutonomousAgent",
        status="AUTONOMOUS",
        confidence_score=0.95,
        capabilities=["stream_chat", "canvas_execute_javascript"]
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    yield agent
    # Cleanup
    db.query(AgentExecution).filter(AgentExecution.agent_id == agent.id).delete()
    db.query(DeepLinkAudit).filter(DeepLinkAudit.agent_id == agent.id).delete()
    db.delete(agent)
    db.commit()


# ============================================================================
# parse_deep_link() Tests
# ============================================================================

class TestParseDeepLink:
    """Test deep link URL parsing."""

    def test_parse_agent_deep_link(self):
        """Test parsing agent deep link."""
        url = "atom://agent/agent-1?message=Hello&session=abc"
        link = parse_deep_link(url)

        assert isinstance(link, DeepLink)
        assert link.scheme == "atom"
        assert link.resource_type == "agent"
        assert link.resource_id == "agent-1"
        assert link.parameters["message"] == "Hello"
        assert link.parameters["session"] == "abc"

    def test_parse_workflow_deep_link(self):
        """Test parsing workflow deep link."""
        url = "atom://workflow/workflow-1?action=start"
        link = parse_deep_link(url)

        assert link.resource_type == "workflow"
        assert link.resource_id == "workflow-1"
        assert link.parameters["action"] == "start"

    def test_parse_canvas_deep_link(self):
        """Test parsing canvas deep link."""
        url = "atom://canvas/canvas-123?action=update"
        link = parse_deep_link(url)

        assert link.resource_type == "canvas"
        assert link.resource_id == "canvas-123"
        assert link.parameters["action"] == "update"

    def test_parse_tool_deep_link(self):
        """Test parsing tool deep link."""
        url = "atom://tool/present_chart"
        link = parse_deep_link(url)

        assert link.resource_type == "tool"
        assert link.resource_id == "present_chart"

    def test_parse_with_json_params(self):
        """Test parsing deep link with JSON parameters."""
        url = 'atom://canvas/canvas-123?action=update&params={"title":"New"}'
        link = parse_deep_link(url)

        assert link.parameters["action"] == "update"
        assert link.parameters["params"] == {"title": "New"}

    def test_parse_with_url_encoding(self):
        """Test parsing with URL-encoded values."""
        url = "atom://agent/agent-1?message=Hello%20World%21"
        link = parse_deep_link(url)

        assert link.parameters["message"] == "Hello World!"

    def test_parse_invalid_scheme(self):
        """Test parsing invalid scheme raises exception."""
        url = "https://agent/agent-1"

        with pytest.raises(DeepLinkParseException) as exc:
            parse_deep_link(url)

        assert "Invalid scheme" in str(exc.value)

    def test_parse_invalid_path_format(self):
        """Test parsing invalid path format raises exception."""
        url = "atom://agent"

        with pytest.raises(DeepLinkParseException) as exc:
            parse_deep_link(url)

        assert "Invalid path format" in str(exc.value)

    def test_parse_invalid_resource_type(self):
        """Test parsing invalid resource type raises exception."""
        url = "atom://invalid/resource-1"

        with pytest.raises(DeepLinkParseException) as exc:
            parse_deep_link(url)

        assert "Invalid resource type" in str(exc.value)

    def test_parse_invalid_resource_id(self):
        """Test parsing invalid resource ID raises security exception."""
        url = "atom://agent/agent-1../../../etc/passwd"

        with pytest.raises(DeepLinkSecurityException) as exc:
            parse_deep_link(url)

        assert "Invalid resource ID format" in str(exc.value)

    def test_parse_empty_url(self):
        """Test parsing empty URL raises exception."""
        with pytest.raises(DeepLinkParseException):
            parse_deep_link("")

    def test_parse_none_url(self):
        """Test parsing None URL raises exception."""
        with pytest.raises(DeepLinkParseException):
            parse_deep_link(None)


# ============================================================================
# execute_agent_deep_link() Tests
# ============================================================================

class TestExecuteAgentDeepLink:
    """Test agent deep link execution."""

    @pytest.mark.asyncio
    async def test_execute_agent_success(self, db, test_agent):
        """Test successful agent deep link execution."""
        link = parse_deep_link(f"atom://agent/{test_agent.id}?message=Hello")
        result = await execute_agent_deep_link(link, "user-1", db)

        assert result["success"] is True
        assert result["agent_id"] == test_agent.id
        assert result["agent_name"] == test_agent.name
        assert "execution_id" in result
        assert result["message"] == "Hello"

        # Verify execution record created
        execution = db.query(AgentExecution).filter(
            AgentExecution.agent_id == test_agent.id
        ).first()
        assert execution is not None
        assert execution.triggered_by == "deeplink"

        # Verify audit entry created
        audit = db.query(DeepLinkAudit).filter(
            DeepLinkAudit.agent_id == test_agent.id
        ).first()
        assert audit is not None
        assert audit.resource_type == "agent"
        assert audit.status == "success"

    @pytest.mark.asyncio
    async def test_execute_agent_not_found(self, db):
        """Test agent not found error."""
        link = parse_deep_link("atom://agent/nonexistent?message=Hello")
        result = await execute_agent_deep_link(link, "user-1", db)

        assert result["success"] is False
        assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_execute_agent_inactive(self, db):
        """Test inactive agent rejection."""
        # Create inactive agent
        agent = AgentRegistry(
            id=f"inactive-agent-{uuid.uuid4()}",
            name="Inactive Agent",
            category="Operations",
            module_path="agents.inactive",
            class_name="InactiveAgent",
            status="INACTIVE",  # Not active
            confidence_score=0.5,
            capabilities=[]
        )
        db.add(agent)
        db.commit()

        link = parse_deep_link(f"atom://agent/{agent.id}?message=Hello")
        result = await execute_agent_deep_link(link, "user-1", db)

        assert result["success"] is False
        assert "not active" in result["error"]

        # Cleanup
        db.delete(agent)
        db.commit()

    @pytest.mark.asyncio
    async def test_execute_agent_governance_check(self, db):
        """Test governance check blocks unauthorized actions."""
        # Create STUDENT agent (lowest maturity)
        agent = AgentRegistry(
            id=f"student-agent-{uuid.uuid4()}",
            name="Student Agent",
            category="Operations",
            module_path="agents.student",
            class_name="StudentAgent",
            status="STUDENT",
            confidence_score=0.3,
            capabilities=[]
        )
        db.add(agent)
        db.commit()

        # Mock governance to deny action
        with patch('core.deeplinks.AgentGovernanceService') as mock_gov:
            mock_instance = Mock()
            mock_instance.can_perform_action.return_value = {
                "allowed": False,
                "reason": "Agent maturity too low"
            }
            mock_gov.return_value = mock_instance

            link = parse_deep_link(f"atom://agent/{agent.id}?message=Hello")
            result = await execute_agent_deep_link(link, "user-1", db)

            assert result["success"] is False
            assert "not permitted" in result["error"]

        # Cleanup
        db.delete(agent)
        db.commit()

    @pytest.mark.asyncio
    async def test_execute_agent_with_session_id(self, db, test_agent):
        """Test agent execution with session ID."""
        link = parse_deep_link(f"atom://agent/{test_agent.id}?message=Hello&session=abc123")
        result = await execute_agent_deep_link(link, "user-1", db)

        assert result["success"] is True
        assert result["session_id"] == "abc123"


# ============================================================================
# execute_workflow_deep_link() Tests
# ============================================================================

class TestExecuteWorkflowDeepLink:
    """Test workflow deep link execution."""

    @pytest.mark.asyncio
    async def test_execute_workflow_success(self, db):
        """Test successful workflow deep link execution."""
        link = parse_deep_link("atom://workflow/workflow-1?action=start")
        result = await execute_workflow_deep_link(link, "user-1", db)

        assert result["success"] is True
        assert result["workflow_id"] == "workflow-1"
        assert result["action"] == "start"

        # Verify audit entry created
        audit = db.query(DeepLinkAudit).filter(
            DeepLinkAudit.resource_type == "workflow",
            DeepLinkAudit.resource_id == "workflow-1"
        ).first()
        assert audit is not None
        assert audit.status == "success"

    @pytest.mark.asyncio
    async def test_execute_workflow_with_params(self, db):
        """Test workflow execution with JSON parameters."""
        params = {"param1": "value1", "param2": 123}
        link = parse_deep_link(f'atom://workflow/workflow-2?action=run&params={params}')
        result = await execute_workflow_deep_link(link, "user-1", db)

        assert result["success"] is True
        assert result["params"] == params


# ============================================================================
# execute_canvas_deep_link() Tests
# ============================================================================

class TestExecuteCanvasDeepLink:
    """Test canvas deep link execution."""

    @pytest.mark.asyncio
    async def test_execute_canvas_update_success(self, db):
        """Test successful canvas update deep link execution."""
        # Mock the update_canvas function
        with patch('core.deeplinks.update_canvas') as mock_update:
            mock_update.return_value = {"success": True}

            link = parse_deep_link("atom://canvas/canvas-123?action=update")
            result = await execute_canvas_deep_link(link, "user-1", db)

            assert result["success"] is True
            mock_update.assert_called_once()

            # Verify audit entry created
            audit = db.query(DeepLinkAudit).filter(
                DeepLinkAudit.resource_type == "canvas",
                DeepLinkAudit.resource_id == "canvas-123"
            ).first()
            assert audit is not None
            assert audit.status == "success"

    @pytest.mark.asyncio
    async def test_execute_canvas_unsupported_action(self, db):
        """Test unsupported canvas action."""
        link = parse_deep_link("atom://canvas/canvas-123?action=delete")
        result = await execute_canvas_deep_link(link, "user-1", db)

        assert result["success"] is False
        assert "Unsupported canvas action" in result["error"]

    @pytest.mark.asyncio
    async def test_execute_canvas_update_failed(self, db):
        """Test canvas update failure."""
        # Mock the update_canvas function to return failure
        with patch('core.deeplinks.update_canvas') as mock_update:
            mock_update.return_value = {"success": False, "error": "Canvas not found"}

            link = parse_deep_link("atom://canvas/canvas-123?action=update")
            result = await execute_canvas_deep_link(link, "user-1", db)

            assert result["success"] is False

            # Verify audit entry shows failure
            audit = db.query(DeepLinkAudit).filter(
                DeepLinkAudit.resource_type == "canvas",
                DeepLinkAudit.resource_id == "canvas-123"
            ).first()
            assert audit is not None
            assert audit.status == "failed"


# ============================================================================
# execute_tool_deep_link() Tests
# ============================================================================

class TestExecuteToolDeepLink:
    """Test tool deep link execution."""

    @pytest.mark.asyncio
    async def test_execute_tool_success(self, db):
        """Test successful tool deep link execution."""
        # Mock tool registry
        mock_tool = Mock()
        mock_tool.to_dict.return_value = {"name": "present_chart", "description": "Chart"}

        with patch('core.deeplinks.get_tool_registry') as mock_registry:
            mock_instance = Mock()
            mock_instance.get.return_value = mock_tool
            mock_registry.return_value = mock_instance

            link = parse_deep_link("atom://tool/present_chart")
            result = await execute_tool_deep_link(link, "user-1", db)

            assert result["success"] is True
            assert result["tool_name"] == "present_chart"
            assert "tool_metadata" in result

            # Verify audit entry created
            audit = db.query(DeepLinkAudit).filter(
                DeepLinkAudit.resource_type == "tool",
                DeepLinkAudit.resource_id == "present_chart"
            ).first()
            assert audit is not None
            assert audit.status == "success"

    @pytest.mark.asyncio
    async def test_execute_tool_not_found(self, db):
        """Test tool not found error."""
        with patch('core.deeplinks.get_tool_registry') as mock_registry:
            mock_instance = Mock()
            mock_instance.get.return_value = None
            mock_registry.return_value = mock_instance

            link = parse_deep_link("atom://tool/nonexistent_tool")
            result = await execute_tool_deep_link(link, "user-1", db)

            assert result["success"] is False
            assert "not found" in result["error"]


# ============================================================================
# execute_deep_link() Tests (Main Entry Point)
# ============================================================================

class TestExecuteDeepLink:
    """Test main execute_deep_link entry point."""

    @pytest.mark.asyncio
    async def test_execute_agent_link(self, db, test_agent):
        """Test executing agent deep link."""
        url = f"atom://agent/{test_agent.id}?message=Hello"
        result = await execute_deep_link(url, "user-1", db)

        assert result["success"] is True
        assert result["agent_id"] == test_agent.id

    @pytest.mark.asyncio
    async def test_execute_workflow_link(self, db):
        """Test executing workflow deep link."""
        url = "atom://workflow/workflow-1?action=start"
        result = await execute_deep_link(url, "user-1", db)

        assert result["success"] is True
        assert result["workflow_id"] == "workflow-1"

    @pytest.mark.asyncio
    async def test_execute_canvas_link(self, db):
        """Test executing canvas deep link."""
        with patch('core.deeplinks.update_canvas') as mock_update:
            mock_update.return_value = {"success": True}

            url = "atom://canvas/canvas-123?action=update"
            result = await execute_deep_link(url, "user-1", db)

            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_execute_tool_link(self, db):
        """Test executing tool deep link."""
        mock_tool = Mock()
        mock_tool.to_dict.return_value = {"name": "test_tool"}

        with patch('core.deeplinks.get_tool_registry') as mock_registry:
            mock_instance = Mock()
            mock_instance.get.return_value = mock_tool
            mock_registry.return_value = mock_instance

            url = "atom://tool/test_tool"
            result = await execute_deep_link(url, "user-1", db)

            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_execute_invalid_url(self, db):
        """Test executing invalid URL returns error."""
        url = "atom://invalid/resource-1"
        result = await execute_deep_link(url, "user-1", db)

        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_execute_with_source_parameter(self, db, test_agent):
        """Test executing with custom source parameter."""
        url = f"atom://agent/{test_agent.id}?message=Hello"
        result = await execute_deep_link(url, "user-1", db, source="mobile_app")

        assert result["success"] is True
        assert result["source"] == "mobile_app"


# ============================================================================
# generate_deep_link() Tests
# ============================================================================

class TestGenerateDeepLink:
    """Test deep link URL generation."""

    def test_generate_agent_link(self):
        """Test generating agent deep link."""
        url = generate_deep_link("agent", "agent-1", message="Hello", session="abc")

        assert url == "atom://agent/agent-1?message=Hello&session=abc"

    def test_generate_workflow_link(self):
        """Test generating workflow deep link."""
        url = generate_deep_link("workflow", "workflow-1", action="start")

        assert url == "atom://workflow/workflow-1?action=start"

    def test_generate_canvas_link_with_json_params(self):
        """Test generating canvas deep link with JSON params."""
        url = generate_deep_link(
            "canvas",
            "canvas-123",
            action="update",
            params={"title": "New Title"}
        )

        assert "atom://canvas/canvas-123?action=update" in url
        assert "params=" in url

    def test_generate_tool_link(self):
        """Test generating tool deep link."""
        url = generate_deep_link("tool", "present_chart")

        assert url == "atom://tool/present_chart"

    def test_generate_invalid_resource_type(self):
        """Test generating link with invalid resource type."""
        with pytest.raises(ValueError) as exc:
            generate_deep_link("invalid", "resource-1")

        assert "Invalid resource_type" in str(exc.value)


# ============================================================================
# Audit Trail Tests
# ============================================================================

class TestDeepLinkAudit:
    """Test deep link audit trail."""

    @pytest.mark.asyncio
    async def test_audit_entry_created(self, db, test_agent):
        """Test audit entry is created for deep link execution."""
        link = parse_deep_link(f"atom://agent/{test_agent.id}?message=Hello")
        await execute_agent_deep_link(link, "user-1", db)

        audit = db.query(DeepLinkAudit).filter(
            DeepLinkAudit.agent_id == test_agent.id
        ).first()

        assert audit is not None
        assert audit.user_id == "user-1"
        assert audit.resource_type == "agent"
        assert audit.resource_id == test_agent.id
        assert audit.action == "execute"
        assert audit.status == "success"
        assert audit.deeplink_url == link.original_url
        assert audit.parameters == link.parameters

    @pytest.mark.asyncio
    async def test_audit_with_custom_source(self, db, test_agent):
        """Test audit entry records custom source."""
        link = parse_deep_link(f"atom://agent/{test_agent.id}?message=Hello")
        await execute_agent_deep_link(link, "user-1", db, source="mobile_app")

        audit = db.query(DeepLinkAudit).filter(
            DeepLinkAudit.agent_id == test_agent.id
        ).first()

        assert audit.source == "mobile_app"


# ============================================================================
# Integration Tests
# ============================================================================

class TestDeepLinkIntegration:
    """Integration tests for deep link system."""

    @pytest.mark.asyncio
    async def test_full_lifecycle_agent_deep_link(self, db, test_agent):
        """Test full lifecycle: generate, parse, execute, audit."""
        # Generate
        url = generate_deep_link("agent", test_agent.id, message="Test message")

        # Parse
        link = parse_deep_link(url)
        assert link.resource_id == test_agent.id

        # Execute
        result = await execute_deep_link(url, "user-1", db)
        assert result["success"] is True

        # Verify audit
        audit = db.query(DeepLinkAudit).filter(
            DeepLinkAudit.agent_id == test_agent.id
        ).first()
        assert audit is not None

        # Verify execution
        execution = db.query(AgentExecution).filter(
            AgentExecution.id == result["execution_id"]
        ).first()
        assert execution is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
