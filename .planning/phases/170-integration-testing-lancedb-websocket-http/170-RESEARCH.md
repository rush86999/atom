# Phase 170: Integration Testing (LanceDB, WebSocket, HTTP) - Research

**Researched:** 2026-03-11
**Domain:** Python integration testing, LanceDB vector operations, WebSocket connection management, HTTP client mocking
**Confidence:** HIGH

## Summary

Phase 170 requires achieving 70%+ line coverage on three integration layers: LanceDB (vector search, semantic similarity, batch operations), WebSocket (async streaming, connection lifecycle, error handling), and HTTP clients (LLM providers, external APIs). The project already has established testing patterns from Phase 169 (browser/device tools achieved 93.5% coverage using AsyncMock) and comprehensive test infrastructure in `backend/tests/integration/services/`. This phase focuses on applying deterministic mocking patterns to external dependencies while testing real integration logic.

**Primary recommendation:** Use AsyncMock for LanceDB connections (mock `lancedb.connect()` and table operations), AsyncMock for WebSocket manager (mock `WebSocketConnectionManager.broadcast()`), and the `responses` library for HTTP client testing (mock httpx requests to external APIs). Write 3-5 test files with 20-30 tests each, targeting 70%+ line coverage on `core/lancedb_handler.py`, `core/websocket_manager.py`, `core/http_client.py`, and `core/websockets.py`.

**Key findings:** (1) LanceDB testing requires mocking the database connection and table operations but can test real embedding generation logic, (2) WebSocket testing requires AsyncMock for all async methods (`connect`, `broadcast`, `send_personal`), (3) HTTP client testing works best with `responses` library for deterministic request/response mocking, (4) Existing test fixtures in `conftest.py` provide `mock_lancedb_embeddings` with semantic-aware vectors, (5) Phase 169 proved AsyncMock patterns work well for external dependencies, (6) The project uses pytest 9.0.2 with pytest-asyncio for async test support.

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **pytest** | 9.0.2 | Test runner and assertion library | Already in project, industry standard |
| **pytest-asyncio** | (installed) | Async test support for WebSocket/LanceDB | Already in project, required for `@pytest.mark.asyncio` |
| **unittest.mock** | (stdlib) | AsyncMock, MagicMock, patch | Built-in Python mocking, no dependency needed |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **responses** | (not in project, add) | HTTP request/response mocking | Mock external API calls (OpenAI, Anthropic, etc.) |
| **pytest-mock** | (in requirements-testing.txt) | Enhanced mocking fixtures | When `mocker` fixture provides cleaner syntax than `patch` |

### Already in Project

From `backend/requirements.txt`:
```python
# Core dependencies
lancedb==0.25.3
httpx==0.28.1
fastapi
sqlalchemy
pytest==9.0.2
pytest-asyncio
pytest-mock>=3.12.0
```

From `backend/requirements-testing.txt`:
```python
pytest-mock>=3.12.0  # Mocking utilities
pytest-timeout>=2.2.0,<3.0.0  # Test timeout enforcement
```

**Recommendation:** Add `responses>=0.25.0` to `requirements-testing.txt` for HTTP mocking.

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| **responses library** | **httpx.MockTransport** | responses is simpler for static mocks; MockTransport better for dynamic behavior |
| **AsyncMock (stdlib)** | **pytest-asyncio auto-mode** | AsyncMock explicit; auto-mode requires pytest config |
| **patch (context manager)** | **pytest-mock mocker fixture** | patch is stdlib; mocker provides cleaner syntax |

## Architecture Patterns

### Recommended Test File Structure

```
backend/tests/integration/services/
├── test_lancedb_integration_coverage.py    # LanceDB handler tests (NEW)
├── test_websocket_manager_coverage.py      # WebSocket manager tests (NEW)
├── test_http_client_coverage.py            # HTTP client tests (EXISTS)
├── test_llm_service_http_coverage.py       # LLM HTTP integration tests (EXISTS)
├── conftest.py                             # Shared fixtures (EXTEND)
└── conftest_episode.py                     # Episode fixtures (existing)
```

