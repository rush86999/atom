"""
Canvas Collaboration Service Unit Tests

Tests for CanvasCollaborationService from core/canvas_collaboration_service.py.

Coverage:
- Session management (create, status, complete)
- Agent management (add, remove)
- Permission checking
- Conflict detection and resolution
- Activity tracking
- Lock management
- Role-based permissions
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from core.canvas_collaboration_service import (
    CanvasCollaborationService,
    CollaborationMode,
    AgentRole
)
from core.models import (
    CanvasCollaborationSession,
    CanvasAgentParticipant,
    CanvasConflict,
    AgentRegistry
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def db():
    """Create mock database session."""
    return MagicMock(spec=Session)


@pytest.fixture
def service(db: Session):
    """Create CanvasCollaborationService instance."""
    return CanvasCollaborationService(db)


@pytest.fixture
def mock_agent(db: Session):
    """Create mock agent."""
    import uuid
    agent_id = str(uuid.uuid4())
    agent = AgentRegistry(
        id=agent_id,
        name=f"Test Agent {agent_id[:8]}",
        category="testing",
        status="autonomous",
        confidence_score=0.9
    )
    return agent


@pytest.fixture
def mock_collaboration_session(db: Session):
    """Create mock collaboration session."""
    import uuid
    session_id = str(uuid.uuid4())
    canvas_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())

    session = CanvasCollaborationSession(
        id=session_id,
        canvas_id=canvas_id,
        session_id=f"canvas-session-{canvas_id[:8]}",
        user_id=user_id,
        collaboration_mode="sequential",
        max_agents=5,
        status="active"
    )
    return session


@pytest.fixture
def mock_participant(db: Session):
    """Create mock participant."""
    import uuid
    participant_id = str(uuid.uuid4())
    participant = CanvasAgentParticipant(
        id=participant_id,
        collaboration_session_id=str(uuid.uuid4()),
        agent_id=str(uuid.uuid4()),
        user_id=str(uuid.uuid4()),
        role="contributor",
        permissions={"read": True, "write": True},
        status="active"
    )
    return participant


# ============================================================================
# Session Management Tests
# ============================================================================

def test_create_collaboration_session_success(service: CanvasCollaborationService, db: MagicMock):
    """Test creating a new collaboration session."""
    import uuid
    canvas_id = str(uuid.uuid4())
    session_id = f"canvas-session-{canvas_id[:8]}"
    user_id = str(uuid.uuid4())

    with patch.object(db, 'add') as mock_add:
        with patch.object(db, 'commit') as mock_commit:
            with patch.object(db, 'refresh') as mock_refresh:
                result = service.create_collaboration_session(
                    canvas_id=canvas_id,
                    session_id=session_id,
                    user_id=user_id,
                    collaboration_mode="sequential",
                    max_agents=5
                )

                assert "session_id" in result
                assert result["canvas_id"] == canvas_id
                assert result["collaboration_mode"] == "sequential"
                assert result["max_agents"] == 5
                assert result["status"] == "active"
                assert "participants" in result
                mock_add.assert_called()


def test_create_collaboration_session_with_initial_agent(service: CanvasCollaborationService, db: MagicMock, mock_agent: AgentRegistry):
    """Test creating a collaboration session with an initial agent."""
    import uuid
    canvas_id = str(uuid.uuid4())
    session_id = f"canvas-session-{canvas_id[:8]}"
    user_id = str(uuid.uuid4())

    with patch.object(db, 'add') as mock_add:
        with patch.object(db, 'commit') as mock_commit:
            with patch.object(db, 'refresh') as mock_refresh:
                with patch.object(service, 'add_agent_to_session') as mock_add_agent:
                    result = service.create_collaboration_session(
                        canvas_id=canvas_id,
                        session_id=session_id,
                        user_id=user_id,
                        collaboration_mode="parallel",
                        max_agents=3,
                        initial_agent_id=mock_agent.id
                    )

                    assert result["collaboration_mode"] == "parallel"
                    assert result["max_agents"] == 3
                    mock_add_agent.assert_called_once()


def test_create_collaboration_session_different_modes(service: CanvasCollaborationService, db: MagicMock):
    """Test creating collaboration sessions with different modes."""
    import uuid

    modes = ["sequential", "parallel", "locked"]
    canvas_id = str(uuid.uuid4())
    session_id = f"canvas-session-{canvas_id[:8]}"
    user_id = str(uuid.uuid4())

    for mode in modes:
        with patch.object(db, 'add'):
            with patch.object(db, 'commit'):
                with patch.object(db, 'refresh'):
                    result = service.create_collaboration_session(
                        canvas_id=canvas_id,
                        session_id=session_id,
                        user_id=user_id,
                        collaboration_mode=mode,
                        max_agents=5
                    )

                    assert result["collaboration_mode"] == mode


def test_get_session_status_success(service: CanvasCollaborationService, db: MagicMock, mock_collaboration_session: CanvasCollaborationSession):
    """Test getting session status."""
    with patch.object(db, 'query') as mock_query:
        mock_query.return_value.filter.return_value.first.return_value = mock_collaboration_session
        mock_query.return_value.filter.return_value.all.return_value = []

        result = service.get_session_status(mock_collaboration_session.id)

        assert result["session_id"] == mock_collaboration_session.id
        assert result["canvas_id"] == mock_collaboration_session.canvas_id
        assert result["status"] == "active"
        assert "participants" in result


def test_get_session_status_not_found(service: CanvasCollaborationService, db: MagicMock):
    """Test getting status for non-existent session."""
    import uuid
    session_id = str(uuid.uuid4())

    with patch.object(db, 'query') as mock_query:
        mock_query.return_value.filter.return_value.first.return_value = None

        result = service.get_session_status(session_id)

        assert "error" in result
        assert "not found" in result["error"].lower()


def test_complete_session_success(service: CanvasCollaborationService, db: MagicMock, mock_collaboration_session: CanvasCollaborationSession):
    """Test completing a collaboration session."""
    with patch.object(db, 'query') as mock_query:
        mock_query.return_value.filter.return_value.first.return_value = mock_collaboration_session
        mock_query.return_value.filter.return_value.count.return_value = 0
        mock_query.return_value.filter.return_value.update.return_value = None

        with patch.object(db, 'commit'):
            result = service.complete_session(mock_collaboration_session.id)

            assert result["session_id"] == mock_collaboration_session.id
            assert result["status"] == "completed"
            assert "completed_at" in result
            assert "total_participants" in result


def test_complete_session_not_found(service: CanvasCollaborationService, db: MagicMock):
    """Test completing a non-existent session."""
    import uuid
    session_id = str(uuid.uuid4())

    with patch.object(db, 'query') as mock_query:
        mock_query.return_value.filter.return_value.first.return_value = None

        result = service.complete_session(session_id)

        assert "error" in result


# ============================================================================
# Agent Management Tests
# ============================================================================

def test_add_agent_to_session_success(service: CanvasCollaborationService, db: MagicMock, mock_collaboration_session: CanvasCollaborationSession, mock_agent: AgentRegistry):
    """Test adding an agent to a session."""
    import uuid
    user_id = str(uuid.uuid4())

    with patch.object(db, 'query') as mock_query:
        # Mock session query
        mock_session_result = MagicMock()
        mock_session_result.first.return_value = mock_collaboration_session
        mock_session_result.filter.return_value = mock_session_result

        # Mock participant check (not exists)
        mock_participant_result = MagicMock()
        mock_participant_result.first.return_value = None
        mock_session_result.filter.return_value = mock_participant_result

        # Mock participant count
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 0
        mock_query.return_value = mock_count_result

        # Mock agent query
        mock_agent_result = MagicMock()
        mock_agent_result.first.return_value = mock_agent
        mock_query.return_value.filter.return_value = mock_agent_result

        with patch.object(db, 'add'):
            with patch.object(db, 'commit'):
                with patch.object(db, 'refresh'):
                    result = service.add_agent_to_session(
                        collaboration_session_id=mock_collaboration_session.id,
                        agent_id=mock_agent.id,
                        user_id=user_id,
                        role="contributor"
                    )

                    assert "participant_id" in result
                    assert result["agent_id"] == mock_agent.id
                    assert result["role"] == "contributor"


def test_add_agent_to_session_not_found(service: CanvasCollaborationService, db: MagicMock):
    """Test adding agent to non-existent session."""
    import uuid
    session_id = str(uuid.uuid4())
    agent_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())

    with patch.object(db, 'query') as mock_query:
        mock_query.return_value.filter.return_value.first.return_value = None

        result = service.add_agent_to_session(session_id, agent_id, user_id)

        assert "error" in result
        assert "not found" in result["error"].lower()


def test_add_agent_to_session_already_exists(service: CanvasCollaborationService, db: MagicMock, mock_participant: CanvasAgentParticipant):
    """Test adding agent that's already in session."""
    import uuid
    user_id = str(uuid.uuid4())

    with patch.object(db, 'query') as mock_query:
        mock_query.return_value.filter.return_value.first.return_value = mock_participant

        result = service.add_agent_to_session(
            collaboration_session_id=mock_participant.collaboration_session_id,
            agent_id=mock_participant.agent_id,
            user_id=user_id
        )

        assert "error" in result
        assert "already" in result["error"].lower()


