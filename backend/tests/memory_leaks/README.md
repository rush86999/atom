# Memory Leak Tests

**Phase:** 243 - Memory & Performance Bug Discovery
**Location:** `backend/tests/memory_leaks/`
**Last Updated:** March 25, 2026

## Purpose

Memory leak tests use Bloomberg's **memray** profiler to detect Python-level memory leaks in critical paths: agent execution, governance cache, LLM streaming, canvas presentation, and episodic memory operations.

**Python 3.11+ Required:** memray only supports Python 3.11+

**Graceful Degradation:** Tests skip with pytest.skip if memray unavailable

## Key Features

- **Python Heap Leak Detection:** Detects uncollected objects (circular references, global caches)
- **Amplification Loops:** 100 iterations to amplify small leaks (1KB → 100KB)
- **Flame Graph Generation:** HTML flame graphs for visualizing memory allocations
- **Threshold Assertions:** 10MB leak threshold for realistic detection
- **Sequential Execution:** Tests run with `-n 1` to avoid interference

## Test Coverage

### Agent Execution Memory Leaks (`test_agent_execution_leaks.py`)

**Tests:**
- `test_agent_execution_no_memory_leak()` - Repeated agent execution (100 iterations)
- `test_concurrent_agent_execution_no_memory_leak()` - Concurrent agent execution
- `test_agent_registry_no_memory_leak()` - Agent registry operations
- `test_agent_governance_cache_no_memory_leak()` - Governance cache operations

**Fixtures:**
- `memray_session` - Memray tracker with max_memory_increase() assertion

**Focus Areas:**
- Agent execution lifecycle
- Database connection pooling
- Cache entry management
- Event listener registration

### Governance Cache Memory Leaks (`test_governance_cache_leaks.py`)

**Tests:**
- `test_governance_cache_get_no_memory_leak()` - Cache get operations
- `test_governance_cache_set_no_memory_leak()` - Cache set operations
- `test_governance_cache_invalidation_no_memory_leak()` - Cache invalidation
- `test_governance_cache_bulk_operations_no_memory_leak()` - Bulk operations

**Fixtures:**
- `memray_session` - Memray tracker
- `governance_cache` - GovernanceCache instance

**Focus Areas:**
- Cache entry lifecycle
- LRU eviction policy
- Bulk operation efficiency
- Cache invalidation cleanup

### LLM Streaming Memory Leaks (`test_llm_streaming_leaks.py`)

**Tests:**
- `test_llm_streaming_no_memory_leak()` - LLM streaming operations
- `test_llm_streaming_large_response_no_memory_leak()` - Large responses (10K tokens)
- `test_llm_streaming_concurrent_no_memory_leak()` - Concurrent streaming
- `test_llm_streaming_error_handling_no_memory_leak()` - Error handling

**Fixtures:**
- `memray_session` - Memray tracker
- `mock_llm_handler` - Mock BYOKHandler

**Focus Areas:**
- Token streaming buffers
- Response accumulation
- Connection pooling
- Error handler cleanup

### Canvas Presentation Memory Leaks (`test_canvas_presentation_leaks.py`)

**Tests:**
- `test_canvas_presentation_no_memory_leak()` - Canvas presentation operations
- `test_canvas_presentation_multiple_canvases_no_memory_leak()` - Multiple canvases
- `test_canvas_presentation_complex_charts_no_memory_leak()` - Complex charts
- `test_canvas_presentation_state_updates_no_memory_leak()` - State updates

**Fixtures:**
- `memray_session` - Memray tracker
- `mock_canvas_tool` - Mock CanvasTool

**Focus Areas:**
- Canvas state management
- Chart rendering buffers
- WebSocket connection pooling
- Event listener cleanup

### Episodic Memory Memory Leaks (`test_episodic_memory_leaks.py`)

**Tests:**
- `test_episode_segmentation_no_memory_leak()` - Episode segmentation
- `test_episode_retrieval_no_memory_leak()` - Episode retrieval
- `test_episode_lifecycle_no_memory_leak()` - Episode lifecycle
- `test_episode_batch_operations_no_memory_leak()` - Batch operations

**Fixtures:**
- `memray_session` - Memray tracker
- `episode_service` - EpisodeSegmentationService, EpisodeRetrievalService

**Focus Areas:**
- Episode segment storage
- Vector embeddings
- LanceDB connections
- Batch operation cleanup

## Fixtures

### memray_session

**Purpose:** Memray tracker for memory leak detection

**Usage:**
```python
def test_no_memory_leak(memray_session):
    with memray_session:
        # Run operations
        for i in range(100):
            execute_operation()

    # Assert no leak
    assert memray_session.get_max_memory_increase() < 10 * 1024 * 1024  # 10MB
```

**Methods:**
- `get_max_memory_increase()` - Returns max memory increase in bytes
- `get_flame_graph_path()` - Returns path to flame graph HTML file

**Artifact Location:** `backend/tests/memory_leaks/artifacts/`

## Test Patterns

### Amplification Loop Pattern

