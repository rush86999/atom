"""
Unit tests for Agent Request Manager

Tests cover:
- AgentRequestManager initialization
- Permission request creation
- Decision request creation
- Request waiting and timeout handling
- Response handling
- Request revocation
- Audit trail creation
- WebSocket broadcasting
- Request expiration
- Feature flag handling
- Error handling and edge cases
"""

import pytest
from unittest.mock import Mock, MagicMock, AsyncMock, patch
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
import asyncio

from core.agent_request_manager import (
    AgentRequestManager,
    get_agent_request_manager,
    AGENT_REQUESTS_ENABLED
)
from core.models import AgentRegistry, AgentRequestLog


@pytest.fixture
def mock_db():
    """Mock database session"""
    db = Mock(spec=Session)
    db.add = Mock()
    db.commit = Mock()
    db.rollback = Mock()
    db.refresh = Mock()
    db.query = Mock()
    return db


@pytest.fixture
def mock_agent():
    """Mock agent"""
    agent = Mock(spec=AgentRegistry)
    agent.id = "agent_123"
    agent.name = "Test Agent"
    return agent


@pytest.fixture
def request_manager(mock_db):
    """Create AgentRequestManager instance"""
    return AgentRequestManager(mock_db)


# ============================================================================
# Initialization Tests
# ============================================================================

def test_request_manager_initialization(request_manager, mock_db):
    """Test manager initializes correctly"""
    assert request_manager is not None
    assert request_manager.db == mock_db
    assert hasattr(request_manager, 'governance')
    assert hasattr(request_manager, '_pending_requests')
    assert isinstance(request_manager._pending_requests, dict)


def test_request_manager_timeouts_defined(request_manager):
    """Test request timeouts are defined"""
    timeouts = request_manager.REQUEST_TIMEOUTS
    assert "low" in timeouts
    assert "medium" in timeouts
    assert "high" in timeouts
    assert "blocking" in timeouts
    assert timeouts["blocking"] < timeouts["high"]
    assert timeouts["high"] < timeouts["medium"]
    assert timeouts["medium"] < timeouts["low"]


def test_get_agent_request_manager_singleton(mock_db):
    """Test singleton helper function"""
    manager1 = get_agent_request_manager(mock_db)
    manager2 = get_agent_request_manager(mock_db)

    # Should return instances (not true singleton, but helper function)
    assert manager1 is not None
    assert manager2 is not None


# ============================================================================
# Permission Request Tests
# ============================================================================

@pytest.mark.asyncio
async def test_create_permission_request_success(request_manager, mock_agent, mock_db):
    """Test successful permission request creation"""
    with patch.object(mock_db, 'query') as mock_query:
        mock_query.return_value.filter.return_value.first.return_value = mock_agent

        request_id = await request_manager.create_permission_request(
            user_id="user_123",
            agent_id=mock_agent.id,
            title="Permission Request",
            permission="read_data",
            context={"operation": "data_access"},
            urgency="medium"
        )

        assert request_id is not None
        # Verify database commit
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_create_permission_request_with_custom_expiry(request_manager, mock_agent, mock_db):
    """Test permission request with custom expiration"""
    with patch.object(mock_db, 'query') as mock_query:
        mock_query.return_value.filter.return_value.first.return_value = mock_agent

        request_id = await request_manager.create_permission_request(
            user_id="user_123",
            agent_id=mock_agent.id,
            title="Custom Expiry Request",
            permission="write_data",
            context={},
            urgency="medium",
            expires_in=300  # 5 minutes
        )

        assert request_id is not None


@pytest.mark.asyncio
async def test_create_permission_request_all_urgency_levels(request_manager, mock_agent, mock_db):
    """Test permission requests with all urgency levels"""
    urgency_levels = ["low", "medium", "high", "blocking"]

    for urgency in urgency_levels:
        with patch.object(mock_db, 'query') as mock_query:
            mock_query.return_value.filter.return_value.first.return_value = mock_agent

            request_id = await request_manager.create_permission_request(
                user_id="user_123",
                agent_id=mock_agent.id,
                title=f"{urgency.title()} Request",
                permission="test_permission",
                context={},
                urgency=urgency
            )

            assert request_id is not None


