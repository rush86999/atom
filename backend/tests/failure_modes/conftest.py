"""
Failure Mode Test Configuration

Shared fixtures and utilities for testing how the system behaves when external
dependencies fail (network timeouts, provider failures, database connection loss,
resource exhaustion).

Failure modes tested:
- Network timeouts (LLM providers, database, WebSocket)
- Provider failures (all providers fail, rate limiting, fallback)
- Database connection loss (pool exhaustion, deadlocks, connection closed)
- Resource exhaustion (out of memory, disk full, file descriptors)
- Graceful degradation (system remains partially functional)
"""

import pytest
import asyncio
import logging
from unittest.mock import patch, MagicMock, AsyncMock
from unittest.mock import _patch as _patch_type
from typing import Any, Dict, List, Optional, Type, Callable
from contextlib import contextmanager
from sqlalchemy.exc import IntegrityError, OperationalError, ProgrammingError, DataError, DBAPIError
from sqlalchemy.orm import Session
import time
import socket


logger = logging.getLogger(__name__)


# ============================================================================
# Network Timeout Fixtures
# ============================================================================


@pytest.fixture
def mock_llm_timeout():
    """
    Mock LLM client to raise asyncio.TimeoutError.

    Usage:
        def test_llm_provider_timeout(mock_llm_timeout):
            with mock_llm_timeout("core.llm.byok_handler.OpenAI"):
                # Test timeout handling
    """
    def _patch(target: str, timeout_message: str = "Request timed out after 30s"):
        """
        Patch LLM client to raise timeout.

        Args:
            target: Import path to LLM client
            timeout_message: Timeout error message
        """
        return patch(target, side_effect=asyncio.TimeoutError(timeout_message))

    return _patch


@pytest.fixture
def mock_db_timeout():
    """
    Mock database connection to raise OperationalError with timeout.

    Usage:
        def test_database_timeout(mock_db_timeout):
            with mock_db_timeout():
                # Test timeout handling
    """
    def _patch(error_message: str = "connection timeout"):
        """
        Patch database to raise timeout error.

        Args:
            error_message: Error message for timeout
        """
        return patch("core.database.engine.connect", side_effect=OperationalError(error_message, None, None))

    return _patch


@pytest.fixture
def mock_websocket_timeout():
    """
    Mock WebSocket to raise ConnectionClosed.

    Usage:
        def test_websocket_timeout(mock_websocket_timeout):
            with mock_websocket_timeout():
                # Test WebSocket timeout handling
    """
    def _patch(code: int = 1000, reason: str = "Connection timeout"):
        """
        Patch WebSocket to raise ConnectionClosed.

        Args:
            code: WebSocket close code
            reason: Close reason
        """
        try:
            from websockets.exceptions import ConnectionClosed
            return patch("core.llm.byok_handler.ConnectionClosed", side_effect=ConnectionClosed(code, reason))
        except ImportError:
            # Fallback for environments without websockets
            return patch("core.llm.byok_handler.ConnectionClosed", side_effect=Exception(f"WebSocket closed: {code} {reason}"))

    return _patch


# ============================================================================
# Provider Failure Fixtures
# ============================================================================


@pytest.fixture
def mock_all_providers_fail():
    """
    Mock all LLM providers to raise Exception.

    Usage:
        def test_all_providers_fail(mock_all_providers_fail):
            with mock_all_providers_fail(handler):
                # Test fallback logic
    """
    def _patch(handler, error_type: str = "API error"):
        """
        Mock all providers in handler to fail.

        Args:
            handler: BYOKHandler instance
            error_type: Type of error to raise
        """
        original_clients = {}

        # Store original clients
        for provider_id, client in handler.clients.items():
            original_clients[provider_id] = client

        # Mock all providers to fail
        for provider_id in handler.clients.keys():
            mock_client = MagicMock()
            mock_client.chat.completions.create = AsyncMock(side_effect=Exception(f"{provider_id}: {error_type}"))
            handler.clients[provider_id] = mock_client
            handler.async_clients[provider_id] = mock_client

        return original_clients

    return _patch


