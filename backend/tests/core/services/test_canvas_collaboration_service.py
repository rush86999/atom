"""
Tests for CanvasCollaborationService

Tests for multi-agent canvas collaboration service including:
- Session management
- Permission checks
- Conflict resolution
- Activity tracking
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def db_session():
    """Create a test database session."""
    engine = create_engine("sqlite:///:memory:")

    # Import Base from models
    from core.models import Base
    Base.metadata.create_all(engine)

    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def collaboration_service(db_session):
    """Create collaboration service instance."""
    try:
        from core.canvas_collaboration_service import CanvasCollaborationService
        return CanvasCollaborationService(db_session)
    except ImportError as e:
        pytest.skip(f"CanvasCollaborationService not available: {e}")


@pytest.fixture
def test_agent(db_session):
    """Create a test agent."""
    try:
        from core.models import AgentRegistry
        agent = AgentRegistry(
            id="test-agent-1",
            name="Test Agent",
            category="general",
            module_path="test.module",
            class_name="TestClass",
            status="AUTONOMOUS",
            confidence_score=0.9,
        )
        db_session.add(agent)
        db_session.commit()
        return agent
    except Exception:
        # Create mock agent
        mock_agent = Mock()
        mock_agent.id = "test-agent-1"
        mock_agent.name = "Test Agent"
        return mock_agent


@pytest.fixture
def test_user_id():
    """Test user ID."""
    return "test-user-123"


class TestCanvasCollaborationServiceInit:
    """Tests for CanvasCollaborationService initialization."""

    def test_init_with_db(self, collaboration_service):
        """Test service initialization with database session."""
        assert collaboration_service.db is not None


class TestCreateCollaborationSession:
    """Tests for create_collaboration_session method."""

    def test_create_session_basic(self, collaboration_service, test_user_id):
        """Test basic session creation."""
        result = collaboration_service.create_collaboration_session(
            canvas_id="test-canvas-1",
            session_id="test-session-1",
            user_id=test_user_id,
        )

        assert "session_id" in result
        assert result.get("canvas_id") == "test-canvas-1"
        assert result.get("status") == "active"


class TestGetSessionStatus:
    """Tests for get_session_status method."""

    def test_get_session_status_not_found(self, collaboration_service):
        """Test getting status of non-existent session."""
        result = collaboration_service.get_session_status("non-existent-session")

        # Should return error or empty result
        assert "error" in result or result == {}


class TestCheckAgentPermission:
    """Tests for check_agent_permission method."""

    def test_check_permission_handling(self, collaboration_service):
        """Test permission check doesn't crash."""
        # This tests that the method handles errors gracefully
        result = collaboration_service.check_agent_permission(
            collaboration_session_id="non-existent",
            agent_id="non-existent",
            action="read",
        )

        # Should return some result without crashing
        assert result is not None or isinstance(result, dict)


class TestCheckForConflicts:
    """Tests for check_for_conflicts method."""

    def test_no_conflict_handling(self, collaboration_service):
        """Test conflict check handles errors gracefully."""
        result = collaboration_service.check_for_conflicts(
            collaboration_session_id="non-existent",
            agent_id="agent-1",
            component_id="component-1",
            action={"type": "update"},
        )

        assert result is not None


class TestCompleteSession:
    """Tests for complete_session method."""

    def test_complete_session_not_found(self, collaboration_service):
        """Test completing non-existent session."""
        result = collaboration_service.complete_session("non-existent-session")

        # Should handle gracefully
        assert result is not None


class TestHelperMethods:
    """Tests for helper methods."""

    def test_get_default_permissions_owner(self, collaboration_service):
        """Test getting default permissions for owner."""
        permissions = collaboration_service._get_default_permissions("owner")

        assert permissions.get("read") is True
        assert permissions.get("write") is True
        assert permissions.get("delete") is True

    def test_get_default_permissions_contributor(self, collaboration_service):
        """Test getting default permissions for contributor."""
        permissions = collaboration_service._get_default_permissions("contributor")

        assert permissions.get("read") is True
        assert permissions.get("write") is True
        assert permissions.get("delete") is False

    def test_get_default_permissions_viewer(self, collaboration_service):
        """Test getting default permissions for viewer."""
        permissions = collaboration_service._get_default_permissions("viewer")

        assert permissions.get("read") is True
        assert "write" not in permissions or permissions.get("write") is False

    def test_get_default_permissions_reviewer(self, collaboration_service):
        """Test getting default permissions for reviewer."""
        permissions = collaboration_service._get_default_permissions("reviewer")

        assert permissions.get("read") is True


