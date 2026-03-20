# Phase 184: Integration Testing (Advanced) - Research

**Researched:** March 13, 2026
**Domain:** Advanced Integration Test Coverage (LanceDB, WebSocket, HTTP Client, Error Paths)
**Confidence:** HIGH

## Summary

Phase 184 targets 75%+ line coverage on three advanced integration components: LanceDB handler (currently 33% coverage, 1397 lines), WebSocket connection lifecycle (currently 97% coverage, 472 lines), and HTTP client connection pooling (currently 96% coverage, 293 lines). The phase also requires 75%+ coverage on integration error paths across these services. Existing tests provide strong foundation: 20 tests for LanceDB integration, 25 tests for WebSocket manager, 53 tests for HTTP client, but significant coverage gaps remain in LanceDB's advanced features (dual vector storage, knowledge graph operations, batch operations, S3/R2 storage, embedding providers).

**Primary recommendation:** Focus 80% of testing effort on LanceDB handler which has the lowest coverage (33%) and highest complexity. Build on Phase 183's AsyncMock patterns and module-level mocking strategies. For LanceDB, mock lancedb.connect() and table operations while testing real embedding logic, vector search flows, and error handling. For WebSocket and HTTP client, focus on the uncovered edge cases (reset_http_clients error paths, WebSocket connection lifecycle edge cases). Create dedicated error path test files for each service following the `tests/error_paths/` directory pattern established in earlier phases.

**Key insight:** LanceDB handler is the critical path - it represents 60% of the lines to cover (1397 of 2162 total). The handler has complex initialization flows (lazy loading, threading timeouts for model loading), dual vector storage (1024-dim ST + 384-dim FastEmbed), S3/R2 storage configuration, and multiple embedding providers (OpenAI, SentenceTransformers, MockEmbedder). Use 3-4 focused plans: Plan 01 for LanceDB initialization and connections, Plan 02 for LanceDB vector operations and search, Plan 03 for LanceDB knowledge graph and advanced features, Plan 04 for WebSocket/HTTP client edge cases and error paths.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pytest | 9.0.2 | Test framework | Industry standard with fixture support, async, coverage |
| pytest-cov | 7.0.0 | Coverage reporting | pytest-native coverage with --cov flag |
| pytest-asyncio | 0.24.x | Async test support | Required for LanceDB async methods, WebSocket tests |
| httpx | 0.27.x | HTTP client mocking | For HTTP client connection pooling tests |
| lancedb | 0.x+ | Vector database | Mock lancedb.connect() for integration tests |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| unittest.mock | stdlib | Mocking LanceDB/HTTP | All LanceDB operations require mocking external I/O |
| pytest-mock | 3.14.x | Mock fixture wrapper | Cleaner mocker.patch syntax than patch() |
| pandas | 2.x | DataFrame mocking | LanceDB search returns pandas DataFrames |
| numpy | 2.x | Vector operations | Mock embedding vectors for search tests |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| unittest.mock | testfixtures | unittest.mock is stdlib, sufficient for mocks |
| pytest-cov | coverage.py | pytest-cov integrates better with pytest CLI |
| Mock LanceDB | Real LanceDB | Real LanceDB requires I/O and is slower, mocks are deterministic |

**Installation:**
```bash
# All packages already installed in backend/
pip install pytest pytest-cov pytest-asyncio pytest-mock
pip install httpx lancedb pandas numpy
```

## Architecture Patterns

### Recommended Project Structure
```
backend/tests/integration/services/
├── test_lancedb_integration_coverage.py      # EXISTING (20 tests, 33% coverage)
├── test_lancedb_initialization.py            # NEW - LanceDB handler initialization
├── test_lancedb_vector_operations.py         # NEW - Vector search, embeddings, dual storage
├── test_lancedb_knowledge_graph.py           # NEW - Knowledge graph operations
├── test_lancedb_batch_operations.py          # NEW - Batch document insertion
├── test_lancedb_s3_storage.py                # NEW - S3/R2 storage configuration
├── test_websocket_manager_coverage.py        # EXISTING (25 tests, 97% coverage)
├── test_websocket_edge_cases.py              # NEW - WebSocket lifecycle edge cases
├── test_http_client_coverage.py              # EXISTING (53 tests, 96% coverage)
├── test_http_client_edge_cases.py            # NEW - Connection pooling edge cases
└── conftest.py                               # EXISTING - shared fixtures

backend/tests/error_paths/
├── test_lancedb_error_paths.py               # NEW - LanceDB error handling
├── test_websocket_error_paths.py             # NEW - WebSocket error paths
└── test_http_client_error_paths.py           # NEW - HTTP client error paths
```

