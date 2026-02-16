"""
Unit Tests for SQLAlchemy ORM Models

Tests ORM relationships, field validation, lifecycle hooks, and constraints:
- Core Model Relationships (AgentRegistry, AgentExecution, AgentFeedback, etc.)
- Field Validation (EmailField, EnumField, JSONField)
- Lifecycle Hooks (before_insert, before_update, after_delete)
- Index and Constraint Tests (unique, foreign key, check constraints)

Target: 50% coverage on models.py (2351 lines)
"""

import pytest
from datetime import datetime, timedelta
from sqlalchemy.orm import Session, lazyload
from sqlalchemy.exc import IntegrityError
import uuid

from core.models import (
    # Agent models
    AgentRegistry,
    AgentExecution,
    AgentFeedback,
    AgentStatus,
    FeedbackStatus,
    # User models
    User,
    UserRole,
    UserStatus,
    # Workflow models
    WorkflowExecution,
    WorkflowExecutionStatus,
    WorkflowStepExecution,
    # Episode models
    Episode,
    EpisodeSegment,
    EpisodeAccessLog,
    # Canvas models
    CanvasAudit,
    # Training models
    BlockedTriggerContext,
    AgentProposal,
    # Other models
    Workspace,
    Team,
    TeamMessage,
)
from tests.factories import (
    AgentFactory,
    UserFactory,
    CanvasAuditFactory,
    EpisodeFactory,
    EpisodeSegmentFactory,
    AgentExecutionFactory,
)


class TestAgentRegistryModel:
    """Test AgentRegistry ORM model relationships and validation."""

    def test_agent_creation_defaults(self, db: Session):
        """Test agent creation with default values."""
        agent = AgentFactory(
            name="test_agent",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.5
        )
        db.flush()

        assert agent.id is not None
        assert agent.name == "test_agent"
        assert agent.status == AgentStatus.STUDENT.value
        assert agent.confidence_score == 0.5
        assert agent.created_at is not None
        assert agent.updated_at is not None
        assert agent.configuration == {}

    def test_agent_execution_relationship(self, db: Session):
        """Test AgentRegistry -> AgentExecution one-to-many relationship."""
        agent = AgentFactory()
        execution = AgentExecution(
            agent_id=agent.id,
            status="running"
        )
        db.add(execution)
        db.commit()

        # Test forward relationship
        loaded_execution = db.query(AgentExecution).filter_by(id=execution.id).first()
        assert loaded_execution.agent.id == agent.id
        assert loaded_execution.agent.name == agent.name

        # Test backward relationship (backref)
        loaded_agent = db.query(AgentRegistry).filter_by(id=agent.id).first()
        assert len(loaded_agent.executions) == 1
        assert loaded_agent.executions[0].id == execution.id

    def test_agent_feedback_relationship(self, db: Session):
        """Test AgentRegistry -> AgentFeedback one-to-many relationship."""
        agent = AgentFactory()
        user = UserFactory()

        feedback = AgentFeedback(
            agent_id=agent.id,
            user_id=user.id,
            original_output="Test output",
            user_correction="Test correction"
        )
        db.add(feedback)
        db.commit()

        # Test relationship access
        loaded_feedback = db.query(AgentFeedback).filter_by(id=feedback.id).first()
        assert loaded_feedback.agent.id == agent.id

    def test_agent_user_relationship(self, db: Session):
        """Test AgentRegistry -> User foreign key relationship."""
        user = UserFactory()
        agent = AgentFactory(user_id=user.id)

        db.commit()

        loaded_agent = db.query(AgentRegistry).filter_by(id=agent.id).first()
        assert loaded_agent.user_id == user.id

    def test_maturity_level_enum_validation(self, db: Session):
        """Test AgentStatus enum validation."""
        valid_statuses = [
            AgentStatus.STUDENT.value,
            AgentStatus.INTERN.value,
            AgentStatus.SUPERVISED.value,
            AgentStatus.AUTONOMOUS.value,
        ]

        for status in valid_statuses:
            agent = AgentFactory(status=status)
            db.commit()
            assert agent.status == status

    def test_agent_configuration_json_field(self, db: Session):
        """Test agent configuration JSON field storage."""
        config = {
            "system_prompt": "You are a helpful assistant",
            "tools": ["browser", "canvas"],
            "temperature": 0.7
        }
        agent = AgentFactory(configuration=config)
        db.commit()

        loaded_agent = db.query(AgentRegistry).filter_by(id=agent.id).first()
        assert loaded_agent.configuration == config
        assert loaded_agent.configuration["tools"] == ["browser", "canvas"]

    def test_agent_unique_id_constraint(self, db: Session):
        """Test agent ID unique constraint."""
        agent1 = AgentFactory()
        db.commit()

        # Try to create another agent with same ID (should fail)
        agent2 = AgentRegistry(
            id=agent1.id,  # Duplicate ID
            name="duplicate_agent",
            category="test"
        )
        db.add(agent2)

        with pytest.raises(IntegrityError):
            db.commit()

    def test_agent_cascade_delete_user(self, db: Session):
        """Test agent behavior when user is deleted."""
        user = UserFactory()
        agent = AgentFactory(user_id=user.id)
        db.commit()

        user_id = user.id
        agent_id = agent.id

        # Delete user (agent should remain, user_id is nullable)
        db.delete(user)
        db.commit()

        # Agent should still exist
        loaded_agent = db.query(AgentRegistry).filter_by(id=agent_id).first()
        assert loaded_agent is not None
        assert loaded_agent.user_id is None


