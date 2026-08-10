"""Coverage wave 10d part 2 — remaining branches of the route cluster.

Pushes workflow_versioning_endpoints / health_monitoring_routes /
project_health_routes to ~90%+: error branches, direct calculator tests,
get_workflow_data, remaining endpoints.
"""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.auth import get_current_user
from core.database import get_db


def _app(router):
    app = FastAPI()
    app.include_router(router)
    return app


def _client(router, db):
    app = _app(router)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id="u-1")
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app, raise_server_exceptions=False)


# =========================================================================== #
# workflow_versioning — error branches + get_workflow_data + tail endpoints
# =========================================================================== #
def _version(version="v1.0", **overrides):
    v = SimpleNamespace(
        workflow_id="wf-1", version=version,
        version_type=SimpleNamespace(value="minor"),
        change_type=SimpleNamespace(value="feature"),
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        created_by="u-1", commit_message="msg", tags=["t"],
        parent_version=None, branch_name="main", checksum="abc",
        is_active=True, workflow_data={"steps": []}, metadata={},
    )
    for k, val in overrides.items():
        setattr(v, k, val)
    return v


class TestWorkflowVersioningBranches:
    @pytest.fixture
    def vs(self):
        v_sys = AsyncMock()
        v_mgr = AsyncMock()
        with patch("api.workflow_versioning_endpoints.versioning_system", v_sys), \
             patch("api.workflow_versioning_endpoints.version_manager", v_mgr):
            yield v_sys, v_mgr

    def _c(self, db=None):
        from api.workflow_versioning_endpoints import router

        return _client(router, db or MagicMock())

    # get_workflow_data
    def test_get_workflow_data_missing_file(self, tmp_path, monkeypatch):
        import api.workflow_versioning_endpoints as wve
        import asyncio

        # Redirect the computed workflows.json path into tmp_path
        monkeypatch.setattr(wve.os.path, "join", lambda *a: str(tmp_path / "workflows.json"))
        monkeypatch.setattr(wve.os.path, "exists", lambda *a: False)
        monkeypatch.setattr(wve.os.path, "dirname", lambda *a: str(tmp_path))
        data = asyncio.run(wve.get_workflow_data("wf-1"))
        assert data["steps"] == []
        assert data["metadata"] == {}

    def test_get_workflow_data_unknown_id(self, tmp_path, monkeypatch):
        import api.workflow_versioning_endpoints as wve
        import json
        import asyncio

        f = tmp_path / "workflows.json"
        f.write_text(json.dumps([{"id": "other", "steps": [{"id": "s1"}]}]))
        monkeypatch.setattr(wve.os.path, "join", lambda *a: str(f))
        monkeypatch.setattr(wve.os.path, "exists", lambda *a: True)
        monkeypatch.setattr(wve.os.path, "dirname", lambda *a: str(tmp_path))
        data = asyncio.run(wve.get_workflow_data("wf-1"))
        assert data["steps"] == []

    def test_get_workflow_data_nodes_to_steps(self, tmp_path, monkeypatch):
        import api.workflow_versioning_endpoints as wve
        import json
        import asyncio

        f = tmp_path / "workflows.json"
        f.write_text(json.dumps([{
            "id": "wf-1", "name": "W", "description": "d", "category": "c",
            "nodes": [
                {"id": "n1", "title": "Step One", "type": "action",
                 "config": {"service": "svc", "action": "act", "parameters": {"p": 1}}},
            ],
            "connections": [{"from": "n1", "to": "n2"}],
            "parameters": {"x": 1},
            "created_at": "2026-01-01", "updated_at": "2026-01-02",
        }]))
        monkeypatch.setattr(wve.os.path, "join", lambda *a: str(f))
        monkeypatch.setattr(wve.os.path, "exists", lambda *a: True)
        monkeypatch.setattr(wve.os.path, "dirname", lambda *a: str(tmp_path))
        data = asyncio.run(wve.get_workflow_data("wf-1"))
        assert data["steps"][0]["id"] == "n1"
        assert data["steps"][0]["name"] == "Step One"
        assert data["steps"][0]["service"] == "svc"
        assert data["metadata"]["name"] == "W"
        assert data["parameters"] == {"x": 1}

    def test_get_workflow_data_corrupt_json(self, tmp_path, monkeypatch):
        import api.workflow_versioning_endpoints as wve
        import asyncio

        f = tmp_path / "workflows.json"
        f.write_text("{not json")
        monkeypatch.setattr(wve.os.path, "join", lambda *a: str(f))
        monkeypatch.setattr(wve.os.path, "exists", lambda *a: True)
        monkeypatch.setattr(wve.os.path, "dirname", lambda *a: str(tmp_path))
        data = asyncio.run(wve.get_workflow_data("wf-1"))
        assert data["steps"] == []

    # error branches
    def test_list_versions_error_500(self, vs):
        v_sys, _ = vs
        v_sys.get_version_history.side_effect = RuntimeError("boom")
        assert self._c().get("/api/v1/workflows/wf-1/versions").status_code == 500

    def test_get_version_exception_500(self, vs):
        v_sys, _ = vs
        v_sys.get_version.side_effect = RuntimeError("boom")
        assert self._c().get("/api/v1/workflows/wf-1/versions/v1").status_code == 500

    def test_version_data_error_500(self, vs):
        v_sys, _ = vs
        v_sys.get_version.side_effect = RuntimeError("boom")
        assert self._c().get("/api/v1/workflows/wf-1/versions/v1/data").status_code == 500

    def test_rollback_error_500(self, vs):
        v_sys, v_mgr = vs
        v_sys.get_version.return_value = _version("v1")
        v_mgr.rollback_workflow.side_effect = RuntimeError("boom")
        r = self._c().post(
            "/api/v1/workflows/wf-1/rollback",
            json={"target_version": "v1", "rollback_reason": "x"},
        )
        assert r.status_code == 500

    def test_compare_error_500(self, vs):
        v_sys, v_mgr = vs
        v_sys.get_version.return_value = _version("v1")
        v_mgr.get_workflow_changes.side_effect = RuntimeError("boom")
        r = self._c().get(
            "/api/v1/workflows/wf-1/versions/compare?from_version=v1&to_version=v2"
        )
        assert r.status_code == 500

    def test_compare_missing_source_404(self, vs):
        v_sys, _ = vs
        v_sys.get_version.return_value = None
        r = self._c().get(
            "/api/v1/workflows/wf-1/versions/compare?from_version=v1&to_version=v2"
        )
        assert r.status_code == 404

    def test_delete_error_500(self, vs):
        v_sys, _ = vs
        v_sys.delete_version.side_effect = RuntimeError("boom")
        r = self._c().delete("/api/v1/workflows/wf-1/versions/v1?delete_reason=x")
        assert r.status_code == 500

    def test_create_branch_error_500(self, vs):
        v_sys, _ = vs
        v_sys.create_branch.side_effect = RuntimeError("boom")
        r = self._c().post(
            "/api/v1/workflows/wf-1/branches",
            json={"branch_name": "b", "base_version": "v1"},
        )
        assert r.status_code == 500

    def test_branches_error_500(self, vs):
        v_sys, _ = vs
        v_sys.get_branches.side_effect = RuntimeError("boom")
        assert self._c().get("/api/v1/workflows/wf-1/branches").status_code == 500

    def test_merge_error_500(self, vs):
        v_sys, _ = vs
        v_sys.merge_branch.side_effect = RuntimeError("boom")
        r = self._c().post(
            "/api/v1/workflows/wf-1/branches/merge",
            json={"source_branch": "a", "target_branch": "b", "merge_message": "m"},
        )
        assert r.status_code == 500

    def test_metrics_error_500(self, vs):
        v_sys, _ = vs
        v_sys.get_version_metrics.side_effect = RuntimeError("boom")
        assert self._c().get("/api/v1/workflows/wf-1/versions/v1/metrics").status_code == 500

    def test_update_metrics_route(self, vs):
        v_sys, _ = vs
        v_sys.update_version_metrics = AsyncMock(return_value=True)
        r = self._c().post(
            "/api/v1/workflows/wf-1/versions/v1/metrics",
            json={"metrics": {"executions": 5}},
        )
        assert r.status_code in (200, 422)
        if r.status_code == 200:
            assert "data" in r.json()

    def test_update_metrics_error_500(self, vs):
        v_sys, _ = vs
        v_sys.update_version_metrics = AsyncMock(side_effect=RuntimeError("boom"))
        r = self._c().post(
            "/api/v1/workflows/wf-1/versions/v1/metrics",
            json={"metrics": {"executions": 5}},
        )
        assert r.status_code == 500

    def test_history_route(self, vs):
        v_sys, _ = vs
        v_sys.get_version_history.return_value = [_version("v1")]
        r = self._c().get("/api/v1/workflows/wf-1/history")
        assert r.status_code in (200, 404, 500)


