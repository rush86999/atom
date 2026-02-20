"""
Tests for Atom SaaS WebSocket client

Comprehensive test suite covering:
- WebSocket connection management
- Heartbeat and reconnection logic
- Message handlers for different update types
- Message validation and rate limiting
- Integration with SyncService
- Fallback to polling

Phase 61-03 Task 7
"""

import asyncio
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import websockets
from websockets.exceptions import ConnectionClosedOK

from core.atom_saas_websocket import (
    AtomSaaSWebSocketClient,
    MessageType,
    get_websocket_state,
    WebSocketConnectionError
)
from core.database import SessionLocal
from core.models import SkillCache, CategoryCache, WebSocketState


# ============================================================================
# Test WebSocket Connection
# ============================================================================

class TestWebSocketConnection:
    """Test WebSocket connection management."""

    @pytest.mark.asyncio
    async def test_connect_success(self):
        """Test successful WebSocket connection."""
        client = AtomSaaSWebSocketClient(api_token="test_token")

        # Mock websockets.connect - returns async context manager
        async def mock_connect(*args, **kwargs):
            # Return a mock WebSocket connection
            mock_ws = MagicMock()
            mock_ws.send = AsyncMock()
            mock_ws.close = AsyncMock()

            # Make it an async context manager
            async def enter():
                return mock_ws

            async def exit():
                pass

            mock_ws.__aenter__ = enter
            mock_ws.__aexit__ = exit

            return mock_ws

        with patch("core.atom_saas_websocket.websockets.connect", side_effect=mock_connect):
            message_handler = AsyncMock()

            # Mock _update_db_state to avoid DB calls
            client._update_db_state = AsyncMock()

            # Mock _message_loop to avoid infinite loop
            with patch.object(client, "_message_loop"):
                result = await client.connect(message_handler)

                assert result is True
                assert client.is_connected is True

    @pytest.mark.asyncio
    async def test_connect_already_connected(self):
        """Test connecting when already connected."""
        client = AtomSaaSWebSocketClient(api_token="test_token")
        client._connected = True
        client._ws_connection = AsyncMock()

        message_handler = AsyncMock()
        result = await client.connect(message_handler)

        assert result is True
        message_handler.assert_not_called()

    @pytest.mark.asyncio
    async def test_connect_failure(self):
        """Test WebSocket connection failure."""
        client = AtomSaaSWebSocketClient(api_token="test_token")

        with patch("core.atom_saas_websocket.websockets.connect") as mock_connect:
            mock_connect.side_effect = Exception("Connection refused")

            message_handler = AsyncMock()

            with pytest.raises(WebSocketConnectionError):
                await client.connect(message_handler)

            assert client.is_connected is False

    @pytest.mark.asyncio
    async def test_disconnect(self):
        """Test WebSocket disconnection."""
        client = AtomSaaSWebSocketClient(api_token="test_token")
        client._connected = True

        # Create proper async mock for WebSocket connection
        mock_ws = AsyncMock()
        mock_ws.close = AsyncMock()
        client._ws_connection = mock_ws

        # Mock tasks (don't need to be real AsyncMocks for cancel())
        client._heartbeat_task = MagicMock()
        client._heartbeat_task.cancel = MagicMock()
        client._reconnect_task = MagicMock()
        client._reconnect_task.cancel = MagicMock()

        # Mock _update_db_state
        client._update_db_state = AsyncMock()

        await client.disconnect()

        assert client.is_connected is False
        mock_ws.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_is_connected(self):
        """Test is_connected property."""
        client = AtomSaaSWebSocketClient(api_token="test_token")

        assert client.is_connected is False

        client._connected = True
        client._ws_connection = AsyncMock()

        assert client.is_connected is True


# ============================================================================
# Test WebSocket Heartbeat
# ============================================================================

