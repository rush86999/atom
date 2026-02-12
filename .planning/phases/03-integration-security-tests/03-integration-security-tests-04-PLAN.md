# WebSocket Integration Tests with Async Patterns

**Phase**: 03 - Integration & Security Tests
**Plan**: 04 - WebSocket Integration Tests
**Status**: Pending
**Priority**: P1 (High)

## Objective

Build comprehensive integration tests for WebSocket connections, testing real-time messaging, streaming, agent execution updates, and proper async coordination patterns.

## Success Criteria

1. WebSocket connection lifecycle is tested (connect, disconnect, reconnect)
2. Real-time messaging is tested (chat, notifications, status updates)
3. Streaming LLM responses are tested (token-by-token streaming)
4. Agent execution updates are tested (progress, completion, errors)
5. WebSocket authentication and authorization are tested
6. WebSocket error handling is tested (connection failures, malformed messages)
7. Async patterns are properly tested (asyncio, async/await)
8. At least 10% increase in overall code coverage

## Key Areas to Cover

### WebSocket Connection Tests
```python
import pytest
from httpx import AsyncClient
from fastapi.testclient import TestClient

@pytest.mark.asyncio
async def test_websocket_connection():
    """Test WebSocket connection establishment"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        async with client.websocket_connect("/ws/chat") as websocket:
            # Send connection message
            await websocket.send_json({"type": "connect", "user_id": "test"})

            # Receive welcome message
            data = await websocket.receive_json()
            assert data["type"] == "connected"
            assert "connection_id" in data

@pytest.mark.asyncio
async def test_websocket_authentication():
    """Test WebSocket requires authentication"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        with pytest.raises(Exception):  # Should fail without auth
            async with client.websocket_connect("/ws/chat") as websocket:
                await websocket.receive_json()

@pytest.mark.asyncio
async def test_websocket_with_valid_token():
    """Test WebSocket connection with valid JWT token"""
    token = create_test_token()
    async with AsyncClient(app=app, base_url="http://test") as client:
        async with client.websocket_connect(
            f"/ws/chat?token={token}"
        ) as websocket:
            data = await websocket.receive_json()
            assert data["type"] == "connected"
```

### Real-time Messaging Tests
```python
@pytest.mark.asyncio
async def test_send_and_receive_message():
    """Test sending and receiving messages via WebSocket"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        async with client.websocket_connect("/ws/chat") as websocket:
            # Send message
            await websocket.send_json({
                "type": "message",
                "content": "Hello, World!"
            })

            # Receive echo or response
            response = await websocket.receive_json()
            assert response["type"] == "message"
            assert "content" in response

@pytest.mark.asyncio
async def test_multiple_clients():
    """Test multiple WebSocket clients can connect simultaneously"""
    async with AsyncClient(app=app, base_url="http://test") as client1, \
                  AsyncClient(app=app, base_url="http://test") as client2:

        async with client1.websocket_connect("/ws/chat") as ws1, \
                   client2.websocket_connect("/ws/chat") as ws2:

            # Client 1 sends message
            await ws1.send_json({
                "type": "broadcast",
                "content": "Broadcast message"
            })

            # Client 2 should receive broadcast
            data = await ws2.receive_json()
            assert data["content"] == "Broadcast message"
```

### Streaming LLM Tests
```python
@pytest.mark.asyncio
async def test_streaming_llm_response():
    """Test token-by-token streaming of LLM responses"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        async with client.websocket_connect("/ws/agent/stream") as websocket:
            # Send agent request
            await websocket.send_json({
                "agent_id": "test-agent",
                "prompt": "Tell me a joke"
            })

            # Receive streaming tokens
            tokens = []
            while True:
                data = await websocket.receive_json()
                if data["type"] == "token":
                    tokens.append(data["token"])
                elif data["type"] == "done":
                    break

            assert len(tokens) > 0
            full_response = "".join(tokens)
            assert len(full_response) > 0

@pytest.mark.asyncio
async def test_streaming_with_error():
    """Test streaming handles errors gracefully"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        async with client.websocket_connect("/ws/agent/stream") as websocket:
            # Send invalid request
            await websocket.send_json({
                "agent_id": "non-existent",
                "prompt": "Test"
            })

            # Should receive error message
            data = await websocket.receive_json()
            assert data["type"] == "error"
            assert "message" in data
```

### Agent Execution Updates Tests
```python
@pytest.mark.asyncio
async def test_agent_execution_progress():
    """Test agent execution progress updates via WebSocket"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        async with client.websocket_connect("/ws/agent/execute") as websocket:
            # Start agent execution
            await websocket.send_json({
                "agent_id": "test-agent",
                "action": "test_action"
            })

            # Receive progress updates
            updates = []
            while True:
                data = await websocket.receive_json()
                if data["type"] == "progress":
                    updates.append(data)
                elif data["type"] == "complete":
                    break

            assert len(updates) > 0

@pytest.mark.asyncio
async def test_agent_execution_error():
    """Test agent execution error via WebSocket"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        async with client.websocket_connect("/ws/agent/execute") as websocket:
            # Send invalid action
            await websocket.send_json({
                "agent_id": "test-agent",
                "action": "invalid_action"
            })

            # Should receive error
            data = await websocket.receive_json()
            assert data["type"] == "error"
```

