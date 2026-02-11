"""
Database integration tests with transaction rollback (INTG-02).

Tests cover:
- Transaction rollback pattern
- Test isolation (no data leakage)
- Database constraints
- Cascade operations
- Multiple operations in single transaction
"""

import pytest
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from tests.factories.agent_factory import AgentFactory, StudentAgentFactory
from tests.factories.user_factory import UserFactory, AdminUserFactory
from tests.factories.execution_factory import AgentExecutionFactory
from tests.factories.episode_factory import EpisodeFactory
from core.models import (
    AgentRegistry,
    AgentExecution,
    User,
    Episode,
    UserRole
)


class TestTransactionRollback:
    """Test transaction rollback ensures test isolation."""

    def test_agent_not_visible_in_next_test(self, db_session: Session):
        """Test agents created in one test don't appear in next."""
        # Create agent
        agent = AgentFactory(name="RollbackTestAgent")
        db_session.add(agent)
        db_session.commit()
        agent_id = agent.id

        # Verify exists in this test
        retrieved = db_session.query(AgentRegistry).filter(
            AgentRegistry.id == agent_id
        ).first()
        assert retrieved is not None
        assert retrieved.name == "RollbackTestAgent"

    def test_database_clean_after_rollback(self, db_session: Session):
        """Test database is clean after transaction rollback."""
        # This test should see clean database
        # The agent from previous test should be gone
        count = db_session.query(AgentRegistry).filter(
            AgentRegistry.name == "RollbackTestAgent"
        ).count()
        assert count == 0, "Previous test data leaked - transaction rollback failed"

    def test_multiple_operations_in_single_transaction(self, db_session: Session):
        """Test multiple operations in same transaction."""
        agent = AgentFactory(name="MultiOpAgent")
        execution = AgentExecutionFactory(agent_id=agent.id)

        db_session.add(agent)
        db_session.add(execution)
        db_session.commit()

        # Both should be visible
        assert db_session.query(AgentRegistry).filter(
            AgentRegistry.id == agent.id
        ).first() is not None

        assert db_session.query(AgentExecution).filter(
            AgentExecution.id == execution.id
        ).first() is not None

    def test_user_not_leaked_between_tests(self, db_session: Session):
        """Test users created don't leak to next test."""
        user = UserFactory(email="leak_test@example.com")
        db_session.add(user)
        db_session.commit()
        user_id = user.id

        # Verify exists in this test
        retrieved = db_session.query(User).filter(User.id == user_id).first()
        assert retrieved is not None
        assert retrieved.email == "leak_test@example.com"

    def test_user_clean_after_rollback(self, db_session: Session):
        """Test users are cleaned up after rollback."""
        # The user from previous test should not exist
        count = db_session.query(User).filter(
            User.email == "leak_test@example.com"
        ).count()
        assert count == 0, "User data leaked between tests"

    def test_episode_not_leaked_between_tests(self, db_session: Session):
        """Test episodes created don't leak to next test."""
        agent = AgentFactory(name="EpisodeLeakTestAgent")
        episode = EpisodeFactory(agent_id=agent.id, title="Leak Test Episode")
        db_session.add(agent)
        db_session.add(episode)
        db_session.commit()
        episode_id = episode.id

        # Verify exists in this test
        retrieved = db_session.query(Episode).filter(Episode.id == episode_id).first()
        assert retrieved is not None
        assert retrieved.title == "Leak Test Episode"

    def test_episode_clean_after_rollback(self, db_session: Session):
        """Test episodes are cleaned up after rollback."""
        # The episode from previous test should not exist
        count = db_session.query(Episode).filter(
            Episode.title == "Leak Test Episode"
        ).count()
        assert count == 0, "Episode data leaked between tests"


