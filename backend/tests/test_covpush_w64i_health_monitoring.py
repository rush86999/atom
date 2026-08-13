"""Coverage wave 64i — core/health_monitoring_service.py to >=95% (TDD).

Extends the existing suites (which reached 97% via
tests/core/test_health_monitoring_service_coverage.py) to 100% standalone:
agent health paused-after-completed branch, integrations outer-exception path,
integration stable-trend branch, monitoring loop with agents present — plus a
regression test for a real bug found during this wave: get_system_metrics
called get_active_alerts_summary() -> get_active_alerts() -> get_system_metrics()
(an infinite mutual recursion terminated only by the Python stack limit).

Style: mocked DB queries, mocked psutil, mocked ws broadcast. No network,
no real DB, no LLM.
"""
import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core import health_monitoring_service as hm_mod
from core.health_monitoring_service import (
    HealthMonitoringService,
    get_health_monitoring_service,
)


def _make_agent(agent_id="a1", name="AgentOne", status="idle",
                confidence_score=0.8, updated_at=None, user_id="u1"):
    ag = MagicMock()
    ag.id = agent_id
    ag.name = name
    ag.status = status
    ag.confidence_score = confidence_score
    ag.updated_at = updated_at or datetime(2026, 1, 1, tzinfo=timezone.utc)
    ag.user_id = user_id
    return ag


def _make_exec(status="completed", started_at=None, completed_at=None,
               input_summary="sum"):
    e = MagicMock()
    e.status = status
    e.started_at = started_at or datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    e.completed_at = completed_at
    e.input_summary = input_summary
    return e


def _make_metric(success_rate, latency_ms=100, requests=10, errors=0):
    m = MagicMock()
    m.success_rate = success_rate
    m.latency_ms = latency_ms
    m.request_count = requests
    m.error_count = errors
    return m


def _make_connection(status="active", updated_at=None, created_at=None,
                     integration_id="i1"):
    conn = MagicMock()
    conn.id = "c1"
    conn.integration_id = integration_id
    conn.status = status
    conn.updated_at = updated_at or datetime(2026, 1, 1, tzinfo=timezone.utc)
    conn.created_at = created_at or datetime(2025, 12, 1, tzinfo=timezone.utc)
    return conn


def _make_integration(iid="i1", name="Int1"):
    integration = MagicMock()
    integration.id = iid
    integration.name = name
    return integration


def _metrics_query(db, metrics):
    """Configure the IntegrationHealthMetrics query chain to return metrics."""
    db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = metrics
    return db


def _base_metrics(cpu=0, memory=0, queue=0):
    return {"cpu_usage": cpu, "memory_usage": memory, "queue_depth": queue,
            "disk_usage": 0}


@pytest.fixture
def service_with_db():
    db = MagicMock()
    return HealthMonitoringService(db), db


# ---------------------------------------------------------------------------
# get_agent_health
# ---------------------------------------------------------------------------