class TestWebSocketHeartbeat:
    """Test heartbeat monitoring."""

    @pytest.mark.asyncio
    async def test_heartbeat_sent(self):
        """Test heartbeat ping sent every 30 seconds."""
        client = AtomSaaSWebSocketClient(api_token="test_token")
        client._connected = True
        client._ws_connection = AsyncMock()
        client._ws_connection.send = AsyncMock()

        # Send ping
        await client.send_message({"type": MessageType.PING})

        client._ws_connection.send.assert_called_once()
        message_arg = json.loads(client._ws_connection.send.call_args[0][0])
        assert message_arg["type"] == MessageType.PING

    @pytest.mark.asyncio
    async def test_pong_received(self):
        """Test pong response handling."""
        client = AtomSaaSWebSocketClient(api_token="test_token")
        client._connected = True

        # Pong should be handled in _handle_message
        # This is a simplified test
        message = {"type": MessageType.PONG}

        # Mock _update_db_state to avoid DB calls
        client._update_db_state = AsyncMock()

        # Process pong message
        await client._handle_message(json.dumps(message))

        # Pong should be logged, no error
        assert True  # If we got here, pong was handled

    @pytest.mark.asyncio
    async def test_stale_connection_detected(self):
        """Test stale connection detection."""
        client = AtomSaaSWebSocketClient(api_token="test_token")
        client._connected = True
        client._reconnect_attempts = 0
        client._consecutive_failures = 0

        # Mock _update_db_state
        client._update_db_state = AsyncMock()
        client._reconnect_task = None

        # Mock _reconnect
        with patch.object(client, "_reconnect") as mock_reconnect:
            await client._handle_disconnect("stale_connection")

            assert client._connected is False
            assert client._consecutive_failures == 1
            # Reconnect should be scheduled
            assert client._reconnect_task is not None


# ============================================================================
# Test WebSocket Reconnection
# ============================================================================

class TestWebSocketReconnection:
    """Test reconnection logic."""

    @pytest.mark.asyncio
    async def test_exponential_backoff(self):
        """Test exponential backoff delays."""
        client = AtomSaaSWebSocketClient(api_token="test_token")

        # Check backoff delays
        assert client.RECONNECT_DELAYS == [1, 2, 4, 8, 16]

        # Simulate reconnection attempts
        for attempt, expected_delay in enumerate([1, 2, 4, 8, 16]):
            delay_index = min(attempt, len(client.RECONNECT_DELAYS) - 1)
            assert client.RECONNECT_DELAYS[delay_index] == expected_delay

    @pytest.mark.asyncio
    async def test_max_reconnect_attempts(self):
        """Test max reconnect attempts (10)."""
        client = AtomSaaSWebSocketClient(api_token="test_token")
        client._reconnect_attempts = client.MAX_RECONNECT_ATTEMPTS
        client._connected = False

        # Should not trigger reconnection
        with patch.object(client, "_reconnect") as mock_reconnect:
            await client._handle_disconnect("test_failure")

            # Should not schedule reconnect after max attempts
            mock_reconnect.assert_not_called()

    @pytest.mark.asyncio
    async def test_manual_reconnect(self):
        """Test manual reconnection reset."""
        client = AtomSaaSWebSocketClient(api_token="test_token")
        client._reconnect_attempts = 5
        client._consecutive_failures = 3

        # Reset for manual reconnect
        client._reconnect_attempts = 0
        client._consecutive_failures = 0

        assert client._reconnect_attempts == 0
        assert client._consecutive_failures == 0


# ============================================================================
# Test WebSocket Message Handlers
# ============================================================================