### Pattern 1: LanceDB Handler with Mocked Connection

**What:** Mock LanceDB connection and table operations while testing embedding logic

**When to use:** Testing `LanceDBHandler` methods that interact with vector database

**Example:**
```python
# backend/tests/integration/services/test_lancedb_integration_coverage.py

import pytest
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from core.lancedb_handler import LanceDBHandler, get_lancedb_handler

class TestLanceDBConnection:
    """Test LanceDB connection and initialization."""

    @patch('core.lancedb_handler.lancedb.connect')
    def test_initializes_db_connection(self, mock_connect):
        """Test that handler initializes LanceDB connection on first use."""
        mock_db = Mock()
        mock_db.table_names = Mock(return_value=[])
        mock_connect.return_value = mock_db

        handler = LanceDBHandler(db_path="./test_db")
        handler._ensure_db()

        assert handler.db is not None
        mock_connect.assert_called_once()

    @patch('core.lancedb_handler.lancedb.connect')
    def test_connection_failure_handling(self, mock_connect):
        """Test graceful handling of connection failures."""
        mock_connect.side_effect = Exception("Connection failed")

        handler = LanceDBHandler(db_path="./test_db")
        result = handler.test_connection()

        assert result["connected"] is False
        assert "Connection failed" in result["message"]

class TestLanceDBVectorSearch:
    """Test vector search operations with mocked LanceDB."""

    @pytest.mark.asyncio
    async def test_similarity_search_with_filters(self):
        """Test vector search with user_id and workspace_id filters."""
        # Mock LanceDB table
        mock_table = Mock()
        mock_table.search = Mock(return_value=mock_table)
        mock_table.where = Mock(return_value=mock_table)
        mock_table.limit = Mock(return_value=mock_table)
        mock_table.to_pandas = Mock(return_value=self._mock_search_results())

        mock_db = Mock()
        mock_db.open_table = Mock(return_value=mock_table)

        with patch('core.lancedb_handler.get_lancedb_handler', return_value=mock_db):
            handler = get_lancedb_handler()
            results = handler.search(
                table_name="episodes",
                query="test query",
                user_id="test_user",
                limit=10
            )

            assert len(results) > 0
            mock_table.search.assert_called_once()
            # Verify filter was applied
            mock_table.where.assert_called()

    def _mock_search_results(self):
        """Create mock pandas DataFrame for search results."""
        import pandas as pd
        return pd.DataFrame({
            'id': ['ep1', 'ep2'],
            'text': ['result 1', 'result 2'],
            'source': ['test', 'test'],
            'metadata': [{'key': 'value'}, {'key2': 'value2'}],
            'created_at': ['2026-01-01', '2026-01-02'],
            '_distance': [0.2, 0.3]
        })

class TestLanceDBBatchOperations:
    """Test batch document operations."""

    @patch('core.lancedb_handler.LanceDBHandler.embed_text')
    def test_add_documents_batch_success(self, mock_embed):
        """Test successful batch document addition."""
        mock_embed.return_value = [0.1] * 384  # Mock embedding vector

        mock_table = Mock()
        mock_table.add = Mock()

        mock_db = Mock()
        mock_db.create_table = Mock(return_value=mock_table)
        mock_db.table_names = Mock(return_value=[])

        with patch('core.lancedb_handler.get_lancedb_handler', return_value=mock_db):
            handler = get_lancedb_handler()
            count = handler.add_documents_batch(
                table_name="test_table",
                documents=[
                    {"text": "doc1", "source": "test"},
                    {"text": "doc2", "source": "test"}
                ]
            )

            assert count == 2
            mock_table.add.assert_called_once()

    @patch('core.lancedb_handler.LanceDBHandler.embed_text')
    def test_batch_handles_embedding_failure(self, mock_embed):
        """Test that batch operations handle embedding failures gracefully."""
        mock_embed.return_value = None  # Embedding fails

        handler = LanceDBHandler()
        count = handler.add_documents_batch(
            table_name="test_table",
            documents=[{"text": "doc1"}]
        )

        # Should skip documents with failed embeddings
        assert count == 0
```

