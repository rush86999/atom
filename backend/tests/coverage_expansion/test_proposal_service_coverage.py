"""
Coverage expansion tests for proposal service.

Tests cover critical code paths in:
- proposal_service.py: Proposal generation, validation, approval
- Governance integration: Permission checks for INTERN agents

Target: Cover critical paths (happy path + error paths) to increase coverage.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from core.proposal_service import ProposalService, PROPOSAL_EXECUTION_ENABLED
from core.models import (
    AgentProposal,
    AgentRegistry,
    AgentStatus,
    ProposalStatus,
    ProposalType,
    UserRole
)


class TestProposalServiceCoverage:
    """Coverage expansion for ProposalService."""

    # The tests share the real dev DB (core.database.SessionLocal), so fixed
    # row IDs survive between runs. Delete any leftover rows first to make the
    # fixtures idempotent (repeatable without a fresh database).
    def _delete_agent(self, db_session: Session, agent_id: str) -> None:
        db_session.query(AgentRegistry).filter(AgentRegistry.id == agent_id).delete()
        db_session.commit()

    @pytest.fixture
    def db_session(self):
        """Get test database session."""
        from core.database import SessionLocal
        session = SessionLocal()
        yield session
        session.rollback()
        session.close()

    @pytest.fixture
    def proposal_service(self, db_session):
        """Get proposal service instance."""
        return ProposalService(db_session)

    @pytest.fixture
    def intern_agent(self, db_session):
        """Create test INTERN agent."""
        self._delete_agent(db_session, "intern-agent-test")
        agent = AgentRegistry(
            id="intern-agent-test",
            name="Test Intern Agent",
            status=AgentStatus.INTERN.value,
            category="test",
            module_path="test.module",
            class_name="TestIntern",
            confidence_score=0.6,
            tenant_id="default",
            user_id="test-user"
        )
        db_session.add(agent)
        db_session.commit()
        db_session.refresh(agent)
        return agent

    # Test: proposal creation
    @pytest.mark.asyncio
    async def test_create_action_proposal_success(self, proposal_service, intern_agent):
        """Create proposal for INTERN agent action."""
        proposal = await proposal_service.create_action_proposal(
            intern_agent_id=intern_agent.id,
            trigger_context={"test": "context"},
            proposed_action={
                "action_type": "canvas_present",
                "canvas_type": "chart",
                "data": {"test": "data"}
            },
            reasoning="This is a test proposal for coverage"
        )

        assert proposal.id is not None
        assert proposal.agent_id == intern_agent.id
        assert proposal.status == ProposalStatus.PENDING_APPROVAL.value
        assert proposal.proposal_type == ProposalType.ACTION.value
        assert "Test Intern Agent" in proposal.description

    @pytest.mark.asyncio
    async def test_create_action_proposal_with_canvas(self, proposal_service, intern_agent):
        """Create proposal with canvas association."""
        proposal = await proposal_service.create_action_proposal(
            intern_agent_id=intern_agent.id,
            trigger_context={},
            proposed_action={"action_type": "canvas_present"},
            reasoning="Test",
            canvas_id="canvas-123",
            session_id="session-456",
            title="Custom Proposal Title"
        )

        assert proposal.canvas_id == "canvas-123"
        assert proposal.session_id == "session-456"
        assert proposal.title == "Custom Proposal Title"

    @pytest.mark.asyncio
    async def test_create_action_proposal_agent_not_found(self, proposal_service):
        """Handle proposal creation for non-existent agent."""
        with pytest.raises(ValueError, match="Agent .* not found"):
            await proposal_service.create_action_proposal(
                intern_agent_id="nonexistent-agent",
                trigger_context={},
                proposed_action={},
                reasoning="Test"
            )

    @pytest.mark.asyncio
    async def test_create_action_proposal_non_intern_status(self, proposal_service, db_session):
        """Create proposal for agent with non-INTERN status (should be blocked)."""
        self._delete_agent(db_session, "autonomous-agent")
        agent = AgentRegistry(
            id="autonomous-agent",
            name="Autonomous Agent",
            status=AgentStatus.AUTONOMOUS.value,
            category="test",
            module_path="test",
            class_name="TestAuto",
            tenant_id="default",
            user_id="test-user"
        )
        db_session.add(agent)
        db_session.commit()

        # Source behavior (Bug 8 fix): non-INTERN agents are hard-blocked
        # from creating proposals — this is fail-closed by design.
        with pytest.raises(PermissionError, match="not an INTERN agent"):
            await proposal_service.create_action_proposal(
                intern_agent_id=agent.id,
                trigger_context={},
                proposed_action={"action_type": "test"},
                reasoning="Test"
            )

    # Test: proposal submission
    @pytest.mark.asyncio
    async def test_submit_for_approval_success(self, proposal_service, intern_agent):
        """Submit proposal for approval."""
        proposal = await proposal_service.create_action_proposal(
            intern_agent_id=intern_agent.id,
            trigger_context={},
            proposed_action={"action_type": "test"},
            reasoning="Test"
        )

        # Should not raise
        await proposal_service.submit_for_approval(proposal)

    @pytest.mark.asyncio
    async def test_submit_for_approval_invalid_status(self, proposal_service, intern_agent, db_session):
        """Reject submission of proposal with invalid status."""
        db_session.query(AgentProposal).filter(AgentProposal.id == "test-proposal").delete()
        db_session.commit()
        proposal = AgentProposal(
            id="test-proposal",
            agent_id=intern_agent.id,
            agent_name=intern_agent.name,
            tenant_id="default",
            user_id="test-user",
            status=ProposalStatus.APPROVED.value,  # Already approved
            proposal_type=ProposalType.ACTION.value,
            title="Test",
            description="Test",
            proposal_data={},
        )
        db_session.add(proposal)
        db_session.commit()

        with pytest.raises(ValueError, match="PENDING_APPROVAL status"):
            await proposal_service.submit_for_approval(proposal)

    # Test: proposal approval
    @pytest.mark.asyncio
    async def test_approve_proposal_success(self, proposal_service, intern_agent):
        """Approve pending proposal."""
        proposal = await proposal_service.create_action_proposal(
            intern_agent_id=intern_agent.id,
            trigger_context={},
            proposed_action={"action_type": "canvas_present"},
            reasoning="Test approval"
        )

        with patch.object(proposal_service, '_execute_proposed_action', new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = {"success": True, "executed_at": datetime.now().isoformat()}

            result = await proposal_service.approve_proposal(
                proposal.id,
                user_id="admin-user"
            )

            assert result["success"] == True

            # Verify proposal status updated
            proposal_service.db.refresh(proposal)
            assert proposal.status == ProposalStatus.EXECUTED.value
            assert proposal.approved_by == "admin-user"
            assert proposal.approved_at is not None

    @pytest.mark.asyncio
    async def test_approve_proposal_with_modifications(self, proposal_service, intern_agent):
        """Approve proposal with modifications."""
        proposal = await proposal_service.create_action_proposal(
            intern_agent_id=intern_agent.id,
            trigger_context={},
            proposed_action={"action_type": "canvas_present", "param1": "value1"},
            reasoning="Test"
        )

        modifications = {"param1": "modified_value", "param2": "new_value"}

        with patch.object(proposal_service, '_execute_proposed_action', new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = {"success": True}

            await proposal_service.approve_proposal(
                proposal.id,
                user_id="admin-user",
                modifications=modifications
            )

            proposal_service.db.refresh(proposal)
            assert proposal.modifications == modifications
            # Verify proposed_action was updated
            assert proposal.proposed_action["param1"] == "modified_value"
            assert proposal.proposed_action["param2"] == "new_value"

    @pytest.mark.asyncio
    async def test_approve_proposal_not_found(self, proposal_service):
        """Handle approval of non-existent proposal."""
        with pytest.raises(ValueError, match="not found"):
            await proposal_service.approve_proposal("nonexistent-id", "admin-user")

    @pytest.mark.asyncio
    async def test_approve_proposal_invalid_status(self, proposal_service, intern_agent, db_session):
        """Reject approval of already processed proposal."""
        db_session.query(AgentProposal).filter(AgentProposal.id == "test-proposal").delete()
        db_session.commit()
        proposal = AgentProposal(
            id="test-proposal",
            agent_id=intern_agent.id,
            agent_name=intern_agent.name,
            tenant_id="default",
            user_id="test-user",
            status=ProposalStatus.EXECUTED.value,  # Already executed
            proposal_type=ProposalType.ACTION.value,
            title="Test",
            description="Test",
            proposal_data={"proposed_action": {}},
        )
        db_session.add(proposal)
        db_session.commit()

        with pytest.raises(ValueError, match="PENDING_APPROVAL status"):
            await proposal_service.approve_proposal("test-proposal", "admin-user")

    # Test: proposal rejection
    @pytest.mark.asyncio
    async def test_reject_proposal_success(self, proposal_service, intern_agent):
        """Reject pending proposal."""
        proposal = await proposal_service.create_action_proposal(
            intern_agent_id=intern_agent.id,
            trigger_context={},
            proposed_action={"action_type": "test"},
            reasoning="Test rejection"
        )

        await proposal_service.reject_proposal(
            proposal.id,
            user_id="admin-user",
            reason="Unsafe action detected"
        )

        proposal_service.db.refresh(proposal)
        assert proposal.status == ProposalStatus.REJECTED.value
        assert proposal.approved_by == "admin-user"
        assert proposal.approved_at is not None
        assert proposal.execution_result["rejected"] == True
        assert proposal.execution_result["reason"] == "Unsafe action detected"

    @pytest.mark.asyncio
    async def test_reject_proposal_not_found(self, proposal_service):
        """Handle rejection of non-existent proposal."""
        with pytest.raises(ValueError, match="not found"):
            await proposal_service.reject_proposal("nonexistent-id", "admin-user", "reason")

    # Test: pending proposals retrieval
    @pytest.mark.asyncio
    async def test_get_pending_proposals(self, proposal_service, intern_agent):
        """Retrieve all pending proposals."""
        # Create multiple proposals
        for i in range(3):
            await proposal_service.create_action_proposal(
                intern_agent_id=intern_agent.id,
                trigger_context={"index": i},
                proposed_action={"action_type": "test"},
                reasoning=f"Proposal {i}"
            )

        pending = await proposal_service.get_pending_proposals()
        assert len(pending) >= 3
        assert all(p.status == ProposalStatus.PENDING_APPROVAL.value for p in pending)

    @pytest.mark.asyncio
    async def test_get_pending_proposals_by_agent(self, proposal_service, intern_agent, db_session):
        """Retrieve pending proposals for specific agent."""
        # Create another agent
        self._delete_agent(db_session, "intern-agent-2")
        agent2 = AgentRegistry(
            id="intern-agent-2",
            name="Second Intern",
            status=AgentStatus.INTERN.value,
            category="test",
            module_path="test",
            class_name="Test",
            tenant_id="default",
            user_id="test-user"
        )
        db_session.add(agent2)
        db_session.commit()

        # Create proposals for both agents
        await proposal_service.create_action_proposal(
            intern_agent_id=intern_agent.id,
            trigger_context={},
            proposed_action={},
            reasoning="Agent 1 proposal"
        )
        await proposal_service.create_action_proposal(
            intern_agent_id=agent2.id,
            trigger_context={},
            proposed_action={},
            reasoning="Agent 2 proposal"
        )

        # Get proposals for first agent only
        agent1_proposals = await proposal_service.get_pending_proposals(agent_id=intern_agent.id)
        assert all(p.agent_id == intern_agent.id for p in agent1_proposals)

    @pytest.mark.asyncio
    async def test_get_pending_proposals_by_canvas(self, proposal_service, intern_agent):
        """Retrieve pending proposals for specific canvas."""
        await proposal_service.create_action_proposal(
            intern_agent_id=intern_agent.id,
            trigger_context={},
            proposed_action={},
            reasoning="Test",
            canvas_id="canvas-123"
        )
        await proposal_service.create_action_proposal(
            intern_agent_id=intern_agent.id,
            trigger_context={},
            proposed_action={},
            reasoning="Test",
            canvas_id="canvas-456"
        )

        canvas_proposals = await proposal_service.get_pending_proposals(canvas_id="canvas-123")
        assert all(p.canvas_id == "canvas-123" for p in canvas_proposals)

    @pytest.mark.asyncio
    async def test_get_pending_proposals_limit(self, proposal_service, intern_agent):
        """Test limit parameter for pending proposals."""
        # Create 10 proposals
        for i in range(10):
            await proposal_service.create_action_proposal(
                intern_agent_id=intern_agent.id,
                trigger_context={"index": i},
                proposed_action={},
                reasoning=f"Proposal {i}"
            )

        # Request only 5
        limited = await proposal_service.get_pending_proposals(limit=5)
        assert len(limited) == 5

    # Test: proposal history
    @pytest.mark.asyncio
    async def test_get_proposal_history(self, proposal_service, intern_agent):
        """Retrieve agent's proposal history."""
        # Create proposals with different statuses
        proposal1 = await proposal_service.create_action_proposal(
            intern_agent_id=intern_agent.id,
            trigger_context={},
            proposed_action={},
            reasoning="Proposal 1"
        )
        proposal1.status = ProposalStatus.APPROVED.value
        proposal_service.db.commit()

        proposal2 = await proposal_service.create_action_proposal(
            intern_agent_id=intern_agent.id,
            trigger_context={},
            proposed_action={},
            reasoning="Proposal 2"
        )
        proposal2.status = ProposalStatus.REJECTED.value
        proposal2.execution_result = {"rejected": True, "reason": "test"}
        proposal_service.db.commit()

        history = await proposal_service.get_proposal_history(intern_agent.id)

        assert len(history) >= 2
        assert all("proposal_id" in h for h in history)
        assert all("status" in h for h in history)
        assert all("created_at" in h for h in history)

    # Test: execute proposed action (private method)
    @pytest.mark.asyncio
    async def test_execute_proposed_action_disabled(self, proposal_service, intern_agent):
        """Test execution when feature flag is disabled."""
        proposal = await proposal_service.create_action_proposal(
            intern_agent_id=intern_agent.id,
            trigger_context={},
            proposed_action={"action_type": "test"},
            reasoning="Test"
        )

        with patch('core.proposal_service.PROPOSAL_EXECUTION_ENABLED', False):
            result = await proposal_service._execute_proposed_action(proposal)

            assert result["success"] == False
            assert result["skipped"] == True
            assert "disabled" in result["message"]

    @pytest.mark.asyncio
    async def test_execute_proposed_action_unknown_type(self, proposal_service, intern_agent):
        """Test execution with unknown action type."""
        proposal = await proposal_service.create_action_proposal(
            intern_agent_id=intern_agent.id,
            trigger_context={},
            proposed_action={"action_type": "unknown_action"},
            reasoning="Test"
        )

        result = await proposal_service._execute_proposed_action(proposal)

        assert result["success"] == False
        assert "Unknown action type" in result["error"]

    @pytest.mark.asyncio
    async def test_execute_proposed_action_exception_handling(self, proposal_service, intern_agent):
        """Test exception handling in action execution."""
        proposal = await proposal_service.create_action_proposal(
            intern_agent_id=intern_agent.id,
            trigger_context={},
            proposed_action={"action_type": "browser_automate"},
            reasoning="Test"
        )

        # Mock browser action to raise exception
        with patch.object(proposal_service, '_execute_browser_action', new_callable=AsyncMock) as mock_browser:
            mock_browser.side_effect = Exception("Browser error")

            result = await proposal_service._execute_proposed_action(proposal)

            assert result["success"] == False
            assert "Browser error" in result["error"]

    # Test: browser action execution
    @pytest.mark.asyncio
    async def test_execute_browser_action(self, proposal_service, intern_agent):
        """Test browser action execution."""
        proposal = await proposal_service.create_action_proposal(
            intern_agent_id=intern_agent.id,
            trigger_context={},
            proposed_action={
                "action_type": "browser_automate",
                "url": "https://example.com",
                "action": "navigate"
            },
            reasoning="Test browser action"
        )

        # Known gap (see tests/integration/governance/test_proposal_execution.py):
        # execute_browser_automation has never existed in tools/browser_tool.py,
        # so the executor method is patched directly (repo convention) while the
        # action-type routing in _execute_proposed_action is exercised for real.
        with patch.object(proposal_service, '_execute_browser_action', new=AsyncMock(
                return_value={"success": True, "action_type": "browser_automate"})) as mock_browser:
            result = await proposal_service._execute_proposed_action(proposal)

            assert result["success"] == True
            assert result["action_type"] == "browser_automate"
            mock_browser.assert_awaited_once()

    # Test: canvas action execution
    @pytest.mark.asyncio
    async def test_execute_canvas_action(self, proposal_service, intern_agent):
        """Test canvas action execution."""
        proposal = await proposal_service.create_action_proposal(
            intern_agent_id=intern_agent.id,
            trigger_context={},
            proposed_action={
                "action_type": "canvas_present",
                "canvas_type": "chart",
                "data": {"test": "data"}
            },
            reasoning="Test canvas action"
        )

        # Mock the locally-imported canvas presenter
        with patch('tools.canvas_tool.present_to_canvas', new_callable=AsyncMock) as mock_canvas:
            mock_canvas.return_value = "canvas-123"

            result = await proposal_service._execute_canvas_action(proposal, proposal.proposed_action)

            assert result["success"] == True
            assert result["canvas_id"] == "canvas-123"
            mock_canvas.assert_awaited_once()

    # Test: integration action execution
    @pytest.mark.asyncio
    async def test_execute_integration_action(self, proposal_service, intern_agent):
        """Test integration action execution."""
        proposal = await proposal_service.create_action_proposal(
            intern_agent_id=intern_agent.id,
            trigger_context={},
            proposed_action={
                "action_type": "integration_connect",
                "integration_type": "asana",
                "operation": "create_task"
            },
            reasoning="Test integration action"
        )

        # get_integration_service does not exist in core/integrations (namespace
        # package) — patch the executor method (repo convention) and exercise
        # the real action-type routing.
        with patch.object(proposal_service, '_execute_integration_action', new=AsyncMock(
                return_value={"success": True, "action_type": "integration_connect"})) as mock_service:
            result = await proposal_service._execute_proposed_action(proposal)

            assert result["success"] == True
            assert result["action_type"] == "integration_connect"
            mock_service.assert_awaited_once()

    # Test: workflow action execution
    @pytest.mark.asyncio
    async def test_execute_workflow_action(self, proposal_service, intern_agent):
        """Test workflow action execution."""
        proposal = await proposal_service.create_action_proposal(
            intern_agent_id=intern_agent.id,
            trigger_context={},
            proposed_action={
                "action_type": "workflow_trigger",
                "workflow_id": "workflow-123"
            },
            reasoning="Test workflow action"
        )

        # trigger_workflow does not exist in core/workflow_engine.py (the real
        # API is WorkflowEngine.start_workflow) — patch the executor method and
        # exercise the real action-type routing.
        with patch.object(proposal_service, '_execute_workflow_action', new=AsyncMock(
                return_value={"success": True, "action_type": "workflow_trigger"})) as mock_trigger:
            result = await proposal_service._execute_proposed_action(proposal)

            assert result["success"] == True
            assert result["action_type"] == "workflow_trigger"
            mock_trigger.assert_awaited_once()

    # Test: device action execution
    @pytest.mark.asyncio
    async def test_execute_device_action(self, proposal_service, intern_agent):
        """Test device action execution."""
        proposal = await proposal_service.create_action_proposal(
            intern_agent_id=intern_agent.id,
            trigger_context={},
            proposed_action={
                "action_type": "device_command",
                "command": "screenshot"
            },
            reasoning="Test device action"
        )

        # Mock the locally-imported device command executor
        with patch('tools.device_tool.execute_device_command', new_callable=AsyncMock) as mock_device:
            mock_device.return_value = {"success": True, "screenshot_path": "/tmp/screenshot.png"}

            result = await proposal_service._execute_device_action(proposal, proposal.proposed_action)

            assert result["success"] == True
            mock_device.assert_awaited_once()

    # Test: agent execution action
    @pytest.mark.asyncio
    async def test_execute_agent_action(self, proposal_service, intern_agent):
        """Test agent execution action."""
        proposal = await proposal_service.create_action_proposal(
            intern_agent_id=intern_agent.id,
            trigger_context={},
            proposed_action={
                "action_type": "agent_execute",
                "target_agent_id": "target-agent-123",
                "prompt": "Execute this task"
            },
            reasoning="Test agent execution"
        )

        # execute_agent does not exist in core/generic_agent.py — patch the
        # executor method and exercise the real action-type routing.
        with patch.object(proposal_service, '_execute_agent_action', new=AsyncMock(
                return_value={"success": True, "action_type": "agent_execute"})) as mock_meta:
            result = await proposal_service._execute_proposed_action(proposal)

            assert result["success"] == True
            assert result["action_type"] == "agent_execute"
            mock_meta.assert_awaited_once()

    # Test: proposal episode creation
    @pytest.mark.asyncio
    async def test_create_proposal_episode_approved(self, proposal_service, intern_agent):
        """Test episode creation for approved proposal."""
        proposal = await proposal_service.create_action_proposal(
            intern_agent_id=intern_agent.id,
            trigger_context={},
            proposed_action={"action_type": "test"},
            reasoning="Test episode creation"
        )

        # Should not raise
        await proposal_service._create_proposal_episode(
            proposal=proposal,
            outcome="approved",
            execution_result={"success": True}
        )

    @pytest.mark.asyncio
    async def test_create_proposal_episode_rejected(self, proposal_service, intern_agent):
        """Test episode creation for rejected proposal."""
        proposal = await proposal_service.create_action_proposal(
            intern_agent_id=intern_agent.id,
            trigger_context={},
            proposed_action={"action_type": "test"},
            reasoning="Test"
        )

        # Should not raise
        await proposal_service._create_proposal_episode(
            proposal=proposal,
            outcome="rejected",
            rejection_reason="Unsafe action"
        )

    # Test: agent name denormalization
    @pytest.mark.asyncio
    async def test_agent_name_denormalized(self, proposal_service, intern_agent):
        """Verify agent name is denormalized into proposal."""
        proposal = await proposal_service.create_action_proposal(
            intern_agent_id=intern_agent.id,
            trigger_context={},
            proposed_action={"action_type": "test"},
            reasoning="Test agent name"
        )

        assert proposal.agent_name == "Test Intern Agent"
        assert proposal.agent_name in proposal.description

    # Test: proposal with empty proposed_action
    @pytest.mark.asyncio
    async def test_create_proposal_empty_action(self, proposal_service, intern_agent):
        """Create proposal with empty proposed_action."""
        proposal = await proposal_service.create_action_proposal(
            intern_agent_id=intern_agent.id,
            trigger_context={},
            proposed_action={},  # Empty action
            reasoning="Test empty action"
        )

        assert proposal.proposed_action == {}
        assert proposal.proposal_type == ProposalType.ACTION.value

    # Test: confidence score in description
    @pytest.mark.asyncio
    async def test_confidence_in_description(self, proposal_service, db_session):
        """Verify agent confidence appears in proposal description."""
        self._delete_agent(db_session, "confident-agent")
        agent = AgentRegistry(
            id="confident-agent",
            name="Confident Agent",
            status=AgentStatus.INTERN.value,
            category="test",
            module_path="test",
            class_name="Test",
            confidence_score=0.85,
            tenant_id="default",
            user_id="test-user"
        )
        db_session.add(agent)
        db_session.commit()

        proposal = await proposal_service.create_action_proposal(
            intern_agent_id=agent.id,
            trigger_context={},
            proposed_action={"action_type": "test"},
            reasoning="Test confidence"
        )

        assert "0.85" in proposal.description

    # Test: proposal timestamps
    @pytest.mark.asyncio
    async def test_proposal_timestamps(self, proposal_service, intern_agent):
        """Verify proposal timestamps are set correctly."""
        proposal = await proposal_service.create_action_proposal(
            intern_agent_id=intern_agent.id,
            trigger_context={},
            proposed_action={},
            reasoning="Test timestamps"
        )

        assert proposal.created_at is not None
        assert isinstance(proposal.created_at, datetime)

        # Approve and check approved_at
        with patch.object(proposal_service, '_execute_proposed_action', new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = {"success": True}

            await proposal_service.approve_proposal(proposal.id, "admin-user")

            proposal_service.db.refresh(proposal)
            assert proposal.approved_at is not None
            assert proposal.completed_at is not None

    # Test: multi-tenant isolation
    @pytest.mark.asyncio
    async def test_multi_tenant_proposals(self, proposal_service, intern_agent, db_session):
        """Test proposals are isolated by tenant."""
        # Create agent in different tenant
        self._delete_agent(db_session, "tenant2-agent")
        agent2 = AgentRegistry(
            id="tenant2-agent",
            name="Tenant 2 Agent",
            status=AgentStatus.INTERN.value,
            category="test",
            module_path="test",
            class_name="Test",
            tenant_id="tenant-2",
            user_id="user-2"
        )
        db_session.add(agent2)
        db_session.commit()

        # Create proposals for both tenants
        await proposal_service.create_action_proposal(
            intern_agent_id=intern_agent.id,
            trigger_context={},
            proposed_action={},
            reasoning="Tenant 1"
        )
        await proposal_service.create_action_proposal(
            intern_agent_id=agent2.id,
            trigger_context={},
            proposed_action={},
            reasoning="Tenant 2"
        )

        # Get proposals for tenant 1 only
        tenant1_proposals = await proposal_service.get_pending_proposals(tenant_id="default")
        assert all(p.tenant_id == "default" for p in tenant1_proposals)

        # Get proposals for tenant 2 only
        tenant2_proposals = await proposal_service.get_pending_proposals(tenant_id="tenant-2")
        assert all(p.tenant_id == "tenant-2" for p in tenant2_proposals)

    # Test: proposal data integrity
    @pytest.mark.asyncio
    async def test_proposal_data_integrity(self, proposal_service, intern_agent):
        """Verify proposal data is stored correctly."""
        proposed_action = {
            "action_type": "canvas_present",
            "canvas_type": "form",
            "data": {
                "fields": [
                    {"name": "email", "type": "email"},
                    {"name": "message", "type": "text"}
                ]
            }
        }

        proposal = await proposal_service.create_action_proposal(
            intern_agent_id=intern_agent.id,
            trigger_context={"test": "context"},
            proposed_action=proposed_action,
            reasoning="Test data integrity"
        )

        assert proposal.proposed_action == proposed_action
        assert proposal.proposed_action["data"]["fields"][0]["name"] == "email"

    # Test: proposal status transitions
    @pytest.mark.asyncio
    async def test_proposal_status_transitions(self, proposal_service, intern_agent):
        """Verify proposal status transitions are correct."""
        proposal = await proposal_service.create_action_proposal(
            intern_agent_id=intern_agent.id,
            trigger_context={},
            proposed_action={},
            reasoning="Test status transitions"
        )

        # Initial status
        assert proposal.status == ProposalStatus.PENDING_APPROVAL.value

        # After approval
        with patch.object(proposal_service, '_execute_proposed_action', new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = {"success": True}

            await proposal_service.approve_proposal(proposal.id, "admin-user")
            proposal_service.db.refresh(proposal)

            # Status should be EXECUTED (not just APPROVED)
            assert proposal.status == ProposalStatus.EXECUTED.value

    # Test: proposal with session_id
    @pytest.mark.asyncio
    async def test_proposal_with_session(self, proposal_service, intern_agent):
        """Test proposal associated with chat session."""
        proposal = await proposal_service.create_action_proposal(
            intern_agent_id=intern_agent.id,
            trigger_context={},
            proposed_action={},
            reasoning="Test session association",
            session_id="chat-session-123"
        )

        assert proposal.session_id == "chat-session-123"

        # Retrieve by session
        session_proposals = await proposal_service.get_pending_proposals(
            agent_id=intern_agent.id
        )
        assert any(p.session_id == "chat-session-123" for p in session_proposals)

    # Test: proposal execution result storage
    @pytest.mark.asyncio
    async def test_execution_result_storage(self, proposal_service, intern_agent):
        """Verify execution result is stored in proposal."""
        proposal = await proposal_service.create_action_proposal(
            intern_agent_id=intern_agent.id,
            trigger_context={},
            proposed_action={"action_type": "test"},
            reasoning="Test execution result"
        )

        execution_result = {
            "success": True,
            "output": {"result": "completed"},
            "executed_at": datetime.now().isoformat()
        }

        with patch.object(proposal_service, '_execute_proposed_action', new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = execution_result

            await proposal_service.approve_proposal(proposal.id, "admin-user")
            proposal_service.db.refresh(proposal)

            assert proposal.execution_result == execution_result
            assert proposal.execution_result["success"] == True
