"""Coverage wave 71 — core/integration_dashboard.py (96% → 100%).

Closes the remaining holes: record_processing/update_health/
_update_health_status lazy init for unknown integrations, error-rate
critical + warning branches in both _update_health_status and
get_alerts, get_health unknown-integration fallback.
"""
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

import core.integration_dashboard as idb
from core.integration_dashboard import (
    IntegrationDashboard,
    IntegrationHealth,
    IntegrationMetrics,
    IntegrationStatus,
    get_integration_dashboard,
    integration_dashboard,
)


@pytest.fixture
def dash():
    return IntegrationDashboard()


class TestLazyInitBranches:
    def test_record_fetch_unknown_integration_init(self, dash):
        dash.record_fetch("webex", 5, 12.0, success=True)
        assert "webex" in dash.metrics
        assert dash.metrics["webex"].messages_fetched == 5

    def test_record_processing_unknown_integration_init(self, dash):
        dash.record_processing("webex", 3, 1, 20.0, attachment_count=2, data_size_bytes=100)
        m = dash.metrics["webex"]
        assert m.messages_duplicate == 1
        assert m.attachment_count == 2
        assert m.fetch_size_bytes == 100
        assert m.avg_process_time_ms == 20.0

    def test_update_health_unknown_integration_init(self, dash):
        dash.update_health("webex", enabled=True, configured=True)
        assert dash.health["webex"].status == IntegrationStatus.HEALTHY

    def test_update_health_status_unknown_integration(self, dash):
        dash._update_health_status("webex")
        assert dash.health["webex"].status == IntegrationStatus.DISABLED


class TestErrorRateStatusBranches:
    def test_error_rate_critical_status(self, dash):
        dash.update_health("slack", enabled=True, configured=True)
        dash.record_fetch("slack", 10, 5.0, success=False)
        assert dash.health["slack"].status == IntegrationStatus.ERROR

    def test_error_rate_warning_status(self, dash):
        dash.update_health("slack", enabled=True, configured=True)
        for _ in range(9):
            dash.record_fetch("slack", 10, 5.0, success=True)
        dash.record_fetch("slack", 10, 5.0, success=False)
        assert dash.health["slack"].status == IntegrationStatus.DEGRADED

    def test_get_health_unknown_returns_empty(self, dash):
        assert dash.get_health("webex") == {}


class TestAlertsErrorRate:
    def test_alerts_error_rate_critical(self, dash):
        dash.update_health("slack", enabled=True, configured=True)
        dash.record_fetch("slack", 10, 5.0, success=False)
        alerts = dash.get_alerts()
        high = [a for a in alerts if a["type"] == "high_error_rate"]
        assert any(a["severity"] == "critical" for a in high)

    def test_alerts_error_rate_warning(self, dash):
        dash.update_health("slack", enabled=True, configured=True)
        for _ in range(9):
            dash.record_fetch("slack", 10, 5.0, success=True)
        dash.record_fetch("slack", 10, 5.0, success=False)
        alerts = dash.get_alerts()
        high = [a for a in alerts if a["type"] == "high_error_rate"]
        assert any(a["severity"] == "warning" for a in high)


class TestMetricsMisc:
    def test_success_rate_default_when_no_activity(self):
        assert IntegrationMetrics().to_dict()["success_rate"] == 100.0

    def test_duplicate_rate_when_no_fetch(self):
        m = IntegrationMetrics()
        assert m._calculate_duplicate_rate() == 0.0

    def test_duplicate_rate_with_data(self):
        m = IntegrationMetrics(messages_fetched=100, messages_duplicate=10)
        assert m._calculate_duplicate_rate() == 10.0

    def test_to_dict_datetime_isoformat(self):
        now = datetime.now()
        m = IntegrationMetrics(last_fetch_time=now, last_success_time=now,
                               last_error_time=now, last_error_message="boom",
                               rate_limit_resets=[now])
        d = m.to_dict()
        assert d["last_fetch_time"] == now.isoformat()
        assert d["rate_limit_resets"] == [now.isoformat()]
        assert d["last_error_message"] == "boom"

    def test_health_to_dict_with_dates(self):
        now = datetime.now()
        h = IntegrationHealth(status=IntegrationStatus.DEGRADED, enabled=True,
                              configured=True, last_check=now, last_error_time=now,
                              token_expiry=now)
        d = h.to_dict()
        assert d["status"] == "degraded"
        assert d["token_expiry"] == now.isoformat()


class TestSingleton:
    def test_get_integration_dashboard_returns_singleton(self):
        assert get_integration_dashboard() is integration_dashboard

    def test_singleton_is_instance(self):
        assert isinstance(integration_dashboard, IntegrationDashboard)


