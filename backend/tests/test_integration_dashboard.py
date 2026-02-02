"""
Tests for Integration Dashboard
Tests real-time metrics, health monitoring, and dashboard endpoints.
"""

import pytest
from datetime import datetime, timedelta
from typing import Dict, Any

from core.integration_dashboard import (
    IntegrationDashboard,
    IntegrationMetrics,
    IntegrationHealth,
    IntegrationStatus,
    get_integration_dashboard
)


@pytest.fixture
def dashboard():
    """Create IntegrationDashboard instance"""
    return IntegrationDashboard()


@pytest.fixture
def populated_dashboard(dashboard):
    """Create a dashboard with sample data"""
    # Add some metrics for Slack
    dashboard.record_fetch(
        "slack",
        message_count=10,
        fetch_time_ms=100,
        success=True
    )
    dashboard.record_processing(
        "slack",
        processed_count=10,
        duplicate_count=2,
        process_time_ms=50,
        attachment_count=3,
        data_size_bytes=5000
    )

    # Add some metrics for Teams
    dashboard.record_fetch(
        "teams",
        message_count=5,
        fetch_time_ms=200,
        success=True
    )

    # Add some failures for Gmail
    dashboard.record_fetch(
        "gmail",
        message_count=0,
        fetch_time_ms=5000,
        success=False,
        error_message="Authentication failed"
    )

    # Update health status
    dashboard.update_health(
        "slack",
        enabled=True,
        configured=True,
        has_valid_token=True,
        has_required_permissions=True
    )
    dashboard.update_health(
        "teams",
        enabled=True,
        configured=True,
        has_valid_token=True,
        has_required_permissions=True
    )
    dashboard.update_health(
        "gmail",
        enabled=True,
        configured=False,
        has_valid_token=False
    )

    return dashboard


class TestIntegrationMetrics:
    """Test IntegrationMetrics dataclass"""

    def test_metrics_initialization(self):
        """Test metrics initialization with defaults"""
        metrics = IntegrationMetrics()

        assert metrics.messages_fetched == 0
        assert metrics.messages_processed == 0
        assert metrics.messages_failed == 0
        assert metrics.avg_fetch_time_ms == 0.0
        assert metrics.last_fetch_time is None

    def test_metrics_to_dict(self):
        """Test converting metrics to dictionary"""
        metrics = IntegrationMetrics(
            messages_fetched=100,
            messages_processed=95,
            messages_failed=5,
            avg_fetch_time_ms=150.5
        )

        metrics_dict = metrics.to_dict()

        assert metrics_dict["messages_fetched"] == 100
        assert metrics_dict["messages_processed"] == 95
        assert metrics_dict["messages_failed"] == 5
        assert metrics_dict["avg_fetch_time_ms"] == 150.5
        assert "success_rate" in metrics_dict
        assert metrics_dict["success_rate"] == 95.0

    def test_success_rate_calculation(self):
        """Test success rate calculation"""
        metrics = IntegrationMetrics(
            messages_processed=80,
            messages_failed=20
        )

        assert metrics._calculate_success_rate() == 80.0

    def test_success_rate_no_messages(self):
        """Test success rate with no messages"""
        metrics = IntegrationMetrics()

        assert metrics._calculate_success_rate() == 100.0

    def test_duplicate_rate_calculation(self):
        """Test duplicate rate calculation"""
        metrics = IntegrationMetrics(
            messages_fetched=100,
            messages_duplicate=15
        )

        assert metrics._calculate_duplicate_rate() == 15.0

    def test_duplicate_rate_no_messages(self):
        """Test duplicate rate with no messages"""
        metrics = IntegrationMetrics()

        assert metrics._calculate_duplicate_rate() == 0.0


class TestIntegrationHealth:
    """Test IntegrationHealth dataclass"""

    def test_health_initialization(self):
        """Test health initialization with defaults"""
        health = IntegrationHealth()

        assert health.status == IntegrationStatus.NOT_CONFIGURED
        assert health.enabled == False
        assert health.configured == False
        assert health.consecutive_failures == 0

    def test_health_to_dict(self):
        """Test converting health to dictionary"""
        health = IntegrationHealth(
            status=IntegrationStatus.HEALTHY,
            enabled=True,
            configured=True,
            consecutive_successes=5
        )

        health_dict = health.to_dict()

        assert health_dict["status"] == "healthy"
        assert health_dict["enabled"] == True
        assert health_dict["configured"] == True
        assert health_dict["consecutive_successes"] == 5


