"""
Unit Tests for Agent Coordination Service

Tests multi-agent canvas collaboration:
- Agent handoff protocols
- Multi-agent coordination (sequential, parallel, consensus)
- Agent presence management on canvases
- Handoff validation and schema checking

Target Coverage: 80%
Target Branch Coverage: 50%+
Pass Rate Target: 95%+
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, AsyncMock, patch
from sqlalchemy.orm import Session

from core.agent_coordination import (
    AgentHandoffProtocol,
    MultiAgentCanvasService
)
from core.models import (
    AgentRegistry,
    AgentHandoff,
    AgentCanvasPresence,
    Canvas,
    AgentStatus,
    User,
    UserRole
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def db():
    """Create database session."""
    from core.database import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def sample_agents(db):
    """Create sample agents for coordination."""
    agent1 = AgentRegistry(
        id="coord-agent-1",
        name="Coordinator Agent 1",
        description="First coordinator agent",
        category="coordination",
        status=AgentStatus.SUPERVISED,
        confidence_score=0.75,
        module_path="agents.coord1",
        class_name="CoordAgent1",
        configuration={},
        workspace_id="default",
        user_id="test-user-123"
    )

    agent2 = AgentRegistry(
        id="coord-agent-2",
        name="Coordinator Agent 2",
        description="Second coordinator agent",
        category="coordination",
        status=AgentStatus.SUPERVISED,
        confidence_score=0.75,
        module_path="agents.coord2",
        class_name="CoordAgent2",
        configuration={},
        workspace_id="default",
        user_id="test-user-123"
    )

    db.add(agent1)
    db.add(agent2)
    db.commit()
    db.refresh(agent1)
    db.refresh(agent2)

    return {"agent1": agent1, "agent2": agent2}


@pytest.fixture
def sample_canvas(db):
    """Create sample canvas."""
    canvas = Canvas(
        id="test-canvas-123",
        title="Test Coordination Canvas",
        tenant_id="default",
        user_id="test-user-123",
        canvas_type="collaboration",
        state={"active": True}
    )
    db.add(canvas)
    db.commit()
    db.refresh(canvas)
    return canvas


# =============================================================================
# Test Class: AgentHandoffProtocol - Validate Handoff Payload
# =============================================================================

class TestValidateHandoffPayload:
    """Tests for validate_handoff_payload method."""

    def test_validates_with_valid_payload_and_schema(self, db, sample_agents):
        """RED: Test validation with valid payload and schema."""
        protocol = AgentHandoffProtocol(db)

        schema = {
            "type": "object",
            "required": ["message", "sender"],
            "properties": {
                "message": {"type": "string"},
                "sender": {"type": "string"}
            }
        }

        payload = {
            "message": "Hello from agent 1",
            "sender": "coord-agent-1"
        }

        result = protocol.validate_handoff_payload(payload, schema)
        assert result is True

    def test_fails_validation_with_missing_required_field(self, db, sample_agents):
        """RED: Test validation fails when required field is missing."""
        protocol = AgentHandoffProtocol(db)

        schema = {
            "type": "object",
            "required": ["message", "sender"],
            "properties": {
                "message": {"type": "string"},
                "sender": {"type": "string"}
            }
        }

        payload = {
            "message": "Hello from agent 1"
            # Missing "sender" field
        }

        result = protocol.validate_handoff_payload(payload, schema)
        assert result is False

    def test_returns_true_when_no_schema_provided(self, db, sample_agents):
        """RED: Test validation passes when no schema is provided."""
        protocol = AgentHandoffProtocol(db)

        payload = {"any": "payload"}

        result = protocol.validate_handoff_payload(payload, None)
        assert result is True


# =============================================================================
# Test Class: AgentHandoffProtocol - Initiate Handoff
# =============================================================================

class TestInitiateHandoff:
    """Tests for initiate_handoff method."""

    @pytest.mark.asyncio
    async def test_initiates_handoff_successfully(self, db, sample_agents, sample_canvas):
        """RED: Test successful handoff initiation."""
        protocol = AgentHandoffProtocol(db)

        context = {"task": "Continue this work"}

        with patch('core.agent_coordination.get_connection_manager') as mock_mgr:
            mock_instance = Mock()
            mock_instance.broadcast_event = AsyncMock()
            mock_instance.AGENT_HANDOFF = "agent_handoff"
            mock_mgr.return_value = mock_instance

            result = await protocol.initiate_handoff(
                from_agent_id=sample_agents["agent1"].id,
                to_agent_id=sample_agents["agent2"].id,
                canvas_id=sample_canvas.id,
                tenant_id="default",
                context=context,
                reason="Task delegation"
            )

            assert "handoff_id" in result
            assert result["status"] == "pending"
            assert "initiated from" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_fails_with_invalid_from_agent(self, db, sample_agents, sample_canvas):
        """RED: Test handoff fails with invalid from_agent."""
        protocol = AgentHandoffProtocol(db)

        with pytest.raises(ValueError, match="Invalid agent IDs"):
            await protocol.initiate_handoff(
                from_agent_id="nonexistent-agent",
                to_agent_id=sample_agents["agent2"].id,
                canvas_id=sample_canvas.id,
                tenant_id="default",
                context={},
                reason="Test"
            )

    @pytest.mark.asyncio
    async def test_fails_with_invalid_canvas(self, db, sample_agents):
        """RED: Test handoff fails with invalid canvas."""
        protocol = AgentHandoffProtocol(db)

        with pytest.raises(ValueError, match="Invalid canvas ID"):
            await protocol.initiate_handoff(
                from_agent_id=sample_agents["agent1"].id,
                to_agent_id=sample_agents["agent2"].id,
                canvas_id="nonexistent-canvas",
                tenant_id="default",
                context={},
                reason="Test"
            )

    @pytest.mark.asyncio
    async def test_validates_input_schema_when_provided(self, db, sample_agents, sample_canvas):
        """RED: Test that input schema is validated."""
        protocol = AgentHandoffProtocol(db)

        schema = {
            "type": "object",
            "required": ["task"]
        }

        # Missing required field
        invalid_context = {"wrong_field": "value"}

        with pytest.raises(ValueError, match="does not match required input schema"):
            await protocol.initiate_handoff(
                from_agent_id=sample_agents["agent1"].id,
                to_agent_id=sample_agents["agent2"].id,
                canvas_id=sample_canvas.id,
                tenant_id="default",
                context=invalid_context,
                reason="Test",
                input_schema=schema
            )


# =============================================================================
# Test Class: AgentHandoffProtocol - Accept Handoff
# =============================================================================

class TestAcceptHandoff:
    """Tests for accept_handoff method."""

    @pytest.mark.asyncio
    async def test_accepts_handoff_successfully(self, db, sample_agents, sample_canvas):
        """RED: Test successful handoff acceptance."""
        protocol = AgentHandoffProtocol(db)

        # First create a handoff
        init_result = await protocol.initiate_handoff(
            from_agent_id=sample_agents["agent1"].id,
            to_agent_id=sample_agents["agent2"].id,
            canvas_id=sample_canvas.id,
            tenant_id="default",
            context={},
            reason="Test"
        )

        handoff_id = init_result["handoff_id"]

        with patch('core.agent_coordination.get_connection_manager') as mock_mgr:
            mock_instance = Mock()
            mock_instance.broadcast_event = AsyncMock()
            mock_instance.AGENT_COORDINATION_RESPONSE = "coord_response"
            mock_mgr.return_value = mock_instance

            result = await protocol.accept_handoff(
                handoff_id=handoff_id,
                agent_id=sample_agents["agent2"].id,
                tenant_id="default"
            )

            assert result["status"] == "accepted"

    @pytest.mark.asyncio
    async def test_fails_when_handoff_not_found(self, db, sample_agents):
        """RED: Test accept fails when handoff doesn't exist."""
        protocol = AgentHandoffProtocol(db)

        with pytest.raises(ValueError, match="Handoff not found"):
            await protocol.accept_handoff(
                handoff_id="nonexistent-handoff",
                agent_id=sample_agents["agent2"].id,
                tenant_id="default"
            )

    @pytest.mark.asyncio
    async def test_fails_when_agent_not_authorized(self, db, sample_agents, sample_canvas):
        """RED: Test accept fails when agent is not the target."""
        protocol = AgentHandoffProtocol(db)

        # Create handoff from agent1 to agent2
        init_result = await protocol.initiate_handoff(
            from_agent_id=sample_agents["agent1"].id,
            to_agent_id=sample_agents["agent2"].id,
            canvas_id=sample_canvas.id,
            tenant_id="default",
            context={},
            reason="Test"
        )

        handoff_id = init_result["handoff_id"]

        # Try to accept with agent1 (not the target)
        with pytest.raises(ValueError, match="not authorized"):
            await protocol.accept_handoff(
                handoff_id=handoff_id,
                agent_id=sample_agents["agent1"].id,
                tenant_id="default"
            )


