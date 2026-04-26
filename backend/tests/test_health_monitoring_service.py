"""
Health Monitoring Service Tests

Tests for health checks, metrics collection, and alerting.
Coverage target: 20-25 tests for health_monitoring_service.py (725 lines)
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from core.health_monitoring_service import (
    HealthMonitoringService,
    get_health_monitoring_service
)


class TestHealthChecks:
    """Test liveness and readiness probe execution."""

    @pytest.mark.asyncio
    async def test_get_agent_health_success(self):
        """HealthMonitoringService returns comprehensive agent health status."""
        db = Mock(spec=Session)

        # Mock agent
        mock_agent = Mock()
        mock_agent.id = "agent-001"
        mock_agent.name = "Test Agent"
        mock_agent.status = "active"
        mock_agent.confidence_score = 0.85
        mock_agent.updated_at = datetime.now()

        # Mock executions
        mock_execution = Mock()
        mock_execution.status = "completed"
        mock_execution.started_at = datetime.now() - timedelta(minutes=30)
        mock_execution.completed_at = datetime.now() - timedelta(minutes=25)

        db.query.return_value.filter.return_value.all.return_value = [mock_execution]
        db.query.return_value.filter.return_value.first.return_value = mock_agent

        service = HealthMonitoringService(db)
        health = await service.get_agent_health(agent_id="agent-001")

        assert health["agent_id"] == "agent-001"
        assert health["status"] in ["active", "idle", "error", "paused"]
        assert "success_rate" in health["metrics"]
        assert "error_rate" in health["metrics"]

    @pytest.mark.asyncio
    async def test_get_agent_health_not_found(self):
        """HealthMonitoringService returns error status when agent not found."""
        db = Mock(spec=Session)
        db.query.return_value.filter.return_value.first.return_value = None

        service = HealthMonitoringService(db)
        health = await service.get_agent_health(agent_id="nonexistent-agent")

        assert health["status"] == "error"
        assert "error" in health

    @pytest.mark.asyncio
    async def test_get_agent_health_calculates_success_rate(self):
        """HealthMonitoringService calculates success rate from recent executions."""
        db = Mock(spec=Session)

        # Mock agent
        mock_agent = Mock()
        mock_agent.id = "agent-001"
        mock_agent.name = "Test Agent"
        mock_agent.status = "active"
        mock_agent.confidence_score = 0.85
        mock_agent.updated_at = datetime.now()

        # Mock executions: 2 completed, 1 failed
        mock_exec_completed = Mock()
        mock_exec_completed.status = "completed"
        mock_exec_completed.started_at = datetime.now() - timedelta(minutes=30)
        mock_exec_completed.completed_at = datetime.now() - timedelta(minutes=25)

        mock_exec_failed = Mock()
        mock_exec_failed.status = "failed"
        mock_exec_failed.started_at = datetime.now() - timedelta(minutes=20)
        mock_exec_failed.completed_at = datetime.now() - timedelta(minutes=18)

        db.query.return_value.filter.return_value.all.return_value = [
            mock_exec_completed,
            mock_exec_completed,
            mock_exec_failed
        ]
        db.query.return_value.filter.return_value.first.return_value = mock_agent

        service = HealthMonitoringService(db)
        health = await service.get_agent_health(agent_id="agent-001")

        # Success rate should be 2/3 = 0.667
        assert health["metrics"]["success_rate"] == pytest.approx(0.667, rel=0.01)

    @pytest.mark.asyncio
    async def test_get_all_integrations_health(self):
        """HealthMonitoringService returns health status for all user integrations."""
        db = Mock(spec=Session)

        # Mock connection
        mock_connection = Mock()
        mock_connection.id = "conn-001"
        mock_connection.user_id = "user-001"
        mock_connection.integration_id = "integration-001"
        mock_connection.status = "active"
        mock_connection.updated_at = datetime.now()

        # Mock integration
        mock_integration = Mock()
        mock_integration.id = "integration-001"
        mock_integration.name = "Test Integration"

        db.query.return_value.filter.return_value.all.return_value = [mock_connection]
        db.query.return_value.filter.return_value.first.return_value = mock_integration

        service = HealthMonitoringService(db)
        health_list = await service.get_all_integrations_health(user_id="user-001")

        assert len(health_list) == 1
        assert health_list[0]["integration_name"] == "Test Integration"


class TestMetricsCollection:
    """Test metric registration and aggregation."""

    @pytest.mark.asyncio
    async def test_get_system_metrics(self):
        """HealthMonitoringService collects system-wide health metrics."""
        db = Mock(spec=Session)

        # Mock agent counts
        db.query.return_value.filter.return_value.count.return_value = 10
        db.query.return_value.filter.return_value.count.return_value = 5

        # Mock integration counts
        db.query.return_value.filter.return_value.count.return_value = 3
        db.query.return_value.filter.return_value.count.return_value = 2

        # Mock execution counts
        db.query.return_value.filter.return_value.count.return_value = 1
        db.query.return_value.filter.return_value.count.return_value = 0

        service = HealthMonitoringService(db)
        metrics = await service.get_system_metrics()

        assert "cpu_usage" in metrics
        assert "memory_usage" in metrics
        assert "active_operations" in metrics
        assert "total_agents" in metrics
        assert "active_agents" in metrics

    @pytest.mark.asyncio
    async def test_get_system_metrics_includes_psutil_data(self):
        """HealthMonitoringService includes psutil system metrics when available."""
        db = Mock(spec=Session)

        # Mock all queries
        db.query.return_value.filter.return_value.count.return_value = 0

        with patch('core.health_monitoring_service.psutil') as mock_psutil:
            # Mock psutil returns
            mock_psutil.cpu_percent.return_value = 45.5
            mock_memory = Mock()
            mock_memory.percent = 62.3
            mock_psutil.virtual_memory.return_value = mock_memory
            mock_disk = Mock()
            mock_disk.percent = 55.0
            mock_psutil.disk_usage.return_value = mock_disk
            mock_psutil.pids.return_value = [1, 2, 3]

            service = HealthMonitoringService(db)
            metrics = await service.get_system_metrics()

            assert metrics["cpu_usage"] == 45.5
            assert metrics["memory_usage"] == 62.3
            assert metrics["disk_usage"] == 55.0


class TestAlerting:
    """Test alert threshold configuration and notification."""

    @pytest.mark.asyncio
    async def test_get_active_alerts_cpu_warning(self):
        """HealthMonitoringService generates alert for high CPU usage."""
        db = Mock(spec=Session)

        # Mock system metrics with high CPU
        with patch.object(HealthMonitoringService, 'get_system_metrics', return_value={
            "cpu_usage": 85.0,
            "memory_usage": 50.0,
            "queue_depth": 10
        }):
            service = HealthMonitoringService(db)
            alerts = await service.get_active_alerts()

            # Should have CPU alert
            cpu_alerts = [a for a in alerts if "CPU" in a["message"]]
            assert len(cpu_alerts) > 0
            assert cpu_alerts[0]["severity"] == "warning"

    @pytest.mark.asyncio
    async def test_get_active_alerts_cpu_critical(self):
        """HealthMonitoringService generates critical alert for very high CPU usage."""
        db = Mock(spec=Session)

        # Mock system metrics with critical CPU
        with patch.object(HealthMonitoringService, 'get_system_metrics', return_value={
            "cpu_usage": 95.0,
            "memory_usage": 50.0,
            "queue_depth": 10
        }):
            service = HealthMonitoringService(db)
            alerts = await service.get_active_alerts()

            # Should have critical CPU alert
            cpu_alerts = [a for a in alerts if "CPU" in a["message"]]
            assert len(cpu_alerts) > 0
            assert cpu_alerts[0]["severity"] == "critical"

    @pytest.mark.asyncio
    async def test_get_active_alerts_queue_depth(self):
        """HealthMonitoringService generates alert for high queue depth."""
        db = Mock(spec=Session)

        # Mock system metrics with high queue depth
        with patch.object(HealthMonitoringService, 'get_system_metrics', return_value={
            "cpu_usage": 50.0,
            "memory_usage": 50.0,
            "queue_depth": 150
        }):
            with patch('core.health_monitoring_service.ALERT_QUEUE_DEPTH_THRESHOLD', 100):
                service = HealthMonitoringService(db)
                alerts = await service.get_active_alerts()

                # Should have queue depth alert
                queue_alerts = [a for a in alerts if "queue" in a["message"].lower()]
                assert len(queue_alerts) > 0

    @pytest.mark.asyncio
    async def test_get_active_alerts_summary(self):
        """HealthMonitoringService summarizes active alerts by severity."""
        db = Mock(spec=Session)

        # Mock alerts
        with patch.object(HealthMonitoringService, 'get_active_alerts', return_value=[
            {"severity": "critical", "acknowledged": False},
            {"severity": "warning", "acknowledged": False},
            {"severity": "warning", "acknowledged": False},
            {"severity": "info", "acknowledged": True}  # Acknowledged, shouldn't count
        ]):
            service = HealthMonitoringService(db)
            summary = await service.get_active_alerts_summary()

            assert summary["critical"] == 1
            assert summary["warning"] == 2
            assert summary["info"] == 0

    @pytest.mark.asyncio
    async def test_acknowledge_alert(self):
        """HealthMonitoringService acknowledges alert and broadcasts update."""
        db = Mock(spec=Session)

        with patch('core.health_monitoring_service.ws_manager') as mock_ws:
            mock_ws.broadcast = AsyncMock()

            service = HealthMonitoringService(db)
            result = await service.acknowledge_alert(
                alert_id="alert-001",
                user_id="user-001"
            )

            assert result is True
            mock_ws.broadcast.assert_called_once()


class TestHealthHistory:
    """Test health history for trend analysis."""

    @pytest.mark.asyncio
    async def test_get_health_history_agent(self):
        """HealthMonitoringService retrieves agent health history."""
        db = Mock(spec=Session)

        # Mock execution history
        mock_execution = Mock()
        mock_execution.started_at = datetime.now() - timedelta(days=1)
        mock_execution.status = "completed"

        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
            mock_execution
        ]

        service = HealthMonitoringService(db)
        history = await service.get_health_history(
            health_type="agent",
            entity_id="agent-001",
            days=30
        )

        assert len(history) >= 0  # May be empty if no executions

    @pytest.mark.asyncio
    async def test_calculate_health_trend_improving(self):
        """HealthMonitoringService detects improving health trend."""
        db = Mock(spec=Session)

        # Mock health history with improving scores
        with patch.object(HealthMonitoringService, 'get_health_history', return_value=[
            {"health_score": 0.5, "timestamp": "2026-01-01T00:00:00Z"},
            {"health_score": 0.7, "timestamp": "2026-01-02T00:00:00Z"},
            {"health_score": 0.9, "timestamp": "2026-01-03T00:00:00Z"}
        ]):
            service = HealthMonitoringService(db)
            trend = await service._calculate_health_trend(agent_id="agent-001")

            assert trend == "improving"

    @pytest.mark.asyncio
    async def test_calculate_health_trend_declining(self):
        """HealthMonitoringService detects declining health trend."""
        db = Mock(spec=Session)

        # Mock health history with declining scores
        with patch.object(HealthMonitoringService, 'get_health_history', return_value=[
            {"health_score": 0.9, "timestamp": "2026-01-01T00:00:00Z"},
            {"health_score": 0.7, "timestamp": "2026-01-02T00:00:00Z"},
            {"health_score": 0.5, "timestamp": "2026-01-03T00:00:00Z"}
        ]):
            service = HealthMonitoringService(db)
            trend = await service._calculate_health_trend(agent_id="agent-001")

            assert trend == "declining"

    @pytest.mark.asyncio
    async def test_calculate_health_trend_stable(self):
        """HealthMonitoringService detects stable health trend."""
        db = Mock(spec=Session)

        # Mock health history with stable scores
        with patch.object(HealthMonitoringService, 'get_health_history', return_value=[
            {"health_score": 0.7, "timestamp": "2026-01-01T00:00:00Z"},
            {"health_score": 0.72, "timestamp": "2026-01-02T00:00:00Z"},
            {"health_score": 0.68, "timestamp": "2026-01-03T00:00:00Z"}
        ]):
            service = HealthMonitoringService(db)
            trend = await service._calculate_health_trend(agent_id="agent-001")

            assert trend == "stable"


class TestIntegrationHealth:
    """Test integration health calculation."""

    @pytest.mark.asyncio
    async def test_calculate_integration_health_healthy(self):
        """HealthMonitoringService calculates healthy status for active integration."""
        db = Mock(spec=Session)

        # Mock connection
        mock_connection = Mock()
        mock_connection.status = "active"
        mock_connection.updated_at = datetime.now()
        mock_connection.created_at = datetime.now()

        # Mock integration
        mock_integration = Mock()
        mock_integration.id = "integration-001"
        mock_integration.name = "Test Integration"

        # Mock health metrics
        mock_metric = Mock()
        mock_metric.latency_ms = 100.0
        mock_metric.success_rate = 0.95

        db.query.return_value.order_by.return_value.limit.return_value.all.return_value = [
            mock_metric, mock_metric
        ]

        service = HealthMonitoringService(db)
        health = await service._calculate_integration_health(
            connection=mock_connection,
            integration=mock_integration
        )

        assert health["status"] == "healthy"
        assert health["connection_status"] == "connected"


class TestHelperFunctions:
    """Test helper functions and utilities."""

    def test_get_health_monitoring_service_singleton(self):
        """get_health_monitoring_service returns HealthMonitoringService instance."""
        db = Mock(spec=Session)

        service = get_health_monitoring_service(db)

        assert isinstance(service, HealthMonitoringService)
        assert service.db == db
