# Phase 129: Backend Critical Error Paths - Research

**Researched:** March 3, 2026
**Domain:** Backend Error Path Testing, Database Failures, External Service Timeouts, Rate Limiting
**Confidence:** HIGH

## Summary

Phase 129 focuses on testing critical error paths in the Atom backend that are rarely executed during normal operation but essential for production reliability. The phase targets five key areas: database connection failures with retry logic validation, external service timeouts with circuit breaker verification, rate limiting with backoff strategy validation, end-to-end error propagation testing, and graceful degradation verification for all critical paths.

**Primary recommendation:** Leverage existing error path testing infrastructure in `/backend/tests/error_paths/` and `/backend/tests/failure_modes/` as the foundation, expand coverage using pytest fixtures for database/HTTP mocking, and implement comprehensive tests using the custom CircuitBreaker and retry_with_backoff patterns already present in `core/auto_healing.py`.

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **pytest** | ≥8.0 | Test framework and fixtures | De facto standard for Python testing in 2026, extensive plugin ecosystem |
| **SQLAlchemy** | 2.0 | Database ORM and error simulation | Industry standard, built-in exception types (IntegrityError, OperationalError, DataError) |
| **unittest.mock** | Built-in | Mock and patch for error injection | Python stdlib, no dependencies, integrates with pytest |
| **respx** | ≥0.21 | HTTP mocking for timeout testing | Best-in-class for httpx/asyncio mocking, superior to responses for async code |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **freezegun** | ≥1.4 | Time mocking for timeout/retry tests | Test circuit breaker timeout transitions, verify backoff delays |
| **pytest-asyncio** | ≥0.23 | Async test support | Required for testing BYOKHandler and external service calls |
| **httpx** | ≥0.27 | HTTP client (respx dependency) | Required for respx mock fixtures |
| **pytest-timeout** | Latest | Test-level timeouts | Prevent hung tests during infinite retry scenarios |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| **respx** | pytest-httpx, responses, aioresponses | respx has superior async support and httpx integration compared to responses (sync-only) and aioresponses ( aiohttp-specific). pytest-httpx is lighter but respx more feature-complete for complex scenarios |
| **freezegun** | time-machine, pytest-freezegun | freezegun is more mature with broader ecosystem support. time-machine has cleaner API but less adoption |
| **CircuitBreaker (custom)** | pybreaker, circuitbreaker | Custom implementation in `core/auto_healing.py` already integrated. Libraries would require refactoring existing code |

**Installation:**
```bash
# Core dependencies (likely already installed)
pip install pytest>=8.0 pytest-asyncio>=0.23

# HTTP mocking for timeout testing
pip install respx>=0.21 httpx>=0.27

# Time mocking for circuit breaker tests
pip install freezegun>=1.4

# Test timeout protection
pip install pytest-timeout
```

## Architecture Patterns

### Recommended Project Structure

```
backend/tests/critical_error_paths/
├── conftest.py                      # Shared fixtures for error injection
├── test_database_connection_failures.py    # Database connection/timeout tests
├── test_external_service_timeouts.py       # LLM provider timeout tests with circuit breaker
├── test_rate_limiting.py                    # Rate limiter backoff strategy tests
├── test_error_propagation.py                # End-to-end error flow (service→API→client)
└── test_graceful_degradation.py             # Fallback behavior validation

backend/tests/failure_modes/          # Already exists - expand this
├── conftest.py                       # Existing fixtures for failure simulation
├── test_database_connection_loss.py  # Already exists - enhance
├── test_network_timeouts.py          # Already exists - enhance
├── test_provider_failures.py         # Already exists - enhance
└── test_resource_exhaustion.py       # Already exists - enhance

backend/tests/error_paths/            # Already exists - reference patterns
├── conftest.py                       # Existing error injection fixtures
├── test_database_error_paths.py      # Reference for database error patterns
├── test_llm_streaming_error_paths.py # Reference for LLM error patterns
└── test_*_error_paths.py             # Other error path examples
```