class TestAgentHealth:
    @pytest.mark.asyncio
    async def test_agent_not_found(self, service_with_db):
        svc, db = service_with_db
        db.query.return_value.filter.return_value.first.return_value = None
        result = await svc.get_agent_health("missing")
        assert result["status"] == "error"
        assert "not found" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_idle_with_no_executions(self, service_with_db):
        svc, db = service_with_db
        db.query.return_value.filter.return_value.first.return_value = _make_agent()
        db.query.return_value.filter.return_value.all.return_value = []
        with patch.object(svc, "_calculate_health_trend", AsyncMock(return_value="stable")):
            result = await svc.get_agent_health("a1")
        assert result["status"] == "idle"
        assert result["operations_completed"] == 0
        assert result["metrics"]["recent_executions"] == 0
        assert result["last_active"] == (
            datetime(2026, 1, 1, tzinfo=timezone.utc).isoformat())

    @pytest.mark.asyncio
    async def test_paused_with_no_executions(self, service_with_db):
        svc, db = service_with_db
        db.query.return_value.filter.return_value.first.return_value = _make_agent(status="paused")
        db.query.return_value.filter.return_value.all.return_value = []
        with patch.object(svc, "_calculate_health_trend", AsyncMock(return_value="stable")):
            result = await svc.get_agent_health("a1")
        assert result["status"] == "paused"

    @pytest.mark.asyncio
    async def test_running_execution_sets_active(self, service_with_db):
        svc, db = service_with_db
        db.query.return_value.filter.return_value.first.return_value = _make_agent()
        db.query.return_value.filter.return_value.all.return_value = [
            _make_exec(status="completed"),
            _make_exec(status="running", input_summary="doing X"),
        ]
        with patch.object(svc, "_calculate_health_trend", AsyncMock(return_value="stable")):
            result = await svc.get_agent_health("a1")
        assert result["status"] == "active"
        assert result["current_operation"] == "doing X"
        assert result["last_active"].startswith("2026-01-01T12:00")

    @pytest.mark.asyncio
    async def test_failed_execution_sets_error(self, service_with_db):
        svc, db = service_with_db
        db.query.return_value.filter.return_value.first.return_value = _make_agent()
        db.query.return_value.filter.return_value.all.return_value = [
            _make_exec(status="failed")]
        with patch.object(svc, "_calculate_health_trend", AsyncMock(return_value="stable")):
            result = await svc.get_agent_health("a1")
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_paused_after_completed_execution(self, service_with_db):
        """Line 126: agent paused + latest execution not running/failed."""
        svc, db = service_with_db
        db.query.return_value.filter.return_value.first.return_value = _make_agent(status="paused")
        db.query.return_value.filter.return_value.all.return_value = [
            _make_exec(status="completed")]
        with patch.object(svc, "_calculate_health_trend", AsyncMock(return_value="stable")):
            result = await svc.get_agent_health("a1")
        assert result["status"] == "paused"

    @pytest.mark.asyncio
    async def test_rates_and_metrics(self, service_with_db):
        svc, db = service_with_db
        db.query.return_value.filter.return_value.first.return_value = _make_agent()
        execs = [
            _make_exec(status="completed"),
            _make_exec(status="completed"),
            _make_exec(status="failed"),
            _make_exec(status="completed"),
        ]
        db.query.return_value.filter.return_value.all.return_value = execs
        with patch.object(svc, "_calculate_health_trend", AsyncMock(return_value="stable")):
            result = await svc.get_agent_health("a1")
        assert result["success_rate"] == 0.75
        assert result["metrics"]["error_rate"] == 0.25
        assert result["operations_completed"] == 3

    @pytest.mark.asyncio
    async def test_avg_execution_time(self, service_with_db):
        svc, db = service_with_db
        db.query.return_value.filter.return_value.first.return_value = _make_agent()
        start = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        end = start + timedelta(seconds=2)
        db.query.return_value.filter.return_value.all.return_value = [
            _make_exec(status="completed", started_at=start, completed_at=end)]
        with patch.object(svc, "_calculate_health_trend", AsyncMock(return_value="stable")):
            result = await svc.get_agent_health("a1")
        assert result["metrics"]["avg_execution_time"] == 2000.0

    @pytest.mark.asyncio
    async def test_avg_execution_time_none(self, service_with_db):
        svc, db = service_with_db
        db.query.return_value.filter.return_value.first.return_value = _make_agent()
        db.query.return_value.filter.return_value.all.return_value = [
            _make_exec(status="running", completed_at=None)]
        with patch.object(svc, "_calculate_health_trend", AsyncMock(return_value="stable")):
            result = await svc.get_agent_health("a1")
        assert result["metrics"]["avg_execution_time"] is None

    @pytest.mark.asyncio
    async def test_confidence_default(self, service_with_db):
        svc, db = service_with_db
        db.query.return_value.filter.return_value.first.return_value = _make_agent(confidence_score=None)
        db.query.return_value.filter.return_value.all.return_value = []
        with patch.object(svc, "_calculate_health_trend", AsyncMock(return_value="stable")):
            result = await svc.get_agent_health("a1")
        assert result["confidence_score"] == 0.5

    @pytest.mark.asyncio
    async def test_outer_exception_returns_error(self, service_with_db):
        svc, db = service_with_db
        db.query.side_effect = RuntimeError("db down")
        result = await svc.get_agent_health("a1")
        assert result["status"] == "error"
        assert "db down" in result["error"]