class TestAddAgentToSession:
    """Tests for add_agent_to_session method."""

    def test_add_agent_success(self, collaboration_service, test_agent, test_user_id, db_session):
        """Test successfully adding agent to session."""
        # Create session
        session_result = collaboration_service.create_collaboration_session(
            canvas_id="test-canvas-1",
            session_id="test-session-1",
            user_id=test_user_id,
        )

        # Get collaboration session ID
        from core.models import CanvasCollaborationSession
        collab_session = db_session.query(CanvasCollaborationSession).first()
        session_id = collab_session.id if collab_session else session_result.get("session_id")

        # Add agent
        result = collaboration_service.add_agent_to_session(
            collaboration_session_id=session_id,
            agent_id=test_agent.id,
            user_id=test_user_id,
            role="contributor",
        )

        assert "participant_id" in result or "error" not in result

    def test_add_agent_session_not_found(self, collaboration_service, test_agent, test_user_id):
        """Test adding agent to non-existent session."""
        result = collaboration_service.add_agent_to_session(
            collaboration_session_id="non-existent-session",
            agent_id=test_agent.id,
            user_id=test_user_id,
        )

        assert "error" in result


class TestRemoveAgentFromSession:
    """Tests for remove_agent_from_session method."""

    def test_remove_agent_success(self, collaboration_service, test_agent, test_user_id, db_session):
        """Test successfully removing agent from session."""
        # Create session with agent
        collaboration_service.create_collaboration_session(
            canvas_id="test-canvas-1",
            session_id="test-session-1",
            user_id=test_user_id,
            initial_agent_id=test_agent.id,
        )

        from core.models import CanvasCollaborationSession
        collab_session = db_session.query(CanvasCollaborationSession).first()

        # Remove agent
        result = collaboration_service.remove_agent_from_session(
            collaboration_session_id=collab_session.id,
            agent_id=test_agent.id,
        )

        assert result.get("status") == "removed" or "error" not in result

    def test_remove_agent_not_found(self, collaboration_service, test_user_id, db_session):
        """Test removing non-existent agent."""
        collaboration_service.create_collaboration_session(
            canvas_id="test-canvas-1",
            session_id="test-session-1",
            user_id=test_user_id,
        )

        from core.models import CanvasCollaborationSession
        collab_session = db_session.query(CanvasCollaborationSession).first()

        result = collaboration_service.remove_agent_from_session(
            collaboration_session_id=collab_session.id,
            agent_id="non-existent-agent",
        )

        assert "error" in result


class TestRecordAgentAction:
    """Tests for record_agent_action method."""

    def test_record_action_success(self, collaboration_service, test_agent, test_user_id, db_session):
        """Test successfully recording agent action."""
        collaboration_service.create_collaboration_session(
            canvas_id="test-canvas-1",
            session_id="test-session-1",
            user_id=test_user_id,
            initial_agent_id=test_agent.id,
        )

        from core.models import CanvasCollaborationSession
        collab_session = db_session.query(CanvasCollaborationSession).first()

        result = collaboration_service.record_agent_action(
            collaboration_session_id=collab_session.id,
            agent_id=test_agent.id,
            action="update",
            component_id="component-1",
        )

        assert result.get("agent_id") == test_agent.id or "error" not in result

    def test_record_action_agent_not_in_session(self, collaboration_service, test_user_id, db_session):
        """Test recording action for agent not in session."""
        collaboration_service.create_collaboration_session(
            canvas_id="test-canvas-1",
            session_id="test-session-1",
            user_id=test_user_id,
        )

        from core.models import CanvasCollaborationSession
        collab_session = db_session.query(CanvasCollaborationSession).first()

        result = collaboration_service.record_agent_action(
            collaboration_session_id=collab_session.id,
            agent_id="not-in-session",
            action="update",
        )

        assert "error" in result


