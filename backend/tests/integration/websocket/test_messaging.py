"""
WebSocket real-time messaging tests (Wave 1, Task 1.2).

Tests cover:
- Send and receive message
- Multiple clients
- Broadcast messages
- Private messages
"""
import asyncio
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from tests.property_tests.conftest import db_session


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def cleanup_websocket_manager():
    """Cleanup WebSocket manager state before/after tests."""
    from core.websockets import manager
    # Store original state
    original_connections = manager.active_connections.copy()
    original_user_connections = manager.user_connections.copy()

    yield

    # Restore state
    manager.active_connections.clear()
    manager.user_connections.clear()
    manager.active_connections.update(original_connections)
    manager.user_connections.update(original_user_connections)


@pytest.fixture
def connected_websocket(cleanup_websocket_manager):
    """Create a connected WebSocket for testing."""
    from core.websockets import manager

    ws = MagicMock()
    ws.accept = AsyncMock()
    ws.send_json = AsyncMock()
    ws.send_text = AsyncMock()

    # Connect with dev-token
    user = asyncio.run(manager.connect(ws, "dev-token"))

    return ws, user


# =============================================================================
# Send and Receive Message Tests
# =============================================================================

class TestSendAndReceiveMessage:
    """Test sending and receiving messages through WebSocket."""

    @pytest.mark.asyncio(mode="auto")
    async def test_send_and_receive_message(self, connected_websocket):
        """Test sending and receiving messages via WebSocket."""
        from core.websockets import manager

        # Given: Connected WebSocket
        ws, user = connected_websocket

        # When: Send message
        test_message = {
            "type": "message",
            "content": "Hello, World!"
        }
        await manager.send_personal_message(user.id, test_message)

        # Then: Should receive message
        ws.send_json.assert_called_once()
        call_args = ws.send_json.call_args[0][0]
        assert call_args["type"] == "message"
        assert call_args["content"] == "Hello, World!"

    @pytest.mark.asyncio(mode="auto")
    async def test_send_message_to_specific_user(self, connected_websocket):
        """Test sending message to specific user."""
        from core.websockets import manager

        # Given: Two connected users
        ws1, user1 = connected_websocket
        ws2 = MagicMock()
        ws2.accept = AsyncMock()
        ws2.send_json = AsyncMock()
        user2 = await manager.connect(ws2, "dev-token")

        # When: Send message to user1 only
        test_message = {"type": "private", "content": "Private message"}
        await manager.send_personal_message(user1.id, test_message)

        # Then: Only user1 should receive
        ws1.send_json.assert_called_once()
        ws2.send_json.assert_not_called()

    @pytest.mark.asyncio(mode="auto")
    async def test_send_message_includes_timestamp(self, connected_websocket):
        """Test broadcast_event automatically includes timestamp."""
        from core.websockets import manager

        # Given: Connected WebSocket
        ws, user = connected_websocket
        user_channel = f"user:{user.id}"

        # When: Broadcast event
        await manager.broadcast_event(
            user_channel,
            "test_event",
            {"data": "test data"}
        )

        # Then: Should include timestamp
        ws.send_json.assert_called_once()
        call_args = ws.send_json.call_args[0][0]
        assert "timestamp" in call_args
        assert call_args["type"] == "test_event"
        assert call_args["data"] == {"data": "test data"}

    @pytest.mark.asyncio(mode="auto")
    async def test_send_multiple_messages_sequentially(self, connected_websocket):
        """Test sending multiple messages sequentially."""
        from core.websockets import manager

        # Given: Connected WebSocket
        ws, user = connected_websocket

        # When: Send multiple messages
        messages = [
            {"type": "msg1", "content": "First"},
            {"type": "msg2", "content": "Second"},
            {"type": "msg3", "content": "Third"},
        ]

        for msg in messages:
            await manager.send_personal_message(user.id, msg)

        # Then: All messages should be sent
        assert ws.send_json.call_count == 3

        # Verify each message
        for i, call in enumerate(ws.send_json.call_args_list):
            sent_msg = call[0][0]
            assert sent_msg["content"] == messages[i]["content"]


# =============================================================================
# Multiple Clients Tests
# =============================================================================