# ---------------------------------------------------------------------------
# get_all_integrations_health / _calculate_integration_health
# ---------------------------------------------------------------------------

class TestIntegrationHealth:
    @pytest.mark.asyncio
    async def test_no_connections(self, service_with_db):
        svc, db = service_with_db
        db.query.return_value.filter.return_value.all.return_value = []
        assert await svc.get_all_integrations_health("u1") == []

    @pytest.mark.asyncio
    async def test_skips_connection_without_catalog_entry(self, service_with_db):
        svc, db = service_with_db
        db.query.return_value.filter.return_value.all.return_value = [
            _make_connection()]
        db.query.return_value.filter.return_value.first.return_value = None
        assert await svc.get_all_integrations_health("u1") == []

    @pytest.mark.asyncio
    async def test_happy_path_with_health(self, service_with_db):
        svc, db = service_with_db
        conn = _make_connection()
        db.query.return_value.filter.return_value.all.return_value = [conn]
        db.query.return_value.filter.return_value.first.return_value = _make_integration()
        _metrics_query(db, [])
        with patch.object(svc, "_calculate_integration_health",
                          AsyncMock(return_value={"integration_id": "i1"})):
            result = await svc.get_all_integrations_health("u1")
        assert result == [{"integration_id": "i1"}]

    @pytest.mark.asyncio
    async def test_outer_exception_returns_empty(self, service_with_db):
        """Lines 205-207: query failure -> []."""
        svc, db = service_with_db
        db.query.side_effect = RuntimeError("db down")
        assert await svc.get_all_integrations_health("u1") == []

    @pytest.mark.asyncio
    async def test_calc_healthy_no_metrics(self):
        db = MagicMock()
        svc = HealthMonitoringService(db)
        _metrics_query(db, [])
        result = await svc._calculate_integration_health(
            _make_connection(), _make_integration())
        assert result["status"] == "healthy"
        assert result["connection_status"] == "connected"
        assert result["latency_ms"] == 0.0
        assert result["error_rate"] == 0.0
        assert result["health_trend"] == "stable"

    @pytest.mark.asyncio
    async def test_calc_error_status(self):
        db = MagicMock()
        svc = HealthMonitoringService(db)
        _metrics_query(db, [])
        result = await svc._calculate_integration_health(
            _make_connection(status="error"), _make_integration())
        assert result["status"] == "error"
        assert result["connection_status"] == "error"

    @pytest.mark.asyncio
    async def test_calc_degraded_status(self):
        db = MagicMock()
        svc = HealthMonitoringService(db)
        _metrics_query(db, [])
        result = await svc._calculate_integration_health(
            _make_connection(status="revoked"), _make_integration())
        assert result["status"] == "degraded"
        assert result["connection_status"] == "disconnected"

    @pytest.mark.asyncio
    async def test_calc_uses_connection_integration_id(self):
        """Health metrics are keyed by integration_id (no connection_id col)."""
        db = MagicMock()
        svc = HealthMonitoringService(db)
        conn = _make_connection(integration_id="i-conn")
        _metrics_query(db, [_make_metric(0.9), _make_metric(0.9)])
        result = await svc._calculate_integration_health(conn, _make_integration())
        assert result["status"] == "healthy"
        filters = db.query.return_value.filter.call_args[0][0]
        assert getattr(filters.left, "name", None) == "integration_id"
        assert filters.right.value == "i-conn"

    @pytest.mark.asyncio
    async def test_calc_trend_improving(self):
        db = MagicMock()
        svc = HealthMonitoringService(db)
        _metrics_query(
            db,
            [_make_metric(0.9) for _ in range(10)]
            + [_make_metric(0.5), _make_metric(0.5)],
        )
        result = await svc._calculate_integration_health(
            _make_connection(), _make_integration())
        assert result["health_trend"] == "improving"

    @pytest.mark.asyncio
    async def test_calc_trend_declining(self):
        db = MagicMock()
        svc = HealthMonitoringService(db)
        _metrics_query(
            db,
            [_make_metric(0.3) for _ in range(10)]
            + [_make_metric(0.9), _make_metric(0.9)],
        )
        result = await svc._calculate_integration_health(
            _make_connection(), _make_integration())
        assert result["health_trend"] == "declining"

    @pytest.mark.asyncio
    async def test_calc_trend_stable(self):
        """Line 614: recent/older success within 0.1 of each other."""
        db = MagicMock()
        svc = HealthMonitoringService(db)
        _metrics_query(db, [_make_metric(0.8) for _ in range(12)])
        result = await svc._calculate_integration_health(
            _make_connection(), _make_integration())
        assert result["health_trend"] == "stable"

    @pytest.mark.asyncio
    async def test_calc_metrics_avg_latency_and_error_rate(self):
        db = MagicMock()
        svc = HealthMonitoringService(db)
        _metrics_query(
            db,
            [_make_metric(0.9, latency_ms=100, requests=100, errors=10) for _ in range(2)],
        )
        result = await svc._calculate_integration_health(
            _make_connection(), _make_integration())
        assert result["latency_ms"] == 100.0
        assert result["error_rate"] == 0.1

    @pytest.mark.asyncio
    async def test_calc_last_used_falls_back_to_created(self):
        db = MagicMock()
        svc = HealthMonitoringService(db)
        _metrics_query(db, [])
        conn = _make_connection()
        conn.updated_at = None
        result = await svc._calculate_integration_health(conn, _make_integration())
        assert result["last_used"].startswith("2025-12-01")

    @pytest.mark.asyncio
    async def test_calc_exception_returns_error_dict(self):
        db = MagicMock()
        db.query.side_effect = RuntimeError("db dead")
        svc = HealthMonitoringService(db)
        result = await svc._calculate_integration_health(
            _make_connection(), _make_integration())
        assert result["status"] == "error"
        assert result["error_rate"] == 1.0
        assert result["health_trend"] == "declining"


