"""
Multi-Agent Canvas Collaboration Tests

Comprehensive test suite for multi-agent canvas collaboration including:
- Session creation and management
- Agent role and permissions
- Conflict detection and resolution
- Activity tracking
- API endpoints
"""

import uuid
from datetime import datetime, timedelta
import pytest
from sqlalchemy.orm import Session

from core.canvas_collaboration_service import (
    AgentRole,
    CanvasCollaborationService,
    CollaborationMode,
)
from core.models import (
    AgentRegistry,
    CanvasAgentParticipant,
    CanvasCollaborationSession,
    CanvasConflict,
    User,
)

# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def db():
    """Create a test database session."""
    from core.database import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def test_user(db):
    """Create a test user."""
    user_id = f"user-{uuid.uuid4()}"
    user = User(
        id=user_id,
        email=f"test-{uuid.uuid4()}@example.com",
        first_name="Test",
        last_name="User"
    )
    db.add(user)
    db.commit()
    db.expunge(user)
    yield user
    db.query(CanvasAgentParticipant).filter(CanvasAgentParticipant.user_id == user_id).delete(synchronize_session=False)
    db.query(CanvasCollaborationSession).filter(CanvasCollaborationSession.user_id == user_id).delete(synchronize_session=False)
    db.query(User).filter(User.id == user_id).delete(synchronize_session=False)
    db.commit()


@pytest.fixture
def agent_a(db):
    """Create test agent A."""
    agent_id = f"agent-a-{uuid.uuid4()}"
    agent = AgentRegistry(
        id=agent_id,
        name="Agent A",
        category="Sales",
        module_path="agents.agent_a",
        class_name="AgentA",
        status="AUTONOMOUS",
        confidence_score=0.95
    )
    db.add(agent)
    db.commit()
    db.expunge(agent)
    yield agent
    db.query(CanvasAgentParticipant).filter(CanvasAgentParticipant.agent_id == agent_id).delete(synchronize_session=False)
    db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).delete(synchronize_session=False)
    db.commit()


@pytest.fixture
def agent_b(db):
    """Create test agent B."""
    agent_id = f"agent-b-{uuid.uuid4()}"
    agent = AgentRegistry(
        id=agent_id,
        name="Agent B",
        category="Finance",
        module_path="agents.agent_b",
        class_name="AgentB",
        status="AUTONOMOUS",
        confidence_score=0.92
    )
    db.add(agent)
    db.commit()
    db.expunge(agent)
    yield agent
    db.query(CanvasAgentParticipant).filter(CanvasAgentParticipant.agent_id == agent_id).delete(synchronize_session=False)
    db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).delete(synchronize_session=False)
    db.commit()


@pytest.fixture
def agent_c(db):
    """Create test agent C."""
    agent_id = f"agent-c-{uuid.uuid4()}"
    agent = AgentRegistry(
        id=agent_id,
        name="Agent C",
        category="Operations",
        module_path="agents.agent_c",
        class_name="AgentC",
        status="AUTONOMOUS",
        confidence_score=0.88
    )
    db.add(agent)
    db.commit()
    db.expunge(agent)
    yield agent
    db.query(CanvasAgentParticipant).filter(CanvasAgentParticipant.agent_id == agent_id).delete(synchronize_session=False)
    db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).delete(synchronize_session=False)
    db.commit()


# ============================================================================
# Session Management Tests
# ============================================================================