# =============================================================================
# Test Class: AgentHandoffProtocol - Reject Handoff
# =============================================================================

class TestRejectHandoff:
    """Tests for reject_handoff method."""

    @pytest.mark.asyncio
    async def test_rejects_handoff_successfully(self, db, sample_agents, sample_canvas):
        """RED: Test successful handoff rejection."""
        protocol = AgentHandoffProtocol(db)

        # First create a handoff
        init_result = await protocol.initiate_handoff(
            from_agent_id=sample_agents["agent1"].id,
            to_agent_id=sample_agents["agent2"].id,
            canvas_id=sample_canvas.id,
            tenant_id="default",
            context={},
            reason="Test"
        )

        handoff_id = init_result["handoff_id"]

        with patch('core.agent_coordination.get_connection_manager') as mock_mgr:
            mock_instance = Mock()
            mock_instance.broadcast_event = AsyncMock()
            mock_instance.AGENT_COORDINATION_RESPONSE = "coord_response"
            mock_mgr.return_value = mock_instance

            result = await protocol.reject_handoff(
                handoff_id=handoff_id,
                agent_id=sample_agents["agent2"].id,
                tenant_id="default",
                reason="Too busy"
            )

            assert result["status"] == "rejected"

    @pytest.mark.asyncio
    async def test_includes_rejection_reason(self, db, sample_agents, sample_canvas):
        """RED: Test that rejection reason is recorded."""
        protocol = AgentHandoffProtocol(db)

        init_result = await protocol.initiate_handoff(
            from_agent_id=sample_agents["agent1"].id,
            to_agent_id=sample_agents["agent2"].id,
            canvas_id=sample_canvas.id,
            tenant_id="default",
            context={},
            reason="Test"
        )

        handoff_id = init_result["handoff_id"]
        reason = "Agent capacity reached"

        await protocol.reject_handoff(
            handoff_id=handoff_id,
            agent_id=sample_agents["agent2"].id,
            tenant_id="default",
            reason=reason
        )

        # Verify rejection reason was saved
        handoff = db.query(AgentHandoff).filter(AgentHandoff.id == handoff_id).first()
        assert handoff.rejection_reason == reason