### Pattern 1: Module-Level LanceDB Mocking
**What:** Mock lancedb at module level to avoid I/O dependencies
**When to use:** All LanceDB handler tests (connection, search, batch operations)
**Example:**
```python
# Source: backend/tests/integration/services/test_lancedb_integration_coverage.py
import sys
from unittest.mock import Mock, MagicMock

# Module-level mocking - patches lancedb BEFORE importing handler
sys.modules['lancedb'] = MagicMock()

mock_lancedb = MagicMock()
mock_lancedb.connect = Mock(return_value=mock_lancedb)
mock_lancedb.table_names = Mock(return_value=[])
sys.modules['lancedb'].connect = mock_lancedb.connect

# Now import handler - it will use mocked lancedb
from core.lancedb_handler import LanceDBHandler
```

### Pattern 2: Pandas DataFrame Mocking for Search Results
**What:** Mock pandas DataFrame for LanceDB search result parsing
**When to use:** Testing vector search, similarity_search(), document retrieval
**Example:**
```python
# Source: test_lancedb_integration_coverage.py (lines 146-150)
@pytest.fixture
def mock_search_results():
    """Mock LanceDB search results as pandas DataFrame."""
    import pandas as pd
    return pd.DataFrame({
        'id': ['ep1', 'ep2'],
        'text': ['result 1', 'result 2'],
        'source': ['test', 'test'],
        'metadata': [{'key': 'value'}, {'key': 'value2'}],
        'created_at': ['2026-01-01T00:00:00', '2026-01-01T01:00:00'],
        '_distance': [0.1, 0.2]
    })

# Usage in test
with patch.object(table, 'to_pandas', return_value=mock_search_results):
    results = handler.search(table_name="episodes", query="test", limit=10)
```

### Pattern 3: AsyncMock for WebSocket Manager
**What:** Use AsyncMock for WebSocket async methods (connect, broadcast, send_personal)
**When to use:** Testing WebSocketConnectionManager, DebuggingWebSocketManager
**Example:**
```python
# Source: test_websocket_manager_coverage.py pattern
from unittest.mock import AsyncMock, patch
import pytest

@pytest.mark.asyncio
async def test_broadcast_to_multiple_connections():
    """Test broadcasting message to all connections in a stream."""
    manager = WebSocketConnectionManager()

    # Mock WebSocket connections
    mock_ws1 = Mock()
    mock_ws2 = Mock()
    mock_ws1.send_text = AsyncMock()
    mock_ws2.send_text = AsyncMock()

    # Add connections to stream
    await manager.connect(mock_ws1, "test_stream")
    await manager.connect(mock_ws2, "test_stream")

    # Broadcast message
    sent_count = await manager.broadcast("test_stream", {"type": "test"})

    # Verify both connections received message
    assert sent_count == 2
    mock_ws1.send_text.assert_called_once()
    mock_ws2.send_text.assert_called_once()
```