class TestCollaborationSessionManagement:
    """Test collaboration session creation and lifecycle."""

    def test_create_session_basic(self, db, test_user):
        """Test basic session creation."""
        service = CanvasCollaborationService(db)

        result = service.create_collaboration_session(
            canvas_id="canvas-123",
            session_id="session-456",
            user_id=test_user.id,
            collaboration_mode="sequential"
        )

        assert "error" not in result
        assert result["canvas_id"] == "canvas-123"
        assert result["collaboration_mode"] == "sequential"
        assert result["status"] == "active"

    def test_create_session_with_initial_agent(self, db, test_user, agent_a):
        """Test creating session with initial agent."""
        service = CanvasCollaborationService(db)

        result = service.create_collaboration_session(
            canvas_id="canvas-123",
            session_id="session-456",
            user_id=test_user.id,
            collaboration_mode="parallel",
            initial_agent_id=agent_a.id
        )

        assert "error" not in result
        assert result["collaboration_mode"] == "parallel"

        # Verify agent was added
        session_status = service.get_session_status(result["session_id"])
        assert len(session_status["participants"]) == 1
        assert session_status["participants"][0]["agent_id"] == agent_a.id
        assert session_status["participants"][0]["role"] == "owner"

    def test_get_session_status(self, db, test_user, agent_a, agent_b):
        """Test getting session status with multiple agents."""
        service = CanvasCollaborationService(db)

        # Create session
        create_result = service.create_collaboration_session(
            canvas_id="canvas-123",
            session_id="session-456",
            user_id=test_user.id,
            collaboration_mode="sequential",
            initial_agent_id=agent_a.id
        )

        session_id = create_result["session_id"]

        # Add another agent
        service.add_agent_to_session(
            collaboration_session_id=session_id,
            agent_id=agent_b.id,
            user_id=test_user.id,
            role="contributor"
        )

        # Get status
        result = service.get_session_status(session_id)

        assert "error" not in result
        assert result["canvas_id"] == "canvas-123"
        assert result["status"] == "active"
        assert len(result["participants"]) == 2

        # Verify agent roles
        participants = {p["agent_id"]: p["role"] for p in result["participants"]}
        assert participants[agent_a.id] == "owner"
        assert participants[agent_b.id] == "contributor"

    def test_complete_session(self, db, test_user, agent_a):
        """Test completing a collaboration session."""
        service = CanvasCollaborationService(db)

        # Create session with agent
        create_result = service.create_collaboration_session(
            canvas_id="canvas-123",
            session_id="session-456",
            user_id=test_user.id,
            initial_agent_id=agent_a.id
        )

        session_id = create_result["session_id"]

        # Record some actions
        service.record_agent_action(
            collaboration_session_id=session_id,
            agent_id=agent_a.id,
            action="update",
            component_id="chart-1"
        )
        service.record_agent_action(
            collaboration_session_id=session_id,
            agent_id=agent_a.id,
            action="update",
            component_id="markdown-1"
        )

        # Complete session
        result = service.complete_session(session_id)

        assert "error" not in result
        assert result["status"] == "completed"
        assert result["total_participants"] == 1
        assert result["total_actions"] == 2


# ============================================================================
# Agent Management Tests
# ============================================================================