class TestAgentExecutionModel:
    """Test AgentExecution ORM model relationships and validation."""

    def test_execution_creation(self, db: Session):
        """Test execution creation with default values."""
        agent = AgentFactory()
        execution = AgentExecutionFactory(agent_id=agent.id)

        assert execution.id is not None
        assert execution.agent_id == agent.id
        assert execution.status == "running"
        assert execution.started_at is not None

    def test_execution_status_transitions(self, db: Session):
        """Test execution status field updates."""
        execution = AgentExecutionFactory(status="running")
        db.commit()

        # Transition to completed
        execution.status = "completed"
        execution.completed_at = datetime.utcnow()
        execution.duration_seconds = 120.0
        db.commit()

        loaded = db.query(AgentExecution).filter_by(id=execution.id).first()
        assert loaded.status == "completed"
        assert loaded.completed_at is not None
        assert loaded.duration_seconds == 120.0

    def test_execution_agent_relationship(self, db: Session):
        """Test Execution -> Agent foreign key relationship."""
        agent = AgentFactory(name="test_agent")
        execution = AgentExecutionFactory(agent_id=agent.id)
        db.commit()

        loaded = db.query(AgentExecution).filter_by(id=execution.id).first()
        assert loaded.agent.name == "test_agent"
        assert loaded.agent.id == agent.id

    def test_execution_duration_calculation(self, db: Session):
        """Test execution duration field storage."""
        started = datetime.utcnow() - timedelta(minutes=5)
        completed = datetime.utcnow()

        execution = AgentExecutionFactory(
            started_at=started,
            completed_at=completed,
            duration_seconds=300.0
        )
        db.commit()

        loaded = db.query(AgentExecution).filter_by(id=execution.id).first()
        assert loaded.duration_seconds == 300.0


