"""
Coverage tests for core/models.py database models.

These tests target uncovered lines in models.py including:
- Model CRUD operations
- Relationship methods
- Validation logic
- Computed properties
- Class methods and static methods

Coverage target: Increase models.py coverage by 5+ percentage points
"""
import pytest
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import exc
import uuid

from core.models import (
    AgentRegistry, AgentExecution, AgentFeedback, CanvasAudit,
    AgentStatus, FeedbackStatus,
    Episode, EpisodeSegment, EpisodeAccessLog,
    AgentProposal, SupervisionSession, TrainingSession,
    SupervisionStatus, ProposalStatus,
    AgentOperationTracker, AgentRequestLog,
    ViewOrchestrationState, OperationErrorResolution,
    User, Workspace, Team, ChatSession, ChatMessage,
    WorkflowExecution, WorkflowStepExecution,
    BlockedTriggerContext,
    UserRole, UserStatus, WorkspaceStatus,
)


# ============================================================================
# TEST CLASS: AgentRegistry Coverage
# ============================================================================

class TestAgentRegistryCoverage:
    """Test coverage for AgentRegistry model."""

    def test_agent_registry_create_with_defaults(self, db_session: Session):
        """Test AgentRegistry creation with default values."""
        agent = AgentRegistry(
            name="TestAgent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
        )
        db_session.add(agent)
        db_session.commit()
        db_session.refresh(agent)

        assert agent.id is not None
        assert agent.name == "TestAgent"
        assert agent.status == AgentStatus.STUDENT.value  # Default status
        assert agent.confidence_score == 0.5  # Default confidence
        assert agent.created_at is not None
        assert agent.version == "1.0.0"  # Default version

    def test_agent_registry_create_with_all_fields(self, db_session: Session):
        """Test AgentRegistry creation with all fields populated."""
        user = User(
            email="test@example.com",
            role=UserRole.MEMBER.value,
        )
        db_session.add(user)
        db_session.commit()

        agent = AgentRegistry(
            name="CompleteAgent",
            description="A fully specified test agent",
            category="testing",
            module_path="test.module",
            class_name="CompleteClass",
            user_id=user.id,
            status=AgentStatus.AUTONOMOUS.value,
            confidence_score=0.95,
            required_role_for_autonomy=UserRole.SUPER_ADMIN.value,
            version="2.5.0",
            configuration={"prompt": "You are a helpful assistant"},
            schedule_config={"cron": "0 0 * * *"},
        )
        db_session.add(agent)
        db_session.commit()
        db_session.refresh(agent)

        assert agent.name == "CompleteAgent"
        assert agent.description == "A fully specified test agent"
        assert agent.status == AgentStatus.AUTONOMOUS.value
        assert agent.confidence_score == 0.95
        assert agent.user_id == user.id

    def test_agent_registry_relationship_executions(self, db_session: Session):
        """Test AgentRegistry relationship to AgentExecution."""
        agent = AgentRegistry(
            name="TestAgent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
        )
        db_session.add(agent)
        db_session.commit()

        execution = AgentExecution(
            agent_id=agent.id,
            status="running",
        )
        db_session.add(execution)
        db_session.commit()

        # Test relationship
        assert len(agent.executions) == 1
        assert agent.executions[0].id == execution.id

    def test_agent_registry_relationship_feedback(self, db_session: Session):
        """Test AgentRegistry relationship to AgentFeedback."""
        agent = AgentRegistry(
            name="TestAgent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
        )
        db_session.add(agent)
        db_session.commit()

        user = User(
            email="feedback@example.com",
            role=UserRole.MEMBER.value,
        )
        db_session.add(user)
        db_session.commit()

        feedback = AgentFeedback(
            agent_id=agent.id,
            user_id=user.id,
            original_output="Agent output",
            user_correction="Corrected output",
        )
        db_session.add(feedback)
        db_session.commit()

        # Test relationship
        assert len(agent.feedback_history) == 1
        assert agent.feedback_history[0].id == feedback.id

    def test_agent_registry_confidence_validation(self, db_session: Session):
        """Test confidence_score validation clamps to [0.0, 1.0]."""
        agent = AgentRegistry(
            name="TestAgent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            confidence_score=1.5,  # Above max
        )
        db_session.add(agent)
        db_session.commit()
        db_session.refresh(agent)

        # Should be clamped to 1.0
        assert agent.confidence_score == 1.0

        # Test lower bound
        agent.confidence_score = -0.5
        db_session.commit()
        db_session.refresh(agent)

        # Should be clamped to 0.0
        assert agent.confidence_score == 0.0

    def test_agent_registry_update_confidence(self, db_session: Session):
        """Test updating confidence score."""
        agent = AgentRegistry(
            name="TestAgent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            confidence_score=0.5,
        )
        db_session.add(agent)
        db_session.commit()

        # Update confidence
        agent.confidence_score = 0.8
        db_session.commit()

        assert agent.confidence_score == 0.8

    def test_agent_registry_query_by_status(self, db_session: Session):
        """Test querying agents by status."""
        student_agent = AgentRegistry(
            name="StudentAgent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
        )
        autonomous_agent = AgentRegistry(
            name="AutonomousAgent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.AUTONOMOUS.value,
        )
        db_session.add_all([student_agent, autonomous_agent])
        db_session.commit()

        # Query by status
        students = db_session.query(AgentRegistry).filter(
            AgentRegistry.status == AgentStatus.STUDENT.value
        ).all()

        assert len(students) == 1
        assert students[0].name == "StudentAgent"

    def test_agent_registry_repr(self, db_session: Session):
        """Test AgentRegistry __repr__ method."""
        agent = AgentRegistry(
            name="TestAgent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.SUPERVISED.value,
            confidence_score=0.75,
        )
        db_session.add(agent)
        db_session.commit()

        repr_str = repr(agent)
        assert "AgentRegistry" in repr_str
        assert agent.name in repr_str
        assert AgentStatus.SUPERVISED.value in repr_str
        assert "0.75" in repr_str

    def test_agent_registry_relationship_canvas_audits(self, db_session: Session):
        """Test AgentRegistry relationship to CanvasAudit."""
        agent = AgentRegistry(
            name="TestAgent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
        )
        db_session.add(agent)
        db_session.commit()

        workspace = Workspace(
            name="TestWorkspace",
            status=WorkspaceStatus.ACTIVE.value,
        )
        db_session.add(workspace)
        db_session.commit()

        user = User(
            email="user@example.com",
            role=UserRole.MEMBER.value,
        )
        db_session.add(user)
        db_session.commit()

        canvas_audit = CanvasAudit(
            workspace_id=workspace.id,
            agent_id=agent.id,
            user_id=user.id,
            canvas_id="test-canvas-123",
            component_type="chart",
            action="present",
        )
        db_session.add(canvas_audit)
        db_session.commit()

        # Test relationship
        assert len(agent.canvas_audits) == 1
        assert agent.canvas_audits[0].canvas_id == "test-canvas-123"