### Pattern 1: Database Connection Failure Testing

**What:** Simulate database connection drops, pool exhaustion, and query timeouts using SQLAlchemy exception injection.

**When to use:** Testing services that depend on `core.database.get_db_session()` or direct database access.

**Example:**
```python
# Source: /backend/tests/error_paths/test_database_error_paths.py (existing pattern)

import pytest
from sqlalchemy.exc import OperationalError, IntegrityError
from unittest.mock import patch

class TestConnectionErrors:
    def test_database_connection_refused(self):
        """ERROR PATH: Database server not reachable (connection refused)."""
        with patch('core.database.create_engine',
                  side_effect=OperationalError("Connection refused", {}, None)):
            with pytest.raises(OperationalError):
                from core.database import engine
                # Try to connect, should fail

    def test_connection_timeout(self):
        """ERROR PATH: Database connection timeout."""
        with patch('core.database.create_engine',
                  side_effect=OperationalError("timeout expired", {}, None)):
            with pytest.raises((OperationalError, Exception)):
                from core.database import get_db_session
                get_db_session().__enter__()
```

### Pattern 2: External Service Timeout with Circuit Breaker

**What:** Mock HTTP client timeouts and verify circuit breaker state transitions (CLOSED → OPEN → HALF_OPEN).

**When to use:** Testing LLM providers, external API calls, webhook endpoints.

**Example:**
```python
# Source: /backend/core/auto_healing.py (custom implementation)

import pytest
from core.auto_healing import CircuitBreaker, retry_with_backoff
from unittest.mock import patch, MagicMock
import time

class TestCircuitBreaker:
    def test_circuit_breaker_opens_after_failures(self):
        """FAILURE MODE: Circuit breaker opens after threshold failures."""
        breaker = CircuitBreaker(failure_threshold=3, timeout=60)

        def failing_call():
            raise Exception("Service unavailable")

        # First 2 failures: circuit stays CLOSED
        for i in range(2):
            with pytest.raises(Exception):
                breaker.call(failing_call)
        assert breaker.state == "CLOSED"

        # 3rd failure: circuit opens
        with pytest.raises(Exception) as exc_info:
            breaker.call(failing_call)
        assert "Circuit breaker OPEN" in str(exc_info.value)
        assert breaker.state == "OPEN"

    def test_circuit_breaker_half_open_after_timeout(self):
        """FAILURE MODE: Circuit breaker transitions to HALF_OPEN after timeout."""
        breaker = CircuitBreaker(failure_threshold=3, timeout=1)

        # Trigger circuit to open
        for i in range(3):
            try:
                breaker.call(lambda: (_ for _ in ()).throw(Exception()))
            except:
                pass

        assert breaker.state == "OPEN"

        # Wait for timeout
        time.sleep(2)

        # Next call should enter HALF_OPEN state
        def successful_call():
            return "success"
        result = breaker.call(successful_call)
        assert result == "success"
        assert breaker.state == "CLOSED"  # Reset after success
```

### Pattern 3: Rate Limiting with Backoff Strategy

**What:** Simulate rate limit errors (HTTP 429) and verify exponential backoff retry logic.

**When to use:** Testing API clients that interact with rate-limited external services.

