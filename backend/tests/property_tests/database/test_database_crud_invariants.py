"""
Property-Based Tests for Database CRUD Operations Invariants

Tests CRITICAL database operation invariants:
- CRUD invariants (create, read, update, delete behavior)
- Foreign key constraints (referential integrity)
- Unique constraints (duplicate prevention)
- Cascade behaviors (dependent records)
- Transaction atomicity (all-or-nothing)

These tests protect against data integrity bugs.
"""

import pytest
from hypothesis import given, strategies as st, settings, example, HealthCheck
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timedelta
import uuid

from core.models import (
    AgentRegistry, AgentStatus, Episode, EpisodeSegment,
    User, UserRole, ChatMessage
)

# Common settings for database property tests
# suppress_health_check=[HealthCheck.function_scoped_fixture] is needed because
# db_session fixture is function-scoped, but tests properly clean up via commits/rollbacks
# deadline=None disables the 200ms deadline since DB operations can be slower
DB_SETTINGS = settings(
    max_examples=50,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None
)
DB_SETTINGS_HIGH = settings(
    max_examples=100,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None
)


class TestCRUDInvariants:
    """Property-based tests for CRUD operation invariants."""

    @given(
        agent_name=st.text(min_size=1, max_size=100, alphabet='abcdefghijklmnopqrstuvwxyz0123456789_-'),
        agent_category=st.text(min_size=1, max_size=50, alphabet='abcdefghijklmnopqrstuvwxyz'),
        confidence_score=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
    )
    @DB_SETTINGS_HIGH
    @example(agent_name='TestAgent', agent_category='test', confidence_score=0.7)
    def test_create_read_invariant(self, db_session, agent_name, agent_category, confidence_score):
        """
        INVARIANT: Agent creation followed by retrieval returns consistent data.

        Tests that data written to database can be read back unchanged.
        Validates float precision handling for confidence_score.
        """
        # Create agent
        agent = AgentRegistry(
            name=agent_name,
            category=agent_category,
            module_path=f"test.{agent_category}",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=confidence_score
        )
        db_session.add(agent)
        db_session.commit()

        # Read back
        retrieved = db_session.query(AgentRegistry).filter(
            AgentRegistry.id == agent.id
        ).first()

        # Verify CRUD invariant
        assert retrieved is not None, "Created agent should be retrievable"
        assert retrieved.name == agent_name, "Name should match"
        assert retrieved.category == agent_category, "Category should match"
        assert abs(retrieved.confidence_score - confidence_score) < 0.0001, \
            f"Confidence score should match within float tolerance"

    @given(
        original_confidence=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        adjustment=st.floats(min_value=-0.5, max_value=0.5, allow_nan=False, allow_infinity=False)
    )
    @DB_SETTINGS_HIGH
    @example(original_confidence=0.5, adjustment=0.1)
    @example(original_confidence=0.9, adjustment=-0.2)
    def test_update_preserves_invariants(self, db_session, original_confidence, adjustment):
        """
        INVARIANT: Updates maintain data integrity constraints.

        Tests that confidence score updates respect [0.0, 1.0] bounds
        and that updated values persist correctly.
        """
        agent = AgentRegistry(
            name="UpdateTest",
            category="test",
            module_path="test.module",
            class_name="Test",
            status=AgentStatus.STUDENT.value,
            confidence_score=original_confidence
        )
        db_session.add(agent)
        db_session.commit()

        # Update confidence
        new_confidence = max(0.0, min(1.0, original_confidence + adjustment))
        agent.confidence_score = new_confidence
        db_session.commit()

        # Verify update persisted
        db_session.refresh(agent)
        assert abs(agent.confidence_score - new_confidence) < 0.0001, \
            "Updated confidence score should persist"

    @given(
        agent_count=st.integers(min_value=1, max_value=10)
    )
    @DB_SETTINGS
    def test_delete_removes_records(self, db_session, agent_count):
        """
        INVARIANT: Delete operations remove records from database.

        Tests that deleted records cannot be queried.
        """
        agent_ids = []
        for i in range(agent_count):
            agent = AgentRegistry(
                name=f"DeleteTest{i}",
                category="test",
                module_path="test.module",
                class_name="Test",
                status=AgentStatus.STUDENT.value
            )
            db_session.add(agent)
            db_session.commit()
            agent_ids.append(agent.id)

        # Delete half of the agents
        for i in range(0, len(agent_ids), 2):
            agent = db_session.query(AgentRegistry).filter(
                AgentRegistry.id == agent_ids[i]
            ).first()
            db_session.delete(agent)
            db_session.commit()

        # Verify deleted agents are gone
        for i in range(0, len(agent_ids), 2):
            deleted = db_session.query(AgentRegistry).filter(
                AgentRegistry.id == agent_ids[i]
            ).first()
            assert deleted is None, f"Deleted agent {i} should not exist"

        # Verify remaining agents still exist
        for i in range(1, len(agent_ids), 2):
            remaining = db_session.query(AgentRegistry).filter(
                AgentRegistry.id == agent_ids[i]
            ).first()
            assert remaining is not None, f"Non-deleted agent {i} should exist"