### Pattern 4: HTTP Client Singleton Testing
**What:** Test HTTP client singleton pattern with reset_http_clients() cleanup
**When to use:** Testing connection pooling, client reuse, configuration
**Example:**
```python
# Source: test_http_client_coverage.py (lines 35-49)
def test_async_client_created_once():
    """Test that async client is created only once (singleton pattern)."""
    from core.http_client import get_async_client, reset_http_clients

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

### Anti-Patterns to Avoid
- **Real LanceDB connections in tests**: Always mock lancedb.connect() - real I/O is slow and flaky
- **Testing pandas in LanceDB tests**: Don't test pandas operations, mock DataFrames instead
- **WebSocket server in tests**: Don't start real WebSocket servers, mock WebSocket objects
- **HTTP requests to external services**: Mock httpx.AsyncClient responses, don't make real requests

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| LanceDB mocking | Custom lancedb mocks | unittest.mock.Mock + MagicMock | LanceDB has complex API, MagicMock handles unknown attributes |
| Async testing | Custom async test runners | pytest-asyncio with @pytest.mark.asyncio | Standard pytest async support, handles event loop cleanup |
| WebSocket testing | Real WebSocket servers | Mock WebSocket with AsyncMock.send_text | Real servers are flaky in CI, mocks are deterministic |
| HTTP testing | Real HTTP requests | httpx.MockTransport or patch client.get() | Real requests are slow, fail without network |
| Vector operations | Custom vector math | numpy arrays for mock embeddings | Numpy is standard, already dependency |

**Key insight:** Integration tests should test YOUR code, not external dependencies. Mock LanceDB, WebSocket, and HTTP clients to test handler logic, error handling, and data flow without I/O dependencies.

## Common Pitfalls

### Pitfall 1: Lazy Initialization Side Effects
**What goes wrong:** Tests fail because LanceDB handler has lazy initialization (db=None until first use). Mocking lancedb.connect() doesn't work if handler never calls _ensure_db().
**Why it happens:** LanceDBHandler.__init__() doesn't initialize db - it's lazy loaded on first _ensure_db() call
**How to avoid:** Call handler._ensure_db() or use handler methods that trigger _ensure_db() before setting assertions. Or manually set handler.db = mock_db after initialization.
**Warning signs:** Tests pass with AttributeError: 'NoneType' object has no attribute 'table_names'

### Pitfall 2: Pandas Dependency in Tests
**What goes wrong:** Tests fail on CI if pandas not installed, or if PANDAS_AVAILABLE=False in handler
**Why it happens:** LanceDB handler checks PANDAS_AVAILABLE at module level and skips pandas operations if False
**How to avoid:** Always patch PANDAS_AVAILABLE=True in LanceDB tests, or mock pandas availability
**Warning signs:** Tests fail with "Pandas not available for search results" log messages

### Pitfall 3: Threading Timeout in Model Loading
**What goes wrong:** Tests timeout or hang when SentenceTransformer initialization hits 15s timeout
**Why it happens:** LanceDBHandler._init_local_embedder() uses threading.Thread with 15s timeout for model loading
**How to avoid:** Mock sentence_transformers at module level BEFORE importing handler, or set embedding_provider="mock"
**Warning signs:** Tests take 15+ seconds, timeout errors in test logs

### Pitfall 4: WebSocket Connection Lifecycle Leaks
**What goes wrong:** WebSocket connections leak between tests, causing assertion errors
**Why it happens:** WebSocketConnectionManager is singleton, connections persist across tests
**How to avoid:** Create fresh WebSocketConnectionManager instance per test, or call disconnect() in cleanup
**Warning signs:** Tests fail with "connection already exists" errors, connection count assertions wrong

### Pitfall 5: HTTP Client Singleton State
**What goes wrong:** HTTP client tests interfere with each other due to shared _async_client/_sync_client globals
**Why it happens:** HTTP client uses module-level singletons that persist across test runs
**How to avoid:** Always call reset_http_clients() in test setup/teardown to clean up singleton state
**Warning signs:** Tests fail with "client already closed" errors, connection count assertions wrong

## Code Examples

Verified patterns from existing codebase:

### LanceDB Handler Initialization Testing
```python
# Source: tests/integration/services/test_lancedb_integration_coverage.py (lines 64-84)
@patch('core.lancedb_handler.LANCEDB_AVAILABLE', True)
def test_initializes_db_connection_on_first_use(self, handler):
    """Test that handler initializes LanceDB connection lazily on first use."""
    # Start with db=None (uninitialized state)
    assert handler.db is None, "Handler should start with uninitialized DB"

    # Mock _initialize_db to simulate successful connection
    mock_db = Mock()
    mock_db.table_names = Mock(return_value=[])

    with patch.object(handler, '_initialize_db') as mock_init:
        handler.db = mock_db

        # Now call _ensure_db - it should check db is not None and skip initialization
        handler._ensure_db()

        # Since we set db manually, _initialize_db should not be called again
        # This verifies lazy initialization (only called when db is None)
        assert handler.db is not None
