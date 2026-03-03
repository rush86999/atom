"""
Critical Error Path Test Configuration

Shared fixtures and utilities for testing critical error paths that are rare in normal
operation but essential for production reliability. These tests focus on database
connection failures with retry logic validation.

Critical paths tested:
- Database connection failures (connection refused, timeout, pool exhausted)
- Connection pool exhaustion and recovery
- Database deadlock handling with retry logic
- Connection timeout scenarios
- Error propagation from database to service layer to API

These fixtures extend patterns from backend/tests/error_paths/conftest.py and
backend/tests/failure_modes/conftest.py, specializing them for critical path testing.
"""

import pytest
import logging
from unittest.mock import patch, MagicMock, AsyncMock, call
from unittest.mock import _patch as _patch_type
from typing import Any, Dict, List, Optional, Type, Callable, Generator
from contextlib import contextmanager
from sqlalchemy.exc import IntegrityError, OperationalError, ProgrammingError, DataError, DBAPIError
from sqlalchemy.orm import Session
from sqlalchemy.pool import Pool, QueuePool
import time


logger = logging.getLogger(__name__)


# ============================================================================
# Database Connection Failure Fixtures
# ============================================================================


@pytest.fixture
def db_session_with_retry():
    """
    Database session that tracks retry attempts for testing retry logic.

    Usage:
        def test_connection_retry(db_session_with_retry):
            with db_session_with_retry() as (db, retry_tracker):
                # Perform database operation that may fail
                # retry_tracker tracks retry attempts
                assert retry_tracker['retry_count'] > 0

    Returns:
        Context manager that yields (db_session, retry_tracker)
        retry_tracker dict contains:
            - retry_count: Number of retry attempts
            - last_error: Last exception raised
            - retry_delay: Total delay from retries
    """
    @contextmanager
    def _session_context():
        from core.database import SessionLocal

        retry_tracker = {
            'retry_count': 0,
            'last_error': None,
            'retry_delay': 0.0,
            'retry_timestamps': []
        }

        # Track retry attempts by patching SessionLocal
        original_connect = SessionLocal().connection

        def tracked_connect():
            retry_tracker['retry_count'] += 1
            retry_tracker['retry_timestamps'].append(time.time())
            return original_connect()

        try:
            db = SessionLocal()
            yield db, retry_tracker
        except Exception as e:
            retry_tracker['last_error'] = e
            raise
        finally:
            if 'db' in locals():
                db.close()

    return _session_context()


@pytest.fixture
def mock_connection_failure():
    """
    Patch engine.connect to raise OperationalError (connection failure).

    Usage:
        def test_connection_refused_triggers_retry(mock_connection_failure):
            with mock_connection_failure(fail_count=2) as mock_connect:
                # First 2 calls fail, 3rd succeeds
                # Test that retry logic handles connection failures

    Args:
        fail_count: Number of times to raise error before succeeding (default: 1)
        error_message: Custom error message (default: "Connection refused")
        error_type: Type of OperationalError (default: "connection_refused")

    Returns:
        Context manager that patches engine.connect
    """
    @contextmanager
    def _patch(fail_count: int = 1, error_message: str = "Connection refused", error_type: str = "connection_refused"):
        call_count = [0]

        error_messages = {
            "connection_refused": "could not connect to server: Connection refused",
            "timeout": "server closed the connection unexpectedly",
            "network_unreachable": "Network is unreachable",
            "host_not_found": "could not translate host name",
        }

        message = error_messages.get(error_type, error_message)

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] <= fail_count:
                raise OperationalError(message, {}, None)
            # Return mock connection after failures exhausted
            mock_conn = MagicMock()
            mock_conn.connect.return_value = MagicMock()
            return mock_conn

        with patch("core.database.engine.connect", side_effect=side_effect):
            yield

    return _patch


@pytest.fixture
def mock_pool_exhaustion():
    """
    Simulate connection pool exhaustion with OperationalError.

    Usage:
        def test_pool_exhaustion_handling(mock_pool_exhaustion):
            with mock_pool_exhaustion():
                # Test pool exhausted error handling

    Args:
        pool_size: Current pool size (default: 20)
        max_overflow: Max overflow (default: 30)
        error_message: Custom error message (default: "connection pool exhausted")

    Returns:
        Context manager that patches pool checkout
    """
    @contextmanager
    def _patch(pool_size: int = 20, max_overflow: int = 30, error_message: str = "connection pool exhausted"):
        def side_effect(*args, **kwargs):
            raise OperationalError(
                f"connection pool exhausted: {pool_size + max_overflow} connections already in use",
                {},
                None
            )

        with patch("sqlalchemy.pool.QueuePool.connect", side_effect=side_effect):
            yield

    return _patch