class TestAgentManagement:
    """Test adding and removing agents from sessions."""

    def test_add_agent_to_session(self, db, test_user, agent_a, agent_b):
        """Test adding agents to session."""
        service = CanvasCollaborationService(db)

        # Create session
        create_result = service.create_collaboration_session(
            canvas_id="canvas-123",
            session_id="session-456",
            user_id=test_user.id,
            initial_agent_id=agent_a.id
        )

        session_id = create_result["session_id"]

        # Add second agent
        add_result = service.add_agent_to_session(
            collaboration_session_id=session_id,
            agent_id=agent_b.id,
            user_id=test_user.id,
            role="reviewer"
        )

        assert "error" not in add_result
        assert add_result["agent_id"] == agent_b.id
        assert add_result["role"] == "reviewer"

    def test_add_agent_exceeds_max(self, db, test_user, agent_a, agent_b, agent_c):
        """Test that max agents limit is enforced."""
        service = CanvasCollaborationService(db)

        # Create session with max_agents=2 and first agent
        create_result = service.create_collaboration_session(
            canvas_id="canvas-123",
            session_id="session-limit",
            user_id=test_user.id,
            max_agents=2,
            initial_agent_id=agent_a.id
        )

        session_id = create_result["session_id"]

        # Add second agent
        service.add_agent_to_session(
            collaboration_session_id=session_id,
            agent_id=agent_b.id,
            user_id=test_user.id
        )

        # Try to add third agent (should fail)
        result = service.add_agent_to_session(
            collaboration_session_id=session_id,
            agent_id=agent_c.id,
            user_id=test_user.id
        )

        assert "error" in result
        assert "maximum" in result["error"].lower()

    def test_add_duplicate_agent(self, db, test_user, agent_a):
        """Test adding same agent twice fails."""
        service = CanvasCollaborationService(db)

        create_result = service.create_collaboration_session(
            canvas_id="canvas-123",
            session_id="session-456",
            user_id=test_user.id,
            initial_agent_id=agent_a.id
        )

        session_id = create_result["session_id"]

        # Try to add same agent again
        result = service.add_agent_to_session(
            collaboration_session_id=session_id,
            agent_id=agent_a.id,
            user_id=test_user.id
        )

        assert "error" in result
        assert "already" in result["error"].lower()

    def test_remove_agent_from_session(self, db, test_user, agent_a, agent_b):
        """Test removing agent from session."""
        service = CanvasCollaborationService(db)

        # Create session with two agents
        create_result = service.create_collaboration_session(
            canvas_id="canvas-123",
            session_id="session-456",
            user_id=test_user.id,
            initial_agent_id=agent_a.id
        )

        session_id = create_result["session_id"]

        service.add_agent_to_session(
            collaboration_session_id=session_id,
            agent_id=agent_b.id,
            user_id=test_user.id,
            role="contributor"
        )

        # Remove agent B
        result = service.remove_agent_from_session(
            collaboration_session_id=session_id,
            agent_id=agent_b.id
        )

        assert "error" not in result
        assert result["status"] == "removed"

        # Verify removal
        status = service.get_session_status(session_id)
        assert len(status["participants"]) == 1
        assert status["participants"][0]["agent_id"] == agent_a.id


# ============================================================================
# Permission Tests
# ============================================================================

class TestPermissions:
    """Test role-based permission checking."""

    def test_owner_full_permissions(self, db, test_user, agent_a):
        """Test owner role has full permissions."""
        service = CanvasCollaborationService(db)

        # Create session with agent as owner
        create_result = service.create_collaboration_session(
            canvas_id="canvas-123",
            session_id="session-456",
            user_id=test_user.id,
            initial_agent_id=agent_a.id
        )

        session_id = create_result["session_id"]

        # Check various permissions
        for action in ["read", "write", "delete", "lock"]:
            result = service.check_agent_permission(
                collaboration_session_id=session_id,
                agent_id=agent_a.id,
                action=action
            )

            assert result["allowed"] is True, f"Owner should be allowed to {action}"

    def test_contributor_limited_permissions(self, db, test_user, agent_a):
        """Test contributor role has limited permissions."""
        service = CanvasCollaborationService(db)

        # Create session with agent as contributor
        create_result = service.create_collaboration_session(
            canvas_id="canvas-123",
            session_id="session-456",
            user_id=test_user.id
        )

        session_id = create_result["session_id"]

        service.add_agent_to_session(
            collaboration_session_id=session_id,
            agent_id=agent_a.id,
            user_id=test_user.id,
            role="contributor"
        )

        # Check allowed permissions
        result = service.check_agent_permission(
            collaboration_session_id=session_id,
            agent_id=agent_a.id,
            action="read"
        )
        assert result["allowed"] is True

        result = service.check_agent_permission(
            collaboration_session_id=session_id,
            agent_id=agent_a.id,
            action="write"
        )
        assert result["allowed"] is True

        # Check disallowed permissions
        result = service.check_agent_permission(
            collaboration_session_id=session_id,
            agent_id=agent_a.id,
            action="delete"
        )
        assert result["allowed"] is False

        result = service.check_agent_permission(
            collaboration_session_id=session_id,
            agent_id=agent_a.id,
            action="lock"
        )
        assert result["allowed"] is False

    def test_viewer_read_only(self, db, test_user, agent_a):
        """Test viewer role only has read permissions."""
        service = CanvasCollaborationService(db)

        # Create session
        create_result = service.create_collaboration_session(
            canvas_id="canvas-123",
            session_id="session-456",
            user_id=test_user.id
        )

        session_id = create_result["session_id"]

        service.add_agent_to_session(
            collaboration_session_id=session_id,
            agent_id=agent_a.id,
            user_id=test_user.id,
            role="viewer"
        )

        # Check read permission
        result = service.check_agent_permission(
            collaboration_session_id=session_id,
            agent_id=agent_a.id,
            action="read"
        )
        assert result["allowed"] is True

        # Check write permission denied
        result = service.check_agent_permission(
            collaboration_session_id=session_id,
            agent_id=agent_a.id,
            action="write"
        )
        assert result["allowed"] is False

    def test_non_existent_agent(self, db, test_user):
        """Test permission check for non-existent agent."""
        service = CanvasCollaborationService(db)

        create_result = service.create_collaboration_session(
            canvas_id="canvas-123",
            session_id="session-456",
            user_id=test_user.id
        )

        session_id = create_result["session_id"]

        result = service.check_agent_permission(
            collaboration_session_id=session_id,
            agent_id="non-existent-agent",
            action="read"
        )

        assert result["allowed"] is False
        assert "not in this collaboration session" in result["reason"].lower()


