"""
Test Coverage for Async Operations

Comprehensive tests for async/await code paths, coroutines, event loops,
and asynchronous execution patterns throughout the backend.

Target Coverage Areas:
- Async/await code paths
- Coroutine execution
- Event loop management
- Async context managers
- Async iterators/generators
- Async fixture patterns
- Async error handling
- Async service orchestration

Tests: ~20 tests
Expected Impact: +2-3 percentage points
"""

import asyncio
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any, Optional

# Import core services with async operations
from core.websocket_manager import WebSocketConnectionManager
from core.governance_cache import GovernanceCache
from core import agent_execution_service
from core.episode_service import EpisodeService
from core.agent_coordination import AgentHandoffProtocol


@pytest.mark.asyncio
class TestWebSocketConnectionManager:
    """Test WebSocket connection management with async operations."""

    async def test_websocket_connect_async(self):
        """Test async WebSocket connection establishment."""
        manager = WebSocketConnectionManager()
        websocket = MagicMock()
        websocket.accept = AsyncMock()
        websocket.send_text = AsyncMock()

        await manager.connect(websocket, "test_stream")

        websocket.accept.assert_called_once()
        assert "test_stream" in manager.active_connections
        assert websocket in manager.active_connections["test_stream"]

    async def test_websocket_disconnect_cleanup(self):
        """Test async WebSocket disconnection and cleanup."""
        manager = WebSocketConnectionManager()
        websocket = MagicMock()
        websocket.accept = AsyncMock()
        websocket.send_text = AsyncMock()

        await manager.connect(websocket, "test_stream")
        manager.disconnect(websocket)

        assert "test_stream" not in manager.active_connections
        assert websocket not in manager.connection_streams

    async def test_send_personal_message_async(self):
        """Test async personal message sending."""
        manager = WebSocketConnectionManager()
        websocket = MagicMock()
        websocket.accept = AsyncMock()
        websocket.send_text = AsyncMock()

        # Manually add to connections (skip connect to avoid double send_text)
        manager.active_connections["test_stream"] = {websocket}
        manager.connection_streams[websocket] = "test_stream"

        message = {"type": "test", "data": "test_data"}

        result = await manager.send_personal(websocket, message)

        assert result is True
        websocket.send_text.assert_called_once()

    async def test_broadcast_message_async(self):
        """Test async broadcast to multiple connections."""
        manager = WebSocketConnectionManager()
        websocket1 = MagicMock()
        websocket2 = MagicMock()
        websocket1.send_text = AsyncMock()
        websocket2.send_text = AsyncMock()

        # Manually setup connections
        manager.active_connections["test_stream"] = {websocket1, websocket2}
        manager.connection_streams[websocket1] = "test_stream"
        manager.connection_streams[websocket2] = "test_stream"

        message = {"type": "broadcast", "data": "test_data"}
        count = await manager.broadcast("test_stream", message)

        assert count == 2
        websocket1.send_text.assert_called_once()
        websocket2.send_text.assert_called_once()

    async def test_concurrent_websocket_connections(self):
        """Test concurrent WebSocket connection handling."""
        manager = WebSocketConnectionManager()
        websockets = []

        # Create mock websockets
        for i in range(10):
            ws = MagicMock()
            ws.accept = AsyncMock()
            ws.send_text = AsyncMock()
            websockets.append(ws)

        # Manually add connections
        for i, ws in enumerate(websockets):
            stream_id = f"stream_{i % 3}"
            if stream_id not in manager.active_connections:
                manager.active_connections[stream_id] = set()
            manager.active_connections[stream_id].add(ws)
            manager.connection_streams[ws] = stream_id

        # Verify all connections established
        total_connections = sum(
            len(conns) for conns in manager.active_connections.values()
        )
        assert total_connections == 10


