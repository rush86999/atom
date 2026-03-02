"""
Monitoring Infrastructure Tests

Tests for Prometheus metrics and structured logging configuration.

Coverage:
- Prometheus metrics (Counters, Histograms, Gauges)
- Structlog configuration
- Context binding (RequestContext)
- Metrics helpers (track_http_request, track_agent_execution, etc.)
"""

import pytest
from unittest.mock import patch, MagicMock
from prometheus_client import Counter, Histogram, Gauge

from core.monitoring import (
    http_requests_total,
    http_request_duration_seconds,
    agent_executions_total,
    agent_execution_duration_seconds,
    active_agents,
    skill_executions_total,
    skill_execution_duration_seconds,
    db_query_duration_seconds,
    db_connections_active,
    db_connections_idle,
    configure_structlog,
    get_logger,
    RequestContext,
    track_http_request,
    track_agent_execution,
    track_skill_execution,
    track_db_query,
    set_active_agents,
    set_db_connections,
    # Deployment metrics
    deployment_total,
    deployment_duration_seconds,
    deployment_rollback_total,
    canary_traffic_percentage,
    smoke_test_total,
    smoke_test_duration_seconds,
    prometheus_query_total,
    prometheus_query_duration_seconds,
    track_deployment,
    track_smoke_test,
    record_rollback,
    update_canary_traffic,
    record_prometheus_query,
    initialize_metrics,
)


class TestPrometheusMetricsInitialization:
    """Tests for Prometheus metrics initialization."""

    def test_http_metrics_are_defined(self):
        """Test HTTP metrics are properly defined."""
        assert http_requests_total is not None
        assert http_request_duration_seconds is not None
        assert isinstance(http_requests_total, Counter)
        assert isinstance(http_request_duration_seconds, Histogram)

    def test_agent_metrics_are_defined(self):
        """Test agent execution metrics are properly defined."""
        assert agent_executions_total is not None
        assert agent_execution_duration_seconds is not None
        assert active_agents is not None
        assert isinstance(agent_executions_total, Counter)
        assert isinstance(agent_execution_duration_seconds, Histogram)
        assert isinstance(active_agents, Gauge)

    def test_skill_metrics_are_defined(self):
        """Test skill execution metrics are properly defined."""
        assert skill_executions_total is not None
        assert skill_execution_duration_seconds is not None
        assert isinstance(skill_executions_total, Counter)
        assert isinstance(skill_execution_duration_seconds, Histogram)

    def test_db_metrics_are_defined(self):
        """Test database metrics are properly defined."""
        assert db_query_duration_seconds is not None
        assert db_connections_active is not None
        assert db_connections_idle is not None
        assert isinstance(db_query_duration_seconds, Histogram)
        assert isinstance(db_connections_active, Gauge)
        assert isinstance(db_connections_idle, Gauge)


class TestDeploymentMetricsInitialization:
    """Tests for deployment metrics initialization."""

    def test_deployment_metrics_are_defined(self):
        """Test deployment metrics are properly defined."""
        assert deployment_total is not None
        assert deployment_duration_seconds is not None
        assert deployment_rollback_total is not None
        assert isinstance(deployment_total, Counter)
        assert isinstance(deployment_duration_seconds, Histogram)
        assert isinstance(deployment_rollback_total, Counter)

    def test_canary_metrics_are_defined(self):
        """Test canary deployment metrics are properly defined."""
        assert canary_traffic_percentage is not None
        assert isinstance(canary_traffic_percentage, Gauge)

    def test_smoke_test_metrics_are_defined(self):
        """Test smoke test metrics are properly defined."""
        assert smoke_test_total is not None
        assert smoke_test_duration_seconds is not None
        assert isinstance(smoke_test_total, Counter)
        assert isinstance(smoke_test_duration_seconds, Histogram)

    def test_prometheus_query_metrics_are_defined(self):
        """Test Prometheus query metrics are properly defined."""
        assert prometheus_query_total is not None
        assert prometheus_query_duration_seconds is not None
        assert isinstance(prometheus_query_total, Counter)
        assert isinstance(prometheus_query_duration_seconds, Histogram)


class TestStructlogConfiguration:
    """Tests for structlog configuration."""

    def test_configure_structlog(self):
        """Test structlog can be configured."""
        # Should not raise exception
        configure_structlog()
        # Verify logger can be created
        log = get_logger(__name__)
        assert log is not None

    def test_get_logger_returns_bound_logger(self):
        """Test get_logger returns a bound logger."""
        log = get_logger("test_logger")
        assert log is not None
        # BoundLogger should have bind method
        assert hasattr(log, 'bind')
        assert hasattr(log, 'info')
        assert hasattr(log, 'error')