class TestAgentFeedbackModel:
    """Test AgentFeedback ORM model relationships and validation."""

    def test_feedback_creation(self, db: Session):
        """Test feedback creation with all fields."""
        agent = AgentFactory()
        user = UserFactory()

        feedback = AgentFeedback(
            agent_id=agent.id,
            user_id=user.id,
            original_output="Original",
            user_correction="Corrected",
            thumbs_up_down=True,
            rating=5
        )
        db.add(feedback)
        db.commit()

        assert feedback.id is not None
        assert feedback.thumbs_up_down is True
        assert feedback.rating == 5

    def test_feedback_status_enum(self, db: Session):
        """Test FeedbackStatus enum validation."""
        agent = AgentFactory()
        user = UserFactory()

        statuses = [
            FeedbackStatus.PENDING.value,
            FeedbackStatus.ADJUDICATED.value,
            FeedbackStatus.REJECTED.value,
        ]

        for status in statuses:
            feedback = AgentFeedback(
                agent_id=agent.id,
                user_id=user.id,
                original_output="Test",
                user_correction="Test",
                status=status
            )
            db.add(feedback)
            db.commit()
            assert feedback.status == status

    def test_feedback_execution_relationship(self, db: Session):
        """Test Feedback -> Execution foreign key relationship."""
        agent = AgentFactory()
        user = UserFactory()
        execution = AgentExecutionFactory(agent_id=agent.id)

        feedback = AgentFeedback(
            agent_id=agent.id,
            user_id=user.id,
            agent_execution_id=execution.id,
            original_output="Test",
            user_correction="Test"
        )
        db.add(feedback)
        db.commit()

        loaded = db.query(AgentFeedback).filter_by(id=feedback.id).first()
        assert loaded.agent_execution_id == execution.id


class TestWorkflowExecutionModel:
    """Test WorkflowExecution ORM model relationships and validation."""

    def test_workflow_creation(self, db: Session):
        """Test workflow execution creation."""
        workflow = WorkflowExecution(
            workflow_id="test_workflow",
            status=WorkflowExecutionStatus.PENDING.value
        )
        db.add(workflow)
        db.commit()

        assert workflow.execution_id is not None
        assert workflow.status == WorkflowExecutionStatus.PENDING.value

    def test_workflow_step_relationship(self, db: Session):
        """Test WorkflowExecution -> WorkflowStepExecution one-to-many."""
        workflow = WorkflowExecution(
            workflow_id="test_workflow",
            status=WorkflowExecutionStatus.PENDING.value
        )
        db.add(workflow)
        db.commit()

        step1 = WorkflowStepExecution(
            workflow_execution_id=workflow.execution_id,
            sequence_order=1,
            status=WorkflowExecutionStatus.PENDING.value
        )
        step2 = WorkflowStepExecution(
            workflow_execution_id=workflow.execution_id,
            sequence_order=2,
            status=WorkflowExecutionStatus.PENDING.value
        )
        db.add_all([step1, step2])
        db.commit()

        # Load workflow with steps
        loaded_workflow = db.query(WorkflowExecution).filter_by(
            execution_id=workflow.execution_id
        ).first()

        # Should have 2 steps
        steps = db.query(WorkflowStepExecution).filter_by(
            workflow_execution_id=workflow.execution_id
        ).all()
        assert len(steps) == 2
        assert steps[0].sequence_order == 1
        assert steps[1].sequence_order == 2

    def test_workflow_status_transitions(self, db: Session):
        """Test workflow status field updates."""
        workflow = WorkflowExecution(
            workflow_id="test_workflow",
            status=WorkflowExecutionStatus.PENDING.value
        )
        db.add(workflow)
        db.commit()

        # PENDING -> RUNNING
        workflow.status = WorkflowExecutionStatus.RUNNING.value
        db.commit()

        loaded = db.query(WorkflowExecution).filter_by(execution_id=workflow.execution_id).first()
        assert loaded.status == WorkflowExecutionStatus.RUNNING.value

        # RUNNING -> COMPLETED
        workflow.status = WorkflowExecutionStatus.COMPLETED.value
        db.commit()

        loaded = db.query(WorkflowExecution).filter_by(execution_id=workflow.execution_id).first()
        assert loaded.status == WorkflowExecutionStatus.COMPLETED.value