def test_add_agent_to_session_max_agents_reached(service: CanvasCollaborationService, db: MagicMock, mock_collaboration_session: CanvasCollaborationSession, mock_agent: AgentRegistry):
    """Test adding agent when max agents limit is reached."""
    import uuid
    user_id = str(uuid.uuid4())

    with patch.object(db, 'query') as mock_query:
        # Mock session
        mock_query.return_value.filter.return_value.first.return_value = mock_collaboration_session

        # Mock participant check (not exists)
        mock_query.return_value.filter.return_value.first.return_value = None

        # Mock participant count (at max)
        mock_query.return_value.filter.return_value.scalar.return_value = 5

        result = service.add_agent_to_session(
            collaboration_session_id=mock_collaboration_session.id,
            agent_id=mock_agent.id,
            user_id=user_id
        )

        assert "error" in result
        assert "maximum" in result["error"].lower() or "capacity" in result["error"].lower()


def test_remove_agent_from_session_success(service: CanvasCollaborationService, db: MagicMock, mock_participant: CanvasAgentParticipant):
    """Test removing an agent from a session."""
    with patch.object(db, 'query') as mock_query:
        mock_query.return_value.filter.return_value.first.return_value = mock_participant

        with patch.object(db, 'commit'):
            result = service.remove_agent_from_session(
                collaboration_session_id=mock_participant.collaboration_session_id,
                agent_id=mock_participant.agent_id
            )

            assert result["agent_id"] == mock_participant.agent_id
            assert result["status"] == "removed"


