"""
Error Path Test Configuration

Shared fixtures and utilities for testing error handling code paths
that are rarely executed in normal operation but critical for production reliability.

Error paths tested:
- Database errors (IntegrityError, OperationalError, DataError)
- Network errors (ConnectionError, TimeoutError)
- LLM errors (APIError, RateLimitError, AuthenticationError)
- Filesystem errors (IOError, OSError)
- Invalid input handling (TypeError, ValueError, KeyError)
- Race conditions and threading errors
- Resource exhaustion (memory, connections, file handles)
"""

import pytest
import logging
from unittest.mock import patch, MagicMock, AsyncMock
from unittest.mock import _patch as _patch_type
from typing import Any, Dict, List, Optional, Type, Callable
from contextlib import contextmanager
from sqlalchemy.exc import IntegrityError, OperationalError, ProgrammingError, DataError
from sqlalchemy.orm import Session
import time


logger = logging.getLogger(__name__)


# ============================================================================
# Error Injection Fixtures
# ============================================================================


@pytest.fixture
def mock_database_error():
    """
    Patch database operations to raise SQLAlchemy exceptions.

    Usage:
        def test_constraint_violation(mock_database_error):
            mock_database_error(patch_target, IntegrityError("unique constraint"))
            # Test that code handles IntegrityError gracefully
    """
    def _patch(target: str, exception: Exception, call_count: int = 1):
        """
        Patch target to raise exception on Nth call.

        Args:
            target: Import path to patch (e.g., "core.database.get_db_session")
            exception: Exception to raise
            call_count: Raise on Nth call (1 = first call, 2 = second call)
        """
        calls = [0]

        def side_effect(*args, **kwargs):
            calls[0] += 1
            if calls[0] == call_count:
                raise exception
            # Return mock response for other calls
            if hasattr(exception, '__class__') and exception.__class__.__name__ == 'IntegrityError':
                # Mock DB session for IntegrityError
                return MagicMock()
            return MagicMock()

        return patch(target, side_effect=side_effect)

    return _patch


@pytest.fixture
def mock_network_error():
    """
    Patch HTTP/network operations to raise connection errors.

    Usage:
        def test_api_timeout(mock_network_error):
            mock_network_error("requests.get", TimeoutError("Connection timed out"))
            # Test retry logic or graceful degradation
    """
    def _patch(target: str, exception: Exception = ConnectionError("Network unreachable")):
        """
        Patch target to raise network exception.

        Args:
            target: Import path to patch
            exception: Network exception to raise (default: ConnectionError)
        """
        return patch(target, side_effect=exception)

    return _patch


@pytest.fixture
def mock_llm_error():
    """
    Patch LLM client operations to raise API errors.

    Usage:
        def test_llm_rate_limit(mock_llm_error):
            mock_llm_error("openai.OpenAI.chat.completions.create", rate_limit_error)
            # Test fallback to next provider
    """
    def _patch(target: str, error_type: str = "rate_limit"):
        """
        Patch LLM client to raise specific error type.

        Args:
            target: Import path to LLM client method
            error_type: One of "rate_limit", "auth", "timeout", "server_error"
        """
        errors = {
            "rate_limit": Exception("Rate limit exceeded (429)"),
            "auth": Exception("Unauthorized (401)"),
            "timeout": TimeoutError("Request timed out"),
            "server_error": Exception("Internal server error (500)"),
            "context_window": Exception("Context window exceeded"),
        }

        exception = errors.get(error_type, errors["server_error"])
        return patch(target, side_effect=exception)

    return _patch


@pytest.fixture
def mock_filesystem_error():
    """
    Patch file operations to raise IO errors.

    Usage:
        def test_file_not_found(mock_filesystem_error):
            mock_filesystem_error("builtins.open", FileNotFoundError("File not found"))
            # Test graceful fallback
    """
    def _patch(target: str, exception: Exception = IOError("Disk error")):
        """
        Patch file operation to raise IO exception.

        Args:
            target: Import path to file operation (e.g., "builtins.open")
            exception: IO exception to raise
        """
        return patch(target, side_effect=exception)

    return _patch


# ============================================================================
# Error Verification Fixtures
# ============================================================================