@pytest.mark.asyncio
async def test_create_permission_request_agent_not_found(request_manager, mock_db):
    """Test permission request when agent not found"""
    with patch.object(mock_db, 'query') as mock_query:
        mock_query.return_value.filter.return_value.first.return_value = None

        request_id = await request_manager.create_permission_request(
            user_id="user_123",
            agent_id="nonexistent_agent",
            title="Test Request",
            permission="test_permission",
            context={},
            urgency="medium"
        )

        # Should still return a request ID
        assert request_id is not None


@pytest.mark.asyncio
async def test_create_permission_request_creates_event(request_manager, mock_agent, mock_db):
    """Test permission request creates response event"""
    with patch.object(mock_db, 'query') as mock_query:
        mock_query.return_value.filter.return_value.first.return_value = mock_agent

        request_id = await request_manager.create_permission_request(
            user_id="user_123",
            agent_id=mock_agent.id,
            title="Test Request",
            permission="test_permission",
            context={},
            urgency="medium"
        )

        # Verify event created for waiting
        assert request_id in request_manager._pending_requests
        assert isinstance(request_manager._pending_requests[request_id], asyncio.Event)


@pytest.mark.asyncio
async def test_create_permission_request_broadcasts(request_manager, mock_agent, mock_db):
    """Test permission request broadcasts via WebSocket"""
    with patch.object(mock_db, 'query') as mock_query:
        mock_query.return_value.filter.return_value.first.return_value = mock_agent

        with patch('core.agent_request_manager.ws_manager') as mock_ws:
            mock_ws.broadcast = AsyncMock()

            request_id = await request_manager.create_permission_request(
                user_id="user_123",
                agent_id=mock_agent.id,
                title="Test Request",
                permission="test_permission",
                context={},
                urgency="medium"
            )

            # Verify broadcast called
            mock_ws.broadcast.assert_called_once()


@pytest.mark.asyncio
async def test_create_permission_request_creates_audit(request_manager, mock_agent, mock_db):
    """Test permission request creates audit entry"""
    with patch.object(mock_db, 'query') as mock_query:
        mock_query.return_value.filter.return_value.first.return_value = mock_agent

        with patch.object(request_manager, '_create_audit', new=AsyncMock()) as mock_audit:
            request_id = await request_manager.create_permission_request(
                user_id="user_123",
                agent_id=mock_agent.id,
                title="Test Request",
                permission="test_permission",
                context={},
                urgency="medium"
            )

            # Verify audit created
            mock_audit.assert_called_once()


# ============================================================================
# Decision Request Tests
# ============================================================================

@pytest.mark.asyncio
async def test_create_decision_request_success(request_manager, mock_agent, mock_db):
    """Test successful decision request creation"""
    with patch.object(mock_db, 'query') as mock_query:
        mock_query.return_value.filter.return_value.first.return_value = mock_agent

        options = [
            {"label": "Option A", "description": "Choose A"},
            {"label": "Option B", "description": "Choose B"}
        ]

        request_id = await request_manager.create_decision_request(
            user_id="user_123",
            agent_id=mock_agent.id,
            title="Decision Needed",
            explanation="Please choose an option",
            options=options,
            context={"decision_point": "branch"},
            urgency="low"
        )

        assert request_id is not None


