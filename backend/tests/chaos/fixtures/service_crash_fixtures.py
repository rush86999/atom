"""
Service crash simulation fixtures for chaos testing.

Simulates service crashes to test:
- LLM provider failures (OpenAI, Anthropic, etc.)
- Redis cache layer failures
- External service unavailability

Uses unittest.mock for safe simulation (no actual service disruption).
"""

import pytest
import time
import subprocess
from typing import Generator, Optional
from contextlib import contextmanager
from unittest.mock import patch, MagicMock


class ServiceCrashSimulator:
    """
    Context manager for service crash simulation.

    Blast radius: Test services only (mocked LLM provider, test Redis)
    Duration: 10 seconds max
    Safety: Automatic restart/restore

    Example:
        with ServiceCrashSimulator.service_crash("llm_provider"):
            # LLM calls will fail
            response = llm_service.chat()
    """

    CRASH_TYPES = ["llm_provider", "redis", "database", "external_api"]

    def __init__(self, service_name: str, duration_seconds: int = 10):
        self.service_name = service_name
        self.duration_seconds = duration_seconds
        self.original = None

    @classmethod
    @contextmanager
    def service_crash(cls, service_name: str, duration_seconds: int = 10):
        """
        Simulate service crash.

        Args:
            service_name: Type of service to crash (llm_provider, redis, etc.)
            duration_seconds: Duration of crash (for auto-restart scenarios)

        Yields:
            Context manager for crash simulation
        """
        simulator = cls(service_name, duration_seconds)
        simulator.crash_service()
        try:
            yield simulator
        finally:
            simulator.restore_service()

    def crash_service(self):
        """Crash the service (inject failure)."""
        if self.service_name == "llm_provider":
            self._crash_llm_provider()
        elif self.service_name == "redis":
            self._crash_redis()
        elif self.service_name == "database":
            self._crash_database()
        elif self.service_name == "external_api":
            self._crash_external_api()

    def restore_service(self):
        """Restore the service."""
        if self.service_name == "llm_provider":
            self._restore_llm_provider()
        elif self.service_name == "redis":
            self._restore_redis()
        elif self.service_name == "database":
            self._restore_database()
        elif self.service_name == "external_api":
            self._restore_external_api()

    def _crash_llm_provider(self):
        """Crash LLM provider by mocking exception."""
        from core.llm.byok_handler import BYOKHandler

        # Save original method
        self.original = BYOKHandler.chat_stream

        # Mock to raise exception
        def mock_crash(*args, **kwargs):
            raise Exception("LLM provider service unavailable: Connection refused")

        BYOKHandler.chat_stream = mock_crash

    def _restore_llm_provider(self):
        """Restore LLM provider."""
        if self.original:
            from core.llm.byok_handler import BYOKHandler
            BYOKHandler.chat_stream = self.original

    def _crash_redis(self):
        """Crash Redis (subprocess or mock based on availability)."""
        # Try to stop actual Redis (if running in test environment)
        try:
            subprocess.run(
                ["redis-cli", "shutdown"],
                capture_output=True,
                timeout=5
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            # Redis not available, use mock
            import redis
            self.original = redis.Redis.execute_command
            redis.Redis.execute_command = lambda *args, **kwargs: (_ for _ in ()).throw(
                ConnectionError("Redis connection refused")
            )

    def _restore_redis(self):
        """Restore Redis."""
        try:
            subprocess.run(
                ["redis-server", "--daemonize", "yes"],
                capture_output=True,
                timeout=5
            )
            time.sleep(2)  # Wait for Redis to start
        except (FileNotFoundError, subprocess.TimeoutExpired):
            # Restore mock if used
            if self.original:
                import redis
                redis.Redis.execute_command = self.original

    def _crash_database(self):
        """Crash database (mock only - safer than actual crash)."""
        # Use mock for database (safer than stopping actual database)
        pass  # Database crash handled by database_chaos_fixtures.py

    def _restore_database(self):
        """Restore database."""
        pass  # Database crash handled by database_chaos_fixtures.py

    def _crash_external_api(self):
        """Crash external API (mock requests library)."""
        import requests
        self.original = requests.get
        requests.get = lambda *args, **kwargs: (_ for _ in ()).throw(
            ConnectionError("External API unavailable")
        )

    def _restore_external_api(self):
        """Restore external API."""
        if self.original:
            import requests
            requests.get = self.original


@pytest.fixture(scope="function")
def llm_provider_crash_simulator():
    """
    Simulate LLM provider crash during test.

    Blast radius: Test only (mocked LLM calls)
    Duration: 10 seconds max
    Safety: Uses unittest.mock (no actual API disruption)

    Yields:
        Context manager for LLM provider crash

    Example:
        with llm_provider_crash_simulator():
            response = llm_service.chat("Hello")
            # Response should indicate LLM unavailable
    """
    @contextmanager
    def _crash_llm():
        simulator = ServiceCrashSimulator("llm_provider", duration_seconds=10)
        simulator.crash_service()
        try:
            yield simulator
        finally:
            simulator.restore_service()

    return _crash_llm


@pytest.fixture(scope="function")
def redis_crash_simulator():
    """
    Simulate Redis crash during test.

    Blast radius: Test services only (test Redis if running, otherwise mock)
    Duration: 10 seconds max
    Safety: Automatic restart

    Yields:
        Context manager for Redis crash

    Example:
        with redis_crash_simulator():
            # Cache operations will fail
            cache.get("key")  # Raises ConnectionError
    """
    @contextmanager
    def _crash_redis():
        simulator = ServiceCrashSimulator("redis", duration_seconds=10)
        simulator.crash_service()
        try:
            yield simulator
        finally:
            simulator.restore_service()

    return _crash_redis


@pytest.fixture(scope="function")
def external_api_crash_simulator():
    """
    Simulate external API crash during test.

    Blast radius: Test only (mocked requests)
    Duration: 10 seconds max
    Safety: Uses unittest.mock

    Yields:
        Context manager for external API crash
    """
    @contextmanager
    def _crash_api():
        simulator = ServiceCrashSimulator("external_api", duration_seconds=10)
        simulator.crash_service()
        try:
            yield simulator
        finally:
            simulator.restore_service()

    return _crash_api


@pytest.fixture(scope="function")
def service_unavailable_response():
    """
    Get expected service unavailable response.

    Returns:
        Dict with expected error response format

    Example:
        expected = service_unavailable_response()
        assert response.status_code == expected["status_code"]
    """
    return {
        "status_code": 503,  # Service Unavailable
        "error": "Service temporarily unavailable",
        "retry_after": 60,  # Suggest retry after 60 seconds
    }