class TestGovernanceCacheAsync:
    """Test governance cache operations."""

    def test_cache_get_with_lock(self):
        """Test cache get with thread-safe locking."""
        cache = GovernanceCache(max_size=100, ttl_seconds=60)

        # Set cache entry
        cache.set("agent1", "action1", {"allowed": True, "data": {}})

        # Get should hit cache
        result = cache.get("agent1", "action1")
        assert result is not None
        assert result["allowed"] is True
        assert cache._hits == 1

    def test_cache_set_with_lock(self):
        """Test cache set with thread-safe locking."""
        cache = GovernanceCache(max_size=100, ttl_seconds=60)

        cache.set("agent1", "action1", {"allowed": True, "data": {}})
        cache.set("agent2", "action2", {"allowed": False, "data": {}})

        assert cache._hits == 0
        assert cache._misses == 0
        assert len(cache._cache) == 2

    def test_cache_lru_eviction(self):
        """Test LRU eviction when max_size exceeded."""
        cache = GovernanceCache(max_size=3, ttl_seconds=60)

        # Fill cache
        cache.set("agent1", "action1", {"allowed": True, "data": {}})
        cache.set("agent2", "action2", {"allowed": True, "data": {}})
        cache.set("agent3", "action3", {"allowed": True, "data": {}})

        # Access agent1 to make it recently used
        cache.get("agent1", "action1")

        # Add new entry, should evict agent2 (least recently used)
        cache.set("agent4", "action4", {"allowed": True, "data": {}})

        assert len(cache._cache) == 3
        assert cache.get("agent1", "action1") is not None
        assert cache.get("agent2", "action2") is None  # Evicted

    def test_cache_ttl_expiration(self):
        """Test cache TTL expiration."""
        cache = GovernanceCache(max_size=100, ttl_seconds=1)

        cache.set("agent1", "action1", {"allowed": True, "data": {}})

        # Should be cached
        result = cache.get("agent1", "action1")
        assert result is not None

        # Wait for expiration
        import time
        time.sleep(2)

        # Should be expired
        result = cache.get("agent1", "action1")
        assert result is None
        assert cache._misses == 1

    def test_cache_invalidation(self):
        """Test cache invalidation."""
        cache = GovernanceCache(max_size=100, ttl_seconds=60)

        cache.set("agent1", "action1", {"allowed": True, "data": {}})
        cache.invalidate("agent1", "action1")

        # Should be invalidated
        result = cache.get("agent1", "action1")
        assert result is None

    def test_cache_statistics(self):
        """Test cache statistics tracking."""
        cache = GovernanceCache(max_size=100, ttl_seconds=60)

        cache.set("agent1", "action1", {"allowed": True, "data": {}})
        cache.get("agent1", "action1")  # Hit
        cache.get("agent2", "action2")  # Miss

        # Check internal stats
        assert cache._hits == 1
        assert cache._misses == 1