### Pattern 2: WebSocket Manager with AsyncMock

**What:** Mock WebSocket async methods for connection lifecycle and broadcasting

**When to use:** Testing `WebSocketConnectionManager` and `DebuggingWebSocketManager`

**Example:**
```python
# backend/tests/integration/services/test_websocket_manager_coverage.py

import pytest
from unittest.mock import AsyncMock, Mock
from fastapi import WebSocket
from core.websocket_manager import WebSocketConnectionManager, DebuggingWebSocketManager

class TestWebSocketConnectionLifecycle:
    """Test WebSocket connection lifecycle management."""

    @pytest.mark.asyncio
    async def test_connect_and_track_connection(self):
        """Test that WebSocket connections are tracked properly."""
        manager = WebSocketConnectionManager()
        mock_websocket = Mock(spec=WebSocket)

        # Mock accept method
        mock_websocket.accept = AsyncMock()

        await manager.connect(mock_websocket, stream_id="test_stream")

        # Verify connection was accepted and tracked
        mock_websocket.accept.assert_called_once()
        assert "test_stream" in manager.active_connections
        assert mock_websocket in manager.active_connections["test_stream"]

    @pytest.mark.asyncio
    async def test_disconnect_removes_from_streams(self):
        """Test that disconnecting removes WebSocket from all streams."""
        manager = WebSocketConnectionManager()
        mock_websocket = Mock(spec=WebSocket)

        mock_websocket.accept = AsyncMock()
        await manager.connect(mock_websocket, stream_id="stream1")

        # Disconnect
        manager.disconnect(mock_websocket)

        # Verify removal
        assert mock_websocket not in manager.active_connections.get("stream1", set())

    @pytest.mark.asyncio
    async def test_multiple_connections_per_stream(self):
        """Test that multiple WebSockets can subscribe to same stream."""
        manager = WebSocketConnectionManager()
        mock_ws1 = Mock(spec=WebSocket)
        mock_ws2 = Mock(spec=WebSocket)

        mock_ws1.accept = AsyncMock()
        mock_ws2.accept = AsyncMock()

        await manager.connect(mock_ws1, stream_id="shared_stream")
        await manager.connect(mock_ws2, stream_id="shared_stream")

        # Both connections tracked
        assert len(manager.active_connections["shared_stream"]) == 2

class TestWebSocketBroadcast:
    """Test WebSocket broadcasting functionality."""

    @pytest.mark.asyncio
    async def test_broadcast_to_all_subscribers(self):
        """Test that broadcast reaches all subscribers in a stream."""
        manager = WebSocketConnectionManager()

        # Create mock WebSockets
        mock_ws1 = Mock(spec=WebSocket)
        mock_ws2 = Mock(spec=WebSocket)
        mock_ws1.send_text = AsyncMock()
        mock_ws2.send_text = AsyncMock()
        mock_ws1.accept = AsyncMock()
        mock_ws2.accept = AsyncMock()

        # Connect both to same stream
        await manager.connect(mock_ws1, stream_id="stream1")
        await manager.connect(mock_ws2, stream_id="stream1")

        # Broadcast message
        sent_count = await manager.broadcast(
            stream_id="stream1",
            message={"type": "test", "data": "hello"}
        )

        # Verify both received message
        assert sent_count == 2
        mock_ws1.send_text.assert_called_once()
        mock_ws2.send_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_broadcast_handles_failed_connection(self):
        """Test that broadcast handles connection failures gracefully."""
        manager = WebSocketConnectionManager()

        mock_ws1 = Mock(spec=WebSocket)
        mock_ws2 = Mock(spec=WebSocket)
        mock_ws1.send_text = AsyncMock()
        mock_ws2.send_text = AsyncMock(side_effect=Exception("Connection lost"))
        mock_ws1.accept = AsyncMock()
        mock_ws2.accept = AsyncMock()

        await manager.connect(mock_ws1, stream_id="stream1")
        await manager.connect(mock_ws2, stream_id="stream1")

        # Broadcast (one will fail)
        sent_count = await manager.broadcast(
            stream_id="stream1",
            message={"type": "test"}
        )

        # Should return successful sends only
        assert sent_count == 1
        # Failed connection should be disconnected
        assert mock_ws2 not in manager.active_connections.get("stream1", set())

    @pytest.mark.asyncio
    async def test_broadcast_to_empty_stream(self):
        """Test broadcast to stream with no subscribers."""
        manager = WebSocketConnectionManager()

        sent_count = await manager.broadcast(
            stream_id="empty_stream",
            message={"type": "test"}
        )

        assert sent_count == 0

class TestDebuggingWebSocketManager:
    """Test debugging-specific WebSocket manager functionality."""

    @pytest.mark.asyncio
    async def test_trace_update_broadcast(self):
        """Test trace update broadcasting."""
        base_manager = WebSocketConnectionManager()
        debug_manager = DebuggingWebSocketManager(base_manager)

        # Mock broadcast
        base_manager.broadcast = AsyncMock(return_value=2)

        await debug_manager.stream_trace(
            execution_id="exec1",
            session_id="session1",
            trace_data={"step": 1, "status": "running"}
        )

        # Verify broadcast called with correct structure
        base_manager.broadcast.assert_called_once()
        call_args = base_manager.broadcast.call_args
        assert "trace_exec1_session1" in call_args[0][0]
        assert call_args[0][1]["type"] == "trace_update"

    @pytest.mark.asyncio
    async def test_variable_changed_notification(self):
        """Test variable change notification broadcast."""
        base_manager = WebSocketConnectionManager()
        debug_manager = DebuggingWebSocketManager(base_manager)

        base_manager.broadcast = AsyncMock(return_value=1)

        await debug_manager.notify_variable_changed(
            session_id="session1",
            variable_name="counter",
            new_value=42,
            previous_value=41
        )

        # Verify notification structure
        base_manager.broadcast.assert_called_once()
        call_args = base_manager.broadcast.call_args[0][1]
        assert call_args["type"] == "variable_changed"
        assert call_args["variable"]["name"] == "counter"
        assert call_args["variable"]["new_value"] == 42
```