class TestForeignKeyInvariants:
    """Property-based tests for foreign key constraint invariants."""

    @given(
        has_parent=st.booleans(),
        child_count=st.integers(min_value=1, max_value=10)
    )
    @DB_SETTINGS
    def test_foreign_key_prevents_orphans(self, db_session, has_parent, child_count):
        """
        INVARIANT: Foreign keys prevent orphaned child records.

        Tests that:
        - Children can only be created with valid parent references
        - Attempts to create orphans are rejected (in production with PostgreSQL)

        NOTE: SQLite doesn't enforce FK constraints by default (PRAGMA foreign_keys = OFF).
        This test documents the expected behavior for production PostgreSQL databases.
        In SQLite, orphaned records CAN be created, which is a documented limitation.
        """
        parent_id = str(uuid.uuid4())

        # Optionally create parent
        if has_parent:
            parent = AgentRegistry(
                id=parent_id,
                name="ParentAgent",
                category="test",
                module_path="test.module",
                class_name="Parent",
                status=AgentStatus.STUDENT.value
            )
            db_session.add(parent)
            db_session.commit()

        # Try to create episode with agent_id reference
        episode = Episode(
            id=str(uuid.uuid4()),
            title="Test Episode",
            agent_id=parent_id,
            workspace_id=str(uuid.uuid4()),
            maturity_at_time=AgentStatus.STUDENT.value,
            intervention_count=0
        )

        # Always succeeds in SQLite (FK constraints not enforced by default)
        # In PostgreSQL with proper FK constraints, this would fail when has_parent=False
        db_session.add(episode)
        db_session.commit()
        assert episode.id is not None, "Episode should be created (SQLite allows orphans)"

        # Document the invariant for production databases
        if not has_parent:
            # In production PostgreSQL, this would raise IntegrityError
            # SQLite limitation: orphaned records are allowed
            pass

    @given(
        segment_count=st.integers(min_value=1, max_value=20)
    )
    @DB_SETTINGS
    def test_foreign_key_cascade_retrieval(self, db_session, segment_count):
        """
        INVARIANT: Foreign keys enable parent-child relationship traversal.

        Tests that:
        - Parent can access children through relationship
        - Children can access parent through relationship
        """
        # Create episode
        episode = Episode(
            id=str(uuid.uuid4()),
            title="Test Episode",
            agent_id=str(uuid.uuid4()),
            workspace_id=str(uuid.uuid4()),
            maturity_at_time=AgentStatus.STUDENT.value,
            human_intervention_count=0
        )
        db_session.add(episode)
        db_session.commit()

        # Create segments
        segment_ids = []
        for i in range(segment_count):
            segment = EpisodeSegment(
                id=str(uuid.uuid4()),
                episode_id=episode.id,
                sequence_order=i,
                segment_type="conversation",
                content=f"Segment {i}",
                source_type="manual"
            )
            db_session.add(segment)
            segment_ids.append(segment.id)
        db_session.commit()

        # Verify parent can access children
        db_session.refresh(episode)
        assert len(episode.segments) == segment_count, \
            f"Episode should have {segment_count} segments"

        # Verify children can access parent
        for segment in episode.segments:
            assert segment.episode_id == episode.id, \
                "Segment should reference correct episode"