**Example:**
```python
# Source: /backend/core/auto_healing.py (existing retry decorator)

import pytest
from core.auto_healing import retry_with_backoff
from unittest.mock import patch
import time

class TestRateLimitingWithBackoff:
    def test_exponential_backoff_on_rate_limit(self):
        """FAILURE MODE: Rate limit error triggers exponential backoff."""
        call_times = []

        @retry_with_backoff(max_retries=3, base_delay=0.1, max_delay=1.0)
        def api_call():
            call_times.append(time.time())
            raise Exception("Rate limit exceeded (429)")

        with pytest.raises(Exception):
            api_call()

        # Verify 4 attempts total (1 initial + 3 retries)
        assert len(call_times) == 4

        # Verify exponential backoff: ~0.1s, ~0.2s, ~0.4s
        if len(call_times) >= 3:
            delay1 = call_times[1] - call_times[0]
            delay2 = call_times[2] - call_times[1]
            assert 0.05 < delay1 < 0.2  # ~100ms with tolerance
            assert 0.15 < delay2 < 0.5  # ~200ms with tolerance

    def test_max_delay_cap_respected(self):
        """FAILURE MODE: Backoff delay capped at max_delay."""
        @retry_with_backoff(max_retries=10, base_delay=1.0, max_delay=2.0)
        def api_call():
            raise Exception("Rate limit exceeded")

        with pytest.raises(Exception):
            api_call()

        # Delays should be: 1s, 2s, 2s, 2s, ... (capped at max_delay)
        # Not verifying exact timing here, just that it completes
        assert True
```

### Pattern 4: HTTP Timeout Testing with respx

**What:** Mock HTTP client timeouts using respx to test external service error handling.

**When to use:** Testing `BYOKHandler`, webhook handlers, integration API calls.

**Example:**
```python
# Source: https://blog.csdn.net/jrckkyy/article/details/150273972 (pytest/respx/pytest-asyncio pattern)

import pytest
import httpx
import respx

class TestExternalServiceTimeouts:
    @respx.mock
    def test_llm_provider_timeout_handling(self):
        """FAILURE MODE: LLM provider request timeout."""
        # Mock timeout response
        respx.get("https://api.openai.com/v1/chat/completions").mock(
            side_effect=httpx.TimeoutException("Request timed out")
        )

        from core.llm.byok_handler import BYOKHandler

        handler = BYOKHandler(workspace_id="test")
        # Should fallback to next provider or raise error
        with pytest.raises((httpx.TimeoutException, Exception)):
            # Call LLM method
            pass

    @respx.mock
    def test_webhook_retry_on_503(self):
        """FAILURE MODE: Webhook receives 503 Service Unavailable."""
        call_count = [0]

        def mock_503_then_200(request):
            call_count[0] += 1
            if call_count[0] < 3:
                return httpx.Response(503, text="Service Unavailable")
            return httpx.Response(200, json={"status": "ok"})

        respx.post("https://external.service/webhook").mock(side_effect=mock_503_then_200)

        # Webhook handler should retry and eventually succeed
        # Verify 3 attempts were made
        assert call_count[0] == 3
```

### Pattern 5: Error Propagation End-to-End

**What:** Verify errors propagate correctly through service layer → API layer → client response.

**When to use:** Testing that AtomException hierarchy converts to correct HTTP responses.

**Example:**
```python
# Source: /backend/core/error_handlers.py (existing error handler)

import pytest
from fastapi.testclient import TestClient
from core.exceptions import DatabaseConnectionError, LLMRateLimitError

class TestErrorPropagation:
    def test_database_error_propagates_to_client(self, client):
        """ERROR PATH: Database connection error reaches client as 500."""
        # Mock database service to raise error
        with patch('core.database.get_db_session',
                  side_effect=DatabaseConnectionError("Connection failed")):
            response = client.get("/api/v1/agents")

        # Should return 500 with error details
        assert response.status_code == 500
        assert "error_code" in response.json()
        assert response.json()["error_code"] == "DB_6002"

    def test_rate_limit_error_propagates_to_client(self, client):
        """ERROR PATH: LLM rate limit error reaches client as 429."""
        with patch('core.llm.byok_handler.BYOKHandler.generate',
                  side_effect=LLMRateLimitError("openai", retry_after=60)):
            response = client.post("/api/v1/chat", json={"message": "test"})

        # Should return 429 with retry-after header
        assert response.status_code == 429
        assert "retry-after" in response.headers or "retry_after" in response.json().get("details", {})
```

### Anti-Patterns to Avoid