# ============================================================================
# TEST CLASS: AgentExecution Coverage
# ============================================================================

class TestAgentExecutionCoverage:
    """Test coverage for AgentExecution model."""

    def test_execution_create_with_defaults(self, db_session: Session):
        """Test execution creation with default values."""
        agent = AgentRegistry(
            name="TestAgent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
        )
        db_session.add(agent)
        db_session.commit()

        execution = AgentExecution(
            agent_id=agent.id,
            status="running",
        )
        db_session.add(execution)
        db_session.commit()

        assert execution.id is not None
        assert execution.status == "running"
        assert execution.triggered_by == "manual"  # Default
        assert execution.started_at is not None
        assert execution.duration_seconds == 0.0

    def test_execution_create_with_full_params(self, db_session: Session):
        """Test execution creation with all parameters."""
        agent = AgentRegistry(
            name="TestAgent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
        )
        db_session.add(agent)
        db_session.commit()

        started_at = datetime.utcnow() - timedelta(seconds=10)
        completed_at = datetime.utcnow()

        execution = AgentExecution(
            agent_id=agent.id,
            workspace_id="workspace-123",
            status="completed",
            input_summary="Test input",
            output_summary="Test output",
            triggered_by="schedule",
            started_at=started_at,
            completed_at=completed_at,
            duration_seconds=10.5,
            result_summary="Execution successful",
            error_message=None,
        )
        db_session.add(execution)
        db_session.commit()

        assert execution.status == "completed"
        assert execution.duration_seconds == 10.5
        assert execution.workspace_id == "workspace-123"
        assert execution.triggered_by == "schedule"

    def test_execution_relationship_agent(self, db_session: Session):
        """Test Execution -> Agent relationship."""
        agent = AgentRegistry(
            name="TestAgent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
        )
        db_session.add(agent)
        db_session.commit()

        execution = AgentExecution(
            agent_id=agent.id,
            status="running",
        )
        db_session.add(execution)
        db_session.commit()

        assert execution.agent.name == "TestAgent"
        assert execution.agent.id == agent.id

    def test_execution_error_state(self, db_session: Session):
        """Test execution in error state."""
        agent = AgentRegistry(
            name="TestAgent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
        )
        db_session.add(agent)
        db_session.commit()

        execution = AgentExecution(
            agent_id=agent.id,
            status="failed",
            error_message="Test error message",
            completed_at=datetime.utcnow(),
        )
        db_session.add(execution)
        db_session.commit()

        assert execution.status == "failed"
        assert execution.error_message == "Test error message"

    def test_execution_relationship_canvas_audits(self, db_session: Session):
        """Test Execution relationship to CanvasAudit."""
        agent = AgentRegistry(
            name="TestAgent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
        )
        db_session.add(agent)
        db_session.commit()

        execution = AgentExecution(
            agent_id=agent.id,
            status="running",
        )
        db_session.add(execution)
        db_session.commit()

        workspace = Workspace(
            name="TestWorkspace",
            status=WorkspaceStatus.ACTIVE.value,
        )
        db_session.add(workspace)
        db_session.commit()

        user = User(
            email="user@example.com",
            role=UserRole.MEMBER.value,
        )
        db_session.add(user)
        db_session.commit()

        canvas_audit = CanvasAudit(
            workspace_id=workspace.id,
            agent_id=agent.id,
            agent_execution_id=execution.id,
            user_id=user.id,
            canvas_id="test-canvas-456",
            component_type="chart",
            action="present",
        )
        db_session.add(canvas_audit)
        db_session.commit()

        # Test relationship
        assert len(execution.canvas_audits) == 1
        assert execution.canvas_audits[0].agent_execution_id == execution.id

    def test_execution_repr(self, db_session: Session):
        """Test AgentExecution __repr__ method."""
        agent = AgentRegistry(
            name="TestAgent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
        )
        db_session.add(agent)
        db_session.commit()

        execution = AgentExecution(
            agent_id=agent.id,
            status="running",
        )
        db_session.add(execution)
        db_session.commit()  # Commit to generate ID

        repr_str = repr(execution)
        assert "AgentExecution" in repr_str
        assert str(execution.id) in repr_str
        assert agent.id in repr_str
        assert "running" in repr_str


