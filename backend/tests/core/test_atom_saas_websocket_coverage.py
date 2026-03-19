"""
Coverage-driven tests for atom_saas_websocket.py (0% -> 75%+ target)

This test suite provides comprehensive coverage for the AtomSaaSWebSocketClient,
covering connection management, message routing, broadcasting, authentication,
and WebSocket lifecycle operations.

Coverage Target: 75%+ (245+ of 328 statements)
Test Count: 18+ tests
"""

import asyncio
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from core.atom_saas_websocket import (
    AtomSaaSWebSocketClient,
    MessageType,
    WebSocketConnectionError,
    get_websocket_state,
)


class TestAtomSaaSWebSocketCoverage:
    """Coverage-driven tests for atom_saas_websocket.py"""

    # ==================== Connection Lifecycle Tests ====================

    @pytest.mark.parametrize("api_token,ws_url,expected_url", [
        ("test_token", None, "ws://localhost:5058/api/ws/satellite/connect"),
        ("test_token", "ws://custom:5050/connect", "ws://custom:5050/connect"),
        ("another_token", "ws://example.com/ws", "ws://example.com/ws"),
    ])
    def test_initialization(self, api_token, ws_url, expected_url):
        """Cover client initialization (lines 74-106)"""
        client = AtomSaaSWebSocketClient(api_token, ws_url)

        assert client.api_token == api_token
        assert client.ws_url == expected_url
        assert not client.is_connected
        assert client._reconnect_attempts == 0
        assert client._consecutive_failures == 0
        assert client._message_timestamps == []

    @pytest.mark.parametrize("connection_state,expected", [
        (True, True),
        (False, False),
    ])
    def test_is_connected_property(self, connection_state, expected):
        """Cover is_connected property (lines 108-111)"""
        client = AtomSaaSWebSocketClient("test_token")
        client._connected = connection_state
        client._ws_connection = Mock() if connection_state else None

        assert client.is_connected == expected

    @pytest.mark.asyncio
    @pytest.mark.parametrize("already_connected,should_connect", [
        (True, False),  # Already connected
        (False, True),  # Should connect
    ])
    async def test_connect_already_connected(self, already_connected, should_connect):
        """Cover connection when already connected (lines 126-128)"""
        client = AtomSaaSWebSocketClient("test_token")
        client._connected = already_connected

        mock_handler = AsyncMock()

        if already_connected:
            result = await client.connect(mock_handler)
            assert result is True
        else:
            # Mock the websockets.connect to avoid real connection
            mock_ws = AsyncMock()
            with patch('core.atom_saas_websocket.websockets.connect', new_callable=AsyncMock, return_value=mock_ws):
                with patch('core.atom_saas_websocket.asyncio.create_task'):
                    with patch.object(client, '_update_db_state', new_callable=AsyncMock):
                        result = await client.connect(mock_handler)
                        assert result is True

    @pytest.mark.asyncio
    async def test_connect_success(self):
        """Cover successful connection (lines 132-162)"""
        client = AtomSaaSWebSocketClient("test_token")

        # Mock websockets.connect
        mock_ws = AsyncMock()
        mock_ws.close = AsyncMock()

        with patch('core.atom_saas_websocket.websockets.connect', new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_ws

            with patch('core.atom_saas_websocket.asyncio.create_task'):
                with patch.object(client, '_update_db_state', new_callable=AsyncMock) as mock_update:
                    mock_handler = AsyncMock()
                    result = await client.connect(mock_handler)

                    assert result is True
                    assert client._connected is True
                    assert client._reconnect_attempts == 0
                    assert client._consecutive_failures == 0
                    assert client._message_handler == mock_handler
                    mock_update.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_failure(self):
        """Cover connection failure (lines 164-174)"""
        client = AtomSaaSWebSocketClient("test_token")

        with patch('core.atom_saas_websocket.websockets.connect', new_callable=AsyncMock) as mock_connect:
            mock_connect.side_effect = Exception("Connection failed")

            with patch.object(client, '_update_db_state', new_callable=AsyncMock) as mock_update:
                mock_handler = AsyncMock()

                with pytest.raises(WebSocketConnectionError):
                    await client.connect(mock_handler)

                assert client._consecutive_failures == 1
                assert client._last_disconnect_reason == "Connection failed"
                mock_update.assert_called_once()

    @pytest.mark.asyncio
    async def test_disconnect(self):
        """Cover graceful disconnection (lines 176-205)"""
        client = AtomSaaSWebSocketClient("test_token")
        client._connected = True
        client._heartbeat_task = Mock()
        client._reconnect_task = Mock()
        client._ws_connection = AsyncMock()
        client._ws_connection.close = AsyncMock()

        with patch.object(client, '_update_db_state', new_callable=AsyncMock) as mock_update:
            await client.disconnect()

            assert client._connected is False
            assert client._heartbeat_task is None
            assert client._reconnect_task is None
            assert client._ws_connection is None
            mock_update.assert_called_once()

    # ==================== Message Routing Tests ====================

    @pytest.mark.asyncio
    @pytest.mark.parametrize("message,should_send", [
        ({"type": "chat", "data": "test"}, True),
        ({"type": "broadcast", "data": {"msg": "test"}}, True),
        ({"type": "ping"}, True),
    ])
    async def test_send_message(self, message, should_send):
        """Cover message sending (lines 207-229)"""
        client = AtomSaaSWebSocketClient("test_token")
        client._connected = True
        client._ws_connection = AsyncMock()
        client._ws_connection.send = AsyncMock()

        result = await client.send_message(message)

        if should_send:
            assert result is True
            client._ws_connection.send.assert_called_once_with(json.dumps(message))

    @pytest.mark.asyncio
    async def test_send_message_not_connected(self):
        """Cover send message when not connected (lines 217-219)"""
        client = AtomSaaSWebSocketClient("test_token")
        client._connected = False

        result = await client.send_message({"type": "test"})

        assert result is False

    @pytest.mark.asyncio
    async def test_send_message_failure(self):
        """Cover send message exception handling (lines 227-229)"""
        client = AtomSaaSWebSocketClient("test_token")
        client._connected = True
        client._ws_connection = AsyncMock()
        client._ws_connection.send = AsyncMock(side_effect=Exception("Send failed"))

        result = await client.send_message({"type": "test"})

        assert result is False

    # ==================== Message Handling Tests ====================

    @pytest.mark.asyncio
    @pytest.mark.parametrize("message_type,data,expected_valid", [
        (MessageType.SKILL_UPDATE, {"skill_id": "skill-1", "name": "Test Skill"}, True),
        (MessageType.CATEGORY_UPDATE, {"name": "Category 1"}, True),
        (MessageType.RATING_UPDATE, {"skill_id": "skill-1", "rating": 5}, True),
        (MessageType.SKILL_DELETE, {"skill_id": "skill-1"}, True),
        (MessageType.RATING_UPDATE, {"skill_id": "skill-1", "rating": 6}, False),  # Invalid rating
        (MessageType.SKILL_UPDATE, {"name": "Test"}, False),  # Missing skill_id
        (MessageType.RATING_UPDATE, {"skill_id": "skill-1", "rating": "high"}, False),  # Non-int rating
    ])
    async def test_validate_message_data(self, message_type, data, expected_valid):
        """Cover message data validation (lines 338-389)"""
        client = AtomSaaSWebSocketClient("test_token")

        result = client._validate_message_data(message_type, data)

        assert result == expected_valid

    @pytest.mark.asyncio
    @pytest.mark.parametrize("message,expected_valid", [
        ({"type": "test", "data": {}}, True),
        ({"type": MessageType.PING}, True),  # No data required
        ({"type": MessageType.PONG}, True),  # No data required
        ({"data": {}}, False),  # Missing type
        (None, False),  # Not a dict
        ("string", False),  # Not a dict
        ([], False),  # Not a dict
        ({"type": "test"}, False),  # Missing data (not ping/pong)
    ])
    async def test_validate_message(self, message, expected_valid):
        """Cover message validation (lines 311-336)"""
        client = AtomSaaSWebSocketClient("test_token")

        result = client._validate_message(message)

        assert result == expected_valid

    @pytest.mark.asyncio
    @pytest.mark.parametrize("raw_message,message_type,data", [
        (json.dumps({"type": "skill_update", "data": {"skill_id": "skill-1", "name": "Test"}}),
         "skill_update", {"skill_id": "skill-1", "name": "Test"}),
        (json.dumps({"type": "ping"}), "ping", None),
        (json.dumps({"type": "pong"}), "pong", None),
    ])
    async def test_handle_message_valid(self, raw_message, message_type, data):
        """Cover valid message handling (lines 249-309)"""
        client = AtomSaaSWebSocketClient("test_token")
        client._connected = True
        client._message_handler = AsyncMock()

        with patch.object(client, '_update_db_state', new_callable=AsyncMock):
            with patch.object(client, '_update_cache', new_callable=AsyncMock):
                await client._handle_message(raw_message)

                if message_type not in [MessageType.PING, MessageType.PONG]:
                    client._message_handler.assert_called_once_with(message_type, data)

    @pytest.mark.asyncio
    async def test_handle_message_invalid_json(self):
        """Cover invalid JSON handling (lines 305-306)"""
        client = AtomSaaSWebSocketClient("test_token")
        client._connected = True

        # Should not raise exception, just log warning
        await client._handle_message("invalid json")

    @pytest.mark.asyncio
    async def test_handle_message_size_limit(self):
        """Cover message size limit (lines 257-260)"""
        client = AtomSaaSWebSocketClient("test_token")
        client._connected = True

        # Create message exceeding 1MB limit
        large_message = json.dumps({"type": "test", "data": "x" * 2_000_000})

        with patch.object(client, '_update_db_state', new_callable=AsyncMock):
            await client._handle_message(large_message)
            # Should return early due to size limit

    @pytest.mark.asyncio
    async def test_handle_message_rate_limit(self):
        """Cover rate limiting (lines 262-268)"""
        client = AtomSaaSWebSocketClient("test_token")
        client._connected = True
        client._message_handler = AsyncMock()

        # Send 101 messages to exceed rate limit
        with patch.object(client, '_update_db_state', new_callable=AsyncMock):
            for i in range(101):
                message = json.dumps({"type": "test", "data": {"id": i}})
                await client._handle_message(message)

            # Last message should be rate limited

    @pytest.mark.asyncio
    async def test_handle_ping_message(self):
        """Cover ping message handling (lines 287-289)"""
        client = AtomSaaSWebSocketClient("test_token")
        client._connected = True
        client._ws_connection = AsyncMock()
        client._ws_connection.send = AsyncMock()

        with patch.object(client, '_update_db_state', new_callable=AsyncMock):
            # Mock send_message to avoid WebSocket dependency
            with patch.object(client, 'send_message', new_callable=AsyncMock, return_value=True) as mock_send:
                await client._handle_message(json.dumps({"type": "ping"}))

                # Should call send_message with pong
                mock_send.assert_called_once()
                sent_data = mock_send.call_args[0][0]
                assert sent_data["type"] == "pong"

    # ==================== Cache Update Tests ====================

    @pytest.mark.asyncio
    @pytest.mark.parametrize("message_type,data", [
        (MessageType.SKILL_UPDATE, {"skill_id": "skill-1", "name": "Test Skill"}),
        (MessageType.CATEGORY_UPDATE, {"name": "Category 1"}),
        (MessageType.SKILL_DELETE, {"skill_id": "skill-1"}),
    ])
    async def test_update_cache_skill(self, message_type, data):
        """Cover cache updates (lines 391-464)"""
        client = AtomSaaSWebSocketClient("test_token")

        await client._update_cache(message_type, data)
        # Should complete without error

    # ==================== Heartbeat Tests ====================

    @pytest.mark.asyncio
    async def test_heartbeat_loop(self):
        """Cover heartbeat loop (lines 466-499)"""
        client = AtomSaaSWebSocketClient("test_token")
        client._connected = True
        client._message_handler = AsyncMock()

        with patch('core.atom_saas_websocket.asyncio.sleep', new_callable=AsyncMock):
            with patch.object(client, 'send_message', new_callable=AsyncMock) as mock_send:
                with patch.object(client, '_wait_for_pong', new_callable=AsyncMock, return_value=True):
                    # Run one iteration
                    task = asyncio.create_task(client._heartbeat_loop())

                    # Cancel after short delay
                    await asyncio.sleep(0.01)
                    task.cancel()

                    try:
                        await task
                    except asyncio.CancelledError:
                        pass

    @pytest.mark.asyncio
    async def test_heartbeat_timeout(self):
        """Cover heartbeat timeout (lines 489-491)"""
        client = AtomSaaSWebSocketClient("test_token")
        client._connected = True

        with patch('core.atom_saas_websocket.asyncio.sleep', new_callable=AsyncMock):
            with patch.object(client, 'send_message', new_callable=AsyncMock):
                with patch.object(client, '_wait_for_pong', new_callable=AsyncMock, side_effect=asyncio.TimeoutError):
                    with patch.object(client, '_handle_disconnect', new_callable=AsyncMock) as mock_disconnect:
                        task = asyncio.create_task(client._heartbeat_loop())

                        await asyncio.sleep(0.01)
                        task.cancel()

                        try:
                            await task
                        except asyncio.CancelledError:
                            pass

    # ==================== Reconnection Tests ====================

    @pytest.mark.asyncio
    @pytest.mark.parametrize("attempt,delay", [
        (0, 1),
        (1, 2),
        (2, 4),
        (3, 8),
        (4, 16),
        (5, 16),  # Max delay
    ])
    async def test_reconnect_delay(self, attempt, delay):
        """Cover reconnection exponential backoff (lines 538-560)"""
        client = AtomSaaSWebSocketClient("test_token")
        client._reconnect_attempts = attempt
        client._message_handler = AsyncMock()

        with patch('core.atom_saas_websocket.asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            with patch.object(client, 'connect', new_callable=AsyncMock, side_effect=Exception("Failed")):
                with patch.object(client, '_update_db_state', new_callable=AsyncMock):
                    await client._reconnect()

                    mock_sleep.assert_called_once_with(delay)

    @pytest.mark.asyncio
    async def test_handle_disconnect_triggers_reconnect(self):
        """Cover disconnect handling with reconnection (lines 508-536)"""
        client = AtomSaaSWebSocketClient("test_token")
        client._connected = True
        client._reconnect_attempts = 0
        client._message_handler = AsyncMock()

        with patch.object(client, '_update_db_state', new_callable=AsyncMock):
            with patch('core.atom_saas_websocket.asyncio.create_task') as mock_create:
                await client._handle_disconnect("test_reason")

                assert client._connected is False
                assert client._last_disconnect_reason == "test_reason"
                assert client._consecutive_failures == 1

    @pytest.mark.asyncio
    async def test_handle_disconnect_max_attempts(self):
        """Cover max reconnect attempts (lines 528-536)"""
        client = AtomSaaSWebSocketClient("test_token")
        client._connected = True
        client._reconnect_attempts = 10  # Max attempts

        with patch.object(client, '_update_db_state', new_callable=AsyncMock):
            await client._handle_disconnect("test_reason")

            assert client._connected is False

    # ==================== Database State Tests ====================

    @pytest.mark.asyncio
    @pytest.mark.parametrize("connected,last_connected,last_message,reason", [
        (True, datetime.now(timezone.utc), datetime.now(timezone.utc), None),
        (False, None, None, "test_disconnect"),
    ])
    async def test_update_db_state(self, connected, last_connected, last_message, reason):
        """Cover database state updates (lines 562-605)"""
        client = AtomSaaSWebSocketClient("test_token")

        with patch('core.atom_saas_websocket.SessionLocal') as mock_session:
            mock_db = MagicMock()
            mock_session.return_value.__enter__.return_value = mock_db

            mock_state = Mock()
            mock_db.query.return_value.first.return_value = mock_state

            await client._update_db_state(
                connected=connected,
                last_connected_at=last_connected,
                last_message_at=last_message,
                disconnect_reason=reason
            )

            if connected is not None:
                assert mock_state.connected == connected
            if last_connected is not None:
                assert mock_state.last_connected_at == last_connected
            if last_message is not None:
                assert mock_state.last_message_at == last_message
            if reason is not None:
                assert mock_state.disconnect_reason == reason

    # ==================== Status and Handler Tests ====================

    def test_get_status(self):
        """Cover status retrieval (lines 607-621)"""
        client = AtomSaaSWebSocketClient("test_token")
        client._connected = True
        client._reconnect_attempts = 3
        client._consecutive_failures = 2
        client._last_disconnect_reason = "test"

        status = client.get_status()

        assert status["connected"] is True
        assert status["ws_url"] == client.ws_url
        assert status["reconnect_attempts"] == 3
        assert status["consecutive_failures"] == 2
        assert status["last_disconnect_reason"] == "test"
        assert status["rate_limit_messages_per_sec"] == 100

    def test_on_message(self):
        """Cover custom message handler registration (lines 623-631)"""
        client = AtomSaaSWebSocketClient("test_token")

        callback = AsyncMock()
        client.on_message(callback)

        assert client._message_handler == callback

    @pytest.mark.asyncio
    @pytest.mark.parametrize("handler,method_name,should_call_cache", [
        ("handle_skill_update", "handle_skill_update", True),
        ("handle_category_update", "handle_category_update", True),
        ("handle_rating_update", "handle_rating_update", False),  # Has custom DB logic
        ("handle_skill_delete", "handle_skill_delete", True),
    ])
    async def test_message_handlers(self, handler, method_name, should_call_cache):
        """Cover specific message handlers (lines 633-692)"""
        client = AtomSaaSWebSocketClient("test_token")

        method = getattr(client, handler)
        data = {"test": "data"}

        if handler == "handle_rating_update":
            # Rating update has custom DB logic, not _update_cache
            # Need skill_id in data for handler to work
            data = {"skill_id": "skill-1", "rating": 5}
            with patch('core.atom_saas_websocket.SessionLocal') as mock_session:
                mock_db = MagicMock()
                mock_session.return_value.__enter__.return_value = mock_db
                mock_skill_cache = Mock()
                mock_db.query.return_value.first.return_value = mock_skill_cache

                await method(data)

                # Verify it queried the cache
                mock_db.query.assert_called()
        else:
            with patch.object(client, '_update_cache', new_callable=AsyncMock) as mock_update:
                await method(data)

                # Should call _update_cache
                if should_call_cache:
                    mock_update.assert_called_once()

    # ==================== Helper Function Tests ====================

    def test_get_websocket_state(self):
        """Cover get_websocket_state helper (lines 695-707)"""
        with patch('core.atom_saas_websocket.SessionLocal') as mock_session:
            mock_db = MagicMock()
            mock_session.return_value.__enter__.return_value = mock_db

            mock_state = Mock()
            mock_db.query.return_value.first.return_value = mock_state

            result = get_websocket_state()

            assert result == mock_state

    def test_get_websocket_state_error(self):
        """Cover get_websocket_state error handling (lines 705-707)"""
        with patch('core.atom_saas_websocket.SessionLocal') as mock_session:
            mock_session.side_effect = Exception("DB error")

            result = get_websocket_state()

            assert result is None