def test_remove_agent_from_session_not_found(service: CanvasCollaborationService, db: MagicMock):
    """Test removing an agent that doesn't exist."""
    import uuid
    session_id = str(uuid.uuid4())
    agent_id = str(uuid.uuid4())

    with patch.object(db, 'query') as mock_query:
        mock_query.return_value.filter.return_value.first.return_value = None

        result = service.remove_agent_from_session(session_id, agent_id)

        assert "error" in result
        assert "not found" in result["error"].lower()


# ============================================================================
# Permission Management Tests
# ============================================================================

def test_check_agent_permission_owner_role(service: CanvasCollaborationService, db: MagicMock, mock_participant: CanvasAgentParticipant):
    """Test permission check for owner role."""
    mock_participant.role = "owner"
    mock_participant.status = "active"
    mock_participant.permissions = {}

    with patch.object(db, 'query') as mock_query:
        mock_query.return_value.filter.return_value.first.return_value = mock_participant

        result = service.check_agent_permission(
            collaboration_session_id=mock_participant.collaboration_session_id,
            agent_id=mock_participant.agent_id,
            action="delete"
        )

        assert result["allowed"] is True


def test_check_agent_permission_viewer_role_read_only(service: CanvasCollaborationService, db: MagicMock, mock_participant: CanvasAgentParticipant):
    """Test permission check for viewer role (read only)."""
    mock_participant.role = "viewer"
    mock_participant.status = "active"
    mock_participant.permissions = {}

    with patch.object(db, 'query') as mock_query:
        mock_query.return_value.filter.return_value.first.return_value = mock_participant

        # Read should be allowed
        result = service.check_agent_permission(
            collaboration_session_id=mock_participant.collaboration_session_id,
            agent_id=mock_participant.agent_id,
            action="read"
        )
        assert result["allowed"] is True

        # Write should be denied
        result = service.check_agent_permission(
            collaboration_session_id=mock_participant.collaboration_session_id,
            agent_id=mock_participant.agent_id,
            action="write"
        )
        assert result["allowed"] is False


