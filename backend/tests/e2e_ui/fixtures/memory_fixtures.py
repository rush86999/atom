"""
Memory leak detection fixtures using Chrome DevTools Protocol (CDP).

This module provides fixtures for detecting memory leaks in E2E tests by
taking heap snapshots before and after operations and comparing them.

Fixtures:
- cdp_session: Creates CDP session for memory inspection (Chromium-only)
- heap_snapshot: Takes heap snapshot via CDP and returns parsed data
- compare_heap_snapshots: Helper function to compare before/after snapshots
- memory_stats: Helper function to get current memory usage stats

CDP Memory Domains:
- Memory.getHeapSnapshot(): Returns heap snapshot as JSON
- HeapProfiler.takeHeapSnapshot(): Takes heap snapshot with more control
- Performance.getMetrics(): Returns performance metrics including memory

Leak Detection Thresholds:
- detached_nodes: >1000 detached DOM nodes indicates leak
- size_increase_bytes: >10MB (10,485,760 bytes) indicates leak
"""

import json
import pytest
from typing import Dict, Any, Optional
from playwright.sync_api import Page


@pytest.fixture(scope="function")
def cdp_session(page: Page):
    """Create Chrome DevTools Protocol (CDP) session for memory inspection.

    This fixture creates a CDP session attached to the current page,
    enabling memory inspection and heap snapshot capture.

    IMPORTANT: Chromium-only. Firefox and Safari don't support CDP.
    Tests using this fixture will be skipped on non-Chromium browsers.

    Args:
        page: Playwright page fixture

    Yields:
        CDP session object for memory operations

    Raises:
        pytest.skip.Exception: If browser is not Chromium

    Example:
        def test_memory_leak(cdp_session, authenticated_page_api):
            # Take initial snapshot
            before = cdp_session.send("HeapProfiler.takeHeapSnapshot")
            # Execute operations
            # Take final snapshot
            after = cdp_session.send("HeapProfiler.takeHeapSnapshot")
    """
    # Check if browser is Chromium (CDP is Chromium-only)
    browser_name = page.context.browser._impl_obj._browser_name.lower()

    if "chromium" not in browser_name:
        pytest.skip(f"CDP session requires Chromium browser (got: {browser_name})")

    # Create CDP session for the page
    # Playwright provides access to CDP via page.context
    try:
        # Method 1: Use new_cdp_session (Playwright 1.40+)
        cdp = page.context.new_cdp_session(page)
    except (AttributeError, TypeError):
        # Method 2: Fallback to direct CDP access (older Playwright)
        try:
            cdp = page.context.cdp
        except AttributeError:
            pytest.skip("CDP not available in this Playwright version or browser configuration")

    yield cdp

    # Cleanup: Close CDP session
    try:
        cdp.detach()
    except Exception:
        pass  # Session may already be closed


@pytest.fixture(scope="function")
def heap_snapshot(cdp_session):
    """Take heap snapshot via CDP and return parsed data.

    This fixture captures the current JavaScript heap state including
    object types, sizes, and reference counts for leak detection.

    Args:
        cdp_session: CDP session fixture

    Returns:
        dict: Parsed heap snapshot with node counts, sizes, and types

    Example:
        def test_memory_growth(heap_snapshot):
            snapshot = heap_snapshot()
            assert snapshot['total_size_bytes'] < 50_000_000  # <50MB
    """
    def take_snapshot() -> Dict[str, Any]:
        """Take heap snapshot and parse into structured data.

        Returns:
            dict with keys:
                - snapshot_string: Raw heap snapshot (truncated for performance)
                - node_counts: Dict of object type counts (e.g., {'string': 1234})
                - total_size_bytes: Total heap size in bytes
                - js_heap_size_used: Used JavaScript heap size
                - js_heap_size_total: Total JavaScript heap size
        """
        # Take heap snapshot using HeapProfiler domain
        result = cdp_session.send("HeapProfiler.takeHeapSnapshot", {
            "reportProgress": False  # Don't report progress for faster execution
        })

        # The result contains chunked data, we need to collect it
        # For simplicity, we'll use Performance.getMetrics instead for quick stats
        metrics = cdp_session.send("Performance.getMetrics")

        # Extract memory metrics
        memory_stats = {}
        for metric in metrics.get("metrics", []):
            name = metric.get("name", "")
            value = metric.get("value", 0)

            if name == "JSHeapUsedSize":
                memory_stats["js_heap_used_size"] = value
            elif name == "JSHeapTotalSize":
                memory_stats["js_heap_total_size"] = value
            elif name == "JSHeapSizeLimit":
                memory_stats["js_heap_size_limit"] = value

        # Calculate total size
        total_size = memory_stats.get("js_heap_used_size", 0)

        # Return parsed snapshot data
        return {
            "snapshot_string": result[:1000] if isinstance(result, str) else str(result)[:1000],
            "node_counts": {},  # Would need full heap snapshot parsing
            "total_size_bytes": total_size,
            "js_heap_size_used": memory_stats.get("js_heap_used_size", 0),
            "js_heap_size_total": memory_stats.get("js_heap_total_size", 0),
            "js_heap_size_limit": memory_stats.get("js_heap_size_limit", 0),
        }

    return take_snapshot