### WebSocket Error Handling Tests
```python
@pytest.mark.asyncio
async def test_websocket_connection_failure():
    """Test WebSocket handles connection failures"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        with pytest.raises(Exception):
            async with client.websocket_connect("/ws/invalid") as websocket:
                await websocket.receive_json()

@pytest.mark.asyncio
async def test_websocket_malformed_message():
    """Test WebSocket handles malformed messages"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        async with client.websocket_connect("/ws/chat") as websocket:
            # Send invalid JSON
            await websocket.send_text("invalid json")

            # Should receive error or disconnect
            with pytest.raises(Exception):
                await websocket.receive_json()

@pytest.mark.asyncio
async def test_websocket_timeout():
    """Test WebSocket handles timeout"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        async with client.websocket_connect("/ws/chat?timeout=1") as websocket:
            # Wait for timeout
            with pytest.raises(Exception):
                await websocket.receive_json(timeout=5)
```

## Tasks

### Wave 1: WebSocket Connection Tests (Priority: P0)

- [ ] **Task 1.1**: Create `backend/tests/integration/websocket/test_connection.py`
  - Test WebSocket connection establishment
  - Test WebSocket authentication
  - Test WebSocket with valid token
  - Test WebSocket disconnect
  - Test WebSocket reconnection
  - **Acceptance**: All connection scenarios tested

- [ ] **Task 1.2**: Create `backend/tests/integration/websocket/test_messaging.py`
  - Test send and receive message
  - Test multiple clients
  - Test broadcast messages
  - Test private messages
  - **Acceptance**: All messaging scenarios tested

- [ ] **Task 1.3**: Create `backend/tests/integration/websocket/test_streaming.py`
  - Test streaming LLM response
  - Test streaming token-by-token
  - Test streaming completion
  - Test streaming with error
  - **Acceptance**: All streaming scenarios tested

### Wave 2: Agent Execution Tests (Priority: P0)

- [ ] **Task 2.1**: Create `backend/tests/integration/websocket/test_agent_execution.py`
  - Test agent execution progress
  - Test agent execution completion
  - Test agent execution error
  - Test agent execution cancellation
  - **Acceptance**: All agent execution scenarios tested

- [ ] **Task 2.2**: Create `backend/tests/integration/websocket/test_agent_updates.py`
  - Test agent status updates
  - Test agent log updates
  - Test agent result updates
  - **Acceptance**: All update scenarios tested

### Wave 3: WebSocket Error Handling (Priority: P1)

- [ ] **Task 3.1**: Create `backend/tests/integration/websocket/test_error_handling.py`
  - Test WebSocket connection failure
  - Test WebSocket malformed message
  - Test WebSocket timeout
  - Test WebSocket disconnection
  - **Acceptance**: All error scenarios tested

- [ ] **Task 3.2**: Create `backend/tests/integration/websocket/test_async_patterns.py`
  - Test async/await patterns
  - Test asyncio coordination
  - Test concurrent connections
  - **Acceptance**: All async patterns tested

### Wave 4: Coverage & Verification (Priority: P1)

- [ ] **Task 4.1**: Run coverage report on WebSocket tests
  - Generate coverage report
  - Identify uncovered lines
  - **Acceptance**: Coverage report generated

- [ ] **Task 4.2**: Add missing tests
  - Review uncovered lines
  - Add edge case tests
  - **Acceptance**: At least 10% increase in coverage

- [ ] **Task 4.3**: Verify all tests pass
  - Run full WebSocket test suite
  - Fix failures
  - **Acceptance**: All WebSocket tests passing

## Dependencies

- Phase 1 (Test Infrastructure) - Complete
- Phase 2 (Core Property Tests) - Complete
- WebSocket server implemented
- Async test infrastructure available

## Estimated Time

- Wave 1: 3-4 hours
- Wave 2: 2-3 hours
- Wave 3: 2-3 hours
- Wave 4: 1-2 hours
- **Total**: 8-12 hours

## Definition of Done

1. WebSocket connection lifecycle tested
2. Real-time messaging tested
3. Streaming LLM responses tested
4. Agent execution updates tested
5. WebSocket authentication tested
6. WebSocket error handling tested
7. Async patterns tested
8. At least 10% increase in overall code coverage
9. All tests passing
10. Documentation updated

## Verification Checklist

- [ ] Connection lifecycle tested
- [ ] Real-time messaging tested
- [ ] Streaming responses tested
- [ ] Agent execution updates tested
- [ ] Authentication tested
- [ ] Error handling tested
- [ ] Async patterns tested
- [ ] Coverage increased by at least 10%
- [ ] All tests passing
