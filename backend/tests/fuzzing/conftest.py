"""
Fuzzing test configuration with Atheris setup.

This module provides pytest fixtures for coverage-guided fuzzing using
Atheris to discover crashes, security vulnerabilities, and edge cases.

Fixtures:
- atheris_fuzz_target: Base fixture for Atheris fuzz targets
- fuzz_input_data: Provider for random fuzz input
- fuzz_timeout: Timeout fixture (default 300s for fuzzing)
- Import existing fixtures from e2e_ui for auth and database isolation
"""

import os
import sys
import tempfile
from typing import Generator, Callable, Any

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# Add backend to path for imports
backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# ============================================================================
# IMPORT EXISTING FIXTURES FROM E2E_UI (NO DUPLICATION)
# ============================================================================
# Reuse existing auth and database fixtures to avoid duplication
from tests.e2e_ui.fixtures.auth_fixtures import authenticated_user, test_user
from tests.e2e_ui.fixtures.database_fixtures import db_session

# Re-export for direct use in fuzzing tests
__all__ = [
    'authenticated_user',
    'test_user',
    'db_session',
    'atheris_fuzz_target',
    'fuzz_input_data',
    'fuzz_timeout',
]


# ============================================================================
# ATHERIS SETUP AND TELEMETRY
# ============================================================================

# Try to import Atheris (optional - graceful degradation if not installed)
try:
    import atheris
    ATHERIS_AVAILABLE = True
except ImportError:
    ATHERIS_AVAILABLE = False
    print("Warning: Atheris not installed. Fuzzing tests will be skipped.")
    print("Install with: pip install atheris")


@pytest.fixture(scope="session")
def atheris_available() -> bool:
    """
    Check if Atheris is available for fuzzing.

    Returns:
        bool: True if Atheris is installed, False otherwise
    """
    return ATHERIS_AVAILABLE


@pytest.fixture(scope="session")
def fuzz_timeout() -> int:
    """
    Default timeout for fuzzing tests in seconds.

    Fuzzing runs can take a long time to discover interesting inputs.
    Default: 300 seconds (5 minutes)

    Returns:
        int: Timeout in seconds
    """
    return int(os.getenv("FUZZ_TIMEOUT", "300"))


@pytest.fixture(scope="function")
def fuzz_input_data() -> Callable[[], bytes]:
    """
    Provider for random fuzz input data.

    This fixture generates random byte sequences for fuzzing.
    Atheris will mutate this input to discover crashes.

    Returns:
        Callable: Function that generates random bytes
    """
    def _generate_random_bytes(max_length: int = 1024) -> bytes:
        """Generate random bytes for fuzzing.

        Args:
            max_length: Maximum length of random bytes (default: 1024)

        Returns:
            bytes: Random byte sequence
        """
        import os
        length = os.urandom(1)[0] % max_length  # Random length up to max_length
        return os.urandom(length)

    return _generate_random_bytes


@pytest.fixture(scope="function")
def atheris_fuzz_target():
    """
    Base fixture for Atheris fuzz targets.

    This fixture provides a context manager for running Atheris fuzzing.
    If Atheris is not installed, the test will be skipped.

    Usage:
        def test_parse_json_fuzz(atheris_fuzz_target):
            with atheris_fuzz_target() as (data, fdp):
                # Mutate input with fdp
                json_str = fdp.ConsumeRandomLengthString()
                # Test code that should not crash
                parse_json(json_str)

    Yields:
        tuple: (data bytes, FileDictProto object) if Atheris available

    Raises:
        pytest.skip.Exception: If Atheris is not installed
    """
    if not ATHERIS_AVAILABLE:
        pytest.skip("Atheris not installed - fuzzing test skipped")

    import atheris

    class FuzzTargetContext:
        """Context manager for Atheris fuzz target."""

        def __enter__(self):
            # Initialize Atheris with libFuzzer
            atheris.Setup(sys.argv, [])

            # Create FileDictProto for structured input generation
            from atheris import fp
            return b"", fp

        def __exit__(self, exc_type, exc_val, exc_tb):
            if exc_type is not None:
                # Fuzzing found a crash
                return False
            return True

    return FuzzTargetContext()


@pytest.fixture(scope="function")
def fuzz_crash_dir() -> str:
    """
    Create temporary directory for crash artifacts.

    When Atheris discovers a crash, it saves the crashing input
    to a directory for later analysis.

    Returns:
        str: Path to crash artifacts directory
    """
    crash_dir = tempfile.mkdtemp(prefix="fuzz_crashes_")
    return crash_dir


@pytest.fixture(scope="function", autouse=True)
def cleanup_fuzz_artifacts(request):
    """
    Clean up fuzzing artifacts after each test.

    This autouse fixture ensures that temporary files created during
    fuzzing are cleaned up after the test completes.

    Args:
        request: Pytest request object
    """
    yield

    # Clean up crash artifacts if test created them
    if hasattr(request, "funcargs"):
        crash_dir = request.funcargs.get("fuzz_crash_dir")
        if crash_dir and os.path.exists(crash_dir):
            import shutil
            try:
                shutil.rmtree(crash_dir)
            except Exception:
                pass  # Best effort cleanup


# ============================================================================
# PYTEST HOOKS FOR FUZZING TESTS
# ============================================================================

def pytest_configure(config):
    """
    Pytest configuration hook for fuzzing tests.

    Register custom markers for fuzzing test categorization.

    Args:
        config: Pytest config object
    """
    config.addinivalue_line(
        "markers",
        "fuzzing: Mark test as fuzzing test (requires Atheris)"
    )
    config.addinivalue_line(
        "markers",
        "crash: Mark test as expected to discover crash"
    )
    config.addinivalue_line(
        "markers",
        "hang: Mark test as expected to discover hang (timeout)"
    )


@pytest.fixture(autouse=True)
def skip_fuzzing_without_atheris(request):
    """
    Automatically skip fuzzing tests if Atheris is not installed.

    This autouse fixture checks for the 'fuzzing' marker and skips
    the test if Atheris is not available.

    Args:
        request: Pytest request object
    """
    if request.node.get_closest_marker('fuzzing') and not ATHERIS_AVAILABLE:
        pytest.skip("Atheris not installed - fuzzing test skipped")


# ============================================================================
# FUZZING CAMPAIGN FIXTURES
# ============================================================================

@pytest.fixture(scope="session")
def fuzz_campaign_duration() -> int:
    """
    Duration for fuzzing campaign in seconds.

    Longer campaigns discover more bugs but take more time.
    Default: 60 seconds for quick fuzzing runs

    Returns:
        int: Campaign duration in seconds
    """
    return int(os.getenv("FUZZ_CAMPAIGN_DURATION", "60"))


@pytest.fixture(scope="function")
def fuzz_stats():
    """
    Track fuzzing statistics during test run.

    This fixture provides a dictionary to store fuzzing metrics
    like executions, crashes, coverage.

    Returns:
        dict: Statistics dictionary
    """
    stats = {
        "executions": 0,
        "crashes": 0,
        "hangs": 0,
        "coverage": 0.0,
        "start_time": None,
        "end_time": None,
    }
    return stats