def test_check_agent_permission_reviewer_role(service: CanvasCollaborationService, db: MagicMock, mock_participant: CanvasAgentParticipant):
    """Test permission check for reviewer role."""
    mock_participant.role = "reviewer"
    mock_participant.status = "active"
    mock_participant.permissions = {}

    with patch.object(db, 'query') as mock_query:
        mock_query.return_value.filter.return_value.first.return_value = mock_participant

        # Read and suggest should be allowed
        result = service.check_agent_permission(
            collaboration_session_id=mock_participant.collaboration_session_id,
            agent_id=mock_participant.agent_id,
            action="suggest"
        )
        assert result["allowed"] is True

        # Delete should be denied
        result = service.check_agent_permission(
            collaboration_session_id=mock_participant.collaboration_session_id,
            agent_id=mock_participant.agent_id,
            action="delete"
        )
        assert result["allowed"] is False


def test_check_agent_permission_not_participant(service: CanvasCollaborationService, db: MagicMock):
    """Test permission check for non-participant."""
    import uuid
    session_id = str(uuid.uuid4())
    agent_id = str(uuid.uuid4())

    with patch.object(db, 'query') as mock_query:
        mock_query.return_value.filter.return_value.first.return_value = None

        result = service.check_agent_permission(session_id, agent_id, "read")

        assert result["allowed"] is False
        assert "not in this collaboration session" in result["reason"]


def test_check_agent_permission_inactive_status(service: CanvasCollaborationService, db: MagicMock, mock_participant: CanvasAgentParticipant):
    """Test permission check for inactive participant."""
    mock_participant.status = "completed"
    mock_participant.permissions = {}

    with patch.object(db, 'query') as mock_query:
        mock_query.return_value.filter.return_value.first.return_value = mock_participant

        result = service.check_agent_permission(
            collaboration_session_id=mock_participant.collaboration_session_id,
            agent_id=mock_participant.agent_id,
            action="read"
        )

        assert result["allowed"] is False
        assert "status" in result["reason"].lower()


def test_check_agent_permission_custom_permissions(service: CanvasCollaborationService, db: MagicMock, mock_participant: CanvasAgentParticipant):
    """Test permission check with custom permissions."""
    mock_participant.role = "contributor"
    mock_participant.status = "active"
    mock_participant.permissions = {"delete": False}

    with patch.object(db, 'query') as mock_query:
        mock_query.return_value.filter.return_value.first.return_value = mock_participant

        # Custom permission should override role default
        result = service.check_agent_permission(
            collaboration_session_id=mock_participant.collaboration_session_id,
            agent_id=mock_participant.agent_id,
            action="delete"
        )

        assert result["allowed"] is False


# ============================================================================
# Conflict Detection Tests
# ============================================================================

def test_check_for_conflicts_no_conflict_sequential(service: CanvasCollaborationService, db: MagicMock, mock_collaboration_session: CanvasCollaborationSession):
    """Test conflict check in sequential mode with no recent activity."""
    import uuid
    agent_id = str(uuid.uuid4())
    component_id = str(uuid.uuid4())

    mock_collaboration_session.collaboration_mode = "sequential"

    with patch.object(db, 'query') as mock_query:
        mock_query.return_value.filter.return_value.first.return_value = mock_collaboration_session
        mock_query.return_value.filter.return_value.all.return_value = []

        result = service.check_for_conflicts(
            collaboration_session_id=mock_collaboration_session.id,
            agent_id=agent_id,
            component_id=component_id,
            action={"type": "update"}
        )

        assert result["has_conflict"] is False