# ============================================================================
# Conflict Resolution Tests
# ============================================================================

class TestConflictResolution:
    """Test conflict detection and resolution mechanisms."""

    def test_sequential_mode_no_conflict(self, db, test_user, agent_a, agent_b):
        """Test sequential mode has no conflicts when agents are idle."""
        service = CanvasCollaborationService(db)

        # Create sequential session
        create_result = service.create_collaboration_session(
            canvas_id="canvas-123",
            session_id="session-456",
            user_id=test_user.id,
            collaboration_mode="sequential",
            initial_agent_id=agent_a.id
        )

        session_id = create_result["session_id"]

        # Add second agent
        service.add_agent_to_session(
            collaboration_session_id=session_id,
            agent_id=agent_b.id,
            user_id=test_user.id
        )

        # Set agent_a's last activity to 10 seconds ago (outside 5-second window)
        from core.models import CanvasAgentParticipant
        agent_a_participant = db.query(CanvasAgentParticipant).filter(
            CanvasAgentParticipant.agent_id == agent_a.id
        ).first()
        agent_a_participant.last_activity_at = datetime.now() - timedelta(seconds=10)
        db.commit()

        # Check for conflicts (agent_a hasn't been active recently)
        result = service.check_for_conflicts(
            collaboration_session_id=session_id,
            agent_id=agent_b.id,
            component_id="chart-1",
            action={"type": "update", "data": {}}
        )

        assert result["has_conflict"] is False

    def test_parallel_mode_lock_mechanism(self, db, test_user, agent_a, agent_b):
        """Test parallel mode lock mechanism."""
        service = CanvasCollaborationService(db)

        # Create parallel session
        create_result = service.create_collaboration_session(
            canvas_id="canvas-123",
            session_id="session-456",
            user_id=test_user.id,
            collaboration_mode="parallel",
            initial_agent_id=agent_a.id
        )

        session_id = create_result["session_id"]

        # Add second agent
        service.add_agent_to_session(
            collaboration_session_id=session_id,
            agent_id=agent_b.id,
            user_id=test_user.id
        )

        # Agent A locks a component
        service.record_agent_action(
            collaboration_session_id=session_id,
            agent_id=agent_a.id,
            action="lock",
            component_id="chart-1"
        )

        # Agent B tries to access same component
        result = service.check_for_conflicts(
            collaboration_session_id=session_id,
            agent_id=agent_b.id,
            component_id="chart-1",
            action={"type": "update", "data": {...}}
        )

        assert result["has_conflict"] is True
        assert result["conflict_type"] == "locked"

    def test_resolve_conflict_first_come_first(self, db, test_user, agent_a, agent_b):
        """Test conflict resolution with first-come-first-served strategy."""
        service = CanvasCollaborationService(db)

        # Create session
        create_result = service.create_collaboration_session(
            canvas_id="canvas-123",
            session_id="session-456",
            user_id=test_user.id
        )

        session_id = create_result["session_id"]

        # Add both agents
        service.add_agent_to_session(
            collaboration_session_id=session_id,
            agent_id=agent_a.id,
            user_id=test_user.id
        )

        service.add_agent_to_session(
            collaboration_session_id=session_id,
            agent_id=agent_b.id,
            user_id=test_user.id
        )

        # Resolve conflict
        result = service.resolve_conflict(
            collaboration_session_id=session_id,
            agent_a_id=agent_a.id,
            agent_b_id=agent_b.id,
            component_id="chart-1",
            agent_a_action={"type": "update", "color": "blue"},
            agent_b_action={"type": "update", "color": "red"},
            resolution_strategy="first_come_first_served"
        )

        assert "error" not in result
        assert result["resolution"] == "agent_a_wins"
        assert result["resolved_action"]["color"] == "blue"

    def test_resolve_conflict_priority(self, db, test_user, agent_a, agent_b):
        """Test conflict resolution with priority-based strategy."""
        service = CanvasCollaborationService(db)

        # Create session
        create_result = service.create_collaboration_session(
            canvas_id="canvas-123",
            session_id="session-456",
            user_id=test_user.id
        )

        session_id = create_result["session_id"]

        # Add agent_b as owner (higher priority)
        service.add_agent_to_session(
            collaboration_session_id=session_id,
            agent_id=agent_b.id,
            user_id=test_user.id,
            role="owner"
        )

        # Add agent_a as contributor (lower priority)
        service.add_agent_to_session(
            collaboration_session_id=session_id,
            agent_id=agent_a.id,
            user_id=test_user.id,
            role="contributor"
        )

        # Resolve conflict with priority
        result = service.resolve_conflict(
            collaboration_session_id=session_id,
            agent_a_id=agent_a.id,
            agent_b_id=agent_b.id,
            component_id="chart-1",
            agent_a_action={"type": "update", "color": "blue"},
            agent_b_action={"type": "update", "color": "red"},
            resolution_strategy="priority"
        )

        assert "error" not in result
        # Agent B has higher role (owner vs contributor)
        assert result["resolution"] == "agent_b_wins"

    def test_locked_mode_conflict(self, db, test_user, agent_a, agent_b):
        """Test locked mode where first agent wins."""
        service = CanvasCollaborationService(db)

        # Create locked session
        create_result = service.create_collaboration_session(
            canvas_id="canvas-123",
            session_id="session-456",
            user_id=test_user.id,
            collaboration_mode="locked"
        )

        session_id = create_result["session_id"]

        # Add agent A and record action
        service.add_agent_to_session(
            collaboration_session_id=session_id,
            agent_id=agent_a.id,
            user_id=test_user.id
        )

        service.record_agent_action(
            collaboration_session_id=session_id,
            agent_id=agent_a.id,
            action="update",
            component_id="chart-1"
        )

        # Agent B tries to access same component
        result = service.check_for_conflicts(
            collaboration_session_id=session_id,
            agent_id=agent_b.id,
            component_id="chart-1",
            action={"type": "update", "data": {...}}
        )

        assert result["has_conflict"] is True
        assert result["conflict_type"] == "locked"