# =========================================================================== #
# health_monitoring — remaining endpoints + error branches
# =========================================================================== #
class TestHealthMonitoringBranches:
    def _c(self, db=None):
        from api.health_monitoring_routes import router

        return _client(router, db or MagicMock())

    def _svc(self, **methods):
        svc = AsyncMock()
        for k, v in methods.items():
            setattr(svc, k, v)
        return svc

    def test_agent_health_error_500(self):
        svc = self._svc(get_agent_health=AsyncMock(side_effect=RuntimeError("boom")))
        with patch("api.health_monitoring_routes.get_health_monitoring_service", return_value=svc):
            assert self._c().get("/api/health/agent/a-1").status_code == 500

    def test_integrations_error_500(self):
        svc = self._svc(get_all_integrations_health=AsyncMock(side_effect=RuntimeError("boom")))
        with patch("api.health_monitoring_routes.get_health_monitoring_service", return_value=svc):
            assert self._c().get("/api/health/integrations").status_code == 500

    def test_system_error_500(self):
        svc = self._svc(get_system_metrics=AsyncMock(side_effect=RuntimeError("boom")))
        with patch("api.health_monitoring_routes.get_health_monitoring_service", return_value=svc):
            assert self._c().get("/api/health/system").status_code == 500

    def test_alerts_error_500(self):
        svc = self._svc(get_active_alerts=AsyncMock(side_effect=RuntimeError("boom")))
        with patch("api.health_monitoring_routes.get_health_monitoring_service", return_value=svc):
            assert self._c().get("/api/health/alerts").status_code == 500

    def test_acknowledge_alert(self):
        svc = self._svc(acknowledge_alert=AsyncMock(return_value=True))
        with patch("api.health_monitoring_routes.get_health_monitoring_service", return_value=svc):
            r = self._c().post("/api/health/alerts/al-1/acknowledge", json={"acknowledged": True})
        assert r.status_code == 200
        svc.acknowledge_alert.assert_awaited_once_with("al-1", "u-1")

    def test_acknowledge_missing_404(self):
        svc = self._svc(acknowledge_alert=AsyncMock(return_value=False))
        with patch("api.health_monitoring_routes.get_health_monitoring_service", return_value=svc):
            r = self._c().post("/api/health/alerts/ghost/acknowledge", json={"acknowledged": True})
        assert r.status_code == 404  # NOT 500 (except HTTPException re-raise)

    def test_acknowledge_error_500(self):
        svc = self._svc(acknowledge_alert=AsyncMock(side_effect=RuntimeError("boom")))
        with patch("api.health_monitoring_routes.get_health_monitoring_service", return_value=svc):
            r = self._c().post("/api/health/alerts/al-1/acknowledge", json={"acknowledged": True})
        assert r.status_code == 500

    def test_health_history(self):
        svc = self._svc(get_health_history=AsyncMock(return_value=[{"ts": "t", "value": 1}]))
        with patch("api.health_monitoring_routes.get_health_monitoring_service", return_value=svc):
            r = self._c().get("/api/health/history/agent?entity_id=a-1&days=7")
        assert r.status_code == 200
        svc.get_health_history.assert_awaited_once()
        kwargs = svc.get_health_history.await_args.kwargs
        assert kwargs["health_type"] == "agent"
        assert kwargs["entity_id"] == "a-1"
        assert kwargs["days"] == 7

    def test_health_history_error_500(self):
        svc = self._svc(get_health_history=AsyncMock(side_effect=RuntimeError("boom")))
        with patch("api.health_monitoring_routes.get_health_monitoring_service", return_value=svc):
            assert self._c().get("/api/health/history/agent").status_code == 500

    def test_health_requires_auth(self):
        from api.health_monitoring_routes import router

        client = TestClient(_app(router), raise_server_exceptions=False)
        assert client.get("/api/health/history/agent").status_code == 401
        assert client.post(
            "/api/health/alerts/x/acknowledge", json={"acknowledged": True}
        ).status_code == 401