@pytest.fixture
def mock_primary_provider_fail():
    """
    Mock primary provider to fail, secondary succeeds.

    Usage:
        def test_primary_provider_fails(mock_primary_provider_fail):
            with mock_primary_provider_fail(handler, primary="openai", secondary="anthropic"):
                # Test fallback to secondary
    """
    def _patch(handler, primary: str = "openai", secondary: str = "anthropic"):
        """
        Mock primary provider to fail, secondary to succeed.

        Args:
            handler: BYOKHandler instance
            primary: Primary provider ID (will fail)
            secondary: Secondary provider ID (will succeed)
        """
        # Mock primary to fail
        if primary in handler.clients:
            mock_primary = MagicMock()
            mock_primary.chat.completions.create = AsyncMock(side_effect=Exception(f"{primary} API error"))
            handler.clients[primary] = mock_primary
            handler.async_clients[primary] = mock_primary

        # Mock secondary to succeed
        if secondary in handler.clients:
            mock_secondary = MagicMock()
            mock_secondary.chat.completions.create = AsyncMock(
                return_value=MagicMock(
                    choices=[MagicMock(message=MagicMock(content=f"Success from {secondary}"))]
                )
            )
            handler.clients[secondary] = mock_secondary
            handler.async_clients[secondary] = mock_secondary

    return _patch


@pytest.fixture
def mock_provider_rate_limit():
    """
    Mock provider to raise rate limit error.

    Usage:
        def test_provider_rate_limit(mock_provider_rate_limit):
            with mock_provider_rate_limit(handler, "openai"):
                # Test rate limit handling
    """
    def _patch(handler, provider_id: str = "openai"):
        """
        Mock provider to raise rate limit error.

        Args:
            handler: BYOKHandler instance
            provider_id: Provider to mock
        """
        if provider_id in handler.clients:
            mock_client = MagicMock()
            mock_client.chat.completions.create = AsyncMock(
                side_effect=Exception(f"Rate limit exceeded (429) for {provider_id}")
            )
            handler.clients[provider_id] = mock_client
            handler.async_clients[provider_id] = mock_client

    return _patch


# ============================================================================
# Database Connection Fixtures
# ============================================================================


@pytest.fixture
def mock_pool_exhausted():
    """
    Mock connection pool to raise OperationalError (pool exhausted).

    Usage:
        def test_pool_exhausted(mock_pool_exhausted):
            with mock_pool_exhausted():
                # Test pool exhaustion handling
    """
    def _patch():
        """
        Patch database connection to raise pool exhausted error.
        """
        return patch("core.database.engine.connect", side_effect=OperationalError("connection pool exhausted", None, None))

    return _patch


@pytest.fixture
def mock_connection_closed():
    """
    Mock connection to close mid-transaction.

    Usage:
        def test_connection_closed(mock_connection_closed):
            with mock_connection_closed():
                # Test connection closed handling
    """
    def _patch():
        """
        Patch database operations to raise connection closed error.
        """
        return patch("sqlalchemy.orm.Session.execute", side_effect=DBAPIError("connection closed", None, None))

    return _patch


@pytest.fixture
def mock_deadlock():
    """
    Mock commit to raise OperationalError (deadlock detected).

    Usage:
        def test_deadlock(mock_deadlock):
            with mock_deadlock():
                # Test deadlock handling
    """
    def _patch():
        """
        Patch database commit to raise deadlock error.
        """
        return patch("sqlalchemy.orm.Session.commit", side_effect=OperationalError("deadlock detected", None, None))

    return _patch


# ============================================================================
# Resource Exhaustion Fixtures
# ============================================================================


@pytest.fixture
def mock_memory_error():
    """
    Mock MemoryError via side_effect.

    Usage:
        def test_memory_error(mock_memory_error):
            with mock_memory_error():
                # Test MemoryError handling
    """
    def _patch(target: str):
        """
        Patch target to raise MemoryError.

        Args:
            target: Import path to patch
        """
        return patch(target, side_effect=MemoryError("Out of memory"))

    return _patch


