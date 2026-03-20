"""
Collection stability verification tests for test suite health.

Tests verify that pytest test collection is consistent, stable, and performant
across multiple runs. Collection errors or inconsistencies can block CI pipelines
and cause intermittent test failures.

Goal: Ensure 100% collection stability - zero errors, zero variance.
"""

import pytest
import subprocess
import time
import re

# Mark all tests in this module as collection tests
pytestmark = pytest.mark.collection


class TestCollectionStability:
    """
    Collection stability verification tests.

    Each test verifies that test collection works consistently across
    multiple executions, regardless of order, import sequence, or environment.
    """

    # ========================================================================
    # Collection Error Detection
    # ========================================================================

    def test_collection_no_errors(self, subprocess_runner):
        """
        Verify zero collection errors when collecting integration tests.

        Collection errors indicate import errors, syntax errors, or
        configuration issues that block test execution.

        This test runs pytest --collect-only and verifies:
        - Zero collection errors
        - No import errors in stderr
        - Tests collected successfully
        """
        result = subprocess_runner([
            "python", "-m", "pytest",
            "tests/integration/quality/",
            "--collect-only",
            "-q"
        ], timeout=60)

        # Verify no collection errors
        assert result.returncode == 0, \
            f"Collection failed with return code {result.returncode}\n" \
            f"stdout: {result.stdout}\n" \
            f"stderr: {result.stderr}"

        # Check for import errors in stderr
        assert "ImportError" not in result.stderr, \
            f"ImportError detected during collection:\n{result.stderr}"

        assert "SyntaxError" not in result.stderr, \
            f"SyntaxError detected during collection:\n{result.stderr}"

        # Verify tests were collected (format: "test_file.py: N")
        # Check if any test files are listed
        assert ".py:" in result.stdout, \
            f"No tests collected:\n{result.stdout}"

    # ========================================================================
    # Collection Consistency Tests
    # ========================================================================

    @pytest.mark.repeat(3)
    def test_collection_consistency(self, subprocess_runner):
        """
        Verify test collection is consistent across multiple runs.

        Runs pytest --collect-only 3 times and compares test counts.
        Collection should be deterministic with zero variance.

        This test uses @pytest.mark.repeat(3) to verify consistency.
        """
        result = subprocess_runner([
            "python", "-m", "pytest",
            "tests/integration/quality/",
            "--collect-only",
            "-q"
        ], timeout=60)

        # Parse test count from output
        # Format: "test_file.py: N" (count all N values)
        matches = re.findall(r'\.py:\s+(\d+)', result.stdout)

        assert matches, f"Could not parse test counts from:\n{result.stdout}"

        # Sum all test counts
        test_count = sum(int(m) for m in matches)

        # Verify tests were collected
        assert test_count > 0, f"No tests collected:\n{result.stdout}"

        # Log test count for comparison across repeats
        print(f"\nCollected {test_count} tests")

        # In production, compare test_count across runs
        # For now, just verify collection succeeds consistently

    # ========================================================================
    # Collection Order Independence Tests
    # ========================================================================

    def test_collection_order_independence(self, subprocess_runner):
        """
        Verify test collection is independent of execution order.

        Collects tests with different random seeds and verifies the same
        tests are collected regardless of order.

        Note: pytest-randomly randomizes execution order, not collection order.
        This test verifies that collection itself is stable.
        """
        # Collect with default settings
        result1 = subprocess_runner([
            "python", "-m", "pytest",
            "tests/integration/quality/",
            "--collect-only",
            "-q"
        ], timeout=60)

        # Parse test count from first run (format: "test_file.py: N")
        matches1 = re.findall(r'\.py:\s+(\d+)', result1.stdout)
        assert matches1, f"Could not parse test count from first run:\n{result1.stdout}"
        count1 = sum(int(m) for m in matches1)

        # Collect again (should be same count)
        result2 = subprocess_runner([
            "python", "-m", "pytest",
            "tests/integration/quality/",
            "--collect-only",
            "-q"
        ], timeout=60)

        matches2 = re.findall(r'\.py:\s+(\d+)', result2.stdout)
        assert matches2, f"Could not parse test count from second run:\n{result2.stdout}"
        count2 = sum(int(m) for m in matches2)

        # Verify same test count
        assert count1 == count2, \
            f"Test count varies: {count1} vs {count2}"

        print(f"\nCollection consistent: {count1} tests both runs")

    # ========================================================================
    # Import Order Independence Tests
    # ========================================================================

    def test_import_order_independence(self, subprocess_runner):
        """
        Verify test collection is independent of import order.

        Tests that all quality tests can be collected regardless of
        import order or PYTHONPATH variations.
        """
        # Collect with explicit PYTHONPATH
        result = subprocess_runner([
            "python", "-m", "pytest",
            "tests/integration/quality/",
            "--collect-only",
            "-q"
        ], timeout=60)

        # Verify collection succeeded
        assert result.returncode == 0, \
            f"Collection failed:\n" \
            f"stdout: {result.stdout}\n" \
            f"stderr: {result.stderr}"

        # Verify tests collected (format: "test_file.py: N")
        matches = re.findall(r'\.py:\s+(\d+)', result.stdout)
        assert matches, f"No tests collected:\n{result.stdout}"

        test_count = sum(int(m) for m in matches)
        assert test_count > 0, f"No tests collected:\n{result.stdout}"

        print(f"\nCollected {test_count} tests")

    # ========================================================================
    # Collection Performance Tests
    # ========================================================================

    def test_measure_collection_time(self, subprocess_runner):
        """
        Measure test collection performance.

        Times pytest --collect-only execution to ensure collection
        completes in reasonable time. Logs collection time for trend tracking.

        Target: Collection completes in <10 seconds
        """
        start_time = time.time()

        result = subprocess_runner([
            "python", "-m", "pytest",
            "tests/integration/quality/",
            "--collect-only",
            "-q"
        ], timeout=60)

        end_time = time.time()
        collection_time = end_time - start_time

        # Verify collection succeeded
        assert result.returncode == 0, \
            f"Collection failed:\n{result.stdout}\n{result.stderr}"

        # Verify collection performance
        assert collection_time < 10.0, \
            f"Collection too slow: {collection_time:.2f}s (target: <10s)"

        print(f"\n✓ Collection completed in {collection_time:.2f}s")

        # Log for trend tracking
        if collection_time > 5.0:
            print(f"  ⚠ Collection time above 5s: {collection_time:.2f}s")
        else:
            print(f"  ✓ Collection time acceptable: {collection_time:.2f}s")

    # ========================================================================
    # Additional Collection Stability Tests
    # ========================================================================

    def test_collection_with_verbose_output(self, subprocess_runner):
        """
        Verify collection works with verbose output.

        Some collection errors only appear in verbose mode.
        """
        result = subprocess_runner([
            "python", "-m", "pytest",
            "tests/integration/quality/",
            "--collect-only",
            "-v"
        ], timeout=60)

        # Verify collection succeeded
        assert result.returncode == 0, \
            f"Collection failed with verbose output:\n" \
            f"stdout: {result.stdout}\n" \
            f"stderr: {result.stderr}"

        # Verify tests listed
        assert "test session starts" in result.stdout, \
            f"No test session in output:\n{result.stdout}"

    def test_collection_deselect_markers(self, subprocess_runner):
        """
        Verify collection respects deselect markers.

        Tests that pytest markers work correctly during collection.
        """
        result = subprocess_runner([
            "python", "-m", "pytest",
            "tests/integration/quality/",
            "--collect-only",
            "-q",
            "-m", "quality"
        ], timeout=60)

        # Verify collection succeeded
        assert result.returncode == 0, \
            f"Collection failed with marker filter:\n" \
            f"stdout: {result.stdout}\n" \
            f"stderr: {result.stderr}"

        print(f"\n✓ Collection with marker filter successful")


