"""
Agent Guidance Canvas Tests

Tests for real-time agent operation broadcasting to canvas.
"""

import json
import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from core.models import AgentOperationTracker, AgentRegistry, CanvasAudit, User, Workspace
from tools.agent_guidance_canvas_tool import AgentGuidanceSystem


@pytest.fixture
def test_user(db_session):
    """Create test user."""
    user = User(
        id=str(uuid.uuid4()),
        email="test@example.com",
        password_hash="hash"
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def test_agent(db_session):
    """Create test agent."""
    agent = AgentRegistry(
        id=str(uuid.uuid4()),
        name="Test Agent",
        description="Test agent for guidance system",
        category="Test",
        module_path="tests.test_module",
        class_name="TestAgent",
        status="autonomous",  # High maturity to pass governance checks
        confidence_score=0.95,
        required_role_for_autonomy="team_lead"
    )
    db_session.add(agent)
    db_session.commit()
    return agent


@pytest.fixture
def guidance_system(db_session):
    """Agent guidance system fixture."""
    return AgentGuidanceSystem(db_session)


@pytest.mark.asyncio
async def test_start_operation(guidance_system, test_user, test_agent):
    """Test starting a new agent operation."""
    with patch('core.websockets.manager.broadcast') as mock_broadcast:
        operation_id = await guidance_system.start_operation(
            user_id=test_user.id,
            agent_id=test_agent.id,
            operation_type="integration_connect",
            context={
                "what": "Connecting to Slack",
                "why": "To enable automated workflows",
                "next": "Opening OAuth page"
            },
            total_steps=5
        )

        # Verify operation ID returned
        assert operation_id is not None
        assert isinstance(operation_id, str)

        # Verify broadcast called
        mock_broadcast.assert_called_once()
        call_args = mock_broadcast.call_args
        assert call_args[0][0] == f"user:{test_user.id}"

        # Verify message structure
        message = call_args[0][1]
        assert message["type"] == "canvas:update"
        assert message["data"]["action"] == "present"
        assert message["data"]["component"] == "agent_operation_tracker"
        assert message["data"]["data"]["operation_id"] == operation_id
        assert message["data"]["data"]["operation_type"] == "integration_connect"
        assert message["data"]["data"]["status"] == "running"
        assert message["data"]["data"]["context"]["what"] == "Connecting to Slack"


@pytest.mark.asyncio
async def test_start_operation_creates_tracker(db_session, guidance_system, test_user, test_agent):
    """Test that start_operation creates database tracker."""
    with patch('core.websockets.manager.broadcast'):
        operation_id = await guidance_system.start_operation(
            user_id=test_user.id,
            agent_id=test_agent.id,
            operation_type="browser_automate",
            context={
                "what": "Automating browser",
                "why": "To fill forms",
                "next": "Opening browser"
            }
        )

        # Verify tracker created in database
        tracker = db_session.query(AgentOperationTracker).filter(
            AgentOperationTracker.operation_id == operation_id
        ).first()

        assert tracker is not None
        assert tracker.agent_id == test_agent.id
        assert tracker.user_id == test_user.id
        assert tracker.operation_type == "browser_automate"
        assert tracker.status == "running"
        assert tracker.progress == 0
        assert tracker.what_explanation == "Automating browser"


@pytest.mark.asyncio
async def test_update_step(guidance_system, test_user, test_agent):
    """Test updating operation step."""
    with patch('core.websockets.manager.broadcast'):
        # Start operation
        operation_id = await guidance_system.start_operation(
            user_id=test_user.id,
            agent_id=test_agent.id,
            operation_type="workflow_execute",
            context={"what": "Executing workflow"}
        )

    with patch('core.websockets.manager.broadcast') as mock_broadcast:
        # Update step
        await guidance_system.update_step(
            user_id=test_user.id,
            operation_id=operation_id,
            step="Step 1: Initialize",
            progress=20,
            add_log={
                "level": "info",
                "message": "Starting workflow execution"
            }
        )

        # Verify broadcast
        mock_broadcast.assert_called_once()
        message = mock_broadcast.call_args[0][1]
        assert message["data"]["updates"]["current_step"] == "Step 1: Initialize"
        assert message["data"]["updates"]["progress"] == 20
        assert message["data"]["updates"]["logs"][0]["message"] == "Starting workflow execution"


@pytest.mark.asyncio
async def test_update_context(guidance_system, test_user, test_agent):
    """Test updating operation context."""
    with patch('core.websockets.manager.broadcast'):
        # Start operation
        operation_id = await guidance_system.start_operation(
            user_id=test_user.id,
            agent_id=test_agent.id,
            operation_type="integration_connect",
            context={"what": "Initial", "why": "Initial", "next": "Initial"}
        )

    with patch('core.websockets.manager.broadcast') as mock_broadcast:
        # Update context
        await guidance_system.update_context(
            user_id=test_user.id,
            operation_id=operation_id,
            what="Connecting to API",
            why="Need to fetch data",
            next_steps="Processing response"
        )

        # Verify broadcast
        mock_broadcast.assert_called_once()
        message = mock_broadcast.call_args[0][1]
        context = message["data"]["updates"]["context"]
        assert context["what"] == "Connecting to API"
        assert context["why"] == "Need to fetch data"
        assert context["next"] == "Processing response"


@pytest.mark.asyncio
async def test_complete_operation(guidance_system, test_user, test_agent):
    """Test completing operation."""
    with patch('core.websockets.manager.broadcast'):
        # Start operation
        operation_id = await guidance_system.start_operation(
            user_id=test_user.id,
            agent_id=test_agent.id,
            operation_type="workflow_execute",
            context={"what": "Running workflow"}
        )

    with patch('core.websockets.manager.broadcast') as mock_broadcast:
        # Complete operation
        await guidance_system.complete_operation(
            user_id=test_user.id,
            operation_id=operation_id,
            status="completed",
            final_message="Workflow completed successfully"
        )

        # Verify broadcast
        mock_broadcast.assert_called_once()
        message = mock_broadcast.call_args[0][1]
        assert message["data"]["updates"]["status"] == "completed"
        assert message["data"]["updates"]["progress"] == 100
        assert message["data"]["updates"]["current_step"] == "Workflow completed successfully"


@pytest.mark.asyncio
async def test_complete_operation_failed(guidance_system, test_user, test_agent):
    """Test completing operation with failure."""
    with patch('core.websockets.manager.broadcast'):
        operation_id = await guidance_system.start_operation(
            user_id=test_user.id,
            agent_id=test_agent.id,
            operation_type="integration_connect",
            context={"what": "Connecting"}
        )

    with patch('core.websockets.manager.broadcast') as mock_broadcast:
        # Complete with failure
        await guidance_system.complete_operation(
            user_id=test_user.id,
            operation_id=operation_id,
            status="failed",
            final_message="Connection failed"
        )

        # Verify status is failed but progress preserved
        message = mock_broadcast.call_args[0][1]
        assert message["data"]["updates"]["status"] == "failed"


@pytest.mark.asyncio
async def test_add_log_entry(guidance_system, test_user, test_agent):
    """Test adding log entries to operation."""
    with patch('core.websockets.manager.broadcast'):
        operation_id = await guidance_system.start_operation(
            user_id=test_user.id,
            agent_id=test_agent.id,
            operation_type="browser_automate",
            context={"what": "Automating"}
        )

    with patch('core.websockets.manager.broadcast'):
        # Add log entries
        await guidance_system.add_log_entry(
            user_id=test_user.id,
            operation_id=operation_id,
            level="info",
            message="Step 1 completed"
        )

        await guidance_system.add_log_entry(
            user_id=test_user.id,
            operation_id=operation_id,
            level="warning",
            message="Slow response detected"
        )

        # Verify logs in database
        tracker = guidance_system.db.query(AgentOperationTracker).filter(
            AgentOperationTracker.operation_id == operation_id
        ).first()

        assert len(tracker.logs) == 2
        assert tracker.logs[0]["level"] == "info"
        assert tracker.logs[0]["message"] == "Step 1 completed"
        assert tracker.logs[1]["level"] == "warning"
        assert tracker.logs[1]["message"] == "Slow response detected"


@pytest.mark.asyncio
async def test_progress_calculation(db_session, guidance_system, test_user, test_agent):
    """Test automatic progress calculation."""
    with patch('core.websockets.manager.broadcast'):
        operation_id = await guidance_system.start_operation(
            user_id=test_user.id,
            agent_id=test_agent.id,
            operation_type="workflow_execute",
            context={"what": "Executing"},
            total_steps=4
        )

    with patch('core.websockets.manager.broadcast'):
        # Update steps without explicit progress
        await guidance_system.update_step(
            user_id=test_user.id,
            operation_id=operation_id,
            step="Step 1"
        )

        await guidance_system.update_step(
            user_id=test_user.id,
            operation_id=operation_id,
            step="Step 2"
        )

        # Verify progress calculated automatically
        tracker = db_session.query(AgentOperationTracker).filter(
            AgentOperationTracker.operation_id == operation_id
        ).first()

        # 2 steps out of 4 = 50%
        assert tracker.progress == 50


@pytest.mark.asyncio
async def test_audit_trail_creation(db_session, guidance_system, test_user, test_agent):
    """Test that operations create audit trail."""
    with patch('core.websockets.manager.broadcast'):
        await guidance_system.start_operation(
            user_id=test_user.id,
            agent_id=test_agent.id,
            operation_type="integration_connect",
            context={"what": "Connecting"}
        )

    # Verify audit entry created
    audit = db_session.query(CanvasAudit).filter(
        CanvasAudit.component_type == "agent_operation_tracker",
        CanvasAudit.action == "start_operation"
    ).first()

    assert audit is not None
    assert audit.user_id == test_user.id
    assert audit.agent_id == test_agent.id


@pytest.mark.asyncio
async def test_feature_flag_disabled(db_session, guidance_system, test_user, test_agent):
    """Test that operations skip when feature flag disabled."""
    with patch('tools.agent_guidance_canvas_tool.AGENT_GUIDANCE_ENABLED', False):
        with patch('core.websockets.manager.broadcast') as mock_broadcast:
            operation_id = await guidance_system.start_operation(
                user_id=test_user.id,
                agent_id=test_agent.id,
                operation_type="test",
                context={"what": "Test"}
            )

            # Should return ID but not broadcast
            assert operation_id is not None
            mock_broadcast.assert_not_called()


@pytest.mark.asyncio
async def test_unknown_operation_update(guidance_system, test_user):
    """Test updating unknown operation doesn't crash."""
    with patch('core.websockets.manager.broadcast') as mock_broadcast:
        # Try to update non-existent operation
        await guidance_system.update_step(
            user_id=test_user.id,
            operation_id="unknown_id",
            step="Some step"
        )

        # Should handle gracefully
        mock_broadcast.assert_not_called()


def test_guidance_system_instantiation(db_session):
    """Test AgentGuidanceSystem can be instantiated."""
    from tools.agent_guidance_canvas_tool import get_agent_guidance_system

    system = get_agent_guidance_system(db_session)
    assert system is not None
    assert system.db == db_session
    assert system.resolver is not None
    assert system.governance is not None
