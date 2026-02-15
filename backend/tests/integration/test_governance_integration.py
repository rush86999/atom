"""
Governance integration tests with database.

Tests cover governance flows that require real database operations:
- Agent registration and maturity updates with database persistence
- Governance cache synchronization with database
- Agent execution record creation with full lifecycle
- Permission checks with database
- Audit trail persistence and querying
- Trigger interceptor database operations
- Proposal creation and approval workflow
- Training session tracking

Uses transaction rollback pattern for test isolation.
"""

import pytest
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from enum import Enum

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.models import (
    AgentRegistry,
    AgentExecution,
    AgentFeedback,
    BlockedTriggerContext,
    AgentProposal,
    ProposalStatus,
    ProposalType,
    SupervisionSession,
    SupervisionStatus,
    TrainingSession,
    TriggerSource,
    User,
    UserRole,
    AgentStatus as AgentStatusEnum
)

# Use the AgentStatus enum from models
AgentStatus = AgentStatusEnum
from core.agent_governance_service import AgentGovernanceService
from core.governance_cache import GovernanceCache
from core.trigger_interceptor import TriggerInterceptor
from tests.factories.agent_factory import (
    AgentFactory,
    StudentAgentFactory,
    InternAgentFactory,
    SupervisedAgentFactory,
    AutonomousAgentFactory
)
from tests.factories.user_factory import UserFactory