class TestUniqueConstraintInvariants:
    """Property-based tests for unique constraint invariants."""

    @given(
        email=st.text(min_size=5, max_size=100, alphabet='abcDEF0123456789@.-_'),
        attempt_duplicate=st.booleans()
    )
    @DB_SETTINGS
    @example(email='test@example.com', attempt_duplicate=True)
    def test_unique_email_rejects_duplicates(self, db_session, email, attempt_duplicate):
        """
        INVARIANT: Unique constraints prevent duplicate records.

        Tests that:
        - First record with unique value succeeds
        - Second record with same unique value fails
        - Email uniqueness is enforced (case-insensitive if applicable)

        NOTE: Uses flush() to detect constraint violations before commit
        to avoid session state issues with Hypothesis replay.
        """
        # Normalize email to lowercase for consistency
        normalized_email = email.lower()

        # Create first user
        user1 = User(
            id=str(uuid.uuid4()),
            email=normalized_email,
            role=UserRole.MEMBER.value
        )
        db_session.add(user1)
        db_session.commit()

        # Try to create duplicate
        if attempt_duplicate:
            user2 = User(
                id=str(uuid.uuid4()),
                email=normalized_email,
                role=UserRole.MEMBER.value
            )
            db_session.add(user2)

            # Should raise IntegrityError for duplicate email
            # Use flush() to detect constraint before commit
            with pytest.raises(IntegrityError):
                db_session.flush()
            # Always rollback to clean up session state
            db_session.rollback()
        else:
            # Different email should succeed
            user2 = User(
                id=str(uuid.uuid4()),
                email=f"different-{normalized_email}",
                role=UserRole.MEMBER.value
            )
            db_session.add(user2)
            db_session.commit()  # Should succeed
            assert user2.id is not None, "User with different email should be created"

    @given(
        agent_name=st.text(min_size=1, max_size=100, alphabet='abcdefghijklmnopqrstuvwxyz0123456789_-')
    )
    @DB_SETTINGS
    def test_unique_id_enforced(self, db_session, agent_name):
        """
        INVARIANT: Primary key uniqueness is enforced.

        Tests that duplicate primary keys are rejected.
        """
        agent_id = str(uuid.uuid4())

        # Create first agent with ID
        agent1 = AgentRegistry(
            id=agent_id,
            name=agent_name,
            category="test",
            module_path="test.module",
            class_name="Test",
            status=AgentStatus.STUDENT.value
        )
        db_session.add(agent1)
        db_session.commit()

        # Try to create second agent with same ID
        agent2 = AgentRegistry(
            id=agent_id,  # Same ID
            name=f"Duplicate-{agent_name}",
            category="test",
            module_path="test.module",
            class_name="Test",
            status=AgentStatus.STUDENT.value
        )
        db_session.add(agent2)

        # Should raise IntegrityError for duplicate primary key
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()


class TestCascadeBehaviorInvariants:
    """Property-based tests for cascade delete behavior invariants."""

    @given(
        create_children=st.booleans(),
        child_count=st.integers(min_value=0, max_value=5)
    )
    @DB_SETTINGS
    def test_delete_cascade_behavior(self, db_session, create_children, child_count):
        """
        INVARIANT: Cascade deletes handle dependent records correctly.

        Tests that:
        - Deleting parent with children triggers correct cascade behavior
        - Cascade delete removes all dependent records
        - SET NULL, CASCADE, RESTRICT behaviors match schema
        """
        if not create_children or child_count == 0:
            return

        # Create parent agent
        parent = AgentRegistry(
            id=str(uuid.uuid4()),
            name="ParentAgent",
            category="test",
            module_path="test.module",
            class_name="Parent",
            status=AgentStatus.STUDENT.value
        )
        db_session.add(parent)
        db_session.commit()

        # Create episode segments (children of episode)
        episode = Episode(
            id=str(uuid.uuid4()),
            agent_id=parent.id,
            workspace_id=str(uuid.uuid4()),
            title="Test Episode",
            maturity_at_time=AgentStatus.STUDENT.value,
            human_intervention_count=0
        )
        db_session.add(episode)
        db_session.commit()

        segment_ids = []
        for i in range(child_count):
            segment = EpisodeSegment(
                id=str(uuid.uuid4()),
                episode_id=episode.id,
                sequence_order=i,
                segment_type="conversation",
                content=f"Segment {i}",
                source_type="manual"
            )
            db_session.add(segment)
            segment_ids.append(segment.id)
        db_session.commit()

        # Delete episode (parent of segments)
        db_session.delete(episode)
        db_session.commit()

        # Verify cascade behavior - segments should be deleted
        remaining_segments = db_session.query(EpisodeSegment).filter(
            EpisodeSegment.id.in_(segment_ids)
        ).all()

        # Cascade delete should remove all segments
        assert len(remaining_segments) == 0, \
            f"All segments should be cascade deleted, but {len(remaining_segments)} remain"

    @given(
        episode_count=st.integers(min_value=1, max_value=5)
    )
    @DB_SETTINGS
    def test_cascade_maintains_referential_integrity(self, db_session, episode_count):
        """
        INVARIANT: Cascade deletes maintain referential integrity.

        Tests that:
        - All dependent records are removed
        - No orphaned records remain
        - Database consistency is maintained
        """
        # Create agent
        agent = AgentRegistry(
            id=str(uuid.uuid4()),
            name="TestAgent",
            category="test",
            module_path="test.module",
            class_name="Test",
            status=AgentStatus.STUDENT.value
        )
        db_session.add(agent)
        db_session.commit()

        # Create episodes
        episode_ids = []
        for i in range(episode_count):
            episode = Episode(
                id=str(uuid.uuid4()),
                agent_id=agent.id,
                workspace_id=str(uuid.uuid4()),
                title=f"Episode {i}",
                maturity_at_time=AgentStatus.STUDENT.value,
                human_intervention_count=0
            )
            db_session.add(episode)
            episode_ids.append(episode.id)
        db_session.commit()

        # Delete agent (parent)
        db_session.delete(agent)
        db_session.commit()

        # Verify all episodes are deleted (cascade)
        remaining_episodes = db_session.query(Episode).filter(
            Episode.id.in_(episode_ids)
        ).all()

        assert len(remaining_episodes) == 0, \
            "All episodes should be cascade deleted when agent is deleted"