class TestDashboardMetricsRecording:
    """Test metrics recording functionality"""

    def test_record_fetch_success(self, dashboard):
        """Test recording a successful fetch"""
        dashboard.record_fetch(
            "slack",
            message_count=10,
            fetch_time_ms=100,
            success=True
        )

        metrics = dashboard.metrics["slack"]
        assert metrics.messages_fetched == 10
        assert metrics.messages_processed == 10
        assert metrics.messages_failed == 0
        assert metrics.last_fetch_time is not None
        assert metrics.last_success_time is not None

    def test_record_fetch_failure(self, dashboard):
        """Test recording a failed fetch"""
        dashboard.record_fetch(
            "gmail",
            message_count=0,
            fetch_time_ms=5000,
            success=False,
            error_message="Auth error"
        )

        metrics = dashboard.metrics["gmail"]
        assert metrics.messages_fetched == 0
        assert metrics.messages_processed == 0
        assert metrics.messages_failed == 0
        assert metrics.last_error_time is not None
        assert metrics.last_error_message == "Auth error"

        health = dashboard.health["gmail"]
        assert health.consecutive_failures == 1

    def test_record_fetch_rate_limited(self, dashboard):
        """Test recording rate limit"""
        dashboard.record_fetch(
            "teams",
            message_count=0,
            fetch_time_ms=100,
            success=False,
            rate_limited=True
        )

        metrics = dashboard.metrics["teams"]
        assert metrics.rate_limit_hits == 1
        assert len(metrics.rate_limit_resets) == 1

    def test_record_processing(self, dashboard):
        """Test recording processing metrics"""
        dashboard.record_processing(
            "slack",
            processed_count=10,
            duplicate_count=2,
            process_time_ms=50,
            attachment_count=3,
            data_size_bytes=5000
        )

        metrics = dashboard.metrics["slack"]
        assert metrics.messages_duplicate == 2
        assert metrics.attachment_count == 3
        assert metrics.fetch_size_bytes == 5000

    def test_timing_metrics_calculation(self, dashboard):
        """Test timing metrics calculation"""
        # Record multiple fetches
        for time_ms in [100, 150, 200, 120, 180]:
            dashboard.record_fetch(
                "slack",
                message_count=5,
                fetch_time_ms=time_ms,
                success=True
            )

        metrics = dashboard.metrics["slack"]
        expected_avg = (100 + 150 + 200 + 120 + 180) / 5

        assert metrics.avg_fetch_time_ms == expected_avg
        assert metrics.p99_fetch_time_ms > 0

    def test_p99_timing_calculation(self, dashboard):
        """Test P99 timing calculation"""
        times = [100, 150, 200, 250, 300, 350, 400, 450, 500, 550]

        for time_ms in times:
            dashboard.record_fetch(
                "slack",
                message_count=1,
                fetch_time_ms=time_ms,
                success=True
            )

        metrics = dashboard.metrics["slack"]
        # P99 should be close to max
        assert metrics.p99_fetch_time_ms >= 500

    def test_timing_history_limit(self, dashboard):
        """Test that timing history is limited to 1000 entries"""
        # Record more than 1000 fetches
        for i in range(1100):
            dashboard.record_fetch(
                "slack",
                message_count=1,
                fetch_time_ms=100,
                success=True
            )

        # Should only keep last 1000
        assert len(dashboard.fetch_times["slack"]) == 1000


