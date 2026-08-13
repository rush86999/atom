# -*- coding: utf-8 -*-
"""Coverage wave 86 — core/health_monitor (checks, thresholds, alerting,
degraded states).

IntegrationHealthCheck / HealthMonitor tested with asyncio + mocked time and
sleeps (no real waiting):

- IntegrationHealthCheck.run_check: fast success → HEALTHY, slow success
  (5–10s) → DEGRADED, false result → UNHEALTHY, exception → UNHEALTHY with
  error payload; consecutive-failure bookkeeping; response time capture.
- HealthMonitor: register, check_all_services (empty + populated + gather
  exception filtering), _check_alerts threshold hit/miss, start_monitoring
  (first start + already-running warning), _monitoring_loop success and
  exception paths, stop_monitoring, get_health_summary (empty, mixed).
- Module-level example checks + global registry wiring.
"""
import asyncio
import logging
from unittest.mock import AsyncMock, patch

import pytest

from core.health_monitor import (
    HealthMonitor, HealthStatus, IntegrationHealthCheck,
    check_google_health, check_microsoft_health, check_salesforce_health,
    health_monitor,
)


async def _ok():
    return True


async def _boom():
    raise RuntimeError("service down")


# ---------------------------------------------------------------------------
# IntegrationHealthCheck.run_check
# ---------------------------------------------------------------------------

def test_run_check_healthy():
    check = IntegrationHealthCheck("svc", _ok)
    result = asyncio.run(check.run_check())
    assert result["status"] == "healthy"
    assert result["name"] == "svc"
    assert result["response_time_ms"] >= 0
    assert result["consecutive_failures"] == 0
    assert result["last_check"] is not None
    assert check.last_status == HealthStatus.HEALTHY


def test_run_check_degraded_when_slow(monkeypatch):
    """A truthy result slower than 5s (but under 10s) → DEGRADED."""
    check = IntegrationHealthCheck("svc", _ok)
    calls = {"n": 0}
    real = __import__("time").time

    def _slow_time():
        if calls["n"] == 0:
            calls["n"] = 1
            return real()
        return real() + 6.5  # 6.5s elapsed

    monkeypatch.setattr("core.health_monitor.time.time", _slow_time)
    result = asyncio.run(check.run_check())
    assert result["status"] == "degraded"
    assert check.last_status == HealthStatus.DEGRADED
    assert check.consecutive_failures == 0


def test_run_check_unhealthy_on_false_result():
    async def _false():
        return None

    check = IntegrationHealthCheck("svc", _false)
    result = asyncio.run(check.run_check())
    assert result["status"] == "unhealthy"
    assert check.last_status == HealthStatus.UNHEALTHY
    assert check.consecutive_failures == 1


def test_run_check_unhealthy_on_exception(caplog):
    check = IntegrationHealthCheck("svc", _boom)
    with caplog.at_level(logging.ERROR, logger="core.health_monitor"):
        result = asyncio.run(check.run_check())
    assert result["status"] == "unhealthy"
    assert "service down" in result["error"]
    assert check.consecutive_failures == 1
    assert "Health check failed for svc" in caplog.text


# ---------------------------------------------------------------------------
# HealthMonitor
# ---------------------------------------------------------------------------

def test_register_health_check(caplog):
    monitor = HealthMonitor()
    with caplog.at_level(logging.INFO, logger="core.health_monitor"):
        monitor.register_health_check("google", _ok)
    assert "google" in monitor.health_checks
    assert "Registered health check for google" in caplog.text


def test_check_all_services_empty():
    monitor = HealthMonitor()
    assert asyncio.run(monitor.check_all_services()) == []


def test_check_all_services_runs_all_and_filters_gather_errors():
    monitor = HealthMonitor()
    monitor.register_health_check("good", _ok)

    async def _raises():
        raise ValueError("x")

    monitor.register_health_check("bad", _raises)
    results = asyncio.run(monitor.check_all_services())
    assert len(results) == 2  # run_check swallows the exception into a dict
    statuses = {r["name"]: r["status"] for r in results}
    assert statuses == {"good": "healthy", "bad": "unhealthy"}


def test_check_all_services_alerts_on_threshold(caplog):
    monitor = HealthMonitor()
    monitor.alert_threshold = 3
    monitor.register_health_check("svc", _boom)
    with caplog.at_level(logging.ERROR, logger="core.health_monitor"):
        for _ in range(3):
            asyncio.run(monitor.check_all_services())
    assert "ALERT: svc has failed 3 consecutive health checks" in caplog.text