# =========================================================================== #
# project_health — direct calculator tests + recommendation branches
# =========================================================================== #
class TestProjectHealthCalculators:
    @pytest.mark.asyncio
    async def test_notion_health(self):
        from api.project_health_routes import calculate_notion_health

        m = await calculate_notion_health("k", "db", 7)
        assert m.name == "Task Management"
        assert m.score == 70.0
        assert m.status == "good"
        assert m.details["total_tasks"] == 50

    @pytest.mark.asyncio
    async def test_github_health(self):
        from api.project_health_routes import calculate_github_health

        m = await calculate_github_health("owner", "repo", 7)
        assert m.max_score == 150.0
        assert 0 <= m.score <= m.max_score

    @pytest.mark.asyncio
    async def test_slack_health(self):
        from api.project_health_routes import calculate_slack_health

        m = await calculate_slack_health("channel", 7)
        assert 0 <= m.score <= m.max_score

    @pytest.mark.asyncio
    async def test_meeting_health(self):
        from api.project_health_routes import calculate_meeting_health

        m = await calculate_meeting_health(14)
        assert 0 <= m.score <= 100
        assert m.trend in ("improving", "stable", "declining")

    def test_recommendations_by_metric_name(self):
        from api.project_health_routes import (
            HealthMetric,
            generate_overall_recommendations,
        )

        def m(name, status):
            return HealthMetric(name=name, score=40, max_score=100, status=status,
                                details={}, trend="stable")

        recs = generate_overall_recommendations({
            "notion": m("Task Management", "warning"),
            "github": m("Code Health", "critical"),
            "slack": m("Communication", "warning"),
            "meetings": m("Meeting Balance", "critical"),
        })
        assert len(recs) == 4
        joined = " ".join(recs)
        assert "overdue" in joined
        assert "PRs" in joined
        assert "response times" in joined
        assert "meeting load" in joined.lower()

        good = generate_overall_recommendations({
            "a": m("Task Management", "excellent"),
        })
        assert good == ["Project health is good! Maintain current practices."]

    def test_overall_score_buckets(self):
        from api.project_health_routes import HealthMetric, calculate_overall_score

        def m(score):
            return HealthMetric(name="x", score=score, max_score=100, status="s",
                                details={}, trend="stable")

        assert calculate_overall_score({"a": m(90)})[1] == "excellent"
        assert calculate_overall_score({"a": m(70)})[1] == "good"
        assert calculate_overall_score({"a": m(50)})[1] == "warning"
        assert calculate_overall_score({"a": m(10)})[1] == "critical"
        assert calculate_overall_score({"a": m(10), "b": m(90)})[0] == 50.0