@pytest.fixture
def mock_disk_full():
    """
    Mock disk full OperationalError.

    Usage:
        def test_disk_full(mock_disk_full):
            with mock_disk_full():
                # Test disk full handling
    """
    def _patch():
        """
        Patch database write to raise disk full error.
        """
        return patch("sqlalchemy.orm.Session.execute", side_effect=OperationalError("disk full", None, None))

    return _patch


@pytest.fixture
def assert_graceful_degradation():
    """
    Verify system continues operating after failure.

    Usage:
        def test_graceful_degradation(assert_graceful_degradation):
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


# ============================================================================
# Helper Functions
# ============================================================================


@pytest.fixture
def assert_timeout_handled():
    """
    Verify timeout exception raised and handled.

    Usage:
        def test_timeout_handled(assert_timeout_handled):
            with pytest.raises(asyncio.TimeoutError):
                await operation_that_times_out()
            assert_timeout_handled("timeout occurred")
    """
    def _verify(error_message: str = None):
        """
        Verify timeout was handled.

        Args:
            error_message: Expected substring in error message
        """
        if error_message:
            assert "timeout" in error_message.lower(), f"Expected 'timeout' in error message: {error_message}"
        return True

    return _verify


@pytest.fixture
def assert_fallback_triggered():
    """
    Verify fallback provider attempted.

    Usage:
        def test_fallback(assert_fallback_triggered):
            # After primary fails
            assert_fallback_triggered(mock_secondary_client.chat.completions.create.called)
    """
    def _verify(secondary_method_called: bool, secondary_provider: str = "secondary"):
        """
        Verify fallback was triggered.

        Args:
            secondary_method_called: Whether secondary method was called
            secondary_provider: Name of secondary provider
        """
        assert secondary_method_called, f"Fallback to {secondary_provider} was not triggered"
        logger.info(f"Fallback to {secondary_provider} verified")
        return True

    return _verify


@pytest.fixture
def assert_recovery_succeeded():
    """
    Verify system recovered after failure.

    Usage:
        def test_recovery(assert_recovery_succeeded):
            # Trigger failure
            with pytest.raises(OperationalError):
                db.execute("SELECT 1")
            # Try again - should succeed
            result = db.execute("SELECT 1")
            assert_recovery_succeeded(result is not None)
    """
    def _verify(recovery_condition: bool, recovery_description: str = "system recovered"):
        """
        Verify recovery succeeded.

        Args:
            recovery_condition: Boolean condition indicating recovery
            recovery_description: Description of what recovered
        """
        assert recovery_condition, f"System did not recover: {recovery_description}"
        logger.info(f"Recovery verified: {recovery_description}")
        return True

    return _verify


# ============================================================================
# Common Failure Scenarios
# ============================================================================


@pytest.fixture
def network_timeout_scenario():
    """
    Simulate network timeout for testing.

    Usage:
        def test_network_timeout(network_timeout_scenario):
            with network_timeout_scenario("openai"):
                response = await handler.generate_response("test")
                assert "timeout" in response.lower()
    """
    @contextmanager
    def _context(provider_id: str = "openai"):
        """
        Context manager for network timeout testing.

        Args:
            provider_id: Provider to timeout
        """
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(
            side_effect=asyncio.TimeoutError(f"{provider_id} request timed out after 30s")
        )

        with patch(f"core.llm.byok_handler.{provider_id.capitalize()}.API", return_value=mock_client):
            yield

    return _context


@pytest.fixture
def provider_cascade_scenario():
    """
    Simulate all providers failing sequentially.

    Usage:
        def test_provider_cascade(provider_cascade_scenario):
            with provider_cascade_scenario(["openai", "anthropic", "deepseek"]):
                response = await handler.generate_response("test")
                assert "all providers failed" in response.lower()
    """
    @contextmanager
    def _context(provider_ids: List[str]):
        """
        Context manager for provider cascade testing.

        Args:
            provider_ids: List of provider IDs to fail sequentially
        """
        mocks = {}
        for provider_id in provider_ids:
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(
                side_effect=Exception(f"{provider_id} API error")
            )
            mocks[provider_id] = mock_client

        with patch("core.llm.byok_handler.BYOKHandler.clients", mocks):
            with patch("core.llm.byok_handler.BYOKHandler.async_clients", mocks):
                yield

    return _context


@pytest.fixture
def connection_pool_scenario():
    """
    Simulate connection pool exhaustion.

    Usage:
        def test_pool_exhaustion(connection_pool_scenario):
            with connection_pool_scenario():
                with pytest.raises(OperationalError):
                    db.execute("SELECT 1")
    """
    @contextmanager
    def _context():
        """
        Context manager for connection pool testing.
        """
        with patch("core.database.engine.connect", side_effect=OperationalError("pool exhausted", None, None)):
            yield

    return _context


@pytest.fixture
def resource_exhaustion_scenario():
    """
    Simulate resource exhaustion (memory, disk, file descriptors).

    Usage:
        def test_resource_exhaustion(resource_exhaustion_scenario):
            with resource_exhaustion_scenario("memory"):
                # Test MemoryError handling
    """
    @contextmanager
    def _context(resource_type: str = "memory"):
        """
        Context manager for resource exhaustion testing.

        Args:
            resource_type: Type of resource ("memory", "disk", "file_descriptor")
        """
        if resource_type == "memory":
            exception = MemoryError("Out of memory")
        elif resource_type == "disk":
            exception = OperationalError("disk full", None, None)
        elif resource_type == "file_descriptor":
            exception = OSError("Too many open files")
        else:
            exception = Exception("Resource exhausted")

        with patch("core.database.SessionLocal", side_effect=exception):
            yield

    return _context


# ============================================================================
# Async Error Context Helpers
# ============================================================================


@pytest.fixture
def async_failure_context():
    """
    Context manager for testing async failure scenarios.

    Usage:
        async def test_async_failure(async_failure_context):
            async with async_failure_context(ValueError("Expected error")):
                await async_function_that_fails()
    """
    @contextmanager
    def _context(expected_exception: Exception):
        """
        Context manager for async failure testing.

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