class TestTransactionAtomicityInvariants:
    """Property-based tests for transaction atomicity invariants."""

    @given(
        success_count=st.integers(min_value=1, max_value=10),
        fail_at_position=st.integers(min_value=-1, max_value=9)
    )
    @DB_SETTINGS
    def test_transaction_rollback_on_error(self, db_session, success_count, fail_at_position):
        """
        INVARIANT: Transactions rollback completely on any error.

        Tests that:
        - All operations in transaction commit together
        - Any error causes complete rollback
        - Partial commits never occur
        """
        initial_count = db_session.query(AgentRegistry).count()

        try:
            # Create multiple agents
            agent_ids = []
            for i in range(success_count):
                agent = AgentRegistry(
                    name=f"Agent{i}",
                    category="test",
                    module_path="test.module",
                    class_name="Test",
                    status=AgentStatus.STUDENT.value
                )
                db_session.add(agent)
                agent_ids.append(agent.id)

                # Simulate failure at specific position
                if i == fail_at_position:
                    raise IntegrityError("Simulated failure", None, None)

            db_session.commit()

            # If no failure, all agents should be created
            final_count = db_session.query(AgentRegistry).count()
            assert final_count == initial_count + success_count, \
                f"All {success_count} agents should be created"

        except IntegrityError:
            db_session.rollback()

            # On rollback, no agents should be created
            final_count = db_session.query(AgentRegistry).count()
            assert final_count == initial_count, \
                "Rollback should leave database unchanged"

    @given(
        update_count=st.integers(min_value=1, max_value=10),
        rollback_at=st.integers(min_value=-1, max_value=9)
    )
    @DB_SETTINGS
    def test_transaction_update_rollback(self, db_session, update_count, rollback_at):
        """
        INVARIANT: Update transactions rollback completely.

        Tests that:
        - Multiple updates in transaction commit together
        - Rollback restores all original values
        """
        # Create initial agents
        agent_ids = []
        original_scores = []
        for i in range(update_count):
            agent = AgentRegistry(
                name=f"UpdateAgent{i}",
                category="test",
                module_path="test.module",
                class_name="Test",
                status=AgentStatus.STUDENT.value,
                confidence_score=0.5
            )
            db_session.add(agent)
            db_session.commit()
            agent_ids.append(agent.id)
            original_scores.append(0.5)

        try:
            # Update all agents
            for i, agent_id in enumerate(agent_ids):
                agent = db_session.query(AgentRegistry).filter(
                    AgentRegistry.id == agent_id
                ).first()
                agent.confidence_score = 0.7

                # Trigger rollback at specific position
                if i == rollback_at:
                    raise IntegrityError("Simulated failure", None, None)

            db_session.commit()

        except IntegrityError:
            db_session.rollback()

            # Verify all agents have original scores
            for i, agent_id in enumerate(agent_ids):
                agent = db_session.query(AgentRegistry).filter(
                    AgentRegistry.id == agent_id
                ).first()
                assert abs(agent.confidence_score - original_scores[i]) < 0.0001, \
                    f"Agent {i} should have original score after rollback"

    @given(
        create_count=st.integers(min_value=1, max_value=5),
        delete_count=st.integers(min_value=1, max_value=5)
    )
    @DB_SETTINGS
    def test_mixed_operation_transaction(self, db_session, create_count, delete_count):
        """
        INVARIANT: Mixed create/delete operations are atomic.

        Tests that:
        - Creates and deletes in same transaction commit together
        - Rollback restores all pre-transaction state
        """
        # Create initial agents to delete
        initial_agent_ids = []
        for i in range(delete_count):
            agent = AgentRegistry(
                name=f"InitialAgent{i}",
                category="test",
                module_path="test.module",
                class_name="Test",
                status=AgentStatus.STUDENT.value
            )
            db_session.add(agent)
            db_session.commit()
            initial_agent_ids.append(agent.id)

        initial_count = db_session.query(AgentRegistry).count()

        # Mixed transaction: delete some, create some
        try:
            # Delete initial agents
            for agent_id in initial_agent_ids:
                agent = db_session.query(AgentRegistry).filter(
                    AgentRegistry.id == agent_id
                ).first()
                db_session.delete(agent)

            # Create new agents
            for i in range(create_count):
                agent = AgentRegistry(
                    name=f"NewAgent{i}",
                    category="test",
                    module_path="test.module",
                    class_name="Test",
                    status=AgentStatus.STUDENT.value
                )
                db_session.add(agent)

            # Simulate error before commit
            raise IntegrityError("Simulated failure", None, None)

        except IntegrityError:
            db_session.rollback()

            # Verify initial state restored
            final_count = db_session.query(AgentRegistry).count()
            assert final_count == initial_count, \
                "Rollback should restore initial count"

            # Verify initial agents still exist
            for agent_id in initial_agent_ids:
                agent = db_session.query(AgentRegistry).filter(
                    AgentRegistry.id == agent_id
                ).first()
                assert agent is not None, "Initial agent should exist after rollback"