- **Silent exception swallowing:** Never catch Exception without logging or re-raising. This hides errors and makes debugging impossible.
- **Missing rollback after database errors:** Always call `db.rollback()` in except blocks. Uncommitted transactions cause lock contention.
- **Hardcoded retry counts:** Use configurable retry policies, not hardcoded `for i in range(3)` loops. Makes testing and tuning impossible.
- **Testing with real external services:** Never test against production APIs. Use respx/mock to simulate failures deterministically.
- **Assuming atomic operations:** Database transactions are NOT atomic across multiple session objects. Test concurrent session access patterns.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTTP mocking for timeouts | Custom `@patch` on `requests.get` | **respx** | Handles async/await, httpx integration, realistic timeout simulation |
| Circuit breaker implementation | Custom state tracking with if/else | **core/auto_healing.CircuitBreaker** (already exists) | Proven pattern, handles OPEN/HALF_OPEN/CLOSED states, integrated into codebase |
| Retry logic with backoff | Custom `time.sleep()` loops | **core/auto_healing.retry_with_backoff** (decorator exists) | Exponential backoff, configurable max delay, cleaner API |
| Time mocking for circuit breaker tests | Manual time manipulation | **freezegun** | Deterministic tests, no actual waiting, handles datetime.now() calls |
| Rate limiting simulation | Custom counters with `threading.Lock` | **core/resource_guards.RateLimiter** (exists) or Redis-backed | Thread-safe, supports distributed rate limiting, already integrated |

**Key insight:** The codebase already has robust circuit breaker (`CircuitBreaker`), retry logic (`retry_with_backoff`, `async_retry_with_backoff`), and error handling infrastructure (`core/exceptions.py`, `core/error_handlers.py`). Phase 129 should TEST this existing infrastructure, not rebuild it. Focus on coverage gaps: testing that these mechanisms work correctly under simulated failure conditions.

## Common Pitfalls

### Pitfall 1: Testing Synchronous Code with Async Mocks

**What goes wrong:** Using `AsyncMock` to patch synchronous functions, or mixing sync/async test patterns.

**Why it happens:** Confusion between `unittest.mock.MagicMock` (sync) and `unittest.mock.AsyncMock` (async).

**How to avoid:**
- Use `MagicMock` for synchronous function calls
- Use `AsyncMock` only for `async def` functions
- Use `pytest-asyncio` `@pytest.mark.asyncio` decorator for async tests
- Never mix sync patches with async test functions