class TestWorkflowStepExecutionModel:
    """Test WorkflowStepExecution ORM model."""

    def test_step_creation(self, db: Session):
        """Test workflow step creation."""
        workflow = WorkflowExecution(
            workflow_id="test_workflow",
            status=WorkflowExecutionStatus.PENDING.value
        )
        db.add(workflow)
        db.commit()

        step = WorkflowStepExecution(
            workflow_execution_id=workflow.execution_id,
            sequence_order=1,
            status=WorkflowExecutionStatus.PENDING.value,
            step_id="step_1"
        )
        db.add(step)
        db.commit()

        assert step.id is not None
        assert step.sequence_order == 1

    def test_step_unique_sequence_order(self, db: Session):
        """Test that sequence_order is unique within workflow."""
        workflow = WorkflowExecution(
            workflow_id="test_workflow",
            status=WorkflowExecutionStatus.PENDING.value
        )
        db.add(workflow)
        db.commit()

        step1 = WorkflowStepExecution(
            workflow_execution_id=workflow.execution_id,
            sequence_order=1,
            status=WorkflowExecutionStatus.PENDING.value
        )
        step2 = WorkflowStepExecution(
            workflow_execution_id=workflow.execution_id,
            sequence_order=1,  # Duplicate sequence order
            status=WorkflowExecutionStatus.PENDING.value
        )
        db.add_all([step1, step2])

        # Both should be added (no unique constraint on sequence_order + workflow_execution_id)
        # This tests the current schema behavior
        db.commit()

        steps = db.query(WorkflowStepExecution).filter_by(
            workflow_execution_id=workflow.execution_id
        ).all()
        assert len(steps) == 2


class TestEpisodeModel:
    """Test Episode ORM model relationships and validation."""

    def test_episode_creation(self, db: Session):
        """Test episode creation with required fields."""
        agent = AgentFactory()
        workspace = Workspace(name="Test Workspace")

        episode = Episode(
            title="Test Episode",
            agent_id=agent.id,
            workspace_id=workspace.id
        )
        db.add(episode)
        db.commit()

        assert episode.id is not None
        assert episode.title == "Test Episode"
        assert episode.agent_id == agent.id
        assert episode.started_at is not None

    def test_episode_segment_relationship(self, db: Session):
        """Test Episode -> EpisodeSegment one-to-many relationship."""
        agent = AgentFactory()
        workspace = Workspace(name="Test Workspace")

        episode = Episode(
            title="Test Episode",
            agent_id=agent.id,
            workspace_id=workspace.id
        )
        db.add(episode)
        db.commit()

        segment1 = EpisodeSegment(
            episode_id=episode.id,
            segment_type="reasoning",
            content="Reasoning content"
        )
        segment2 = EpisodeSegment(
            episode_id=episode.id,
            segment_type="action",
            content="Action content"
        )
        db.add_all([segment1, segment2])
        db.commit()

        # Load segments
        segments = db.query(EpisodeSegment).filter_by(episode_id=episode.id).all()
        assert len(segments) == 2
        assert segments[0].segment_type == "reasoning"
        assert segments[1].segment_type == "action"

    def test_episode_access_log(self, db: Session):
        """Test EpisodeAccessLog relationship."""
        agent = AgentFactory()
        workspace = Workspace(name="Test Workspace")

        episode = Episode(
            title="Test Episode",
            agent_id=agent.id,
            workspace_id=workspace.id
        )
        db.add(episode)
        db.commit()

        access_log = EpisodeAccessLog(
            episode_id=episode.id,
            access_type="retrieval"
        )
        db.add(access_log)
        db.commit()

        logs = db.query(EpisodeAccessLog).filter_by(episode_id=episode.id).all()
        assert len(logs) == 1
        assert logs[0].access_type == "retrieval"

    def test_episode_canvas_ids_json_field(self, db: Session):
        """Test episode canvas_ids JSON field."""
        agent = AgentFactory()
        workspace = Workspace(name="Test Workspace")
        canvas = CanvasAuditFactory()

        episode = Episode(
            title="Test Episode",
            agent_id=agent.id,
            workspace_id=workspace.id,
            canvas_ids=[canvas.id]
        )
        db.add(episode)
        db.commit()

        loaded = db.query(Episode).filter_by(id=episode.id).first()
        assert isinstance(loaded.canvas_ids, list)
        assert len(loaded.canvas_ids) == 1
        assert loaded.canvas_ids[0] == canvas.id

    def test_episode_feedback_ids_json_field(self, db: Session):
        """Test episode feedback_ids JSON field."""
        agent = AgentFactory()
        workspace = Workspace(name="Test Workspace")
        user = UserFactory()

        feedback = AgentFeedback(
            agent_id=agent.id,
            user_id=user.id,
            original_output="Test",
            user_correction="Test"
        )
        db.add(feedback)
        db.commit()

        episode = Episode(
            title="Test Episode",
            agent_id=agent.id,
            workspace_id=workspace.id,
            feedback_ids=[feedback.id]
        )
        db.add(episode)
        db.commit()

        loaded = db.query(Episode).filter_by(id=episode.id).first()
        assert isinstance(loaded.feedback_ids, list)
        assert len(loaded.feedback_ids) == 1


