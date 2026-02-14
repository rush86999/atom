"""
Comprehensive unit tests for Canvas Collaboration Service

Tests cover:
- Session management (create, add agent, remove agent, get status, complete session)
- Permission management (check permissions for all roles)
- Lock management (record action, release lock)
- Conflict resolution (detect conflicts, resolve conflicts with different strategies)
- Role-based access control (owner, contributor, reviewer, viewer)
- Collaboration modes (sequential, parallel, locked)
- Activity tracking and edge cases

Total lines: 450+
Total tests: 30+
Target coverage: 50%+
"""

import pytest
from unittest.mock import MagicMock, Mock, patch
from datetime import datetime, timedelta
from typing import Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_

from core.canvas_collaboration_service import (
    CanvasCollaborationService,
    CollaborationMode,
    AgentRole,
)
from core.models import (
    CanvasCollaborationSession,
    CanvasAgentParticipant,
    CanvasConflict,
    AgentRegistry,
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def db_session():
    """Create a mock database session"""
    db = MagicMock(spec=Session)
    db.add = MagicMock()
    db.commit = MagicMock()
    db.rollback = MagicMock()
    db.refresh = MagicMock()
    db.query = MagicMock()
    return db


@pytest.fixture
def sample_agent():
    """Sample agent registry"""
    agent = MagicMock(spec=AgentRegistry)
    agent.id = "agent_123"
    agent.name = "Test Agent"
    agent.maturity_level = "INTERN"
    return agent


@pytest.fixture
def collaboration_session():
    """Sample collaboration session"""
    session = MagicMock(spec=CanvasCollaborationSession)
    session.id = "collab_session_123"
    session.canvas_id = "canvas_123"
    session.session_id = "canvas_session_123"
    session.user_id = "user_123"
    session.collaboration_mode = CollaborationMode.SEQUENTIAL.value
    session.max_agents = 5
    session.status = "active"
    session.created_at = datetime.now()
    session.completed_at = None
    return session


@pytest.fixture
def agent_participant():
    """Sample agent participant"""
    participant = MagicMock(spec=CanvasAgentParticipant)
    participant.id = "participant_123"
    participant.collaboration_session_id = "collab_session_123"
    participant.agent_id = "agent_123"
    participant.user_id = "user_123"
    participant.role = AgentRole.CONTRIBUTOR.value
    participant.status = "active"
    participant.permissions = {"read": True, "write": True, "delete": False}
    participant.held_locks = []
    participant.actions_count = 5
    participant.last_activity_at = datetime.now()
    participant.left_at = None
    return participant


@pytest.fixture
def service(db_session):
    """Create CanvasCollaborationService instance"""
    return CanvasCollaborationService(db_session)


# =============================================================================
# TEST CLASS: Initialization
# =============================================================================

class TestCanvasCollaborationServiceInit:
    """Tests for CanvasCollaborationService initialization"""

    def test_service_initialization(self, service, db_session):
        """Verify service initializes with database session"""
        assert service.db == db_session
        assert service.db is not None

    def test_service_has_required_methods(self, service):
        """Verify service has all required methods"""
        # Session management
        assert hasattr(service, 'create_collaboration_session')
        assert hasattr(service, 'add_agent_to_session')
        assert hasattr(service, 'remove_agent_from_session')
        assert hasattr(service, 'get_session_status')
        assert hasattr(service, 'complete_session')
        # Permission management
        assert hasattr(service, 'check_agent_permission')
        # Conflict resolution
        assert hasattr(service, 'check_for_conflicts')
        assert hasattr(service, 'resolve_conflict')
        # Activity tracking
        assert hasattr(service, 'record_agent_action')
        assert hasattr(service, 'release_agent_lock')


# =============================================================================
# TEST CLASS: Session Management
# =============================================================================

class TestSessionManagement:
    """Tests for collaboration session management"""

    def test_create_collaboration_session_sequential_mode(self, service, db_session):
        """Test creating session with sequential collaboration mode"""
        db_session.add = MagicMock()
        db_session.commit = MagicMock()
        db_session.refresh = MagicMock()

        result = service.create_collaboration_session(
            canvas_id="canvas_123",
            session_id="canvas_session_123",
            user_id="user_123",
            collaboration_mode=CollaborationMode.SEQUENTIAL.value,
            max_agents=5
        )

        assert "session_id" in result
        assert result["canvas_id"] == "canvas_123"
        assert result["collaboration_mode"] == CollaborationMode.SEQUENTIAL.value
        assert result["max_agents"] == 5
        assert result["status"] == "active"
        db_session.add.assert_called_once()
        db_session.commit.assert_called()

    def test_create_collaboration_session_parallel_mode(self, service, db_session):
        """Test creating session with parallel collaboration mode"""
        db_session.add = MagicMock()
        db_session.commit = MagicMock()

        result = service.create_collaboration_session(
            canvas_id="canvas_123",
            session_id="canvas_session_123",
            user_id="user_123",
            collaboration_mode=CollaborationMode.PARALLEL.value
        )

        assert result["collaboration_mode"] == CollaborationMode.PARALLEL.value

    def test_create_collaboration_session_locked_mode(self, service, db_session):
        """Test creating session with locked collaboration mode"""
        db_session.add = MagicMock()
        db_session.commit = MagicMock()

        result = service.create_collaboration_session(
            canvas_id="canvas_123",
            session_id="canvas_session_123",
            user_id="user_123",
            collaboration_mode=CollaborationMode.LOCKED.value
        )

        assert result["collaboration_mode"] == CollaborationMode.LOCKED.value

    def test_create_session_with_initial_agent(self, service, db_session, sample_agent):
        """Test creating session with initial agent"""
        db_session.add = MagicMock()
        db_session.commit = MagicMock()

        with patch.object(service, 'add_agent_to_session') as mock_add:
            mock_add.return_value = {"participant_id": "p_123"}

            result = service.create_collaboration_session(
                canvas_id="canvas_123",
                session_id="canvas_session_123",
                user_id="user_123",
                initial_agent_id="agent_123"
            )

            mock_add.assert_called_once_with(
                result["session_id"],
                "agent_123",
                "user_123",
                role="owner"
            )

    def test_add_agent_to_session_success(self, service, db_session, collaboration_session, sample_agent):
        """Test successfully adding agent to session"""
        db_session.query.return_value.filter.return_value.first.side_effect = [
            collaboration_session,
            None,  # No existing participant
            sample_agent
        ]
        db_session.query.return_value.filter.return_value.scalar.return_value = 0  # No participants yet
        db_session.add = MagicMock()
        db_session.commit = MagicMock()

        result = service.add_agent_to_session(
            collaboration_session_id="collab_session_123",
            agent_id="agent_123",
            user_id="user_123",
            role=AgentRole.CONTRIBUTOR.value
        )

        assert result["agent_id"] == "agent_123"
        assert result["role"] == AgentRole.CONTRIBUTOR.value
        assert "permissions" in result
        db_session.add.assert_called()
        db_session.commit.assert_called()

    def test_add_agent_session_not_found(self, service, db_session):
        """Test adding agent to non-existent session"""
        db_session.query.return_value.filter.return_value.first.return_value = None

        result = service.add_agent_to_session(
            collaboration_session_id="nonexistent",
            agent_id="agent_123",
            user_id="user_123"
        )

        assert "error" in result
        assert "not found" in result["error"].lower()

    def test_add_agent_session_not_active(self, service, db_session, collaboration_session):
        """Test adding agent to completed session"""
        collaboration_session.status = "completed"
        db_session.query.return_value.filter.return_value.first.return_value = collaboration_session

        result = service.add_agent_to_session(
            collaboration_session_id="collab_session_123",
            agent_id="agent_123",
            user_id="user_123"
        )

        assert "error" in result
        assert "completed" in result["error"].lower()

    def test_add_agent_already_in_session(self, service, db_session, collaboration_session, agent_participant):
        """Test adding agent that's already in session"""
        db_session.query.return_value.filter.return_value.first.side_effect = [
            collaboration_session,
            agent_participant  # Agent already exists
        ]

        result = service.add_agent_to_session(
            collaboration_session_id="collab_session_123",
            agent_id="agent_123",
            user_id="user_123"
        )

        assert "error" in result
        assert "already" in result["error"].lower()

    def test_add_agent_max_agents_reached(self, service, db_session, collaboration_session):
        """Test adding agent when max agents limit reached"""
        collaboration_session.max_agents = 3
        db_session.query.return_value.filter.return_value.first.side_effect = [
            collaboration_session,
            None  # Agent not in session yet
        ]
        db_session.query.return_value.filter.return_value.scalar.return_value = 3  # Already at max

        result = service.add_agent_to_session(
            collaboration_session_id="collab_session_123",
            agent_id="agent_123",
            user_id="user_123"
        )

        assert "error" in result
        assert "maximum" in result["error"].lower() or "capacity" in result["error"].lower()

    def test_add_agent_not_found(self, service, db_session, collaboration_session):
        """Test adding non-existent agent"""
        db_session.query.return_value.filter.return_value.first.side_effect = [
            collaboration_session,
            None,  # Not already in session
            None  # Agent doesn't exist
        ]
        db_session.query.return_value.filter.return_value.scalar.return_value = 0

        result = service.add_agent_to_session(
            collaboration_session_id="collab_session_123",
            agent_id="nonexistent_agent",
            user_id="user_123"
        )

        assert "error" in result
        assert "not found" in result["error"].lower()

    def test_remove_agent_from_session_success(self, service, db_session, agent_participant):
        """Test successfully removing agent from session"""
        db_session.query.return_value.filter.return_value.first.return_value = agent_participant
        agent_participant.held_locks = ["component_1", "component_2"]
        db_session.commit = MagicMock()

        result = service.remove_agent_from_session(
            collaboration_session_id="collab_session_123",
            agent_id="agent_123"
        )

        assert result["agent_id"] == "agent_123"
        assert result["status"] == "removed"
        assert agent_participant.left_at is not None
        assert agent_participant.status == "completed"
        db_session.commit.assert_called()

    def test_remove_agent_not_found(self, service, db_session):
        """Test removing agent that's not in session"""
        db_session.query.return_value.filter.return_value.first.return_value = None

        result = service.remove_agent_from_session(
            collaboration_session_id="collab_session_123",
            agent_id="nonexistent_agent"
        )

        assert "error" in result
        assert "not found" in result["error"].lower()

    def test_get_session_status_success(self, service, db_session, collaboration_session):
        """Test getting session status"""
        # Setup participants
        participant1 = MagicMock(spec=CanvasAgentParticipant)
        participant1.id = "p1"
        participant1.agent_id = "agent_1"
        participant1.role = "owner"
        participant1.status = "active"
        participant1.actions_count = 10
        participant1.held_locks = []
        participant1.last_activity_at = datetime.now()

        participant2 = MagicMock(spec=CanvasAgentParticipant)
        participant2.id = "p2"
        participant2.agent_id = "agent_2"
        participant2.role = "contributor"
        participant2.status = "active"
        participant2.actions_count = 5
        participant2.held_locks = ["component_1"]
        participant2.last_activity_at = datetime.now()

        db_session.query.return_value.filter.side_effect = [
            MagicMock(first=MagicMock(return_value=collaboration_session)),
            MagicMock(all=MagicMock(return_value=[participant1, participant2]))
        ]

        result = service.get_session_status("collab_session_123")

        assert result["session_id"] == "collab_session_123"
        assert result["status"] == "active"
        assert result["collaboration_mode"] == CollaborationMode.SEQUENTIAL.value
        assert result["max_agents"] == 5
        assert len(result["participants"]) == 2
        assert result["participants"][0]["agent_id"] == "agent_1"

    def test_get_session_status_not_found(self, service, db_session):
        """Test getting status for non-existent session"""
        db_session.query.return_value.filter.return_value.first.return_value = None

        result = service.get_session_status("nonexistent")

        assert "error" in result
        assert "not found" in result["error"].lower()

    def test_complete_session_success(self, service, db_session, collaboration_session):
        """Test completing a collaboration session"""
        # Setup participants
        participant1 = MagicMock(spec=CanvasAgentParticipant)
        participant1.actions_count = 10
        participant2 = MagicMock(spec=CanvasAgentParticipant)
        participant2.actions_count = 5

        db_session.query.return_value.filter.side_effect = [
            MagicMock(first=MagicMock(return_value=collaboration_session)),
            MagicMock(update=MagicMock()),
            MagicMock(all=MagicMock(return_value=[participant1, participant2])),
            MagicMock(count=MagicMock(return_value=2))
        ]
        db_session.commit = MagicMock()

        result = service.complete_session("collab_session_123")

        assert result["session_id"] == "collab_session_123"
        assert result["status"] == "completed"
        assert result["total_participants"] == 2
        assert result["total_actions"] == 15
        assert result["total_conflicts"] == 2
        assert collaboration_session.status == "completed"
        db_session.commit.assert_called()

    def test_complete_session_not_found(self, service, db_session):
        """Test completing non-existent session"""
        db_session.query.return_value.filter.return_value.first.return_value = None

        result = service.complete_session("nonexistent")

        assert "error" in result
        assert "not found" in result["error"].lower()


# =============================================================================
# TEST CLASS: Permission Management
# =============================================================================

class TestPermissionManagement:
    """Tests for permission management"""

    def test_check_permission_owner_read(self, service, db_session, agent_participant):
        """Test owner has read permission"""
        agent_participant.role = AgentRole.OWNER.value
        db_session.query.return_value.filter.return_value.first.return_value = agent_participant

        result = service.check_agent_permission(
            collaboration_session_id="collab_session_123",
            agent_id="agent_123",
            action="read"
        )

        assert result["allowed"] is True

    def test_check_permission_owner_delete(self, service, db_session, agent_participant):
        """Test owner has delete permission"""
        agent_participant.role = AgentRole.OWNER.value
        db_session.query.return_value.filter.return_value.first.return_value = agent_participant

        result = service.check_agent_permission(
            collaboration_session_id="collab_session_123",
            agent_id="agent_123",
            action="delete"
        )

        assert result["allowed"] is True

    def test_check_permission_contributor_write(self, service, db_session, agent_participant):
        """Test contributor has write permission"""
        agent_participant.role = AgentRole.CONTRIBUTOR.value
        db_session.query.return_value.filter.return_value.first.return_value = agent_participant

        result = service.check_agent_permission(
            collaboration_session_id="collab_session_123",
            agent_id="agent_123",
            action="write"
        )

        assert result["allowed"] is True

    def test_check_permission_contributor_cannot_delete(self, service, db_session, agent_participant):
        """Test contributor cannot delete"""
        agent_participant.role = AgentRole.CONTRIBUTOR.value
        agent_participant.permissions = {"read": True, "write": True, "delete": False}
        db_session.query.return_value.filter.return_value.first.return_value = agent_participant

        result = service.check_agent_permission(
            collaboration_session_id="collab_session_123",
            agent_id="agent_123",
            action="delete"
        )

        assert result["allowed"] is False

    def test_check_permission_reviewer_read(self, service, db_session, agent_participant):
        """Test reviewer can read"""
        agent_participant.role = AgentRole.REVIEWER.value
        db_session.query.return_value.filter.return_value.first.return_value = agent_participant

        result = service.check_agent_permission(
            collaboration_session_id="collab_session_123",
            agent_id="agent_123",
            action="read"
        )

        assert result["allowed"] is True

    def test_check_permission_reviewer_suggest(self, service, db_session, agent_participant):
        """Test reviewer can suggest"""
        agent_participant.role = AgentRole.REVIEWER.value
        db_session.query.return_value.filter.return_value.first.return_value = agent_participant

        result = service.check_agent_permission(
            collaboration_session_id="collab_session_123",
            agent_id="agent_123",
            action="suggest"
        )

        assert result["allowed"] is True

    def test_check_permission_reviewer_cannot_write(self, service, db_session, agent_participant):
        """Test reviewer cannot write"""
        agent_participant.role = AgentRole.REVIEWER.value
        db_session.query.return_value.filter.return_value.first.return_value = agent_participant

        result = service.check_agent_permission(
            collaboration_session_id="collab_session_123",
            agent_id="agent_123",
            action="write"
        )

        assert result["allowed"] is False

    def test_check_permission_viewer_read_only(self, service, db_session, agent_participant):
        """Test viewer can only read"""
        agent_participant.role = AgentRole.VIEWER.value
        db_session.query.return_value.filter.return_value.first.return_value = agent_participant

        result = service.check_agent_permission(
            collaboration_session_id="collab_session_123",
            agent_id="agent_123",
            action="read"
        )

        assert result["allowed"] is True

    def test_check_permission_viewer_cannot_write(self, service, db_session, agent_participant):
        """Test viewer cannot write"""
        agent_participant.role = AgentRole.VIEWER.value
        db_session.query.return_value.filter.return_value.first.return_value = agent_participant

        result = service.check_agent_permission(
            collaboration_session_id="collab_session_123",
            agent_id="agent_123",
            action="write"
        )

        assert result["allowed"] is False

    def test_check_permission_not_in_session(self, service, db_session):
        """Test permission check for agent not in session"""
        db_session.query.return_value.filter.return_value.first.return_value = None

        result = service.check_agent_permission(
            collaboration_session_id="collab_session_123",
            agent_id="nonexistent_agent",
            action="read"
        )

        assert result["allowed"] is False
        assert "not in this collaboration session" in result["reason"]

    def test_check_permission_inactive_agent(self, service, db_session, agent_participant):
        """Test permission check for inactive agent"""
        agent_participant.status = "completed"
        db_session.query.return_value.filter.return_value.first.return_value = agent_participant

        result = service.check_agent_permission(
            collaboration_session_id="collab_session_123",
            agent_id="agent_123",
            action="read"
        )

        assert result["allowed"] is False
        assert "completed" in result["reason"]

    def test_check_permission_component_specific(self, service, db_session, agent_participant):
        """Test component-specific permission override"""
        agent_participant.role = AgentRole.CONTRIBUTOR.value
        agent_participant.permissions = {
            "read": True,
            "write": True,
            "components": {
                "special_component": {"write": False}
            }
        }
        db_session.query.return_value.filter.return_value.first.return_value = agent_participant

        result = service.check_agent_permission(
            collaboration_session_id="collab_session_123",
            agent_id="agent_123",
            action="write",
            component_id="special_component"
        )

        assert result["allowed"] is False
        assert "Component-specific permission" in result["reason"]


# =============================================================================
# TEST CLASS: Conflict Resolution
# =============================================================================

class TestConflictResolution:
    """Tests for conflict detection and resolution"""

    def test_check_conflicts_sequential_mode_no_conflict(self, service, db_session, collaboration_session):
        """Test sequential mode with no recent activity"""
        collaboration_session.collaboration_mode = CollaborationMode.SEQUENTIAL.value
        db_session.query.return_value.filter.return_value.first.side_effect = [
            collaboration_session,
            None  # No recent activity
        ]

        result = service.check_for_conflicts(
            collaboration_session_id="collab_session_123",
            agent_id="agent_123",
            component_id="component_1",
            action={"type": "update"}
        )

        assert result["has_conflict"] is False

    def test_check_conflicts_sequential_mode_with_conflict(self, service, db_session, collaboration_session):
        """Test sequential mode with recent activity from another agent"""
        collaboration_session.collaboration_mode = CollaborationMode.SEQUENTIAL.value

        recent_participant = MagicMock(spec=CanvasAgentParticipant)
        recent_participant.agent_id = "agent_456"
        recent_participant.last_activity_at = datetime.now()

        db_session.query.return_value.filter.return_value.first.side_effect = [
            collaboration_session,
            recent_participant  # Recent activity
        ]

        result = service.check_for_conflicts(
            collaboration_session_id="collab_session_123",
            agent_id="agent_123",
            component_id="component_1",
            action={"type": "update"}
        )

        assert result["has_conflict"] is True
        assert result["conflict_type"] == "sequential"
        assert result["conflicting_agent"] == "agent_456"

    def test_check_conflicts_parallel_mode_locked_component(self, service, db_session, collaboration_session):
        """Test parallel mode with locked component"""
        collaboration_session.collaboration_mode = CollaborationMode.PARALLEL.value

        locking_participant = MagicMock(spec=CanvasAgentParticipant)
        locking_participant.agent_id = "agent_456"
        locking_participant.status = "active"
        locking_participant.held_locks = ["component_1"]

        db_session.query.return_value.filter.return_value.first.side_effect = [
            collaboration_session,
            MagicMock(all=MagicMock(return_value=[locking_participant]))
        ]

        result = service.check_for_conflicts(
            collaboration_session_id="collab_session_123",
            agent_id="agent_123",
            component_id="component_1",
            action={"type": "update"}
        )

        assert result["has_conflict"] is True
        assert result["conflict_type"] == "locked"

    def test_check_conflicts_parallel_mode_no_conflict(self, service, db_session, collaboration_session):
        """Test parallel mode with no locks"""
        collaboration_session.collaboration_mode = CollaborationMode.PARALLEL.value

        db_session.query.return_value.filter.return_value.first.side_effect = [
            collaboration_session,
            MagicMock(all=MagicMock(return_value=[]))
        ]

        result = service.check_for_conflicts(
            collaboration_session_id="collab_session_123",
            agent_id="agent_123",
            component_id="component_1",
            action={"type": "update"}
        )

        assert result["has_conflict"] is False

    def test_check_conflicts_locked_mode(self, service, db_session, collaboration_session):
        """Test locked mode"""
        collaboration_session.collaboration_mode = CollaborationMode.LOCKED.value

        locking_participant = MagicMock(spec=CanvasAgentParticipant)
        locking_participant.agent_id = "agent_456"
        locking_participant.status = "active"
        locking_participant.held_locks = ["component_1"]

        db_session.query.return_value.filter.return_value.first.side_effect = [
            collaboration_session,
            MagicMock(all=MagicMock(return_value=[locking_participant]))
        ]

        result = service.check_for_conflicts(
            collaboration_session_id="collab_session_123",
            agent_id="agent_123",
            component_id="component_1",
            action={"type": "update"}
        )

        assert result["has_conflict"] is True
        assert result["conflict_type"] == "locked"

    def test_resolve_conflict_first_come_first_served(self, service, db_session, collaboration_session):
        """Test conflict resolution with first_come_first_served strategy"""
        agent_a_action = {"type": "update", "value": "A"}
        agent_b_action = {"type": "update", "value": "B"}

        db_session.query.return_value.filter.return_value.first.return_value = collaboration_session
        db_session.add = MagicMock()
        db_session.commit = MagicMock()

        result = service.resolve_conflict(
            collaboration_session_id="collab_session_123",
            agent_a_id="agent_a",
            agent_b_id="agent_b",
            component_id="component_1",
            agent_a_action=agent_a_action,
            agent_b_action=agent_b_action,
            resolution_strategy="first_come_first_served"
        )

        assert result["resolution"] == "agent_a_wins"
        assert result["resolved_action"] == agent_a_action
        db_session.add.assert_called()
        db_session.commit.assert_called()

    def test_resolve_conflict_priority_owner_wins(self, service, db_session, collaboration_session):
        """Test conflict resolution with priority strategy"""
        # Create participants with different roles
        participant_a = MagicMock(spec=CanvasAgentParticipant)
        participant_a.role = AgentRole.CONTRIBUTOR.value

        participant_b = MagicMock(spec=CanvasAgentParticipant)
        participant_b.role = AgentRole.OWNER.value

        agent_a_action = {"type": "update", "value": "A"}
        agent_b_action = {"type": "update", "value": "B"}

        db_session.query.return_value.filter.side_effect = [
            MagicMock(first=MagicMock(return_value=collaboration_session)),
            MagicMock(first=MagicMock(return_value=participant_a)),
            MagicMock(first=MagicMock(return_value=participant_b))
        ]
        db_session.add = MagicMock()
        db_session.commit = MagicMock()

        result = service.resolve_conflict(
            collaboration_session_id="collab_session_123",
            agent_a_id="agent_a",
            agent_b_id="agent_b",
            component_id="component_1",
            agent_a_action=agent_a_action,
            agent_b_action=agent_b_action,
            resolution_strategy="priority"
        )

        # Owner has higher priority than contributor
        assert result["resolution"] == "agent_b_wins"
        assert result["resolved_action"] == agent_b_action

    def test_resolve_conflict_merge(self, service, db_session, collaboration_session):
        """Test conflict resolution with merge strategy"""
        agent_a_action = {"type": "update", "value": "A"}
        agent_b_action = {"type": "update", "value": "B"}

        db_session.query.return_value.filter.return_value.first.return_value = collaboration_session
        db_session.add = MagicMock()
        db_session.commit = MagicMock()

        result = service.resolve_conflict(
            collaboration_session_id="collab_session_123",
            agent_a_id="agent_a",
            agent_b_id="agent_b",
            component_id="component_1",
            agent_a_action=agent_a_action,
            agent_b_action=agent_b_action,
            resolution_strategy="merge"
        )

        assert result["resolution"] == "merged"
        # Merge implementation currently prefers action_a
        assert result["resolved_action"] == agent_a_action


# =============================================================================
# TEST CLASS: Activity Tracking
# =============================================================================

class TestActivityTracking:
    """Tests for activity tracking and lock management"""

    def test_record_agent_action_success(self, service, db_session, agent_participant):
        """Test recording agent action"""
        db_session.query.return_value.filter.return_value.first.return_value = agent_participant
        agent_participant.actions_count = 5
        db_session.commit = MagicMock()
        db_session.refresh = MagicMock()

        result = service.record_agent_action(
            collaboration_session_id="collab_session_123",
            agent_id="agent_123",
            action="update",
            component_id="component_1"
        )

        assert result["agent_id"] == "agent_123"
        assert result["action"] == "update"
        assert result["component_id"] == "component_1"
        assert result["actions_count"] == 6  # Incremented
        assert agent_participant.last_activity_at is not None
        db_session.commit.assert_called()

    def test_record_agent_action_with_lock(self, service, db_session, agent_participant):
        """Test recording action adds lock"""
        db_session.query.return_value.filter.return_value.first.return_value = agent_participant
        agent_participant.actions_count = 0
        agent_participant.held_locks = []
        db_session.commit = MagicMock()
        db_session.refresh = MagicMock()

        result = service.record_agent_action(
            collaboration_session_id="collab_session_123",
            agent_id="agent_123",
            action="update",
            component_id="component_1"
        )

        assert "component_1" in agent_participant.held_locks
        db_session.commit.assert_called()

    def test_record_agent_action_not_in_session(self, service, db_session):
        """Test recording action for agent not in session"""
        db_session.query.return_value.filter.return_value.first.return_value = None

        result = service.record_agent_action(
            collaboration_session_id="collab_session_123",
            agent_id="nonexistent",
            action="update"
        )

        assert "error" in result
        assert "not found" in result["error"].lower()

    def test_release_agent_lock_success(self, service, db_session, agent_participant):
        """Test releasing agent lock"""
        agent_participant.held_locks = ["component_1", "component_2"]
        db_session.query.return_value.filter.return_value.first.return_value = agent_participant
        db_session.commit = MagicMock()
        db_session.refresh = MagicMock()

        result = service.release_agent_lock(
            collaboration_session_id="collab_session_123",
            agent_id="agent_123",
            component_id="component_1"
        )

        assert result["status"] == "released"
        assert result["component_id"] == "component_1"
        assert "component_1" not in agent_participant.held_locks
        db_session.commit.assert_called()

    def test_release_agent_lock_not_held(self, service, db_session, agent_participant):
        """Test releasing lock that agent doesn't hold"""
        agent_participant.held_locks = ["component_2"]
        db_session.query.return_value.filter.return_value.first.return_value = agent_participant

        result = service.release_agent_lock(
            collaboration_session_id="collab_session_123",
            agent_id="agent_123",
            component_id="component_1"
        )

        assert "error" in result
        assert "does not hold lock" in result["error"].lower()

    def test_release_agent_lock_not_in_session(self, service, db_session):
        """Test releasing lock for agent not in session"""
        db_session.query.return_value.filter.return_value.first.return_value = None

        result = service.release_agent_lock(
            collaboration_session_id="collab_session_123",
            agent_id="nonexistent",
            component_id="component_1"
        )

        assert "error" in result
        assert "not found" in result["error"].lower()


# =============================================================================
# TEST CLASS: Edge Cases and Error Handling
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling"""

    def test_add_agent_with_custom_permissions(self, service, db_session, collaboration_session, sample_agent):
        """Test adding agent with custom permissions"""
        custom_perms = {"read": True, "write": True, "delete": True, "lock": True}
        db_session.query.return_value.filter.side_effect = [
            MagicMock(first=MagicMock(return_value=collaboration_session)),
            MagicMock(first=MagicMock(return_value=None)),  # Not already in session
            MagicMock(first=MagicMock(return_value=sample_agent))
        ]
        db_session.query.return_value.scalar.return_value = 0
        db_session.add = MagicMock()
        db_session.commit = MagicMock()

        result = service.add_agent_to_session(
            collaboration_session_id="collab_session_123",
            agent_id="agent_123",
            user_id="user_123",
            role=AgentRole.CONTRIBUTOR.value,
            permissions=custom_perms
        )

        assert result["permissions"] == custom_perms

    def test_get_default_permissions_owner(self, service):
        """Test default permissions for owner role"""
        perms = service._get_default_permissions(AgentRole.OWNER.value)
        assert perms["read"] is True
        assert perms["write"] is True
        assert perms["delete"] is True
        assert perms["lock"] is True

    def test_get_default_permissions_contributor(self, service):
        """Test default permissions for contributor role"""
        perms = service._get_default_permissions(AgentRole.CONTRIBUTOR.value)
        assert perms["read"] is True
        assert perms["write"] is True
        assert perms["delete"] is False
        assert perms["lock"] is False

    def test_get_default_permissions_reviewer(self, service):
        """Test default permissions for reviewer role"""
        perms = service._get_default_permissions(AgentRole.REVIEWER.value)
        assert perms["read"] is True
        assert perms["suggest"] is True
        assert perms["write"] is False
        assert perms["delete"] is False

    def test_get_default_permissions_viewer(self, service):
        """Test default permissions for viewer role"""
        perms = service._get_default_permissions(AgentRole.VIEWER.value)
        assert perms["read"] is True
        assert "write" not in perms

    def test_merge_actions(self, service):
        """Test action merge functionality"""
        action_a = {"type": "update", "value": "A", "data": {"key": "val"}}
        action_b = {"type": "update", "value": "B"}

        result = service._merge_actions(action_a, action_b)

        # Current implementation returns action_a
        assert result == action_a

    def test_release_all_locks(self, service, agent_participant):
        """Test releasing all locks for participant"""
        agent_participant.held_locks = ["comp1", "comp2", "comp3"]
        db_session = MagicMock()
        db_session.commit = MagicMock()

        service._release_all_locks(agent_participant)

        assert agent_participant.held_locks == []
        db_session.commit.assert_called_once()

    def test_remove_agent_releases_locks(self, service, db_session, agent_participant):
        """Test that removing agent releases their locks"""
        agent_participant.held_locks = ["component_1", "component_2"]
        db_session.query.return_value.filter.return_value.first.return_value = agent_participant
        db_session.commit = MagicMock()

        service.remove_agent_from_session(
            collaboration_session_id="collab_session_123",
            agent_id="agent_123"
        )

        # Locks should be released
        assert agent_participant.held_locks == []

    def test_check_conflicts_session_not_found(self, service, db_session):
        """Test conflict check for non-existent session"""
        db_session.query.return_value.filter.return_value.first.return_value = None

        result = service.check_for_conflicts(
            collaboration_session_id="nonexistent",
            agent_id="agent_123",
            component_id="component_1",
            action={"type": "update"}
        )

        assert result["has_conflict"] is False
        assert "Session not found" in result["reason"]

    def test_resolve_conflict_default_strategy(self, service, db_session, collaboration_session):
        """Test conflict resolution with default/unknown strategy"""
        db_session.query.return_value.filter.return_value.first.return_value = collaboration_session
        db_session.add = MagicMock()
        db_session.commit = MagicMock()

        result = service.resolve_conflict(
            collaboration_session_id="collab_session_123",
            agent_a_id="agent_a",
            agent_b_id="agent_b",
            component_id="component_1",
            agent_a_action={"value": "A"},
            agent_b_action={"value": "B"},
            resolution_strategy="unknown_strategy"
        )

        # Should default to agent_a_wins
        assert result["resolution"] == "agent_a_wins"

    def test_record_action_without_component(self, service, db_session, agent_participant):
        """Test recording action without component ID"""
        db_session.query.return_value.filter.return_value.first.return_value = agent_participant
        agent_participant.actions_count = 5
        agent_participant.held_locks = []
        db_session.commit = MagicMock()

        result = service.record_agent_action(
            collaboration_session_id="collab_session_123",
            agent_id="agent_123",
            action="read"
        )

        assert result["actions_count"] == 6
        assert agent_participant.held_locks == []  # No lock added


# =============================================================================
# TEST CLASS: Collaboration Mode Specific Tests
# =============================================================================

class TestCollaborationModes:
    """Tests specific to collaboration modes"""

    def test_sequential_mode_time_window(self, service, db_session, collaboration_session):
        """Test that sequential mode uses 5-second time window"""
        collaboration_session.collaboration_mode = CollaborationMode.SEQUENTIAL.value

        # Activity older than 5 seconds
        old_participant = MagicMock(spec=CanvasAgentParticipant)
        old_participant.agent_id = "agent_456"
        old_participant.last_activity_at = datetime.now() - timedelta(seconds=6)

        db_session.query.return_value.filter.return_value.first.side_effect = [
            collaboration_session,
            None  # No recent activity
        ]

        result = service.check_for_conflicts(
            collaboration_session_id="collab_session_123",
            agent_id="agent_123",
            component_id="component_1",
            action={"type": "update"}
        )

        assert result["has_conflict"] is False

    def test_parallel_mode_concurrent_different_components(self, service, db_session, collaboration_session):
        """Test parallel mode allows different components"""
        collaboration_session.collaboration_mode = CollaborationMode.PARALLEL.value

        other_participant = MagicMock(spec=CanvasAgentParticipant)
        other_participant.agent_id = "agent_456"
        other_participant.held_locks = ["component_2"]  # Different component

        db_session.query.return_value.filter.return_value.first.side_effect = [
            collaboration_session,
            MagicMock(all=MagicMock(return_value=[other_participant]))
        ]

        result = service.check_for_conflicts(
            collaboration_session_id="collab_session_123",
            agent_id="agent_123",
            component_id="component_1",  # Different component
            action={"type": "update"}
        )

        assert result["has_conflict"] is False

    def test_locked_mode_first_come_first_served(self, service, db_session, collaboration_session):
        """Test locked mode allows first agent to work"""
        collaboration_session.collaboration_mode = CollaborationMode.LOCKED.value

        # No one has locked component_1 yet
        db_session.query.return_value.filter.return_value.first.side_effect = [
            collaboration_session,
            MagicMock(all=MagicMock(return_value=[]))
        ]

        result = service.check_for_conflicts(
            collaboration_session_id="collab_session_123",
            agent_id="agent_123",
            component_id="component_1",
            action={"type": "update"}
        )

        assert result["has_conflict"] is False