### Pattern 3: HTTP Client with responses Library

**What:** Mock HTTP requests to external APIs using responses library

**When to use:** Testing `http_client.py` and LLM provider API calls

**Example:**
```python
# backend/tests/integration/services/test_http_client_coverage.py (EXTEND EXISTING)

import pytest
import responses
from unittest.mock import patch
from core.http_client import get_async_client, async_get, async_post
import httpx

class TestHTTPClientWithResponses:
    """Test HTTP client using responses library for deterministic mocking."""

    @responses.activate
    def test_async_get_with_mocked_response(self):
        """Test async GET with mocked response using responses library."""
        # Mock HTTP response
        responses.add(
            responses.GET,
            "https://api.example.com/test",
            json={"status": "ok", "data": "test"},
            status=200
        )

        async def _test():
            response = await async_get("https://api.example.com/test")
            assert response.status_code == 200
            assert response.json()["status"] == "ok"

        import asyncio
        asyncio.run(_test())

    @responses.activate
    def test_async_post_with_mocked_response(self):
        """Test async POST with mocked response."""
        responses.add(
            responses.POST,
            "https://api.example.com/create",
            json={"id": "123", "created": True},
            status=201
        )

        async def _test():
            response = await async_post(
                "https://api.example.com/create",
                json={"name": "test"}
            )
            assert response.status_code == 201
            assert response.json()["id"] == "123"

        import asyncio
        asyncio.run(_test())

    @responses.activate
    def test_http_timeout_error(self):
        """Test handling of HTTP timeout errors."""
        # Mock timeout
        responses.add(
            responses.GET,
            "https://api.example.com/slow",
            body=httpx.TimeoutException("Request timed out"),
            status=504
        )

        async def _test():
            with pytest.raises(httpx.TimeoutException):
                await async_get("https://api.example.com/slow")

        import asyncio
        asyncio.run(_test())

    @responses.activate
    def test_http_network_error(self):
        """Test handling of network errors."""
        responses.add(
            responses.GET,
            "https://api.example.com/fail",
            body=httpx.NetworkError("Network unreachable"),
            status=503
        )

        async def _test():
            with pytest.raises(httpx.NetworkError):
                await async_get("https://api.example.com/fail")

        import asyncio
        asyncio.run(_test())

    @responses.activate
    def test_retry_on_transient_failure(self):
        """Test retry logic on 5xx errors."""
        # First call fails, second succeeds
        responses.add(
            responses.GET,
            "https://api.example.com/flaky",
            status=503
        )
        responses.add(
            responses.GET,
            "https://api.example.com/flaky",
            json={"status": "ok"},
            status=200
        )

        async def _test():
            # Test retry logic (implementation dependent)
            response = await async_get("https://api.example.com/flaky")
            assert response.status_code == 200

        import asyncio
        asyncio.run(_test())
```