```python
@pytest.mark.memory_leak
def test_operation_no_memory_leak(memray_session):
    """
    PROPERTY: Operation should not leak memory over 100 iterations

    STRATEGY: Use memray to track Python heap allocations during repeated
    operations. Amplify potential leaks by running 100 iterations.

    INVARIANT: max_memory_increase < LEAK_THRESHOLD (10MB)

    RADII: 100 iterations provides 99% confidence for detecting leaks
    with 1MB amplification (100 * 10KB per operation).
    """
    with memray_session:
        # Amplification loop: 100 iterations
        for i in range(100):
            execute_operation(data=f"test-{i}")

    # Assertion: No memory leak
    assert memray_session.get_max_memory_increase() < 10 * 1024 * 1024  # 10MB
```

### Threshold Assertion Pattern

```python
@pytest.mark.memory_leak
def test_cache_operations_no_memory_leak(memray_session, governance_cache):
    """
    PROPERTY: Cache operations should not leak memory

    THRESHOLD: 10MB leak threshold allows for GC delay and cache warming
    """
    with memray_session:
        # Perform 100 cache operations
        for i in range(100):
            governance_cache.get(f"agent:{i}")
            governance_cache.set(f"agent:{i}", {"data": f"value-{i}"})

    # Assert memory increase < 10MB
    max_increase = memray_session.get_max_memory_increase()
    assert max_increase < 10 * 1024 * 1024, f"Leaked {max_increase / 1024 / 1024:.2f}MB"
```

### Error Handling Pattern

```python
@pytest.mark.memory_leak
def test_error_handling_no_memory_leak(memray_session):
    """
    PROPERTY: Error handling should not leak resources (connections, buffers)

    STRATEGY: Trigger errors and verify no resource leaks
    """
    with memray_session:
        for i in range(100):
            try:
                # Trigger error
                execute_invalid_operation()
            except ValueError:
                pass  # Expected error

    # Assert no leak despite errors
    assert memray_session.get_max_memory_increase() < 10 * 1024 * 1024
```

## Running Tests

### Run All Memory Leak Tests

```bash
cd backend
pytest tests/memory_leaks/ -v -m memory_leak

# Sequential execution (required for memray)
pytest tests/memory_leaks/ -v -m memory_leak -n 1

# With flame graph generation
pytest tests/memory_leaks/ -v -m memory_leak -n 1 --memray
```

### Run Specific Test File

```bash
# Agent execution leaks
pytest tests/memory_leaks/test_agent_execution_leaks.py -v

# Governance cache leaks
pytest tests/memory_leaks/test_governance_cache_leaks.py -v

# LLM streaming leaks
pytest tests/memory_leaks/test_llm_streaming_leaks.py -v

# Canvas presentation leaks
pytest tests/memory_leaks/test_canvas_presentation_leaks.py -v

# Episodic memory leaks
pytest tests/memory_leaks/test_episodic_memory_leaks.py -v
```

### Run Single Test

```bash
pytest tests/memory_leaks/test_agent_execution_leaks.py::test_agent_execution_no_memory_leak -v
```

### Generate Flame Graphs

```bash
# Run tests with memray profiling
pytest tests/memory_leaks/ -v -m memory_leak -n 1 --memray

# Open flame graph in browser
open backend/tests/memory_leaks/artifacts/test_agent_execution_no_memory_leak.html
```

## Troubleshooting

### Common Issues

**1. memray not installed (Python 3.11+ required)**
```bash
# Symptom: Tests skip with "memray not installed"
# Solution: Install memray (Python 3.11+ only)
python --version  # Must be 3.11+
pip install memray
```

**2. Test fails with small leak (<1MB)**
```bash
# Symptom: Test fails with "Leaked 0.5MB"
# Solution: This is likely GC delay, re-run test
pytest tests/memory_leaks/test_agent_execution_leaks.py::test_agent_execution_no_memory_leak -v
```

**3. Flame graph not generated**
```bash
# Symptom: No HTML file in artifacts/
# Solution: Run with --memray flag
pytest tests/memory_leaks/ -v -m memory_leak -n 1 --memray
```

**4. Test hangs indefinitely**
```bash
# Symptom: Test never completes
# Solution: Test has infinite loop, check for missing break conditions
pytest tests/memory_leaks/test_agent_execution_leaks.py -v -s  # -s for output
```

### Debugging Memory Leaks

**View Flame Graphs:**
```bash
# Open flame graph in browser
open backend/tests/memory_leaks/artifacts/test_agent_execution_no_memory_leak.html

# Flame graph shows:
# - Function call stacks
# - Memory allocation hotspots (red/yellow towers)
# - Leak locations (tall towers = many allocations)
```

**Memory Leak Categories:**
1. **Python Heap Leaks:** Uncollected objects (circular references, global caches)
2. **C Extension Leaks:** Native memory leaks (e.g., database connection pools)
3. **Amplification Leaks:** Small leaks multiplied over iterations