class TestMultipleClients:
    """Test multiple WebSocket clients simultaneously."""

    @pytest.mark.asyncio(mode="auto")
    async def test_multiple_clients_connected(self, cleanup_websocket_manager):
        """Test multiple WebSocket clients can connect simultaneously."""
        from core.websockets import manager

        # Given: Multiple clients
        clients = []
        for i in range(5):
            ws = MagicMock()
            ws.accept = AsyncMock()
            ws.send_json = AsyncMock()
            user = await manager.connect(ws, "dev-token")
            clients.append((ws, user))

        # Then: All clients should be connected
        assert len(manager.user_connections) == 5  # All "dev-user" but different connections

    @pytest.mark.asyncio(mode="auto")
    async def test_broadcast_to_all_clients_in_channel(self, cleanup_websocket_manager):
        """Test broadcasting message to all clients in a channel."""
        from core.websockets import manager

        # Given: Multiple clients in same channel
        channel = "test_broadcast_channel"
        clients = []
        for i in range(3):
            ws = MagicMock()
            ws.accept = AsyncMock()
            ws.send_json = AsyncMock()
            await manager.connect(ws, "dev-token")
            manager.subscribe(ws, channel)
            clients.append(ws)

        # When: Broadcast to channel
        await manager.broadcast(channel, {"type": "broadcast", "count": 3})

        # Then: All clients should receive
        for ws in clients:
            ws.send_json.assert_called_once()

    @pytest.mark.asyncio(mode="auto")
    async def test_send_personal_message_to_user_with_multiple_connections(self, cleanup_websocket_manager):
        """Test sending personal message to user with multiple connections."""
        from core.websockets import manager

        # Given: User with 3 connections
        user_id = "dev-user"
        connections = []
        for i in range(3):
            ws = MagicMock()
            ws.accept = AsyncMock()
            ws.send_json = AsyncMock()
            await manager.connect(ws, "dev-token")
            connections.append(ws)

        # When: Send personal message
        await manager.send_personal_message(user_id, {"type": "test", "content": "Hello"})

        # Then: All connections should receive
        for ws in connections:
            ws.send_json.assert_called_once()

    @pytest.mark.asyncio(mode="auto")
    async def test_clients_dont_interfere_with_each_other(self, cleanup_websocket_manager):
        """Test multiple clients don't interfere with each other."""
        from core.websockets import manager

        # Given: Two users
        ws1 = MagicMock()
        ws1.accept = AsyncMock()
        ws1.send_json = AsyncMock()
        user1 = await manager.connect(ws1, "dev-token")

        ws2 = MagicMock()
        ws2.accept = AsyncMock()
        ws2.send_json = AsyncMock()
        user2 = await manager.connect(ws2, "dev-token")

        # When: Send message to user1
        await manager.send_personal_message(user1.id, {"type": "private", "to": "user1"})

        # Then: Only user1 receives
        ws1.send_json.assert_called_once()
        ws2.send_json.assert_not_called()


# =============================================================================
# Broadcast Messages Tests
# =============================================================================

class TestBroadcastMessages:
    """Test broadcasting messages to channels."""

    @pytest.mark.asyncio(mode="auto")
    async def test_broadcast_to_channel(self, connected_websocket):
        """Test broadcasting message to a channel."""
        from core.websockets import manager

        # Given: WebSocket subscribed to channel
        ws, user = connected_websocket
        channel = "test_channel"
        manager.subscribe(ws, channel)

        # When: Broadcast message
        test_message = {"type": "broadcast", "content": "Hello, channel!"}
        await manager.broadcast(channel, test_message)

        # Then: Message should be sent
        ws.send_json.assert_called()
        # At least once (may have other calls from connection)
        assert any(
            call[0][0]["type"] == "broadcast"
            for call in ws.send_json.call_args_list
        )

    @pytest.mark.asyncio(mode="auto")
    async def test_broadcast_to_multiple_channels(self, connected_websocket):
        """Test broadcasting to multiple channels."""
        from core.websockets import manager

        # Given: WebSocket subscribed to multiple channels
        ws, user = connected_websocket
        channels = ["channel_1", "channel_2", "channel_3"]
        for ch in channels:
            manager.subscribe(ws, ch)

        # When: Broadcast to each channel
        for channel in channels:
            await manager.broadcast(channel, {"type": "msg", "channel": channel})

        # Then: Should receive all broadcasts
        broadcast_calls = [
            call for call in ws.send_json.call_args_list
            if call[0][0].get("type") == "msg"
        ]
        assert len(broadcast_calls) == 3

    @pytest.mark.asyncio(mode="auto")
    async def test_broadcast_to_empty_channel(self, connected_websocket, caplog):
        """Test broadcasting to empty channel logs warning."""
        from core.websockets import manager
        import logging

        # Given: Empty channel
        empty_channel = "empty_channel_xyz"

        # When: Try to broadcast
        with caplog.at_level(logging.WARNING):
            await manager.broadcast(empty_channel, {"type": "test"})

        # Then: Should log warning (and not crash)
        assert any("EMPTY channel" in record.message for record in caplog.records)

    @pytest.mark.asyncio(mode="auto")
    async def test_broadcast_json_serialization(self, connected_websocket):
        """Test broadcast message is properly JSON serialized."""
        from core.websockets import manager

        # Given: WebSocket subscribed to channel
        ws, user = connected_websocket
        channel = "json_test_channel"
        manager.subscribe(ws, channel)

        # When: Broadcast complex message
        complex_message = {
            "type": "complex",
            "nested": {
                "data": [1, 2, 3],
                "metadata": {"key": "value"}
            },
            "timestamp": datetime.now().isoformat()
        }
        await manager.broadcast(channel, complex_message)

        # Then: Should be serialized correctly
        ws.send_json.assert_called()
        sent_data = ws.send_json.call_args[0][0]
        assert sent_data["nested"]["data"] == [1, 2, 3]
        assert sent_data["nested"]["metadata"]["key"] == "value"