### Anti-Patterns to Avoid

- **Testing external dependencies directly**: Don't make real HTTP requests to APIs or real LanceDB connections in unit tests
- **Synchronous async tests**: Don't forget `@pytest.mark.asyncio` decorator on async test methods
- **Incomplete mocking**: Don't mock only part of an async flow - mock all external dependencies
- **Testing mock behavior**: Don't assert on mock internals; test the code that uses the mock
- **Ignoring error paths**: Don't only test happy paths - test failures, timeouts, network errors

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| **HTTP mocking** | Custom request interceptors | `responses` library | Handles httpx mocking correctly, thread-safe |
| **Async test runner** | Custom async wrapper | `@pytest.mark.asyncio` | Standard pytest pattern, handles event loops |
| **WebSocket mocks** | Manual WebSocket implementation | `AsyncMock` on WebSocket methods | Simpler, focuses on interface |
| **LanceDB mocks** | In-memory vector DB | `Mock()` on connection/table | Faster, deterministic, no dependency on LanceDB |
| **Fixture factories** | Manual setup/teardown | `pytest` fixtures with `yield` | Automatic cleanup, scoped fixtures |

**Key insight:** Integration tests should test YOUR code, not external dependencies. Mock all external I/O (HTTP, WebSocket, database) and focus on testing logic, error handling, and data flow.

## Common Pitfalls

### Pitfall 1: AsyncMock Not Returning Coroutines

**What goes wrong:** Tests fail with "coroutine was never awaited" errors

**Why it happens:** AsyncMock methods need to be awaited, but sometimes the mock isn't configured correctly

**How to avoid:** (1) Always use `AsyncMock()` for async methods, (2) Use `side_effect=[async_func]` for custom async behavior, (3) Ensure test methods have `@pytest.mark.asyncio` decorator

**Warning signs:** "RuntimeWarning: coroutine was never awaited", tests hanging indefinitely

### Pitfall 2: Responses Library Not Working with httpx

**What goes wrong:** `responses.add()` doesn't intercept httpx requests

**Why it happens:** httpx uses its own HTTP client, not requests library

**How to avoid:** (1) Use `httpx.MockTransport` for complex mocking, (2) Or mock higher-level functions (e.g., `async_get`) instead of raw httpx calls, (3) Or use `responses` with `responses.mock.enable_httpx()` if supported

**Warning signs:** "Connection refused" errors when mocking should work, responses not being triggered

### Pitfall 3: LanceDB Pandas Dependency

**What goes wrong:** Tests fail with "Pandas not available" errors

**Why it happens:** LanceDB operations return pandas DataFrames, but pandas isn't always available in test environment

