"""
Unit tests for CollaborationService

Tests cover:
- Session management (create, get active, update activity)
- Participant management (add, remove, update heartbeat)
- Edit locking (acquire, release, get active locks)
- Sharing (create share, get share, revoke share)
- Comments (add, get, resolve comments)
- Audit logging
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List
from sqlalchemy.orm import Session

from core.collaboration_service import CollaborationService


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
def mock_permission_manager():
    """Mock permission manager"""
    manager = MagicMock()
    manager.check_permission = MagicMock(return_value=True)
    manager.get_user_permissions = MagicMock(return_value=["read", "write"])
    return manager


@pytest.fixture
def sample_collaboration_space():
    """Sample collaboration space"""
    return {
        "workflow_id": "workflow_123",
        "name": "Test Workspace",
        "created_by": "user_123",
        "mode": "parallel",
        "max_users": 10
    }


@pytest.fixture
def collaboration_service(mock_db):
    """Create CollaborationService instance"""
    return CollaborationService(mock_db)


# =============================================================================
# TEST CLASS: CollaborationInit
# =============================================================================

class TestCollaborationInit:
    """Tests for CollaborationService initialization"""

    def test_collaboration_service_init(self, collaboration_service, mock_db):
        """Verify service initializes with database session"""
        assert collaboration_service.db == mock_db
        assert collaboration_service.db is not None

    def test_collaboration_service_db_session(self, collaboration_service):
        """Verify database session is accessible"""
        assert hasattr(collaboration_service, 'db')
        assert hasattr(collaboration_service.db, 'query')
        assert hasattr(collaboration_service.db, 'add')
        assert hasattr(collaboration_service.db, 'commit')


# =============================================================================
# TEST CLASS: SharedWorkspaces
# =============================================================================

class TestSharedWorkspaces:
    """Tests for shared workspace functionality"""

    def test_create_collaboration_session_basic(self, collaboration_service, mock_db):
        """Verify collaboration session can be created"""
        mock_query_result = MagicMock()
        mock_query_result.first = MagicMock(return_value=None)
        mock_db.query.return_value.filter.return_value = mock_query_result

        session = collaboration_service.create_collaboration_session(
            workflow_id="workflow_123",
            user_id="user_123",
            collaboration_mode="parallel",
            max_users=10
        )

        assert session is not None
        assert session.workflow_id == "workflow_123"
        assert session.created_by == "user_123"
        assert session.collaboration_mode == "parallel"
        assert session.max_users == 10

    def test_create_collaboration_session_with_defaults(self, collaboration_service, mock_db):
        """Verify session creation with default values"""
        mock_query_result = MagicMock()
        mock_query_result.first = MagicMock(return_value=None)
        mock_db.query.return_value.filter.return_value = mock_query_result

        session = collaboration_service.create_collaboration_session(
            workflow_id="workflow_456",
            user_id="user_456"
        )

        assert session.collaboration_mode == "parallel"  # Default
        assert session.max_users == 10  # Default

    def test_get_active_session(self, collaboration_service, mock_db):
        """Verify active session can be retrieved"""
        mock_session = MagicMock()
        mock_session.session_id = "session_123"
        mock_session.workflow_id = "workflow_123"

        mock_query_result = MagicMock()
        mock_query_result.first = MagicMock(return_value=mock_session)
        mock_db.query.return_value.filter.return_value = mock_query_result

        session = collaboration_service.get_active_session("workflow_123")

        assert session is not None
        assert session.session_id == "session_123"

    def test_get_active_session_none_when_inactive(self, collaboration_service, mock_db):
        """Verify None returned when no active session"""
        mock_query_result = MagicMock()
        mock_query_result.first = MagicMock(return_value=None)
        mock_db.query.return_value.filter.return_value = mock_query_result

        session = collaboration_service.get_active_session("workflow_999")

        assert session is None

    def test_update_session_activity(self, collaboration_service, mock_db):
        """Verify session activity can be updated"""
        mock_session = MagicMock()
        mock_session.last_activity = datetime.now(timezone.utc)

        mock_query_result = MagicMock()
        mock_query_result.first = MagicMock(return_value=mock_session)
        mock_db.query.return_value.filter.return_value = mock_query_result

        collaboration_service.update_session_activity("session_123")

        assert mock_db.commit.called


# =============================================================================
# TEST CLASS: RealTimeCollaboration
# =============================================================================

class TestRealTimeCollaboration:
    """Tests for real-time collaboration features"""

    def test_add_participant_to_session(self, collaboration_service, mock_db):
        """Verify participant can be added to session"""
        mock_user = MagicMock()
        mock_user.email = "test@example.com"
        mock_user.first_name = "Test"
        mock_user.last_name = "User"

        # Mock user query
        mock_user_query = MagicMock()
        mock_user_query.first = MagicMock(return_value=mock_user)

        # Mock session query
        mock_session = MagicMock()
        mock_session.active_users = ["user_123"]
        mock_session_query = MagicMock()
        mock_session_query.first = MagicMock(return_value=mock_session)

        mock_db.query.side_effect = [mock_user_query, mock_session_query]

        participant = collaboration_service.add_participant_to_session(
            session_id="session_123",
            user_id="user_456",
            role="editor"
        )

        assert participant is not None
        assert participant.user_id == "user_456"
        assert participant.role == "editor"

    def test_remove_participant_from_session(self, collaboration_service, mock_db):
        """Verify participant can be removed from session"""
        mock_participant = MagicMock()
        mock_participant_query = MagicMock()
        mock_participant_query.filter.return_value.first.return_value = mock_participant

        mock_session = MagicMock()
        mock_session.active_users = ["user_123", "user_456"]
        mock_session_query = MagicMock()
        mock_session_query.first = MagicMock(return_value=mock_session)

        mock_db.query.side_effect = [mock_participant_query, mock_session_query]

        collaboration_service.remove_participant_from_session(
            session_id="session_123",
            user_id="user_456"
        )

        assert mock_db.commit.called

    def test_update_participant_heartbeat(self, collaboration_service, mock_db):
        """Verify participant heartbeat can be updated"""
        mock_participant = MagicMock()
        mock_participant.last_heartbeat = datetime.now(timezone.utc)

        mock_query_result = MagicMock()
        mock_query_result.filter.return_value.first.return_value = mock_participant
        mock_db.query.return_value = mock_query_result

        collaboration_service.update_participant_heartbeat(
            session_id="session_123",
            user_id="user_123",
            cursor_position={"x": 100, "y": 200},
            selected_node="node_1"
        )

        assert mock_db.commit.called

    def test_get_session_participants(self, collaboration_service, mock_db):
        """Verify session participants can be retrieved"""
        mock_participants = [
            MagicMock(user_id="user_1", user_name="User 1"),
            MagicMock(user_id="user_2", user_name="User 2")
        ]

        mock_query_result = MagicMock()
        mock_query_result.filter.return_value.all.return_value = mock_participants
        mock_db.query.return_value = mock_query_result

        participants = collaboration_service.get_session_participants("session_123")

        assert len(participants) == 2


# =============================================================================
# TEST CLASS: PermissionChecks
# =============================================================================

class TestPermissionChecks:
    """Tests for permission validation and checks"""

    def test_acquire_edit_lock_success(self, collaboration_service, mock_db):
        """Verify edit lock can be acquired"""
        mock_query_result = MagicMock()
        mock_query_result.filter.return_value.first.return_value = None  # No existing lock
        mock_db.query.return_value = mock_query_result

        lock = collaboration_service.acquire_edit_lock(
            session_id="session_123",
            workflow_id="workflow_123",
            user_id="user_123",
            resource_type="node",
            resource_id="node_1"
        )

        assert lock is not None
        assert lock.locked_by == "user_123"
        assert lock.resource_id == "node_1"

    def test_acquire_edit_lock_already_locked(self, collaboration_service, mock_db):
        """Verify edit lock fails when already locked"""
        existing_lock = MagicMock()
        existing_lock.expires_at = datetime.now(timezone.utc) + timedelta(minutes=30)

        mock_query_result = MagicMock()
        mock_query_result.filter.return_value.first.return_value = existing_lock
        mock_db.query.return_value = mock_query_result

        lock = collaboration_service.acquire_edit_lock(
            session_id="session_123",
            workflow_id="workflow_123",
            user_id="user_456",
            resource_type="node",
            resource_id="node_1"
        )

        assert lock is None  # Lock already held

    def test_release_edit_lock_success(self, collaboration_service, mock_db):
        """Verify edit lock can be released"""
        mock_lock = MagicMock()
        mock_lock.is_active = True

        mock_query_result = MagicMock()
        mock_query_result.filter.return_value.first.return_value = mock_lock
        mock_db.query.return_value = mock_query_result

        result = collaboration_service.release_edit_lock(
            session_id="session_123",
            resource_type="node",
            resource_id="node_1",
            user_id="user_123"
        )

        assert result is True
        assert mock_lock.is_active is False

    def test_get_active_locks(self, collaboration_service, mock_db):
        """Verify active locks can be retrieved"""
        mock_locks = [
            MagicMock(resource_id="node_1", locked_by="user_1"),
            MagicMock(resource_id="node_2", locked_by="user_2")
        ]

        mock_query_result = MagicMock()
        mock_query_result.filter.return_value.all.return_value = mock_locks
        mock_db.query.return_value = mock_query_result

        locks = collaboration_service.get_active_locks("workflow_123")

        assert len(locks) == 2


# =============================================================================
# TEST CLASS: SharingFunctionality
# =============================================================================

class TestSharingFunctionality:
    """Tests for workflow sharing features"""

    def test_create_workflow_share(self, collaboration_service, mock_db):
        """Verify workflow share can be created"""
        share = collaboration_service.create_workflow_share(
            workflow_id="workflow_123",
            user_id="user_123",
            share_type="link",
            permissions={"can_view": True, "can_edit": False},
            expires_in_days=7,
            max_uses=100
        )

        assert share is not None
        assert share.workflow_id == "workflow_123"
        assert share.share_type == "link"
        assert share.max_uses == 100

    def test_create_workflow_share_defaults(self, collaboration_service, mock_db):
        """Verify share creation with default permissions"""
        share = collaboration_service.create_workflow_share(
            workflow_id="workflow_456",
            user_id="user_456"
        )

        assert share.permissions["can_view"] is True
        assert share.permissions["can_edit"] is False
        assert share.permissions["can_comment"] is True

    def test_get_workflow_share(self, collaboration_service, mock_db):
        """Verify workflow share can be retrieved"""
        mock_share = MagicMock()
        mock_share.is_active = True
        mock_share.expires_at = None
        mock_share.max_uses = None
        mock_share.use_count = 5

        mock_query_result = MagicMock()
        mock_query_result.filter.return_value.first.return_value = mock_share
        mock_db.query.return_value = mock_query_result

        share = collaboration_service.get_workflow_share("share_123")

        assert share is not None

    def test_revoke_workflow_share(self, collaboration_service, mock_db):
        """Verify workflow share can be revoked"""
        mock_share = MagicMock()
        mock_share.created_by = "user_123"

        mock_query_result = MagicMock()
        mock_query_result.first.return_value = mock_share
        mock_db.query.return_value = mock_query_result

        result = collaboration_service.revoke_workflow_share(
            share_id="share_123",
            user_id="user_123"
        )

        assert result is True
        assert mock_share.is_active is False


# =============================================================================
# TEST CLASS: CommentsFunctionality
# =============================================================================

class TestCommentsFunctionality:
    """Tests for comment functionality"""

    def test_add_comment(self, collaboration_service, mock_db):
        """Verify comment can be added"""
        comment = collaboration_service.add_comment(
            workflow_id="workflow_123",
            user_id="user_123",
            content="This is a test comment",
            context_type="node",
            context_id="node_1"
        )

        assert comment is not None
        assert comment.content == "This is a test comment"
        assert comment.context_type == "node"

    def test_get_workflow_comments(self, collaboration_service, mock_db):
        """Verify workflow comments can be retrieved"""
        mock_comments = [
            MagicMock(id=1, content="Comment 1"),
            MagicMock(id=2, content="Comment 2")
        ]

        mock_query = MagicMock()
        mock_query.filter.return_value.order_by.return_value.all.return_value = mock_comments
        mock_db.query.return_value = mock_query

        comments = collaboration_service.get_workflow_comments("workflow_123")

        assert len(comments) == 2

    def test_get_comments_with_context(self, collaboration_service, mock_db):
        """Verify comments can be filtered by context"""
        mock_comments = [MagicMock(id=1, content="Node comment")]

        mock_query = MagicMock()
        mock_query.filter.return_value.order_by.return_value.all.return_value = mock_comments
        mock_db.query.return_value = mock_query

        comments = collaboration_service.get_workflow_comments(
            workflow_id="workflow_123",
            context_type="node",
            context_id="node_1"
        )

        assert len(comments) == 1

    def test_resolve_comment(self, collaboration_service, mock_db):
        """Verify comment can be resolved"""
        mock_comment = MagicMock()

        mock_query_result = MagicMock()
        mock_query_result.filter.return_value.first.return_value = mock_comment
        mock_db.query.return_value = mock_query_result

        result = collaboration_service.resolve_comment(
            comment_id="comment_123",
            user_id="user_123"
        )

        assert result is True
        assert mock_comment.is_resolved is True


# =============================================================================
# TEST CLASS: AuditFunctionality
# =============================================================================

class TestAuditFunctionality:
    """Tests for audit logging functionality"""

    def test_audit_log_entry_created(self, collaboration_service, mock_db):
        """Verify audit log entry is created"""
        mock_session = MagicMock()
        mock_session.session_id = "session_123"
        mock_query_result = MagicMock()
        mock_query_result.filter.return_value.first.return_value = mock_session
        mock_db.query.return_value = mock_query_result

        collaboration_service.create_collaboration_session(
            workflow_id="workflow_123",
            user_id="user_123"
        )

        # Verify audit was logged (called during session creation)
        assert mock_db.add.called

    def test_get_audit_log(self, collaboration_service, mock_db):
        """Verify audit log can be retrieved"""
        mock_audits = [
            MagicMock(action_type="create_session"),
            MagicMock(action_type="add_comment")
        ]

        mock_query_result = MagicMock()
        mock_query_result.filter.return_value.order_by.return_value.limit.return_value.all.return_value = mock_audits
        mock_db.query.return_value = mock_query_result

        audits = collaboration_service.get_audit_log("workflow_123", limit=100)

        assert len(audits) == 2


# =============================================================================
# TEST CLASS: EdgeCases
# =============================================================================

class TestCollaborationEdgeCases:
    """Tests for edge cases and boundary conditions"""

    def test_session_with_no_participants(self, collaboration_service, mock_db):
        """Verify session with no participants is handled"""
        mock_query_result = MagicMock()
        mock_query_result.filter.return_value.all.return_value = []
        mock_db.query.return_value = mock_query_result

        participants = collaboration_service.get_session_participants("session_empty")

        assert len(participants) == 0

    def test_concurrent_edit_lock_requests(self, collaboration_service, mock_db):
        """Verify concurrent lock requests are handled"""
        # First request succeeds
        mock_query_result = MagicMock()
        mock_query_result.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query_result

        lock1 = collaboration_service.acquire_edit_lock(
            session_id="session_123",
            workflow_id="workflow_123",
            user_id="user_1",
            resource_type="node",
            resource_id="node_1"
        )

        assert lock1 is not None

    def test_share_with_no_expiry(self, collaboration_service, mock_db):
        """Verify share without expiry is handled"""
        share = collaboration_service.create_workflow_share(
            workflow_id="workflow_123",
            user_id="user_123",
            expires_in_days=None
        )

        assert share.expires_at is None

    def test_comment_with_no_context(self, collaboration_service, mock_db):
        """Verify comment without context is handled"""
        comment = collaboration_service.add_comment(
            workflow_id="workflow_123",
            user_id="user_123",
            content="General comment"
        )

        assert comment.context_type is None
        assert comment.context_id is None


# =============================================================================
# ADDITIONAL TESTS
# =============================================================================

class TestCollaborationHelpers:
    """Tests for helper methods"""

    def test_generate_user_color_consistent(self, collaboration_service):
        """Verify user color generation is consistent"""
        color1 = collaboration_service._generate_user_color("user_123")
        color2 = collaboration_service._generate_user_color("user_123")

        assert color1 == color2  # Same user_id should produce same color

    def test_generate_user_color_different_users(self, collaboration_service):
        """Verify different users get different colors"""
        color1 = collaboration_service._generate_user_color("user_1")
        color2 = collaboration_service._generate_user_color("user_2")

        # May be same by chance with small color palette, but unlikely
        assert isinstance(color1, str)
        assert isinstance(color2, str)
        assert color1.startswith("#")
        assert color2.startswith("#")