@pytest.fixture
def assert_logs_error(caplog):
    """
    Verify that an error was logged with correct level and message.

    Usage:
        def test_error_logging(caplog, assert_logs_error):
            with caplog.at_level(logging.ERROR):
                # Trigger error
                service.method_that_fails()
            # Verify error was logged
            assert_logs_error(caplog, "expected error message")
    """
    def _verify(caplog_object, expected_message: str = None, level: int = logging.ERROR):
        """
        Verify error log entry exists.

        Args:
            caplog_object: pytest caplog fixture
            expected_message: Substring to match in log message (optional)
            level: Expected log level (default: ERROR)
        """
        assert caplog_object.records, f"No log records found"

        # Check for matching level
        level_matches = [r for r in caplog_object.records if r.levelno == level]
        assert level_matches, f"No {logging.getLevelName(level)} logs found. Got levels: {[r.levelno for r in caplog_object.records]}"

        if expected_message:
            # Check for message substring
            message_matches = [r for r in level_matches if expected_message.lower() in r.message.lower()]
            assert message_matches, f"No log entry contains '{expected_message}'. Messages: {[r.message for r in level_matches]}"

        return True

    return _verify


@pytest.fixture
def assert_graceful_degradation():
    """
    Verify service remains operational after error.

    Usage:
        def test_graceful_degradation(assert_graceful_degradation, db_session):
            cache = GovernanceCache(max_size=100, ttl_seconds=60)
            # Trigger error
            with pytest.raises(IntegrityError):
                db_session.commit()
            # Verify cache still works
            assert_graceful_degradation(cache, "get", agent_id="test", action_type="stream_chat")
    """
    def _verify(service, method: str, *args, **kwargs):
        """
        Verify service method still works after error.

        Args:
            service: Service instance to test
            method: Method name to call
            *args: Positional args for method
            **kwargs: Keyword args for method
        """
        method_obj = getattr(service, method, None)
        assert method_obj is not None, f"Service has no method '{method}'"

        # Try calling method
        try:
            result = method_obj(*args, **kwargs)
            logger.info(f"Service degraded gracefully: {method}() returned {type(result)}")
            return True
        except Exception as e:
            logger.error(f"Service did NOT degrade gracefully: {method}() raised {type(e).__name__}: {e}")
            raise AssertionError(f"Service method '{method}' failed after error: {e}")

    return _verify


@pytest.fixture
def assert_error_message_contains():
    """
    Verify exception message contains expected pattern.

    Usage:
        def test_error_message(assert_error_message_contains):
            with pytest.raises(ValueError) as exc_info:
                raise ValueError("Invalid agent ID: must be string")
            assert_error_message_contains(exc_info, "Invalid agent ID")
    """
    def _verify(exc_info: pytest.ExceptionInfo, pattern: str, use_regex: bool = False):
        """
        Verify exception message contains pattern.

        Args:
            exc_info: pytest exception info from pytest.raises()
            pattern: String or regex pattern to match
            use_regex: True if pattern is regex (default: False for substring)
        """
        message = str(exc_info.value)

        if use_regex:
            import re
            assert re.search(pattern, message, re.IGNORECASE), f"Exception message does not match regex '{pattern}': {message}"
        else:
            assert pattern.lower() in message.lower(), f"Exception message does not contain '{pattern}': {message}"

        return True

    return _verify


# ============================================================================
# Common Error Scenarios
# ============================================================================


@pytest.fixture
def corrupt_cache_entry():
    """
    Create a corrupted cache entry for testing cache recovery.

    Usage:
        def test_corrupted_cache_entry(corrupt_cache_entry):
            cache = GovernanceCache(max_size=100, ttl_seconds=60)
            corrupted = corrupt_cache_entry()  # Missing 'data' key
            cache._cache["test:stream_chat"] = corrupted
            # Test that cache handles corruption gracefully
    """
    def _create(corruption_type: str = "missing_data") -> Dict[str, Any]:
        """
        Create corrupted cache entry.

        Args:
            corruption_type: Type of corruption
                - "missing_data": Entry lacks 'data' key
                - "missing_timestamp": Entry lacks 'cached_at' key
                - "invalid_data": Entry has non-dict data
                - "expired": Entry has ancient timestamp
        """
        corrupted_entries = {
            "missing_data": {"cached_at": time.time()},  # Missing 'data' key
            "missing_timestamp": {"data": {"allowed": True}},  # Missing 'cached_at' key
            "invalid_data": ["not", "a", "dict"],  # Wrong type
            "expired": {"data": {"allowed": True}, "cached_at": 0},  # Ancient timestamp
        }

        return corrupted_entries.get(corruption_type, corrupted_entries["missing_data"])

    return _create