```

### Vector Search with Mocked Embeddings
```python
# Source: tests/integration/services/test_lancedb_integration_coverage.py (lines 131-150)
@patch('core.lancedb_handler.LanceDBHandler.embed_text')
@patch('core.lancedb_handler.LanceDBHandler.get_table')
def test_similarity_search_with_filters(self, mock_get_table, mock_embed, handler):
    """Test vector search with user_id and workspace_id filters."""
    # Mock embedding - return a Mock with tolist() method
    import numpy as np
    mock_vector = np.array([0.1] * 384, dtype=np.float32)
    mock_embed.return_value = mock_vector

    # Mock table search chain
    mock_table = Mock()
    mock_table.search = Mock(return_value=mock_table)
    mock_table.where = Mock(return_value=mock_table)
    mock_table.limit = Mock(return_value=mock_table)

    # Mock pandas result
    mock_df = pd.DataFrame({
        'id': ['ep1', 'ep2'],
        'text': ['result 1', 'result 2'],
        'source': ['test', 'test'],
        'metadata': [{'key': 'value'}, {'key': 'value2'}],
        'created_at': ['2026-01-01T00:00:00', '2026-01-01T01:00:00'],
        '_distance': [0.1, 0.2]
    })
    mock_table.to_pandas = Mock(return_value=mock_df)
    mock_get_table.return_value = mock_table

    # Execute search
    results = handler.search(table_name="episodes", query="test query", limit=10)

    # Assertions
    assert len(results) == 2
    assert results[0]['id'] == 'ep1'
    assert results[0]['score'] == 0.9  # 1.0 - 0.1 distance
```

### WebSocket Broadcast Error Handling
```python
# Source: tests/integration/services/test_websocket_manager_coverage.py pattern
@pytest.mark.asyncio
async def test_broadcast_handles_failed_sends():
    """Test that broadcast continues even if one connection fails."""
    manager = WebSocketConnectionManager()

    # Mock connections - one will fail
    mock_ws1 = Mock()
    mock_ws2 = Mock()
    mock_ws1.send_text = AsyncMock()
    mock_ws2.send_text = AsyncMock(side_effect=Exception("Connection closed"))

    await manager.connect(mock_ws1, "test_stream")
    await manager.connect(mock_ws2, "test_stream")

    # Broadcast - should handle exception and continue
    sent_count = await manager.broadcast("test_stream", {"type": "test"})

    # Only one succeeded (second failed)
    assert sent_count == 1
    mock_ws1.send_text.assert_called_once()
    # Failed connection should be disconnected
    assert len(manager.active_connections["test_stream"]) == 0
```

### HTTP Client Connection Pooling
```python
# Source: tests/integration/services/test_http_client_coverage.py (lines 106-131)
@pytest.mark.asyncio
async def test_async_connection_reuse():
    """Test that async client reuses connections across requests."""
    from core.http_client import get_async_client, reset_http_clients

    reset_http_clients()

    # Mock the get method to return successful response
    client = get_async_client()

    with patch.object(client, 'get', new_callable=AsyncMock) as mock_get:
        # Configure mock to return success response
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        # Make 2 requests to same URL
        url = "http://example.com/api/test"
        response1 = await client.get(url)
        response2 = await client.get(url)

        # Verify both succeeded
        assert response1.status_code == 200
        assert response2.status_code == 200

        # Verify same client instance used (connection reuse)
        assert mock_get.call_count == 2

    reset_http_clients()
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Real LanceDB in tests | Mocked LanceDB with MagicMock | Phase 182 (Feb 2026) | Tests are faster (<1s) and deterministic |
| pytest fixtures for mocks | Module-level mocking | Phase 182 (Feb 2026) | Avoids import side effects, cleaner patches |
| Manual test cleanup | reset_http_clients() cleanup | Phase 183 (Mar 2026) | Prevents singleton state leaks between tests |
| Error path testing in same file | Separate error_paths/ directory | Phase 176 (Jan 2026) | Better organization, focused error path tests |