class TestDashboardHealthMonitoring:
    """Test health monitoring functionality"""

    def test_update_health_status(self, dashboard):
        """Test updating health status"""
        dashboard.update_health(
            "slack",
            enabled=True,
            configured=True,
            has_valid_token=True,
            has_required_permissions=True
        )

        health = dashboard.health["slack"]
        assert health.enabled == True
        assert health.configured == True
        assert health.has_valid_token == True
        assert health.has_required_permissions == True

    def test_health_status_healthy(self, dashboard):
        """Test healthy status calculation"""
        dashboard.update_health(
            "slack",
            enabled=True,
            configured=True,
            has_valid_token=True,
            has_required_permissions=True
        )

        dashboard.record_fetch(
            "slack",
            message_count=10,
            fetch_time_ms=100,
            success=True
        )

        health = dashboard.health["slack"]
        assert health.status == IntegrationStatus.HEALTHY

    def test_health_status_disabled(self, dashboard):
        """Test disabled status"""
        dashboard.update_health(
            "slack",
            enabled=False,
            configured=True
        )

        health = dashboard.health["slack"]
        assert health.status == IntegrationStatus.DISABLED

    def test_health_status_not_configured(self, dashboard):
        """Test not_configured status"""
        dashboard.update_health(
            "gmail",
            enabled=True,
            configured=False
        )

        health = dashboard.health["gmail"]
        assert health.status == IntegrationStatus.NOT_CONFIGURED

    def test_health_status_degraded_consecutive_failures(self, dashboard):
        """Test degraded status from consecutive failures"""
        dashboard.update_health(
            "teams",
            enabled=True,
            configured=True
        )

        # Record 3 consecutive failures (warning threshold)
        for _ in range(3):
            dashboard.record_fetch(
                "teams",
                message_count=0,
                fetch_time_ms=100,
                success=False
            )

        health = dashboard.health["teams"]
        assert health.status == IntegrationStatus.DEGRADED
        assert health.consecutive_failures == 3

    def test_health_status_error_consecutive_failures(self, dashboard):
        """Test error status from many consecutive failures"""
        dashboard.update_health(
            "gmail",
            enabled=True,
            configured=True
        )

        # Record 5 consecutive failures (critical threshold)
        for _ in range(5):
            dashboard.record_fetch(
                "gmail",
                message_count=0,
                fetch_time_ms=100,
                success=False
            )

        health = dashboard.health["gmail"]
        assert health.status == IntegrationStatus.ERROR
        assert health.consecutive_failures == 5

    def test_health_status_recovery(self, dashboard):
        """Test health status recovery after failures"""
        dashboard.update_health(
            "slack",
            enabled=True,
            configured=True
        )

        # Record failures
        for _ in range(3):
            dashboard.record_fetch(
                "slack",
                message_count=0,
                fetch_time_ms=100,
                success=False
            )

        health = dashboard.health["slack"]
        assert health.consecutive_failures == 3

        # Record success
        dashboard.record_fetch(
            "slack",
            message_count=10,
            fetch_time_ms=100,
            success=True
        )

        health = dashboard.health["slack"]
        assert health.consecutive_failures == 0
        assert health.consecutive_successes == 1
        assert health.status == IntegrationStatus.HEALTHY


class TestDashboardMetricsRetrieval:
    """Test metrics retrieval functionality"""

    def test_get_metrics_all(self, populated_dashboard):
        """Test getting metrics for all integrations"""
        metrics = populated_dashboard.get_metrics()

        assert "slack" in metrics
        assert "teams" in metrics
        assert "gmail" in metrics

        assert metrics["slack"]["messages_fetched"] == 10
        assert metrics["teams"]["messages_fetched"] == 5

    def test_get_metrics_specific(self, populated_dashboard):
        """Test getting metrics for specific integration"""
        metrics = populated_dashboard.get_metrics("slack")

        assert metrics["messages_fetched"] == 10
        assert metrics["messages_duplicate"] == 2

    def test_get_metrics_nonexistent(self, dashboard):
        """Test getting metrics for non-existent integration"""
        metrics = dashboard.get_metrics("nonexistent")

        assert metrics == {}

    def test_get_health_all(self, populated_dashboard):
        """Test getting health for all integrations"""
        health = populated_dashboard.get_health()

        assert "slack" in health
        assert "teams" in health
        assert "gmail" in health

        assert health["slack"]["status"] == "healthy"
        assert health["gmail"]["status"] == "not_configured"

    def test_get_health_specific(self, populated_dashboard):
        """Test getting health for specific integration"""
        health = populated_dashboard.get_health("slack")

        assert health["enabled"] == True
        assert health["configured"] == True

    def test_get_overall_status(self, populated_dashboard):
        """Test getting overall status"""
        status = populated_dashboard.get_overall_status()

        assert "overall_status" in status
        assert "total_integrations" in status
        assert "healthy_count" in status
        assert "degraded_count" in status
        assert "error_count" in status
        assert status["total_integrations"] == 4