# ---------------------------------------------------------------------------
# get_system_metrics
# ---------------------------------------------------------------------------

class TestSystemMetrics:
    def _counts(self, db):
        db.query.return_value.count.return_value = 7
        db.query.return_value.filter.return_value.count.return_value = 3
        return db

    @pytest.mark.asyncio
    async def test_psutil_success(self, service_with_db):
        svc, db = service_with_db
        self._counts(db)
        fake = MagicMock()
        fake.cpu_percent.return_value = 42.5
        mem = MagicMock()
        mem.percent = 60.0
        fake.virtual_memory.return_value = mem
        disk = MagicMock()
        disk.percent = 75.0
        fake.disk_usage.return_value = disk
        fake.pids.return_value = list(range(10))
        with patch.dict("sys.modules", {"psutil": fake}):
            result = await svc.get_system_metrics()
        assert result["cpu_usage"] == 42.5
        assert result["memory_usage"] == 60.0
        assert result["disk_usage"] == 75.0
        assert result["total_agents"] == 7
        assert result["active_agents"] == 3
        assert result["active_operations"] == 3
        assert result["queue_depth"] == 3
        assert result["total_integrations"] == 7
        assert result["healthy_integrations"] == 3
        assert result["alerts"] == {"critical": 0, "warning": 0, "info": 0}
        assert "timestamp" in result

    @pytest.mark.asyncio
    async def test_psutil_import_error(self, service_with_db):
        svc, db = service_with_db
        self._counts(db)
        with patch.dict("sys.modules", {"psutil": None}):
            result = await svc.get_system_metrics()
        assert result["cpu_usage"] == 0
        assert result["memory_usage"] == 0

    @pytest.mark.asyncio
    async def test_psutil_runtime_error(self, service_with_db):
        svc, db = service_with_db
        self._counts(db)
        fake = MagicMock()
        fake.cpu_percent.side_effect = OSError("no perm")
        with patch.dict("sys.modules", {"psutil": fake}):
            result = await svc.get_system_metrics()
        assert result["cpu_usage"] == 0

    @pytest.mark.asyncio
    async def test_alert_counts_from_cache(self, service_with_db):
        svc, db = service_with_db
        self._counts(db)
        svc._alert_cache = {
            "1": {"severity": "critical", "acknowledged": False},
            "2": {"severity": "warning", "acknowledged": False},
            "3": {"severity": "warning", "acknowledged": True},
            "4": {"severity": "info", "acknowledged": False},
        }
        with patch.dict("sys.modules", {"psutil": None}):
            result = await svc.get_system_metrics()
        assert result["alerts"] == {"critical": 1, "warning": 1, "info": 1}

    @pytest.mark.asyncio
    async def test_no_alert_recursion(self, service_with_db):
        """REGRESSION: get_system_metrics must NOT call get_active_alerts*
        (that chain is a mutual recursion — previously ~240 nested cycles
        per call, terminated only by the Python stack limit)."""
        svc, db = service_with_db
        self._counts(db)
        with patch.dict("sys.modules", {"psutil": None}), \
             patch.object(svc, "get_active_alerts", AsyncMock()) as m, \
             patch.object(svc, "get_active_alerts_summary", AsyncMock()) as m2:
            result = await svc.get_system_metrics()
        assert result["alerts"] == {"critical": 0, "warning": 0, "info": 0}
        m.assert_not_awaited()
        m2.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_outer_exception(self, service_with_db):
        svc, db = service_with_db
        db.query.side_effect = RuntimeError("db dead")
        result = await svc.get_system_metrics()
        assert result["total_agents"] == 0
        assert "error" in result


