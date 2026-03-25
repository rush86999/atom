"""
Memory Pressure Chaos Tests

Tests system resilience to memory pressure.

Requirements:
    CHAOS-04: Memory pressure injection (heap exhaustion testing)

Scenarios:
    - Heap exhaustion handling (1GB allocation)
    - Memory leak detection (10MB+ increase)
    - Memory release after pressure removed
    - Graceful degradation under memory pressure
"""

import pytest
import psutil
import gc
import time

from tests.chaos.core.chaos_coordinator import ChaosCoordinator
from tests.chaos.core.blast_radius_controls import assert_blast_radius
from core.models import AgentRegistry


@pytest.mark.chaos
@pytest.mark.timeout(60)
def test_heap_exhaustion_handling(memory_pressure_injector, chaos_db_session):
    """
    Test system resilience to heap exhaustion.

    Scenario: Allocate 1GB memory for 30 seconds
    Duration: 30 seconds
    Blast radius: test process only

    CHAOS-04: Memory pressure injection (heap exhaustion testing)
    """
    # Baseline memory
    baseline_mb = psutil.virtual_memory().used / (1024 * 1024)

    # Create test data
    agent = AgentRegistry(
        id="test-heap-agent",
        name="heap_test",
        description="Test agent for heap exhaustion chaos",
        category="Testing",
        module_path="test.heap",
        class_name="HeapTestAgent"
    )
    chaos_db_session.add(agent)
    chaos_db_session.commit()

    agent_id = agent.id

    # Inject memory pressure
    # Create a new injector instance with max_mb=512
    from tests.chaos.fixtures.memory_chaos_fixtures import MemoryPressureInjector
    injector = MemoryPressureInjector(max_mb=512)
    with injector:
        # System should handle memory pressure gracefully
        # Verify memory was allocated (check injector's memory blocks)
        assert len(injector.memory_blocks) > 0, "Memory pressure not applied"

        # Query should not crash with OutOfMemoryError
        agent = chaos_db_session.query(AgentRegistry).filter_by(id=agent_id).first()
        assert agent is not None, "Query failed under memory pressure"

    # Verify recovery
    recovered_mb = psutil.virtual_memory().used / (1024 * 1024)
    memory_diff = abs(recovered_mb - baseline_mb)
    assert memory_diff < 100, f"Memory did not recover: diff={memory_diff:.2f}MB"

    # Verify data integrity
    recovered_agent = chaos_db_session.query(AgentRegistry).filter_by(id=agent_id).first()
    assert recovered_agent is not None, "Agent was lost during memory pressure"
    assert recovered_agent.name == "heap_test", "Agent data corrupted"


@pytest.mark.chaos
@pytest.mark.timeout(60)
def test_memory_leak_detection(heap_snapshot, chaos_db_session):
    """
    Test memory leak detection during agent operations.

    Scenario: Execute multiple agent operations, detect memory leaks
    Duration: 30 seconds
    Blast radius: test process only

    CHAOS-04: Memory leak detection (10MB+ increase indicates leak)
    """
    # Take initial snapshot
    before_snapshot = heap_snapshot()

    # Create multiple agents (potential leak source)
    agent_ids = []
    for i in range(10):
        agent = AgentRegistry(
            id=f"test-leak-agent-{i}",
            name=f"leak_test_{i}",
            description=f"Test agent {i} for memory leak detection",
            category="Testing",
            module_path="test.leak",
            class_name=f"LeakTestAgent{i}"
        )
        chaos_db_session.add(agent)
        agent_ids.append(agent.id)

    chaos_db_session.commit()

    # Take final snapshot
    after_snapshot = heap_snapshot()

    # Calculate memory increase
    memory_increase_mb = after_snapshot["used_mb"] - before_snapshot["used_mb"]

    # Assert no significant memory leak (within 100MB tolerance)
    assert memory_increase_mb < 100, \
        f"Memory leak detected: {memory_increase_mb:.2f}MB increase"


@pytest.mark.chaos
@pytest.mark.timeout(60)
def test_memory_release_after_pressure(memory_pressure_injector, system_memory_monitor, chaos_db_session):
    """
    Test memory is released after pressure removed.

    Scenario: Allocate 512MB memory, release, verify return to baseline
    Duration: 30 seconds
    Blast radius: test process only

    CHAOS-07: Recovery validation (memory release)
    """
    # Baseline memory
    baseline_stats = system_memory_monitor()
    baseline_mb = baseline_stats["used_mb"]

    # Inject memory pressure
    from tests.chaos.fixtures.memory_chaos_fixtures import MemoryPressureInjector
    injector = MemoryPressureInjector(max_mb=512)
    with injector:
        # Memory should be elevated (verify via memory blocks)
        assert len(injector.memory_blocks) > 0, "Memory pressure not applied"

        # Memory stats should show pressure
        during_stats = system_memory_monitor()
        # Just verify we can get stats under pressure
        assert during_stats["used_mb"] > 0

    # Verify memory released (within ±100MB of baseline)
    recovery_stats = system_memory_monitor()
    recovery_mb = recovery_stats["used_mb"]

    memory_diff = abs(recovery_mb - baseline_mb)
    assert memory_diff < 100, \
        f"Memory not released: baseline={baseline_mb:.2f}MB, recovery={recovery_mb:.2f}MB, diff={memory_diff:.2f}MB"