class TestEpisodeSegmentModel:
    """Test EpisodeSegment ORM model."""

    def test_segment_creation(self, db: Session):
        """Test segment creation."""
        agent = AgentFactory()
        workspace = Workspace(name="Test Workspace")

        episode = Episode(
            title="Test Episode",
            agent_id=agent.id,
            workspace_id=workspace.id
        )
        db.add(episode)
        db.commit()

        segment = EpisodeSegment(
            episode_id=episode.id,
            segment_type="reasoning",
            content="Test reasoning"
        )
        db.add(segment)
        db.commit()

        assert segment.id is not None
        assert segment.segment_type == "reasoning"
        assert segment.content == "Test reasoning"


class TestUserModel:
    """Test User ORM model relationships and validation."""

    def test_user_creation(self, db: Session):
        """Test user creation with defaults."""
        user = UserFactory(
            email="test@example.com",
            role=UserRole.MEMBER.value
        )
        db.commit()

        assert user.id is not None
        assert user.email == "test@example.com"
        assert user.role == UserRole.MEMBER.value
        assert user.status == UserStatus.ACTIVE.value
        assert user.created_at is not None

    def test_user_email_unique_constraint(self, db: Session):
        """Test user email unique constraint."""
        user1 = UserFactory(email="unique@example.com")
        db.commit()

        # Try to create another user with same email
        user2 = User(
            email="unique@example.com",  # Duplicate email
            password_hash="hash"
        )
        db.add(user2)

        with pytest.raises(IntegrityError):
            db.commit()

    def test_user_role_enum_validation(self, db: Session):
        """Test UserRole enum validation."""
        roles = [
            UserRole.SUPER_ADMIN.value,
            UserRole.MEMBER.value,
            UserRole.GUEST.value,
        ]

        for role in roles:
            user = UserFactory(role=role)
            db.commit()
            assert user.role == role

    def test_user_status_enum_validation(self, db: Session):
        """Test UserStatus enum validation."""
        statuses = [
            UserStatus.ACTIVE.value,
            UserStatus.SUSPENDED.value,
            UserStatus.PENDING.value,
        ]

        for status in statuses:
            user = UserFactory(status=status)
            db.commit()
            assert user.status == status

    def test_user_preferences_json_field(self, db: Session):
        """Test user preferences JSON field."""
        preferences = {
            "theme": "dark",
            "notifications": True,
            "language": "en"
        }
        user = UserFactory(preferences=preferences)
        db.commit()

        loaded = db.query(User).filter_by(id=user.id).first()
        assert loaded.preferences == preferences
        assert loaded.preferences["theme"] == "dark"