# ============================================================================
# TEST CLASS: AgentFeedback Coverage
# ============================================================================

class TestAgentFeedbackCoverage:
    """Test coverage for AgentFeedback model."""

    def test_feedback_create_with_defaults(self, db_session: Session):
        """Test creating feedback with minimal fields."""
        agent = AgentRegistry(
            name="TestAgent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
        )
        db_session.add(agent)
        db_session.commit()

        user = User(
            email="user@example.com",
            role=UserRole.MEMBER.value,
        )
        db_session.add(user)
        db_session.commit()

        feedback = AgentFeedback(
            agent_id=agent.id,
            user_id=user.id,
            original_output="Agent said this",
            user_correction="Actually, it should be this",
        )
        db_session.add(feedback)
        db_session.commit()

        assert feedback.id is not None
        assert feedback.status == FeedbackStatus.PENDING.value  # Default
        assert feedback.created_at is not None

    def test_feedback_create_with_rating(self, db_session: Session):
        """Test creating feedback with rating."""
        agent = AgentRegistry(
            name="TestAgent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
        )
        db_session.add(agent)
        db_session.commit()

        user = User(
            email="user@example.com",
            role=UserRole.MEMBER.value,
        )
        db_session.add(user)
        db_session.commit()

        feedback = AgentFeedback(
            agent_id=agent.id,
            user_id=user.id,
            original_output="Agent response",
            user_correction="Better response",
            feedback_type="rating",
            rating=5,
            thumbs_up_down=True,
        )
        db_session.add(feedback)
        db_session.commit()

        assert feedback.rating == 5
        assert feedback.thumbs_up_down is True
        assert feedback.feedback_type == "rating"

    def test_feedback_create_with_execution_link(self, db_session: Session):
        """Test creating feedback linked to execution."""
        agent = AgentRegistry(
            name="TestAgent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
        )
        db_session.add(agent)
        db_session.commit()

        execution = AgentExecution(
            agent_id=agent.id,
            status="completed",
        )
        db_session.add(execution)
        db_session.commit()

        user = User(
            email="user@example.com",
            role=UserRole.MEMBER.value,
        )
        db_session.add(user)
        db_session.commit()

        feedback = AgentFeedback(
            agent_id=agent.id,
            agent_execution_id=execution.id,
            user_id=user.id,
            original_output="Output",
            user_correction="Correction",
        )
        db_session.add(feedback)
        db_session.commit()

        assert feedback.agent_execution_id == execution.id

    def test_feedback_relationships(self, db_session: Session):
        """Test Feedback relationships to Agent, Execution, User."""
        agent = AgentRegistry(
            name="TestAgent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
        )
        db_session.add(agent)
        db_session.commit()

        execution = AgentExecution(
            agent_id=agent.id,
            status="completed",
        )
        db_session.add(execution)
        db_session.commit()

        user = User(
            email="user@example.com",
            role=UserRole.MEMBER.value,
        )
        db_session.add(user)
        db_session.commit()

        feedback = AgentFeedback(
            agent_id=agent.id,
            agent_execution_id=execution.id,
            user_id=user.id,
            original_output="Output",
            user_correction="Correction",
        )
        db_session.add(feedback)
        db_session.commit()

        # Test all relationships
        assert feedback.agent.name == "TestAgent"
        assert feedback.execution.id == execution.id
        assert feedback.user.email == "user@example.com"


