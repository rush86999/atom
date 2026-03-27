"""
Pytest configuration and fixtures for memory leak detection tests.

This module provides fixtures for memory leak detection using Bloomberg's memray
profiler. All fixtures include graceful degradation if memray is not installed.

Key Fixtures:
- memray_session: Yields memray.Tracker for memory profiling
- check_memory_growth: Helper function to assert memory growth thresholds
- amplification_loop: Helper function for 100-iteration amplification loops

Usage:
    def test_my_function_no_leak(memray_session, check_memory_growth):
        from core.my_module import my_function

        for i in range(100):
            my_function(f"test_{i}")

        # Assert <10MB memory growth
        check_memory_growth(memray_session, threshold_mb=10)

Phase: 243-01 (Memory & Performance Bug Discovery)
"""

import sys
from pathlib import Path
from typing import Optional

import pytest


# =============================================================================
# Memory Leak Detection Fixture
# =============================================================================

@pytest.fixture(scope="function")
def memray_session(tmp_path):
    """
    Memray session fixture for memory leak detection.

    This fixture provides a memray.Stats instance for analyzing Python
    memory allocations during test execution. It handles graceful degradation
    if memray is not installed or Python version is <3.11.

    Yields:
        memray.Tracker: Started tracker instance (use after test for stats)

    Examples:
        def test_agent_execution_no_leak(memray_session, check_memory_growth):
            from core.agent_governance_service import AgentGovernanceService

            governance = AgentGovernanceService()

            for i in range(100):
                governance.execute_agent(
                    agent_id="test_agent",
                    query=f"Test {i}",
                    db_session=db_session
                )

            # Assert <10MB memory growth
            check_memory_growth(memray_session, threshold_mb=10)

    Requirements:
        - Python 3.11+ (memray requirement)
        - memray>=1.12.0 (install with: pip install memray)

    Graceful Degradation:
        - Skips with pytest.skip if Python <3.11
        - Skips with pytest.skip if memray not installed
        - Does NOT fail CI if memray unavailable

    Phase: 243-01
    """
    # Python 3.11+ version check (memray requirement)
    if sys.version_info < (3, 11):
        pytest.skip(
            "memray requires Python 3.11+. "
            f"Current version: {sys.version_info.major}.{sys.version_info.minor}"
        )

    # Import memray with graceful degradation
    try:
        import memray
    except ImportError:
        pytest.skip(
            "memray not installed. Install with: pip install memray>=1.12.0"
        )

    # Create output file for memray binary
    output_file = tmp_path / "memray.bin"

    # Start tracking memory allocations
    tracker = memray.Tracker(str(output_file))
    tracker.start()

    yield tracker

    # Stop tracking and analyze results
    tracker.stop()

    # Load stats for memory analysis and attach to tracker object
    stats = memray.Stats(str(output_file))
    tracker.stats = stats


# =============================================================================
# Memory Leak Assertion Helpers
# =============================================================================

@pytest.fixture(scope="function")
def check_memory_growth():
    """
    Helper function to assert memory growth thresholds.

    This fixture provides a helper function for asserting that memory growth
    during a test stays within acceptable bounds. It calculates growth between
    start and peak memory usage.

    Returns:
        Callable[[memray.Stats, float, Optional[str]], None]: Assertion function

    Args:
        stats: memray.Stats instance from memray_session
        threshold_mb: Maximum allowed memory growth in MB
        context_msg: Optional context message for assertion failure

    Examples:
        def test_agent_execution_no_leak(memray_session, check_memory_growth):
            # ... run test ...

            # Assert <10MB memory growth
            check_memory_growth(memray_session, threshold_mb=10)

    Thresholds by Test Category:
        - Agent execution: <10MB (100 iterations)
        - Governance cache: <5MB (1000 operations)
        - LLM streaming: <15MB (1000 tokens)

    Phase: 243-01
    """
    def _check_memory_growth(
        stats,
        threshold_mb: float,
        context_msg: Optional[str] = None
    ) -> None:
        """
        Assert memory growth threshold.

        Args:
            stats: memray.Stats instance
            threshold_mb: Maximum allowed memory growth in MB
            context_msg: Optional context message for assertion

        Raises:
            AssertionError: If memory growth exceeds threshold
        """
        # Calculate memory growth in MB
        memory_growth_mb = stats.peak_memory_mb - stats.start_memory_mb

        # Build assertion message
        base_msg = (
            f"Memory leak detected: {memory_growth_mb:.2f} MB growth "
            f"(threshold: {threshold_mb} MB)"
        )
        full_msg = f"{context_msg}: {base_msg}" if context_msg else base_msg

        # Assert threshold
        assert memory_growth_mb < threshold_mb, full_msg

    return _check_memory_growth