# ============================================================================
# Activity Tracking Tests
# ============================================================================

class TestActivityTracking:
    """Test agent activity tracking and lock management."""

    def test_record_agent_action(self, db, test_user, agent_a):
        """Test recording agent actions."""
        service = CanvasCollaborationService(db)

        # Create session
        create_result = service.create_collaboration_session(
            canvas_id="canvas-123",
            session_id="session-456",
            user_id=test_user.id,
            initial_agent_id=agent_a.id
        )

        session_id = create_result["session_id"]

        # Record actions
        result1 = service.record_agent_action(
            collaboration_session_id=session_id,
            agent_id=agent_a.id,
            action="update",
            component_id="chart-1"
        )

        result2 = service.record_agent_action(
            collaboration_session_id=session_id,
            agent_id=agent_a.id,
            action="update",
            component_id="markdown-1"
        )

        assert result1["actions_count"] == 1
        assert result2["actions_count"] == 2

        # Verify in session status
        status = service.get_session_status(session_id)
        participant = next(p for p in status["participants"] if p["agent_id"] == agent_a.id)
        assert participant["actions_count"] == 2

    def test_lock_management(self, db, test_user, agent_a, agent_b):
        """Test lock acquisition and release."""
        service = CanvasCollaborationService(db)

        # Create parallel session
        create_result = service.create_collaboration_session(
            canvas_id="canvas-123",
            session_id="session-456",
            user_id=test_user.id,
            collaboration_mode="parallel",
            initial_agent_id=agent_a.id
        )

        session_id = create_result["session_id"]

        # Add second agent
        service.add_agent_to_session(
            collaboration_session_id=session_id,
            agent_id=agent_b.id,
            user_id=test_user.id
        )

        # Agent A acquires locks
        service.record_agent_action(
            collaboration_session_id=session_id,
            agent_id=agent_a.id,
            action="lock",
            component_id="chart-1"
        )

        service.record_agent_action(
            collaboration_session_id=session_id,
            agent_id=agent_a.id,
            action="lock",
            component_id="chart-2"
        )

        # Verify locks
        status = service.get_session_status(session_id)
        agent_a_participant = next(p for p in status["participants"] if p["agent_id"] == agent_a.id)
        assert "chart-1" in agent_a_participant["held_locks"]
        assert "chart-2" in agent_a_participant["held_locks"]

        # Release one lock
        result = service.release_agent_lock(
            collaboration_session_id=session_id,
            agent_id=agent_a.id,
            component_id="chart-1"
        )

        assert result["status"] == "released"

        # Verify lock was released
        status = service.get_session_status(session_id)
        agent_a_participant = next(p for p in status["participants"] if p["agent_id"] == agent_a.id)
        assert "chart-1" not in agent_a_participant["held_locks"]
        assert "chart-2" in agent_a_participant["held_locks"]