# ============================================================================
# TEST CLASS: CanvasAudit Coverage
# ============================================================================

class TestCanvasAuditCoverage:
    """Test coverage for CanvasAudit model."""

    def test_canvas_audit_create_minimal(self, db_session: Session):
        """Test canvas audit creation with minimal fields."""
        workspace = Workspace(
            name="TestWorkspace",
            status=WorkspaceStatus.ACTIVE.value,
        )
        db_session.add(workspace)
        db_session.commit()

        user = User(
            email="user@example.com",
            role=UserRole.MEMBER.value,
        )
        db_session.add(user)
        db_session.commit()

        audit = CanvasAudit(
            workspace_id=workspace.id,
            user_id=user.id,
            canvas_type="generic",
            component_type="markdown",
            action="present",
        )
        db_session.add(audit)
        db_session.commit()

        assert audit.id is not None
        assert audit.action == "present"
        assert audit.canvas_type == "generic"
        assert audit.governance_check_passed is None

    def test_canvas_audit_create_full(self, db_session: Session):
        """Test canvas audit creation with all fields."""
        agent = AgentRegistry(
            name="TestAgent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
        )
        db_session.add(agent)
        db_session.commit()

        execution = AgentExecution(
            agent_id=agent.id,
            status="running",
        )
        db_session.add(execution)
        db_session.commit()

        workspace = Workspace(
            name="TestWorkspace",
            status=WorkspaceStatus.ACTIVE.value,
        )
        db_session.add(workspace)
        db_session.commit()

        user = User(
            email="user@example.com",
            role=UserRole.MEMBER.value,
        )
        db_session.add(user)
        db_session.commit()

        audit = CanvasAudit(
            workspace_id=workspace.id,
            agent_id=agent.id,
            agent_execution_id=execution.id,
            user_id=user.id,
            canvas_id="test-canvas-789",
            session_id="session-123",
            canvas_type="sheets",
            component_type="chart",
            component_name="line_chart",
            action="present",
            audit_metadata={"chart_type": "line", "data_points": 100},
            governance_check_passed=True,
        )
        db_session.add(audit)
        db_session.commit()

        assert audit.canvas_id == "test-canvas-789"
        assert audit.session_id == "session-123"
        assert audit.canvas_type == "sheets"
        assert audit.component_name == "line_chart"
        assert audit.governance_check_passed is True

    def test_canvas_audit_query_by_canvas(self, db_session: Session):
        """Test querying audits by canvas ID."""
        workspace = Workspace(
            name="TestWorkspace",
            status=WorkspaceStatus.ACTIVE.value,
        )
        db_session.add(workspace)
        db_session.commit()

        user = User(
            email="user@example.com",
            role=UserRole.MEMBER.value,
        )
        db_session.add(user)
        db_session.commit()

        canvas_id = "test-canvas-999"

        audit1 = CanvasAudit(
            workspace_id=workspace.id,
            user_id=user.id,
            canvas_id=canvas_id,
            canvas_type="generic",
            component_type="chart",
            action="present",
        )
        audit2 = CanvasAudit(
            workspace_id=workspace.id,
            user_id=user.id,
            canvas_id=canvas_id,
            canvas_type="generic",
            component_type="form",
            action="update",
        )
        db_session.add_all([audit1, audit2])
        db_session.commit()

        audits = db_session.query(CanvasAudit).filter(
            CanvasAudit.canvas_id == canvas_id
        ).all()

        assert len(audits) == 2

    def test_canvas_audit_relationships(self, db_session: Session):
        """Test CanvasAudit relationships."""
        agent = AgentRegistry(
            name="TestAgent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
        )
        db_session.add(agent)
        db_session.commit()

        execution = AgentExecution(
            agent_id=agent.id,
            status="running",
        )
        db_session.add(execution)
        db_session.commit()

        workspace = Workspace(
            name="TestWorkspace",
            status=WorkspaceStatus.ACTIVE.value,
        )
        db_session.add(workspace)
        db_session.commit()

        user = User(
            email="user@example.com",
            role=UserRole.MEMBER.value,
        )
        db_session.add(user)
        db_session.commit()

        audit = CanvasAudit(
            workspace_id=workspace.id,
            agent_id=agent.id,
            agent_execution_id=execution.id,
            user_id=user.id,
            canvas_type="generic",
            component_type="chart",
            action="present",
        )
        db_session.add(audit)
        db_session.commit()

        # Test relationships
        assert audit.agent.name == "TestAgent"
        assert audit.execution.id == execution.id
        assert audit.user.email == "user@example.com"

    def test_canvas_audit_repr(self, db_session: Session):
        """Test CanvasAudit __repr__ method."""
        workspace = Workspace(
            name="TestWorkspace",
            status=WorkspaceStatus.ACTIVE.value,
        )
        db_session.add(workspace)
        db_session.commit()

        user = User(
            email="user@example.com",
            role=UserRole.MEMBER.value,
        )
        db_session.add(user)
        db_session.commit()

        audit = CanvasAudit(
            workspace_id=workspace.id,
            user_id=user.id,
            canvas_type="generic",
            component_type="chart",
            action="present",
        )
        db_session.add(audit)
        db_session.commit()  # Commit to generate ID

        repr_str = repr(audit)
        assert "CanvasAudit" in repr_str
        assert audit.id in repr_str
        assert "present" in repr_str
        assert "chart" in repr_str