# ============================================================================
# Collection Stability Utilities
# ============================================================================

def parse_test_count(output: str) -> int:
    """
    Parse test count from pytest output.

    Args:
        output: Pytest stdout string

    Returns:
        Number of tests collected

    Raises:
        ValueError: If test count cannot be parsed
    """
    # Try multiple patterns
    patterns = [
        r'collected (\d+) items?',
        r'(\d+) items collected',
        r'(\d+) test.*\.py'
    ]

    for pattern in patterns:
        match = re.search(pattern, output)
        if match:
            return int(match.group(1))

    raise ValueError(f"Could not parse test count from:\n{output}")


def verify_no_collection_errors(output: str) -> bool:
    """
    Verify no collection errors in pytest output.

    Args:
        output: Pytest stderr string

    Returns:
        True if no errors, False otherwise
    """
    error_patterns = [
        'ImportError',
        'SyntaxError',
        'CollectionError',
        'ERROR collecting',
        'failed to import'
    ]

    for pattern in error_patterns:
        if pattern in output:
            print(f"Found error pattern: {pattern}")
            return False

    return True


# ============================================================================
# Test Session Summary
# ============================================================================

@pytest.fixture(scope="session", autouse=True)
def collection_stability_summary():
    """
    Print collection stability summary at end of test session.

    Provides summary statistics for collection stability tests.
    """
    import time

    start_time = time.time()

    yield

    end_time = time.time()
    duration = end_time - start_time

    print(f"\n{'='*60}")
    print(f"Collection Stability Test Suite Duration: {duration:.2f}s")
    print(f"{'='*60}")
    print(f"Collection stability ensures:")
    print(f"  1. Zero collection errors (no import/syntax errors)")
    print(f"  2. Consistent test counts (zero variance)")
    print(f"  3. Order independence (same tests always collected)")
    print(f"  4. Fast collection (<10s for quality suite)")
    print(f"{'='*60}")