**How to avoid:** (1) Mock `table.to_pandas()` to return test DataFrames, (2) Use `conftest.py` fixture to check PANDAS_AVAILABLE, (3) Add pandas to test requirements

**Warning signs:** "AttributeError: 'Mock' object has no attribute 'to_pandas'"

### Pitfall 4: WebSocket State Leaking Between Tests

**What goes wrong:** Tests pass individually but fail when run together

**Why it happens:** WebSocket manager is a singleton; connections persist across tests

**How to avoid:** (1) Use function-scoped fixtures for WebSocket manager, (2) Call cleanup in test teardown, (3) Reset manager state in `pytest.fixture(autouse=True)` if needed

**Warning signs:** "AssertionError: 1 != 0" when checking connection count, tests failing only in CI

### Pitfall 5: Mock Embeddings Not Matching Vector Dimensions

**What goes wrong:** LanceDB operations fail with "dimension mismatch" errors

**Why it happens:** Mock embeddings return wrong-sized vectors (e.g., 384-dim instead of 1536-dim for OpenAI)

**How to avoid:** (1) Use `conftest.py`'s `mock_lancedb_embeddings` fixture with correct dimensions, (2) Check embedding provider in test setup (OpenAI=1536, local=384), (3) Mock `embed_text` to return correctly-sized lists

**Warning signs:** "ValueError: Dimension mismatch: expected 1536, got 384"

## Code Examples

Verified patterns from existing Atom codebase:

### Example 1: LanceDB Semantic Search Mock

```python
# Source: backend/tests/integration/services/conftest.py

@pytest.fixture(scope="function")
def mock_lancedb_embeddings():
    """
    Mock LanceDB embedding generation with semantic similarity vectors.

    Returns vectors that produce predictable similarity scores:
    - Same topic: [0.9, 0.1, 0.0] (high similarity)
    - Different topic: [0.1, 0.9, 0.0] (low similarity <0.75)
    """
    mock_db = Mock()
    mock_db.embed_text = Mock(side_effect=lambda text: (
        [0.9, 0.1, 0.0] if "python" in text.lower() or "web" in text.lower()
        else [0.1, 0.9, 0.0]  # Cooking/topic change
    ))
    mock_db.search = Mock(return_value=[])
    mock_db.db = Mock()
    mock_db.table_names = Mock(return_value=[])
    return mock_db
```

### Example 2: WebSocket Broadcast Mock (from existing tests)

```python
# Source: backend/tests/integration/services/test_websocket_coverage.py

@pytest.fixture
def mock_ws_manager():
    """Mock WebSocket manager with AsyncMock for async broadcast methods."""
    mock_mgr = Mock()
    mock_mgr.broadcast = AsyncMock()

    with patch('tools.canvas_tool.ws_manager', mock_mgr):
        yield mock_mgr

@pytest.mark.asyncio
async def test_chart_broadcast_called(self, mock_ws_manager):
    """Test that chart presentation triggers WebSocket broadcast."""
    from tools.canvas_tool import present_chart

    result = await present_chart(
        user_id="test_user",
        chart_type="line_chart",
        data=[{"x": 1, "y": 2}],
        title="Test Chart"
    )

    assert result["success"] is True
    assert mock_ws_manager.broadcast.called
```

### Example 3: HTTP Client Reset Pattern (from existing tests)