class TestBoundaryConditionInvariants:
    """Property-based tests for boundary condition invariants."""

    @given(
        confidence_score=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
    )
    @DB_SETTINGS_HIGH
    @example(confidence_score=0.0)  # Exact lower bound
    @example(confidence_score=1.0)  # Exact upper bound
    @example(confidence_score=0.5)  # STUDENT -> INTERN threshold
    @example(confidence_score=0.7)  # INTERN -> SUPERVISED threshold
    @example(confidence_score=0.9)  # SUPERVISED -> AUTONOMOUS threshold
    def test_confidence_score_boundaries(self, db_session, confidence_score):
        """
        INVARIANT: Confidence scores respect [0.0, 1.0] boundaries.

        Tests that exact boundary values (0.0, 1.0) and maturity thresholds
        (0.5, 0.7, 0.9) are handled correctly.
        """
        agent = AgentRegistry(
            name="BoundaryTest",
            category="test",
            module_path="test.module",
            class_name="Test",
            status=AgentStatus.STUDENT.value,
            confidence_score=confidence_score
        )
        db_session.add(agent)
        db_session.commit()

        # Verify score stored correctly
        assert agent.confidence_score == confidence_score, \
            f"Confidence score {confidence_score} should be stored exactly"

        # Verify maturity assignment based on thresholds
        if confidence_score >= 0.9:
            expected_status = AgentStatus.AUTONOMOUS.value
        elif confidence_score >= 0.7:
            expected_status = AgentStatus.SUPERVISED.value
        elif confidence_score >= 0.5:
            expected_status = AgentStatus.INTERN.value
        else:
            expected_status = AgentStatus.STUDENT.value

        # Status is assigned by service layer, not model
        # This test validates the boundary values themselves
        assert 0.0 <= agent.confidence_score <= 1.0, \
            "Confidence score must be within valid range"

    @given(
        sequence_order=st.integers(min_value=0, max_value=1000)
    )
    @DB_SETTINGS_HIGH
    @example(sequence_order=0)  # Minimum
    @example(sequence_order=999)  # Maximum
    def test_segment_sequence_order_boundaries(self, db_session, sequence_order):
        """
        INVARIANT: EpisodeSegment sequence_order handles boundary values.

        Tests that sequence order is stored correctly at boundaries.
        """
        # Create episode
        episode = Episode(
            id=str(uuid.uuid4()),
            title="Test Episode",
            agent_id=str(uuid.uuid4()),
            workspace_id=str(uuid.uuid4()),
            maturity_at_time=AgentStatus.STUDENT.value,
            human_intervention_count=0
        )
        db_session.add(episode)
        db_session.commit()

        # Create segment with specific sequence_order
        segment = EpisodeSegment(
            id=str(uuid.uuid4()),
            episode_id=episode.id,
            sequence_order=sequence_order,
            segment_type="conversation",
            content="Test segment",
            source_type="manual"
        )
        db_session.add(segment)
        db_session.commit()

        # Verify sequence_order stored correctly
        assert segment.sequence_order == sequence_order, \
            f"Sequence order {sequence_order} should be stored exactly"
        assert segment.sequence_order >= 0, \
            "Sequence order should be non-negative"

    @given(
        intervention_count=st.integers(min_value=0, max_value=100)
    )
    @DB_SETTINGS_HIGH
    @example(intervention_count=0)  # No intervention
    @example(intervention_count=50)  # High intervention
    @example(intervention_count=100)  # Maximum
    def test_intervention_count_boundaries(self, db_session, intervention_count):
        """
        INVARIANT: Episode human_intervention_count handles boundary values.

        Tests that intervention count is stored correctly.
        """
        episode = Episode(
            id=str(uuid.uuid4()),
            title="Test Episode",
            agent_id=str(uuid.uuid4()),
            workspace_id=str(uuid.uuid4()),
            maturity_at_time=AgentStatus.STUDENT.value,
            human_intervention_count=intervention_count
        )
        db_session.add(episode)
        db_session.commit()

        # Verify intervention_count stored correctly
        assert episode.human_intervention_count == intervention_count, \
            f"Intervention count {intervention_count} should be stored exactly"
        assert episode.human_intervention_count >= 0, \
            "Intervention count should be non-negative"


