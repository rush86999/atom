"""
Quality test fixtures for test suite health verification.

Provides fixtures for flakiness detection, test isolation verification,
and collection stability testing.
"""

import os
import sys
import pytest
import subprocess
import tempfile
from pathlib import Path

# Set TESTING environment variable BEFORE any imports
os.environ["TESTING"] = "1"

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from core.database import Base
from core.governance_cache import GovernanceCache


# ============================================================================
# Random Seed Fixture for Reproducible Test Runs
# ============================================================================

@pytest.fixture(scope="session")
def random_seed():
    """
    Generate consistent random seed for reproducible test runs.

    This seed is logged by pytest-randomly and can be used to reproduce
    flaky test failures. The seed is automatically applied by pytest-randomly
    via the --randomly-seed option.

    Usage:
        pytest tests/integration/quality/ --randomly-seed=1234

    The seed will be logged in test output:
        pytest-randomly seeded tests using seed=1234
    """
    # Use pytest-randomly's built-in seed fixture if available
    try:
        seed = pytest.config.getoption("randomly_seed")
    except (AttributeError, ValueError):
        # Fallback to fixed seed if pytest-randomly not available
        seed = 1234
    return seed


# ============================================================================
# Repeat Count Fixture for Flakiness Detection
# ============================================================================

@pytest.fixture(scope="session")
def repeat_count():
    """
    Configurable repeat count for flakiness detection tests.

    Default: 5 iterations per test
    Override via pytest mark: @pytest.mark.repeat(10)

    This fixture provides the repeat count used by flakiness detection
    tests to verify consistent behavior across multiple executions.

    Usage:
        @pytest.mark.repeat(5)
        def test_deterministic_behavior():
            # Test runs 5 times
            pass
    """
    return 5


# ============================================================================
# Isolated Database Fixture for Quality Tests
# ============================================================================

@pytest.fixture(scope="function")
def test_database():
    """
    Isolated database for testing test isolation.

    Creates a fresh in-memory database for each quality test to verify
    no data leaks between tests. The database is cleaned up after each test.

    Usage:
        def test_database_isolation(test_database):
            # Insert test data
            # Data is automatically cleaned up after test
            pass
    """
    # Use file-based temp SQLite for tests
    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)

    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        echo=False
    )

    # Store path for cleanup
    engine._test_db_path = db_path

    # Create tables
    try:
        Base.metadata.create_all(engine, checkfirst=True)
    except Exception:
        # If create_all fails, create tables individually
        for table in Base.metadata.tables.values():
            try:
                table.create(engine, checkfirst=True)
            except Exception:
                # Skip tables that can't be created
                continue

    # Create session
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()

    yield session

    # Cleanup
    session.close()
    engine.dispose()
    # Delete temp database file
    if hasattr(engine, '_test_db_path'):
        try:
            os.unlink(engine._test_db_path)
        except Exception:
            pass


# ============================================================================
# Cache Clearing Fixture for Quality Tests
# ============================================================================

@pytest.fixture(scope="function")
def clean_cache():
    """
    Clear all caches before quality tests.

    This fixture clears governance_cache, LRU caches, and other cached data
    to verify cache isolation between tests.

    Usage:
        def test_cache_isolation(clean_cache):
            # Populate governance_cache
            # Cache is automatically cleared after test
            pass
    """
    # Clear governance cache if available
    try:
        from core.governance_cache import governance_cache
        governance_cache.clear()
    except (ImportError, AttributeError):
        pass

    # Clear all LRU caches
    import functools
    for obj in dir(globals().get('__main__', type('', (), {}))):
        try:
            if hasattr(obj, 'cache_clear'):
                obj.cache_clear()
        except Exception:
            pass

    yield

    # Clear again after test
    try:
        from core.governance_cache import governance_cache
        governance_cache.clear()
    except (ImportError, AttributeError):
        pass


# ============================================================================
# Subprocess Runner Fixture for Collection Stability Tests
# ============================================================================