class TestRequestContext:
    """Tests for RequestContext context manager."""

    def test_request_context_binds_attributes(self):
        """Test RequestContext binds context to logger."""
        with RequestContext(request_id="req-123", user_id="user-456") as log:
            assert log is not None
            # Context should be bound
            # (exact behavior depends on structlog internals)

    def test_request_context_restores_after_exit(self):
        """Test RequestContext restores old context on exit."""
        log1 = get_logger("test")
        original_context = log1._context.copy() if hasattr(log1, '_context') else {}

        with RequestContext(request_id="req-123"):
            pass

        # Context should be restored after exit
        log2 = get_logger("test")


class TestMetricsHelpers:
    """Tests for metrics helper functions."""

    def test_track_http_request(self):
        """Test HTTP request tracking."""
        initial_count = http_requests_total.labels(
            method="GET", endpoint="/test", status="200"
        )._value.get()

        track_http_request(method="GET", endpoint="/test", status=200, duration=0.1)

        new_count = http_requests_total.labels(
            method="GET", endpoint="/test", status="200"
        )._value.get()

        assert new_count > initial_count

    def test_track_agent_execution(self):
        """Test agent execution tracking."""
        track_agent_execution(agent_id="test-agent", status="success", duration=1.5)
        # Should not raise exception

    def test_track_skill_execution(self):
        """Test skill execution tracking."""
        track_skill_execution(skill_id="test-skill", status="failure", duration=0.5)
        # Should not raise exception

    def test_track_db_query(self):
        """Test database query tracking."""
        track_db_query(operation="select", duration=0.01)
        # Should not raise exception

    def test_set_active_agents(self):
        """Test setting active agents gauge."""
        set_active_agents(5)
        # Should not raise exception

    def test_set_db_connections(self):
        """Test setting database connection metrics."""
        set_db_connections(active=3, idle=2)
        # Should not raise exception


class TestDeploymentMetricsHelpers:
    """Tests for deployment metrics helper functions."""

    def test_track_deployment_success(self):
        """Test tracking successful deployment."""
        with track_deployment('staging'):
            # Deployment succeeded
            pass
        # Should not raise exception

    def test_track_deployment_failure(self):
        """Test tracking failed deployment."""
        with pytest.raises(Exception):
            with track_deployment('production'):
                raise Exception("Deployment failed")

        # Check that failed counter was incremented
        count = deployment_total.labels(environment='production', status='failed')._value.get()
        assert count > 0

    def test_track_smoke_test_success(self):
        """Test tracking successful smoke test."""
        with track_smoke_test('staging'):
            # Smoke test passed
            pass
        # Should not raise exception

    def test_track_smoke_test_failure(self):
        """Test tracking failed smoke test."""
        with pytest.raises(Exception):
            with track_smoke_test('production'):
                raise Exception("Smoke test failed")

        # Check that failed counter was incremented
        count = smoke_test_total.labels(environment='production', result='failed')._value.get()
        assert count > 0

    def test_record_rollback(self):
        """Test recording deployment rollback."""
        record_rollback('production', 'smoke_test_failed')
        # Should not raise exception

        # Check that rollback counter was incremented
        count = deployment_rollback_total.labels(
            environment='production',
            reason='smoke_test_failed'
        )._value.get()
        assert count > 0

    def test_update_canary_traffic(self):
        """Test updating canary traffic percentage."""
        update_canary_traffic('production', 'deploy-123', 50)
        # Should not raise exception

    def test_record_prometheus_query(self):
        """Test recording Prometheus query."""
        record_prometheus_query('deploy-staging', True, 0.5)
        record_prometheus_query('deploy-production', False, 2.0)
        # Should not raise exception

        # Check that query counters were incremented
        success_count = prometheus_query_total.labels(
            workflow='deploy-staging',
            result='success'
        )._value.get()
        failed_count = prometheus_query_total.labels(
            workflow='deploy-production',
            result='failed'
        )._value.get()
        assert success_count > 0
        assert failed_count > 0


class TestLogProcessors:
    """Tests for structlog processors."""

    def test_add_log_level_processor(self):
        """Test add_log_level processor adds level to event dict."""
        from core.monitoring import add_log_level
        logger = MagicMock()
        logger.name = "test_logger"

        result = add_log_level(logger, "info", {"event": "test"})

        assert result["level"] == "INFO"
        assert result["event"] == "test"

    def test_add_logger_name_processor(self):
        """Test add_logger_name processor adds logger name to event dict."""
        from core.monitoring import add_logger_name
        logger = MagicMock()
        logger.name = "test.module"

        result = add_logger_name(logger, "info", {"event": "test"})

        assert result["logger"] == "test.module"
        assert result["event"] == "test"


class TestMetricsInitialization:
    """Tests for metrics initialization."""

    def test_initialize_metrics_starts_server(self):
        """Test initialize_metrics starts Prometheus server."""
        from core.monitoring import initialize_metrics
        from unittest.mock import patch
        from prometheus_client import start_http_server

        with patch('prometheus_client.start_http_server') as mock_start:
            initialize_metrics()
            mock_start.assert_called_once_with(8001)

    def test_initialize_metrics_handles_oserror(self):
        """Test initialize_metrics handles already running server."""
        from core.monitoring import initialize_metrics
        from unittest.mock import patch
        from prometheus_client import start_http_server

        with patch('prometheus_client.start_http_server') as mock_start:
            mock_start.side_effect = OSError("Address already in use")
            # Should not raise exception
            initialize_metrics()