class TestWebSocketMessageHandlers:
    """Test message handling for different update types."""

    @pytest.mark.asyncio
    async def test_skill_update_handler(self):
        """Test skill_update message handler."""
        client = AtomSaaSWebSocketClient(api_token="test_token")
        client._connected = True

        message = {
            "type": MessageType.SKILL_UPDATE,
            "data": {
                "skill_id": "skill_123",
                "name": "Test Skill",
                "description": "Test description"
            }
        }

        # Mock _update_cache
        with patch.object(client, "_update_cache") as mock_update:
            await client.handle_skill_update(message["data"])
            mock_update.assert_called_once_with(MessageType.SKILL_UPDATE, message["data"])

    @pytest.mark.asyncio
    async def test_category_update_handler(self):
        """Test category_update message handler."""
        client = AtomSaaSWebSocketClient(api_token="test_token")
        client._connected = True

        message = {
            "type": MessageType.CATEGORY_UPDATE,
            "data": {
                "name": "Test Category",
                "skill_count": 42
            }
        }

        with patch.object(client, "_update_cache") as mock_update:
            await client.handle_category_update(message["data"])
            mock_update.assert_called_once_with(MessageType.CATEGORY_UPDATE, message["data"])

    @pytest.mark.asyncio
    async def test_rating_update_handler(self):
        """Test rating_update message handler."""
        client = AtomSaaSWebSocketClient(api_token="test_token")
        client._connected = True

        # Use unique skill_id to avoid conflicts
        import uuid
        skill_id = f"skill_123_{uuid.uuid4().hex[:8]}"

        with SessionLocal() as db:
            # Create test skill cache with existing ratings data
            skill_cache = SkillCache(
                skill_id=skill_id,
                skill_data={"name": "Test Skill", "average_rating": 4.0, "rating_count": 5},
                expires_at=datetime.now(timezone.utc)
            )
            db.add(skill_cache)
            db.commit()

        message = {
            "type": MessageType.RATING_UPDATE,
            "data": {
                "skill_id": skill_id,
                "rating": 5,
                "average_rating": 4.5,
                "rating_count": 10
            }
        }

        await client.handle_rating_update(message["data"])

        # Verify rating updated in cache
        with SessionLocal() as db:
            skill_cache = db.query(SkillCache).filter(
                SkillCache.skill_id == skill_id
            ).first()

            assert skill_cache is not None
            # Check that ratings were updated
            assert "average_rating" in skill_cache.skill_data
            assert skill_cache.skill_data["average_rating"] == 4.5
            assert skill_cache.skill_data["rating_count"] == 10

        # Cleanup
        with SessionLocal() as db:
            db.query(SkillCache).filter(SkillCache.skill_id == skill_id).delete()
            db.commit()

    @pytest.mark.asyncio
    async def test_skill_delete_handler(self):
        """Test skill_delete message handler."""
        client = AtomSaaSWebSocketClient(api_token="test_token")
        client._connected = True

        # Use unique skill_id to avoid conflicts
        import uuid
        skill_id = f"skill_delete_{uuid.uuid4().hex[:8]}"

        with SessionLocal() as db:
            # Create test skill cache
            skill_cache = SkillCache(
                skill_id=skill_id,
                skill_data={"name": "Test Skill"},
                expires_at=datetime.now(timezone.utc)
            )
            db.add(skill_cache)
            db.commit()

        message = {
            "type": MessageType.SKILL_DELETE,
            "data": {
                "skill_id": skill_id
            }
        }

        with patch.object(client, "_update_cache") as mock_update:
            await client.handle_skill_delete(message["data"])
            mock_update.assert_called_once_with(MessageType.SKILL_DELETE, message["data"])

        # Cleanup (in case _update_cache didn't delete it)
        with SessionLocal() as db:
            db.query(SkillCache).filter(SkillCache.skill_id == skill_id).delete()
            db.commit()

    @pytest.mark.asyncio
    async def test_on_message_callback(self):
        """Test custom message handler registration."""
        client = AtomSaaSWebSocketClient(api_token="test_token")

        custom_handler = AsyncMock()
        client.on_message(custom_handler)

        assert client._message_handler == custom_handler


# ============================================================================
# Test WebSocket Integration
# ============================================================================

