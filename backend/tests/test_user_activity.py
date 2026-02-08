"""
Tests for User Activity Service

Test user activity tracking, state transitions, and supervision availability.
"""

import pytest
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from core.database import get_db
from core.models import (
    User,
    UserActivity,
    UserActivitySession,
    UserState,
)
from core.user_activity_service import UserActivityService


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def db():
    """Get database session."""
    db = next(get_db())
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def test_user(db: Session):
    """Create test user."""
    user = User(
        email="test@example.com",
        first_name="Test",
        last_name="User",
        status="ACTIVE",
        specialty="Accountant"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def activity_service(db: Session):
    """Get UserActivityService instance."""
    return UserActivityService(db)


# ============================================================================
# Heartbeat Recording Tests
# ============================================================================

def test_record_heartbeat_creates_activity_and_session(
    activity_service: UserActivityService,
    test_user: User
):
    """Test that recording heartbeat creates activity and session records."""
    import asyncio

    async def run_test():
        activity = asyncio.run(activity_service.record_heartbeat(
            user_id=test_user.id,
            session_token="test_session_token",
            session_type="web",
            user_agent="Mozilla/5.0",
            ip_address="192.168.1.1"
        ))

        assert activity is not None
        assert activity.user_id == test_user.id
        assert activity.state == UserState.online
        assert activity.manual_override is False

        # Check session was created
        session = activity_service.db.query(UserActivitySession).filter(
            UserActivitySession.session_token == "test_session_token"
        ).first()

        assert session is not None
        assert session.user_id == test_user.id
        assert session.session_type == "web"
        assert session.user_agent == "Mozilla/5.0"
        assert session.ip_address == "192.168.1.1"
        assert session.terminated_at is None

    run_test()


def test_record_heartbeat_updates_existing_session(
    activity_service: UserActivityService,
    test_user: User,
    db: Session
):
    """Test that recording heartbeat updates existing session."""
    import asyncio

    # Create initial session
    activity = asyncio.run(activity_service.record_heartbeat(
        user_id=test_user.id,
        session_token="existing_token",
        session_type="web"
    ))

    original_heartbeat = activity.last_activity_at

    # Wait a moment and record another heartbeat
    import time
    time.sleep(0.1)

    updated_activity = asyncio.run(activity_service.record_heartbeat(
        user_id=test_user.id,
        session_token="existing_token",
        session_type="web"
    ))

    # Should update the same session
    session = db.query(UserActivitySession).filter(
        UserActivitySession.session_token == "existing_token"
    ).first()

    assert session is not None
    assert session.last_heartbeat > original_heartbeat


def test_multiple_sessions_keep_user_online(
    activity_service: UserActivityService,
    test_user: User
):
    """Test that multiple sessions keep user online."""
    import asyncio

    # Create two sessions
    asyncio.run(activity_service.record_heartbeat(
        user_id=test_user.id,
        session_token="session1",
        session_type="web"
    ))

    asyncio.run(activity_service.record_heartbeat(
        user_id=test_user.id,
        session_token="session2",
        session_type="desktop"
    ))

    activity = db.query(UserActivity).filter(
        UserActivity.user_id == test_user.id
    ).first()

    assert activity.state == UserState.online

    # Check both sessions exist
    sessions = activity_service.db.query(UserActivitySession).filter(
        UserActivitySession.user_id == test_user.id,
        UserActivitySession.terminated_at.is_(None)
    ).all()

    assert len(sessions) == 2


# ============================================================================
# State Management Tests
# ============================================================================

def test_get_user_state_returns_offline_for_no_activity(
    activity_service: UserActivityService,
    test_user: User
):
    """Test that user without activity record is offline."""
    import asyncio

    state = asyncio.run(activity_service.get_user_state(test_user.id))

    assert state == UserState.offline


def test_get_user_state_returns_online_with_recent_heartbeat(
    activity_service: UserActivityService,
    test_user: User
):
    """Test that user with recent heartbeat is online."""
    import asyncio

    # Record heartbeat
    asyncio.run(activity_service.record_heartbeat(
        user_id=test_user.id,
        session_token="test_token"
    ))

    # Get state
    state = asyncio.run(activity_service.get_user_state(test_user.id))

    assert state == UserState.online


def test_should_supervise_returns_true_for_online_and_away(
    activity_service: UserActivityService,
    db: Session
):
    """Test that should_supervise returns True for online and away states."""
    # Test online
    online_activity = UserActivity(
        user_id="test_user",
        state=UserState.online
    )
    assert activity_service.should_supervise(online_activity) is True

    # Test away
    away_activity = UserActivity(
        user_id="test_user",
        state=UserState.away
    )
    assert activity_service.should_supervise(away_activity) is True

    # Test offline
    offline_activity = UserActivity(
        user_id="test_user",
        state=UserState.offline
    )
    assert activity_service.should_supervise(offline_activity) is False


# ============================================================================
# Manual Override Tests
# ============================================================================

def test_set_manual_override_sets_state(
    activity_service: UserActivityService,
    test_user: User
):
    """Test setting manual override."""
    import asyncio

    activity = asyncio.run(activity_service.set_manual_override(
        user_id=test_user.id,
        state=UserState.away
    ))

    assert activity.state == UserState.away
    assert activity.manual_override is True
    assert activity.manual_override_expires_at is None


def test_set_manual_override_with_expiry(
    activity_service: UserActivityService,
    test_user: User
):
    """Test setting manual override with expiry."""
    import asyncio

    expires_at = datetime.utcnow() + timedelta(hours=1)

    activity = asyncio.run(activity_service.set_manual_override(
        user_id=test_user.id,
        state=UserState.offline,
        expires_at=expires_at
    ))

    assert activity.state == UserState.offline
    assert activity.manual_override is True
    assert activity.manual_override_expires_at is not None


def test_clear_manual_override_returns_automatic_tracking(
    activity_service: UserActivityService,
    test_user: User
):
    """Test clearing manual override."""
    import asyncio

    # Set manual override
    asyncio.run(activity_service.set_manual_override(
        user_id=test_user.id,
        state=UserState.offline
    ))

    # Record heartbeat (should not update state due to override)
    asyncio.run(activity_service.record_heartbeat(
        user_id=test_user.id,
        session_token="test_token"
    ))

    activity = activity_service.db.query(UserActivity).filter(
        UserActivity.user_id == test_user.id
    ).first()

    assert activity.state == UserState.offline  # Still offline due to override

    # Clear override
    asyncio.run(activity_service.clear_manual_override(test_user.id))

    # State should recalculate based on actual activity
    assert activity.manual_override is False


# ============================================================================
# Available Supervisors Tests
# ============================================================================

def test_get_available_supervisors_returns_online_and_away_users(
    activity_service: UserActivityService,
    test_user: User,
    db: Session
):
    """Test that available supervisors includes online and away users."""
    import asyncio

    # Set user as online
    asyncio.run(activity_service.set_manual_override(
        user_id=test_user.id,
        state=UserState.online
    ))

    supervisors = asyncio.run(activity_service.get_available_supervisors())

    assert len(supervisors) > 0
    assert any(s["user_id"] == test_user.id for s in supervisors)
    assert all(s["state"] in ["online", "away"] for s in supervisors)


def test_get_available_supervisors_filters_by_category(
    activity_service: UserActivityService,
    test_user: User
):
    """Test filtering available supervisors by category."""
    import asyncio

    # Set user as online
    asyncio.run(activity_service.set_manual_override(
        user_id=test_user.id,
        state=UserState.online
    ))

    supervisors = asyncio.run(activity_service.get_available_supervisors(
        category="Accountant"
    ))

    assert test_user.specialty == "Accountant"
    assert any(s["user_id"] == test_user.id for s in supervisors)


# ============================================================================
# Session Management Tests
# ============================================================================

def test_terminate_session_marks_as_terminated(
    activity_service: UserActivityService,
    test_user: User
):
    """Test terminating a session."""
    import asyncio

    # Create session
    asyncio.run(activity_service.record_heartbeat(
        user_id=test_user.id,
        session_token="terminate_test"
    ))

    # Terminate session
    success = asyncio.run(activity_service.terminate_session("terminate_test"))

    assert success is True

    # Check session is terminated
    session = activity_service.db.query(UserActivitySession).filter(
        UserActivitySession.session_token == "terminate_test"
    ).first()

    assert session is not None
    assert session.terminated_at is not None


def test_terminate_nonexistent_session_returns_false(
    activity_service: UserActivityService
):
    """Test terminating non-existent session returns False."""
    import asyncio

    success = asyncio.run(activity_service.terminate_session("nonexistent_token"))

    assert success is False


def test_get_active_sessions_returns_only_active_sessions(
    activity_service: UserActivityService,
    test_user: User
):
    """Test getting active sessions excludes terminated ones."""
    import asyncio

    # Create two sessions
    asyncio.run(activity_service.record_heartbeat(
        user_id=test_user.id,
        session_token="active_session"
    ))

    asyncio.run(activity_service.record_heartbeat(
        user_id=test_user.id,
        session_token="terminated_session"
    ))

    # Terminate one session
    asyncio.run(activity_service.terminate_session("terminated_session"))

    # Get active sessions
    sessions = asyncio.run(activity_service.get_active_sessions(test_user.id))

    assert len(sessions) == 1
    assert sessions[0].session_token == "active_session"


# ============================================================================
# State Transition Tests
# ============================================================================

def test_transition_state_batch_processes_multiple_users(
    activity_service: UserActivityService,
    db: Session
):
    """Test batch processing of state transitions."""
    import asyncio

    # Create multiple users with stale activity
    users = []
    for i in range(3):
        user = User(
            email=f"test{i}@example.com",
            status="ACTIVE"
        )
        db.add(user)
        users.append(user)

    db.commit()

    # Create activities with old timestamps
    for user in users:
        activity = UserActivity(
            user_id=user.id,
            state=UserState.online,
            last_activity_at=datetime.utcnow() - timedelta(minutes=10)
        )
        db.add(activity)

    db.commit()

    # Process state transitions
    transitions = asyncio.run(activity_service.transition_state_batch(limit=10))

    assert transitions["total_processed"] > 0


def test_cleanup_stale_sessions_removes_old_sessions(
    activity_service: UserActivityService,
    test_user: User
):
    """Test cleanup of stale sessions."""
    import asyncio

    # Create session with old heartbeat
    asyncio.run(activity_service.record_heartbeat(
        user_id=test_user.id,
        session_token="stale_session"
    ))

    # Manually set heartbeat to old time
    session = activity_service.db.query(UserActivitySession).filter(
        UserActivitySession.session_token == "stale_session"
    ).first()

    session.last_heartbeat = datetime.utcnow() - timedelta(hours=2)
    activity_service.db.commit()

    # Run cleanup
    count = asyncio.run(activity_service.cleanup_stale_sessions(limit=10))

    assert count > 0

    # Check session is terminated
    activity_service.db.refresh(session)
    assert session.terminated_at is not None