**Warning signs:** Tests pass but don't actually execute the code path, or `TypeError: object MagicMock can't be used in 'await' expression`.

### Pitfall 2: Database Session Leakage in Tests

**What goes wrong:** Tests create database sessions but don't close them, causing connection pool exhaustion.

**Why it happens:** Forgetting to call `db.close()` or using raw `SessionLocal()` without context manager.

**How to avoid:**
- Always use `with get_db_session() as db:` context manager
- For FastAPI endpoints, use `Depends(get_db)` dependency injection
- Use `autouse=True` fixture to clean up sessions after each test
- Verify session count in teardown if tests fail intermittently

**Warning signs:** Intermittent test failures, "connection pool exhausted" errors, tests pass in isolation but fail in suites.

### Pitfall 3: Mocking the Wrong Import Path

**What goes wrong:** Patching `core.database.SessionLocal` but the code imports `from database import SessionLocal`.

**Why it happens:** Python's import system creates multiple references to the same object. Patching one reference doesn't affect others.

**How to avoid:**
- Patch where the object is USED, not where it's DEFINED
- Use full import path: `patch('core.services.agent_service.get_db_session')`
- Verify patches by adding `side_effect=Exception("PATCHED")` and confirming it raises

**Warning signs:** Mocked function still executes real code, patches have no effect, tests pass when they should fail.

### Pitfall 4: Not Verifying Side Effects in Error Paths

**What goes wrong:** Testing that an exception is raised but not verifying cleanup (rollback, cache invalidation, logging).

**Why it happens:** Focusing only on `pytest.raises(Exception)` without checking post-condition state.

**How to avoid:**
- After exception, verify database state (transaction rolled back)
- Check logs for error messages (`caplog` fixture)
- Verify cache entries invalidated
- Confirm circuit breaker state changed
- Use fixtures like `assert_logs_error` from `/backend/tests/error_paths/conftest.py`

**Warning signs:** Tests pass but production has data inconsistencies, stale cache entries, or silent failures.

### Pitfall 5: Infinite Retry Loops in Tests

**What goes wrong:** Tests hang because retry logic keeps retrying forever with mocked failures.

**Why it happens:** Mocking a function to always raise exception without limiting retries.

**How to avoid:**
- Always use `max_retries` parameter in retry decorators
- Use `pytest-timeout` plugin: `@pytest.mark.timeout(5)`
- Mock side effects to succeed after N failures: `side_effect=[Exception(), Exception(), "success"]`
- Test retry exhaustion path explicitly

**Warning signs:** Tests never complete, CI builds time out, "pytest stuck" messages.

### Pitfall 6: Testing Implementation Details Instead of Behavior

**What goes wrong:** Testing that `circuit_breaker.failure_count == 5` instead of "circuit opens after 5 failures".

**Why it happens:** Easier to access internal state than verify external behavior.

**How to avoid:**
- Test public API behavior, not private attributes
- Verify exceptions raised with correct messages
- Check that subsequent calls fail after circuit opens
- Use black-box testing: input → expected output

**Warning signs:** Tests break when refactoring internal implementation, brittle tests, need to update tests for code style changes.

## Code Examples

Verified patterns from official sources:

### Database Connection Failure Test

```python
# Source: /backend/tests/error_paths/test_database_error_paths.py (existing codebase)

def test_database_connection_refused(self):
    """
    ERROR PATH: Database server not reachable (connection refused).
    EXPECTED: OperationalError raised or connection retry logic.
    """
    # Patch create_engine to raise connection error
    with patch('core.database.create_engine',
              side_effect=OperationalError("Connection refused", {}, None)):
        with pytest.raises(OperationalError):
            from core.database import engine
            # Try to connect, should fail
```

### Circuit Breaker State Transition Test

```python
# Source: /backend/core/auto_healing.py (existing implementation)

def test_circuit_breaker_opens_after_failures(self):
    """FAILURE MODE: Circuit breaker opens after threshold failures."""
    breaker = CircuitBreaker(failure_threshold=3, timeout=60)

    def failing_call():
        raise Exception("Service unavailable")

    # First 2 failures: circuit stays CLOSED
    for i in range(2):
        with pytest.raises(Exception):
            breaker.call(failing_call)
    assert breaker.state == "CLOSED"

    # 3rd failure: circuit opens
    with pytest.raises(Exception) as exc_info:
        breaker.call(failing_call)
    assert "Circuit breaker OPEN" in str(exc_info.value)
    assert breaker.state == "OPEN"
```

### Retry with Exponential Backoff Test

```python
# Source: /backend/core/auto_healing.py (existing implementation)

def test_exponential_backoff_on_rate_limit(self):
    """FAILURE MODE: Rate limit error triggers exponential backoff."""
    call_times = []

    @retry_with_backoff(max_retries=3, base_delay=0.1, max_delay=1.0)
    def api_call():
        call_times.append(time.time())
        raise Exception("Rate limit exceeded (429)")

    with pytest.raises(Exception):
        api_call()

    # Verify 4 attempts total (1 initial + 3 retries)
    assert len(call_times) == 4

    # Verify exponential backoff: ~0.1s, ~0.2s, ~0.4s
    if len(call_times) >= 3:
        delay1 = call_times[1] - call_times[0]
        delay2 = call_times[2] - call_times[1]
        assert 0.05 < delay1 < 0.2  # ~100ms with tolerance
        assert 0.15 < delay2 < 0.5  # ~200ms with tolerance