# ---------------------------------------------------------------------------
# get_active_alerts / summary
# ---------------------------------------------------------------------------

class TestActiveAlerts:
    @pytest.mark.asyncio
    async def test_no_alerts(self, service_with_db):
        svc, db = service_with_db
        with patch.object(svc, "get_system_metrics",
                          AsyncMock(return_value=_base_metrics())):
            assert await svc.get_active_alerts() == []

    @pytest.mark.asyncio
    async def test_cpu_warning(self, service_with_db):
        svc, db = service_with_db
        with patch.object(svc, "get_system_metrics",
                          AsyncMock(return_value=_base_metrics(cpu=85))):
            alerts = await svc.get_active_alerts()
        assert alerts[0]["severity"] == "warning"
        assert "CPU" in alerts[0]["message"]
        assert alerts[0]["action_required"] is True

    @pytest.mark.asyncio
    async def test_cpu_critical(self, service_with_db):
        svc, db = service_with_db
        with patch.object(svc, "get_system_metrics",
                          AsyncMock(return_value=_base_metrics(cpu=95))):
            alerts = await svc.get_active_alerts()
        assert alerts[0]["severity"] == "critical"

    @pytest.mark.asyncio
    async def test_memory_warning_and_critical(self, service_with_db):
        svc, db = service_with_db
        with patch.object(svc, "get_system_metrics",
                          AsyncMock(return_value=_base_metrics(memory=85))):
            alerts = await svc.get_active_alerts()
        assert alerts[0]["severity"] == "warning"
        with patch.object(svc, "get_system_metrics",
                          AsyncMock(return_value=_base_metrics(memory=95))):
            alerts = await svc.get_active_alerts()
        assert alerts[0]["severity"] == "critical"

    @pytest.mark.asyncio
    async def test_queue_depth_alert(self, service_with_db):
        svc, db = service_with_db
        with patch.object(svc, "get_system_metrics",
                          AsyncMock(return_value=_base_metrics(
                              queue=hm_mod.ALERT_QUEUE_DEPTH_THRESHOLD + 1))):
            alerts = await svc.get_active_alerts()
        assert alerts[0]["severity"] == "warning"
        assert alerts[0]["action_required"] is False

    @pytest.mark.asyncio
    async def test_agent_error_rate_alert(self, service_with_db):
        svc, db = service_with_db
        agent = _make_agent(user_id="u1")
        db.query.return_value.filter.return_value.all.return_value = [agent]

        async def fake_health(agent_id):
            return {"metrics": {"error_rate": hm_mod.ALERT_ERROR_RATE_THRESHOLD + 0.2}}

        with patch.object(svc, "get_system_metrics",
                          AsyncMock(return_value=_base_metrics())), \
             patch.object(svc, "get_agent_health", side_effect=fake_health):
            alerts = await svc.get_active_alerts(user_id="u1")
        assert len(alerts) == 1
        assert alerts[0]["source_type"] == "agent"
        assert alerts[0]["source_id"] == "a1"

    @pytest.mark.asyncio
    async def test_agent_below_threshold_no_alert(self, service_with_db):
        svc, db = service_with_db
        db.query.return_value.filter.return_value.all.return_value = [
            _make_agent(user_id="u1")]

        async def fake_health(agent_id):
            return {"metrics": {"error_rate": 0.01}}

        with patch.object(svc, "get_system_metrics",
                          AsyncMock(return_value=_base_metrics())), \
             patch.object(svc, "get_agent_health", side_effect=fake_health):
            alerts = await svc.get_active_alerts(user_id="u1")
        assert alerts == []

    @pytest.mark.asyncio
    async def test_exception_returns_empty(self, service_with_db):
        svc, db = service_with_db
        with patch.object(svc, "get_system_metrics",
                          AsyncMock(side_effect=RuntimeError("boom"))):
            assert await svc.get_active_alerts() == []

    @pytest.mark.asyncio
    async def test_summary_counts_and_acknowledged_skip(self, service_with_db):
        svc, db = service_with_db
        fake_alerts = [
            {"severity": "critical", "acknowledged": False},
            {"severity": "warning", "acknowledged": False},
            {"severity": "warning", "acknowledged": True},
            {"severity": "info", "acknowledged": False},
        ]
        with patch.object(svc, "get_active_alerts",
                          AsyncMock(return_value=fake_alerts)):
            summary = await svc.get_active_alerts_summary()
        assert summary["critical"] == 1
        assert summary["warning"] == 1
        assert summary["info"] == 1

    @pytest.mark.asyncio
    async def test_summary_exception(self, service_with_db):
        svc, db = service_with_db
        with patch.object(svc, "get_active_alerts",
                          AsyncMock(side_effect=RuntimeError("boom"))):
            assert await svc.get_active_alerts_summary() == {
                "critical": 0, "warning": 0, "info": 0}