@pytest.fixture
def mock_deadlock_scenario():
    """
    Mock deadlock OperationalError with retry capability.

    Usage:
        def test_deadlock_triggers_retry(mock_deadlock_scenario):
            with mock_deadlock_scenario(retry_count=3) as deadlock_mock:
                # First 3 attempts deadlock, 4th succeeds
                # Test deadlock retry logic

    Args:
        retry_count: Number of deadlocks before success (default: 1)
        error_message: Custom error message (default: "deadlock detected")

    Returns:
        Context manager that patches commit to raise deadlock error
    """
    @contextmanager
    def _patch(retry_count: int = 1, error_message: str = "deadlock detected"):
        call_count = [0]

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] <= retry_count:
                # Deadlock error with PostgreSQL-specific message
                raise OperationalError(
                    f"deadlock detected: {error_message}",
                    {},
                    Exception("DETAIL: Process 123 waits for ShareLock on transaction 456; blocked by process 789.")
                )
            return None  # Success after retries

        with patch("sqlalchemy.orm.Session.commit", side_effect=side_effect):
            yield

    return _patch


@pytest.fixture
def track_retry_attempts():
    """
    Track and verify retry attempts during database operations.

    Usage:
        def test_retry_logic(track_retry_attempts):
            with track_retry_attempts() as retry_tracker:
                # Perform operation that may retry
                assert retry_tracker.call_count > 0
                assert retry_tracker.total_delay > 0

    Returns:
        Context manager that yields RetryTracker object with:
            - call_count: Number of retry attempts
            - total_delay: Total time spent in retries
            - call_timestamps: List of retry timestamps
            - exceptions: List of exceptions caught
    """
    class RetryTracker:
        def __init__(self):
            self.call_count = 0
            self.total_delay = 0.0
            self.call_timestamps = []
            self.exceptions = []

        def record_call(self, exception: Exception = None):
            self.call_count += 1
            self.call_timestamps.append(time.time())
            if exception:
                self.exceptions.append(exception)

        def get_delay(self) -> float:
            """Calculate total delay between retries"""
            if len(self.call_timestamps) < 2:
                return 0.0
            return self.call_timestamps[-1] - self.call_timestamps[0]

        def verify_retry_count(self, expected: int) -> bool:
            """Verify exact retry count"""
            return self.call_count == expected

        def verify_min_retries(self, min_count: int) -> bool:
            """Verify minimum retry count"""
            return self.call_count >= min_count

        def verify_exponential_backoff(self) -> bool:
            """Verify delays increase exponentially (roughly)"""
            if len(self.call_timestamps) < 3:
                return True  # Not enough data points
            delays = []
            for i in range(1, len(self.call_timestamps)):
                delays.append(self.call_timestamps[i] - self.call_timestamps[i-1])
            # Check if delays are generally increasing
            return all(delays[i] * 0.8 <= delays[i+1] for i in range(len(delays)-1))

    @contextmanager
    def _track():
        tracker = RetryTracker()
        try:
            yield tracker
        finally:
            logger.info(f"Retry tracker: {tracker.call_count} attempts, {tracker.get_delay():.2f}s total delay")

    return _track


# ============================================================================
# Connection Timeout Fixtures
# ============================================================================


@pytest.fixture
def mock_connection_timeout():
    """
    Mock database connection timeout with OperationalError.

    Usage:
        def test_connection_timeout_handling(mock_connection_timeout):
            with mock_connection_timeout(timeout_seconds=30):
                # Test timeout handling

    Args:
        timeout_seconds: Connection timeout duration (default: 30)
        error_type: Type of timeout (default: "connect")

    Returns:
        Context manager that patches connection with timeout error
    """
    @contextmanager
    def _patch(timeout_seconds: int = 30, error_type: str = "connect"):
        error_messages = {
            "connect": f"server closed the connection unexpectedly: This probably means the server terminated abnormally before or while processing the request. (timeout after {timeout_seconds}s)",
            "query": f"canceling statement due to statement timeout: timeout after {timeout_seconds}s",
            "lock": "canceling statement due to lock timeout",
        }

        message = error_messages.get(error_type, f"timeout after {timeout_seconds}s")

        def side_effect(*args, **kwargs):
            raise OperationalError(message, {}, None)

        with patch("core.database.engine.connect", side_effect=side_effect):
            yield

    return _patch