def compare_heap_snapshots(before_snapshot: Dict[str, Any], after_snapshot: Dict[str, Any]) -> Dict[str, Any]:
    """Compare two heap snapshots to detect memory leaks.

    This function analyzes the difference between before and after heap snapshots
    to identify potential memory leaks based on detached DOM nodes and heap size growth.

    Leak Detection Criteria:
    - detached_nodes > 1000: Too many detached DOM nodes
    - size_increase_bytes > 10MB (10,485,760): Significant heap growth

    Args:
        before_snapshot: Heap snapshot before operations
        after_snapshot: Heap snapshot after operations

    Returns:
        dict: Comparison results with keys:
            - detached_nodes: Count of detached DOM nodes (simulated)
            - size_increase_bytes: Heap size difference in bytes
            - leak_detected: Boolean indicating potential leak
            - percentage_used_before: Heap usage % before
            - percentage_used_after: Heap usage % after

    Example:
        before = heap_snapshot()
        # Execute operations that might leak
        after = heap_snapshot()
        result = compare_heap_snapshots(before, after)
        assert not result['leak_detected'], "Memory leak detected"
    """
    # Calculate size difference
    before_size = before_snapshot.get("total_size_bytes", 0)
    after_size = after_snapshot.get("total_size_bytes", 0)
    size_increase = after_size - before_size

    # Calculate heap usage percentage
    before_limit = before_snapshot.get("js_heap_size_limit", 1)
    after_limit = after_snapshot.get("js_heap_size_limit", 1)
    percentage_before = (before_size / before_limit * 100) if before_limit > 0 else 0
    percentage_after = (after_size / after_limit * 100) if after_limit > 0 else 0

    # Estimate detached nodes (simplified heuristic)
    # Real detached node count requires full heap snapshot parsing
    # We'll use size increase as proxy: ~1KB per detached node
    estimated_detached = max(0, size_increase // 1024)

    # Leak detection thresholds
    LEAK_NODE_THRESHOLD = 1000  # Detached nodes
    LEAK_SIZE_THRESHOLD = 10 * 1024 * 1024  # 10MB

    leak_detected = (
        estimated_detached > LEAK_NODE_THRESHOLD or
        size_increase > LEAK_SIZE_THRESHOLD
    )

    return {
        "detached_nodes": estimated_detached,
        "size_increase_bytes": size_increase,
        "leak_detected": leak_detected,
        "percentage_used_before": percentage_before,
        "percentage_used_after": percentage_after,
        "size_increase_mb": round(size_increase / (1024 * 1024), 2),
    }


def memory_stats(cdp_session) -> Dict[str, Any]:
    """Get current memory usage statistics via CDP.

    This function provides real-time memory metrics including heap usage,
    total heap size, and heap limit.

    Args:
        cdp_session: CDP session object

    Returns:
        dict: Memory statistics with keys:
            - js_heap_used_size: Used JavaScript heap size in bytes
            - js_heap_total_size: Total JavaScript heap size in bytes
            - js_heap_size_limit: Maximum heap size in bytes
            - percentage_used: Heap usage percentage (0-100)
            - available_bytes: Available heap space in bytes

    Example:
        stats = memory_stats(cdp_session)
        assert stats['percentage_used'] < 90  # Don't exceed 90% heap usage
    """
    # Get performance metrics from CDP
    metrics = cdp_session.send("Performance.getMetrics")

    memory_stats = {}
    for metric in metrics.get("metrics", []):
        name = metric.get("name", "")
        value = metric.get("value", 0)

        if name == "JSHeapUsedSize":
            memory_stats["js_heap_used_size"] = value
        elif name == "JSHeapTotalSize":
            memory_stats["js_heap_total_size"] = value
        elif name == "JSHeapSizeLimit":
            memory_stats["js_heap_size_limit"] = value

    # Calculate derived metrics
    used = memory_stats.get("js_heap_used_size", 0)
    limit = memory_stats.get("js_heap_size_limit", 1)
    total = memory_stats.get("js_heap_total_size", 0)

    memory_stats["percentage_used"] = (used / limit * 100) if limit > 0 else 0
    memory_stats["available_bytes"] = max(0, limit - used)

    return memory_stats


# ============================================================================
# Helper Functions for Test Convenience
# ============================================================================

def get_heap_snapshot(cdp_session) -> Dict[str, Any]:
    """Convenience function to take heap snapshot (alternative to fixture).

    This is a standalone function version of the heap_snapshot fixture,
    useful for tests that need multiple snapshots during execution.

    Args:
        cdp_session: CDP session object

    Returns:
        dict: Heap snapshot data (same format as heap_snapshot fixture)

    Example:
        def test_multiple_snapshots(cdp_session):
            before = get_heap_snapshot(cdp_session)
            # Execute operations
            during = get_heap_snapshot(cdp_session)
            # Execute more operations
            after = get_heap_snapshot(cdp_session)
    """
    # Get performance metrics
    metrics = cdp_session.send("Performance.getMetrics")

    memory_stats = {}
    for metric in metrics.get("metrics", []):
        name = metric.get("name", "")
        value = metric.get("value", 0)

        if name == "JSHeapUsedSize":
            memory_stats["js_heap_used_size"] = value
        elif name == "JSHeapTotalSize":
            memory_stats["js_heap_total_size"] = value
        elif name == "JSHeapSizeLimit":
            memory_stats["js_heap_size_limit"] = value

    total_size = memory_stats.get("js_heap_used_size", 0)

    return {
        "total_size_bytes": total_size,
        "js_heap_size_used": memory_stats.get("js_heap_used_size", 0),
        "js_heap_total_size": memory_stats.get("js_heap_total_size", 0),
        "js_heap_size_limit": memory_stats.get("js_heap_size_limit", 0),
    }


# Export functions for use in tests
__all__ = [
    "compare_heap_snapshots",
    "memory_stats",
    "get_heap_snapshot",
]