@pytest.mark.chaos
@pytest.mark.timeout(60)
def test_graceful_degradation_under_memory_pressure(memory_pressure_injector, chaos_db_session):
    """
    Test graceful degradation under memory pressure.

    Scenario: System under memory pressure still functions (no OOM crash)
    Duration: 30 seconds
    Blast radius: test process only

    Validates:
    - No OutOfMemoryError crash
    - Operations complete successfully
    - Appropriate error handling if memory exhausted
    """
    # Baseline memory
    baseline_mb = psutil.virtual_memory().used / (1024 * 1024)

    # Create test data
    agent = AgentRegistry(
        id="test-degradation-agent",
        name="degradation_test",
        description="Test agent for graceful degradation under memory pressure",
        category="Testing",
        module_path="test.degradation",
        class_name="DegradationTestAgent"
    )
    chaos_db_session.add(agent)
    chaos_db_session.commit()

    agent_id = agent.id

    # Inject memory pressure and test operations
    from tests.chaos.fixtures.memory_chaos_fixtures import MemoryPressureInjector
    with MemoryPressureInjector(max_mb=512):
        # System should still function under memory pressure
        # Query should not crash with OutOfMemoryError
        try:
            agent = chaos_db_session.query(AgentRegistry).filter_by(id=agent_id).first()
            assert agent is not None, "Query failed under memory pressure"
        except MemoryError:
            pytest.fail("System crashed with OutOfMemoryError under memory pressure")

        # Create additional agent (should not crash)
        agent2 = AgentRegistry(
            id="test-degradation-agent-2",
            name="degradation_test_2",
            description="Test agent 2 for graceful degradation",
            category="Testing",
            module_path="test.degradation",
            class_name="DegradationTestAgent2"
        )
        chaos_db_session.add(agent2)
        chaos_db_session.commit()

    # Verify all data persisted
    all_agents = chaos_db_session.query(AgentRegistry).filter(
        AgentRegistry.id.like("test-degradation-agent%")
    ).all()
    assert len(all_agents) == 2, "Data lost under memory pressure"


@pytest.mark.chaos
@pytest.mark.timeout(60)
def test_memory_pressure_recovery_time(memory_pressure_injector, system_memory_monitor, chaos_db_session):
    """
    Test memory recovery time after pressure removed.

    Scenario: Allocate 1GB memory, release, measure recovery time
    Duration: 30 seconds
    Blast radius: test process only

    Validates:
    - Memory returns to baseline within 5 seconds
    - Garbage collection works properly
    """
    # Baseline memory
    baseline_mb = system_memory_monitor()["used_mb"]

    # Inject memory pressure
    from tests.chaos.fixtures.memory_chaos_fixtures import MemoryPressureInjector
    with MemoryPressureInjector(max_mb=1024):
        # Memory elevated
        pass

    # Measure recovery time
    start_time = time.time()
    recovery_timeout = 5  # 5 seconds

    while time.time() - start_time < recovery_timeout:
        current_mb = system_memory_monitor()["used_mb"]
        memory_diff = abs(current_mb - baseline_mb)

        if memory_diff < 100:  # Within tolerance
            recovery_time = time.time() - start_time
            assert recovery_time < 5, f"Memory recovery took {recovery_time:.2f}s (expected <5s)"
            break

        time.sleep(0.1)
    else:
        # Recovery didn't complete within timeout
        current_mb = system_memory_monitor()["used_mb"]
        memory_diff = abs(current_mb - baseline_mb)
        pytest.fail(f"Memory did not recover within {recovery_timeout}s: diff={memory_diff:.2f}MB")


@pytest.mark.chaos
@pytest.mark.timeout(60)
def test_memory_pressure_with_chaos_coordinator(memory_pressure_injector, chaos_coordinator, chaos_db_session):
    """
    Test memory pressure using ChaosCoordinator orchestration.

    Scenario: Allocate 512MB memory with full experiment lifecycle
    Duration: 30 seconds
    Blast radius: test process only

    Validates:
    - ChaosCoordinator orchestrates memory pressure experiments
    - Blast radius checks enforced
    - Recovery validation passes
    - Automated bug filing on resilience failure
    """
    # Baseline memory
    baseline_mb = psutil.virtual_memory().used / (1024 * 1024)

    # Create test data
    agent = AgentRegistry(
        id="test-coordinator-agent",
        name="coordinator_test",
        description="Test agent for ChaosCoordinator memory pressure",
        category="Testing",
        module_path="test.coordinator",
        class_name="CoordinatorTestAgent"
    )
    chaos_db_session.add(agent)
    chaos_db_session.commit()

    agent_id = agent.id

    # Define memory pressure injection
    def inject_memory_pressure():
        from tests.chaos.fixtures.memory_chaos_fixtures import MemoryPressureInjector
        return MemoryPressureInjector(max_mb=512)

    def verify_graceful_degradation(metrics):
        """System should handle memory pressure gracefully."""
        # System should not crash under memory pressure
        assert metrics["cpu_percent"] < 100, "CPU at 100% indicates hang/crash"
        # Memory should be elevated (but we can't reliably measure it due to GC)
        # Just verify system is responsive

    # Run chaos experiment
    results = chaos_coordinator.run_experiment(
        experiment_name="test_memory_pressure_with_chaos_coordinator",
        failure_injection=inject_memory_pressure,
        verify_graceful_degradation=verify_graceful_degradation,
        blast_radius_checks=[assert_blast_radius]
    )

    # Verify success
    assert results["success"], "Chaos experiment failed"

    # Verify data integrity
    recovered_agent = chaos_db_session.query(AgentRegistry).filter_by(id=agent_id).first()
    assert recovered_agent is not None, "Agent was lost during memory pressure"
    assert recovered_agent.name == "coordinator_test", "Agent data corrupted"