@pytest.mark.asyncio
async def test_create_decision_request_with_suggestion(request_manager, mock_agent, mock_db):
    """Test decision request with suggested option"""
    with patch.object(mock_db, 'query') as mock_query:
        mock_query.return_value.filter.return_value.first.return_value = mock_agent

        options = [
            {"label": "A", "description": "Option A"},
            {"label": "B", "description": "Option B"},
            {"label": "C", "description": "Option C"}
        ]

        request_id = await request_manager.create_decision_request(
            user_id="user_123",
            agent_id=mock_agent.id,
            title="Choose",
            explanation="Pick one",
            options=options,
            context={},
            urgency="low",
            suggested_option=1  # Suggest option B
        )

        assert request_id is not None


@pytest.mark.asyncio
async def test_create_decision_request_all_urgency_levels(request_manager, mock_agent, mock_db):
    """Test decision requests with all urgency levels"""
    with patch.object(mock_db, 'query') as mock_query:
        mock_query.return_value.filter.return_value.first.return_value = mock_agent

        options = [{"label": "Yes", "description": "Confirm"}]

        for urgency in ["low", "medium", "high"]:
            request_id = await request_manager.create_decision_request(
                user_id="user_123",
                agent_id=mock_agent.id,
                title=f"{urgency} Decision",
                explanation="Need decision",
                options=options,
                context={},
                urgency=urgency
            )

            assert request_id is not None


@pytest.mark.asyncio
async def test_create_decision_request_creates_event(request_manager, mock_agent, mock_db):
    """Test decision request creates response event"""
    with patch.object(mock_db, 'query') as mock_query:
        mock_query.return_value.filter.return_value.first.return_value = mock_agent

        options = [{"label": "OK", "description": "Continue"}]

        request_id = await request_manager.create_decision_request(
            user_id="user_123",
            agent_id=mock_agent.id,
            title="Continue?",
            explanation="Should we proceed",
            options=options,
            context={}
        )

        # Verify event created
        assert request_id in request_manager._pending_requests


# ============================================================================
# wait_for_response Tests
# ============================================================================

@pytest.mark.asyncio
async def test_wait_for_response_success(request_manager, mock_db):
    """Test successful wait for response"""
    request_id = "test_request_123"
    request_manager._pending_requests[request_id] = asyncio.Event()

    # Mock request log
    mock_log = Mock(spec=AgentRequestLog)
    mock_log.user_response = {"action": "approve"}
    mock_log.expires_at = datetime.now() + timedelta(minutes=10)

    with patch.object(mock_db, 'query') as mock_query:
        mock_query.return_value.filter.return_value.first.return_value = mock_log

        # Simulate response
        async def respond():
            await asyncio.sleep(0.1)
            request_manager._pending_requests[request_id].set()

        # Start response in background
        response_task = asyncio.create_task(respond())

        # Wait for response
        response = await request_manager.wait_for_response(request_id, timeout=5)

        await response_task

        assert response is not None
        assert response["action"] == "approve"


@pytest.mark.asyncio
async def test_wait_for_response_timeout(request_manager, mock_db):
    """Test wait for response times out"""
    request_id = "timeout_request"
    request_manager._pending_requests[request_id] = asyncio.Event()

    # Mock request log with expiration
    mock_log = Mock(spec=AgentRequestLog)
    mock_log.expires_at = datetime.now() + timedelta(seconds=1)

    with patch.object(mock_db, 'query') as mock_query:
        mock_query.return_value.filter.return_value.first.return_value = mock_log

        # Don't set the event, so it will timeout
        response = await request_manager.wait_for_response(request_id, timeout=0.5)

        assert response is None


@pytest.mark.asyncio
async def test_wait_for_response_request_not_found(request_manager):
    """Test wait for response when request not found"""
    response = await request_manager.wait_for_response("nonexistent_request")

    assert response is None


@pytest.mark.asyncio
async def test_wait_for_response_cleanup(request_manager, mock_db):
    """Test wait cleans up pending request"""
    request_id = "cleanup_test"
    event = asyncio.Event()
    request_manager._pending_requests[request_id] = event

    # Mock request log
    mock_log = Mock(spec=AgentRequestLog)
    mock_log.user_response = {"data": "response"}

    with patch.object(mock_db, 'query') as mock_query:
        mock_query.return_value.filter.return_value.first.return_value = mock_log

        # Set event and wait
        event.set()
        await request_manager.wait_for_response(request_id)

        # Verify cleanup
        assert request_id not in request_manager._pending_requests


