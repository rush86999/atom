# -*- coding: utf-8 -*-
"""Round 80 — zero-coverage gap: core/health_monitor.py.

Tests for IntegrationHealthCheck (healthy/degraded/unhealthy classification,
response-time thresholds, failure counting) and HealthMonitor (registration,
check_all_services, alert firing at the consecutive-failure threshold, the
monitoring loop lifecycle and the aggregate health summary).
"""
import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from core.health_monitor import (
    HealthMonitor,
    HealthStatus,
    IntegrationHealthCheck,
    health_monitor,
)


class _Clock:
    """Injectable time source to simulate slow health checks."""

    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def advance(self, ms):
        self.now += ms / 1000.0


@pytest.fixture()
def clock():
    return _Clock()


@pytest.fixture(autouse=True)
def _patch_time(monkeypatch, clock):
    monkeypatch.setattr("core.health_monitor.time.time", clock)


async def _ok():
    return True


async def _boom():
    raise ConnectionError("refused")


def _delayed_ok(clock, ms):
    async def _check():
        clock.advance(ms)
        return True
    return _check


class TestIntegrationHealthCheck:
    def test_fast_success_is_healthy(self, clock):
        check = IntegrationHealthCheck("svc", _delayed_ok(clock, 100))
        result = asyncio.run(check.run_check())
        assert result["status"] == "healthy"
        assert result["response_time_ms"] == pytest.approx(100.0)
        assert check.last_status == HealthStatus.HEALTHY
        assert check.consecutive_failures == 0

    def test_slow_success_is_degraded(self, clock):
        check = IntegrationHealthCheck("svc", _delayed_ok(clock, 7000))
        result = asyncio.run(check.run_check())
        assert result["status"] == "degraded"
        assert check.last_status == HealthStatus.DEGRADED

    def test_exception_is_unhealthy_and_counts_failure(self, clock):
        check = IntegrationHealthCheck("svc", _boom)
        result = asyncio.run(check.run_check())
        assert result["status"] == "unhealthy"
        assert "refused" in result["error"]
        assert check.consecutive_failures == 1
        assert check.last_status == HealthStatus.UNHEALTHY

    def test_failures_reset_after_success(self, clock):
        check = IntegrationHealthCheck("svc", _boom)
        asyncio.run(check.run_check())
        asyncio.run(check.run_check())
        assert check.consecutive_failures == 2
        check.check_func = _ok
        asyncio.run(check.run_check())
        assert check.consecutive_failures == 0
        assert check.last_status == HealthStatus.HEALTHY

    def test_success_resets_failure_count_before_threshold(self, clock):
        """A success between failures must reset the counter (no false alert)."""
        check = IntegrationHealthCheck("svc", _boom)
        asyncio.run(check.run_check())
        check.check_func = _ok
        asyncio.run(check.run_check())
        assert check.consecutive_failures == 0