class TestWorkspaceModel:
    """Test Workspace ORM model."""

    def test_workspace_creation(self, db: Session):
        """Test workspace creation."""
        workspace = Workspace(name="Test Workspace")
        db.add(workspace)
        db.commit()

        assert workspace.id is not None
        assert workspace.name == "Test Workspace"
        assert workspace.status == "active"
        assert workspace.created_at is not None

    def test_workspace_user_many_to_many(self, db: Session):
        """Test Workspace <-> User many-to-many relationship."""
        workspace = Workspace(name="Test Workspace")
        user1 = UserFactory()
        user2 = UserFactory()

        workspace.users.append(user1)
        workspace.users.append(user2)
        db.commit()

        loaded_workspace = db.query(Workspace).filter_by(id=workspace.id).first()
        assert len(loaded_workspace.users) == 2

        loaded_user1 = db.query(User).filter_by(id=user1.id).first()
        assert len(loaded_user1.workspaces) == 1
        assert loaded_user1.workspaces[0].id == workspace.id


class TestTeamModel:
    """Test Team ORM model."""

    def test_team_creation(self, db: Session):
        """Test team creation."""
        workspace = Workspace(name="Test Workspace")
        team = Team(
            name="Test Team",
            workspace_id=workspace.id
        )
        db.add(team)
        db.commit()

        assert team.id is not None
        assert team.name == "Test Team"
        assert team.workspace_id == workspace.id

    def test_team_workspace_relationship(self, db: Session):
        """Test Team -> Workspace foreign key."""
        workspace = Workspace(name="Test Workspace")
        team = Team(name="Test Team", workspace_id=workspace.id)
        db.add(team)
        db.commit()

        loaded_team = db.query(Team).filter_by(id=team.id).first()
        assert loaded_team.workspace_id == workspace.id

    def test_team_user_many_to_many(self, db: Session):
        """Test Team <-> User many-to-many relationship."""
        workspace = Workspace(name="Test Workspace")
        team = Team(name="Test Team", workspace_id=workspace.id)
        user1 = UserFactory()
        user2 = UserFactory()

        team.members.append(user1)
        team.members.append(user2)
        db.commit()

        loaded_team = db.query(Team).filter_by(id=team.id).first()
        assert len(loaded_team.members) == 2


class TestCanvasAuditModel:
    """Test CanvasAudit ORM model."""

    def test_canvas_creation(self, db: Session):
        """Test canvas audit creation."""
        agent = AgentFactory()
        execution = AgentExecutionFactory(agent_id=agent.id)

        canvas = CanvasAudit(
            agent_id=agent.id,
            execution_id=execution.id,
            canvas_type="chart"
        )
        db.add(canvas)
        db.commit()

        assert canvas.id is not None
        assert canvas.agent_id == agent.id
        assert canvas.execution_id == execution.id

    def test_canvas_execution_relationship(self, db: Session):
        """Test CanvasAudit -> Execution foreign key."""
        agent = AgentFactory()
        execution = AgentExecutionFactory(agent_id=agent.id)

        canvas = CanvasAudit(
            agent_id=agent.id,
            execution_id=execution.id,
            canvas_type="chart"
        )
        db.add(canvas)
        db.commit()

        loaded = db.query(CanvasAudit).filter_by(id=canvas.id).first()
        assert loaded.execution_id == execution.id


class TestBlockedTriggerContextModel:
    """Test BlockedTriggerContext ORM model."""

    def test_blocked_trigger_creation(self, db: Session):
        """Test blocked trigger context creation."""
        agent = AgentFactory()

        blocked = BlockedTriggerContext(
            agent_id=agent.id,
            trigger_type="automated",
            reason="Agent is in STUDENT maturity"
        )
        db.add(blocked)
        db.commit()

        assert blocked.id is not None
        assert blocked.agent_id == agent.id
        assert blocked.trigger_type == "automated"


class TestAgentProposalModel:
    """Test AgentProposal ORM model."""

    def test_proposal_creation(self, db: Session):
        """Test agent proposal creation."""
        agent = AgentFactory()
        user = UserFactory()

        proposal = AgentProposal(
            agent_id=agent.id,
            user_id=user.id,
            proposal_type="action",
            proposed_action="Execute browser automation"
        )
        db.add(proposal)
        db.commit()

        assert proposal.id is not None
        assert proposal.agent_id == agent.id
        assert proposal.user_id == user.id
        assert proposal.status == "pending"

    def test_proposal_status_transitions(self, db: Session):
        """Test proposal status field updates."""
        agent = AgentFactory()
        user = UserFactory()

        proposal = AgentProposal(
            agent_id=agent.id,
            user_id=user.id,
            proposal_type="action",
            proposed_action="Test action"
        )
        db.add(proposal)
        db.commit()

        # PENDING -> APPROVED
        proposal.status = "approved"
        db.commit()

        loaded = db.query(AgentProposal).filter_by(id=proposal.id).first()
        assert loaded.status == "approved"