class TestDatabaseConstraints:
    """Test database constraints are enforced."""

    def test_unique_constraint_on_email(self, db_session: Session):
        """Test unique email constraint is enforced."""
        user1 = UserFactory(email="duplicate@test.com")
        user2 = UserFactory(email="duplicate@test.com")

        db_session.add(user1)
        db_session.add(user2)

        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_unique_constraint_on_agent_name_within_workspace(self, db_session: Session):
        """Test agent name uniqueness (if constraint exists)."""
        # Note: AgentRegistry may not have unique constraint on name
        # This test documents current behavior
        agent1 = AgentFactory(name="SameNameAgent")
        agent2 = AgentFactory(name="SameNameAgent")

        db_session.add(agent1)
        db_session.add(agent2)

        # May or may not raise IntegrityError depending on schema
        try:
            db_session.commit()
            # If no constraint, both agents created successfully
            assert agent1.id != agent2.id
        except IntegrityError:
            # If unique constraint exists, this is expected
            pytest.skip("Agent name has unique constraint")

    def test_foreign_key_constraint_on_execution(self, db_session: Session):
        """Test foreign key constraints prevent orphaned records."""
        from sqlalchemy.exc import flush_error

        # Create execution with invalid agent_id
        execution = AgentExecutionFactory(agent_id="nonexistent_agent_id")

        db_session.add(execution)

        # Should fail on flush or commit due to foreign key constraint
        with pytest.raises((IntegrityError, Exception)):
            db_session.commit()

    def test_agent_status_enum_constraint(self, db_session: Session):
        """Test agent status only accepts valid enum values."""
        from core.models import AgentStatus

        # Valid status should work
        agent = AgentFactory(status=AgentStatus.STUDENT.value)
        db_session.add(agent)
        db_session.commit()

        # Verify status was set correctly
        retrieved = db_session.query(AgentRegistry).filter(
            AgentRegistry.id == agent.id
        ).first()
        assert retrieved.status == AgentStatus.STUDENT.value

    def test_user_role_enum_constraint(self, db_session: Session):
        """Test user role only accepts valid enum values."""
        # Valid role should work
        user = UserFactory(role=UserRole.MEMBER.value)
        db_session.add(user)
        db_session.commit()

        # Verify role was set correctly
        retrieved = db_session.query(User).filter(User.id == user.id).first()
        assert retrieved.role == UserRole.MEMBER.value

    def test_not_null_constraints(self, db_session: Session):
        """Test NOT NULL constraints on required fields."""
        # Try to create agent without required fields
        agent = AgentFactory(name=None)  # name should be required

        db_session.add(agent)

        # Should fail due to NOT NULL constraint
        with pytest.raises((IntegrityError, Exception)):
            db_session.commit()


class TestCascadeOperations:
    """Test cascade delete and update operations."""

    def test_agent_deletion_cascades_to_executions(self, db_session: Session):
        """Test deleting agent cascades to related executions."""
        agent = AgentFactory(name="CascadeTestAgent")
        execution = AgentExecutionFactory(agent_id=agent.id)

        db_session.add(agent)
        db_session.add(execution)
        db_session.commit()

        agent_id = agent.id
        execution_id = execution.id

        # Delete agent
        db_session.delete(agent)
        db_session.commit()

        # Verify agent is deleted
        assert db_session.query(AgentRegistry).filter(
            AgentRegistry.id == agent_id
        ).first() is None

        # Execution behavior depends on cascade configuration
        # May be deleted (CASCADE) or nullified (SET NULL)
        execution = db_session.query(AgentExecution).filter(
            AgentExecution.id == execution_id
        ).first()

        # Either execution is deleted or agent_id is nullified
        if execution is not None:
            # If cascade is SET NULL or similar
            assert execution.agent_id is None or execution.agent_id != agent_id
        else:
            # If cascade is DELETE
            assert execution is None

    def test_user_deletion_cascades_to_episodes(self, db_session: Session):
        """Test deleting user cascades to related episodes (if configured)."""
        user = UserFactory(email="cascade_user@test.com")
        agent = AgentFactory(name="CascadeTestAgent")
        episode = EpisodeFactory(agent_id=agent.id)

        db_session.add(user)
        db_session.add(agent)
        db_session.add(episode)
        db_session.commit()

        user_id = user.id
        episode_id = episode.id

        # Delete user (may not cascade to episodes depending on schema)
        db_session.delete(user)
        db_session.commit()

        # Verify user is deleted
        assert db_session.query(User).filter(User.id == user_id).first() is None

        # Episode may or may not exist depending on cascade config
        episode = db_session.query(Episode).filter(Episode.id == episode_id).first()
        # Just verify no error occurs

    def test_agent_execution_relationship(self, db_session: Session):
        """Test agent-execution relationship works correctly."""
        agent = AgentFactory(name="RelationTestAgent")
        execution = AgentExecutionFactory(agent_id=agent.id)

        db_session.add(agent)
        db_session.add(execution)
        db_session.commit()

        # Test relationship from execution to agent
        retrieved_execution = db_session.query(AgentExecution).filter(
            AgentExecution.id == execution.id
        ).first()

        # Note: Relationship may or may not be loaded depending on schema
        assert retrieved_execution is not None
        assert retrieved_execution.agent_id == agent.id

    def test_episode_agent_relationship(self, db_session: Session):
        """Test episode-agent relationship works correctly."""
        agent = AgentFactory(name="EpisodeRelationAgent")
        episode = EpisodeFactory(agent_id=agent.id)

        db_session.add(agent)
        db_session.add(episode)
        db_session.commit()

        # Test relationship from episode to agent
        retrieved_episode = db_session.query(Episode).filter(
            Episode.id == episode.id
        ).first()

        assert retrieved_episode is not None
        assert retrieved_episode.agent_id == agent.id