@pytest.fixture(scope="function")
def subprocess_runner():
    """
    Helper for running pytest in subprocess.

    Used for collection stability tests to verify test collection is
    consistent across multiple runs. Captures stdout/stderr for analysis.

    Usage:
        def test_collection_consistency(subprocess_runner):
            result = subprocess_runner([
                "pytest", "tests/integration/", "--collect-only"
            ])
            assert result.returncode == 0
            assert "test session starts" in result.stdout

    Returns:
        function: Subprocess runner that takes command list and returns
                  CompletedProcess with stdout, stderr, returncode
    """
    def _run(cmd, cwd=None, timeout=60):
        """
        Run command in subprocess and capture output.

        Args:
            cmd: Command list to execute
            cwd: Working directory (defaults to backend root)
            timeout: Timeout in seconds (default: 60)

        Returns:
            CompletedProcess with stdout, stderr, returncode
        """
        if cwd is None:
            cwd = str(Path(__file__).parent.parent.parent.parent)

        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout
        )

        return result

    return _run


# ============================================================================
# Mock WebSocket Fixture (for async tests)
# ============================================================================

@pytest.fixture(scope="function")
def mock_websocket():
    """
    Mock WebSocket for async test isolation.

    Provides a mock WebSocket connection for testing async operations
    without actual WebSocket server.
    """
    class MockWebSocket:
        def __init__(self):
            self.messages = []
            self.closed = False

        async def send_json(self, data):
            self.messages.append(data)

        async def close(self):
            self.closed = True

        async def receive_json(self):
            return {"type": "test", "data": "test_data"}

    return MockWebSocket()


# ============================================================================
# Test Execution Tracker Fixture
# ============================================================================

@pytest.fixture(scope="function")
def execution_tracker():
    """
    Track test execution for flakiness detection.

    Returns a dict that can be used to track execution counts and
    results across test runs.
    """
    tracker = {
        "executions": [],
        "results": [],
        "start_time": None,
        "end_time": None
    }

    yield tracker

    # Log execution summary
    if tracker["executions"]:
        print(f"\n=== Test Execution Tracker ===")
        print(f"Total executions: {len(tracker['executions'])}")
        print(f"Passed: {sum(1 for r in tracker['results'] if r)}")
        print(f"Failed: {sum(1 for r in tracker['results'] if not r)}")
        if tracker["start_time"] and tracker["end_time"]:
            duration = tracker["end_time"] - tracker["start_time"]
            print(f"Duration: {duration:.2f}s")


# ============================================================================
# Pytest Configuration for Quality Tests
# ============================================================================

def pytest_configure(config):
    """
    Configure pytest for quality test execution.

    Registers custom markers and sets up quality test configuration.
    """
    # Register custom markers
    config.addinivalue_line(
        "markers", "quality: Test quality verification test"
    )
    config.addinivalue_line(
        "markers", "flaky: Test that may be flaky (temporary workaround)"
    )
    config.addinivalue_line(
        "markers", "isolation: Test isolation verification test"
    )
    config.addinivalue_line(
        "markers", "collection: Test collection stability test"
    )


# ============================================================================
# Quality Test Utilities
# ============================================================================

def parse_pytest_output(output: str) -> dict:
    """
    Parse pytest output for test counts and results.

    Args:
        output: Pytest stdout string

    Returns:
        dict with keys: tests_collected, tests_passed, tests_failed, duration
    """
    import re

    result = {
        "tests_collected": 0,
        "tests_passed": 0,
        "tests_failed": 0,
        "duration": 0.0
    }

    # Parse test count
    match = re.search(r'collected (\d+) items?', output)
    if match:
        result["tests_collected"] = int(match.group(1))

    # Parse passed/failed
    match = re.search(r'(\d+) passed', output)
    if match:
        result["tests_passed"] = int(match.group(1))

    match = re.search(r'(\d+) failed', output)
    if match:
        result["tests_failed"] = int(match.group(1))

    # Parse duration
    match = re.search(r'in ([\d.]+)s', output)
    if match:
        result["duration"] = float(match.group(1))

    return result
