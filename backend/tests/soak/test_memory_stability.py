"""
Soak Tests for Memory Leak Detection

Extended duration tests (1-2 hours) to detect memory leaks in critical components:
- GovernanceCache: Cache operations under extended load
- EpisodeService: Episode creation and retrieval patterns
- WorkflowEngine: Workflow execution memory patterns

Memory leak detection strategy:
1. Measure initial memory usage
2. Run operations for extended period (1-2 hours)
3. Force garbage collection periodically
4. Log memory growth at regular intervals
5. Fail fast if memory growth exceeds fail-fast threshold
6. Final assertion: memory growth < threshold for duration

Tests use psutil for accurate memory measurement and gc.collect() to
distinguish leaks from cached data.
"""

import gc
import pytest
import time
import psutil
from typing import Dict, Any

from core.governance_cache import GovernanceCache


@pytest.mark.soak
@pytest.mark.timeout(3600)  # 1 hour
def test_governance_cache_memory_stability_1hr(
    memory_monitor: Dict[str, Any],
    enable_gc_control: Dict[str, Any],
    soak_test_config: Dict[str, int]
):
    """
    Soak test for GovernanceCache memory leak detection (1 hour).

    Validates:
    - Cache operations don't leak memory under extended load
    - Memory growth remains within 100MB threshold over 1 hour
    - Cache LRU eviction works correctly (doesn't grow unbounded)

    Test pattern:
    - Run for 1 hour (3600 seconds)
    - Perform 1000 cache operations per iteration (set + get)
    - Log memory growth every 60 iterations (~1 minute)
    - Force GC every 10 iterations
    - Fail fast if memory growth > 500MB

    Duration: 1 hour
    Memory threshold: < 100MB growth
    Failure: Memory growth > 100MB or > 500MB (fail-fast)
    """
    process = memory_monitor["process"]
    initial_memory = memory_monitor["initial_memory_mb"]
    config = soak_test_config

    # Create cache with realistic configuration
    cache = GovernanceCache(max_size=1000, ttl_seconds=60)

    start_time = time.time()
    iterations = 0

    # Run cache operations for 1 hour
    while time.time() - start_time < 3600:
        # Perform 1000 cache operations per iteration
        for i in range(1000):
            cache.set(
                agent_id=f"agent_{iterations}_{i}",
                action_type="test_action",
                data={"allowed": True, "maturity_level": "AUTONOMOUS"}
            )
            cache.get(agent_id=f"agent_{iterations}_{i}", action_type="test_action")

        iterations += 1

        # Force garbage collection every 10 iterations
        if iterations % 10 == 0:
            enable_gc_control["collect"]()

        # Log memory growth every 60 iterations (~1 minute)
        if iterations % 60 == 0:
            current_memory = process.memory_info().rss / 1024 / 1024
            memory_growth = current_memory - initial_memory

            _log_memory_growth(process, initial_memory, iterations)

            # Fail fast if memory growth > 500MB
            if memory_growth > config["fail_fast_threshold_mb"]:
                pytest.fail(
                    f"FAIL-FAST: Memory leak detected - {memory_growth:.2f}MB growth "
                    f"(threshold: {config['fail_fast_threshold_mb']}MB)"
                )

    # Final memory check
    final_memory = process.memory_info().rss / 1024 / 1024
    memory_growth = final_memory - initial_memory

    # Assert memory growth < 100MB over 1 hour
    assert memory_growth < config["memory_threshold_1hr_mb"], (
        f"Memory leak detected: {memory_growth:.2f}MB growth over 1 hour "
        f"(threshold: {config['memory_threshold_1hr_mb']}MB)"
    )

    print(f"\n✅ Soak test complete: {iterations} iterations, {memory_growth:.2f}MB memory growth")


@pytest.mark.soak
@pytest.mark.timeout(1800)  # 30 minutes
def test_episode_service_memory_stability_30min(
    memory_monitor: Dict[str, Any],
    enable_gc_control: Dict[str, Any],
    soak_test_config: Dict[str, int]
):
    """
    Soak test for episode service memory patterns (30 minutes).

    Validates:
    - Episode creation doesn't leak memory
    - Episode metadata tracking remains stable
    - Memory growth < 50MB over 30 minutes (shorter test, lower threshold)

    Test pattern:
    - Run for 30 minutes (1800 seconds)
    - Create mock episodes (100 episodes per iteration)
    - Track memory growth
    - Force GC every 10 iterations
    - Log memory every 60 iterations

    Duration: 30 minutes
    Memory threshold: < 50MB growth
    Purpose: Detect memory leaks in episode lifecycle operations

    Note: This test uses mock episode creation to avoid database dependency.
    Real episode service memory patterns should be tested with integration tests.
    """
    process = memory_monitor["process"]
    initial_memory = memory_monitor["initial_memory_mb"]
    config = soak_test_config

    # Simulated episode storage (in-memory for this test)
    episodes = []

    start_time = time.time()
    iterations = 0

    # Run episode creation for 30 minutes
    while time.time() - start_time < 1800:
        # Create 100 mock episodes per iteration
        for i in range(100):
            episode = {
                "id": f"episode_{iterations}_{i}",
                "agent_id": f"agent_{iterations}",
                "start_time": time.time(),
                "segments": [
                    {"action": "test_action", "timestamp": time.time()}
                ],
                "metadata": {"test": "data"}
            }
            episodes.append(episode)

            # Simulate episode cleanup (LRU eviction)
            if len(episodes) > 10000:
                episodes = episodes[-5000:]  # Keep last 5000

        iterations += 1

        # Force garbage collection every 10 iterations
        if iterations % 10 == 0:
            enable_gc_control["collect"]()

        # Log memory growth every 60 iterations
        if iterations % 60 == 0:
            current_memory = process.memory_info().rss / 1024 / 1024
            memory_growth = current_memory - initial_memory

            _log_memory_growth(process, initial_memory, iterations)

            # Fail fast if memory growth > 500MB
            if memory_growth > config["fail_fast_threshold_mb"]:
                pytest.fail(
                    f"FAIL-FAST: Memory leak detected - {memory_growth:.2f}MB growth "
                    f"(threshold: {config['fail_fast_threshold_mb']}MB)"
                )

    # Final memory check
    final_memory = process.memory_info().rss / 1024 / 1024
    memory_growth = final_memory - initial_memory

    # Assert memory growth < 50MB over 30 minutes (lower threshold for shorter test)
    threshold_mb = config["memory_threshold_1hr_mb"] // 2  # 50MB for 30min
    assert memory_growth < threshold_mb, (
        f"Memory leak detected: {memory_growth:.2f}MB growth over 30 minutes "
        f"(threshold: {threshold_mb}MB)"
    )

    print(f"\n✅ Soak test complete: {iterations} iterations, {memory_growth:.2f}MB memory growth")


def _log_memory_growth(process: psutil.Process, initial_memory_mb: float, iteration: int):
    """
    Helper function to log memory growth during soak tests.

    Args:
        process: psutil.Process instance
        initial_memory_mb: Initial memory usage in MB
        iteration: Current iteration number

    Prints formatted memory information including:
    - Current memory usage (MB)
    - Memory growth (MB)
    - Iteration number
    """
    current_memory = process.memory_info().rss / 1024 / 1024
    memory_growth = current_memory - initial_memory_mb

    print(
        f"Iteration {iteration}: "
        f"Memory = {current_memory:.2f}MB, "
        f"Growth = {memory_growth:+.2f}MB"
    )