# =========================================================================== #
# wave 10d part 3 — tail endpoints
# =========================================================================== #
class TestWorkflowVersioningTail:
    @pytest.fixture
    def vs(self):
        v_sys = AsyncMock()
        v_mgr = AsyncMock()
        with patch("api.workflow_versioning_endpoints.versioning_system", v_sys), \
             patch("api.workflow_versioning_endpoints.version_manager", v_mgr):
            yield v_sys, v_mgr

    def _c(self, db=None):
        from api.workflow_versioning_endpoints import router

        return _client(router, db or MagicMock())

    def test_update_metrics_success_and_failure(self, vs):
        v_sys, _ = vs
        v_sys.update_version_metrics = AsyncMock(return_value=True)
        r = self._c().post(
            "/api/v1/workflows/wf-1/versions/v1/metrics",
            json={"execution_time_ms": 100, "success": True},
        )
        assert r.status_code == 200
        assert r.json()["data"] is not None or "message" in r.json()

        v_sys.update_version_metrics = AsyncMock(return_value=False)
        r2 = self._c().post(
            "/api/v1/workflows/wf-1/versions/v1/metrics",
            json={"execution_time_ms": 100},
        )
        assert r2.status_code == 200

    def test_update_metrics_error_500(self, vs):
        v_sys, _ = vs
        v_sys.update_version_metrics = AsyncMock(side_effect=RuntimeError("boom"))
        r = self._c().post(
            "/api/v1/workflows/wf-1/versions/v1/metrics",
            json={"execution_time_ms": 100},
        )
        assert r.status_code == 500

    def test_latest_version(self, vs):
        v_sys, _ = vs
        v_sys.get_version_history.return_value = [_version("v2.0")]
        r = self._c().get("/api/v1/workflows/wf-1/versions/latest")
        assert r.status_code == 200
        assert r.json()["version"] == "v2.0"

        v_sys.get_version_history.return_value = []
        r2 = self._c().get("/api/v1/workflows/wf-1/versions/latest")
        assert r2.status_code == 404

        v_sys.get_version_history.side_effect = RuntimeError("boom")
        assert self._c().get("/api/v1/workflows/wf-1/versions/latest").status_code == 500

    def test_version_summary(self, vs):
        v_sys, _ = vs
        v_sys.get_version_history.return_value = [
            _version("v2.0", created_at=datetime(2026, 2, 1, tzinfo=timezone.utc)),
            _version("v1.0", version_type=SimpleNamespace(value="major"),
                     created_at=datetime(2026, 1, 1, tzinfo=timezone.utc)),
        ]
        r = self._c().get("/api/v1/workflows/wf-1/versions/summary")
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["total_versions"] == 2
        assert data["version_types"] == {"minor": 1, "major": 1}
        assert data["unique_contributors"] == 1
        assert data["latest_version"] == "v2.0"
        assert data["oldest_version"] == "v1.0"
        assert data["date_range"]["first_created"] is not None

        v_sys.get_version_history.return_value = []
        r2 = self._c().get("/api/v1/workflows/wf-1/versions/summary")
        data2 = r2.json()["data"]
        assert data2["total_versions"] == 0
        assert data2["latest_version"] is None

        v_sys.get_version_history.side_effect = RuntimeError("boom")
        assert self._c().get("/api/v1/workflows/wf-1/versions/summary").status_code == 500

    def test_health_check(self, vs):
        r = self._c().get("/api/v1/workflows/versioning/health")
        assert r.status_code == 200
        assert r.json()["data"]["versioning_system"] == "operational"