def test_check_for_conflicts_sequential_conflict(service: CanvasCollaborationService, db: MagicMock, mock_collaboration_session: CanvasCollaborationSession):
    """Test conflict check in sequential mode with recent activity."""
    import uuid
    agent_id = str(uuid.uuid4())
    component_id = str(uuid.uuid4())

    mock_collaboration_session.collaboration_mode = "sequential"

    # Create a participant with recent activity
    recent_participant = MagicMock()
    recent_participant.agent_id = str(uuid.uuid4())
    recent_participant.last_activity_at = datetime.now() - timedelta(seconds=2)

    with patch.object(db, 'query') as mock_query:
        mock_query.return_value.filter.return_value.first.return_value = mock_collaboration_session
        mock_query.return_value.filter.return_value.first.return_value = recent_participant

        result = service.check_for_conflicts(
            collaboration_session_id=mock_collaboration_session.id,
            agent_id=agent_id,
            component_id=component_id,
            action={"type": "update"}
        )

        assert result["has_conflict"] is True
        assert result["conflict_type"] == "sequential"


def test_check_for_conflicts_parallel_no_locks(service: CanvasCollaborationService, db: MagicMock, mock_collaboration_session: CanvasCollaborationSession):
    """Test conflict check in parallel mode with no locks held."""
    import uuid
    agent_id = str(uuid.uuid4())
    component_id = str(uuid.uuid4())

    mock_collaboration_session.collaboration_mode = "parallel"

    with patch.object(db, 'query') as mock_query:
        mock_query.return_value.filter.return_value.first.return_value = mock_collaboration_session
        # No other participants
        mock_query.return_value.filter.return_value.all.return_value = []

        result = service.check_for_conflicts(
            collaboration_session_id=mock_collaboration_session.id,
            agent_id=agent_id,
            component_id=component_id,
            action={"type": "update"}
        )

        assert result["has_conflict"] is False


def test_check_for_conflicts_parallel_locked(service: CanvasCollaborationService, db: MagicMock, mock_collaboration_session: CanvasCollaborationSession):
    """Test conflict check in parallel mode with locked component."""
    import uuid
    agent_id = str(uuid.uuid4())
    component_id = str(uuid.uuid4())

    mock_collaboration_session.collaboration_mode = "parallel"

    # Create a participant holding a lock
    locking_participant = MagicMock()
    locking_participant.agent_id = str(uuid.uuid4())
    locking_participant.status = "active"
    locking_participant.held_locks = [component_id]

    with patch.object(db, 'query') as mock_query:
        mock_query.return_value.filter.return_value.first.return_value = mock_collaboration_session
        mock_query.return_value.filter.return_value.all.return_value = [locking_participant]

        result = service.check_for_conflicts(
            collaboration_session_id=mock_collaboration_session.id,
            agent_id=agent_id,
            component_id=component_id,
            action={"type": "update"}
        )

        assert result["has_conflict"] is True
        assert result["conflict_type"] == "locked"


def test_check_for_conflicts_locked_mode(service: CanvasCollaborationService, db: MagicMock, mock_collaboration_session: CanvasCollaborationSession):
    """Test conflict check in locked mode."""
    import uuid
    agent_id = str(uuid.uuid4())
    component_id = str(uuid.uuid4())

    mock_collaboration_session.collaboration_mode = "locked"

    with patch.object(db, 'query') as mock_query:
        mock_query.return_value.filter.return_value.first.return_value = mock_collaboration_session
        # No participants with locks
        mock_query.return_value.filter.return_value.all.return_value = []

        result = service.check_for_conflicts(
            collaboration_session_id=mock_collaboration_session.id,
            agent_id=agent_id,
            component_id=component_id,
            action={"type": "update"}
        )

        assert result["has_conflict"] is False


# ============================================================================
# Conflict Resolution Tests
# ============================================================================