@pytest.fixture
def invalid_agent_id():
    """
    Generate invalid agent_id values for testing input validation.

    Usage:
        def test_invalid_agent_id(invalid_agent_id):
            cache = GovernanceCache(max_size=100, ttl_seconds=60)
            for invalid_id in invalid_agent_id():
                with pytest.raises((TypeError, ValueError)):
                    cache.get(invalid_id, "stream_chat")
    """
    def _generate(format_type: str = "all") -> List[Any]:
        """
        Generate invalid agent_id values.

        Args:
            format_type: Type of invalid values to return
                - "type": Wrong types (int, list, dict, None)
                - "empty": Empty strings, whitespace
                - "special": Special characters, unicode
                - "all": All of the above (default)

        Returns:
            List of invalid agent_id values
        """
        invalid_values = {
            "type": [12345, None, ["list"], {"dict": "value"}, 3.14],
            "empty": ["", "   ", "\t", "\n"],
            "special": ["agent@example.com", "agent/with/slashes", "agent\\with\\backslashes", "agent with spaces"],
        }

        if format_type == "all":
            all_invalid = []
            for values in invalid_values.values():
                all_invalid.extend(values)
            return all_invalid

        return invalid_values.get(format_type, [])

    return _generate


@pytest.fixture
def malformed_database_result():
    """
    Create malformed database query result for testing ORM error handling.

    Usage:
        def test_malformed_result(malformed_database_result, db_session):
            malformed = malformed_database_result("missing_column")
            with patch.object(db_session, 'query', return_value=malformed):
                # Test that code handles missing columns gracefully
    """
    def _create(malformation_type: str = "missing_column"):
        """
        Create malformed database result.

        Args:
            malformation_type: Type of malformation
                - "missing_column": Result lacks required column
                - "wrong_type": Column has wrong type
                - "null_value": Required column is None
                - "empty_result": Query returns empty list
        """
        # Create mock result with specific malformation
        mock_result = MagicMock()

        if malformation_type == "missing_column":
            # AttributeError when accessing missing column
            mock_result.configure_mock(**{"id": "test-agent", "status": "STUDENT"})
            # Deliberately remove 'name' attribute
            del mock_result.name

        elif malformation_type == "wrong_type":
            mock_result.configure_mock(**{"id": 12345, "status": "STUDENT"})  # id should be str

        elif malformation_type == "null_value":
            mock_result.configure_mock(**{"id": None, "status": "STUDENT"})

        elif malformation_type == "empty_result":
            mock_result = []

        return mock_result

    return _create


@pytest.fixture
def race_condition_scenario():
    """
    Simulate race condition for testing thread safety.

    Usage:
        def test_concurrent_write(race_condition_scenario):
            cache = GovernanceCache(max_size=100, ttl_seconds=60)
            def write_operation():
                cache.set("agent-1", "stream_chat", {"allowed": True})
            # Run concurrent writes
            race_condition_scenario(write_operation, num_threads=10)
    """
    def _simulate(operation: Callable, num_threads: int = 5, delay_ms: int = 10):
        """
        Simulate concurrent execution of operation.

        Args:
            operation: Function to execute concurrently
            num_threads: Number of threads to spawn
            delay_ms: Delay between thread starts (ms) to increase race likelihood
        """
        import threading
        import time

        threads = []
        errors = []

        def thread_func():
            try:
                time.sleep(delay_ms / 1000.0)  # Stagger starts
                operation()
            except Exception as e:
                errors.append(e)

        # Spawn threads
        for _ in range(num_threads):
            thread = threading.Thread(target=thread_func)
            threads.append(thread)
            thread.start()

        # Wait for completion
        for thread in threads:
            thread.join(timeout=5.0)

        # Check for errors
        if errors:
            raise AssertionError(f"Race condition detected: {len(errors)} threads raised exceptions: {errors}")

        return True

    return _simulate