# ============================================================================
# Integration Tests
# ============================================================================

class TestMultiAgentCanvasIntegration:
    """Integration tests for complete multi-agent workflows."""

    def test_sequential_collaboration_workflow(self, db, test_user, agent_a, agent_b, agent_c):
        """Test sequential collaboration where agents take turns."""
        service = CanvasCollaborationService(db)

        # Create session
        create_result = service.create_collaboration_session(
            canvas_id="canvas-sequential",
            session_id="session-sequential",
            user_id=test_user.id,
            collaboration_mode="sequential",
            max_agents=3
        )

        session_id = create_result["session_id"]

        # Add all agents
        service.add_agent_to_session(
            collaboration_session_id=session_id,
            agent_id=agent_a.id,
            user_id=test_user.id,
            role="owner"
        )

        service.add_agent_to_session(
            collaboration_session_id=session_id,
            agent_id=agent_b.id,
            user_id=test_user.id,
            role="contributor"
        )

        service.add_agent_to_session(
            collaboration_session_id=session_id,
            agent_id=agent_c.id,
            user_id=test_user.id,
            role="contributor"
        )

        # Agent A adds chart
        service.record_agent_action(
            collaboration_session_id=session_id,
            agent_id=agent_a.id,
            action="add",
            component_id="chart-sales"
        )

        # Agent B adds markdown (no conflict because sequential)
        import time
        time.sleep(0.1)  # Ensure timestamp difference

        service.record_agent_action(
            collaboration_session_id=session_id,
            agent_id=agent_b.id,
            action="add",
            component_id="markdown-intro"
        )

        # Agent C adds form
        time.sleep(0.1)

        service.record_agent_action(
            collaboration_session_id=session_id,
            agent_id=agent_c.id,
            action="add",
            component_id="form-feedback"
        )

        # Complete and verify
        final_result = service.complete_session(session_id)

        assert final_result["total_participants"] == 3
        assert final_result["total_actions"] == 3
        assert final_result["status"] == "completed"

    def test_parallel_collaboration_with_conflicts(self, db, test_user, agent_a, agent_b):
        """Test parallel collaboration with conflict resolution."""
        service = CanvasCollaborationService(db)

        # Create parallel session
        create_result = service.create_collaboration_session(
            canvas_id="canvas-parallel",
            session_id="session-parallel",
            user_id=test_user.id,
            collaboration_mode="parallel"
        )

        session_id = create_result["session_id"]

        # Add agents
        service.add_agent_to_session(
            collaboration_session_id=session_id,
            agent_id=agent_a.id,
            user_id=test_user.id,
            role="owner"
        )

        service.add_agent_to_session(
            collaboration_session_id=session_id,
            agent_id=agent_b.id,
            user_id=test_user.id,
            role="contributor"
        )

        # Both agents try to update same component
        service.record_agent_action(
            collaboration_session_id=session_id,
            agent_id=agent_a.id,
            action="lock",
            component_id="chart-main"
        )

        # Agent B tries to access locked component
        conflict_result = service.check_for_conflicts(
            collaboration_session_id=session_id,
            agent_id=agent_b.id,
            component_id="chart-main",
            action={"type": "update", "data": {"title": "New Title"}}
        )

        assert conflict_result["has_conflict"] is True

        # Resolve conflict (agent A wins due to lock)
        resolve_result = service.resolve_conflict(
            collaboration_session_id=session_id,
            agent_a_id=agent_a.id,
            agent_b_id=agent_b.id,
            component_id="chart-main",
            agent_a_action={"type": "update", "data": {"title": "Agent A's Title"}},
            agent_b_action={"type": "update", "data": {"title": "Agent B's Title"}},
            resolution_strategy="first_come_first_served"
        )

        assert resolve_result["resolution"] == "agent_a_wins"

        # Agent A releases lock
        service.release_agent_lock(
            collaboration_session_id=session_id,
            agent_id=agent_a.id,
            component_id="chart-main"
        )

        # Now agent B can access
        conflict_result2 = service.check_for_conflicts(
            collaboration_session_id=session_id,
            agent_id=agent_b.id,
            component_id="chart-main",
            action={"type": "update", "data": {"title": "Now Agent B can update"}}
        )

        assert conflict_result2["has_conflict"] is False

        # Complete session
        result = service.complete_session(session_id)
        assert result["total_conflicts"] >= 1

    def test_role_based_workflow(self, db, test_user, agent_a, agent_b, agent_c):
        """Test workflow where agents have different roles."""
        service = CanvasCollaborationService(db)

        # Create session
        create_result = service.create_collaboration_session(
            canvas_id="canvas-roles",
            session_id="session-roles",
            user_id=test_user.id
        )

        session_id = create_result["session_id"]

        # Owner agent with full permissions
        service.add_agent_to_session(
            collaboration_session_id=session_id,
            agent_id=agent_a.id,
            user_id=test_user.id,
            role="owner"
        )

        # Contributor agent who can add/edit
        service.add_agent_to_session(
            collaboration_session_id=session_id,
            agent_id=agent_b.id,
            user_id=test_user.id,
            role="contributor"
        )

        # Reviewer who can only read and suggest
        service.add_agent_to_session(
            collaboration_session_id=session_id,
            agent_id=agent_c.id,
            user_id=test_user.id,
            role="reviewer"
        )

        # Owner adds components
        for action in ["add", "add", "add"]:
            service.record_agent_action(
                collaboration_session_id=session_id,
                agent_id=agent_a.id,
                action=action,
                component_id=f"component-{action}"
            )

        # Contributor edits components
        for component_id in ["component-1", "component-2", "component-3"]:
            check = service.check_agent_permission(
                collaboration_session_id=session_id,
                agent_id=agent_b.id,
                action="write",
                component_id=component_id
            )
            assert check["allowed"] is True

            service.record_agent_action(
                collaboration_session_id=session_id,
                agent_id=agent_b.id,
                action="edit",
                component_id=component_id
            )

        # Reviewer can only read
        check = service.check_agent_permission(
            collaboration_session_id=session_id,
            agent_id=agent_c.id,
            action="read"
        )
        assert check["allowed"] is True

        check = service.check_agent_permission(
            collaboration_session_id=session_id,
            agent_id=agent_c.id,
            action="write"
        )
        assert check["allowed"] is False

        # Complete
        result = service.complete_session(session_id)
        assert result["status"] == "completed"
        assert result["total_actions"] == 6  # 3 from owner, 3 from contributor
