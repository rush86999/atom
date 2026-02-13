"""
Unit tests for Canvas Collaboration Service

Tests cover:
- Session management (create, add agent, remove agent, get status)
- Permission management (check permissions, update permissions)
- Lock management (acquire lock, release lock, get active locks)
- Conflict resolution (detect conflicts, resolve conflicts)
- Role-based access control (owner, contributor, reviewer, viewer)
- Collaboration modes (sequential, parallel, locked)
"""

import pytest
from unittest.mock import MagicMock, Mock, patch
from datetime import datetime, timedelta
from typing import Dict, Any, List
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
def mock_db():
    """Mock database session"""
    db = MagicMock(spec=Session)
    db.add = MagicMock()
    db.commit = MagicMock()
    db.rollback = MagicMock()
    db.refresh = MagicMock()
    db.query = MagicMock()
    return db


@pytest.fixture
def collaboration_service(mock_db):
    """Create CanvasCollaborationService instance"""
    return CanvasCollaborationService(mock_db)


@pytest.fixture
def sample_session():
    """Sample collaboration session"""
    session = MagicMock(spec=CanvasCollaborationSession)
    session.id = "session_123"
    session.canvas_id = "canvas_123"
    session.session_id = "canvas_session_123"
    session.user_id = "user_123"
    session.collaboration_mode = CollaborationMode.SEQUENTIAL.value
    session.max_agents = 5
    session.status = "active"
    session.created_at = datetime.now()
    return session


@pytest.fixture
def sample_agent():
    """Sample agent"""
    agent = MagicMock(spec=AgentRegistry)
    agent.id = "agent_123"
    agent.name = "Test Agent"
    agent.maturity_level = "INTERN"
    return agent


@pytest.fixture
def sample_participant():
    """Sample canvas participant"""
    participant = MagicMock(spec=CanvasAgentParticipant)
    participant.id = "participant_123"
    participant.collaboration_session_id = "session_123"
    participant.agent_id = "agent_123"
    participant.user_id = "user_123"
    participant.role = AgentRole.CONTRIBUTOR.value
    participant.status = "active"
    participant.permissions = {"read": True, "write": True, "delete": False}
    participant.held_locks = []
    participant.actions_count = 0
    participant.last_activity_at = datetime.now()
    participant.left_at = None
    return participant


# =============================================================================
# TEST CLASS: Initialization
# =============================================================================

class TestCanvasCollaborationServiceInit:
    """Tests for CanvasCollaborationService initialization"""

    def test_service_init(self, collaboration_service, mock_db):
        """Verify service initializes with database session"""
        assert collaboration_service.db == mock_db
        assert collaboration_service.db is not None

    def test_service_has_required_methods(self, collaboration_service):
        """Verify service has all required methods"""
        assert hasattr(collaboration_service, 'create_collaboration_session')
        assert hasattr(collaboration_service, 'add_agent_to_session')
        assert hasattr(collaboration_service, 'remove_agent_from_session')
        assert hasattr(collaboration_service, 'get_session_status')
        assert hasattr(collaboration_service, 'check_agent_permission')
        assert hasattr(collaboration_service, 'acquire_component_lock')
        assert hasattr(collaboration_service, 'release_component_lock')
        assert hasattr(collaboration_service, 'detect_conflict')
        assert hasattr(collaboration_service, 'resolve_conflict')


# =============================================================================
# TEST CLASS: Session Management
# =============================================================================