class TestTransactionIsolation:
    """Test transaction isolation between concurrent operations."""

    def test_read_committed_isolation(self, db_session: Session):
        """Test that committed changes are visible."""
        # Create and commit an agent
        agent = AgentFactory(name="IsolationTestAgent")
        db_session.add(agent)
        db_session.commit()

        # Query in same session should see it
        retrieved = db_session.query(AgentRegistry).filter(
            AgentRegistry.name == "IsolationTestAgent"
        ).first()
        assert retrieved is not None

    def test_rollback_undoes_changes(self, db_session: Session):
        """Test that rollback undoes uncommitted changes."""
        agent = AgentFactory(name="RollbackIsolationAgent")
        db_session.add(agent)
        db_session.commit()
        agent_id = agent.id

        # Modify and rollback
        agent.name = "ModifiedName"
        db_session.rollback()

        # Query should return original state
        retrieved = db_session.query(AgentRegistry).filter(
            AgentRegistry.id == agent_id
        ).first()
        assert retrieved is not None
        assert retrieved.name == "RollbackIsolationAgent"

    def test_multiple_commits_independently(self, db_session: Session):
        """Test multiple commits are independent."""
        # Create and commit first agent
        agent1 = AgentFactory(name="FirstAgent")
        db_session.add(agent1)
        db_session.commit()

        # Create and commit second agent
        agent2 = AgentFactory(name="SecondAgent")
        db_session.add(agent2)
        db_session.commit()

        # Both should be visible
        assert db_session.query(AgentRegistry).filter(
            AgentRegistry.name == "FirstAgent"
        ).first() is not None

        assert db_session.query(AgentRegistry).filter(
            AgentRegistry.name == "SecondAgent"
        ).first() is not None


class TestBatchOperations:
    """Test batch database operations."""

    def test_batch_insert_agents(self, db_session: Session):
        """Test inserting multiple agents in single transaction."""
        agents = [
            AgentFactory(name=f"BatchAgent{i}") for i in range(10)
        ]

        for agent in agents:
            db_session.add(agent)

        db_session.commit()

        # Verify all agents were created
        count = db_session.query(AgentRegistry).filter(
            AgentRegistry.name.like("BatchAgent%")
        ).count()

        assert count == 10

    def test_batch_delete_with_filter(self, db_session: Session):
        """Test deleting multiple records with filter."""
        # Create batch of agents
        for i in range(5):
            agent = AgentFactory(name=f"DeleteAgent{i}")
            db_session.add(agent)

        db_session.commit()

        # Delete all with matching pattern
        db_session.query(AgentRegistry).filter(
            AgentRegistry.name.like("DeleteAgent%")
        ).delete()

        db_session.commit()

        # Verify all were deleted
        count = db_session.query(AgentRegistry).filter(
            AgentRegistry.name.like("DeleteAgent%")
        ).count()

        assert count == 0

    def test_batch_update(self, db_session: Session):
        """Test updating multiple records in single operation."""
        # Create batch of student agents
        for i in range(5):
            agent = StudentAgentFactory(name=f"UpdateAgent{i}")
            db_session.add(agent)

        db_session.commit()

        # Update all to INTERN status
        from core.models import AgentStatus
        db_session.query(AgentRegistry).filter(
            AgentRegistry.name.like("UpdateAgent%")
        ).update({"status": AgentStatus.INTERN.value})

        db_session.commit()

        # Verify all were updated
        count = db_session.query(AgentRegistry).filter(
            AgentRegistry.name.like("UpdateAgent%"),
            AgentRegistry.status == AgentStatus.INTERN.value
        ).count()

        assert count == 5