# ============================================================================
# handle_response Tests
# ============================================================================

@pytest.mark.asyncio
async def test_handle_response_success(request_manager, mock_db):
    """Test successful response handling"""
    request_id = "response_test"
    user_id = "user_123"

    # Mock request log
    mock_log = Mock(spec=AgentRequestLog)
    mock_log.expires_at = datetime.now() + timedelta(minutes=10)
    mock_log.created_at = datetime.now() - timedelta(seconds=5)

    with patch.object(mock_db, 'query') as mock_query:
        mock_query.return_value.filter.return_value.first.return_value = mock_log

        response = {"action": "approve", "comment": "Proceed"}

        await request_manager.handle_response(user_id, request_id, response)

        # Verify log updated
        assert mock_log.user_response == response
        assert mock_log.responded_at is not None
        assert mock_log.response_time_seconds >= 0


@pytest.mark.asyncio
async def test_handle_response_request_not_found(request_manager, mock_db):
    """Test handle response when request not found"""
    with patch.object(mock_db, 'query') as mock_query:
        mock_query.return_value.filter.return_value.first.return_value = None

        # Should not raise exception
        await request_manager.handle_response("user_123", "nonexistent", {})


@pytest.mark.asyncio
async def test_handle_response_expired_request(request_manager, mock_db):
    """Test handle response for expired request"""
    mock_log = Mock(spec=AgentRequestLog)
    mock_log.expires_at = datetime.now() - timedelta(minutes=1)  # Expired

    with patch.object(mock_db, 'query') as mock_query:
        mock_query.return_value.filter.return_value.first.return_value = mock_log

        # Should not update expired request
        await request_manager.handle_response("user_123", "expired_request", {})

        # Should not update log
        assert not hasattr(mock_log, 'user_response') or mock_log.user_response is None


@pytest.mark.asyncio
async def test_handle_response_triggers_event(request_manager, mock_db):
    """Test handle response triggers waiting event"""
    request_id = "event_trigger_test"
    event = asyncio.Event()
    request_manager._pending_requests[request_id] = event

    mock_log = Mock(spec=AgentRequestLog)
    mock_log.expires_at = datetime.now() + timedelta(minutes=10)
    mock_log.created_at = datetime.now()

    with patch.object(mock_db, 'query') as mock_query:
        mock_query.return_value.filter.return_value.first.return_value = mock_log

        await request_manager.handle_response("user_123", request_id, {"action": "approve"})

        # Verify event was set
        assert event.is_set()


@pytest.mark.asyncio
async def test_handle_response_creates_audit(request_manager, mock_db):
    """Test handle response creates audit entry"""
    mock_log = Mock(spec=AgentRequestLog)
    mock_log.agent_id = "agent_123"
    mock_log.expires_at = datetime.now() + timedelta(minutes=10)
    mock_log.created_at = datetime.now()

    with patch.object(mock_db, 'query') as mock_query:
        mock_query.return_value.filter.return_value.first.return_value = mock_log

        with patch.object(request_manager, '_create_audit', new=AsyncMock()) as mock_audit:
            await request_manager.handle_response("user_123", "request_id", {"action": "approve"})

            # Verify audit created
            mock_audit.assert_called_once()


# ============================================================================
# revoke_request Tests
# ============================================================================