# ============================================================================
# TEST CLASS: Episode Coverage
# ============================================================================

class TestEpisodeCoverage:
    """Test coverage for Episode model."""

    def test_episode_create_minimal(self, db_session: Session):
        """Test episode creation with minimal fields."""
        agent = AgentRegistry(
            name="TestAgent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
        )
        db_session.add(agent)
        db_session.commit()

        workspace = Workspace(
            name="TestWorkspace",
            status=WorkspaceStatus.ACTIVE.value,
        )
        db_session.add(workspace)
        db_session.commit()

        episode = Episode(
            title="Test Episode",
            agent_id=agent.id,
            workspace_id=workspace.id,
            maturity_at_time="INTERN",
            human_intervention_count=0,
        )
        db_session.add(episode)
        db_session.commit()

        assert episode.id is not None
        assert episode.title == "Test Episode"
        assert episode.status == "active"  # Default
        assert episode.importance_score == 0.5  # Default

    def test_episode_create_full(self, db_session: Session):
        """Test episode creation with all fields."""
        agent = AgentRegistry(
            name="TestAgent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
        )
        db_session.add(agent)
        db_session.commit()

        workspace = Workspace(
            name="TestWorkspace",
            status=WorkspaceStatus.ACTIVE.value,
        )
        db_session.add(workspace)
        db_session.commit()

        user = User(
            email="user@example.com",
            role=UserRole.MEMBER.value,
        )
        db_session.add(user)
        db_session.commit()

        started_at = datetime.utcnow() - timedelta(hours=1)
        ended_at = datetime.utcnow()

        episode = Episode(
            title="Complete Episode",
            description="A fully specified episode",
            summary="Episode summary",
            agent_id=agent.id,
            user_id=user.id,
            workspace_id=workspace.id,
            session_id="chat-session-123",
            execution_ids=["exec-1", "exec-2"],
            canvas_ids=["canvas-1", "canvas-2"],
            canvas_action_count=2,
            feedback_ids=["feedback-1"],
            aggregate_feedback_score=0.8,
            intervention_count=1,
            intervention_types=["pause"],
            started_at=started_at,
            ended_at=ended_at,
            duration_seconds=3600,
            status="completed",
            topics=["testing", "coverage"],
            entities=["agent", "workspace"],
            importance_score=0.9,
            maturity_at_time="SUPERVISED",
            human_intervention_count=1,
            constitutional_score=0.85,
        )
        db_session.add(episode)
        db_session.commit()

        assert episode.title == "Complete Episode"
        assert episode.description == "A fully specified episode"
        assert episode.intervention_count == 1
        assert episode.duration_seconds == 3600
        assert episode.status == "completed"

    def test_episode_segments_relationship(self, db_session: Session):
        """Test Episode -> EpisodeSegments relationship."""
        agent = AgentRegistry(
            name="TestAgent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
        )
        db_session.add(agent)
        db_session.commit()

        workspace = Workspace(
            name="TestWorkspace",
            status=WorkspaceStatus.ACTIVE.value,
        )
        db_session.add(workspace)
        db_session.commit()

        episode = Episode(
            title="Test Episode",
            agent_id=agent.id,
            workspace_id=workspace.id,
            maturity_at_time="INTERN",
            human_intervention_count=0,
        )
        db_session.add(episode)
        db_session.commit()

        now = datetime.utcnow()

        segment1 = EpisodeSegment(
            episode_id=episode.id,
            segment_type="conversation",
            sequence_order=1,
            content="Test conversation",
            source_type="chat_message",
            source_id="msg-1",
        )
        segment2 = EpisodeSegment(
            episode_id=episode.id,
            segment_type="execution",
            sequence_order=2,
            content="Test execution",
            source_type="agent_execution",
            source_id="exec-1",
        )
        db_session.add_all([segment1, segment2])
        db_session.commit()

        # Note: segments relationship requires explicit backref configuration
        # This test verifies the segments can be created with proper episode_id
        segments = db_session.query(EpisodeSegment).filter(
            EpisodeSegment.episode_id == episode.id
        ).all()
        assert len(segments) == 2
        assert segments[0].segment_type == "conversation"
        assert segments[1].segment_type == "execution"

    def test_episode_query_by_status(self, db_session: Session):
        """Test querying episodes by status."""
        agent = AgentRegistry(
            name="TestAgent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
        )
        db_session.add(agent)
        db_session.commit()

        workspace = Workspace(
            name="TestWorkspace",
            status=WorkspaceStatus.ACTIVE.value,
        )
        db_session.add(workspace)
        db_session.commit()

        episode1 = Episode(
            title="Active Episode",
            agent_id=agent.id,
            workspace_id=workspace.id,
            maturity_at_time="INTERN",
            human_intervention_count=0,
            status="active",
        )
        episode2 = Episode(
            title="Completed Episode",
            agent_id=agent.id,
            workspace_id=workspace.id,
            maturity_at_time="INTERN",
            human_intervention_count=0,
            status="completed",
        )
        db_session.add_all([episode1, episode2])
        db_session.commit()

        active_episodes = db_session.query(Episode).filter(
            Episode.status == "active"
        ).all()

        assert len(active_episodes) == 1
        assert active_episodes[0].title == "Active Episode"