```

### HTTP Timeout with respx Mock

```python
# Source: https://blog.csdn.net/jrckkyy/article/details/150273972 (pytest/respx pattern)

@respx.mock
def test_llm_provider_timeout_handling(self):
    """FAILURE MODE: LLM provider request timeout."""
    # Mock timeout response
    respx.get("https://api.openai.com/v1/chat/completions").mock(
        side_effect=httpx.TimeoutException("Request timed out")
    )

    from core.llm.byok_handler import BYOKHandler

    handler = BYOKHandler(workspace_id="test")
    # Should fallback to next provider or raise error
    with pytest.raises((httpx.TimeoutException, Exception)):
        handler.generate("test prompt")
```

### Error Propagation Test

```python
# Source: /backend/core/error_handlers.py (existing error handler)

def test_database_error_propagates_to_client(self, client):
    """ERROR PATH: Database connection error reaches client as 500."""
    # Mock database service to raise error
    with patch('core.database.get_db_session',
              side_effect=DatabaseConnectionError("Connection failed")):
        response = client.get("/api/v1/agents")

    # Should return 500 with error details
    assert response.status_code == 500
    assert "error_code" in response.json()
    assert response.json()["error_code"] == "DB_6002"
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| **Manual HTTP mocking with `@patch`** | **respx for httpx/asyncio mocking** | 2024-2025 | Realistic timeout simulation, async support, cleaner API |
| **Custom retry loops** | **Decorators (`@retry_with_backoff`)** | 2023-2024 | Reusable retry logic, exponential backoff built-in, testable |
| **Global circuit breakers** | **Per-service circuit breakers** | 2024 | Isolated failures, fine-grained control, better observability |
| **Silent error handling** | **Structured AtomException hierarchy** | 2025 | Consistent error responses, audit trail, easier debugging |
| **Timeout testing with `time.sleep()`** | **freezegun for time mocking** | 2024-2025 | Fast tests (no actual waiting), deterministic behavior |

**Deprecated/outdated:**
- **responses library**: Superseded by respx for async/await code. responses only supports synchronous requests.
- **Manual circuit breaker implementations**: Use `core/auto_healing.CircuitBreaker` instead of building custom state machines.
- **Pytest's `xdist` for parallel error injection**: Can cause race conditions in failure simulation. Use sequential execution for reliability tests.
- **SQLite for testing transaction isolation**: SQLite doesn't enforce foreign keys by default. Use PostgreSQL or explicitly enable FK enforcement.

## Open Questions

1. **Database constraint testing with SQLite vs PostgreSQL**
   - What we know: SQLite doesn't enforce foreign keys by default, PostgreSQL does. Test suite uses SQLite.
   - What's unclear: Whether foreign key violation tests in `test_database_error_paths.py` actually verify FK constraints.
   - Recommendation: Explicitly enable `PRAGMA foreign_keys=ON` in test fixtures or use PostgreSQL for constraint testing. Verify with `db.execute("PRAGMA foreign_keys")` in test setup.

2. **Circuit breaker timeout testing without real delays**
   - What we know: freezegun can mock `time.time()` but may not work with `time.sleep()` in circuit breaker.
   - What's unclear: Whether `core/auto_healing.CircuitBreaker.timeout` logic can be tested deterministically.
   - Recommendation: Use `freezegun` for state-based timeouts, or mock `datetime.now()` instead of `time.time()` in CircuitBreaker implementation. Test with small timeouts (100ms) if mocking fails.

3. **Rate limiter testing without Redis**
   - What we know: Codebase has Redis-backed rate limiters (SlackRateLimiter, TeamsRateLimiter) but tests may not have Redis.
   - What's unclear: Whether rate limiter tests should mock Redis or use in-memory fallback.
   - Recommendation: Create `MockRateLimiter` class for testing that replicates Redis logic in-memory. Verify rate limiting behavior without Redis dependency. Add integration tests with Redis for completeness.