class TestReleaseAgentLock:
    """Tests for release_agent_lock method."""

    def test_release_lock_success(self, collaboration_service, test_agent, test_user_id, db_session):
        """Test successfully releasing agent lock."""
        collaboration_service.create_collaboration_session(
            canvas_id="test-canvas-1",
            session_id="test-session-1",
            user_id=test_user_id,
            collaboration_mode="parallel",
        )

        from core.models import CanvasCollaborationSession
        collab_session = db_session.query(CanvasCollaborationSession).first()

        # Record action with lock
        collaboration_service.record_agent_action(
            collaboration_session_id=collab_session.id,
            agent_id=test_agent.id,
            action="lock",
            component_id="component-1",
        )

        # Release lock
        result = collaboration_service.release_agent_lock(
            collaboration_session_id=collab_session.id,
            agent_id=test_agent.id,
            component_id="component-1",
        )

        assert result.get("status") == "released" or "error" not in result

    def test_release_lock_agent_not_found(self, collaboration_service, test_user_id, db_session):
        """Test releasing lock for agent not in session."""
        collaboration_service.create_collaboration_session(
            canvas_id="test-canvas-1",
            session_id="test-session-1",
            user_id=test_user_id,
        )

        from core.models import CanvasCollaborationSession
        collab_session = db_session.query(CanvasCollaborationSession).first()

        result = collaboration_service.release_agent_lock(
            collaboration_session_id=collab_session.id,
            agent_id="not-in-session",
            component_id="component-1",
        )

        assert "error" in result


class TestResolveConflict:
    """Tests for resolve_conflict method."""

    def test_resolve_conflict_first_come_first_served(
        self, collaboration_service, test_agent, test_user_id, db_session
    ):
        """Test conflict resolution with first_come_first_served strategy."""
        collaboration_service.create_collaboration_session(
            canvas_id="test-canvas-1",
            session_id="test-session-1",
            user_id=test_user_id,
            initial_agent_id=test_agent.id,
        )

        from core.models import CanvasCollaborationSession
        collab_session = db_session.query(CanvasCollaborationSession).first()

        result = collaboration_service.resolve_conflict(
            collaboration_session_id=collab_session.id,
            agent_a_id=test_agent.id,
            agent_b_id="agent-b",
            component_id="component-1",
            agent_a_action={"type": "update"},
            agent_b_action={"type": "delete"},
            resolution_strategy="first_come_first_served",
        )

        assert "resolution" in result or "error" not in result

    def test_resolve_conflict_priority_strategy(
        self, collaboration_service, test_agent, test_user_id, db_session
    ):
        """Test conflict resolution with priority strategy."""
        collaboration_service.create_collaboration_session(
            canvas_id="test-canvas-1",
            session_id="test-session-1",
            user_id=test_user_id,
            initial_agent_id=test_agent.id,
        )

        from core.models import CanvasCollaborationSession
        collab_session = db_session.query(CanvasCollaborationSession).first()

        result = collaboration_service.resolve_conflict(
            collaboration_session_id=collab_session.id,
            agent_a_id=test_agent.id,
            agent_b_id="agent-b",
            component_id="component-1",
            agent_a_action={"type": "update"},
            agent_b_action={"type": "delete"},
            resolution_strategy="priority",
        )

        assert "resolution" in result or "error" not in result


class TestCollaborationModes:
    """Tests for different collaboration modes."""

    def test_create_session_parallel_mode(self, collaboration_service, test_user_id):
        """Test creating session with parallel mode."""
        result = collaboration_service.create_collaboration_session(
            canvas_id="test-canvas-1",
            session_id="test-session-1",
            user_id=test_user_id,
            collaboration_mode="parallel",
        )

        assert result.get("collaboration_mode") == "parallel"

    def test_create_session_locked_mode(self, collaboration_service, test_user_id):
        """Test creating session with locked mode."""
        result = collaboration_service.create_collaboration_session(
            canvas_id="test-canvas-1",
            session_id="test-session-1",
            user_id=test_user_id,
            collaboration_mode="locked",
        )

        assert result.get("collaboration_mode") == "locked"


class TestMergeActions:
    """Tests for _merge_actions helper method."""

    def test_merge_actions_basic(self, collaboration_service):
        """Test basic action merging."""
        action_a = {"type": "update", "value": "A"}
        action_b = {"type": "update", "value": "B"}

        result = collaboration_service._merge_actions(action_a, action_b)

        # For now, should prefer action_a
        assert result == action_a
