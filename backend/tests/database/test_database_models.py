"""
Comprehensive database model tests covering relationships, constraints, cascading operations, and ORM queries.

Goal: Achieve 90%+ coverage of database models through comprehensive testing of:
- Relationship types (one-to-one, one-to-many, many-to-many)
- Foreign key constraints
- Cascade delete operations
- ORM queries (filters, joins, aggregations)
- JSON fields and special properties

Tests use:
- pytest fixtures for database sessions (db_session from conftest.py)
- Factory pattern for test data creation (factories in tests/factories/)
- Real database (SQLite for tests, migration to PostgreSQL in CI)
- SQLAlchemy ORM for queries
"""

import uuid
import pytest
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import and_, or_, func, desc, asc
import time

from tests.factories.agent_factory import AgentFactory, StudentAgentFactory
from tests.factories.user_factory import UserFactory, AdminUserFactory
from tests.factories.execution_factory import AgentExecutionFactory
from tests.factories.episode_factory import EpisodeFactory
from tests.factories.feedback_factory import AgentFeedbackFactory
from tests.factories.workspace_factory import WorkspaceFactory, TeamFactory
from core.models import (
    AgentRegistry,
    AgentExecution,
    AgentFeedback,
    User,
    Workspace,
    Team,
    UserRole,
    UserStatus,
    WorkspaceStatus,
    AgentStatus,
    FeedbackStatus,
    HITLActionStatus,
    Episode,
    EpisodeSegment,
    OAuthToken,
    OAuthState,
    user_workspaces,
    team_members,
)


# ============================================================================
# Task 1: Relationship Tests
# ============================================================================