class TestOverallStatus:
    def test_overall_status_healthy(self, dash):
        dash.update_health("slack", enabled=True, configured=True)
        dash.update_health("teams", enabled=True, configured=True)
        status = dash.get_overall_status()
        assert status["overall_status"] == "healthy"
        assert status["healthy_count"] == 2

    def test_overall_status_degraded_without_errors(self, dash):
        dash.update_health("slack", enabled=True, configured=True)
        dash.update_health("teams", enabled=True, configured=True)
        dash.record_fetch("teams", 10, 5.0, success=False)
        dash.record_fetch("teams", 10, 5.0, success=False)
        dash.record_fetch("teams", 10, 5.0, success=False)
        status = dash.get_overall_status()
        assert status["overall_status"] == "degraded"

    def test_overall_status_error(self, dash):
        dash.update_health("slack", enabled=True, configured=True)
        dash.update_health("teams", enabled=True, configured=True)
        for _ in range(6):
            dash.record_fetch("teams", 10, 5.0, success=False)
        status = dash.get_overall_status()
        assert status["overall_status"] == "error"
        assert status["error_count"] == 1

    def test_overall_success_rate_zero_activity(self, dash):
        assert dash.get_overall_status()["overall_success_rate"] == 100.0

    def test_overall_success_rate_computed(self, dash):
        dash.record_fetch("slack", 100, 5.0, success=True)
        dash.record_fetch("teams", 50, 5.0, success=False)
        assert dash.get_overall_status()["overall_success_rate"] == 66.66666666666666


class TestConfigurationAndReset:
    def test_get_configuration_single_unknown(self, dash):
        assert dash.get_configuration("webex") == {}

    def test_update_and_get_configuration(self, dash):
        dash.update_configuration("slack", {"webhook": "x"})
        assert dash.get_configuration("slack") == {"webhook": "x"}
        assert dash.get_configuration() == {"slack": {"webhook": "x"}}

    def test_reset_metrics_single(self, dash):
        dash.record_fetch("slack", 10, 5.0)
        dash.reset_metrics("slack")
        assert dash.metrics["slack"].messages_fetched == 0

    def test_reset_metrics_all(self, dash):
        dash.record_fetch("slack", 10, 5.0)
        dash.record_fetch("teams", 10, 5.0)
        dash.reset_metrics()
        assert dash.metrics["slack"].messages_fetched == 0
        assert dash.metrics["teams"].messages_fetched == 0


class TestStatisticsSummary:
    def test_summary_active_integrations(self, dash):
        dash.record_fetch("slack", 10, 5.0)
        summary = dash.get_statistics_summary()
        assert summary["total_messages_24h"] == 10
        assert summary["active_integrations"] == 1
        assert "alert_count" in summary

    def test_summary_stale_integration_not_counted(self, dash):
        dash.record_fetch("slack", 10, 5.0)
        dash.metrics["slack"].last_fetch_time = datetime.now() - timedelta(days=2)
        summary = dash.get_statistics_summary()
        assert summary["active_integrations"] == 0
        assert summary["total_messages_24h"] == 0


class TestHealthStatusTransitions:
    def test_disabled_status(self, dash):
        dash.record_fetch("slack", 1, 1.0)
        dash.update_health("slack", enabled=False)
        assert dash.health["slack"].status == IntegrationStatus.DISABLED

    def test_not_configured_status(self, dash):
        dash.update_health("slack", enabled=True, configured=False)
        assert dash.health["slack"].status == IntegrationStatus.NOT_CONFIGURED

    def test_critical_failures_status(self, dash):
        dash.update_health("slack", enabled=True, configured=True)
        for _ in range(5):
            dash.record_fetch("slack", 1, 1.0, success=False)
        assert dash.health["slack"].status == IntegrationStatus.ERROR

    def test_warning_failures_status(self, dash):
        dash.update_health("slack", enabled=True, configured=True)
        for _ in range(3):
            dash.record_fetch("slack", 1, 1.0, success=False)
        assert dash.health["slack"].status == IntegrationStatus.DEGRADED

    def test_token_expiry_degraded(self, dash):
        dash.update_health("slack", enabled=True, configured=True,
                           token_expiry=datetime.now() + timedelta(minutes=30))
        assert dash.health["slack"].status == IntegrationStatus.DEGRADED

    def test_token_expiry_healthy_far_out(self, dash):
        dash.update_health("slack", enabled=True, configured=True,
                           token_expiry=datetime.now() + timedelta(days=30))
        assert dash.health["slack"].status == IntegrationStatus.HEALTHY


class TestFetchProcessingMetrics:
    def test_record_fetch_rate_limited(self, dash):
        dash.record_fetch("slack", 5, 10.0, success=True, rate_limited=True)
        m = dash.metrics["slack"]
        assert m.rate_limit_hits == 1
        assert len(m.rate_limit_resets) == 1
        assert m.p99_fetch_time_ms == 10.0

    def test_record_fetch_failure_tracks_error(self, dash):
        dash.record_fetch("slack", 3, 8.0, success=False, error_message="timeout")
        m = dash.metrics["slack"]
        assert m.messages_failed == 3
        assert m.last_error_message == "timeout"
        assert dash.health["slack"].consecutive_failures == 1

    def test_record_fetch_success_resets_failure_count(self, dash):
        dash.record_fetch("slack", 1, 1.0, success=False)
        dash.record_fetch("slack", 1, 1.0, success=True)
        assert dash.health["slack"].consecutive_failures == 0
        assert dash.health["slack"].consecutive_successes == 1

    def test_record_fetch_unknown_integration_new_health(self, dash):
        dash.record_fetch("teams", 2, 3.0, success=True)
        assert dash.health["teams"].consecutive_successes == 1

    def test_processing_p99(self, dash):
        for i in range(1, 101):
            dash.record_processing("slack", 1, 0, float(i))
        m = dash.metrics["slack"]
        assert m.p99_process_time_ms >= 99.0
        assert m.avg_process_time_ms == 50.5