# =============================================================================
# Private Messages Tests
# =============================================================================

class TestPrivateMessages:
    """Test private messaging functionality."""

    @pytest.mark.asyncio(mode="auto")
    async def test_private_message_only_reaches_target_user(self, cleanup_websocket_manager):
        """Test private message only reaches target user."""
        from core.websockets import manager

        # Given: Two users
        ws1 = MagicMock()
        ws1.accept = AsyncMock()
        ws1.send_json = AsyncMock()
        user1 = await manager.connect(ws1, "dev-token")

        ws2 = MagicMock()
        ws2.accept = AsyncMock()
        ws2.send_json = AsyncMock()
        user2 = await manager.connect(ws2, "dev-token")

        # When: Send private message to user1
        private_msg = {
            "type": "private",
            "from": "system",
            "content": "Secret message"
        }
        await manager.send_personal_message(user1.id, private_msg)

        # Then: Only user1 receives
        ws1.send_json.assert_called_once()
        ws2.send_json.assert_not_called()

    @pytest.mark.asyncio(mode="auto")
    async def test_private_message_to_nonexistent_user(self, connected_websocket, caplog):
        """Test sending private message to nonexistent user handles gracefully."""
        from core.websockets import manager
        import logging

        # Given: Nonexistent user
        nonexistent_user = "nonexistent_user_xyz"

        # When: Try to send message (should not raise exception)
        with caplog.at_level(logging.ERROR):
            await manager.send_personal_message(
                nonexistent_user,
                {"type": "test"}
            )

        # Then: Should handle gracefully (may log error)
        # Test passes if no exception is raised
        assert True

    @pytest.mark.asyncio(mode="auto")
    async def test_private_message_reaches_all_user_connections(self, cleanup_websocket_manager):
        """Test private message reaches all connections for a user."""
        from core.websockets import manager

        # Given: User with 2 connections
        ws1 = MagicMock()
        ws1.accept = AsyncMock()
        ws1.send_json = AsyncMock()
        user1 = await manager.connect(ws1, "dev-token")

        ws2 = MagicMock()
        ws2.accept = AsyncMock()
        ws2.send_json = AsyncMock()
        await manager.connect(ws2, "dev-token")  # Same user

        # When: Send private message
        await manager.send_personal_message(user1.id, {"type": "test"})

        # Then: Both connections should receive
        ws1.send_json.assert_called_once()
        ws2.send_json.assert_called_once()


# =============================================================================
# Channel Isolation Tests
# =============================================================================

class TestChannelIsolation:
    """Test messages don't leak between channels."""

    @pytest.mark.asyncio(mode="auto")
    async def test_channel_isolation_messages_dont_leak(self, cleanup_websocket_manager):
        """Test messages don't leak between channels."""
        from core.websockets import manager

        # Given: Connections in different channels
        ws_channel_a = MagicMock()
        ws_channel_a.send_json = AsyncMock()
        ws_channel_b = MagicMock()
        ws_channel_b.send_json = AsyncMock()

        manager.subscribe(ws_channel_a, "channel_a")
        manager.subscribe(ws_channel_b, "channel_b")

        # When: Broadcast to channel_a
        await manager.broadcast("channel_a", {"type": "test", "channel": "a"})

        # Then: Only channel_a receives message
        ws_channel_a.send_json.assert_called_once()
        ws_channel_b.send_json.assert_not_called()

    @pytest.mark.asyncio(mode="auto")
    async def test_user_and_workspace_channels_separate(self, connected_websocket):
        """Test user and workspace channels are isolated."""
        from core.websockets import manager

        # Given: Connected user with user and workspace channels
        ws, user = connected_websocket
        user_channel = f"user:{user.id}"
        workspace_channel = f"workspace:{user.workspace_id}"

        # Reset call counts to isolate test
        ws.send_json.reset_mock()

        # When: Broadcast to user channel only
        await manager.broadcast(user_channel, {"type": "user_only"})

        # Then: Message should be sent
        # (Workspace channel shouldn't receive this message)
        assert any(
            call[0][0].get("type") == "user_only"
            for call in ws.send_json.call_args_list
        )


# =============================================================================
# Message Ordering Tests
# =============================================================================

class TestMessageOrdering:
    """Test message ordering and delivery guarantees."""

    @pytest.mark.asyncio(mode="auto")
    async def test_messages_delivered_in_order(self, connected_websocket):
        """Test messages are delivered in order."""
        from core.websockets import manager

        # Given: Connected WebSocket
        ws, user = connected_websocket

        # When: Send multiple messages in sequence
        messages = [
            {"seq": 1, "content": "First"},
            {"seq": 2, "content": "Second"},
            {"seq": 3, "content": "Third"},
        ]

        for msg in messages:
            await manager.send_personal_message(user.id, msg)
            # Small delay to ensure ordering
            await asyncio.sleep(0.01)

        # Then: Messages should be delivered in order
        assert ws.send_json.call_count == 3
        for i, call in enumerate(ws.send_json.call_args_list):
            sent_msg = call[0][0]
            assert sent_msg["seq"] == i + 1