class TestAgentGovernanceIntegration:
    """Test agent governance with database persistence."""

    def test_register_agent_with_database(self, db_session: Session):
        """Test agent creation and query from database."""
        # Create agent directly in database
        agent = AgentRegistry(
            name="TestAgent",
            description="Test agent for governance",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.INTERN.value,
            confidence_score=0.6,
            user_id="test-user"
        )
        db_session.add(agent)
        db_session.commit()
        db_session.refresh(agent)

        # Verify agent exists in database
        retrieved = db_session.query(AgentRegistry).filter(
            AgentRegistry.id == agent.id
        ).first()

        assert retrieved is not None
        assert retrieved.name == "TestAgent"
        assert retrieved.status == AgentStatus.INTERN.value

    def test_update_agent_maturity(self, db_session: Session):
        """Test updating agent maturity and verifying persistence."""
        # Create agent
        agent = StudentAgentFactory(name="PromotionAgent", _session=db_session)
        db_session.commit()

        # Update maturity
        agent.status = AgentStatus.SUPERVISED.value
        agent.confidence_score = 0.8
        db_session.commit()

        # Query and verify
        retrieved = db_session.query(AgentRegistry).filter(
            AgentRegistry.id == agent.id
        ).first()

        assert retrieved.status == AgentStatus.SUPERVISED.value
        assert retrieved.confidence_score == 0.8

    def test_agent_execution_record_creation(self, db_session: Session):
        """Test full agent execution record lifecycle with database."""
        # Create agent
        agent = AgentFactory(name="ExecutionAgent", _session=db_session)
        db_session.commit()

        # Create execution record
        execution = AgentExecution(
            agent_id=agent.id,
            status="running",
            input_summary="Test input",
            triggered_by="manual",
            started_at=datetime.utcnow()
        )
        db_session.add(execution)
        db_session.commit()

        # Update execution
        execution.status = "completed"
        execution.completed_at = datetime.utcnow()
        execution.duration_seconds = 2.5
        execution.result_summary = "Test completed"
        db_session.commit()

        # Verify full lifecycle
        retrieved = db_session.query(AgentExecution).filter(
            AgentExecution.id == execution.id
        ).first()

        assert retrieved.status == "completed"
        assert retrieved.duration_seconds == 2.5
        assert retrieved.result_summary == "Test completed"

    def test_permission_check_with_database(self, db_session: Session):
        """Test permission checks using database agent data."""
        # Create agents with different maturity levels
        student = StudentAgentFactory(name="StudentAgent", _session=db_session)
        intern = InternAgentFactory(name="InternAgent", _session=db_session)
        supervised = SupervisedAgentFactory(name="SupervisedAgent", _session=db_session)
        autonomous = AutonomousAgentFactory(name="AutonomousAgent", _session=db_session)
        db_session.commit()

        # Query and check permissions
        # STUDENT agents cannot execute automated triggers
        student_agent = db_session.query(AgentRegistry).filter(
            AgentRegistry.id == student.id
        ).first()
        assert student_agent.status == AgentStatus.STUDENT.value

        # INTERN agents can stream presentations
        intern_agent = db_session.query(AgentRegistry).filter(
            AgentRegistry.id == intern.id
        ).first()
        assert intern_agent.status == AgentStatus.INTERN.value

        # SUPERVISED agents can execute state changes
        supervised_agent = db_session.query(AgentRegistry).filter(
            AgentRegistry.id == supervised.id
        ).first()
        assert supervised_agent.status == AgentStatus.SUPERVISED.value

        # AUTONOMOUS agents can do critical operations
        autonomous_agent = db_session.query(AgentRegistry).filter(
            AgentRegistry.id == autonomous.id
        ).first()
        assert autonomous_agent.status == AgentStatus.AUTONOMOUS.value

    def test_audit_trail_persistence(self, db_session: Session):
        """Test audit trail creation and querying."""
        # Create agent and execution
        agent = AgentFactory(name="AuditAgent", _session=db_session)
        execution = AgentExecution(
            agent_id=agent.id,
            status="running",
            triggered_by="manual"
        )
        db_session.add(execution)
        db_session.commit()

        # Create audit trail (feedback)
        feedback = AgentFeedback(
            agent_id=agent.id,
            agent_execution_id=execution.id,
            user_id="test-user",
            rating=5,
            original_output="Excellent performance",
            user_correction="Great work"
        )
        db_session.add(feedback)
        db_session.commit()

        # Query audit trail
        audit_records = db_session.query(AgentFeedback).filter(
            AgentFeedback.agent_id == agent.id
        ).all()

        assert len(audit_records) > 0
        assert audit_records[0].rating == 5
        assert "Excellent" in audit_records[0].original_output

    def test_multiple_executions_query(self, db_session: Session):
        """Test querying multiple executions for an agent."""
        # Create agent
        agent = AgentFactory(name="MultiExecAgent", _session=db_session)
        db_session.commit()

        # Create multiple executions
        for i in range(5):
            execution = AgentExecution(
                agent_id=agent.id,
                status="completed",
                triggered_by="manual",
                duration_seconds=1.0 + i * 0.5,
                started_at=datetime.utcnow()
            )
            db_session.add(execution)
        db_session.commit()

        # Query executions
        executions = db_session.query(AgentExecution).filter(
            AgentExecution.agent_id == agent.id
        ).all()

        assert len(executions) >= 5

    def test_agent_status_filter(self, db_session: Session):
        """Test filtering agents by status."""
        # Create agents with different statuses
        active = AgentFactory(
            name="ActiveAgent",
            status=AgentStatus.AUTONOMOUS,
            _session=db_session
        )
        inactive = AgentFactory(
            name="InactiveAgent",
            status=AgentStatus.PAUSED,
            _session=db_session
        )
        archived = AgentFactory(
            name="ArchivedAgent",
            status=AgentStatus.DEPRECATED,
            _session=db_session
        )
        db_session.commit()

        # Query autonomous agents
        autonomous_agents = db_session.query(AgentRegistry).filter(
            AgentRegistry.status == AgentStatus.AUTONOMOUS
        ).all()

        assert len(autonomous_agents) >= 1
        assert any(a.name == "ActiveAgent" for a in autonomous_agents)