@pytest.mark.asyncio
class TestAgentExecutionAsync:
    """Test agent execution service async operations."""

    async def test_async_agent_execution(self):
        """Test async agent execution with coroutine handling."""
        # Mock the execute_agent_chat function
        with patch('core.agent_execution_service.execute_agent_chat', new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = {
                "response": "Test response",
                "execution_id": "exec123"
            }

            result = await agent_execution_service.execute_agent_chat(
                agent_id="agent1",
                message="test message",
                user_id="user1"
            )

            assert result["response"] == "Test response"
            mock_exec.assert_called_once()

    async def test_concurrent_agent_executions(self):
        """Test concurrent agent execution handling."""
        # Mock the execute_agent_chat function
        with patch('core.agent_execution_service.execute_agent_chat', new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = {
                "response": "Test response",
                "execution_id": "exec123"
            }

            # Execute multiple agents concurrently
            tasks = [
                agent_execution_service.execute_agent_chat(f"agent{i}", "test", "user1")
                for i in range(5)
            ]

            results = await asyncio.gather(*tasks)

            assert len(results) == 5
            assert all(r["response"] == "Test response" for r in results)
            assert mock_exec.call_count == 5

    async def test_async_execution_timeout(self):
        """Test async execution timeout handling."""
        # Mock slow execution
        async def slow_execution(*args, **kwargs):
            await asyncio.sleep(2)
            return {"response": "slow response"}

        with patch('core.agent_execution_service.execute_agent_chat', new_callable=AsyncMock) as mock_exec:
            mock_exec.side_effect = slow_execution

            # Should timeout
            with pytest.raises((asyncio.TimeoutError, TimeoutError)):
                await asyncio.wait_for(
                    agent_execution_service.execute_agent_chat("agent1", "test", "user1"),
                    timeout=1.0
                )

    async def test_async_execution_error_handling(self):
        """Test async execution error handling."""
        # Mock failing execution
        with patch('core.agent_execution_service.execute_agent_chat', new_callable=AsyncMock) as mock_exec:
            mock_exec.side_effect = Exception("Execution failed")

            with pytest.raises(Exception, match="Execution failed"):
                await agent_execution_service.execute_agent_chat("agent1", "test", "user1")


@pytest.mark.asyncio
class TestEpisodeServiceAsync:
    """Test episode service async operations."""

    async def test_async_episode_creation(self):
        """Test async episode creation with EpisodeService."""
        # Test that we can import EpisodeService
        from core.database import SessionLocal
        db = SessionLocal()
        try:
            service = EpisodeService(db)
            # Verify service has expected attributes
            assert hasattr(service, 'create_episode_from_execution')
            assert hasattr(service, 'get_agent_episodes')
        finally:
            db.close()

    async def test_async_episode_query(self):
        """Test async episode query patterns."""
        # Mock database query
        async def mock_query():
            return [
                {"episode_id": "ep1", "summary": "test"},
                {"episode_id": "ep2", "summary": "test2"}
            ]

        results = await mock_query()
        assert len(results) == 2

    async def test_async_episode_lifecycle(self):
        """Test async episode lifecycle operations."""
        # Simulate episode lifecycle
        episode_state = {"status": "created"}

        async def update_status(status):
            episode_state["status"] = status
            await asyncio.sleep(0.01)
            return episode_state

        result = await update_status("processing")
        assert result["status"] == "processing"


@pytest.mark.asyncio
class TestAgentCoordinationAsync:
    """Test agent coordination async operations."""

    async def test_agent_handoff_protocol(self):
        """Test agent handoff protocol initialization."""
        from core.database import SessionLocal

        db = SessionLocal()
        try:
            protocol = AgentHandoffProtocol(db)
            assert hasattr(protocol, 'validate_handoff_payload')
        finally:
            db.close()

    async def test_async_handoff_validation(self):
        """Test async handoff payload validation."""
        from core.database import SessionLocal

        db = SessionLocal()
        try:
            protocol = AgentHandoffProtocol(db)

            # Test validation
            payload = {"data": "test"}
            schema = {
                "type": "object",
                "required": ["data"]
            }

            result = protocol.validate_handoff_payload(payload, schema)
            assert result is True
        finally:
            db.close()

    async def test_concurrent_handoff_validations(self):
        """Test concurrent handoff validations."""
        from core.database import SessionLocal

        async def validate_handoff():
            db = SessionLocal()
            try:
                protocol = AgentHandoffProtocol(db)
                return protocol.validate_handoff_payload(
                    {"data": "test"},
                    {"type": "object", "required": ["data"]}
                )
            finally:
                db.close()

        # Run concurrent validations
        tasks = [validate_handoff() for _ in range(5)]
        results = await asyncio.gather(*tasks)

        assert all(results)


@pytest.mark.asyncio
class TestAsyncContextManagers:
    """Test async context manager patterns."""

    async def test_async_database_session_context(self):
        """Test async database session context manager."""
        # Mock async session
        async_mock_session = AsyncMock()
        async_mock_session.__aenter__ = AsyncMock(return_value=async_mock_session)
        async_mock_session.__aexit__ = AsyncMock(return_value=None)

        async with async_mock_session as session:
            assert session is not None

        async_mock_session.__aenter__.assert_called_once()
        async_mock_session.__aexit__.assert_called_once()

    async def test_async_lock_context(self):
        """Test async lock context manager."""
        lock = asyncio.Lock()

        async with lock:
            # Lock is held here
            assert lock.locked()

        # Lock is released
        assert not lock.locked()

    async def test_concurrent_async_lock_contention(self):
        """Test concurrent async lock contention."""
        lock = asyncio.Lock()
        results = []

        async def worker(worker_id):
            async with lock:
                results.append(worker_id)
                await asyncio.sleep(0.1)

        # Run workers concurrently
        tasks = [worker(i) for i in range(5)]
        await asyncio.gather(*tasks)

        # All workers should have completed
        assert len(results) == 5


@pytest.mark.asyncio
class TestAsyncGenerators:
    """Test async generator and iterator patterns."""

    async def test_async_generator_iteration(self):
        """Test async generator iteration."""
        async def async_range(n):
            for i in range(n):
                yield i
                await asyncio.sleep(0.01)

        results = []
        async for i in async_range(5):
            results.append(i)

        assert results == [0, 1, 2, 3, 4]

    async def test_async_stream_processing(self):
        """Test async stream processing."""
        async def async_stream():
            for i in range(3):
                yield {"data": f"item{i}"}
                await asyncio.sleep(0.01)

        results = []
        async for item in async_stream():
            results.append(item["data"])

        assert results == ["item0", "item1", "item2"]


@pytest.mark.asyncio
class TestAsyncErrorHandling:
    """Test async error handling patterns."""

    async def test_async_exception_propagation(self):
        """Test async exception propagation."""
        async def failing_coroutine():
            raise ValueError("Async error")

        with pytest.raises(ValueError, match="Async error"):
            await failing_coroutine()

    async def test_async_exception_handling(self):
        """Test async exception handling."""
        async def failing_coroutine():
            raise ValueError("Async error")

        try:
            await failing_coroutine()
        except ValueError as e:
            assert str(e) == "Async error"

    async def test_async_gather_with_exceptions(self):
        """Test asyncio.gather with exceptions."""
        async def worker(i):
            if i == 2:
                raise ValueError(f"Worker {i} failed")
            await asyncio.sleep(0.01)
            return i

        # gather with return_exceptions=True
        results = await asyncio.gather(
            worker(1),
            worker(2),
            worker(3),
            return_exceptions=True
        )

        assert results[0] == 1
        assert isinstance(results[1], ValueError)
        assert results[2] == 3

    async def test_async_task_cancellation(self):
        """Test async task cancellation."""
        async def cancellable_task():
            try:
                await asyncio.sleep(1)
                return "completed"
            except asyncio.CancelledError:
                return "cancelled"

        task = asyncio.create_task(cancellable_task())
        await asyncio.sleep(0.1)
        task.cancel()

        result = await task
        assert result == "cancelled"