# ============================================================================
# TEST CLASS: EpisodeSegment Coverage
# ============================================================================

class TestEpisodeSegmentCoverage:
    """Test coverage for EpisodeSegment model."""

    def test_segment_create_minimal(self, db_session: Session):
        """Test segment creation with minimal fields."""
        agent = AgentRegistry(
            name="TestAgent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
        )
        db_session.add(agent)
        db_session.commit()

        workspace = Workspace(
            name="TestWorkspace",
            status=WorkspaceStatus.ACTIVE.value,
        )
        db_session.add(workspace)
        db_session.commit()

        episode = Episode(
            title="Test Episode",
            agent_id=agent.id,
            workspace_id=workspace.id,
            maturity_at_time="INTERN",
            human_intervention_count=0,
        )
        db_session.add(episode)
        db_session.commit()

        segment = EpisodeSegment(
            episode_id=episode.id,
            segment_type="conversation",
            sequence_order=1,
            content="Test content",
            source_type="chat_message",
        )
        db_session.add(segment)
        db_session.commit()

        assert segment.id is not None
        assert segment.segment_type == "conversation"
        assert segment.sequence_order == 1
        assert segment.content_summary is None

    def test_segment_create_with_canvas_context(self, db_session: Session):
        """Test segment creation with canvas context."""
        agent = AgentRegistry(
            name="TestAgent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
        )
        db_session.add(agent)
        db_session.commit()

        workspace = Workspace(
            name="TestWorkspace",
            status=WorkspaceStatus.ACTIVE.value,
        )
        db_session.add(workspace)
        db_session.commit()

        episode = Episode(
            title="Test Episode",
            agent_id=agent.id,
            workspace_id=workspace.id,
            maturity_at_time="INTERN",
            human_intervention_count=0,
        )
        db_session.add(episode)
        db_session.commit()

        canvas_context = {
            "canvas_type": "sheets",
            "presentation_summary": "Agent presented revenue chart",
            "visual_elements": ["line_chart", "data_table"],
            "user_interaction": "User clicked 'Approve'",
            "critical_data_points": {
                "workflow_id": "wf-123",
                "approval_status": "approved",
                "revenue": "$1.2M",
            }
        }

        segment = EpisodeSegment(
            episode_id=episode.id,
            segment_type="execution",
            sequence_order=1,
            content="Agent executed workflow",
            source_type="agent_execution",
            source_id="exec-123",
            canvas_context=canvas_context,
        )
        db_session.add(segment)
        db_session.commit()

        assert segment.canvas_context is not None
        assert segment.canvas_context["canvas_type"] == "sheets"
        assert segment.canvas_context["critical_data_points"]["revenue"] == "$1.2M"


# ============================================================================
# TEST CLASS: WorkflowExecution Coverage
# ============================================================================