class TestDashboardConfiguration:
    """Test configuration management"""

    def test_update_configuration(self, dashboard):
        """Test updating configuration"""
        config = {
            "batch_size": 50,
            "polling_interval": 300,
            "enabled_channels": ["general", "random"]
        }

        result = dashboard.update_configuration("slack", config)

        assert result == True
        assert dashboard.configurations["slack"]["batch_size"] == 50
        assert dashboard.configurations["slack"]["polling_interval"] == 300

    def test_update_configuration_append(self, dashboard):
        """Test that update_configuration appends to existing config"""
        dashboard.update_configuration("teams", {"batch_size": 25})
        dashboard.update_configuration("teams", {"polling_interval": 600})

        assert dashboard.configurations["teams"]["batch_size"] == 25
        assert dashboard.configurations["teams"]["polling_interval"] == 600

    def test_get_configuration_all(self, dashboard):
        """Test getting all configurations"""
        dashboard.update_configuration("slack", {"batch_size": 50})
        dashboard.update_configuration("teams", {"batch_size": 25})

        config = dashboard.get_configuration()

        assert "slack" in config
        assert "teams" in config
        assert config["slack"]["batch_size"] == 50

    def test_get_configuration_specific(self, dashboard):
        """Test getting specific configuration"""
        dashboard.update_configuration("gmail", {"label_ids": ["INBOX"]})

        config = dashboard.get_configuration("gmail")

        assert config["label_ids"] == ["INBOX"]


class TestDashboardAlerts:
    """Test alert generation"""

    def test_alert_consecutive_failures_warning(self, dashboard):
        """Test alert for consecutive failures (warning)"""
        dashboard.update_health("slack", enabled=True, configured=True)

        for _ in range(3):
            dashboard.record_fetch(
                "slack",
                message_count=0,
                fetch_time_ms=100,
                success=False
            )

        alerts = dashboard.get_alerts()

        failure_alerts = [a for a in alerts if a["type"] == "consecutive_failures"]
        assert len(failure_alerts) == 1
        assert failure_alerts[0]["severity"] == "warning"

    def test_alert_consecutive_failures_critical(self, dashboard):
        """Test alert for consecutive failures (critical)"""
        dashboard.update_health("teams", enabled=True, configured=True)

        for _ in range(5):
            dashboard.record_fetch(
                "teams",
                message_count=0,
                fetch_time_ms=100,
                success=False
            )

        alerts = dashboard.get_alerts()

        failure_alerts = [a for a in alerts if a["type"] == "consecutive_failures"]
        assert len(failure_alerts) == 1
        assert failure_alerts[0]["severity"] == "critical"

    def test_alert_slow_fetch_warning(self, dashboard):
        """Test alert for slow fetch (warning)"""
        dashboard.update_health("slack", enabled=True, configured=True)

        # Record slow fetch
        for _ in range(10):
            dashboard.record_fetch(
                "slack",
                message_count=1,
                fetch_time_ms=6000,  # Above warning threshold
                success=True
            )

        alerts = dashboard.get_alerts()

        slow_alerts = [a for a in alerts if a["type"] == "slow_fetch"]
        assert len(slow_alerts) == 1
        assert slow_alerts[0]["severity"] == "warning"

    def test_alert_slow_fetch_critical(self, dashboard):
        """Test alert for slow fetch (critical)"""
        dashboard.update_health("teams", enabled=True, configured=True)

        # Record very slow fetch
        for _ in range(10):
            dashboard.record_fetch(
                "teams",
                message_count=1,
                fetch_time_ms=12000,  # Above critical threshold
                success=True
            )

        alerts = dashboard.get_alerts()

        slow_alerts = [a for a in alerts if a["type"] == "slow_fetch"]
        assert len(slow_alerts) == 1
        assert slow_alerts[0]["severity"] == "critical"

    def test_alert_token_expiry_warning(self, dashboard):
        """Test alert for token expiry (warning)"""
        dashboard.update_health(
            "gmail",
            enabled=True,
            configured=True,
            token_expiry=datetime.now() + timedelta(minutes=45)
        )

        alerts = dashboard.get_alerts()

        token_alerts = [a for a in alerts if a["type"] == "token_expiry"]
        assert len(token_alerts) == 1
        assert token_alerts[0]["severity"] == "warning"

    def test_alert_token_expiry_critical(self, dashboard):
        """Test alert for token expiry (critical)"""
        dashboard.update_health(
            "outlook",
            enabled=True,
            configured=True,
            token_expiry=datetime.now() + timedelta(minutes=10)
        )

        alerts = dashboard.get_alerts()

        token_alerts = [a for a in alerts if a["type"] == "token_expiry"]
        assert len(token_alerts) == 1
        assert token_alerts[0]["severity"] == "critical"

    def test_no_alerts_healthy_system(self, dashboard):
        """Test that healthy system generates no alerts"""
        dashboard.update_health(
            "slack",
            enabled=True,
            configured=True,
            has_valid_token=True,
            has_required_permissions=True
        )

        dashboard.record_fetch(
            "slack",
            message_count=10,
            fetch_time_ms=100,
            success=True
        )

        alerts = dashboard.get_alerts()

        # Should have minimal or no alerts
        failure_alerts = [a for a in alerts if a["severity"] in ["critical", "warning"]]
        assert len(failure_alerts) == 0