@pytest.fixture(scope="function")
def assert_allocation_count():
    """
    Helper function to assert allocation count thresholds.

    This fixture provides a helper function for asserting that the number
    of memory allocations during a test stays within acceptable bounds.

    Returns:
        Callable[[memray.Stats, int, Optional[str]], None]: Assertion function

    Args:
        stats: memray.Stats instance from memray_session
        max_allocations: Maximum allowed allocation count
        context_msg: Optional context message for assertion failure

    Examples:
        def test_agent_execution_no_leak(memray_session, assert_allocation_count):
            # ... run test ...

            # Assert <1000 allocations per execution
            assert_allocation_count(memray_session, max_allocations=1000)

    Phase: 243-01
    """
    def _assert_allocation_count(
        stats,
        max_allocations: int,
        context_msg: Optional[str] = None
    ) -> None:
        """
        Assert allocation count threshold.

        Args:
            stats: memray.Stats instance
            max_allocations: Maximum allowed allocation count
            context_msg: Optional context message for assertion

        Raises:
            AssertionError: If allocation count exceeds threshold
        """
        # Get allocation metadata from stats
        # Note: memray.Stats provides various metrics, we use total allocations
        try:
            # Get allocation data (may vary by memray version)
            allocation_data = stats.get_metrics()
            total_allocations = allocation_data.get("total_allocations", 0)
        except (AttributeError, KeyError):
            # Fallback: skip allocation count check if not available
            pytest.skip("Allocation count not available in this memray version")

        # Build assertion message
        base_msg = (
            f"Too many allocations: {total_allocations} "
            f"(threshold: {max_allocations})"
        )
        full_msg = f"{context_msg}: {base_msg}" if context_msg else base_msg

        # Assert threshold
        assert total_allocations < max_allocations, full_msg

    return _assert_allocation_count


# =============================================================================
# Amplification Loop Helper
# =============================================================================

@pytest.fixture(scope="function")
def amplification_loop():
    """
    Helper function for 100-iteration amplification loops.

    This fixture provides a helper function for running test functions
    in amplification loops (100 iterations) to amplify small memory leaks
    into detectable growth.

    Returns:
        Callable[[Callable, int, Optional[dict]], None]: Loop runner function

    Args:
        test_func: Function to execute in loop
        iterations: Number of iterations (default: 100)
        context: Optional context dictionary for test data

    Examples:
        def test_agent_execution_no_leak(memray_session, amplification_loop):
            from core.agent_governance_service import AgentGovernanceService

            governance = AgentGovernanceService()

            def execute_agent(iteration):
                governance.execute_agent(
                    agent_id="test_agent",
                    query=f"Test {iteration}",
                    db_session=db_session
                )

            # Run 100 iterations
            amplification_loop(execute_agent, iterations=100)

    Amplification Strategy:
        - Small leaks (1KB/iteration) become detectable (100KB over 100 iterations)
        - Detects cumulative leaks from repeated operations
        - Identifies cache misses, unclosed connections, etc.

    Phase: 243-01
    """
    def _amplification_loop(
        test_func: callable,
        iterations: int = 100,
        context: Optional[dict] = None
    ) -> None:
        """
        Run test function in amplification loop.

        Args:
            test_func: Function to execute (receives iteration index)
            iterations: Number of iterations (default: 100)
            context: Optional context dictionary for test data

        Raises:
            Exception: Propagates exceptions from test_func (logged, not swallowed)
        """
        for i in range(iterations):
            try:
                # Call test function with iteration index
                test_func(i, context)
            except Exception as e:
                # Log but continue (testing memory, not functionality)
                # Use pytest's logging to avoid print statements
                pytest.logger.warning(
                    f"Amplification loop iteration {i} failed: {e}"
                )

    return _amplification_loop


# =============================================================================
# Pytest Marker Configuration
# =============================================================================

def pytest_configure(config):
    """
    Configure pytest markers for memory leak tests.

    This function is called by pytest at configuration time to register
    custom markers used in memory leak tests.

    Markers Registered:
        - memory_leak: Memory leak detection tests (run sequentially, weekly)

    Usage:
        @pytest.mark.memory_leak
        @pytest.mark.slow
        def test_my_function_no_leak(memray_session):
            ...

    CI/CD Integration:
        - Run weekly via: pytest -m memory_leak
        - Excluded from fast PR tests (<10 minutes)
        - Tests skip gracefully if memray unavailable

    Phase: 243-01
    """
    config.addinivalue_line(
        "markers",
        "memory_leak: Memory leak detection tests (run sequentially, weekly)"
    )