class TestHealthMonitor:
    def test_register_adds_check(self):
        monitor = HealthMonitor()
        monitor.register_health_check("svc", _ok)
        assert "svc" in monitor.health_checks
        assert monitor.health_checks["svc"].name == "svc"

    def test_check_all_returns_results(self, clock):
        monitor = HealthMonitor()
        monitor.register_health_check("ok", _ok)
        monitor.register_health_check("bad", _boom)
        clock.advance(50)
        results = asyncio.run(monitor.check_all_services())
        statuses = {r["name"]: r["status"] for r in results}
        assert statuses == {"ok": "healthy", "bad": "unhealthy"}

    def test_check_all_empty_returns_empty(self):
        monitor = HealthMonitor()
        assert asyncio.run(monitor.check_all_services()) == []

    def test_alert_fires_at_threshold(self, clock):
        monitor = HealthMonitor()
        monitor.alert_threshold = 2
        monitor.register_health_check("svc", _boom)
        with patch("core.health_monitor.logger.error") as mock_err:
            asyncio.run(monitor.check_all_services())
            asyncio.run(monitor.check_all_services())
        assert any("ALERT" in str(call) for call in mock_err.call_args_list)

    def test_no_alert_below_threshold(self, clock):
        monitor = HealthMonitor()
        monitor.alert_threshold = 3
        monitor.register_health_check("svc", _boom)
        with patch("core.health_monitor.logger.error") as mock_err:
            asyncio.run(monitor.check_all_services())
            asyncio.run(monitor.check_all_services())
        assert not any("ALERT" in str(call) for call in mock_err.call_args_list)

    def test_alert_disabled(self, clock):
        monitor = HealthMonitor()
        monitor.alerts_enabled = False
        monitor.alert_threshold = 1
        monitor.register_health_check("svc", _boom)
        with patch("core.health_monitor.logger.error") as mock_err:
            asyncio.run(monitor.check_all_services())
        assert not any("ALERT" in str(call) for call in mock_err.call_args_list)

    def test_start_and_stop_monitoring(self):
        monitor = HealthMonitor(check_interval_seconds=60)
        monitor.register_health_check("svc", _ok)
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            loop.run_until_complete(monitor.start_monitoring())
            assert monitor.monitoring_task is not None
            assert not monitor.monitoring_task.done()
            monitor.stop_monitoring()
            with pytest.raises(asyncio.CancelledError):
                loop.run_until_complete(monitor.monitoring_task)
            assert monitor.monitoring_task.cancelled()
        finally:
            loop.close()
            asyncio.set_event_loop(None)

    def test_start_twice_keeps_single_task(self):
        monitor = HealthMonitor(check_interval_seconds=60)
        monitor.register_health_check("svc", _ok)
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            loop.run_until_complete(monitor.start_monitoring())
            first = monitor.monitoring_task
            with patch("core.health_monitor.logger.warning") as mock_warn:
                loop.run_until_complete(monitor.start_monitoring())
            assert monitor.monitoring_task is first
            mock_warn.assert_called()
            monitor.stop_monitoring()
            with pytest.raises(asyncio.CancelledError):
                loop.run_until_complete(monitor.monitoring_task)
        finally:
            loop.close()
            asyncio.set_event_loop(None)

    def test_loop_recovers_from_exception(self):
        """A check raising inside the loop must not kill the loop; it sleeps
        the recovery interval and keeps going. The loop exits when a later
        iteration is cancelled."""
        monitor = HealthMonitor(check_interval_seconds=60)
        monitor.register_health_check("svc", _boom)
        with patch("asyncio.sleep", new=AsyncMock(side_effect=asyncio.CancelledError)):
            with pytest.raises(asyncio.CancelledError):
                asyncio.run(monitor._monitoring_loop())
        assert monitor.health_checks["svc"].consecutive_failures >= 1


class TestHealthSummary:
    def test_summary_counts(self, clock):
        monitor = HealthMonitor()
        monitor.register_health_check("a", _ok)
        monitor.register_health_check("b", _ok)
        monitor.register_health_check("c", _boom)
        asyncio.run(monitor.check_all_services())
        summary = monitor.get_health_summary()
        assert summary["total_services"] == 3
        assert summary["healthy"] == 2
        assert summary["unhealthy"] == 1
        assert summary["degraded"] == 0
        assert summary["health_percentage"] == pytest.approx(66.7, abs=0.1)
        assert len(summary["services"]) == 3

    def test_summary_empty_monitor(self):
        summary = HealthMonitor().get_health_summary()
        assert summary["total_services"] == 0
        assert summary["health_percentage"] == 0.0
        assert summary["services"] == []

    def test_summary_reflects_unknown_before_checks(self):
        monitor = HealthMonitor()
        monitor.register_health_check("svc", _ok)
        summary = monitor.get_health_summary()
        assert summary["services"][0]["status"] == "unknown"
        assert summary["services"][0]["last_check"] is None

    def test_global_monitor_has_default_services(self):
        assert {"google", "microsoft", "salesforce"} <= set(health_monitor.health_checks.keys())