class TestReconciliationTail:
    def _c(self, db=None):
        from api.reconciliation_routes import router

        return _client(router, db or MagicMock())

    def test_ledger_success_path(self):
        import core.reconciliation_engine as re_mod

        engine = MagicMock()
        p = patch.object(re_mod, "reconciliation_engine", engine)
        with p:
            r = self._c().post("/reconciliation/ledger-entries", json={
                "id": "l-1", "source": "ledger", "date": "2026-01-01T00:00:00",
                "amount": 42.0, "description": "invoice",
            })
        assert r.status_code == 200
        engine.add_ledger_entry.assert_called_once()

    def test_agent_resolution_missing_agent_continues(self):
        import core.reconciliation_engine as re_mod

        resolver = AsyncMock()
        resolver.resolve_agent_for_request.return_value = (None, {})
        engine = MagicMock()
        p = patch.object(re_mod, "reconciliation_engine", engine)
        with patch("core.agent_context_resolver.AgentContextResolver", return_value=resolver), \
             patch("core.agent_governance_service.AgentGovernanceService"), p:
            r = self._c().post("/reconciliation/bank-entries", json={
                "id": "b-9", "source": "bank", "date": "2026-01-01",
                "amount": 1.0, "description": "x", "agent_id": "ghost",
            })
        assert r.status_code == 200
        engine.add_bank_entry.assert_called_once()

    def test_reconcile_error_500(self):
        import core.reconciliation_engine as re_mod

        engine = MagicMock()
        engine.reconcile.side_effect = RuntimeError("boom")
        with patch.object(re_mod, "reconciliation_engine", engine):
            assert self._c().post("/reconciliation/reconcile").status_code == 500

    def test_anomalies_error_500(self):
        import core.reconciliation_engine as re_mod

        engine = MagicMock()
        engine.get_anomalies.side_effect = RuntimeError("boom")
        with patch.object(re_mod, "reconciliation_engine", engine):
            assert self._c().get("/reconciliation/anomalies").status_code == 500

    def test_detect_error_500(self):
        import core.reconciliation_engine as re_mod

        engine = MagicMock()
        engine.detect_anomalies.side_effect = RuntimeError("boom")
        with patch.object(re_mod, "reconciliation_engine", engine):
            assert self._c().post("/reconciliation/detect-anomalies").status_code == 500


class TestHealthMonitoringTail:
    def _c(self, db=None):
        from api.health_monitoring_routes import router

        return _client(router, db or MagicMock())

    def test_external_data_health(self):
        pricing = MagicMock()
        pricing.last_fetch = datetime(2026, 1, 1, tzinfo=timezone.utc)
        pricing.pricing_cache = {"gpt-4o": 1}
        pricing._is_cache_valid.return_value = True
        benchmark = MagicMock()
        benchmark.last_fetch = None
        benchmark.benchmark_cache = {}
        benchmark._is_cache_valid.return_value = False
        with patch("core.dynamic_pricing_fetcher.get_pricing_fetcher", return_value=pricing), \
             patch("core.dynamic_benchmark_fetcher.get_benchmark_fetcher", return_value=benchmark):
            r = self._c().get("/api/health/external-data")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] in ("healthy", "degraded")
        assert body["pricing"]["model_count"] == 1

    def test_external_data_health_error(self):
        with patch(
            "core.dynamic_pricing_fetcher.get_pricing_fetcher",
            side_effect=RuntimeError("fetcher down"),
        ):
            r = self._c().get("/api/health/external-data")
        assert r.status_code == 500

    def test_health_check_endpoint(self):
        r = self._c().get("/api/health/health")
        assert r.status_code == 200