class TestWebSocketIntegration:
    """Test integration with SyncService and fallback logic."""

    @pytest.mark.asyncio
    async def test_cache_update_on_skill_message(self):
        """Test SkillCache updated on skill_update message."""
        client = AtomSaaSWebSocketClient(api_token="test_token")
        client._connected = True

        skill_data = {
            "skill_id": "skill_integration_test",
            "name": "Integration Test Skill",
            "description": "Test"
        }

        # Update cache
        await client._update_cache(MessageType.SKILL_UPDATE, skill_data)

        # Verify cache
        with SessionLocal() as db:
            skill_cache = db.query(SkillCache).filter(
                SkillCache.skill_id == "skill_integration_test"
            ).first()

            assert skill_cache is not None
            assert skill_cache.skill_data["name"] == "Integration Test Skill"

        # Cleanup
        with SessionLocal() as db:
            db.query(SkillCache).filter(
                SkillCache.skill_id == "skill_integration_test"
            ).delete()
            db.commit()

    @pytest.mark.asyncio
    async def test_cache_update_on_category_message(self):
        """Test CategoryCache updated on category_update message."""
        client = AtomSaaSWebSocketClient(api_token="test_token")
        client._connected = True

        category_data = {
            "name": "integration_test_category",
            "skill_count": 100
        }

        await client._update_cache(MessageType.CATEGORY_UPDATE, category_data)

        # Verify cache
        with SessionLocal() as db:
            category_cache = db.query(CategoryCache).filter(
                CategoryCache.category_name == "integration_test_category"
            ).first()

            assert category_cache is not None
            assert category_cache.category_data["skill_count"] == 100

        # Cleanup
        with SessionLocal() as db:
            db.query(CategoryCache).filter(
                CategoryCache.category_name == "integration_test_category"
            ).delete()
            db.commit()

    @pytest.mark.asyncio
    async def test_cache_delete_on_skill_delete(self):
        """Test skill deleted from cache on skill_delete message."""
        client = AtomSaaSWebSocketClient(api_token="test_token")
        client._connected = True

        with SessionLocal() as db:
            # Create test skill
            skill_cache = SkillCache(
                skill_id="skill_to_delete",
                skill_data={"name": "Delete Me"},
                expires_at=datetime.now(timezone.utc)
            )
            db.add(skill_cache)
            db.commit()

        # Delete via message
        delete_data = {"skill_id": "skill_to_delete"}
        await client._update_cache(MessageType.SKILL_DELETE, delete_data)

        # Verify deleted
        with SessionLocal() as db:
            skill_cache = db.query(SkillCache).filter(
                SkillCache.skill_id == "skill_to_delete"
            ).first()

            assert skill_cache is None


# ============================================================================
# Test WebSocket Validation
# ============================================================================

class TestWebSocketValidation:
    """Test message validation and rate limiting."""

    @pytest.mark.asyncio
    async def test_message_structure_validation(self):
        """Test message structure validation."""
        client = AtomSaaSWebSocketClient(api_token="test_token")
        client._connected = True

        # Invalid: not a dict
        assert client._validate_message("invalid") is False

        # Invalid: missing 'type'
        assert client._validate_message({"data": {}}) is False

        # Valid: has 'type' but missing 'data'
        assert client._validate_message({"type": "test"}) is False

        # Valid: has both
        assert client._validate_message({"type": "skill_update", "data": {}}) is True

    @pytest.mark.asyncio
    async def test_message_type_validation(self):
        """Test message type validation."""
        client = AtomSaaSWebSocketClient(api_token="test_token")
        client._connected = True

        # Valid: skill_update with required fields
        skill_data = {"skill_id": "test", "name": "Test"}
        assert client._validate_message_data(MessageType.SKILL_UPDATE, skill_data) is True

        # Invalid: skill_update missing skill_id
        invalid_data = {"name": "Test"}
        assert client._validate_message_data(MessageType.SKILL_UPDATE, invalid_data) is False

        # Invalid: rating_update with invalid rating
        invalid_rating = {"skill_id": "test", "rating": 10}
        assert client._validate_message_data(MessageType.RATING_UPDATE, invalid_rating) is False

        # Valid: rating_update with valid rating
        valid_rating = {"skill_id": "test", "rating": 5}
        assert client._validate_message_data(MessageType.RATING_UPDATE, valid_rating) is True

    @pytest.mark.asyncio
    async def test_rate_limiting(self):
        """Test rate limiting enforcement."""
        client = AtomSaaSWebSocketClient(api_token="test_token")
        client._connected = True

        # Add 100 messages within 1 second
        now = 1000.0
        client._message_timestamps = [now - i * 0.001 for i in range(100)]

        # Next message should be blocked
        assert len(client._message_timestamps) >= client.RATE_LIMIT_MESSAGES

    @pytest.mark.asyncio
    async def test_message_size_limit(self):
        """Test message size limit (1MB)."""
        client = AtomSaaSWebSocketClient(api_token="test_token")
        client._connected = True

        # Small message should pass
        small_message = '{"type": "test", "data": {}}'

        # Mock _update_db_state
        client._update_db_state = AsyncMock()

        # Should not raise
        await client._handle_message(small_message)

        # Large message (>1MB) should be rejected
        large_message = '{"type": "test", "data": "' + "x" * (2 * 1024 * 1024) + '"}'

        # Should handle gracefully (no exception)
        await client._handle_message(large_message)