# ============================================================================
# Database Error Scenarios
# ============================================================================


@pytest.fixture
def database_constraint_error():
    """
    Create database constraint violation for testing.

    Usage:
        def test_unique_constraint(database_constraint_error, db_session):
            agent1 = AgentRegistry(id="duplicate-id", name="Agent1")
            db_session.add(agent1)
            db_session.commit()
            agent2 = AgentRegistry(id="duplicate-id", name="Agent2")
            db_session.add(agent2)
            with pytest.raises(IntegrityError):
                db_session.commit()
    """
    def _create(constraint_type: str = "unique") -> Exception:
        """
        Create database constraint error.

        Args:
            constraint_type: Type of constraint
                - "unique": Unique constraint violation
                - "foreign_key": Foreign key violation
                - "not_null": NOT NULL violation
                - "check": CHECK constraint violation
        """
        messages = {
            "unique": "duplicate key value violates unique constraint",
            "foreign_key": "insert or update on table violates foreign key constraint",
            "not_null": "null value in column violates not-null constraint",
            "check": "new row for relation violates check constraint",
        }

        orig = Exception(messages[constraint_type])
        return IntegrityError("INSERT INTO agents", {}, orig)

    return _create


@pytest.fixture
def database_connection_error():
    """
    Simulate database connection failure.

    Usage:
        def test_db_connection_failure(database_connection_error):
            with patch("core.database.create_engine", side_effect=database_connection_error()):
                # Test connection error handling
    """
    def _create(error_type: str = "connection_refused") -> Exception:
        """
        Create database connection error.

        Args:
            error_type: Type of connection error
                - "connection_refused": Server not reachable
                - "timeout": Connection timeout
                - "auth_failed": Authentication failed
                - "pool_exhausted": Connection pool exhausted
        """
        messages = {
            "connection_refused": "could not connect to server: Connection refused",
            "timeout": "server closed the connection unexpectedly",
            "auth_failed": "password authentication failed",
            "pool_exhausted": "connection pool exhausted",
        }

        return OperationalError(messages[error_type], {}, None)

    return _create


# ============================================================================
# LLM Error Scenarios
# ============================================================================


@pytest.fixture
def llm_provider_error():
    """
    Create LLM provider error for testing fallback logic.

    Usage:
        def test_provider_fallback(llm_provider_error):
            with patch("core.llm.byok_handler.OpenAI", side_effect=llm_provider_error("auth")):
                # Test fallback to next provider
    """
    def _create(error_type: str = "rate_limit") -> Exception:
        """
        Create LLM provider error.

        Args:
            error_type: Type of LLM error
                - "rate_limit": Rate limit exceeded (429)
                - "auth": Invalid API key (401)
                - "timeout": Request timeout
                - "server_error": Internal server error (500)
                - "context_window": Prompt too long
        """
        errors = {
            "rate_limit": Exception("Rate limit exceeded (429)"),
            "auth": Exception("Unauthorized (401): Invalid API key"),
            "timeout": TimeoutError("Request timed out after 30s"),
            "server_error": Exception("Internal server error (500)"),
            "context_window": Exception("This model's maximum context length is"),
        }

        return errors.get(error_type, errors["server_error"])

    return _create


# ============================================================================
# Helpers for Testing Async Error Paths
# ============================================================================


@pytest.fixture
def async_error_context():
    """
    Context manager for testing async error paths.

    Usage:
        async def test_async_error(async_error_context):
            async with async_error_context(ValueError("Expected error")):
                await async_function_that_fails()
    """
    @contextmanager
    def _context(expected_exception: Exception):
        """
        Context manager for async error testing.

        Args:
            expected_exception: Exception expected to be raised
        """
        try:
            yield
        except Exception as e:
            if type(e).__name__ == type(expected_exception).__name__:
                logger.info(f"Caught expected error: {type(e).__name__}")
                raise
            else:
                logger.error(f"Unexpected error type: {type(e).__name__} vs {type(expected_exception).__name__}")
                raise

    return _context