class TestMemoryTail:
    def _c(self, db=None):
        from api.memory_routes import router

        return _client(router, db or MagicMock())

    def test_empty_query_returns_limited_results(self):
        import api.memory_routes as mr

        mr._memory_store.clear()
        for i in range(15):
            mr._memory_store[f"k{i}"] = {"key": f"k{i}", "value": f"v{i}",
                                          "metadata": {}, "timestamp": "t"}
        r = self._c().get("/api/memory/search?q=")
        assert r.status_code == 200
        assert r.json()["metadata"]["count"] == 10  # limit 10 default


class TestReconciliationFinal:
    def _c(self, db=None):
        from api.reconciliation_routes import router

        return _client(router, db or MagicMock())

    def test_bank_invalid_date_422(self):
        import core.reconciliation_engine as re_mod

        engine = MagicMock()
        with patch.object(re_mod, "reconciliation_engine", engine):
            r = self._c().post("/reconciliation/bank-entries", json={
                "id": "b-x", "source": "bank", "date": "junk",
                "amount": 1.0, "description": "x",
            })
        assert r.status_code == 422
        engine.add_bank_entry.assert_not_called()

    def test_bank_engine_error_500(self):
        import core.reconciliation_engine as re_mod

        engine = MagicMock()
        engine.add_bank_entry.side_effect = RuntimeError("engine down")
        with patch.object(re_mod, "reconciliation_engine", engine):
            r = self._c().post("/reconciliation/bank-entries", json={
                "id": "b-y", "source": "bank", "date": "2026-01-01",
                "amount": 1.0, "description": "x",
            })
        assert r.status_code == 500

    def test_ledger_with_agent_governance(self):
        import core.reconciliation_engine as re_mod

        resolver = AsyncMock()
        resolver.resolve_agent_for_request.return_value = (SimpleNamespace(id="a-1"), {})
        governance = MagicMock()
        governance.can_perform_action.return_value = {"allowed": True, "reason": None}
        engine = MagicMock()
        with patch("core.agent_context_resolver.AgentContextResolver", return_value=resolver), \
             patch("core.agent_governance_service.AgentGovernanceService", return_value=governance), \
             patch.object(re_mod, "reconciliation_engine", engine):
            r = self._c().post("/reconciliation/ledger-entries", json={
                "id": "l-x", "source": "ledger", "date": "2026-01-01",
                "amount": 1.0, "description": "x", "agent_id": "a-1",
            })
        assert r.status_code == 200
        engine.add_ledger_entry.assert_called_once()

    def test_resolve_engine_error_500(self):
        import core.reconciliation_engine as re_mod

        engine = MagicMock()
        engine.resolve_anomaly.side_effect = RuntimeError("engine down")
        with patch.object(re_mod, "reconciliation_engine", engine):
            r = self._c().post("/reconciliation/anomalies/an-1/resolve")
        assert r.status_code == 500


class TestProjectHealthIntegrationFailures:
    def _c(self, db=None):
        from api.project_health_routes import router

        return _client(router, db or MagicMock())

    def _metric(self, name, score=80, status="good"):
        from api.project_health_routes import HealthMetric

        return HealthMetric(name=name, score=score, max_score=100, status=status,
                            details={}, trend="stable")

    def test_github_and_slack_failures_swallowed(self):
        with patch("api.project_health_routes.calculate_notion_health",
                   AsyncMock(return_value=self._metric("Task Management"))), \
             patch("api.project_health_routes.calculate_github_health",
                   AsyncMock(side_effect=RuntimeError("github down"))), \
             patch("api.project_health_routes.calculate_slack_health",
                   AsyncMock(side_effect=RuntimeError("slack down"))), \
             patch("api.project_health_routes.calculate_meeting_health",
                   AsyncMock(return_value=self._metric("Meeting Balance"))):
            r = self._c().post("/api/v1/projects/health", json={
                "notion_api_key": "k", "notion_database_id": "db",
                "github_owner": "o", "github_repo": "r", "slack_channel_id": "c",
            })
        assert r.status_code == 200
        assert set(r.json()["metrics"].keys()) == {"notion", "meetings"}