class TestTriggerInterceptorIntegration:
    """Test trigger interceptor with database operations."""

    def test_blocked_trigger_context_saved(self, db_session: Session):
        """Test that blocked triggers are saved to database."""
        # Create student agent
        agent = StudentAgentFactory(name="BlockedAgent", _session=db_session)
        user = UserFactory(email="blocked@test.com", _session=db_session)
        db_session.commit()

        # Create blocked trigger context
        blocked_context = BlockedTriggerContext(
            agent_id=agent.id,
            agent_name=agent.name,
            agent_maturity_at_block=AgentStatus.STUDENT.value,
            confidence_score_at_block=agent.confidence_score,
            trigger_source=TriggerSource.WORKFLOW_ENGINE.value,
            trigger_type="workflow_trigger",
            trigger_context={"workflow_id": "test-workflow"},
            routing_decision="training",
            block_reason="STUDENT maturity blocks automated triggers"
        )
        db_session.add(blocked_context)
        db_session.commit()

        # Verify blocked context was saved
        retrieved = db_session.query(BlockedTriggerContext).filter(
            BlockedTriggerContext.agent_id == agent.id
        ).first()

        assert retrieved is not None
        assert retrieved.resolved == False
        assert "STUDENT" in retrieved.block_reason

    def test_query_blocked_triggers_by_agent(self, db_session: Session):
        """Test querying blocked triggers for a specific agent."""
        # Create student agent
        agent = StudentAgentFactory(name="MultiBlockedAgent", _session=db_session)
        user = UserFactory(email="multi-blocked@test.com", _session=db_session)
        db_session.commit()

        # Create multiple blocked contexts
        for i in range(3):
            blocked = BlockedTriggerContext(
                agent_id=agent.id,
                agent_name=agent.name,
                agent_maturity_at_block=AgentStatus.STUDENT.value,
                confidence_score_at_block=agent.confidence_score,
                trigger_source=TriggerSource.MANUAL.value,
                trigger_type=f"trigger_{i}",
                trigger_context={"index": i},
                routing_decision="training",
                block_reason=f"STUDENT maturity blocks trigger {i}"
            )
            db_session.add(blocked)
        db_session.commit()

        # Query blocked triggers
        blocked_triggers = db_session.query(BlockedTriggerContext).filter(
            BlockedTriggerContext.agent_id == agent.id
        ).all()

        assert len(blocked_triggers) >= 3

    def test_blocked_trigger_time_range(self, db_session: Session):
        """Test querying blocked triggers within time range."""
        # Create student agent
        agent = StudentAgentFactory(name="TimeRangeAgent", _session=db_session)
        user = UserFactory(email="timerange@test.com", _session=db_session)
        db_session.commit()

        now = datetime.utcnow()

        # Create blocked context at specific time
        blocked = BlockedTriggerContext(
            agent_id=agent.id,
            agent_name=agent.name,
            agent_maturity_at_block=AgentStatus.STUDENT.value,
            confidence_score_at_block=agent.confidence_score,
            trigger_source=TriggerSource.DATA_SYNC.value,
            trigger_type="test_trigger",
            trigger_context={},
            routing_decision="training",
            block_reason="Test time range query",
            created_at=now
        )
        db_session.add(blocked)
        db_session.commit()

        # Query within time range
        recent_blocked = db_session.query(BlockedTriggerContext).filter(
            and_(
                BlockedTriggerContext.agent_id == agent.id,
                BlockedTriggerContext.created_at >= now - timedelta(minutes=5)
            )
        ).all()

        assert len(recent_blocked) >= 1