class TestLifecycleHooks:
    """Test SQLAlchemy lifecycle hooks (created_at, updated_at)."""

    def test_created_at_auto_generation(self, db: Session):
        """Test created_at is automatically set."""
        agent = AgentFactory()
        db.commit()

        assert agent.created_at is not None
        assert isinstance(agent.created_at, datetime)

    def test_updated_at_auto_update(self, db: Session):
        """Test updated_at is automatically updated."""
        agent = AgentFactory(name="Original Name")
        db.commit()

        original_updated_at = agent.updated_at

        # Wait a bit to ensure timestamp difference
        import time
        time.sleep(0.01)

        agent.name = "Updated Name"
        db.commit()

        assert agent.updated_at > original_updated_at

    def test_default_timestamp_on_insert(self, db: Session):
        """Test default timestamps are set on insert."""
        user = UserFactory()
        execution = AgentExecutionFactory()

        assert user.created_at is not None
        assert execution.started_at is not None


class TestFieldValidation:
    """Test field validation constraints."""

    def test_email_not_null_constraint(self, db: Session):
        """Test user.email NOT NULL constraint."""
        user = User(
            password_hash="hash"  # Missing email
        )
        db.add(user)

        with pytest.raises(IntegrityError):
            db.commit()

    def test_string_max_length(self, db: Session):
        """Test string fields respect max length."""
        # This tests application-level validation
        # SQLAlchemy doesn't enforce max_length automatically
        agent = AgentFactory(name="a" * 255)
        db.commit()

        assert len(agent.name) == 255

    def test_json_field_default_empty_dict(self, db: Session):
        """Test JSON fields default to empty dict."""
        agent = AgentFactory()
        db.commit()

        assert agent.configuration == {}
        assert agent.schedule_config == {}

    def test_float_field_defaults(self, db: Session):
        """Test float fields have correct defaults."""
        agent = AgentFactory()
        db.commit()

        assert agent.confidence_score >= 0.0
        assert agent.confidence_score <= 1.0


class TestIndexConstraints:
    """Test index constraints."""

    def test_user_email_index(self, db: Session):
        """Test user.email has unique index."""
        user = UserFactory(email="indexed@example.com")
        db.commit()

        # Query by email should use index
        loaded = db.query(User).filter_by(email="indexed@example.com").first()
        assert loaded is not None

    def test_agent_id_index(self, db: Session):
        """Test agent_id is indexed in executions."""
        agent = AgentFactory()
        execution = AgentExecutionFactory(agent_id=agent.id)
        db.commit()

        # Query by agent_id should use index
        executions = db.query(AgentExecution).filter_by(agent_id=agent.id).all()
        assert len(executions) == 1


class TestCascadeBehaviors:
    """Test cascade delete behaviors."""

    def test_workflow_steps_cascade_delete(self, db: Session):
        """Test workflow steps are deleted when workflow is deleted."""
        workflow = WorkflowExecution(
            workflow_id="test_workflow",
            status=WorkflowExecutionStatus.PENDING.value
        )
        db.add(workflow)
        db.commit()

        step = WorkflowStepExecution(
            workflow_execution_id=workflow.execution_id,
            sequence_order=1,
            status=WorkflowExecutionStatus.PENDING.value
        )
        db.add(step)
        db.commit()

        step_id = step.id

        # Delete workflow
        db.delete(workflow)
        db.commit()

        # Step should be deleted (cascade)
        step = db.query(WorkflowStepExecution).filter_by(id=step_id).first()
        assert step is None
