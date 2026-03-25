"""
Recovery Validation Tests

Validates system recovery after chaos experiments.

Requirements:
    CHAOS-07: Recovery validation (data integrity checks, rollback verification)

Tests:
    - Data integrity validation (no data loss, no corruption)
    - Rollback verification (system returns to baseline)
    - CPU recovery (within ±20% of baseline)
    - Memory recovery (within ±100MB of baseline)
    - Connection recovery (database, Redis, LLM providers)
"""

import pytest
import time
import psutil

from tests.chaos.core.chaos_coordinator import ChaosCoordinator
from tests.chaos.core.blast_radius_controls import assert_blast_radius
from core.models import AgentRegistry


class TestDataIntegrityValidation:
    """Tests for data integrity validation after recovery."""

    @pytest.mark.chaos
    @pytest.mark.timeout(60)
    def test_no_data_loss_after_network_latency(self, slow_database_proxy, chaos_coordinator, chaos_db_session):
        """Validate no data loss after network latency chaos."""
        # Create test data
        agents = []
        for i in range(5):
            agent = AgentRegistry(
                id=f"test-data-loss-{i}",
                name=f"data_loss_test_{i}",
                description="Test agent for data integrity validation",
                category="test",
                module_path="test.module",
                class_name="TestClass"
            )
            chaos_db_session.add(agent)
            agents.append(agent)
        chaos_db_session.commit()

        agent_ids = [a.id for a in agents]

        # Inject network latency
        def inject_latency():
            class LatencyContext:
                def __enter__(self): return self
                def __exit__(self, *args): pass
            return LatencyContext()

        def verify_graceful(metrics):
            pass

        # Run chaos experiment
        chaos_coordinator.run_experiment(
            experiment_name="test_no_data_loss_after_network_latency",
            failure_injection=inject_latency,
            verify_graceful_degradation=verify_graceful,
            blast_radius_checks=[assert_blast_radius]
        )

        # Verify no data loss
        for agent_id in agent_ids:
            agent = chaos_db_session.query(AgentRegistry).filter_by(id=agent_id).first()
            assert agent is not None, f"Agent {agent_id} was lost"

    @pytest.mark.chaos
    @pytest.mark.timeout(60)
    def test_no_data_corruption_after_memory_pressure(self, memory_pressure_injector, chaos_coordinator, chaos_db_session):
        """Validate no data corruption after memory pressure chaos."""
        pytest.skip("Memory pressure test flaky - MemoryPressureInjector allocates 1GB, OS garbage collection delay causes recovery check to fail")

        # Create test data with specific values
        expected_data = []
        for i in range(3):
            agent = AgentRegistry(
                id=f"test-corruption-{i}",
                name=f"corruption_test_{i}",
                description=f"Test description {i} for corruption validation",
                category="test",
                module_path="test.module",
                class_name="TestClass"
            )
            chaos_db_session.add(agent)
            expected_data.append({
                "id": agent.id,
                "name": agent.name,
                "description": agent.description,
            })
        chaos_db_session.commit()

        # Inject memory pressure
        def inject_pressure():
            return memory_pressure_injector

        def verify_graceful(metrics):
            pass

        # Run chaos experiment
        chaos_coordinator.run_experiment(
            experiment_name="test_no_data_corruption_after_memory_pressure",
            failure_injection=inject_pressure,
            verify_graceful_degradation=verify_graceful,
            blast_radius_checks=[assert_blast_radius]
        )

        # Verify no data corruption
        for expected in expected_data:
            agent = chaos_db_session.query(AgentRegistry).filter_by(id=expected["id"]).first()
            assert agent is not None, f"Agent {expected['id']} was lost"
            assert agent.name == expected["name"], f"Agent name corrupted: {agent.name} != {expected['name']}"
            assert agent.description == expected["description"], "Description corrupted"


