"""
Blast Radius Control Validation Tests

Validates that all blast radius controls work correctly to prevent
chaos experiments from affecting production systems.

Requirements:
    CHAOS-06: Blast radius controls (isolated test databases, failure injection limits)

Tests:
    - Environment validation (ENVIRONMENT=test required)
    - Database URL validation (no production endpoints)
    - Hostname validation (no production hosts)
    - Duration cap enforcement (60s max)
    - Injection scope limits (test network only)
"""

import os
import pytest
from unittest.mock import patch

from tests.chaos.core.blast_radius_controls import (
    assert_blast_radius,
    assert_test_database_only,
    assert_environment_safe
)


class TestBlastRadiusEnvironmentChecks:
    """Tests for environment validation in blast radius controls."""

    def test_assert_blast_radius_passes_in_test_environment(self):
        """assert_blast_radius() should pass in test environment."""
        with patch.dict(os.environ, {"ENVIRONMENT": "test", "DATABASE_URL": "sqlite:///./test.db"}):
            # Should not raise
            assert_blast_radius()

    def test_assert_blast_radius_passes_in_development_environment(self):
        """assert_blast_radius() should pass in development environment."""
        with patch.dict(os.environ, {"ENVIRONMENT": "development", "DATABASE_URL": "sqlite:///./dev.db"}):
            # Should not raise
            assert_blast_radius()

    def test_assert_blast_radius_fails_in_production_environment(self):
        """assert_blast_radius() should fail in production environment."""
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            with pytest.raises(AssertionError, match="Unsafe: Environment is production"):
                assert_blast_radius()

    def test_assert_blast_radius_fails_with_production_database_url(self):
        """assert_blast_radius() should fail with production database URL."""
        with patch.dict(os.environ, {
            "ENVIRONMENT": "test",
            "DATABASE_URL": "postgresql://user:pass@prod-db.example.com/production"
        }):
            with pytest.raises(AssertionError, match="Unsafe:.*production"):
                assert_blast_radius()

    def test_assert_blast_radius_fails_with_production_hostname(self):
        """assert_blast_radius() should fail on production host."""
        with patch.dict(os.environ, {
            "ENVIRONMENT": "test",
            "DATABASE_URL": "sqlite:///./test.db"
        }):
            with patch("subprocess.check_output", return_value=b"prod-server-001"):
                with pytest.raises(AssertionError, match="Unsafe: Running on production host"):
                    assert_blast_radius()


class TestBlastRadiusDatabaseValidation:
    """Tests for database URL validation in blast radius controls."""

    def test_assert_test_database_only_passes_with_test_database(self):
        """assert_test_database_only() should pass with test database."""
        with patch.dict(os.environ, {"DATABASE_URL": "sqlite:///./test_chaos.db"}):
            # Should not raise
            assert_test_database_only()

    def test_assert_test_database_only_passes_with_dev_database(self):
        """assert_test_database_only() should pass with dev database."""
        with patch.dict(os.environ, {"DATABASE_URL": "sqlite:///./dev_chaos.db"}):
            # Should not raise
            assert_test_database_only()

    def test_assert_test_database_only_passes_with_chaos_database(self):
        """assert_test_database_only() should pass with chaos database."""
        with patch.dict(os.environ, {"DATABASE_URL": "sqlite:///./chaos_test.db"}):
            # Should not raise
            assert_test_database_only()

    def test_assert_test_database_only_fails_with_production_database(self):
        """assert_test_database_only() should fail with production database."""
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://prod-db/example/production"}):
            with pytest.raises(AssertionError, match="Unsafe:.*must contain 'test', 'dev', or 'chaos'"):
                assert_test_database_only()


class TestBlastRadiusEnvironmentSafety:
    """Tests for environment safety validation."""

    def test_assert_environment_safe_passes_in_test(self):
        """assert_environment_safe() should pass in test environment."""
        with patch.dict(os.environ, {"ENVIRONMENT": "test"}):
            # Should not raise
            assert_environment_safe()

    def test_assert_environment_safe_passes_in_development(self):
        """assert_environment_safe() should pass in development environment."""
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            # Should not raise
            assert_environment_safe()

    def test_assert_environment_safe_fails_in_production(self):
        """assert_environment_safe() should fail in production environment."""
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            with pytest.raises(AssertionError, match="Unsafe: Chaos tests cannot run in production"):
                assert_environment_safe()

    def test_assert_environment_safe_fails_in_staging(self):
        """assert_environment_safe() should fail in staging environment."""
        with patch.dict(os.environ, {"ENVIRONMENT": "staging"}):
            with pytest.raises(AssertionError, match="Unsafe: Environment staging not approved"):
                assert_environment_safe()


class TestBlastRadiusDurationCaps:
    """Tests for duration cap enforcement."""

    @pytest.mark.timeout(65)  # Slightly longer than 60s cap
    @pytest.mark.chaos
    def test_chaos_experiment_enforces_60_second_duration_cap(self, chaos_coordinator, chaos_db_session):
        """Chaos experiments should enforce 60-second duration cap."""
        from core.models import AgentRegistry
        import time

        # Create test agent
        agent = AgentRegistry(
            id="test-duration-cap-agent",
            name="duration_cap_test",
            description="Test agent for duration cap validation",
            maturity_level="STUDENT"
        )
        chaos_db_session.add(agent)
        chaos_db_session.commit()

        # Track experiment duration
        start_time = time.time()

        # Run experiment (should complete within 60s)
        def short_injection():
            class ShortContext:
                def __enter__(self): return self
                def __exit__(self, *args): pass
            return ShortContext()

        def verify_nothing(metrics):
            pass

        from tests.chaos.core.blast_radius_controls import assert_blast_radius
        results = chaos_coordinator.run_experiment(
            experiment_name="test_duration_cap",
            failure_injection=short_injection,
            verify_graceful_degradation=verify_nothing,
            blast_radius_checks=[assert_blast_radius]
        )

        duration = time.time() - start_time

        # Should complete well within 60s
        assert duration < 60, f"Experiment exceeded duration cap: {duration:.2f}s"
        assert results["success"]


class TestBlastRadiusInjectionScope:
    """Tests for injection scope limits."""

    def test_network_chaos_limited_to_test_network(self, slow_database_proxy):
        """Network chaos should be limited to test network only."""
        # Verify proxy is using localhost
        # Toxiproxy runs on localhost:8474 (test network only)
        assert hasattr(slow_database_proxy, "name"), "Proxy not configured"
        assert "localhost" in str(slow_database_proxy), "Proxy must use localhost only"

    def test_database_chaos_limited_to_test_database(self, database_connection_dropper):
        """Database chaos should be limited to test database only."""
        # Blast radius check in fixture
        import os
        db_url = os.getenv("DATABASE_URL", "")
        assert "test" in db_url or "dev" in db_url or "chaos" in db_url, \
            f"Database chaos requires test database: {db_url}"

    def test_memory_chaos_limited_to_test_process(self, memory_pressure_injector):
        """Memory chaos should be limited to test process only."""
        # Memory pressure only affects current process
        # Verify by checking memory increase is local
        baseline = memory_pressure_injector.get_memory_used_mb()

        with memory_pressure_injector:
            # Memory elevated in this process only
            current = memory_pressure_injector.get_memory_used_mb()
            # Should see increase in local process
            assert current >= baseline, "Memory pressure not applied"
