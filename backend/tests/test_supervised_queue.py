"""
Tests for Supervised Queue Service

Test queue management for SUPERVISED agents when users are unavailable.
"""

import pytest
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from core.database import get_db
from core.models import (
    AgentRegistry,
    AgentStatus,
    QueueStatus,
    SupervisedExecutionQueue,
    User,
    UserActivity,
    UserState,
)
from core.supervised_queue_service import SupervisedQueueService


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
        status="ACTIVE"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def test_agent(db: Session, test_user: User):
    """Create test SUPERVISED agent."""
    agent = AgentRegistry(
        name="Test Supervised Agent",
        description="An agent for testing",
        agent_type="generic",
        category="testing",
        status=AgentStatus.SUPERVISED.value,
        confidence_score=0.75,
        user_id=test_user.id
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


@pytest.fixture
def queue_service(db: Session):
    """Get SupervisedQueueService instance."""
    return SupervisedQueueService(db)


# ============================================================================
# Queue Enqueue Tests
# ============================================================================

def test_enqueue_execution_creates_queue_entry(
    queue_service: SupervisedQueueService,
    test_agent: AgentRegistry,
    test_user: User
):
    """Test that enqueuing execution creates proper queue entry."""
    import asyncio

    execution_context = {
        "action": "test_action",
        "params": {"key": "value"}
    }

    entry = asyncio.run(queue_service.enqueue_execution(
        agent_id=test_agent.id,
        user_id=test_user.id,
        trigger_type="automated",
        execution_context=execution_context,
        priority=1
    ))

    assert entry is not None
    assert entry.agent_id == test_agent.id
    assert entry.user_id == test_user.id
    assert entry.trigger_type == "automated"
    assert entry.status == QueueStatus.pending
    assert entry.priority == 1
    assert entry.attempt_count == 0
    assert entry.max_attempts == 3


def test_enqueue_execution_with_custom_expiry(
    queue_service: SupervisedQueueService,
    test_agent: AgentRegistry,
    test_user: User
):
    """Test enqueuing execution with custom expiry time."""
    import asyncio

    expires_at = datetime.utcnow() + timedelta(hours=48)

    entry = asyncio.run(queue_service.enqueue_execution(
        agent_id=test_agent.id,
        user_id=test_user.id,
        trigger_type="manual",
        execution_context={},
        expires_at=expires_at
    ))

    assert entry.expires_at == expires_at


def test_enqueue_execution_defaults_to_24hr_expiry(
    queue_service: SupervisedQueueService,
    test_agent: AgentRegistry,
    test_user: User
):
    """Test that default expiry is 24 hours."""
    import asyncio

    entry = asyncio.run(queue_service.enqueue_execution(
        agent_id=test_agent.id,
        user_id=test_user.id,
        trigger_type="automated",
        execution_context={}
    ))

    # Should be approximately 24 hours from now
    time_diff = entry.expires_at - datetime.utcnow()
    assert 23.9 * 3600 <= time_diff.total_seconds() <= 24.1 * 3600


# ============================================================================
# Queue Processing Tests
# ============================================================================

def test_process_pending_queues_for_available_user(
    queue_service: SupervisedQueueService,
    test_agent: AgentRegistry,
    test_user: User,
    db: Session
):
    """Test processing queues when user is available."""
    import asyncio

    # Create user activity as online
    activity = UserActivity(
        user_id=test_user.id,
        state=UserState.online
    )
    db.add(activity)
    db.commit()

    # Enqueue execution
    entry = asyncio.run(queue_service.enqueue_execution(
        agent_id=test_agent.id,
        user_id=test_user.id,
        trigger_type="automated",
        execution_context={}
    ))

    # Process pending queues
    processed = asyncio.run(queue_service.process_pending_queues(limit=10))

    assert len(processed) > 0
    assert processed[0].id == entry.id
    assert processed[0].status in [QueueStatus.executing, QueueStatus.completed, QueueStatus.failed]


def test_process_pending_queues_skips_unavailable_users(
    queue_service: SupervisedQueueService,
    test_agent: AgentRegistry,
    test_user: User,
    db: Session
):
    """Test that offline users' queues are not processed."""
    import asyncio

    # User is offline (no activity record)

    # Enqueue execution
    asyncio.run(queue_service.enqueue_execution(
        agent_id=test_agent.id,
        user_id=test_user.id,
        trigger_type="automated",
        execution_context={}
    ))

    # Process pending queues
    processed = asyncio.run(queue_service.process_pending_queues(limit=10))

    assert len(processed) == 0


def test_process_pending_queues_orders_by_priority(
    queue_service: SupervisedQueueService,
    test_agent: AgentRegistry,
    test_user: User,
    db: Session
):
    """Test that queues are processed by priority (highest first)."""
    import asyncio

    # Create user activity as online
    activity = UserActivity(
        user_id=test_user.id,
        state=UserState.online
    )
    db.add(activity)
    db.commit()

    # Enqueue multiple executions with different priorities
    low_priority = asyncio.run(queue_service.enqueue_execution(
        agent_id=test_agent.id,
        user_id=test_user.id,
        trigger_type="automated",
        execution_context={"priority": "low"},
        priority=0
    ))

    high_priority = asyncio.run(queue_service.enqueue_execution(
        agent_id=test_agent.id,
        user_id=test_user.id,
        trigger_type="automated",
        execution_context={"priority": "high"},
        priority=10
    ))

    medium_priority = asyncio.run(queue_service.enqueue_execution(
        agent_id=test_agent.id,
        user_id=test_user.id,
        trigger_type="automated",
        execution_context={"priority": "medium"},
        priority=5
    ))

    # Process queues
    processed = asyncio.run(queue_service.process_pending_queues(limit=10))

    # Should process in priority order
    assert len(processed) >= 3
    # First processed should be high priority
    assert processed[0].id == high_priority.id


# ============================================================================
# Queue Cancellation Tests
# ============================================================================

def test_cancel_queue_entry_success(
    queue_service: SupervisedQueueService,
    test_agent: AgentRegistry,
    test_user: User
):
    """Test cancelling a queue entry."""
    import asyncio

    # Enqueue execution
    entry = asyncio.run(queue_service.enqueue_execution(
        agent_id=test_agent.id,
        user_id=test_user.id,
        trigger_type="automated",
        execution_context={}
    ))

    # Cancel it
    success = asyncio.run(queue_service.cancel_queue_entry(
        queue_id=entry.id,
        user_id=test_user.id
    ))

    assert success is True

    # Check status is cancelled
    db = queue_service.db
    db.refresh(entry)
    assert entry.status == QueueStatus.cancelled


def test_cancel_queue_entry_unauthorized_user(
    queue_service: SupervisedQueueService,
    test_agent: AgentRegistry,
    test_user: User,
    db: Session
):
    """Test that only owner can cancel queue entry."""
    import asyncio

    # Create another user
    other_user = User(
        email="other@example.com",
        status="ACTIVE"
    )
    db.add(other_user)
    db.commit()

    # Enqueue execution
    entry = asyncio.run(queue_service.enqueue_execution(
        agent_id=test_agent.id,
        user_id=test_user.id,
        trigger_type="automated",
        execution_context={}
    ))

    # Try to cancel with different user
    success = asyncio.run(queue_service.cancel_queue_entry(
        queue_id=entry.id,
        user_id=other_user.id
    ))

    assert success is False


def test_cancel_nonexistent_entry_returns_false(
    queue_service: SupervisedQueueService
):
    """Test cancelling non-existent queue entry."""
    import asyncio

    success = asyncio.run(queue_service.cancel_queue_entry(
        queue_id="nonexistent_id",
        user_id="test_user"
    ))

    assert success is False


# ============================================================================
# Get User Queue Tests
# ============================================================================

def test_get_user_queue_returns_all_entries(
    queue_service: SupervisedQueueService,
    test_agent: AgentRegistry,
    test_user: User
):
    """Test getting all queue entries for a user."""
    import asyncio

    # Enqueue multiple executions
    asyncio.run(queue_service.enqueue_execution(
        agent_id=test_agent.id,
        user_id=test_user.id,
        trigger_type="automated",
        execution_context={"index": "1"}
    ))

    asyncio.run(queue_service.enqueue_execution(
        agent_id=test_agent.id,
        user_id=test_user.id,
        trigger_type="manual",
        execution_context={"index": "2"}
    ))

    # Get user queue
    entries = asyncio.run(queue_service.get_user_queue(test_user.id))

    assert len(entries) == 2


def test_get_user_queue_filters_by_status(
    queue_service: SupervisedQueueService,
    test_agent: AgentRegistry,
    test_user: User
):
    """Test filtering user queue by status."""
    import asyncio

    # Enqueue execution
    entry = asyncio.run(queue_service.enqueue_execution(
        agent_id=test_agent.id,
        user_id=test_user.id,
        trigger_type="automated",
        execution_context={}
    ))

    # Get pending entries
    pending_entries = asyncio.run(queue_service.get_user_queue(
        test_user.id,
        status=QueueStatus.pending
    ))

    assert len(pending_entries) == 1
    assert pending_entries[0].id == entry.id

    # Get completed entries (should be empty)
    completed_entries = asyncio.run(queue_service.get_user_queue(
        test_user.id,
        status=QueueStatus.completed
    ))

    assert len(completed_entries) == 0


# ============================================================================
# Queue Status Update Tests
# ============================================================================

def test_update_queue_status_to_executing(
    queue_service: SupervisedQueueService,
    test_agent: AgentRegistry,
    test_user: User
):
    """Test updating queue entry status to executing."""
    import asyncio

    # Enqueue execution
    entry = asyncio.run(queue_service.enqueue_execution(
        agent_id=test_agent.id,
        user_id=test_user.id,
        trigger_type="automated",
        execution_context={}
    ))

    # Update status
    updated = asyncio.run(queue_service.update_queue_status(
        queue_id=entry.id,
        status=QueueStatus.executing,
        execution_id="exec_123"
    ))

    assert updated.status == QueueStatus.executing
    assert updated.execution_id == "exec_123"


def test_update_queue_status_to_failed_with_error(
    queue_service: SupervisedQueueService,
    test_agent: AgentRegistry,
    test_user: User
):
    """Test updating queue entry status to failed with error message."""
    import asyncio

    # Enqueue execution
    entry = asyncio.run(queue_service.enqueue_execution(
        agent_id=test_agent.id,
        user_id=test_user.id,
        trigger_type="automated",
        execution_context={}
    ))

    # Update status to failed
    updated = asyncio.run(queue_service.update_queue_status(
        queue_id=entry.id,
        status=QueueStatus.failed,
        error_message="Execution failed: timeout"
    ))

    assert updated.status == QueueStatus.failed
    assert updated.error_message == "Execution failed: timeout"


# ============================================================================
# Expiry Tests
# ============================================================================

def test_mark_expired_queues_updates_status(
    queue_service: SupervisedQueueService,
    test_agent: AgentRegistry,
    test_user: User
):
    """Test marking expired queues as failed."""
    import asyncio

    # Enqueue execution with past expiry
    expires_at = datetime.utcnow() - timedelta(hours=1)

    entry = asyncio.run(queue_service.enqueue_execution(
        agent_id=test_agent.id,
        user_id=test_user.id,
        trigger_type="automated",
        execution_context={},
        expires_at=expires_at
    ))

    # Mark expired
    count = asyncio.run(queue_service.mark_expired_queues())

    assert count > 0

    # Check entry is marked as failed
    queue_service.db.refresh(entry)
    assert entry.status == QueueStatus.failed
    assert "expired" in entry.error_message.lower()


def test_mark_expired_queues_only_marks_pending(
    queue_service: SupervisedQueueService,
    test_agent: AgentRegistry,
    test_user: User
):
    """Test that only pending entries are marked as expired."""
    import asyncio

    # Enqueue and complete execution
    entry = asyncio.run(queue_service.enqueue_execution(
        agent_id=test_agent.id,
        user_id=test_user.id,
        trigger_type="automated",
        execution_context={}
    ))

    # Mark as completed
    asyncio.run(queue_service.update_queue_status(
        queue_id=entry.id,
        status=QueueStatus.completed
    ))

    # Mark expired (should not mark completed entries)
    count = asyncio.run(queue_service.mark_expired_queues())

    # Entry should still be completed
    queue_service.db.refresh(entry)
    assert entry.status == QueueStatus.completed


# ============================================================================
# Queue Statistics Tests
# ============================================================================

def test_get_queue_stats_returns_counts(
    queue_service: SupervisedQueueService,
    test_agent: AgentRegistry,
    test_user: User
):
    """Test getting queue statistics."""
    import asyncio

    # Enqueue multiple executions
    asyncio.run(queue_service.enqueue_execution(
        agent_id=test_agent.id,
        user_id=test_user.id,
        trigger_type="automated",
        execution_context={}
    ))

    asyncio.run(queue_service.enqueue_execution(
        agent_id=test_agent.id,
        user_id=test_user.id,
        trigger_type="manual",
        execution_context={}
    ))

    # Get stats
    stats = asyncio.run(queue_service.get_queue_stats())

    assert stats["pending"] == 2
    assert stats["total"] == 2
    assert stats["completed"] == 0
    assert stats["failed"] == 0


def test_get_queue_stats_filters_by_user(
    queue_service: SupervisedQueueService,
    test_agent: AgentRegistry,
    test_user: User,
    db: Session
):
    """Test filtering queue statistics by user."""
    import asyncio

    # Create another user
    other_user = User(
        email="other@example.com",
        status="ACTIVE"
    )
    db.add(other_user)
    db.commit()

    # Enqueue for both users
    asyncio.run(queue_service.enqueue_execution(
        agent_id=test_agent.id,
        user_id=test_user.id,
        trigger_type="automated",
        execution_context={}
    ))

    asyncio.run(queue_service.enqueue_execution(
        agent_id=test_agent.id,
        user_id=other_user.id,
        trigger_type="manual",
        execution_context={}
    ))

    # Get stats for test user
    stats = asyncio.run(queue_service.get_queue_stats(user_id=test_user.id))

    assert stats["pending"] == 1
    assert stats["total"] == 1