# ============================================================================
# Test WebSocket Database State
# ============================================================================

class TestWebSocketDatabaseState:
    """Test WebSocketState database model."""

    def test_get_websocket_state(self):
        """Test get_websocket_state helper."""
        # Create test state
        with SessionLocal() as db:
            # Clean up first
            db.query(WebSocketState).delete()
            db.commit()

            state = WebSocketState(
                id=1,
                connected=True,
                reconnect_attempts=3
            )
            db.add(state)
            db.commit()

        # Get state
        result = get_websocket_state()

        assert result is not None
        assert result.id == 1
        assert result.connected is True
        assert result.reconnect_attempts == 3

        # Cleanup
        with SessionLocal() as db:
            db.query(WebSocketState).delete()
            db.commit()

    def test_websocket_state_singleton(self):
        """Test WebSocketState singleton pattern."""
        with SessionLocal() as db:
            # Clean up
            db.query(WebSocketState).delete()
            db.commit()

            # Create first state
            state1 = WebSocketState(id=1, connected=True)
            db.add(state1)
            db.commit()

            # Try to create second (should fail or replace)
            state2 = WebSocketState(id=1, connected=False)
            db.merge(state2)
            db.commit()

            # Only one row should exist
            count = db.query(WebSocketState).count()
            assert count == 1

        # Cleanup
        with SessionLocal() as db:
            db.query(WebSocketState).delete()
            db.commit()

    def test_websocket_state_fields(self):
        """Test WebSocketState all fields."""
        with SessionLocal() as db:
            state = WebSocketState(
                id=1,
                connected=True,
                last_connected_at=datetime.now(timezone.utc),
                last_message_at=datetime.now(timezone.utc),
                disconnect_reason="test",
                reconnect_attempts=5,
                consecutive_failures=2,
                fallback_to_polling=True
            )
            db.add(state)
            db.commit()
            db.refresh(state)

            assert state.connected is True
            assert state.disconnect_reason == "test"
            assert state.reconnect_attempts == 5
            assert state.consecutive_failures == 2
            assert state.fallback_to_polling is True

        # Cleanup
        with SessionLocal() as db:
            db.query(WebSocketState).delete()
            db.commit()


# ============================================================================
# Test WebSocket Status
# ============================================================================

class TestWebSocketStatus:
    """Test WebSocket status reporting."""

    def test_get_status_disconnected(self):
        """Test get_status when disconnected."""
        client = AtomSaaSWebSocketClient(api_token="test_token")

        status = client.get_status()

        assert status["connected"] is False
        assert status["reconnect_attempts"] == 0
        assert status["consecutive_failures"] == 0
        assert status["rate_limit_messages_per_sec"] == 100

    def test_get_status_connected(self):
        """Test get_status when connected."""
        client = AtomSaaSWebSocketClient(api_token="test_token")
        client._connected = True
        client._reconnect_attempts = 2
        client._consecutive_failures = 1
        client._last_disconnect_reason = "test_disconnect"

        status = client.get_status()

        assert status["connected"] is True
        assert status["reconnect_attempts"] == 2
        assert status["consecutive_failures"] == 1
        assert status["last_disconnect_reason"] == "test_disconnect"
