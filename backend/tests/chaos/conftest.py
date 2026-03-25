"""
Chaos Engineering Test Configuration

Fixtures for chaos engineering tests:
- chaos_db_session: Isolated test database per test
- bug_filing_service: BugFilingService for automated bug filing
- chaos_coordinator: ChaosCoordinator instance
- slow_database_proxy: Toxiproxy proxy for database latency injection
- toxiproxy_server: Toxiproxy client for network chaos
- memory_pressure_injector: Memory pressure injection fixture
- system_memory_monitor: System memory monitoring fixture
- heap_snapshot: Heap snapshot fixture for leak detection
- memory_pressure_thresholds: Memory pressure threshold values
"""

import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from core.models import Base

from tests.chaos.core.chaos_coordinator import ChaosCoordinator
from tests.bug_discovery.bug_filing_service import BugFilingService

# Import network chaos fixtures
try:
    from tests.chaos.fixtures.network_chaos_fixtures import toxiproxy_server, slow_database_proxy
except ImportError:
    # toxiproxy-python not installed, fixtures will skip tests
    pass

# Import memory chaos fixtures
try:
    from tests.chaos.fixtures.memory_chaos_fixtures import (
        MemoryPressureInjector,
        memory_pressure_injector,
        system_memory_monitor,
        heap_snapshot,
        memory_pressure_thresholds,
    )
except ImportError:
    # psutil not installed, fixtures will skip tests
    pass

# Import database chaos fixtures
try:
    from tests.chaos.fixtures.database_chaos_fixtures import database_connection_dropper
except ImportError:
    # Database chaos fixtures not available
    pass

# Import Redis chaos fixtures
try:
    from tests.chaos.fixtures.redis_chaos_fixtures import redis_crash_simulator
except ImportError:
    # Redis chaos fixtures not available
    pass


@pytest.fixture(scope="function")
def chaos_db_session():
    """
    Isolated database for chaos testing.

    IMPORTANT: This must be a separate database from other tests
    to prevent interference with concurrent test runs.

    Yields:
        SQLAlchemy session for test database

    Cleanup:
        Drops database and removes test_chaos.db file after test
    """
    # Create test database
    db_url = "sqlite:///./test_chaos.db"
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)

    Session = sessionmaker(bind=engine)
    session = Session()

    yield session

    # Cleanup: Drop database after test
    session.close()
    try:
        os.remove("./test_chaos.db")
    except FileNotFoundError:
        pass


@pytest.fixture(scope="function")
def bug_filing_service():
    """
    BugFilingService instance for automated bug filing.

    Returns:
        BugFilingService instance if GITHUB_TOKEN and GITHUB_REPOSITORY are configured
        None otherwise (tests should handle this gracefully)

    Environment variables:
        GITHUB_TOKEN: GitHub Personal Access Token with repo scope
        GITHUB_REPOSITORY: Repository in format "owner/repo"
    """
    github_token = os.getenv("GITHUB_TOKEN")
    github_repository = os.getenv("GITHUB_REPOSITORY")

    if not github_token or not github_repository:
        # Return None if GitHub credentials not configured
        # Tests should handle this gracefully
        return None

    return BugFilingService(github_token, github_repository)


@pytest.fixture(scope="function")
def chaos_coordinator(chaos_db_session, bug_filing_service):
    """
    ChaosCoordinator instance for orchestrating chaos experiments.

    Args:
        chaos_db_session: Isolated test database session
        bug_filing_service: BugFilingService for automated bug filing

    Returns:
        ChaosCoordinator instance configured with test database and bug filing
    """
    return ChaosCoordinator(
        db_session=chaos_db_session,
        bug_filing_service=bug_filing_service
    )


@pytest.fixture(scope="function")
def assert_blast_radius():
    """
    Fixture to run blast radius checks before chaos test.

    Runs all blast radius safety checks before test execution.
    Ensures failure injection is scoped to test environment only.

    Raises:
        AssertionError: If blast radius checks fail (test stops immediately)

    Usage:
        @pytest.mark.chaos
        def test_network_latency_chaos(assert_blast_radius):
            # Test runs only after blast radius checks pass
            ...
    """
    from tests.chaos.core.blast_radius_controls import assert_blast_radius as _assert
    _assert()
    yield