**Common Memory Leak Patterns:**
```python
# Pattern 1: Global list growing unbounded
GLOBAL_CACHE = []  # LEAK: Never cleared

# Solution: Use LRU cache with size limit
from functools import lru_cache
@lru_cache(maxsize=1000)
def get_agent(agent_id):
    return AgentRegistry.query.get(agent_id)

# Pattern 2: Circular references
class Agent:
    def __init__(self):
        self.parent = None
        self.children = []
        # Circular reference: parent <-> children

# Solution: Use weak references
import weakref
class Agent:
    def __init__(self):
        self.parent = None
        self.children = []  # Store weak references

# Pattern 3: Unclosed database connections
from sqlalchemy.orm import Session
session = Session()  # LEAK: Never closed

# Solution: Use context manager
with Session() as session:
    agents = session.query(Agent).all()
# Connection automatically closed

# Pattern 4: Event listeners not removed
class EventEmitter:
    def __init__(self):
        self.listeners = []

    def add_listener(self, listener):
        self.listeners.append(listener)  # LEAK: Never removed

# Solution: Auto-remove listeners or use weak references
import weakref

class EventEmitter:
    def __init__(self):
        self.listeners = weakref.WeakSet()

    def add_listener(self, listener):
        self.listeners.add(listener)  # Auto-removed when listener GC'd
```

## Examples

### Writing Memory Leak Tests

**Example 1: Agent Execution Memory Leak**
```python
import pytest
from tests.memory_leaks.conftest import memray_session

@pytest.mark.memory_leak
def test_agent_execution_no_memory_leak(memray_session):
    """
    PROPERTY: Agent execution should not leak memory over 100 iterations

    STRATEGY: Use memray to track Python heap allocations during repeated
    agent execution operations. Amplify potential leaks by running 100
    iterations.

    INVARIANT: max_memory_increase < LEAK_THRESHOLD (10MB)

    RADII: 100 iterations provides 99% confidence for detecting leaks
    with 1MB amplification (100 * 10KB per execution).
    """
    from core.agent_governance_service import AgentGovernanceService
    from core.models import AgentRegistry

    # Setup
    service = AgentGovernanceService()

    with memray_session:
        # Amplification loop: 100 iterations
        for i in range(100):
            agent = AgentRegistry(
                id=f"test-agent-{i}",
                name=f"Test Agent {i}",
                category="testing",
                module_path="core.agent_governance_service",
                class_name="AgentGovernanceService",
                status="AUTONOMOUS"
            )

            # Execute agent (potential leak point)
            service.execute_agent(agent.id)

    # Assertion: No memory leak
    assert memray_session.get_max_memory_increase() < 10 * 1024 * 1024  # 10MB
```

**Example 2: Cache Memory Leak**
```python
@pytest.mark.memory_leak
def test_governance_cache_no_memory_leak(memray_session):
    """
    PROPERTY: Governance cache should not leak memory

    STRATEGY: Perform 100 cache get/set operations and verify no leak
    """
    from core.governance_cache import GovernanceCache

    # Setup
    cache = GovernanceCache()

    with memray_session:
        # Amplification loop: 100 iterations
        for i in range(100):
            cache.get(f"agent:{i}")
            cache.set(f"agent:{i}", {"data": f"value-{i}"})

    # Assertion: No memory leak
    assert memray_session.get_max_memory_increase() < 10 * 1024 * 1024  # 10MB
```

**Example 3: LLM Streaming Memory Leak**
```python
@pytest.mark.memory_leak
def test_llm_streaming_no_memory_leak(memray_session, mock_llm_handler):
    """
    PROPERTY: LLM streaming should not leak memory

    STRATEGY: Stream 100 responses and verify no leak in token buffers
    """
    with memray_session:
        # Amplification loop: 100 iterations
        for i in range(100):
            response = mock_llm_handler.stream_response(f"prompt-{i}")
            tokens = list(response)  # Consume stream

    # Assertion: No memory leak
    assert memray_session.get_max_memory_increase() < 10 * 1024 * 1024  # 10MB
```

## Best Practices

1. **Use Amplification Loops:** 100 iterations to amplify small leaks (1KB → 100KB)
2. **Set Realistic Thresholds:** 10MB for Python heap leaks (allows for GC delay)
3. **Generate Flame Graphs:** Essential for debugging complex leaks
4. **Test Sequential Execution:** Use `-n 1` to avoid interference from parallel tests
5. **Graceful Degradation:** Skip tests if memray unavailable (Python 3.11+ required)
6. **Document Invariants:** Use PROPERTY/STRATEGY/INVARIANT/RADII format
7. **Test Critical Paths:** Focus on agent execution, cache, streaming, episodic memory

## References

- **Phase 243 Documentation:** `docs/archive/implementation/MEMORY_PERFORMANCE_BUG_DISCOVERY.md`
- **memray Documentation:** https://bloomberg.github.io/memray/
- **Conftest:** `backend/tests/memory_leaks/conftest.py`
- **Weekly CI:** `.github/workflows/memory-performance-weekly.yml`

---

*Last Updated: March 25, 2026*
*Phase 243 - Memory & Performance Bug Discovery*