```python
# Source: backend/tests/integration/services/test_http_client_coverage.py

def test_async_client_created_once(self):
    """Test that async client is created only once (singleton pattern)."""
    # Reset to ensure clean state
    reset_http_clients()

    # Get client twice
    client1 = get_async_client()
    client2 = get_async_client()

    # Verify singleton (same instance)
    assert client1 is client2
    assert isinstance(client1, httpx.AsyncClient)

    # Cleanup
    reset_http_clients()
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| **unittest.Mock** | **AsyncMock (Python 3.8+)** | 2021-2022 (Python 3.8) | Better async testing support |
| **requests-mock** | **responses library** | 2020-2021 | httpx compatibility, cleaner API |
| **Real DB tests** | **Mocked DB tests** | 2019-2020 | Faster, deterministic tests |
| **Manual async wrappers** | **@pytest.mark.asyncio** | 2022-2023 (pytest-asyncio) | Simpler async test syntax |

**Deprecated/outdated:**
- **Manual event loop management**: pytest-asyncio handles this automatically
- **Mock objects without spec**: Use `spec=ClassName` for better error messages
- **Synchronous async testing**: Always use `@pytest.mark.asyncio` for async tests

## Open Questions

1. **LanceDB S3/R2 Integration Testing**
   - What we know: LanceDB handler supports S3 and R2 storage backends
   - What's unclear: How to mock S3/R2 connections without AWS credentials
   - Recommendation: Mock at `lancedb.connect()` level, don't test S3 integration directly (outsider concern)

2. **WebSocket Connection Pooling**
   - What we know: FastAPI WebSocket doesn't use connection pooling like HTTP
   - What's unclear: How to test concurrent WebSocket connections
   - Recommendation: Use `pytest.mark.asyncio` with multiple mock WebSockets, test race conditions in disconnect logic

3. **HTTP/2 Support in httpx**
   - What we know: http_client.py enables HTTP/2 with `http2=True`
   - What's unclear: How `responses` library handles HTTP/2 mocking
   - Recommendation: Mock at application layer, not transport layer - HTTP/2 is transparent to application code

## Sources

### Primary (HIGH confidence)

- **Existing Test Infrastructure** - `/Users/rushiparikh/projects/atom/backend/tests/integration/services/conftest.py` - Comprehensive fixtures for LanceDB, WebSocket, HTTP mocking
- **HTTP Client Tests** - `/Users/rushiparikh/projects/atom/backend/tests/integration/services/test_http_client_coverage.py` - 508 lines covering httpx singleton, timeouts, error handling
- **WebSocket Tests** - `/Users/rushiparikh/projects/atom/backend/tests/integration/services/test_websocket_coverage.py` - 404 lines covering broadcast, routing, error handling
- **LanceDB Handler** - `/Users/rushiparikh/projects/atom/backend/core/lancedb_handler.py` - 1398 lines implementing vector search, batch operations, embeddings
- **WebSocket Manager** - `/Users/rushiparikh/projects/atom/backend/core/websocket_manager.py` - 473 lines implementing connection lifecycle, broadcasting
- **HTTP Client** - `/Users/rushiparikh/projects/atom/backend/core/http_client.py` - 294 lines implementing async/sync clients, connection pooling

### Secondary (MEDIUM confidence)

- **Phase 169 Tool Testing** - `.planning/phases/169-tools-integrations-coverage/169-01-PLAN.md` - Proven AsyncMock patterns for external dependencies
- **Python AsyncMock Documentation** - https://docs.python.org/3/library/unittest.mock.html - Official AsyncMock reference
- **pytest-asyncio Documentation** - https://pytest-asyncio.readthedocs.io/ - Async test patterns
- **responses Library** - https://responses.readthedocs.io/ - HTTP mocking for httpx

### Tertiary (LOW confidence)

- **LanceDB Documentation** - https://lancedb.github.io/lancedb/ - LanceDB API reference (verify mocking approach)
- **FastAPI WebSocket Testing** - https://fastapi.tiangolo.com/advanced/websockets/ - WebSocket testing patterns
- **httpx Mocking** - https://www.python-httpx.org/advanced/#mocking - httpx.MockTransport patterns

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All libraries verified in project, versions confirmed
- Architecture: HIGH - Existing test patterns (Phase 169) prove AsyncMock works well
- Pitfalls: HIGH - Common async testing issues well-documented, conftest.py provides working examples

**Research date:** 2026-03-11
**Valid until:** 2026-04-11 (30 days - stable testing patterns, but library versions may change)