class TestProposalWorkflowIntegration:
    """Test proposal creation and approval workflow with database."""

    def test_proposal_creation_and_approval(self, db_session: Session):
        """Test full proposal lifecycle from creation to approval."""
        # Create intern agent
        agent = InternAgentFactory(name="ProposalAgent", _session=db_session)
        user = UserFactory(email="proposal@test.com", _session=db_session)
        db_session.commit()

        # Create proposal
        proposal = AgentProposal(
            agent_id=agent.id,
            agent_name=agent.name,
            proposal_type=ProposalType.ACTION.value,
            title="Delete record proposal",
            description="Test proposal for integration",
            proposed_action={"record_id": "test-123"},
            reasoning="Test proposal for integration",
            proposed_by=agent.id
        )
        db_session.add(proposal)
        db_session.commit()

        # Update proposal status
        proposal.status = ProposalStatus.APPROVED.value
        proposal.reviewed_at = datetime.utcnow()
        proposal.review_comments="Approved for testing"
        db_session.commit()

        # Verify proposal lifecycle
        retrieved = db_session.query(AgentProposal).filter(
            AgentProposal.id == proposal.id
        ).first()

        assert retrieved.status == ProposalStatus.APPROVED.value
        assert retrieved.review_comments == "Approved for testing"

    def test_query_pending_proposals(self, db_session: Session):
        """Test querying pending proposals."""
        # Create agent and user
        agent = InternAgentFactory(name="PendingProposalAgent", _session=db_session)
        user = UserFactory(email="pending@test.com", _session=db_session)
        db_session.commit()

        # Create multiple proposals
        for i in range(3):
            proposal = AgentProposal(
                agent_id=agent.id,
                agent_name=agent.name,
                proposal_type=ProposalType.ACTION.value,
                title=f"Action {i}",
                description="Test pending proposal",
                proposed_action={"action": f"action_{i}"},
                reasoning="Test pending proposal",
                proposed_by=agent.id
            )
            db_session.add(proposal)
        db_session.commit()

        # Query pending proposals
        pending = db_session.query(AgentProposal).filter(
            and_(
                AgentProposal.agent_id == agent.id,
                AgentProposal.status == ProposalStatus.PROPOSED
            )
        ).all()

        assert len(pending) >= 3

    def test_proposal_rejection(self, db_session: Session):
        """Test proposal rejection."""
        # Create agent and user
        agent = InternAgentFactory(name="RejectAgent", _session=db_session)
        user = UserFactory(email="reject@test.com", _session=db_session)
        db_session.commit()

        # Create and reject proposal
        proposal = AgentProposal(
            agent_id=agent.id,
            agent_name=agent.name,
            proposal_type=ProposalType.ACTION.value,
            title="Risky action",
            description="Test rejection",
            proposed_action={"action": "risky_action"},
            reasoning="Test rejection",
            proposed_by=agent.id
        )
        db_session.add(proposal)
        db_session.commit()

        # Reject proposal
        proposal.status = ProposalStatus.REJECTED.value
        proposal.reviewed_at = datetime.utcnow()
        proposal.review_comments="Too risky"
        db_session.commit()

        # Verify rejection
        retrieved = db_session.query(AgentProposal).filter(
            AgentProposal.id == proposal.id
        ).first()

        assert retrieved.status == ProposalStatus.REJECTED.value
        assert "Too risky" in retrieved.review_comments


class TestTrainingSessionIntegration:
    """Test training session tracking with database."""

    def test_training_session_tracking(self, db_session: Session):
        """Test creating and tracking training sessions."""
        # Create student agent
        agent = StudentAgentFactory(name="TrainingAgent", _session=db_session)
        user = UserFactory(email="training@test.com", _session=db_session)
        db_session.commit()

        # Create a proposal first (required for TrainingSession)
        proposal = AgentProposal(
            agent_id=agent.id,
            agent_name=agent.name,
            proposal_type=ProposalType.TRAINING.value,
            title="Basic Workflow Execution",
            description="Scenario based training",
            reasoning="Test training session",
            proposed_by=agent.id
        )
        db_session.add(proposal)
        db_session.commit()

        # Create training session
        session = TrainingSession(
            proposal_id=proposal.id,
            agent_id=agent.id,
            agent_name=agent.name,
            supervisor_id=user.id,
            status="in_progress",
            started_at=datetime.utcnow()
        )
        db_session.add(session)
        db_session.commit()

        # Update session
        session.status = "completed"
        session.completed_at = datetime.utcnow()
        session.performance_score = 0.95
        db_session.commit()

        # Verify training session
        retrieved = db_session.query(TrainingSession).filter(
            TrainingSession.id == session.id
        ).first()

        assert retrieved.status == "completed"
        assert retrieved.performance_score == 0.95

    def test_query_training_sessions_by_agent(self, db_session: Session):
        """Test querying training sessions for an agent."""
        # Create student agent
        agent = StudentAgentFactory(name="MultiTrainingAgent", _session=db_session)
        user = UserFactory(email="multi-training@test.com", _session=db_session)
        db_session.commit()

        # Create multiple training sessions
        for i in range(3):
            # Create proposal first
            proposal = AgentProposal(
                agent_id=agent.id,
                agent_name=agent.name,
                proposal_type=ProposalType.TRAINING.value,
                title=f"Scenario {i}",
                description=f"Training scenario {i}",
                reasoning="Test training session",
                proposed_by=agent.id
            )
            db_session.add(proposal)
            db_session.commit()

            session = TrainingSession(
                proposal_id=proposal.id,
                agent_id=agent.id,
                agent_name=agent.name,
                supervisor_id=user.id,
                status="completed",
                performance_score=0.8 + (i * 0.05),
                started_at=datetime.utcnow(),
                completed_at=datetime.utcnow()
            )
            db_session.add(session)
        db_session.commit()

        # Query training sessions
        sessions = db_session.query(TrainingSession).filter(
            TrainingSession.agent_id == agent.id
        ).all()

        assert len(sessions) >= 3

    def test_supervision_session_tracking(self, db_session: Session):
        """Test supervision session database operations."""
        # Create supervised agent
        agent = SupervisedAgentFactory(name="SupervisedAgent", _session=db_session)
        user = UserFactory(email="supervision@test.com", _session=db_session)
        db_session.commit()

        # Create supervision session
        supervision = SupervisionSession(
            agent_id=agent.id,
            agent_name=agent.name,
            supervisor_id=user.id,
            workspace_id="test-workspace",
            trigger_context={"workflow_id": "test-workflow"},
            status=SupervisionStatus.RUNNING.value,
            started_at=datetime.utcnow()
        )
        db_session.add(supervision)
        db_session.commit()

        # Update supervision
        supervision.status = SupervisionStatus.COMPLETED.value
        supervision.completed_at = datetime.utcnow()
        supervision.intervention_count = 2
        db_session.commit()

        # Verify supervision session
        retrieved = db_session.query(SupervisionSession).filter(
            SupervisionSession.id == supervision.id
        ).first()

        assert retrieved.status == SupervisionStatus.COMPLETED
        assert retrieved.intervention_count == 2