# ---------------------------------------------------------------------------
# acknowledge_alert
# ---------------------------------------------------------------------------

class TestAcknowledgeAlert:
    @pytest.mark.asyncio
    async def test_success(self, service_with_db):
        svc, db = service_with_db
        with patch("core.health_monitoring_service.ws_manager.broadcast",
                   AsyncMock()) as m:
            assert await svc.acknowledge_alert("aid", "u1") is True
        m.assert_awaited_once()
        assert m.await_args.args[0] == "system:alerts"

    @pytest.mark.asyncio
    async def test_broadcast_failure(self, service_with_db):
        svc, db = service_with_db
        with patch("core.health_monitoring_service.ws_manager.broadcast",
                   AsyncMock(side_effect=RuntimeError("ws down"))):
            assert await svc.acknowledge_alert("aid", "u1") is False


# ---------------------------------------------------------------------------
# get_health_history / _calculate_health_trend
# ---------------------------------------------------------------------------

class TestHealthHistory:
    @pytest.mark.asyncio
    async def test_agent_history_grouping_and_sort(self, service_with_db):
        svc, db = service_with_db
        day1 = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
        day2 = datetime(2026, 1, 2, 10, 0, tzinfo=timezone.utc)
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
            _make_exec(status="completed", started_at=day1),
            _make_exec(status="failed", started_at=day1),
            _make_exec(status="completed", started_at=day2),
            _make_exec(status="failed", started_at=day2),
        ]
        result = await svc.get_health_history("agent", "a1", days=30)
        assert len(result) == 2
        assert result[0]["timestamp"] == "2026-01-01T00:00:00Z"
        assert result[1]["timestamp"] == "2026-01-02T00:00:00Z"
        assert result[0]["health_score"] == 0.5
        assert result[0]["status"] == "degraded"
        assert result[0]["metrics"] == {"total_executions": 2,
                                        "completed": 1, "failed": 1}

    @pytest.mark.asyncio
    async def test_history_healthy_status(self, service_with_db):
        svc, db = service_with_db
        day = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
            _make_exec(status="completed", started_at=day),
            _make_exec(status="completed", started_at=day),
            _make_exec(status="completed", started_at=day),
        ]
        result = await svc.get_health_history("agent", "a1", days=30)
        assert result[0]["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_history_error_status(self, service_with_db):
        svc, db = service_with_db
        day = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
            _make_exec(status="failed", started_at=day),
        ]
        result = await svc.get_health_history("agent", "a1", days=30)
        assert result[0]["status"] == "error"

    @pytest.mark.asyncio
    async def test_non_agent_type_returns_empty(self, service_with_db):
        svc, db = service_with_db
        assert await svc.get_health_history("system", None, days=30) == []

    @pytest.mark.asyncio
    async def test_history_entity_id_none_for_agent(self, service_with_db):
        svc, db = service_with_db
        result = await svc.get_health_history("agent", None, days=30)
        assert result == []

    @pytest.mark.asyncio
    async def test_exception_returns_empty(self, service_with_db):
        svc, db = service_with_db
        db.query.side_effect = RuntimeError("db down")
        assert await svc.get_health_history("agent", "a1", days=30) == []

    @pytest.mark.asyncio
    async def test_trend_improving(self, service_with_db):
        svc, db = service_with_db
        with patch.object(svc, "get_health_history", AsyncMock(return_value=[
            {"health_score": 0.3}, {"health_score": 0.9}])):
            assert await svc._calculate_health_trend("a1") == "improving"

    @pytest.mark.asyncio
    async def test_trend_declining(self, service_with_db):
        svc, db = service_with_db
        with patch.object(svc, "get_health_history", AsyncMock(return_value=[
            {"health_score": 0.9}, {"health_score": 0.2}])):
            assert await svc._calculate_health_trend("a1") == "declining"

    @pytest.mark.asyncio
    async def test_trend_stable(self, service_with_db):
        svc, db = service_with_db
        with patch.object(svc, "get_health_history", AsyncMock(return_value=[
            {"health_score": 0.7}, {"health_score": 0.75}])):
            assert await svc._calculate_health_trend("a1") == "stable"

    @pytest.mark.asyncio
    async def test_trend_too_few_points(self, service_with_db):
        svc, db = service_with_db
        with patch.object(svc, "get_health_history", AsyncMock(return_value=[
            {"health_score": 0.7}])):
            assert await svc._calculate_health_trend("a1") == "stable"

    @pytest.mark.asyncio
    async def test_trend_exception(self, service_with_db):
        svc, db = service_with_db
        with patch.object(svc, "get_health_history",
                          AsyncMock(side_effect=RuntimeError("boom"))):
            assert await svc._calculate_health_trend("a1") == "stable"