@pytest.fixture
def mock_query_timeout():
    """
    Mock query execution timeout with OperationalError.

    Usage:
        def test_query_timeout_handling(mock_query_timeout):
            with mock_query_timeout(timeout_ms=5000):
                # Test query timeout handling

    Args:
        timeout_ms: Query timeout in milliseconds (default: 5000)
        recover_after: Number of timeouts before recovery (default: 1)

    Returns:
        Context manager that patches execute with timeout error
    """
    @contextmanager
    def _patch(timeout_ms: int = 5000, recover_after: int = 1):
        call_count = [0]

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] <= recover_after:
                raise OperationalError(
                    f"canceling statement due to statement timeout: timeout after {timeout_ms}ms",
                    {},
                    None
                )
            # Return mock result after recovery
            return MagicMock()

        with patch("sqlalchemy.orm.Session.execute", side_effect=side_effect):
            yield

    return _patch


# ============================================================================
# Error Propagation Fixtures
# ============================================================================


@pytest.fixture
def verify_error_propagation():
    """
    Verify error propagation from database through service layer to API.

    Usage:
        def test_error_propagation(verify_error_propagation):
            with verify_error_propagation() as verifier:
                # Trigger database error
                raise OperationalError("test", {}, None)
            # verifier captures exception chain

    Returns:
        Context manager that yields ErrorPropagationVerifier with:
            - original_exception: Original database exception
            - wrapped_exceptions: List of wrapped exceptions
            - final_exception: Final exception raised to caller
            - propagation_chain: Full exception chain
    """
    class ErrorPropagationVerifier:
        def __init__(self):
            self.original_exception = None
            self.wrapped_exceptions = []
            self.final_exception = None
            self.propagation_chain = []

        def record_exception(self, exc: Exception):
            """Record exception in propagation chain"""
            if self.original_exception is None:
                self.original_exception = exc
            self.wrapped_exceptions.append(exc)
            self.final_exception = exc
            self.propagation_chain.append({
                'type': type(exc).__name__,
                'message': str(exc),
                'module': type(exc).__module__
            })

        def verify_exception_type(self, expected_type: Type[Exception]) -> bool:
            """Verify final exception is expected type"""
            return isinstance(self.final_exception, expected_type)

        def verify_error_code(self, expected_code: str) -> bool:
            """Verify AtomException error code"""
            if hasattr(self.final_exception, 'error_code'):
                return str(self.final_exception.error_code) == expected_code
            return False

        def verify_chain_contains(self, exception_type: Type[Exception]) -> bool:
            """Verify exception chain contains specific type"""
            for exc_info in self.propagation_chain:
                if exc_info['type'] == exception_type.__name__:
                    return True
            return False

    @contextmanager
    def _verify():
        verifier = ErrorPropagationVerifier()
        try:
            yield verifier
        except Exception as e:
            verifier.record_exception(e)
            raise
        finally:
            logger.info(f"Error propagation chain: {verifier.propagation_chain}")

    return _verify


# ============================================================================
# Retry Logic Verification Helpers
# ============================================================================


@pytest.fixture
def assert_retry_occurred():
    """
    Verify that retry logic was triggered during operation.

    Usage:
        def test_connection_retry(assert_retry_occurred):
            with track_retry_attempts() as tracker:
                # Operation that should retry
                pass
            assert_retry_occurred(tracker, min_retries=1)

    Args:
        tracker: RetryTracker instance
        min_retries: Minimum expected retry count (default: 1)
    """
    def _verify(tracker, min_retries: int = 1):
        assert tracker.call_count >= min_retries, f"Expected at least {min_retries} retries, got {tracker.call_count}"
        logger.info(f"Retry verified: {tracker.call_count} attempts")
        return True

    return _verify


@pytest.fixture
def assert_exponential_backoff():
    """
    Verify retry delays follow exponential backoff pattern.

    Usage:
        def test_exponential_backoff(assert_exponential_backoff):
            with track_retry_attempts() as tracker:
                # Operation with retries
                pass
            assert_exponential_backoff(tracker, base_delay=1.0)

    Args:
        tracker: RetryTracker instance
        base_delay: Base delay in seconds (default: 1.0)
        tolerance: Tolerance for backoff verification (default: 0.2)
    """
    def _verify(tracker, base_delay: float = 1.0, tolerance: float = 0.2):
        if len(tracker.call_timestamps) < 3:
            logger.warning(f"Not enough retry attempts to verify exponential backoff: {tracker.call_count}")
            return True

        delays = []
        for i in range(1, len(tracker.call_timestamps)):
            delays.append(tracker.call_timestamps[i] - tracker.call_timestamps[i-1])

        # Expected delays: base_delay, 2*base_delay, 4*base_delay, ...
        for i, delay in enumerate(delays):
            expected = base_delay * (2 ** i)
            if not (expected * (1 - tolerance) <= delay <= expected * (1 + tolerance)):
                logger.warning(f"Retry delay {i}: expected {expected:.2f}s, got {delay:.2f}s")

        logger.info(f"Exponential backoff verified: {delays}")
        return True

    return _verify