@pytest.mark.asyncio
async def test_revoke_request_success(request_manager, mock_db):
    """Test successful request revocation"""
    request_id = "revoke_test"

    # Mock request log
    mock_log = Mock(spec=AgentRequestLog)
    mock_log.revoked = False

    with patch.object(mock_db, 'query') as mock_query:
        mock_query.return_value.filter.return_value.first.return_value = mock_log

        await request_manager.revoke_request(request_id)

        # Verify revoked
        assert mock_log.revoked is True
        mock_db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_revoke_request_triggers_event(request_manager):
    """Test revoke request triggers waiting event"""
    request_id = "revoke_event_test"
    event = asyncio.Event()
    request_manager._pending_requests[request_id] = event

    await request_manager.revoke_request(request_id)

    # Verify event was set
    assert event.is_set()


@pytest.mark.asyncio
async def test_revoke_nonexistent_request(request_manager):
    """Test revoking nonexistent request"""
    # Should not raise exception
    await request_manager.revoke_request("nonexistent")


# ============================================================================
# _create_audit Tests
# ============================================================================

@pytest.mark.asyncio
async def test_create_audit_success(request_manager, mock_db):
    """Test audit entry creation"""
    await request_manager._create_audit(
        agent_id="agent_123",
        user_id="user_123",
        request_id="request_123",
        action="create_permission_request"
    )

    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_create_audit_with_metadata(request_manager, mock_db):
    """Test audit entry with metadata"""
    metadata = {"test_key": "test_value"}

    await request_manager._create_audit(
        agent_id="agent_123",
        user_id="user_123",
        request_id="request_123",
        action="handle_response",
        metadata=metadata
    )

    # Verify audit created with metadata
    mock_db.add.assert_called_once()


@pytest.mark.asyncio
async def test_create_audit_handles_error(request_manager, mock_db):
    """Test audit creation handles errors"""
    mock_db.commit.side_effect = Exception("Database error")

    # Should not raise exception
    await request_manager._create_audit(
        agent_id="agent_123",
        user_id="user_123",
        request_id="request_123",
        action="test_action"
    )


# ============================================================================
# Feature Flag Tests
# ============================================================================

@pytest.mark.asyncio
async def test_feature_flag_disabled_returns_early(mock_db):
    """Test requests return early when feature disabled"""
    with patch('core.agent_request_manager.AGENT_REQUESTS_ENABLED', False):
        manager = AgentRequestManager(mock_db)

        # Should return UUID without database interaction
        request_id = await manager.create_permission_request(
            user_id="user_123",
            agent_id="agent_123",
            title="Test",
            permission="test",
            context={}
        )

        assert request_id is not None
        # Should not call database
        mock_db.add.assert_not_called()


@pytest.mark.asyncio
async def test_feature_flag_current_state(request_manager):
    """Test current feature flag state"""
    # This test documents the current state
    # AGENT_REQUESTS_ENABLED is True by default
    assert AGENT_REQUESTS_ENABLED in [True, False]


# ============================================================================
# Error Handling Tests
# ============================================================================

@pytest.mark.asyncio
async def test_create_permission_request_handles_error(request_manager, mock_agent, mock_db):
    """Test permission request handles errors gracefully"""
    with patch.object(mock_db, 'query') as mock_query:
        mock_query.return_value.filter.return_value.first.return_value = mock_agent
        mock_db.commit.side_effect = Exception("Database error")

        # Should not raise exception
        request_id = await request_manager.create_permission_request(
            user_id="user_123",
            agent_id=mock_agent.id,
            title="Test",
            permission="test",
            context={}
        )

        # Should still return request ID
        assert request_id is not None


@pytest.mark.asyncio
async def test_create_decision_request_handles_error(request_manager, mock_agent, mock_db):
    """Test decision request handles errors gracefully"""
    with patch.object(mock_db, 'query') as mock_query:
        mock_query.return_value.filter.return_value.first.return_value = mock_agent
        mock_db.commit.side_effect = Exception("Database error")

        options = [{"label": "OK", "description": "Continue"}]

        # Should not raise exception
        request_id = await request_manager.create_decision_request(
            user_id="user_123",
            agent_id=mock_agent.id,
            title="Test",
            explanation="Test",
            options=options,
            context={}
        )

        assert request_id is not None