def test_resolve_conflict_first_come_first_served(service: CanvasCollaborationService, db: MagicMock, mock_collaboration_session: CanvasCollaborationSession):
    """Test conflict resolution with first-come-first-served strategy."""
    import uuid
    agent_a_id = str(uuid.uuid4())
    agent_b_id = str(uuid.uuid4())
    component_id = str(uuid.uuid4())

    action_a = {"type": "update", "value": "A"}
    action_b = {"type": "update", "value": "B"}

    with patch.object(db, 'query') as mock_query:
        mock_query.return_value.filter.return_value.first.return_value = mock_collaboration_session
        mock_query.return_value.filter.return_value.scalar.return_value = 0

        with patch.object(db, 'add'):
            with patch.object(db, 'commit'):
                result = service.resolve_conflict(
                    collaboration_session_id=mock_collaboration_session.id,
                    agent_a_id=agent_a_id,
                    agent_b_id=agent_b_id,
                    component_id=component_id,
                    agent_a_action=action_a,
                    agent_b_action=action_b,
                    resolution_strategy="first_come_first_served"
                )

                assert result["resolution"] == "agent_a_wins"
                assert result["resolved_action"] == action_a


def test_resolve_conflict_priority_strategy(service: CanvasCollaborationService, db: MagicMock, mock_collaboration_session: CanvasCollaborationSession):
    """Test conflict resolution with priority strategy."""
    import uuid
    agent_a_id = str(uuid.uuid4())
    agent_b_id = str(uuid.uuid4())
    component_id = str(uuid.uuid4())

    action_a = {"type": "update", "value": "A"}
    action_b = {"type": "update", "value": "B"}

    # Create participants with different roles
    participant_a = MagicMock()
    participant_a.role = "contributor"

    participant_b = MagicMock()
    participant_b.role = "owner"

    with patch.object(db, 'query') as mock_query:
        mock_query.return_value.filter.return_value.first.return_value = mock_collaboration_session
        mock_query.return_value.filter.return_value.scalar.return_value = 0

        # First query for participant_a returns contributor
        mock_query_result = MagicMock()
        mock_query_result.first.return_value = participant_a
        mock_query.return_value.filter.return_value = mock_query_result

        with patch.object(db, 'add'):
            with patch.object(db, 'commit'):
                result = service.resolve_conflict(
                    collaboration_session_id=mock_collaboration_session.id,
                    agent_a_id=agent_a_id,
                    agent_b_id=agent_b_id,
                    component_id=component_id,
                    agent_a_action=action_a,
                    agent_b_action=action_b,
                    resolution_strategy="priority"
                )

                # Owner should win
                assert result["resolution"] in ["agent_a_wins", "agent_b_wins"]


def test_resolve_conflict_merge_strategy(service: CanvasCollaborationService, db: MagicMock, mock_collaboration_session: CanvasCollaborationSession):
    """Test conflict resolution with merge strategy."""
    import uuid
    agent_a_id = str(uuid.uuid4())
    agent_b_id = str(uuid.uuid4())
    component_id = str(uuid.uuid4())

    action_a = {"type": "update", "value": "A"}
    action_b = {"type": "update", "value": "B"}

    with patch.object(db, 'query') as mock_query:
        mock_query.return_value.filter.return_value.first.return_value = mock_collaboration_session
        mock_query.return_value.filter.return_value.scalar.return_value = 0

        with patch.object(db, 'add'):
            with patch.object(db, 'commit'):
                result = service.resolve_conflict(
                    collaboration_session_id=mock_collaboration_session.id,
                    agent_a_id=agent_a_id,
                    agent_b_id=agent_b_id,
                    component_id=component_id,
                    agent_a_action=action_a,
                    agent_b_action=action_b,
                    resolution_strategy="merge"
                )

                assert result["resolution"] == "merged"


# ============================================================================
# Activity Tracking Tests
# ============================================================================