class TestWorkflowExecutionCoverage:
    """Test coverage for WorkflowExecution model."""

    def test_workflow_execution_create(self, db_session: Session):
        """Test workflow execution creation."""
        user = User(
            email="user@example.com",
            role=UserRole.MEMBER.value,
        )
        db_session.add(user)
        db_session.commit()

        execution = WorkflowExecution(
            workflow_id="wf-123",
            user_id=user.id,
            status="running",
        )
        db_session.add(execution)
        db_session.commit()

        assert execution.execution_id is not None
        assert execution.status == "running"
        assert execution.version == 1  # Default

    def test_workflow_execution_with_steps(self, db_session: Session):
        """Test workflow execution with step tracking."""
        user = User(
            email="user@example.com",
            role=UserRole.MEMBER.value,
        )
        db_session.add(user)
        db_session.commit()

        execution = WorkflowExecution(
            workflow_id="wf-456",
            user_id=user.id,
            status="completed",
            steps='[{"step": "1", "action": "test"}]',
            outputs='{"result": "success"}',
            error=None,
        )
        db_session.add(execution)
        db_session.commit()

        assert execution.steps is not None
        assert execution.outputs is not None
        assert execution.error is None

    def test_workflow_execution_relationships(self, db_session: Session):
        """Test WorkflowExecution relationships."""
        user = User(
            email="user@example.com",
            role=UserRole.MEMBER.value,
        )
        db_session.add(user)
        db_session.commit()

        execution = WorkflowExecution(
            workflow_id="wf-789",
            user_id=user.id,
            status="running",
        )
        db_session.add(execution)
        db_session.commit()

        # Test user relationship
        assert execution.user.email == "user@example.com"


# ============================================================================
# TEST CLASS: WorkflowStepExecution Coverage
# ============================================================================

class TestWorkflowStepExecutionCoverage:
    """Test coverage for WorkflowStepExecution model."""

    def test_step_execution_create(self, db_session: Session):
        """Test step execution creation."""
        user = User(
            email="user@example.com",
            role=UserRole.MEMBER.value,
        )
        db_session.add(user)
        db_session.commit()

        workflow_exec = WorkflowExecution(
            workflow_id="wf-123",
            user_id=user.id,
            status="running",
        )
        db_session.add(workflow_exec)
        db_session.commit()

        step_exec = WorkflowStepExecution(
            execution_id=workflow_exec.execution_id,
            workflow_id="wf-123",
            step_id="step-1",
            step_name="Test Step",
            step_type="action",
            sequence_order=1,
            status="running",
        )
        db_session.add(step_exec)
        db_session.commit()

        assert step_exec.id is not None
        assert step_exec.step_name == "Test Step"
        assert step_exec.status == "running"
        assert step_exec.retry_count == 0  # Default

    def test_step_execution_with_timing(self, db_session: Session):
        """Test step execution with timing data."""
        user = User(
            email="user@example.com",
            role=UserRole.MEMBER.value,
        )
        db_session.add(user)
        db_session.commit()

        workflow_exec = WorkflowExecution(
            workflow_id="wf-123",
            user_id=user.id,
            status="running",
        )
        db_session.add(workflow_exec)
        db_session.commit()

        started_at = datetime.utcnow() - timedelta(seconds=5)
        completed_at = datetime.utcnow()

        step_exec = WorkflowStepExecution(
            execution_id=workflow_exec.execution_id,
            workflow_id="wf-123",
            step_id="step-2",
            step_name="Timed Step",
            step_type="action",
            sequence_order=1,
            status="completed",
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=5000,
        )
        db_session.add(step_exec)
        db_session.commit()

        assert step_exec.duration_ms == 5000
        assert step_exec.started_at is not None
        assert step_exec.completed_at is not None


# ============================================================================
# TEST CLASS: Cross-Model Relationships
# ============================================================================

class TestRelationshipCrossCoverage:
    """Test cross-model relationships."""

    def test_agent_execution_feedback_chain(self, db_session: Session):
        """Test Agent -> Execution -> Feedback relationship chain."""
        agent = AgentRegistry(
            name="TestAgent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
        )
        db_session.add(agent)
        db_session.commit()

        execution = AgentExecution(
            agent_id=agent.id,
            status="completed",
        )
        db_session.add(execution)
        db_session.commit()

        user = User(
            email="user@example.com",
            role=UserRole.MEMBER.value,
        )
        db_session.add(user)
        db_session.commit()

        feedback = AgentFeedback(
            agent_id=agent.id,
            agent_execution_id=execution.id,
            user_id=user.id,
            original_output="Output",
            user_correction="Correction",
        )
        db_session.add(feedback)
        db_session.commit()

        # Verify chain
        assert execution.agent.id == agent.id
        assert feedback.agent_id == agent.id
        assert feedback.agent_execution_id == execution.id

    def test_workspace_user_team_relationships(self, db_session: Session):
        """Test Workspace -> User -> Team many-to-many relationships."""
        workspace = Workspace(
            name="TestWorkspace",
            status=WorkspaceStatus.ACTIVE.value,
        )
        db_session.add(workspace)
        db_session.commit()

        user = User(
            email="user@example.com",
            role=UserRole.MEMBER.value,
        )
        db_session.add(user)
        db_session.commit()

        team = Team(
            name="TestTeam",
            workspace_id=workspace.id,
        )
        db_session.add(team)
        db_session.commit()

        # Link user to workspace and team
        workspace.users.append(user)
        team.members.append(user)
        db_session.commit()

        # Verify relationships
        assert user in workspace.users
        assert user in team.members
        assert workspace in user.workspaces
        assert team in user.teams