# ---------------------------------------------------------------------------
# start_health_monitoring / factory
# ---------------------------------------------------------------------------

class TestMonitoringLoop:
    @pytest.mark.asyncio
    async def test_loop_with_agents_broadcasts(self, service_with_db):
        """Lines 699-700: agent loop with agents present."""
        svc, db = service_with_db
        agent = _make_agent(user_id="u1")
        db.query.return_value.filter.return_value.all.return_value = [agent]
        calls = {"sleep": 0}

        async def fake_sleep(seconds):
            calls["sleep"] += 1
            raise asyncio.CancelledError()

        with patch.object(svc, "get_agent_health",
                          AsyncMock(return_value={"agent_id": "a1"})) as agent_health, \
             patch.object(svc, "get_all_integrations_health",
                          AsyncMock(return_value=[{"integration_id": "i1"}])), \
             patch.object(svc, "get_active_alerts",
                          AsyncMock(return_value=[{"alert_id": "x"}])), \
             patch("core.health_monitoring_service.ws_manager.broadcast",
                   AsyncMock()) as broadcast, \
             patch("asyncio.sleep", new=fake_sleep):
            with pytest.raises(asyncio.CancelledError):
                await svc.start_health_monitoring("u1")
            agent_health.assert_awaited_once_with("a1")
            broadcast.assert_awaited_once()
            channel, payload = broadcast.await_args.args
            assert channel == "user:u1"
            assert payload["type"] == "health:update"
            assert payload["data"]["agents"] == [{"agent_id": "a1"}]
            assert payload["data"]["alerts"] == [{"alert_id": "x"}]

    @pytest.mark.asyncio
    async def test_loop_exception_swallowed(self, service_with_db):
        svc, db = service_with_db
        db.query.side_effect = RuntimeError("db dead")
        await svc.start_health_monitoring("u1")

    def test_factory(self):
        db = MagicMock()
        svc = get_health_monitoring_service(db)
        assert isinstance(svc, HealthMonitoringService)
        assert svc.db is db