# ============================================================================
# Test Data Generators
# ============================================================================


@pytest.fixture
def timeout_scenarios():
    """
    Generate various timeout scenarios for testing.

    Returns:
        List of (timeout_type, error_message) tuples
    """
    return [
        ("connection", "Connection timed out"),
        ("read", "Read operation timed out"),
        ("write", "Write operation timed out"),
        ("network", "Network timeout"),
        ("request", "Request timed out after 30s"),
    ]


@pytest.fixture
def provider_error_scenarios():
    """
    Generate various provider error scenarios for testing.

    Returns:
        List of (error_type, error_message) tuples
    """
    return [
        ("rate_limit", "Rate limit exceeded (429)"),
        ("auth", "Unauthorized (401): Invalid API key"),
        ("timeout", "Request timed out"),
        ("server_error", "Internal server error (500)"),
        ("unavailable", "Service unavailable (503)"),
        ("context_window", "This model's maximum context length is"),
    ]


@pytest.fixture
def database_error_scenarios():
    """
    Generate various database error scenarios for testing.

    Returns:
        List of (error_type, exception_class) tuples
    """
    return [
        ("pool_exhausted", OperationalError("connection pool exhausted", None, None)),
        ("timeout", OperationalError("connection timeout", None, None)),
        ("deadlock", OperationalError("deadlock detected", None, None)),
        ("connection_closed", DBAPIError("connection closed", None, None)),
        ("disk_full", OperationalError("disk full", None, None)),
    ]


@pytest.fixture
def resource_error_scenarios():
    """
    Generate various resource error scenarios for testing.

    Returns:
        List of (resource_type, exception_class) tuples
    """
    return [
        ("memory", MemoryError("Out of memory")),
        ("disk", OperationalError("disk full", None, None)),
        ("file_descriptor", OSError("Too many open files")),
        ("socket", socket.error("Too many open sockets")),
    ]