# =============================================================================
# Test Class: AgentHandoffProtocol - Complete Handoff
# =============================================================================

class TestCompleteHandoff:
    """Tests for complete_handoff method."""

    @pytest.mark.asyncio
    async def test_completes_handoff_with_result(self, db, sample_agents, sample_canvas):
        """RED: Test handoff completion with result."""
        protocol = AgentHandoffProtocol(db)

        # First create and accept a handoff
        init_result = await protocol.initiate_handoff(
            from_agent_id=sample_agents["agent1"].id,
            to_agent_id=sample_agents["agent2"].id,
            canvas_id=sample_canvas.id,
            tenant_id="default",
            context={"task": "Test task"},
            reason="Test"
        )

        handoff_id = init_result["handoff_id"]

        result_data = {"output": "Task completed successfully"}

        with patch('core.agent_coordination.get_connection_manager') as mock_mgr:
            mock_instance = Mock()
            mock_instance.broadcast_event = AsyncMock()
            mock_instance.AGENT_ACTION_COMPLETE = "action_complete"
            mock_mgr.return_value = mock_instance

            result = await protocol.complete_handoff(
                handoff_id=handoff_id,
                result=result_data,
                tenant_id="default"
            )

            assert result["status"] == "completed"
            assert result["result"] == result_data


# =============================================================================
# Test Class: MultiAgentCanvasService
# =============================================================================

class TestMultiAgentCanvasService:
    """Tests for MultiAgentCanvasService."""

    @pytest.mark.asyncio
    async def test_adds_agent_to_canvas(self, db, sample_agents, sample_canvas):
        """RED: Test adding agent to canvas collaboration."""
        service = MultiAgentCanvasService(db)

        result = await service.add_agent_to_canvas(
            agent_id=sample_agents["agent1"].id,
            canvas_id=sample_canvas.id,
            tenant_id="default",
            role="collaborator"
        )

        assert "agent_id" in result or "success" in result

    @pytest.mark.asyncio
    async def test_removes_agent_from_canvas(self, db, sample_agents, sample_canvas):
        """RED: Test removing agent from canvas."""
        service = MultiAgentCanvasService(db)

        # First add agent
        await service.add_agent_to_canvas(
            agent_id=sample_agents["agent1"].id,
            canvas_id=sample_canvas.id,
            tenant_id="default"
        )

        # Then remove
        result = await service.remove_agent_from_canvas(
            agent_id=sample_agents["agent1"].id,
            canvas_id=sample_canvas.id,
            tenant_id="default"
        )

        assert "agent_id" in result or "success" in result


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