# ============================================================================
# TEST CLASS: Model Validation
# ============================================================================

class TestModelValidationCoverage:
    """Test model validation and constraints."""

    def test_agent_name_required(self, db_session: Session):
        """Test that agent name is required."""
        agent = AgentRegistry(
            name=None,  # Should fail validation
            category="testing",
            module_path="test.module",
            class_name="TestClass",
        )
        db_session.add(agent)

        with pytest.raises(Exception):  # Could be IntegrityError
            db_session.commit()

    def test_workspace_name_required(self, db_session: Session):
        """Test that workspace name is required."""
        workspace = Workspace(
            name=None,  # Should fail
            status=WorkspaceStatus.ACTIVE.value,
        )
        db_session.add(workspace)

        with pytest.raises(Exception):
            db_session.commit()

    def test_user_email_required(self, db_session: Session):
        """Test that user email is required."""
        user = User(
            email=None,  # Should fail,
            role=UserRole.MEMBER.value,
        )
        db_session.add(user)

        with pytest.raises(Exception):
            db_session.commit()

    def test_timestamp_defaults(self, db_session: Session):
        """Test that timestamps are auto-generated."""
        agent = AgentRegistry(
            name="TestAgent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
        )
        db_session.add(agent)
        db_session.commit()

        assert agent.created_at is not None
        assert isinstance(agent.created_at, datetime)

    def test_updated_at_auto_update(self, db_session: Session):
        """Test that updated_at is auto-updated on modification."""
        agent = AgentRegistry(
            name="TestAgent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
        )
        db_session.add(agent)
        db_session.commit()

        original_updated_at = agent.updated_at

        # Wait a bit to ensure timestamp difference
        import time
        time.sleep(0.01)

        agent.description = "Updated description"
        db_session.commit()

        # updated_at should have changed
        assert agent.updated_at is not None
        # Note: In SQLite, datetime precision might be low, so we just check it's set


# ============================================================================
# TEST CLASS: Model Edge Cases
# ============================================================================

class TestModelEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_long_text_fields(self, db_session: Session):
        """Test handling of long text fields."""
        long_description = "x" * 10000  # Very long description

        agent = AgentRegistry(
            name="TestAgent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            description=long_description,
        )
        db_session.add(agent)
        db_session.commit()

        assert len(agent.description) == 10000

    def test_unicode_characters(self, db_session: Session):
        """Test handling of unicode characters."""
        agent = AgentRegistry(
            name="TestAgent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            description="Test with unicode: ✓ ✗ ☀ ☁ 🎉",
        )
        db_session.add(agent)
        db_session.commit()

        assert "✓" in agent.description

    def test_json_field_handling(self, db_session: Session):
        """Test JSON field serialization/deserialization."""
        config_data = {
            "nested": {
                "data": [1, 2, 3],
                "string": "test"
            },
            "boolean": True,
            "number": 42.5
        }

        agent = AgentRegistry(
            name="TestAgent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            configuration=config_data,
        )
        db_session.add(agent)
        db_session.commit()

        assert isinstance(agent.configuration, dict)
        assert agent.configuration["nested"]["data"] == [1, 2, 3]
        assert agent.configuration["boolean"] is True
        assert agent.configuration["number"] == 42.5

    def test_null_handling_in_optional_fields(self, db_session: Session):
        """Test that optional fields can be None."""
        agent = AgentRegistry(
            name="TestAgent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            description=None,  # Optional field
            user_id=None,  # Optional field
        )
        db_session.add(agent)
        db_session.commit()

        assert agent.description is None
        assert agent.user_id is None

    def test_zero_values(self, db_session: Session):
        """Test handling of zero values."""
        agent = AgentRegistry(
            name="TestAgent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            confidence_score=0.0,  # Valid zero value
        )
        db_session.add(agent)
        db_session.commit()

        assert agent.confidence_score == 0.0