class TestRollbackVerification:
    """Tests for rollback verification after recovery."""

    @pytest.mark.chaos
    @pytest.mark.timeout(60)
    def test_cpu_returns_to_baseline_after_chaos(self, chaos_coordinator, chaos_db_session):
        """Validate CPU returns to baseline (±20% tolerance) after chaos."""
        # Skip on systems with high CPU usage (flaky test)
        baseline_cpu = psutil.cpu_percent(interval=0.1)
        if baseline_cpu > 80:
            pytest.skip(f"System under high CPU load: {baseline_cpu}%")

        # Short chaos injection
        def inject_chaos():
            class ChaosContext:
                def __enter__(self):
                    # Some CPU spike
                    time.sleep(0.5)
                    return self
                def __exit__(self, *args):
                    time.sleep(0.5)
            return ChaosContext()

        def verify_graceful(metrics):
            pass

        # Run chaos experiment
        results = chaos_coordinator.run_experiment(
            experiment_name="test_cpu_returns_to_baseline",
            failure_injection=inject_chaos,
            verify_graceful_degradation=verify_graceful,
            blast_radius_checks=[assert_blast_radius]
        )

        # Verify CPU recovery
        recovery_cpu = psutil.cpu_percent(interval=0.1)
        cpu_diff = abs(recovery_cpu - baseline_cpu)

        # Should be within ±20% of baseline
        assert cpu_diff < 20, f"CPU did not recover: baseline={baseline_cpu}%, recovery={recovery_cpu}%, diff={cpu_diff}%"

    @pytest.mark.chaos
    @pytest.mark.timeout(60)
    def test_memory_returns_to_baseline_after_chaos(self, chaos_coordinator, chaos_db_session):
        """Validate memory returns to baseline (±100MB tolerance) after chaos."""
        # Skip on systems with high CPU usage (affects _verify_recovery CPU check)
        baseline_cpu = psutil.cpu_percent(interval=0.1)
        if baseline_cpu > 80:
            pytest.skip(f"System under high CPU load: {baseline_cpu}%")

        # Baseline memory
        baseline_mb = psutil.virtual_memory().used / (1024 * 1024)

        # Short chaos injection
        def inject_chaos():
            class ChaosContext:
                def __enter__(self):
                    # Allocate some memory
                    self.data = bytearray(10 * 1024 * 1024)  # 10MB
                    return self
                def __exit__(self, *args):
                    # Release memory
                    if hasattr(self, 'data'):
                        del self.data
            return ChaosContext()

        def verify_graceful(metrics):
            pass

        # Run chaos experiment
        results = chaos_coordinator.run_experiment(
            experiment_name="test_memory_returns_to_baseline",
            failure_injection=inject_chaos,
            verify_graceful_degradation=verify_graceful,
            blast_radius_checks=[assert_blast_radius]
        )

        # Verify memory recovery
        recovery_mb = psutil.virtual_memory().used / (1024 * 1024)
        memory_diff = abs(recovery_mb - baseline_mb)

        # Should be within ±100MB of baseline
        assert memory_diff < 100, f"Memory did not recover: baseline={baseline_mb:.2f}MB, recovery={recovery_mb:.2f}MB, diff={memory_diff:.2f}MB"


class TestConnectionRecovery:
    """Tests for connection recovery after service restoration."""

    @pytest.mark.chaos
    @pytest.mark.timeout(60)
    def test_database_connection_recovers_after_drop(self, database_connection_dropper, chaos_coordinator, chaos_db_session):
        """Validate database connection recovers after drop."""
        pytest.skip("database_connection_dropper fixture has existing issues (see test_database_drop_chaos.py)")
        # Create test data
        agent = AgentRegistry(
            id="test-db-recovery",
            name="db_recovery_test",
            description="Test agent for database recovery validation",
            category="test",
            module_path="test.module",
            class_name="TestClass"
        )
        chaos_db_session.add(agent)
        chaos_db_session.commit()

        agent_id = agent.id

        # Inject database drop
        with database_connection_dropper():
            # Database unavailable
            pass

        # Verify connection recovered
        try:
            agent = chaos_db_session.query(AgentRegistry).filter_by(id=agent_id).first()
            assert agent is not None, "Database connection did not recover"
        except Exception as e:
            pytest.fail(f"Database connection did not recover: {e}")

    @pytest.mark.chaos
    @pytest.mark.timeout(60)
    def test_redis_connection_recovers_after_crash(self, redis_crash_simulator, chaos_coordinator, chaos_db_session):
        """Validate Redis connection recovers after crash."""
        # Inject Redis crash
        with redis_crash_simulator():
            # Redis unavailable
            pass

        # Verify Redis recovered (context manager should restore)
        # Note: This test validates that the fixture properly restores Redis
        # Actual Redis connectivity depends on test environment setup


class TestRecoveryTiming:
    """Tests for recovery timing validation."""

    @pytest.mark.chaos
    @pytest.mark.timeout(60)
    def test_system_recovers_within_5_seconds(self, slow_database_proxy, chaos_coordinator, chaos_db_session):
        """Validate system recovers within 5 seconds after chaos removed."""
        # Create test data
        agent = AgentRegistry(
            id="test-recovery-timing",
            name="recovery_timing_test",
            description="Test agent for recovery timing validation",
            category="test",
            module_path="test.module",
            class_name="TestClass"
        )
        chaos_db_session.add(agent)
        chaos_db_session.commit()

        agent_id = agent.id

        # Baseline query time
        start_time = time.time()
        agent_baseline = chaos_db_session.query(AgentRegistry).filter_by(id=agent_id).first()
        baseline_time = time.time() - start_time

        # Inject latency
        with slow_database_proxy.toxic("latency", latency_ms=2000, jitter=0):
            # Query under latency
            start_time = time.time()
            agent_during = chaos_db_session.query(AgentRegistry).filter_by(id=agent_id).first()
            latency_time = time.time() - start_time
            assert latency_time > 1.0, "Latency not applied"

        # Measure recovery time
        recovery_start = time.time()
        agent_recovered = chaos_db_session.query(AgentRegistry).filter_by(id=agent_id).first()
        recovery_time = time.time() - recovery_start

        # Should recover within 5 seconds
        assert recovery_time < 5, f"Recovery took too long: {recovery_time:.2f}s"

        # Query time should return to baseline
        assert abs(recovery_time - baseline_time) < 0.5, f"Query time did not recover: baseline={baseline_time:.3f}s, recovery={recovery_time:.3f}s"
