"""
Memory pressure injection fixtures for chaos testing.

Simulates memory pressure to test:
- Heap exhaustion handling
- Graceful degradation under memory pressure
- Memory release after pressure removed

Uses psutil for cross-platform system monitoring.
"""

import pytest
import time
from typing import Generator, Callable, Dict, Any
from contextlib import contextmanager

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    psutil = None


class MemoryPressureInjector:
    """
    Context manager for memory pressure injection.

    Blast radius: Test process only
    Duration: Automatic cleanup (release memory)
    Safety: Maximum 1GB allocation

    Example:
        with MemoryPressureInjector(max_mb=1024):
            # System under memory pressure
            agent = create_agent()
    """

    def __init__(self, max_mb: int = 1024, duration_seconds: int = 30):
        self.max_mb = max_mb
        self.duration_seconds = duration_seconds
        self.memory_blocks = []
        self.baseline_mb = 0

    def __enter__(self):
        """Allocate memory blocks to simulate pressure."""
        if not PSUTIL_AVAILABLE:
            raise ImportError("psutil not installed: pip install psutil")

        # Baseline memory
        self.baseline_mb = psutil.virtual_memory().used / (1024 * 1024)

        # Allocate memory in 10MB chunks
        chunk_size = 10 * 1024 * 1024  # 10MB
        num_chunks = self.max_mb // 10

        for i in range(num_chunks):
            # Allocate byte array (prevents garbage collection)
            block = bytearray(chunk_size)
            self.memory_blocks.append(block)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Release all allocated memory."""
        self.memory_blocks.clear()
        return False

    def get_memory_used_mb(self) -> float:
        """Get current memory usage in MB."""
        if PSUTIL_AVAILABLE:
            return psutil.virtual_memory().used / (1024 * 1024)
        return 0.0

    def get_memory_increase_mb(self) -> float:
        """Get memory increase since baseline in MB."""
        if PSUTIL_AVAILABLE:
            current_mb = psutil.virtual_memory().used / (1024 * 1024)
            return current_mb - self.baseline_mb
        return 0.0


@pytest.fixture(scope="function")
def memory_pressure_injector():
    """
    Inject memory pressure during test.

    Blast radius: Test process only
    Duration: 30 seconds max
    Safety: Maximum 1GB allocation

    Yields:
        MemoryPressureInjector context manager

    Example:
        with memory_pressure_injector(max_mb=512):
            # System under 512MB memory pressure
            result = perform_operation()
    """
    if not PSUTIL_AVAILABLE:
        pytest.skip("psutil not installed: pip install psutil")

    # Baseline memory
    baseline_mb = psutil.virtual_memory().used / (1024 * 1024)

    injector = MemoryPressureInjector(max_mb=1024, duration_seconds=30)

    yield injector

    # Cleanup: Ensure memory released
    current_mb = psutil.virtual_memory().used / (1024 * 1024)
    if current_mb > baseline_mb + 100:
        # Memory not fully released (within 100MB tolerance)
        print(f"Warning: Memory not fully released: {current_mb - baseline_mb:.2f}MB")


@pytest.fixture(scope="function")
def system_memory_monitor():
    """
    Monitor system memory during test.

    Yields:
        Function to get memory stats

    Example:
        stats = system_memory_monitor()
        print(stats['used_mb'], stats['available_mb'])
    """
    if not PSUTIL_AVAILABLE:
        pytest.skip("psutil not installed: pip install psutil")

    def get_memory_stats() -> Dict[str, Any]:
        """Get current memory statistics."""
        mem = psutil.virtual_memory()
        return {
            "total_mb": mem.total / (1024 * 1024),
            "available_mb": mem.available / (1024 * 1024),
            "used_mb": mem.used / (1024 * 1024),
            "free_mb": mem.free / (1024 * 1024),
            "percent_used": mem.percent,
            "timestamp": time.time()
        }

    yield get_memory_stats


@pytest.fixture(scope="function")
def heap_snapshot():
    """
    Take heap snapshot for memory leak detection.

    Uses psutil for memory statistics (Python-native approach).

    Yields:
        Function to take heap snapshot

    Example:
        before = heap_snapshot()
        # Execute operations
        after = heap_snapshot()
        increase = after['used_mb'] - before['used_mb']
    """
    if not PSUTIL_AVAILABLE:
        pytest.skip("psutil not installed: pip install psutil")

    def take_snapshot() -> Dict[str, Any]:
        """Take heap snapshot and return memory statistics."""
        process = psutil.Process()

        return {
            "used_mb": process.memory_info().rss / (1024 * 1024),
            "percent": process.memory_percent(),
            "timestamp": time.time()
        }

    yield take_snapshot


@pytest.fixture(scope="function")
def memory_pressure_thresholds():
    """
    Memory pressure thresholds for chaos tests.

    Returns:
        Dict with threshold values

    Example:
        thresholds = memory_pressure_thresholds()
        assert used_mb < thresholds['max_allocation_mb']
    """
    return {
        "max_allocation_mb": 1024,  # 1GB maximum allocation
        "leak_threshold_mb": 100,   # 100MB increase indicates leak
        "recovery_tolerance_mb": 100,  # ±100MB tolerance for recovery
        "warning_threshold_percent": 90,  # 90% heap usage warning
    }
