"""
Soak Test Configuration and Fixtures

This module provides shared fixtures for soak testing (extended duration tests for
memory leak detection and resource stability validation).

Soak tests run for 1-4 hours to detect:
- Memory leaks (slow growth over time)
- Connection pool exhaustion
- Cache unbounded growth
- Resource leaks

Fixtures:
- memory_monitor: Track memory usage using psutil
- enable_gc_control: Control garbage collection during tests
- soak_test_config: Configuration for memory thresholds and logging intervals
"""

import gc
import pytest
import psutil
from typing import Dict, Any


@pytest.fixture
def memory_monitor() -> Dict[str, Any]:
    """
    Fixture providing memory monitoring capabilities.

    Returns a dictionary with:
    - process: psutil.Process instance for memory tracking
    - initial_memory_mb: Initial memory usage in MB
    - check_interval: Seconds between memory checks (default: 60)

    Usage:
        def test_memory_leak(memory_monitor):
            process = memory_monitor["process"]
            initial = memory_monitor["initial_memory_mb"]
            current = process.memory_info().rss / 1024 / 1024
            growth = current - initial
            assert growth < 100, f"Memory grew {growth:.2f}MB"
    """
    process = psutil.Process()
    initial_memory_mb = process.memory_info().rss / 1024 / 1024

    return {
        "process": process,
        "initial_memory_mb": initial_memory_mb,
        "check_interval": 60  # Check memory every 60 seconds
    }


@pytest.fixture
def enable_gc_control() -> Dict[str, Any]:
    """
    Fixture enabling garbage collection control for leak detection.

    Enables GC debug stats and provides a control object with:
    - collect(): Method to force garbage collection
    - stats_enabled: Boolean indicating if stats are enabled

    Purpose: Force GC during tests to distinguish memory leaks from
    cached data that hasn't been collected yet.

    Usage:
        def test_with_gc(enable_gc_control):
            # Run operations that may leak memory
            enable_gc_control["collect"]()  # Force GC
            # Check memory usage after GC
    """
    # Enable GC debug stats to track collection cycles
    gc.set_debug(gc.DEBUG_STATS)

    return {
        "collect": lambda: gc.collect(),
        "stats_enabled": True
    }


@pytest.fixture
def soak_test_config() -> Dict[str, int]:
    """
    Fixture providing soak test configuration thresholds.

    Returns configuration dict with:
    - memory_threshold_1hr_mb: Max allowed memory growth over 1 hour (100MB)
    - memory_threshold_2hr_mb: Max allowed memory growth over 2 hours (200MB)
    - fail_fast_threshold_mb: Immediate failure if memory growth exceeds this (500MB)
    - log_interval_seconds: How often to log memory usage (60 seconds)

    Purpose: Centralize soak test thresholds for consistent memory leak
    detection across all soak tests.

    Usage:
        def test_soak(soak_test_config, memory_monitor):
            threshold = soak_test_config["memory_threshold_1hr_mb"]
            # Run test, fail if memory_growth > threshold
    """
    return {
        "memory_threshold_1hr_mb": 100,
        "memory_threshold_2hr_mb": 200,
        "fail_fast_threshold_mb": 500,
        "log_interval_seconds": 60
    }


# Pytest mark for filtering soak tests
soak = pytest.mark.soak
"""
Marker for soak tests (extended duration tests).

Usage:
    @pytest.mark.soak
    @pytest.mark.timeout(3600)  # 1 hour
    def test_memory_leak_detection():
        ...

Running soak tests:
    pytest -m soak -v              # All soak tests
    pytest -m soak --timeout=7200  # With timeout override
    pytest tests/soak/ -v          # All tests in soak directory
"""