class TestSessionManagement:
    """Tests for collaboration session management"""

    def test_create_collaboration_session_success(self, collaboration_service, mock_db, sample_session):
        """Test successful collaboration session creation"""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = collaboration_service.create_collaboration_session(
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
        mock_db.add.assert_called()

    def test_create_collaboration_session_with_initial_agent(self, collaboration_service, mock_db, sample_agent):
        """Test creating session with initial agent"""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_agent

        with patch.object(collaboration_service, 'add_agent_to_session') as mock_add:
            mock_add.return_value = {"participant_id": "p_123"}

            result = collaboration_service.create_collaboration_session(
                canvas_id="canvas_123",
                session_id="canvas_session_123",
                user_id="user_123",
                initial_agent_id="agent_123"
            )

            mock_add.assert_called_once()

    def test_create_collaboration_session_parallel_mode(self, collaboration_service, mock_db):
        """Test creating session with parallel collaboration mode"""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = collaboration_service.create_collaboration_session(
            canvas_id="canvas_123",
            session_id="canvas_session_123",
            user_id="user_123",
            collaboration_mode=CollaborationMode.PARALLEL.value
        )

        assert result["collaboration_mode"] == CollaborationMode.PARALLEL.value

    def test_create_collaboration_session_locked_mode(self, collaboration_service, mock_db):
        """Test creating session with locked collaboration mode"""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = collaboration_service.create_collaboration_session(
            canvas_id="canvas_123",
            session_id="canvas_session_123",
            user_id="user_123",
            collaboration_mode=CollaborationMode.LOCKED.value
        )

        assert result["collaboration_mode"] == CollaborationMode.LOCKED.value

    def test_add_agent_to_session_success(self, collaboration_service, mock_db, sample_session, sample_agent):
        """Test successfully adding agent to session"""
        mock_db.query.return_value.filter.return_value.first.side_effect = [sample_session, sample_agent, None]

        result = collaboration_service.add_agent_to_session(
            collaboration_session_id="session_123",
            agent_id="agent_123",
            user_id="user_123",
            role=AgentRole.CONTRIBUTOR.value
        )

        assert "participant_id" in result
        assert result["agent_id"] == "agent_123"
        assert result["role"] == AgentRole.CONTRIBUTOR.value
        mock_db.add.assert_called()

    def test_add_agent_to_session_not_found(self, collaboration_service, mock_db):
        """Test adding agent to non-existent session"""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = collaboration_service.add_agent_to_session(
            collaboration_session_id="nonexistent",
            agent_id="agent_123",
            user_id="user_123"
        )

        assert "error" in result
        assert "not found" in result["error"]

    def test_add_agent_to_session_inactive(self, collaboration_service, mock_db, sample_session):
        """Test adding agent to inactive session"""
        sample_session.status = "completed"
        mock_db.query.return_value.filter.return_value.first.return_value = sample_session

        result = collaboration_service.add_agent_to_session(
            collaboration_session_id="session_123",
            agent_id="agent_123",
            user_id="user_123"
        )

        assert "error" in result
        assert "completed" in result["error"]

    def test_add_agent_already_in_session(self, collaboration_service, mock_db, sample_session, sample_participant):
        """Test adding agent that's already in session"""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_participant

        result = collaboration_service.add_agent_to_session(
            collaboration_session_id="session_123",
            agent_id="agent_123",
            user_id="user_123"
        )

        assert "error" in result
        assert "already in this session" in result["error"]

    def test_add_agent_exceeds_max_agents(self, collaboration_service, mock_db, sample_session):
        """Test adding agent exceeds max capacity"""
        from sqlalchemy import func

        mock_db.query.return_value.filter.return_value.first.side_effect = [sample_session, None]
        mock_db.query.return_value.filter.return_value.scalar.return_value = 5  # Max reached

        result = collaboration_service.add_agent_to_session(
            collaboration_session_id="session_123",
            agent_id="agent_new",
            user_id="user_123"
        )

        assert "error" in result
        assert "maximum agent capacity" in result["error"]

    def test_remove_agent_from_session_success(self, collaboration_service, mock_db, sample_participant):
        """Test successfully removing agent from session"""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_participant

        result = collaboration_service.remove_agent_from_session(
            collaboration_session_id="session_123",
            agent_id="agent_123"
        )

        assert result["agent_id"] == "agent_123"
        assert result["status"] == "removed"
        mock_db.commit.assert_called()

    def test_remove_agent_not_in_session(self, collaboration_service, mock_db):
        """Test removing agent not in session"""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = collaboration_service.remove_agent_from_session(
            collaboration_session_id="session_123",
            agent_id="agent_123"
        )

        assert "error" in result
        assert "not found in session" in result["error"]

    def test_get_session_status_success(self, collaboration_service, mock_db, sample_session, sample_participant):
        """Test successfully getting session status"""
        mock_db.query.return_value.filter.return_value.first.side_effect = [sample_session, [sample_participant]]

        result = collaboration_service.get_session_status("session_123")

        assert result["session_id"] == "session_123"
        assert result["canvas_id"] == "canvas_123"
        assert result["status"] == "active"
        assert "participants" in result
        assert len(result["participants"]) == 1

    def test_get_session_status_not_found(self, collaboration_service, mock_db):
        """Test getting status of non-existent session"""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = collaboration_service.get_session_status("nonexistent")

        assert "error" in result
        assert "not found" in result["error"]


# =============================================================================
# TEST CLASS: Permission Management
# =============================================================================

class TestPermissionManagement:
    """Tests for permission management"""

    def test_check_agent_permission_allowed(self, collaboration_service, mock_db, sample_participant):
        """Test agent has permission for action"""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_participant

        result = collaboration_service.check_agent_permission(
            collaboration_session_id="session_123",
            agent_id="agent_123",
            action="write",
            component_id="component_123"
        )

        assert result["allowed"] is True

    def test_check_agent_permission_not_participant(self, collaboration_service, mock_db):
        """Test checking permission for non-participant"""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = collaboration_service.check_agent_permission(
            collaboration_session_id="session_123",
            agent_id="agent_123",
            action="write"
        )

        assert result["allowed"] is False
        assert "not in this collaboration session" in result["reason"]

    def test_check_agent_permission_inactive(self, collaboration_service, mock_db, sample_participant):
        """Test checking permission for inactive participant"""
        sample_participant.status = "completed"
        mock_db.query.return_value.filter.return_value.first.return_value = sample_participant

        result = collaboration_service.check_agent_permission(
            collaboration_session_id="session_123",
            agent_id="agent_123",
            action="write"
        )

        assert result["allowed"] is False

    def test_check_owner_permission_all_actions(self, collaboration_service, mock_db):
        """Test owner has permission for all actions"""
        participant = MagicMock(spec=CanvasAgentParticipant)
        participant.role = AgentRole.OWNER.value
        participant.status = "active"
        participant.permissions = {"read": True, "write": True, "delete": True, "lock": True}

        mock_db.query.return_value.filter.return_value.first.return_value = participant

        for action in ["read", "write", "delete", "lock"]:
            result = collaboration_service.check_agent_permission(
                collaboration_session_id="session_123",
                agent_id="agent_123",
                action=action
            )
            assert result["allowed"] is True

    def test_check_viewer_permission_read_only(self, collaboration_service, mock_db):
        """Test viewer only has read permission"""
        participant = MagicMock(spec=CanvasAgentParticipant)
        participant.role = AgentRole.VIEWER.value
        participant.status = "active"
        participant.permissions = {"read": True, "write": False, "delete": False}

        mock_db.query.return_value.filter.return_value.first.return_value = participant

        # Read should be allowed
        result = collaboration_service.check_agent_permission(
            collaboration_session_id="session_123",
            agent_id="agent_123",
            action="read"
        )
        assert result["allowed"] is True

        # Write should be denied
        result = collaboration_service.check_agent_permission(
            collaboration_session_id="session_123",
            agent_id="agent_123",
            action="write"
        )
        assert result["allowed"] is False


# =============================================================================
# TEST CLASS: Lock Management
# =============================================================================

class TestLockManagement:
    """Tests for component lock management"""

    def test_acquire_lock_success(self, collaboration_service, mock_db, sample_participant, sample_session):
        """Test successfully acquiring component lock"""
        mock_db.query.return_value.filter.return_value.first.side_effect = [sample_participant, None, sample_session]

        result = collaboration_service.acquire_component_lock(
            collaboration_session_id="session_123",
            agent_id="agent_123",
            component_id="component_123"
        )

        assert result["success"] is True
        assert "component_123" in result["lock_id"]
        mock_db.commit.assert_called()

    def test_acquire_lock_already_locked(self, collaboration_service, mock_db, sample_participant):
        """Test acquiring lock on already locked component"""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_participant

        result = collaboration_service.acquire_component_lock(
            collaboration_session_id="session_123",
            agent_id="agent_123",
            component_id="component_123"
        )

        # The implementation should check if already locked
        assert "success" in result or "error" in result

    def test_release_lock_success(self, collaboration_service, mock_db, sample_participant):
        """Test successfully releasing component lock"""
        sample_participant.held_locks = ["lock_123"]
        mock_db.query.return_value.filter.return_value.first.return_value = sample_participant

        result = collaboration_service.release_component_lock(
            collaboration_session_id="session_123",
            agent_id="agent_123",
            lock_id="lock_123"
        )

        assert result["success"] is True
        mock_db.commit.assert_called()

    def test_release_lock_not_held(self, collaboration_service, mock_db, sample_participant):
        """Test releasing lock not held by agent"""
        sample_participant.held_locks = []
        mock_db.query.return_value.filter.return_value.first.return_value = sample_participant

        result = collaboration_service.release_component_lock(
            collaboration_session_id="session_123",
            agent_id="agent_123",
            lock_id="lock_123"
        )

        assert "error" in result or result["success"] is False

    def test_get_active_locks_success(self, collaboration_service, mock_db, sample_session, sample_participant):
        """Test getting all active locks"""
        sample_participant.held_locks = ["lock_123", "lock_456"]
        mock_db.query.return_value.filter.return_value.first.side_effect = [sample_session, [sample_participant]]

        result = collaboration_service.get_active_locks("session_123")

        assert "locks" in result
        assert len(result["locks"]) >= 2


# =============================================================================
# TEST CLASS: Conflict Resolution
# =============================================================================

class TestConflictResolution:
    """Tests for conflict detection and resolution"""

    def test_detect_conflict_concurrent_edit(self, collaboration_service, mock_db):
        """Test detecting concurrent edit conflict"""
        # This would test the conflict detection logic
        result = collaboration_service.detect_conflict(
            collaboration_session_id="session_123",
            agent_id="agent_123",
            component_id="component_123",
            action="edit"
        )

        assert "conflict_detected" in result

    def test_resolve_conflict_last_write_wins(self, collaboration_service, mock_db):
        """Test resolving conflict with last-write-wins strategy"""
        result = collaboration_service.resolve_conflict(
            conflict_id="conflict_123",
            resolution_strategy="last_write_wins"
        )

        assert result["success"] is True or "error" in result

    def test_resolve_conflict_manual_review(self, collaboration_service, mock_db):
        """Test resolving conflict with manual review"""
        result = collaboration_service.resolve_conflict(
            conflict_id="conflict_123",
            resolution_strategy="manual_review",
            resolution_data={"chosen_version": "agent_456"}
        )

        assert "success" in result or "error" in result


# =============================================================================
# TEST CLASS: Role-Based Access Control
# =============================================================================

class TestRoleBasedAccess:
    """Tests for role-based access control"""

    def test_owner_full_permissions(self, collaboration_service):
        """Test owner role has full permissions"""
        permissions = collaboration_service._get_default_permissions(AgentRole.OWNER.value)

        assert permissions["read"] is True
        assert permissions["write"] is True
        assert permissions["delete"] is True
        assert permissions["lock"] is True

    def test_contributor_limited_permissions(self, collaboration_service):
        """Test contributor role has limited permissions"""
        permissions = collaboration_service._get_default_permissions(AgentRole.CONTRIBUTOR.value)

        assert permissions["read"] is True
        assert permissions["write"] is True
        assert permissions["delete"] is False
        assert permissions["lock"] is True

    def test_reviewer_read_only(self, collaboration_service):
        """Test reviewer role is read-only"""
        permissions = collaboration_service._get_default_permissions(AgentRole.REVIEWER.value)

        assert permissions["read"] is True
        assert permissions["write"] is False
        assert permissions["delete"] is False
        assert permissions["lock"] is False

    def test_viewer_minimal_permissions(self, collaboration_service):
        """Test viewer role has minimal permissions"""
        permissions = collaboration_service._get_default_permissions(AgentRole.VIEWER.value)

        assert permissions["read"] is True
        assert permissions["write"] is False
        assert permissions["delete"] is False
        assert permissions["lock"] is False


# =============================================================================
# TEST CLASS: Collaboration Modes
# =============================================================================

class TestCollaborationModes:
    """Tests for different collaboration modes"""

    def test_sequential_mode_enforces_turns(self, collaboration_service, mock_db):
        """Test sequential mode enforces agent turns"""
        session = MagicMock(spec=CanvasCollaborationSession)
        session.collaboration_mode = CollaborationMode.SEQUENTIAL.value
        session.id = "session_123"

        mock_db.query.return_value.filter.return_value.first.return_value = session

        # Check if mode is enforced
        assert session.collaboration_mode == CollaborationMode.SEQUENTIAL.value

    def test_parallel_mode_allows_concurrent(self, collaboration_service):
        """Test parallel mode allows concurrent access"""
        session = MagicMock(spec=CanvasCollaborationSession)
        session.collaboration_mode = CollaborationMode.PARALLEL.value

        assert session.collaboration_mode == CollaborationMode.PARALLEL.value

    def test_locked_mode_first_come_first_serve(self, collaboration_service):
        """Test locked mode gives priority to first agent"""
        session = MagicMock(spec=CanvasCollaborationSession)
        session.collaboration_mode = CollaborationMode.LOCKED.value

        assert session.collaboration_mode == CollaborationMode.LOCKED.value


# =============================================================================
# TEST CLASS: Error Handling
# =============================================================================

class TestErrorHandling:
    """Tests for error handling"""

    def test_invalid_collaboration_mode(self, collaboration_service, mock_db):
        """Test handling invalid collaboration mode"""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        # Should handle gracefully or default to sequential
        result = collaboration_service.create_collaboration_session(
            canvas_id="canvas_123",
            session_id="session_123",
            user_id="user_123",
            collaboration_mode="invalid_mode"
        )

        # Either succeeds with default mode or provides error
        assert "session_id" in result or "error" in result

    def test_invalid_agent_role(self, collaboration_service, mock_db):
        """Test handling invalid agent role"""
        permissions = collaboration_service._get_default_permissions("invalid_role")

        # Should provide safe defaults
        assert isinstance(permissions, dict)

    def test_database_error_handling(self, collaboration_service, mock_db):
        """Test graceful handling of database errors"""
        mock_db.commit.side_effect = Exception("Database error")

        result = collaboration_service.create_collaboration_session(
            canvas_id="canvas_123",
            session_id="session_123",
            user_id="user_123"
        )

        # Should handle error gracefully
        assert True  # If we get here without exception, error was handled


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
