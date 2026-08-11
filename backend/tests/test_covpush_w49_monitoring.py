"""Coverage wave 49 — core/monitoring.py (46% → 90%+).

Structlog processors + configuration, RequestContext binding/restore, all
metric-tracker helpers (http/agent/skill/db/deployment/smoke/rollback/canary/
prometheus-query), deployment + smoke context managers (success/failure),
metrics-server init (success/OSError).
"""
import time
from unittest.mock import Mock, patch

import pytest

import core.monitoring as mon


class TestStructlogHelpers:
    def test_add_log_level(self):
        event = {}
        result = mon.add_log_level(Mock(), "info", event)
        assert result["level"] == "INFO"

    def test_add_logger_name(self):
        logger = Mock()
        logger.name = "my.logger"
        assert mon.add_logger_name(logger, "info", {})["logger"] == "my.logger"

    def test_configure_structlog(self):
        with patch("structlog.configure") as cfg, \
             patch("logging.basicConfig") as bc:
            mon.configure_structlog()
        cfg.assert_called_once()
        bc.assert_called_once()

    def test_get_logger(self):
        with patch("structlog.get_logger", return_value="lg") as gl:
            assert mon.get_logger("name") == "lg"
            gl.assert_called_once_with("name")


class TestRequestContext:
    def test_binds_and_restores(self):
        base = Mock()
        base._context = {"k": "v"}
        bound = Mock()
        bound._context = {"k": "v", "req": "1"}
        base.bind.return_value = bound
        with patch("structlog.get_logger", return_value=base) as gl:
            with mon.RequestContext(req="1") as log:
                assert log is bound
                base.bind.assert_called_once_with(req="1")
        # restored
        assert base._context == {"k": "v"}


class TestMetricTrackers:
    def test_track_http_request(self):
        with patch.object(mon, "http_requests_total") as total, \
             patch.object(mon, "http_request_duration_seconds") as dur:
            mon.track_http_request("POST", "/api/x", 201, 0.5)
        total.labels.return_value.inc.assert_called_once()
        dur.labels.return_value.observe.assert_called_once_with(0.5)

    def test_track_agent_execution(self):
        with patch.object(mon, "agent_executions_total") as total, \
             patch.object(mon, "agent_execution_duration_seconds") as dur:
            mon.track_agent_execution("a1", "success", 1.2)
        total.labels.return_value.inc.assert_called_once()
        dur.labels.return_value.observe.assert_called_once_with(1.2)

    def test_track_skill_execution(self):
        with patch.object(mon, "skill_executions_total") as total, \
             patch.object(mon, "skill_execution_duration_seconds") as dur:
            mon.track_skill_execution("s1", "failure", 0.3)
        total.labels.return_value.inc.assert_called_once()
        dur.labels.return_value.observe.assert_called_once_with(0.3)

    def test_track_db_query(self):
        with patch.object(mon, "db_query_duration_seconds") as dur:
            mon.track_db_query("select", 0.01)
        dur.labels.return_value.observe.assert_called_once_with(0.01)

    def test_set_active_agents(self):
        with patch.object(mon, "active_agents") as gauge:
            mon.set_active_agents(7)
        gauge.set.assert_called_once_with(7)

    def test_set_db_connections(self):
        with patch.object(mon, "db_connections_active") as act, \
             patch.object(mon, "db_connections_idle") as idle:
            mon.set_db_connections(3, 5)
        act.set.assert_called_once_with(3)
        idle.set.assert_called_once_with(5)


class TestDeploymentMetrics:
    def test_track_deployment_success(self):
        with patch.object(mon, "deployment_total") as total, \
             patch.object(mon, "deployment_duration_seconds") as dur:
            with mon.track_deployment("staging"):
                pass
        total.labels.assert_called_once_with(environment="staging", status="success")
        dur.labels.return_value.observe.assert_called_once()

    def test_track_deployment_failure(self):
        with patch.object(mon, "deployment_total") as total, \
             patch.object(mon, "deployment_duration_seconds") as dur:
            with pytest.raises(RuntimeError):
                with mon.track_deployment("prod"):
                    raise RuntimeError("boom")
        total.labels.assert_called_once_with(environment="prod", status="failed")

    def test_track_smoke_test_success_and_failure(self):
        with patch.object(mon, "smoke_test_total") as total, \
             patch.object(mon, "smoke_test_duration_seconds") as dur:
            with mon.track_smoke_test("staging"):
                pass
            total.labels.assert_called_once_with(environment="staging", result="passed")
            with pytest.raises(RuntimeError):
                with mon.track_smoke_test("prod"):
                    raise RuntimeError("boom")
            total.labels.assert_called_with(environment="prod", result="failed")

    def test_record_rollback(self):
        with patch.object(mon, "deployment_rollback_total") as total:
            mon.record_rollback("prod", "smoke_test_failed")
        total.labels.assert_called_once_with(environment="prod", reason="smoke_test_failed")
        total.labels.return_value.inc.assert_called_once()

    def test_update_canary_traffic(self):
        with patch.object(mon, "canary_traffic_percentage") as gauge:
            mon.update_canary_traffic("prod", "sha1", 25)
        gauge.labels.assert_called_once_with(environment="prod", deployment_id="sha1")
        gauge.labels.return_value.set.assert_called_once_with(25)

    def test_record_prometheus_query(self):
        with patch.object(mon, "prometheus_query_total") as total, \
             patch.object(mon, "prometheus_query_duration_seconds") as dur:
            mon.record_prometheus_query("deploy-staging", True, 0.4)
            mon.record_prometheus_query("deploy-staging", False, 0.6)
        total.labels.assert_called_with(workflow="deploy-staging", result="failed")
        assert dur.labels.return_value.observe.call_count == 2


class TestMetricsServer:
    def test_initialize_metrics_success(self):
        with patch("prometheus_client.start_http_server") as start, \
             patch.object(mon, "get_logger") as gl:
            mon.initialize_metrics()
        start.assert_called_once_with(8001)
        gl.return_value.info.assert_called_once()

    def test_initialize_metrics_oserror(self):
        with patch("prometheus_client.start_http_server",
                   side_effect=OSError("in use")) as start, \
             patch.object(mon, "get_logger") as gl:
            mon.initialize_metrics()
        start.assert_called_once_with(8001)
        gl.return_value.warning.assert_called_once()