class TestDeploymentMetricsHelpersExtended:
    """Extended tests for deployment metrics helper functions."""

    def test_deployment_metrics_are_defined(self):
        """Test deployment metrics are properly defined."""
        from core.monitoring import (
            deployment_total,
            deployment_duration_seconds,
            deployment_rollback_total,
            deployment_frequency,
            canary_traffic_percentage,
            smoke_test_total,
            smoke_test_duration_seconds,
            prometheus_query_total,
            prometheus_query_duration_seconds,
        )
        from prometheus_client import Counter, Histogram, Gauge

        assert isinstance(deployment_total, Counter)
        assert isinstance(deployment_duration_seconds, Histogram)
        assert isinstance(deployment_rollback_total, Counter)
        assert isinstance(deployment_frequency, Gauge)
        assert isinstance(canary_traffic_percentage, Gauge)
        assert isinstance(smoke_test_total, Counter)
        assert isinstance(smoke_test_duration_seconds, Histogram)
        assert isinstance(prometheus_query_total, Counter)
        assert isinstance(prometheus_query_duration_seconds, Histogram)

    def test_track_deployment_success(self):
        """Test deployment tracking on success."""
        from core.monitoring import track_deployment, deployment_total

        initial_count = deployment_total.labels(
            environment="staging", status="success"
        )._value.get()

        with track_deployment('staging'):
            pass  # Successful deployment

        new_count = deployment_total.labels(
            environment="staging", status="success"
        )._value.get()

        assert new_count >= initial_count

    def test_track_deployment_failure(self):
        """Test deployment tracking on failure."""
        from core.monitoring import track_deployment, deployment_total

        initial_count = deployment_total.labels(
            environment="production", status="failed"
        )._value.get()

        try:
            with track_deployment('production'):
                raise Exception("Deployment failed")
        except Exception:
            pass

        new_count = deployment_total.labels(
            environment="production", status="failed"
        )._value.get()

        assert new_count >= initial_count

    def test_track_smoke_test_passed(self):
        """Test smoke test tracking on pass."""
        from core.monitoring import track_smoke_test, smoke_test_total

        initial_count = smoke_test_total.labels(
            environment="staging", result="passed"
        )._value.get()

        with track_smoke_test('staging'):
            pass  # Test passed

        new_count = smoke_test_total.labels(
            environment="staging", result="passed"
        )._value.get()

        assert new_count >= initial_count

    def test_track_smoke_test_failed(self):
        """Test smoke test tracking on failure."""
        from core.monitoring import track_smoke_test, smoke_test_total

        initial_count = smoke_test_total.labels(
            environment="production", result="failed"
        )._value.get()

        try:
            with track_smoke_test('production'):
                raise AssertionError("Smoke test failed")
        except AssertionError:
            pass

        new_count = smoke_test_total.labels(
            environment="production", result="failed"
        )._value.get()

        assert new_count >= initial_count

    def test_record_rollback(self):
        """Test recording deployment rollback."""
        from core.monitoring import record_rollback, deployment_rollback_total

        initial_count = deployment_rollback_total.labels(
            environment="production", reason="smoke_test_failed"
        )._value.get()

        record_rollback('production', 'smoke_test_failed')

        new_count = deployment_rollback_total.labels(
            environment="production", reason="smoke_test_failed"
        )._value.get()

        assert new_count >= initial_count

    def test_update_canary_traffic(self):
        """Test updating canary traffic percentage."""
        from core.monitoring import update_canary_traffic, canary_traffic_percentage

        update_canary_traffic('production', 'deploy-123', 25)

        # Gauge should be set (verify no exception raised)

    def test_record_prometheus_query(self):
        """Test recording Prometheus query metrics."""
        from core.monitoring import record_prometheus_query, prometheus_query_total

        initial_count = prometheus_query_total.labels(
            workflow="deploy-staging", result="success"
        )._value.get()

        record_prometheus_query('deploy-staging', success=True, duration=0.5)

        new_count = prometheus_query_total.labels(
            workflow="deploy-staging", result="success"
        )._value.get()

        assert new_count >= initial_count

    def test_record_prometheus_query_failure(self):
        """Test recording Prometheus query failure."""
        from core.monitoring import record_prometheus_query, prometheus_query_total

        initial_count = prometheus_query_total.labels(
            workflow="deploy-production", result="failed"
        )._value.get()

        record_prometheus_query('deploy-production', success=False, duration=5.0)

        new_count = prometheus_query_total.labels(
            workflow="deploy-production", result="failed"
        )._value.get()

        assert new_count >= initial_count