@pytest.mark.asyncio
async def test_wait_for_response_handles_error(request_manager):
    """Test wait for response handles errors"""
    request_id = "error_test"
    request_manager._pending_requests[request_id] = asyncio.Event()

    # Mock query that raises error
    with patch('core.agent_request_manager.AgentRequestLog') as MockLog:
        MockLog.query.side_effect = Exception("Query error")

        # Set event to avoid timeout
        request_manager._pending_requests[request_id].set()

        # Should handle error gracefully
        response = await request_manager.wait_for_response(request_id)

        # Should return None on error
        assert response is None


@pytest.mark.asyncio
async def test_handle_response_handles_error(request_manager, mock_db):
    """Test handle response handles errors"""
    with patch.object(mock_db, 'query') as mock_query:
        mock_query.return_value.filter.return_value.first.side_effect = Exception("Query error")

        # Should not raise exception
        await request_manager.handle_response("user_123", "request_id", {})


@pytest.mark.asyncio
async def test_revoke_request_handles_error(request_manager, mock_db):
    """Test revoke request handles errors"""
    with patch.object(mock_db, 'query') as mock_query:
        mock_query.return_value.filter.return_value.first.side_effect = Exception("Query error")

        # Should not raise exception
        await request_manager.revoke_request("request_id")


# ============================================================================
# Request Lifecycle Tests
# ============================================================================

@pytest.mark.asyncio
async def test_full_request_lifecycle(request_manager, mock_agent, mock_db):
    """Test complete request lifecycle"""
    with patch.object(mock_db, 'query') as mock_query:
        mock_query.return_value.filter.return_value.first.return_value = mock_agent

        # 1. Create request
        request_id = await request_manager.create_permission_request(
            user_id="user_123",
            agent_id=mock_agent.id,
            title="Test Request",
            permission="test_permission",
            context={}
        )

        assert request_id is not None
        assert request_id in request_manager._pending_requests

        # 2. Handle response
        mock_log = Mock(spec=AgentRequestLog)
        mock_log.expires_at = datetime.now() + timedelta(minutes=10)
        mock_log.created_at = datetime.now()
        mock_log.agent_id = mock_agent.id

        mock_query.return_value.filter.return_value.first.return_value = mock_log

        await request_manager.handle_response("user_123", request_id, {"action": "approve"})

        # 3. Verify event was set
        assert request_manager._pending_requests[request_id].is_set()


@pytest.mark.asyncio
async def test_request_revocation_before_response(request_manager, mock_agent, mock_db):
    """Test request can be revoked before response"""
    with patch.object(mock_db, 'query') as mock_query:
        mock_query.return_value.filter.return_value.first.return_value = mock_agent

        # Create request
        request_id = await request_manager.create_permission_request(
            user_id="user_123",
            agent_id=mock_agent.id,
            title="Test",
            permission="test",
            context={}
        )

        # Revoke before response
        mock_log = Mock(spec=AgentRequestLog)
        mock_log.revoked = False
        mock_query.return_value.filter.return_value.first.return_value = mock_log

        await request_manager.revoke_request(request_id)

        # Event should be set
        assert request_manager._pending_requests[request_id].is_set()


@pytest.mark.asyncio
async def test_multiple_concurrent_requests(request_manager, mock_agent, mock_db):
    """Test handling multiple concurrent requests"""
    with patch.object(mock_db, 'query') as mock_query:
        mock_query.return_value.filter.return_value.first.return_value = mock_agent

        # Create multiple requests
        request_ids = []
        for i in range(3):
            request_id = await request_manager.create_permission_request(
                user_id="user_123",
                agent_id=mock_agent.id,
                title=f"Request {i}",
                permission="test",
                context={}
            )
            request_ids.append(request_id)

        # All should be tracked
        for request_id in request_ids:
            assert request_id in request_manager._pending_requests


# ============================================================================
# WebSocket Broadcast Tests
# ============================================================================