**Deprecated/outdated:**
- **Real I/O in integration tests**: Phase 182+ uses mocks for all external dependencies (LanceDB, Docker, subprocess)
- **Global test state**: Phase 183+ uses reset_http_clients() and fresh instances per test
- **Mixed unit/integration tests**: Phase 176+ separates unit tests, integration tests, and error paths into different directories

## Open Questions

1. **LanceDB S3/R2 Storage Testing**
   - What we know: Handler has S3 storage_options configuration (endpoint, access keys, region). Current coverage is 33%.
   - What's unclear: Whether to test S3 configuration paths with mocked boto3/sts, or focus on vector operations only.
   - Recommendation: **Focus on vector operations first** (Plans 01-02). S3 storage tests can use moto library for AWS mocking if needed, but vector operations are higher priority for 75% coverage.

2. **Knowledge Graph Integration Testing**
   - What we know: Handler has add_knowledge_edge(), query_knowledge_graph() methods. Knowledge graph is separate table with from_id, to_id, type fields.
   - What's unclear: Whether knowledge graph is actively used in production, or just experimental feature.
   - Recommendation: **Test knowledge graph methods** (Plan 03) but don't over-invest. Basic CRUD operations + vector search is sufficient for 75% coverage.

3. **Dual Vector Storage Testing**
   - What we know: Handler supports dual vector storage - "vector" (1024-dim SentenceTransformers) and "vector_fastembed" (384-dim FastEmbed). Methods: add_embedding(), similarity_search(), get_embedding().
   - What's unclear: Whether both vector columns are used in production, or if FastEmbed is the default.
   - Recommendation: **Test both vector columns** (Plan 02). Dual storage is core feature - add 10-15 tests for dimension validation, column selection, and vector search.

## Sources

### Primary (HIGH confidence)
- backend/core/lancedb_handler.py (1397 lines) - Full implementation including lazy initialization, dual vector storage, S3 configuration
- backend/core/websocket_manager.py (472 lines) - WebSocketConnectionManager and DebuggingWebSocketManager
- backend/core/http_client.py (293 lines) - HTTP client singleton with connection pooling
- backend/tests/integration/services/test_lancedb_integration_coverage.py - 20 existing tests showing mocking patterns
- backend/tests/integration/services/test_websocket_manager_coverage.py - 25 existing tests showing async patterns
- backend/tests/integration/services/test_http_client_coverage.py - 53 existing tests showing singleton patterns
- backend/tests/error_paths/test_edge_case_error_paths.py - Error path testing pattern (VALIDATED_BUG docstrings)

### Secondary (MEDIUM confidence)
- Phase 183 RESEARCH.md (March 13, 2026) - AsyncMock patterns, module-level mocking strategies
- Phase 182 coverage patterns - SQLAlchemy Session fixtures, Docker mocking
- pytest-asyncio documentation - async test patterns, event loop handling
- httpx documentation - HTTP client mocking, AsyncClient testing

### Tertiary (LOW confidence)
- LanceDB GitHub repository - API reference for table.search(), table.add(), vector operations
- pandas DataFrame documentation - For mocking search results in LanceDB tests

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All libraries verified in backend/requirements.txt and tests/
- Architecture: HIGH - Existing test patterns (LanceDB 33%, WebSocket 97%, HTTP 96%) provide proven foundation
- Pitfalls: HIGH - Lazy initialization, pandas dependency, threading timeouts observed in current tests
- Code examples: HIGH - All examples from existing test files in backend/tests/integration/services/

**Research date:** March 13, 2026
**Valid until:** March 27, 2026 (30 days - stable testing patterns)