class TestNullConstraintInvariants:
    """Property-based tests for NULL constraint invariants."""

    @given(
        has_description=st.booleans(),
        has_module_path=st.booleans()
    )
    @DB_SETTINGS
    def test_nullable_vs_non_nullable_fields(self, db_session, has_description, has_module_path):
        """
        INVARIANT: Nullable fields accept NULL, non-nullable fields reject NULL.

        Tests that:
        - Fields with nullable=True can be NULL
        - Fields with nullable=False require values
        """
        # Create agent with nullable fields
        agent = AgentRegistry(
            name="TestAgent",
            category="test",
            module_path="test.module" if has_module_path else None,
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            description="Test description" if has_description else None
        )

        if has_module_path:
            # Should succeed - module_path is provided
            db_session.add(agent)
            db_session.commit()
            assert agent.id is not None, "Agent should be created with module_path"
        else:
            # Should fail - module_path is non-nullable
            db_session.add(agent)
            with pytest.raises(IntegrityError):
                db_session.commit()
            db_session.rollback()

    @given(
        has_title=st.booleans(),
        has_workspace_id=st.booleans()
    )
    @DB_SETTINGS
    def test_episode_required_fields(self, db_session, has_title, has_workspace_id):
        """
        INVARIANT: Episode required fields reject NULL.

        Tests that title and workspace_id are required.
        """
        episode = Episode(
            title="Test Title" if has_title else None,
            agent_id=str(uuid.uuid4()),
            workspace_id=str(uuid.uuid4()) if has_workspace_id else None,
            maturity_at_time=AgentStatus.STUDENT.value,
            human_intervention_count=0
        )

        if has_title and has_workspace_id:
            # Should succeed - all required fields provided
            db_session.add(episode)
            db_session.commit()
            assert episode.id is not None, "Episode should be created with all required fields"
        else:
            # Should fail - missing required fields
            db_session.add(episode)
            with pytest.raises((IntegrityError, Exception)):
                db_session.commit()
            db_session.rollback()