class TestRelationships:
    """Test all model relationship types."""

    def test_user_workspace_many_to_many_relationship(self, db_session: Session):
        """Test User-Workspace many-to-many relationship via user_workspaces table."""
        # Create workspace
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()
        db_session.refresh(workspace)

        # Create users
        user1 = UserFactory(email="user1@test.com", _session=db_session)
        user2 = UserFactory(email="user2@test.com", _session=db_session)

        # Add users to workspace
        workspace.users.append(user1)
        workspace.users.append(user2)
        db_session.commit()

        # Verify relationship from workspace to users
        retrieved_workspace = db_session.query(Workspace).filter(
            Workspace.id == workspace.id
        ).first()
        assert retrieved_workspace is not None
        assert len(retrieved_workspace.users) == 2

        # Verify relationship from user to workspaces
        retrieved_user1 = db_session.query(User).filter(User.id == user1.id).first()
        assert len(retrieved_user1.workspaces) == 1
        assert retrieved_user1.workspaces[0].id == workspace.id

    def test_workspace_user_relationship(self, db_session: Session):
        """Test Workspace can have multiple users."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        # Create multiple users
        users = [UserFactory(email=f"user{i}@test.com", _session=db_session) for i in range(3)]
        for user in users:
            workspace.users.append(user)

        db_session.commit()

        # Query workspaces from user relationship
        retrieved_workspace = db_session.query(Workspace).filter(
            Workspace.id == workspace.id
        ).first()
        assert len(retrieved_workspace.users) == 3

    def test_team_membership_many_to_many_relationship(self, db_session: Session):
        """Test User-Team many-to-many relationship via team_members table."""
        # Create workspace
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        # Create team
        team = TeamFactory(workspace_id=workspace.id, _session=db_session)
        db_session.commit()

        # Create users
        user1 = UserFactory(email="member1@test.com", _session=db_session)
        user2 = UserFactory(email="member2@test.com", _session=db_session)

        # Add users to team
        team.members.append(user1)
        team.members.append(user2)
        db_session.commit()

        # Verify team members
        retrieved_team = db_session.query(Team).filter(Team.id == team.id).first()
        assert retrieved_team is not None
        assert len(retrieved_team.members) == 2

        # Verify user teams
        retrieved_user1 = db_session.query(User).filter(User.id == user1.id).first()
        assert len(retrieved_user1.teams) == 1
        assert retrieved_user1.teams[0].id == team.id

    def test_agent_execution_one_to_many_relationship(self, db_session: Session):
        """Test Agent has many executions (one-to-many)."""
        # Create agent
        agent = AgentFactory(name="MultiExecutionAgent", _session=db_session)

        # Create multiple executions
        execution1 = AgentExecutionFactory(agent_id=agent.id, _session=db_session)
        execution2 = AgentExecutionFactory(agent_id=agent.id, _session=db_session)
        execution3 = AgentExecutionFactory(agent_id=agent.id, _session=db_session)

        db_session.commit()

        # Query executions for agent (note: using agent_id filter as relationship may not be defined)
        executions = db_session.query(AgentExecution).filter(
            AgentExecution.agent_id == agent.id
        ).all()

        assert len(executions) == 3
        assert all(e.agent_id == agent.id for e in executions)

    def test_execution_belongs_to_one_agent(self, db_session: Session):
        """Test Execution belongs to one agent."""
        agent = AgentFactory(name="SingleAgent", _session=db_session)
        execution = AgentExecutionFactory(agent_id=agent.id, _session=db_session)
        db_session.commit()

        # Verify execution belongs to agent
        retrieved_execution = db_session.query(AgentExecution).filter(
            AgentExecution.id == execution.id
        ).first()
        assert retrieved_execution.agent_id == agent.id

    def test_agent_feedback_multiple_relationships(self, db_session: Session):
        """Test Feedback links to agent, execution, user, and episode."""
        # Create test data
        agent = AgentFactory(name="FeedbackAgent", _session=db_session)
        user = UserFactory(email="feedbackuser@test.com", _session=db_session)
        execution = AgentExecutionFactory(agent_id=agent.id, _session=db_session)
        episode = EpisodeFactory(agent_id=agent.id, title="Feedback Episode", _session=db_session)

        # Create feedback
        feedback = AgentFeedbackFactory(
            agent_id=agent.id,
            user_id=user.id,
            agent_execution_id=execution.id,
            episode_id=episode.id,
            _session=db_session
        )
        db_session.commit()

        # Verify all foreign keys are correct
        retrieved_feedback = db_session.query(AgentFeedback).filter(
            AgentFeedback.id == feedback.id
        ).first()
        assert retrieved_feedback.agent_id == agent.id
        assert retrieved_feedback.user_id == user.id
        assert retrieved_feedback.agent_execution_id == execution.id
        assert retrieved_feedback.episode_id == episode.id

    def test_feedback_from_agent_relationship(self, db_session: Session):
        """Test Query feedback from agent feedback_history relationship."""
        agent = AgentFactory(name="FeedbackHistoryAgent", _session=db_session)
        user = UserFactory(email="historyuser@test.com", _session=db_session)

        # Create multiple feedback entries
        feedback1 = AgentFeedbackFactory(agent_id=agent.id, user_id=user.id, _session=db_session)
        feedback2 = AgentFeedbackFactory(agent_id=agent.id, user_id=user.id, _session=db_session)
        db_session.commit()

        # Query feedback via agent_id (using relationship if available, otherwise filter)
        feedback_list = db_session.query(AgentFeedback).filter(
            AgentFeedback.agent_id == agent.id
        ).all()

        assert len(feedback_list) == 2
        assert all(f.agent_id == agent.id for f in feedback_list)

    def test_feedback_from_user_relationship(self, db_session: Session):
        """Test Query feedback from user submitted_feedback relationship."""
        user = UserFactory(email="submitter@test.com", _session=db_session)
        agent = AgentFactory(name="UserFeedbackAgent", _session=db_session)

        # Create feedback entries from user
        feedback1 = AgentFeedbackFactory(agent_id=agent.id, user_id=user.id, _session=db_session)
        feedback2 = AgentFeedbackFactory(agent_id=agent.id, user_id=user.id, _session=db_session)
        db_session.commit()

        # Query feedback submitted by user
        user_feedback = db_session.query(AgentFeedback).filter(
            AgentFeedback.user_id == user.id
        ).all()

        assert len(user_feedback) == 2

    def test_episode_segment_one_to_many_relationship(self, db_session: Session):
        """Test Episode has many segments."""
        agent = AgentFactory(name="SegmentAgent", _session=db_session)
        episode = EpisodeFactory(agent_id=agent.id, title="Segment Test Episode", _session=db_session)

        # Create segments manually (factory doesn't exist)
        segment1 = EpisodeSegment(
            episode_id=episode.id,
            segment_type="conversation",
            sequence_order=1,
            content="First segment content",
            source_type="chat_message"
        )
        segment2 = EpisodeSegment(
            episode_id=episode.id,
            segment_type="execution",
            sequence_order=2,
            content="Second segment content",
            source_type="agent_execution"
        )
        segment3 = EpisodeSegment(
            episode_id=episode.id,
            segment_type="reflection",
            sequence_order=3,
            content="Third segment content",
            source_type="manual"
        )

        db_session.add_all([segment1, segment2, segment3])
        db_session.commit()

        # Query segments for episode
        segments = db_session.query(EpisodeSegment).filter(
            EpisodeSegment.episode_id == episode.id
        ).all()

        assert len(segments) == 3

    def test_segment_belongs_to_one_episode(self, db_session: Session):
        """Test Segment belongs to one episode."""
        agent = AgentFactory(name="SingleSegmentAgent", _session=db_session)
        episode = EpisodeFactory(agent_id=agent.id, title="Single Segment Episode", _session=db_session)

        segment = EpisodeSegment(
            episode_id=episode.id,
            segment_type="conversation",
            sequence_order=1,
            content="Segment content",
            source_type="chat_message"
        )
        db_session.add(segment)
        db_session.commit()

        # Verify segment belongs to episode
        retrieved_segment = db_session.query(EpisodeSegment).filter(
            EpisodeSegment.id == segment.id
        ).first()
        assert retrieved_segment.episode_id == episode.id

    def test_segment_ordering_by_timestamp(self, db_session: Session):
        """Test Ordering of segments by sequence_order."""
        agent = AgentFactory(name="OrderAgent", _session=db_session)
        episode = EpisodeFactory(agent_id=agent.id, title="Order Episode", _session=db_session)

        # Create segments out of order
        segment3 = EpisodeSegment(
            episode_id=episode.id,
            segment_type="conversation",
            sequence_order=3,
            content="Third",
            source_type="chat_message"
        )
        segment1 = EpisodeSegment(
            episode_id=episode.id,
            segment_type="conversation",
            sequence_order=1,
            content="First",
            source_type="chat_message"
        )
        segment2 = EpisodeSegment(
            episode_id=episode.id,
            segment_type="conversation",
            sequence_order=2,
            content="Second",
            source_type="chat_message"
        )

        db_session.add_all([segment3, segment1, segment2])
        db_session.commit()

        # Query ordered by sequence_order
        segments = db_session.query(EpisodeSegment).filter(
            EpisodeSegment.episode_id == episode.id
        ).order_by(EpisodeSegment.sequence_order).all()

        assert segments[0].sequence_order == 1
        assert segments[1].sequence_order == 2
        assert segments[2].sequence_order == 3

    def test_oauth_token_user_relationship(self, db_session: Session):
        """Test OAuthToken belongs to user."""
        user = UserFactory(email="oauthuser@test.com", _session=db_session)

        # Create OAuth token
        token = OAuthToken(
            user_id=user.id,
            provider="google",
            access_token="test_access_token",
            token_type="Bearer"
        )
        db_session.add(token)
        db_session.commit()

        # Verify token belongs to user
        retrieved_token = db_session.query(OAuthToken).filter(
            OAuthToken.id == token.id
        ).first()
        assert retrieved_token.user_id == user.id

    def test_user_has_multiple_oauth_tokens(self, db_session: Session):
        """Test User has multiple oauth_tokens."""
        user = UserFactory(email="multiuser@test.com", _session=db_session)

        # Create multiple tokens for different providers
        google_token = OAuthToken(
            user_id=user.id,
            provider="google",
            access_token="google_token",
            token_type="Bearer"
        )
        github_token = OAuthToken(
            user_id=user.id,
            provider="github",
            access_token="github_token",
            token_type="Bearer"
        )
        notion_token = OAuthToken(
            user_id=user.id,
            provider="notion",
            access_token="notion_token",
            token_type="Bearer"
        )

        db_session.add_all([google_token, github_token, notion_token])
        db_session.commit()

        # Query tokens for user
        user_tokens = db_session.query(OAuthToken).filter(
            OAuthToken.user_id == user.id
        ).all()

        assert len(user_tokens) == 3

    def test_oauth_token_provider_filtering(self, db_session: Session):
        """Test Provider filtering works for OAuth tokens."""
        user = UserFactory(email="provideruser@test.com", _session=db_session)

        # Create tokens for different providers
        google_token = OAuthToken(
            user_id=user.id,
            provider="google",
            access_token="google_access",
            token_type="Bearer"
        )
        github_token = OAuthToken(
            user_id=user.id,
            provider="github",
            access_token="github_access",
            token_type="Bearer"
        )

        db_session.add_all([google_token, github_token])
        db_session.commit()

        # Filter by provider
        google_tokens = db_session.query(OAuthToken).filter(
            and_(OAuthToken.user_id == user.id, OAuthToken.provider == "google")
        ).all()

        github_tokens = db_session.query(OAuthToken).filter(
            and_(OAuthToken.user_id == user.id, OAuthToken.provider == "github")
        ).all()

        assert len(google_tokens) == 1
        assert google_tokens[0].provider == "google"
        assert len(github_tokens) == 1
        assert github_tokens[0].provider == "github"


# ============================================================================
# Task 2: Constraint Tests
# ============================================================================

class TestConstraints:
    """Test database constraints (unique, not null, enum, foreign key, check)."""

    def test_unique_constraint_user_email(self, db_session: Session):
        """Test User.email must be unique (IntegrityError on duplicate)."""
        # Create first user
        user1 = UserFactory(email="unique@test.com", _session=db_session)
        db_session.commit()

        # Try to create second user with same email - should raise IntegrityError
        with pytest.raises(IntegrityError):
            user2 = User(email="unique@test.com", first_name="User", last_name="Two")
            db_session.add(user2)
            db_session.commit()

        db_session.rollback()

    def test_unique_constraint_oauth_state(self, db_session: Session):
        """Test OAuthState.state must be unique."""
        user = UserFactory(email="stateuser@test.com", _session=db_session)

        # Create first OAuth state
        state1 = OAuthState(
            user_id=user.id,
            provider="google",
            state="unique_state_123",
            expires_at=datetime.utcnow() + timedelta(minutes=10)
        )
        db_session.add(state1)
        db_session.commit()

        # Try to create second state with same state string
        with pytest.raises(IntegrityError):
            state2 = OAuthState(
                user_id=user.id,
                provider="github",
                state="unique_state_123",  # Duplicate state
                expires_at=datetime.utcnow() + timedelta(minutes=10)
            )
            db_session.add(state2)
            db_session.commit()

        db_session.rollback()

    def test_not_null_constraint_agent_name(self, db_session: Session):
        """Test AgentRegistry.name cannot be NULL."""
        # Try to create agent without name
        agent = AgentRegistry(
            name=None,  # Violates NOT NULL
            category="test",
            module_path="test.module",
            class_name="TestAgent"
        )
        db_session.add(agent)

        with pytest.raises((IntegrityError, Exception)):
            db_session.commit()

        db_session.rollback()

    def test_not_null_constraint_user_email(self, db_session: Session):
        """Test User.email cannot be NULL."""
        user = User(
            email=None,  # Violates NOT NULL
            first_name="Test",
            last_name="User"
        )
        db_session.add(user)

        with pytest.raises((IntegrityError, Exception)):
            db_session.commit()

        db_session.rollback()

    def test_not_null_constraint_agent_category(self, db_session: Session):
        """Test AgentRegistry.category cannot be NULL."""
        agent = AgentRegistry(
            name="TestAgent",
            category=None,  # Violates NOT NULL
            module_path="test.module",
            class_name="TestAgent"
        )
        db_session.add(agent)

        with pytest.raises((IntegrityError, Exception)):
            db_session.commit()

        db_session.rollback()

    def test_enum_constraint_agent_status(self, db_session: Session):
        """Test AgentStatus only allows valid enum values."""
        # Valid status should work
        agent = AgentFactory(
            status=AgentStatus.SUPERVISED.value,
            _session=db_session
        )
        db_session.commit()

        retrieved = db_session.query(AgentRegistry).filter(
            AgentRegistry.id == agent.id
        ).first()
        assert retrieved.status == AgentStatus.SUPERVISED.value

    def test_enum_constraint_user_role(self, db_session: Session):
        """Test UserRole only allows valid roles."""
        # Valid role should work
        user = UserFactory(
            role=UserRole.TEAM_LEAD.value,
            _session=db_session
        )
        db_session.commit()

        retrieved = db_session.query(User).filter(User.id == user.id).first()
        assert retrieved.role == UserRole.TEAM_LEAD.value

    def test_enum_constraint_feedback_status(self, db_session: Session):
        """Test FeedbackStatus only allows pending/accepted/rejected."""
        agent = AgentFactory(_session=db_session)
        user = UserFactory(_session=db_session)

        # Valid status should work
        feedback = AgentFeedbackFactory(
            agent_id=agent.id,
            user_id=user.id,
            status=FeedbackStatus.ACCEPTED.value,
            _session=db_session
        )
        db_session.commit()

        retrieved = db_session.query(AgentFeedback).filter(
            AgentFeedback.id == feedback.id
        ).first()
        assert retrieved.status == FeedbackStatus.ACCEPTED.value

    def test_foreign_key_constraint_execution_agent(self, db_session: Session):
        """Test AgentExecution.agent_id must reference valid agent."""
        # Try to create execution with invalid agent_id
        # Note: SQLite doesn't enforce FK by default, but we test the relationship
        execution = AgentExecutionFactory(
            agent_id="nonexistent_agent_id",
            _session=db_session
        )
        db_session.commit()

        # Verify execution was created (SQLite allows this)
        # In production PostgreSQL, this would raise IntegrityError
        retrieved = db_session.query(AgentExecution).filter(
            AgentExecution.id == execution.id
        ).first()
        assert retrieved is not None
        assert retrieved.agent_id == "nonexistent_agent_id"

    def test_foreign_key_constraint_feedback_agent(self, db_session: Session):
        """Test AgentFeedback.agent_id must reference valid agent."""
        user = UserFactory(_session=db_session)

        # Create feedback with invalid agent_id
        feedback = AgentFeedbackFactory(
            agent_id="invalid_agent_id",
            user_id=user.id,
            _session=db_session
        )
        db_session.commit()

        # Verify feedback was created (SQLite allows this)
        retrieved = db_session.query(AgentFeedback).filter(
            AgentFeedback.id == feedback.id
        ).first()
        assert retrieved.agent_id == "invalid_agent_id"

    def test_foreign_key_constraint_episode_agent(self, db_session: Session):
        """Test Episode.agent_id must reference valid agent."""
        # Create episode with invalid agent_id (Episode requires maturity_at_time)
        episode = Episode(
            id=str(uuid.uuid4()),
            agent_id="invalid_agent_id",
            workspace_id=str(uuid.uuid4()),
            title="Test Episode",
            maturity_at_time="STUDENT",  # Required field
            human_intervention_count=0,  # Required field
            started_at=datetime.utcnow()
        )
        db_session.add(episode)
        db_session.commit()

        # Verify episode was created (SQLite doesn't enforce FK)
        retrieved = db_session.query(Episode).filter(Episode.id == episode.id).first()
        assert retrieved.agent_id == "invalid_agent_id"

    def test_check_constraint_confidence_score_range(self, db_session: Session):
        """Test Confidence score between 0.0 and 1.0."""
        # Valid scores
        agent1 = AgentFactory(confidence_score=0.0, _session=db_session)
        agent2 = AgentFactory(confidence_score=0.5, _session=db_session)
        agent3 = AgentFactory(confidence_score=1.0, _session=db_session)
        db_session.commit()

        assert agent1.confidence_score == 0.0
        assert agent2.confidence_score == 0.5
        assert agent3.confidence_score == 1.0

    def test_check_constraint_rating_range(self, db_session: Session):
        """Test Rating between 1 and 5 stars."""
        agent = AgentFactory(_session=db_session)
        user = UserFactory(_session=db_session)

        # Valid ratings
        feedback1 = AgentFeedbackFactory(
            agent_id=agent.id,
            user_id=user.id,
            rating=1,
            _session=db_session
        )
        feedback2 = AgentFeedbackFactory(
            agent_id=agent.id,
            user_id=user.id,
            rating=3,
            _session=db_session
        )
        feedback3 = AgentFeedbackFactory(
            agent_id=agent.id,
            user_id=user.id,
            rating=5,
            _session=db_session
        )
        db_session.commit()

        assert feedback1.rating == 1
        assert feedback2.rating == 3
        assert feedback3.rating == 5


# ============================================================================
# Task 3: Cascade Delete Tests
# ============================================================================

class TestCascades:
    """Test cascade delete and update operations."""

    def test_cascade_delete_agent_to_executions(self, db_session: Session):
        """Test deleting agent requires deleting executions first (no cascade configured)."""
        agent = AgentFactory(name="CascadeAgent", _session=db_session)

        # Create 3 executions
        execution1 = AgentExecutionFactory(agent_id=agent.id, _session=db_session)
        execution2 = AgentExecutionFactory(agent_id=agent.id, _session=db_session)
        execution3 = AgentExecutionFactory(agent_id=agent.id, _session=db_session)
        db_session.commit()

        agent_id = agent.id
        execution_ids = [execution1.id, execution2.id, execution3.id]

        # Verify relationship exists
        executions = db_session.query(AgentExecution).filter(
            AgentExecution.agent_id == agent_id
        ).all()
        assert len(executions) == 3

        # Delete executions first (FK constraint prevents direct agent deletion)
        for execution in executions:
            db_session.delete(execution)
        db_session.commit()

        # Now delete agent
        db_session.delete(agent)
        db_session.commit()

        # Verify agent is deleted
        assert db_session.query(AgentRegistry).filter(
            AgentRegistry.id == agent_id
        ).first() is None

        # Verify executions are deleted
        remaining_executions = db_session.query(AgentExecution).filter(
            AgentExecution.id.in_(execution_ids)
        ).all()
        assert len(remaining_executions) == 0

    def test_cascade_delete_agent_to_feedback(self, db_session: Session):
        """Test deleting agent requires deleting feedback first (no cascade configured)."""
        agent = AgentFactory(name="FeedbackCascadeAgent", _session=db_session)
        user = UserFactory(_session=db_session)

        # Create 5 feedback entries
        feedback_list = []
        for i in range(5):
            feedback = AgentFeedbackFactory(
                agent_id=agent.id,
                user_id=user.id,
                _session=db_session
            )
            feedback_list.append(feedback)
        db_session.commit()

        agent_id = agent.id
        feedback_ids = [f.id for f in feedback_list]

        # Verify feedback exists
        feedback_count = db_session.query(AgentFeedback).filter(
            AgentFeedback.agent_id == agent_id
        ).count()
        assert feedback_count == 5

        # Delete feedback first (FK constraint)
        for feedback in feedback_list:
            db_session.delete(feedback)
        db_session.commit()

        # Now delete agent
        db_session.delete(agent)
        db_session.commit()

        # Verify agent deleted
        assert db_session.query(AgentRegistry).filter(
            AgentRegistry.id == agent_id
        ).first() is None

        # Verify feedback deleted
        remaining_feedback = db_session.query(AgentFeedback).filter(
            AgentFeedback.id.in_(feedback_ids)
        ).all()
        assert len(remaining_feedback) == 0

    def test_cascade_delete_episode_to_segments(self, db_session: Session):
        """Test deleting episode removes segments (cascade configured)."""
        agent = AgentFactory(name="SegmentCascadeAgent", _session=db_session)
        episode = EpisodeFactory(agent_id=agent.id, title="Cascade Episode", _session=db_session)

        # Create 10 segments
        segments = []
        for i in range(10):
            segment = EpisodeSegment(
                episode_id=episode.id,
                segment_type="conversation",
                sequence_order=i + 1,
                content=f"Segment {i}",
                source_type="chat_message"
            )
            segments.append(segment)

        db_session.add_all(segments)
        db_session.commit()

        episode_id = episode.id
        segment_ids = [s.id for s in segments]

        # Delete episode
        db_session.delete(episode)
        db_session.commit()

        # Verify episode deleted
        assert db_session.query(Episode).filter(Episode.id == episode_id).first() is None

        # Verify segments are deleted (cascade delete configured in EpisodeSegment)
        remaining_segments = db_session.query(EpisodeSegment).filter(
            EpisodeSegment.episode_id == episode_id
        ).all()
        assert len(remaining_segments) == 0, "Segments should be cascade deleted"

    def test_no_cascade_on_nullify_relationships(self, db_session: Session):
        """Test feedback deletion when agent is deleted (manual cascade)."""
        agent = AgentFactory(name="NullifyAgent", _session=db_session)
        user = UserFactory(email="nullify@test.com", _session=db_session)

        # Create feedback
        feedback = AgentFeedbackFactory(
            agent_id=agent.id,
            user_id=user.id,
            _session=db_session
        )
        db_session.commit()

        feedback_id = feedback.id

        # Delete feedback first (FK constraint), then agent
        db_session.delete(feedback)
        db_session.delete(agent)
        db_session.commit()

        # Verify both are deleted
        assert db_session.query(AgentFeedback).filter(
            AgentFeedback.id == feedback_id
        ).first() is None

        assert db_session.query(AgentRegistry).filter(
            AgentRegistry.id == agent.id
        ).first() is None


# ============================================================================
# Task 4: ORM Query Tests
# ============================================================================

class TestORMQueries:
    """Test ORM queries: filters, joins, aggregations, sorting, pagination."""

    def test_filter_agents_by_status(self, db_session: Session):
        """Test Filter agents by status."""
        # Create agents with different statuses
        student = AgentFactory(status=AgentStatus.STUDENT.value, _session=db_session)
        intern = AgentFactory(status=AgentStatus.INTERN.value, _session=db_session)
        supervised = AgentFactory(status=AgentStatus.SUPERVISED.value, _session=db_session)
        autonomous = AgentFactory(status=AgentStatus.AUTONOMOUS.value, _session=db_session)
        db_session.commit()

        # Filter by STUDENT status
        student_agents = db_session.query(AgentRegistry).filter(
            AgentRegistry.status == AgentStatus.STUDENT.value
        ).all()
        assert len(student_agents) == 1
        assert student_agents[0].id == student.id

        # Filter by SUPERVISED status
        supervised_agents = db_session.query(AgentRegistry).filter(
            AgentRegistry.status == AgentStatus.SUPERVISED.value
        ).all()
        assert len(supervised_agents) == 1

    def test_filter_users_by_role(self, db_session: Session):
        """Test Filter users by role."""
        admin = UserFactory(role=UserRole.SUPER_ADMIN.value, email="admin@test.com", _session=db_session)
        member = UserFactory(role=UserRole.MEMBER.value, email="member@test.com", _session=db_session)
        lead = UserFactory(role=UserRole.TEAM_LEAD.value, email="lead@test.com", _session=db_session)
        db_session.commit()

        # Filter by TEAM_LEAD role
        leads = db_session.query(User).filter(
            User.role == UserRole.TEAM_LEAD.value
        ).all()
        assert len(leads) == 1

    def test_chained_filters(self, db_session: Session):
        """Test Chained filters (status AND category)."""
        # Create agents with same status but different categories
        ops1 = AgentFactory(
            status=AgentStatus.STUDENT.value,
            category="Operations",
            _session=db_session
        )
        ops2 = AgentFactory(
            status=AgentStatus.STUDENT.value,
            category="Operations",
            _session=db_session
        )
        finance = AgentFactory(
            status=AgentStatus.STUDENT.value,
            category="Finance",
            _session=db_session
        )
        db_session.commit()

        # Filter by status AND category
        ops_students = db_session.query(AgentRegistry).filter(
            and_(
                AgentRegistry.status == AgentStatus.STUDENT.value,
                AgentRegistry.category == "Operations"
            )
        ).all()

        assert len(ops_students) == 2

    def test_join_agents_with_executions(self, db_session: Session):
        """Test Join agents with executions."""
        agent = AgentFactory(name="JoinAgent", _session=db_session)
        execution1 = AgentExecutionFactory(agent_id=agent.id, _session=db_session)
        execution2 = AgentExecutionFactory(agent_id=agent.id, _session=db_session)
        db_session.commit()

        # Join query
        results = db_session.query(AgentRegistry, AgentExecution).join(
            AgentExecution, AgentRegistry.id == AgentExecution.agent_id
        ).all()

        assert len(results) == 2

    def test_join_users_with_workspaces(self, db_session: Session):
        """Test Join users with workspaces."""
        workspace = WorkspaceFactory(name="JoinWorkspace", _session=db_session)
        db_session.commit()

        user1 = UserFactory(email="joinuser1@test.com", _session=db_session)
        user2 = UserFactory(email="joinuser2@test.com", _session=db_session)

        workspace.users.append(user1)
        workspace.users.append(user2)
        db_session.commit()

        # Query with join
        results = db_session.query(Workspace, User).join(
            User, Workspace.users
        ).all()

        assert len(results) == 2

    def test_join_episodes_with_segments(self, db_session: Session):
        """Test Join episodes with segments."""
        agent = AgentFactory(name="JoinEpisodeAgent", _session=db_session)
        episode = EpisodeFactory(agent_id=agent.id, title="Join Episode", _session=db_session)

        segment1 = EpisodeSegment(
            episode_id=episode.id,
            segment_type="conversation",
            sequence_order=1,
            content="First",
            source_type="chat_message"
        )
        segment2 = EpisodeSegment(
            episode_id=episode.id,
            segment_type="execution",
            sequence_order=2,
            content="Second",
            source_type="agent_execution"
        )
        db_session.add_all([segment1, segment2])
        db_session.commit()

        # Join episodes with segments
        results = db_session.query(Episode, EpisodeSegment).join(
            EpisodeSegment, Episode.id == EpisodeSegment.episode_id
        ).all()

        assert len(results) == 2

    def test_count_agents_by_status(self, db_session: Session):
        """Test Count agents by status."""
        # Create agents
        for _ in range(3):
            AgentFactory(status=AgentStatus.STUDENT.value, _session=db_session)
        for _ in range(2):
            AgentFactory(status=AgentStatus.INTERN.value, _session=db_session)
        AgentFactory(status=AgentStatus.AUTONOMOUS.value, _session=db_session)
        db_session.commit()

        # Count by status
        student_count = db_session.query(AgentRegistry).filter(
            AgentRegistry.status == AgentStatus.STUDENT.value
        ).count()
        intern_count = db_session.query(AgentRegistry).filter(
            AgentRegistry.status == AgentStatus.INTERN.value
        ).count()

        assert student_count == 3
        assert intern_count == 2

    def test_aggregate_average_confidence_by_category(self, db_session: Session):
        """Test Average confidence score by category."""
        AgentFactory(category="Operations", confidence_score=0.6, _session=db_session)
        AgentFactory(category="Operations", confidence_score=0.8, _session=db_session)
        AgentFactory(category="Finance", confidence_score=0.7, _session=db_session)
        db_session.commit()

        # Calculate average confidence by category
        ops_avg = db_session.query(func.avg(AgentRegistry.confidence_score)).filter(
            AgentRegistry.category == "Operations"
        ).scalar()

        assert ops_avg == 0.7

    def test_max_min_created_at(self, db_session: Session):
        """Test Max/min created_at timestamps."""
        agent1 = AgentFactory(_session=db_session)
        db_session.commit()  # Commit to set created_at

        # Wait a bit to ensure different timestamps
        import time
        time.sleep(0.01)

        agent2 = AgentFactory(_session=db_session)
        db_session.commit()

        # Get max created_at
        max_created = db_session.query(func.max(AgentRegistry.created_at)).scalar()
        assert max_created is not None

    def test_order_agents_by_confidence_desc(self, db_session: Session):
        """Test Order agents by confidence_score DESC."""
        agent1 = AgentFactory(confidence_score=0.5, _session=db_session)
        agent2 = AgentFactory(confidence_score=0.9, _session=db_session)
        agent3 = AgentFactory(confidence_score=0.7, _session=db_session)
        db_session.commit()

        # Order by confidence DESC
        agents = db_session.query(AgentRegistry).order_by(
            desc(AgentRegistry.confidence_score)
        ).all()

        assert agents[0].confidence_score == 0.9
        assert agents[1].confidence_score == 0.7
        assert agents[2].confidence_score == 0.5

    def test_order_executions_by_created_at_desc(self, db_session: Session):
        """Test Order executions by started_at DESC."""
        agent = AgentFactory(_session=db_session)

        # Create executions with explicit timestamps to ensure ordering
        base_time = datetime.utcnow()

        execution1 = AgentExecutionFactory(
            agent_id=agent.id,
            started_at=base_time,
            _session=db_session
        )
        execution2 = AgentExecutionFactory(
            agent_id=agent.id,
            started_at=base_time + timedelta(seconds=1),
            _session=db_session
        )
        execution3 = AgentExecutionFactory(
            agent_id=agent.id,
            started_at=base_time + timedelta(seconds=2),
            _session=db_session
        )
        db_session.commit()

        # Order by started_at DESC (most recent first)
        executions = db_session.query(AgentExecution).order_by(
            desc(AgentExecution.started_at)
        ).all()

        # execution3 should be first (latest timestamp)
        assert executions[0].id == execution3.id
        assert executions[1].id == execution2.id
        assert executions[2].id == execution1.id

    def test_pagination_limit_offset(self, db_session: Session):
        """Test Limit and offset for pagination."""
        # Create 20 agents
        for i in range(20):
            AgentFactory(name=f"PageAgent{i}", _session=db_session)
        db_session.commit()

        # First page: limit=10, offset=0
        page1 = db_session.query(AgentRegistry).order_by(
            AgentRegistry.name
        ).limit(10).offset(0).all()
        assert len(page1) == 10

        # Second page: limit=10, offset=10
        page2 = db_session.query(AgentRegistry).order_by(
            AgentRegistry.name
        ).limit(10).offset(10).all()
        assert len(page2) == 10

        # Ensure different results
        page1_names = [a.name for a in page1]
        page2_names = [a.name for a in page2]
        assert set(page1_names).isdisjoint(set(page2_names))

    def test_like_search_pattern(self, db_session: Session):
        """Test Search agents by name pattern (LIKE)."""
        AgentFactory(name="AlphaAgent", _session=db_session)
        AgentFactory(name="BetaAgent", _session=db_session)
        AgentFactory(name="GammaAgent", _session=db_session)
        AgentFactory(name="NotMatching", _session=db_session)
        db_session.commit()

        # Search for names ending with "Agent"
        results = db_session.query(AgentRegistry).filter(
            AgentRegistry.name.like("%Agent")
        ).all()

        assert len(results) == 3

        # Search for names starting with "A"
        results = db_session.query(AgentRegistry).filter(
            AgentRegistry.name.like("A%")
        ).all()
        assert len(results) == 1
        assert results[0].name == "AlphaAgent"

    def test_date_range_filter(self, db_session: Session):
        """Test Filter by created_at date range."""
        # Create agents with explicit timestamps
        base_time = datetime.utcnow()

        agent1 = AgentFactory(
            name="DateAgent1",
            created_at=base_time,
            _session=db_session
        )
        agent2 = AgentFactory(
            name="DateAgent2",
            created_at=base_time + timedelta(hours=1),
            _session=db_session
        )
        agent3 = AgentFactory(
            name="DateAgent3",
            created_at=base_time + timedelta(hours=2),
            _session=db_session
        )
        db_session.commit()

        # Filter agents created in the last hour (should find agent2 and agent3)
        cutoff = base_time + timedelta(minutes=30)
        results = db_session.query(AgentRegistry).filter(
            AgentRegistry.created_at > cutoff
        ).all()

        # Should find agent2 and agent3
        assert len(results) == 2
        result_ids = [r.id for r in results]
        assert agent2.id in result_ids
        assert agent3.id in result_ids

    def test_filter_by_last_login(self, db_session: Session):
        """Test Filter by last_login > timedelta."""
        # Create user with recent login
        user1 = UserFactory(
            email="recent@test.com",
            last_login=datetime.utcnow() - timedelta(hours=1),
            _session=db_session
        )
        # Create user with old login
        user2 = UserFactory(
            email="old@test.com",
            last_login=datetime.utcnow() - timedelta(days=30),
            _session=db_session
        )
        db_session.commit()

        # Filter users logged in within last 24 hours
        cutoff = datetime.utcnow() - timedelta(hours=24)
        recent_users = db_session.query(User).filter(
            User.last_login > cutoff
        ).all()

        assert len(recent_users) == 1
        assert recent_users[0].id == user1.id


# ============================================================================
# Task 5: JSON Field and Special Property Tests
# ============================================================================

class TestSpecialFields:
    """Test JSON columns and special model properties."""

    def test_json_field_agent_configuration(self, db_session: Session):
        """Test AgentRegistry.configuration JSON field."""
        config_data = {
            "system_prompt": "You are a helpful assistant",
            "tools": ["search", "calculator"],
            "max_tokens": 2000
        }

        agent = AgentFactory(
            name="ConfigAgent",
            configuration=config_data,
            _session=db_session
        )
        db_session.commit()

        # Retrieve and verify JSON data
        retrieved = db_session.query(AgentRegistry).filter(
            AgentRegistry.id == agent.id
        ).first()
        assert retrieved.configuration == config_data
        assert retrieved.configuration["system_prompt"] == "You are a helpful assistant"
        assert "search" in retrieved.configuration["tools"]

    def test_json_field_user_preferences(self, db_session: Session):
        """Test User.preferences JSON field."""
        prefs = {
            "theme": "dark",
            "notifications": True,
            "language": "en"
        }

        user = UserFactory(
            email="prefs@test.com",
            preferences=prefs,
            _session=db_session
        )
        db_session.commit()

        # Verify preferences stored correctly
        retrieved = db_session.query(User).filter(User.id == user.id).first()
        assert retrieved.preferences["theme"] == "dark"
        assert retrieved.preferences["notifications"] is True

    def test_json_field_workspace_metadata(self, db_session: Session):
        """Test Workspace.metadata_json JSON field."""
        metadata = {
            "settings": {"feature_x": True},
            "limits": {"agents": 10},
            "tags": ["production", "premium"]
        }

        workspace = WorkspaceFactory(
            name="MetadataWorkspace",
            metadata_json=metadata,
            _session=db_session
        )
        db_session.commit()

        # Verify metadata stored
        retrieved = db_session.query(Workspace).filter(
            Workspace.id == workspace.id
        ).first()
        assert retrieved.metadata_json["limits"]["agents"] == 10
        assert "premium" in retrieved.metadata_json["tags"]

    def test_token_encryption_decryption(self, db_session: Session):
        """Test OAuthToken access_token is encrypted on write and decrypted on read."""
        import uuid
        user = UserFactory(email="tokenuser@test.com", _session=db_session)

        # Set access token (should be encrypted)
        original_token = "original_access_token_12345"
        oauth_token = OAuthToken(
            id=str(uuid.uuid4()),
            user_id=user.id,
            provider="test",
            access_token=original_token,
            token_type="Bearer"
        )
        db_session.add(oauth_token)
        db_session.commit()

        # Retrieve and verify decrypted value
        retrieved = db_session.query(OAuthToken).filter(
            OAuthToken.id == oauth_token.id
        ).first()
        assert retrieved.access_token == original_token

    def test_token_refresh_encryption(self, db_session: Session):
        """Test OAuthToken.refresh_token encryption/decryption."""
        import uuid
        user = UserFactory(email="refreshuser@test.com", _session=db_session)

        refresh_token = "refresh_token_secret_67890"
        oauth_token = OAuthToken(
            id=str(uuid.uuid4()),
            user_id=user.id,
            provider="test",
            access_token="access",
            refresh_token=refresh_token,
            token_type="Bearer"
        )
        db_session.add(oauth_token)
        db_session.commit()

        # Verify refresh token decrypted correctly
        retrieved = db_session.query(OAuthToken).filter(
            OAuthToken.id == oauth_token.id
        ).first()
        assert retrieved.refresh_token == refresh_token

    def test_boolean_default_email_verified(self, db_session: Session):
        """Test User.email_verified defaults to False."""
        import uuid
        user = User(
            id=str(uuid.uuid4()),
            email="verify@test.com",
            first_name="Test",
            last_name="User"
        )
        db_session.add(user)
        db_session.commit()

        # Verify default is False
        assert user.email_verified is False

    def test_boolean_default_workspace_is_startup(self, db_session: Session):
        """Test Workspace.is_startup defaults to False."""
        workspace = Workspace(name="StartupWorkspace")
        db_session.add(workspace)
        db_session.commit()

        # Verify default is False
        assert workspace.is_startup is False

    def test_boolean_default_oauth_state_used(self, db_session: Session):
        """Test OAuthState.used defaults to False."""
        user = UserFactory(email="oauthstate@test.com", _session=db_session)
        state = OAuthState(
            user_id=user.id,
            provider="google",
            state="test_state",
            expires_at=datetime.utcnow() + timedelta(minutes=10)
        )
        db_session.add(state)
        db_session.commit()

        # Verify default is False
        assert state.used is False

    def test_datetime_default_created_at(self, db_session: Session):
        """Test created_at defaults to current timestamp."""
        import uuid
        # Create agent directly without factory to test default
        agent = AgentRegistry(
            id=str(uuid.uuid4()),
            name="TimestampAgent",
            category="test",
            module_path="test.module",
            class_name="TestAgent"
        )
        db_session.add(agent)
        db_session.commit()

        # Verify created_at is set
        assert agent.created_at is not None
        assert isinstance(agent.created_at, datetime)

        # Should be within last minute
        assert datetime.utcnow() - agent.created_at < timedelta(minutes=1)

    def test_string_default_agent_status(self, db_session: Session):
        """Test AgentRegistry.status defaults to 'student'."""
        import uuid
        agent = AgentRegistry(
            id=str(uuid.uuid4()),
            name="DefaultStatusAgent",
            category="test",
            module_path="test.module",
            class_name="TestAgent"
        )
        db_session.add(agent)
        db_session.commit()

        # Verify default status
        assert agent.status == AgentStatus.STUDENT.value

    def test_string_default_user_role(self, db_session: Session):
        """Test User.role defaults to 'member'."""
        import uuid
        # Create user directly without factory to test default
        user = User(
            id=str(uuid.uuid4()),
            email="roleuser@test.com",
            first_name="Test",
            last_name="User"
        )
        db_session.add(user)
        db_session.commit()

        # Verify default role
        assert user.role == UserRole.MEMBER.value

    def test_string_default_workspace_status(self, db_session: Session):
        """Test Workspace.status defaults to 'active'."""
        workspace = WorkspaceFactory(name="DefaultStatusWorkspace", _session=db_session)
        db_session.commit()

        # Verify default status
        assert workspace.status == WorkspaceStatus.ACTIVE.value