class TestGovernanceDatabaseQueries:
    """Test governance-related database queries and aggregations."""

    def test_count_agents_by_maturity(self, db_session: Session):
        """Test counting agents grouped by maturity level."""
        from sqlalchemy import func

        # Create agents with different maturity levels
        StudentAgentFactory(name="CountStudent1", _session=db_session)
        StudentAgentFactory(name="CountStudent2", _session=db_session)
        InternAgentFactory(name="CountIntern", _session=db_session)
        SupervisedAgentFactory(name="CountSupervised", _session=db_session)
        db_session.commit()

        # Count by maturity
        result = db_session.query(
            AgentRegistry.status,
            func.count(AgentRegistry.id)
        ).group_by(AgentRegistry.status).all()

        maturity_counts = {row[0]: row[1] for row in result}
        assert maturity_counts.get(AgentStatus.STUDENT.value, 0) >= 2

    def test_query_recent_executions(self, db_session: Session):
        """Test querying recent executions across all agents."""
        # Create agent and executions
        agent = AgentFactory(name="RecentExecAgent", _session=db_session)
        db_session.commit()

        for i in range(5):
            execution = AgentExecution(
                agent_id=agent.id,
                status="completed",
                triggered_by="manual",
                started_at=datetime.utcnow()
            )
            db_session.add(execution)
        db_session.commit()

        # Query recent executions
        recent = db_session.query(AgentExecution).order_by(
            AgentExecution.started_at.desc()
        ).limit(10).all()

        assert len(recent) >= 5

    def test_agent_feedback_aggregation(self, db_session: Session):
        """Test aggregating feedback scores for an agent."""
        from sqlalchemy import func

        # Create agent and feedback
        agent = AgentFactory(name="FeedbackAgent", _session=db_session)
        db_session.commit()

        ratings = [5, 4, 5, 3, 4]
        for rating in ratings:
            feedback = AgentFeedback(
                agent_id=agent.id,
                user_id="test-user",
                rating=rating,
                original_output="Test feedback",
                user_correction="No correction needed"
            )
            db_session.add(feedback)
        db_session.commit()

        # Calculate average rating
        avg_rating = db_session.query(
            func.avg(AgentFeedback.rating)
        ).filter(
            AgentFeedback.agent_id == agent.id
        ).scalar()

        expected_avg = sum(ratings) / len(ratings)
        assert abs(avg_rating - expected_avg) < 0.01