def test_check_alerts_below_threshold_no_alert(caplog):
    monitor = HealthMonitor()
    monitor.alert_threshold = 3
    monitor.register_health_check("svc", _boom)
    with caplog.at_level(logging.ERROR, logger="core.health_monitor"):
        asyncio.run(monitor.check_all_services())  # 1 failure < 3
    assert "ALERT" not in caplog.text


def test_start_monitoring_and_stop():
    monitor = HealthMonitor(check_interval_seconds=0)
    monitor.register_health_check("svc", _ok)

    async def _main():
        await monitor.start_monitoring()
        assert monitor.monitoring_task is not None
        monitor.stop_monitoring()
        with pytest.raises(asyncio.CancelledError):
            await monitor.monitoring_task

    asyncio.run(_main())


def test_start_monitoring_already_running_warning(caplog):
    monitor = HealthMonitor(check_interval_seconds=0)

    async def _main():
        await monitor.start_monitoring()
        with caplog.at_level(logging.WARNING, logger="core.health_monitor"):
            await monitor.start_monitoring()  # second start → warning
        assert "already running" in caplog.text
        monitor.stop_monitoring()

    asyncio.run(_main())


def test_monitoring_loop_runs_checks():
    monitor = HealthMonitor(check_interval_seconds=0)
    monitor.register_health_check("svc", _ok)
    real_sleep = asyncio.sleep

    async def _sleep(delay):
        if delay >= 1:  # interval/recovery sleeps return instantly
            return
        await real_sleep(delay)

    with patch("core.health_monitor.asyncio.sleep", side_effect=_sleep):
        async def _main():
            await monitor.start_monitoring()
            await real_sleep(0.05)
            monitor.stop_monitoring()
            with pytest.raises(asyncio.CancelledError):
                await monitor.monitoring_task

        asyncio.run(_main())
    assert monitor.health_checks["svc"].last_status == HealthStatus.HEALTHY


def test_monitoring_loop_exception_path():
    monitor = HealthMonitor(check_interval_seconds=0)
    monitor.register_health_check("svc", _ok)
    real_sleep = asyncio.sleep

    async def _sleep(delay):
        await real_sleep(0.01)  # brief real yield, no long waits

    with patch("core.health_monitor.asyncio.sleep", side_effect=_sleep):
        with patch.object(monitor, "check_all_services", side_effect=RuntimeError("loop boom")):
            async def _main():
                await monitor.start_monitoring()
                await real_sleep(0.05)
                monitor.stop_monitoring()
                with pytest.raises(asyncio.CancelledError):
                    await monitor.monitoring_task

            asyncio.run(_main())


def test_get_health_summary_empty():
    monitor = HealthMonitor()
    summary = monitor.get_health_summary()
    assert summary["total_services"] == 0
    assert summary["health_percentage"] == 0
    assert summary["services"] == []


def test_get_health_summary_mixed_statuses():
    monitor = HealthMonitor()
    monitor.register_health_check("a", _ok)
    monitor.register_health_check("b", _boom)
    asyncio.run(monitor.check_all_services())  # a healthy, b unhealthy

    summary = monitor.get_health_summary()
    assert summary["total_services"] == 2
    assert summary["healthy"] == 1
    assert summary["unhealthy"] == 1
    assert summary["degraded"] == 0
    assert summary["health_percentage"] == 50.0
    by_name = {s["name"]: s for s in summary["services"]}
    assert by_name["a"]["status"] == "healthy"
    assert by_name["b"]["status"] == "unhealthy"
    assert by_name["a"]["last_check"] is not None


def test_get_health_summary_counts_degraded():
    monitor = HealthMonitor()
    check = IntegrationHealthCheck("slow", _ok)
    monitor.health_checks["slow"] = check
    with patch("core.health_monitor.time.time") as t:
        t.return_value = 1_000_000.0

        async def _first_call():
            pass

        # Simulate a 7s run: first time() call at start, second 7s later
        real = __import__("time").time
        calls = {"n": 0}

        def _slow_time():
            if calls["n"] == 0:
                calls["n"] = 1
                return real()
            return real() + 7.0

        with patch("core.health_monitor.time.time", _slow_time):
            asyncio.run(check.run_check())
    summary = monitor.get_health_summary()
    assert summary["degraded"] == 1
    assert summary["healthy"] == 0


# ---------------------------------------------------------------------------
# module-level example checks + global registry
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_example_health_checks():
    assert await check_google_health() is True
    assert await check_microsoft_health() is True
    assert await check_salesforce_health() is True


def test_global_monitor_registry():
    assert set(health_monitor.health_checks.keys()) == {"google", "microsoft", "salesforce"}