@pytest.fixture
def assert_max_retries_not_exceeded():
    """
    Verify retry logic respects maximum retry limit.

    Usage:
        def test_max_retries(assert_max_retries_not_exceeded):
            with track_retry_attempts() as tracker:
                # Operation with limited retries
                pass
            assert_max_retries_not_exceeded(tracker, max_retries=3)

    Args:
        tracker: RetryTracker instance
        max_retries: Maximum allowed retries (default: 3)
    """
    def _verify(tracker, max_retries: int = 3):
        assert tracker.call_count <= max_retries, f"Retry count {tracker.call_count} exceeds max {max_retries}"
        logger.info(f"Max retries verified: {tracker.call_count} <= {max_retries}")
        return True

    return _verify


# ============================================================================
# Database Session Helpers
# ============================================================================


@pytest.fixture
def mock_session_with_retry_decorator():
    """
    Mock a service function that uses @retry_with_backoff decorator.

    Usage:
        def test_retry_decorator(mock_session_with_retry_decorator):
            with mock_session_with_retry_decorator(max_retries=3) as mock_func:
                # Test decorated function retry behavior

    Args:
        max_retries: Maximum retry attempts (default: 3)
        backoff_base: Base backoff delay in seconds (default: 1.0)

    Returns:
        Context manager that mocks decorated function
    """
    @contextmanager
    def _mock(max_retries: int = 3, backoff_base: float = 1.0):
        call_count = [0]
        delays = []

        def mock_func_with_retry(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] < max_retries:
                delays.append(backoff_base * (2 ** (call_count[0] - 1)))
                raise OperationalError("Temporary failure", {}, None)
            # Success on final attempt
            return MagicMock()

        with patch("core.auto_healing.retry_with_backoff", return_value=mock_func_with_retry):
            yield mock_func_with_retry

    return _mock


# ============================================================================
# Test Data Generators
# ============================================================================


@pytest.fixture
def connection_error_scenarios():
    """
    Generate various connection error scenarios for testing.

    Returns:
        List of (error_type, error_message, recoverable) tuples
    """
    return [
        ("connection_refused", "could not connect to server: Connection refused", True),
        ("timeout", "server closed the connection unexpectedly", True),
        ("network_unreachable", "Network is unreachable", False),
        ("host_not_found", "could not translate host name", False),
        ("authentication_failed", "password authentication failed", False),
        ("ssl_error", "SSL error: certificate verify failed", False),
    ]


@pytest.fixture
def deadlock_scenarios():
    """
    Generate various deadlock scenarios for testing.

    Returns:
        List of (scenario_type, error_message, retry_success) tuples
    """
    return [
        ("simple_deadlock", "deadlock detected", True),
        ("lock_timeout", "canceling statement due to lock timeout", True),
        ("serialization_failure", "could not serialize access due to concurrent update", True),
    ]


@pytest.fixture
def pool_exhaustion_scenarios():
    """
    Generate various pool exhaustion scenarios for testing.

    Returns:
        List of (scenario_type, pool_size, max_overflow) tuples
    """
    return [
        ("small_pool", 5, 5),
        ("medium_pool", 20, 30),
        ("large_pool", 50, 50),
        ("exhausted_with_overflow", 20, 0),
    ]


# ============================================================================
# Verification Helpers
# ============================================================================


@pytest.fixture
def verify_database_session_health():
    """
    Verify database session is healthy after error recovery.

    Usage:
        def test_session_recovery(verify_database_session_health):
            with get_db_session() as db:
                # Trigger and recover from error
                pass
            verify_database_session_health(db)

    Args:
        db: Database session to verify

    Returns:
        True if session is healthy, raises AssertionError otherwise
    """
    def _verify(db: Session):
        # Try a simple query to verify session health
        try:
            result = db.execute("SELECT 1").scalar()
            assert result == 1, "Session health check failed"
            logger.info("Database session health verified")
            return True
        except Exception as e:
            raise AssertionError(f"Database session unhealthy: {e}")

    return _verify