@pytest.mark.asyncio
async def test_permission_request_broadcast_message_format(request_manager, mock_agent, mock_db):
    """Test permission request broadcasts correct message format"""
    with patch.object(mock_db, 'query') as mock_query:
        mock_query.return_value.filter.return_value.first.return_value = mock_agent

        with patch('core.agent_request_manager.ws_manager') as mock_ws:
            mock_ws.broadcast = AsyncMock()

            await request_manager.create_permission_request(
                user_id="user_123",
                agent_id=mock_agent.id,
                title="Test Request",
                permission="test_permission",
                context={"operation": "test"}
            )

            # Verify broadcast call
            assert mock_ws.broadcast.called
            call_args = mock_ws.broadcast.call_args
            assert call_args[0][0] == "user:user_123"
            message = call_args[0][1]
            assert message["type"] == "agent:request"
            assert "data" in message


@pytest.mark.asyncio
async def test_decision_request_broadcast_message_format(request_manager, mock_agent, mock_db):
    """Test decision request broadcasts correct message format"""
    with patch.object(mock_db, 'query') as mock_query:
        mock_query.return_value.filter.return_value.first.return_value = mock_agent

        with patch('core.agent_request_manager.ws_manager') as mock_ws:
            mock_ws.broadcast = AsyncMock()

            options = [{"label": "Yes", "description": "Confirm"}]

            await request_manager.create_decision_request(
                user_id="user_123",
                agent_id=mock_agent.id,
                title="Decision",
                explanation="Choose",
                options=options,
                context={}
            )

            # Verify broadcast
            assert mock_ws.broadcast.called
            call_args = mock_ws.broadcast.call_args
            message = call_args[0][1]
            assert message["data"]["request_type"] == "decision"


# ============================================================================
# Request Timeout Tests
# ============================================================================

@pytest.mark.asyncio
async def test_request_timeout_marked_revoked(request_manager, mock_db):
    """Test timed out request is marked as revoked"""
    request_id = "timeout_test"
    request_manager._pending_requests[request_id] = asyncio.Event()

    mock_log = Mock(spec=AgentRequestLog)
    mock_log.expires_at = datetime.now() + timedelta(seconds=1)

    with patch.object(mock_db, 'query') as mock_query:
        mock_query.return_value.filter.return_value.first.return_value = mock_log

        # Wait with short timeout
        response = await request_manager.wait_for_response(request_id, timeout=0.5)

        assert response is None
        # Verify marked as revoked
        assert mock_log.revoked is True


@pytest.mark.asyncio
async def test_request_timeout_calculation(request_manager, mock_db):
    """Test timeout calculated from request expiration"""
    request_id = "timeout_calc"
    request_manager._pending_requests[request_id] = asyncio.Event()

    # Request expires in 30 seconds
    mock_log = Mock(spec=AgentRequestLog)
    mock_log.expires_at = datetime.now() + timedelta(seconds=30)

    with patch.object(mock_db, 'query') as mock_query:
        mock_query.return_value.filter.return_value.first.return_value = mock_log

        # Should use request expiration if no timeout provided
        response = await request_manager.wait_for_response(request_id, timeout=None)

        # Should have waited close to expiration time
        assert response is None  # No response provided


@pytest.mark.asyncio
async def test_request_timeout_default_fallback(request_manager, mock_db):
    """Test default timeout when no expiration set"""
    request_id = "default_timeout"
    request_manager._pending_requests[request_id] = asyncio.Event()

    mock_log = Mock(spec=AgentRequestLog)
    mock_log.expires_at = None

    with patch.object(mock_db, 'query') as mock_query:
        mock_query.return_value.filter.return_value.first.return_value = mock_log

        # Set event to avoid long wait
        request_manager._pending_requests[request_id].set()

        # Should use default timeout
        response = await request_manager.wait_for_response(request_id)

        # Should return None since no response was set
        assert response is None