class TestDashboardReset:
    """Test metrics reset functionality"""

    def test_reset_metrics_all(self, populated_dashboard):
        """Test resetting all metrics"""
        populated_dashboard.reset_metrics()

        for metrics in populated_dashboard.metrics.values():
            assert metrics.messages_fetched == 0
            assert metrics.messages_processed == 0
            assert metrics.avg_fetch_time_ms == 0.0

        assert len(populated_dashboard.fetch_times) == 0
        assert len(populated_dashboard.process_times) == 0

    def test_reset_metrics_specific(self, populated_dashboard):
        """Test resetting metrics for specific integration"""
        slack_messages_before = populated_dashboard.metrics["slack"].messages_fetched

        populated_dashboard.reset_metrics("slack")

        assert populated_dashboard.metrics["slack"].messages_fetched == 0
        # Teams should be unaffected
        assert populated_dashboard.metrics["teams"].messages_fetched == 5


class TestDashboardStatistics:
    """Test statistics and summary"""

    def test_statistics_summary(self, dashboard):
        """Test statistics summary generation"""
        dashboard.update_health("slack", enabled=True, configured=True)
        dashboard.record_fetch(
            "slack",
            message_count=10,
            fetch_time_ms=100,
            success=True
        )

        summary = dashboard.get_statistics_summary()

        assert "total_messages_24h" in summary
        assert "active_integrations" in summary
        assert "overall_status" in summary
        assert "alert_count" in summary
        assert "timestamp" in summary

    def test_statistics_summary_multiple_integrations(self, populated_dashboard):
        """Test statistics with multiple active integrations"""
        summary = populated_dashboard.get_statistics_summary()

        assert summary["active_integrations"] >= 2  # Slack and Teams


class TestDashboardSingleton:
    """Test singleton instance"""

    def test_singleton_instance(self):
        """Test that get_integration_dashboard returns singleton"""
        dashboard1 = get_integration_dashboard()
        dashboard2 = get_integration_dashboard()

        assert dashboard1 is dashboard2

    def test_singleton_persistence(self):
        """Test that changes persist through singleton"""
        dashboard = get_integration_dashboard()

        dashboard.record_fetch(
            "test",
            message_count=5,
            fetch_time_ms=100,
            success=True
        )

        # Get instance again
        dashboard2 = get_integration_dashboard()

        assert dashboard2.metrics["test"].messages_fetched == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