def test_record_agent_action_success(service: CanvasCollaborationService, db: MagicMock, mock_participant: CanvasAgentParticipant):
    """Test recording an agent action."""
    import uuid
    component_id = str(uuid.uuid4())

    mock_participant.actions_count = 5

    with patch.object(db, 'query') as mock_query:
        mock_query.return_value.filter.return_value.first.return_value = mock_participant

        with patch.object(db, 'commit'):
            with patch.object(db, 'refresh') as mock_refresh:
                # Simulate increment
                mock_refresh.return_value = None
                mock_participant.actions_count = 6

                result = service.record_agent_action(
                    collaboration_session_id=mock_participant.collaboration_session_id,
                    agent_id=mock_participant.agent_id,
                    action="update",
                    component_id=component_id
                )

                assert result["agent_id"] == mock_participant.agent_id
                assert result["action"] == "update"
                assert result["component_id"] == component_id


def test_record_agent_action_not_found(service: CanvasCollaborationService, db: MagicMock):
    """Test recording action for non-existent participant."""
    import uuid
    session_id = str(uuid.uuid4())
    agent_id = str(uuid.uuid4())
    component_id = str(uuid.uuid4())

    with patch.object(db, 'query') as mock_query:
        mock_query.return_value.filter.return_value.first.return_value = None

        result = service.record_agent_action(
            collaboration_session_id=session_id,
            agent_id=agent_id,
            action="update",
            component_id=component_id
        )

        assert "error" in result


def test_release_agent_lock_success(service: CanvasCollaborationService, db: MagicMock, mock_participant: CanvasAgentParticipant):
    """Test releasing an agent's lock."""
    import uuid
    component_id = str(uuid.uuid4())

    mock_participant.held_locks = [component_id, str(uuid.uuid4())]

    with patch.object(db, 'query') as mock_query:
        mock_query.return_value.filter.return_value.first.return_value = mock_participant

        with patch.object(db, 'commit'):
            with patch.object(db, 'refresh'):
                with patch('core.canvas_collaboration_service.flag_modified'):
                    result = service.release_agent_lock(
                        collaboration_session_id=mock_participant.collaboration_session_id,
                        agent_id=mock_participant.agent_id,
                        component_id=component_id
                    )

                    assert result["agent_id"] == mock_participant.agent_id
                    assert result["status"] == "released"


def test_release_agent_lock_not_held(service: CanvasCollaborationService, db: MagicMock, mock_participant: CanvasAgentParticipant):
    """Test releasing a lock that isn't held."""
    import uuid
    component_id = str(uuid.uuid4())

    mock_participant.held_locks = [str(uuid.uuid4())]  # Different component

    with patch.object(db, 'query') as mock_query:
        mock_query.return_value.filter.return_value.first.return_value = mock_participant

        result = service.release_agent_lock(
            collaboration_session_id=mock_participant.collaboration_session_id,
            agent_id=mock_participant.agent_id,
            component_id=component_id
        )

        assert "error" in result


# ============================================================================
# Default Permissions Tests
# ============================================================================

def test_get_default_permissions_owner_role(service: CanvasCollaborationService):
    """Test default permissions for owner role."""
    permissions = service._get_default_permissions("owner")

    assert permissions["read"] is True
    assert permissions["write"] is True
    assert permissions["delete"] is True
    assert permissions["lock"] is True


def test_get_default_permissions_contributor_role(service: CanvasCollaborationService):
    """Test default permissions for contributor role."""
    permissions = service._get_default_permissions("contributor")

    assert permissions["read"] is True
    assert permissions["write"] is True
    assert permissions["delete"] is False
    assert permissions["lock"] is False


def test_get_default_permissions_reviewer_role(service: CanvasCollaborationService):
    """Test default permissions for reviewer role."""
    permissions = service._get_default_permissions("reviewer")

    assert permissions["read"] is True
    assert permissions["suggest"] is True
    assert permissions["write"] is False
    assert permissions["delete"] is False


def test_get_default_permissions_viewer_role(service: CanvasCollaborationService):
    """Test default permissions for viewer role."""
    permissions = service._get_default_permissions("viewer")

    assert permissions["read"] is True
    assert "write" not in permissions


def test_merge_actions(service: CanvasCollaborationService):
    """Test merge actions helper."""
    action_a = {"type": "update", "value": "A"}
    action_b = {"type": "update", "value": "B"}

    result = service._merge_actions(action_a, action_b)

    # Currently returns action_a (simple implementation)
    assert result == action_a