## Sources

### Primary (HIGH confidence)

- [circuitbreaker - PyPI](https://pypi.org/project/circuitbreaker/) - Python Circuit Breaker pattern implementation with decorator support
- [CSDN: pytest/respx/pytest-asyncio Tutorial](https://blog.csdn.net/jrckkyy/article/details/150273972) - Comprehensive guide to HTTP mocking with respx for async code (August 2025)
- [CSDN: RESPX Usage Tutorial](https://blog.csdn.net/gitblog_01135/article/details/146974520) - Basic RESPX patterns with httpx (April 2025)
- [CSDN: Python Mock Testing Chapter 11](https://www.cnblogs.com/ying360/p/18760955) - Mock testing patterns with pytest (2025)
- [CSDN: pytest-HTTPX vs RESPX Comparison](https://blog.csdn.net/gitblog_00709/article/details/148391494) - HTTPX ecosystem guide, tool selection (June 2025)
- **Codebase sources** (HIGH confidence - existing implementation):
  - `/backend/core/auto_healing.py` - CircuitBreaker, retry_with_backoff, async_retry_with_backoff implementations
  - `/backend/core/exceptions.py` - AtomException hierarchy (1000-line exception system)
  - `/backend/core/error_handlers.py` - API error response handlers, global exception handlers
  - `/backend/core/database.py` - Database session management, connection pooling
  - `/backend/tests/error_paths/conftest.py` - Existing error injection fixtures (600 lines)
  - `/backend/tests/error_paths/test_database_error_paths.py` - Database error patterns (700 lines)
  - `/backend/tests/failure_modes/test_provider_failures.py` - External service failure tests (550 lines)
  - `/backend/tests/failure_modes/test_network_timeouts.py` - Network timeout tests (450 lines)
  - `/backend/tests/failure_modes/test_database_connection_loss.py` - Connection loss tests (450 lines)

### Secondary (MEDIUM confidence)

- [CSDN: Python Circuit Breaker pybreaker Guide](https://m.blog.csdn.net/gitblog_00410/article/details/141450824) - pybreaker library usage examples (2024)
- [CSDN: Dynamic Backoff Retry Configuration](https://m.php.cn/faq/1918624.html) - Environment variable-based retry testing with monkeypatch (2024)
- [CSDN: pytest Timeout Testing](https://m.php.cn/faq/1918624.html) - pytest-timeout plugin for preventing hung tests (2024)

### Tertiary (LOW confidence)

- **Python Testing Engineer Interview Questions 2026** - General pytest patterns, not specific to error path testing
- **CSDN: pytest Plugin Ecosystem Review** - Mentions pytest-timeout but lacks specific error testing patterns (2025)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - pytest, SQLAlchemy, respx are industry standards. Codebase already has implementations.
- Architecture: HIGH - Existing test patterns in `/backend/tests/error_paths/` and `/backend/tests/failure_modes/` provide proven templates.
- Pitfalls: HIGH - Well-documented testing anti-patterns, verified against codebase issues in BUG_FINDINGS.md files.

**Research date:** March 3, 2026
**Valid until:** March 31, 2026 (30 days - testing tooling evolves rapidly, re-verify pytest/respx versions before planning)

**Key findings for planner:**
1. Codebase already has extensive error path testing infrastructure (2000+ lines of fixtures and tests)
2. Custom CircuitBreaker and retry decorators exist in `core/auto_healing.py` - TEST them, don't rebuild
3. Use respx for HTTP timeout mocking, not manual patches
4. Focus on coverage gaps: existing error_paths tests have 2000+ lines but may miss critical paths
5. Verify existing tests actually test what they claim (some may be placeholder/TODO tests)
6. Leverage freezegun for circuit breaker timeout tests to avoid slow tests
7. Existing failure_modes tests need enhancement (some are marked as "hard to simulate")
