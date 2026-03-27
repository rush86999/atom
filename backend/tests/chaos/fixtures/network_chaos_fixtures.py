"""
Network chaos fixtures using Toxiproxy.

Provides TCP proxy for network latency injection (slow 3G simulation).

Requirements:
    pip install toxiproxy-python

Usage:
    def test_slow_3g(slow_database_proxy, chaos_db_session):
        # Query will have 2000ms latency injected
        agent = chaos_db_session.query(AgentRegistry).first()
"""

import pytest
import time
import os
from typing import Generator

try:
    from toxiproxy import Toxiproxy
    TOXIPROXY_AVAILABLE = True
except ImportError:
    TOXIPROXY_AVAILABLE = False
    Toxiproxy = None


@pytest.fixture(scope="function")
def toxiproxy_server() -> Generator:
    """
    Start Toxiproxy server for network chaos experiments.

    Blast radius: Test network only (localhost:8474)
    Duration: Automatic cleanup after test

    Yields:
        Toxiproxy client instance

    Skip:
        If toxiproxy-python not installed
    """
    if not TOXIPROXY_AVAILABLE:
        pytest.skip("toxiproxy-python not installed: pip install toxiproxy-python")

    # Create Toxiproxy client (assumes Toxiproxy running on localhost:8474)
    toxiproxy = Toxiproxy.create_toxiproxy("localhost:8474")

    yield toxiproxy

    # Cleanup: Destroy all proxies
    try:
        for proxy in toxiproxy.proxies():
            proxy.destroy()
    except Exception:
        pass


@pytest.fixture(scope="function")
def slow_database_proxy(toxiproxy_server):
    """
    Create Toxiproxy proxy for database with slow 3G latency.

    Scenario: 2000ms network latency to database
    Duration: Controlled by context manager
    Blast radius: Test database only

    Yields:
        Toxiproxy proxy object with toxic() context manager

    Example:
        with slow_database_proxy.toxic("latency", latency_ms=2000, jitter=0):
            # Database queries will have 2 second latency
            agent = db_session.query(Agent).first()
    """
    # Get database URL from environment
    database_url = os.getenv("DATABASE_URL", "sqlite:///./test_chaos.db")

    # Parse database host and port (for PostgreSQL)
    # For SQLite, we'll create a mock proxy for testing
    if "sqlite" in database_url:
        # SQLite doesn't use network, create mock proxy for interface compatibility
        class MockProxy:
            def __init__(self):
                self.name = "mock_sqlite_proxy"
            def toxic(self, toxic_type, **kwargs):
                # Simulate latency with time.sleep for SQLite
                class LatencyContext:
                    def __init__(self, latency_ms):
                        self.latency_ms = latency_ms
                    def __enter__(self):
                        time.sleep(self.latency_ms / 1000.0)
                        return self
                    def __exit__(self, *args):
                        time.sleep(self.latency_ms / 1000.0)
                return LatencyContext(kwargs.get("latency_ms", 2000))
            def destroy(self):
                pass

        yield MockProxy()
        return

    # For PostgreSQL/MySQL, create real Toxiproxy proxy
    # Extract host:port from database URL
    # Format: postgresql://user:pass@localhost:5432/db
    upstream_host = "localhost"
    upstream_port = 5432

    try:
        proxy = toxiproxy_server.create_proxy(
            name="db_proxy",
            upstream=f"{upstream_host}:{upstream_port}",
            listen="localhost:5555"
        )

        yield proxy

    finally:
        # Cleanup: Destroy proxy
        try:
            proxy.destroy()
        except Exception:
            pass


@pytest.fixture(scope="function")
def slow_3g_latency(toxiproxy_server):
    """
    Create Toxiproxy proxy with slow 3G network conditions.

    Slow 3G profile:
    - Download: 500 Kbps (~62.5 KB/s)
    - Upload: 500 Kbps (~62.5 KB/s)
    - Latency: 2000ms RTT

    Blast radius: Test network only

    Yields:
        Toxiproxy proxy with slow_3g_toxic() method
    """
    proxy = toxiproxy_server.create_proxy(
        name="slow_3g_proxy",
        upstream="localhost:8000",  # Backend API
        listen="localhost:5556"
    )

    def slow_3g_toxic():
        """Apply slow 3G network conditions."""
        return proxy.toxic("latency", latency_ms=2000, jitter=500)

    yield slow_3g_toxic

    proxy.destroy()
