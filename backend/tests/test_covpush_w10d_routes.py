"""Coverage wave 10d — never-covered api/ route cluster (TDD).

Modules: workflow_versioning_endpoints, meeting_routes, memory_routes,
reconciliation_routes, health_monitoring_routes, project_health_routes.

Real-bug probes (RED first):
- WE1: ``memory_routes.get_memory_stats`` except-path leaks ``str(e)`` into the
  response payload (info leak); should be generic + logged.
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
# workflow_versioning_endpoints
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


def _branch(**overrides):
    b = SimpleNamespace(
        branch_name="feature/x", workflow_id="wf-1", base_version="v1.0",
        current_version="v1.1", created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        created_by="u-1", is_protected=False, merge_strategy="merge_commit",
    )
    for k, val in overrides.items():
        setattr(b, k, val)
    return b


class TestWorkflowVersioning:
    @pytest.fixture
    def vs(self):
        from api.workflow_versioning_endpoints import (
            versioning_system,
            version_manager,
        )

        v_sys = AsyncMock()
        v_mgr = AsyncMock()
        with patch("api.workflow_versioning_endpoints.versioning_system", v_sys), \
             patch("api.workflow_versioning_endpoints.version_manager", v_mgr):
            yield v_sys, v_mgr

    def _c(self, db):
        from api.workflow_versioning_endpoints import router

        return _client(router, db)

    def test_create_version(self, vs):
        v_sys, v_mgr = vs
        v_mgr.create_workflow_version.return_value = {"version": "v1.1"}
        v_sys.get_version.return_value = _version("v1.1")
        with patch(
            "api.workflow_versioning_endpoints.get_workflow_data",
            AsyncMock(return_value={"steps": [], "parameters": {}}),
        ):
            r = self._c(MagicMock()).post(
                "/api/v1/workflows/wf-1/versions",
                json={"version_type": "minor", "commit_message": "add feature"},
            )
        assert r.status_code == 200
        body = r.json()
        assert body["version"] == "v1.1"
        assert body["workflow_id"] == "wf-1"
        assert body["commit_message"] == "msg"
        v_mgr.create_workflow_version.assert_awaited_once()
        kwargs = v_mgr.create_workflow_version.await_args.kwargs
        assert kwargs["workflow_id"] == "wf-1"
        assert kwargs["user_id"] == "u-1"
        assert kwargs["version_type"] == "minor"

    def test_create_version_missing_after_create_500(self, vs):
        v_sys, v_mgr = vs
        v_mgr.create_workflow_version.return_value = {"version": "v1.1"}
        v_sys.get_version.return_value = None
        with patch(
            "api.workflow_versioning_endpoints.get_workflow_data",
            AsyncMock(return_value={"steps": []}),
        ):
            r = self._c(MagicMock()).post(
                "/api/v1/workflows/wf-1/versions",
                json={"version_type": "patch", "commit_message": "fix"},
            )
        assert r.status_code == 500

    def test_create_version_invalid_type_422(self, vs):
        r = self._c(MagicMock()).post(
            "/api/v1/workflows/wf-1/versions",
            json={"version_type": "weird", "commit_message": "x"},
        )
        assert r.status_code == 422

    def test_list_versions(self, vs):
        v_sys, _ = vs
        v_sys.get_version_history.return_value = [_version("v1.0"), _version("v0.9")]
        r = self._c(MagicMock()).get("/api/v1/workflows/wf-1/versions?branch_name=main&limit=5")
        assert r.status_code == 200
        rows = r.json()
        assert len(rows) == 2
        assert rows[0]["version"] == "v1.0"
        assert rows[0]["version_type"] == "minor"

    def test_list_versions_limit_bounds(self, vs):
        r = self._c(MagicMock()).get("/api/v1/workflows/wf-1/versions?limit=0")
        assert r.status_code == 422
        r2 = self._c(MagicMock()).get("/api/v1/workflows/wf-1/versions?limit=999")
        assert r2.status_code == 422

    def test_get_version_found_and_missing(self, vs):
        v_sys, _ = vs
        v_sys.get_version.return_value = _version("v1.0")
        r = self._c(MagicMock()).get("/api/v1/workflows/wf-1/versions/v1.0")
        assert r.status_code == 200
        assert r.json()["checksum"] == "abc"

        v_sys.get_version.return_value = None
        r2 = self._c(MagicMock()).get("/api/v1/workflows/wf-1/versions/v9")
        assert r2.status_code == 404

    def test_get_version_data(self, vs):
        v_sys, _ = vs
        v_sys.get_version.return_value = _version("v1.0")
        r = self._c(MagicMock()).get("/api/v1/workflows/wf-1/versions/v1.0/data")
        assert r.status_code == 200
        body = r.json()
        assert body["data"]["version"] == "v1.0"
        assert body["data"]["workflow_data"] == {"steps": []}

        v_sys.get_version.return_value = None
        r2 = self._c(MagicMock()).get("/api/v1/workflows/wf-1/versions/v9/data")
        assert r2.status_code == 404

    def test_rollback_success_and_missing_target(self, vs):
        v_sys, v_mgr = vs
        v_sys.get_version.return_value = _version("v1.0")
        v_mgr.rollback_workflow.return_value = {
            "rollback_version": "v1.1", "target_version": "v1.0",
            "created_at": "2026-01-02T00:00:00Z",
        }
        r = self._c(MagicMock()).post(
            "/api/v1/workflows/wf-1/rollback",
            json={"target_version": "v1.0", "rollback_reason": "bad deploy"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["data"]["rollback_version"] == "v1.1"
        v_mgr.rollback_workflow.assert_awaited_once()

        v_sys.get_version.return_value = None
        r2 = self._c(MagicMock()).post(
            "/api/v1/workflows/wf-1/rollback",
            json={"target_version": "v9", "rollback_reason": "x"},
        )
        assert r2.status_code == 404

    def test_compare_versions(self, vs):
        v_sys, v_mgr = vs
        v_sys.get_version.return_value = _version("v1.0")
        v_mgr.get_workflow_changes.return_value = {
            "from_version": "v1.0", "to_version": "v1.1", "impact_level": "medium",
            "added_steps_count": 1, "removed_steps_count": 0, "modified_steps_count": 2,
            "structural_changes": ["added step"], "dependency_changes": [],
            "parametric_changes": {}, "metadata_changes": {},
        }
        r = self._c(MagicMock()).get(
            "/api/v1/workflows/wf-1/versions/compare?from_version=v1.0&to_version=v1.1"
        )
        assert r.status_code == 200
        body = r.json()
        assert body["impact_level"] == "medium"
        assert body["added_steps_count"] == 1

    def test_delete_version(self, vs):
        v_sys, _ = vs
        v_sys.delete_version.return_value = True
        r = self._c(MagicMock()).delete(
            "/api/v1/workflows/wf-1/versions/v1.0?delete_reason=cleanup"
        )
        assert r.status_code == 200
        v_sys.delete_version.assert_awaited_once()
        assert v_sys.delete_version.await_args.kwargs["delete_reason"] == "cleanup"

        v_sys.delete_version.return_value = False
        r2 = self._c(MagicMock()).delete(
            "/api/v1/workflows/wf-1/versions/v1.0?delete_reason=cleanup"
        )
        assert r2.status_code == 422  # router.validation_error -> 422

    def test_create_and_list_branches(self, vs):
        v_sys, _ = vs
        v_sys.create_branch.return_value = _branch()
        r = self._c(MagicMock()).post(
            "/api/v1/workflows/wf-1/branches",
            json={"branch_name": "feature/x", "base_version": "v1.0"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["branch_name"] == "feature/x"
        assert body["merge_strategy"] == "merge_commit"

        v_sys.get_branches.return_value = [_branch(), _branch(branch_name="main")]
        r2 = self._c(MagicMock()).get("/api/v1/workflows/wf-1/branches")
        assert r2.status_code == 200
        assert [b["branch_name"] for b in r2.json()] == ["feature/x", "main"]

    def test_merge_branch(self, vs):
        v_sys, _ = vs
        v_sys.merge_branch.return_value = _version("v2.0")
        r = self._c(MagicMock()).post(
            "/api/v1/workflows/wf-1/branches/merge",
            json={"source_branch": "feature/x", "target_branch": "main", "merge_message": "merge"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["data"]["merged_version"] == "v2.0"
        v_sys.merge_branch.assert_awaited_once()
        kwargs = v_sys.merge_branch.await_args.kwargs
        assert kwargs["source_branch"] == "feature/x"
        assert kwargs["merge_by"] == "u-1"

    def test_metrics(self, vs):
        v_sys, _ = vs
        v_sys.get_version_metrics.return_value = {"executions": 10}
        r = self._c(MagicMock()).get("/api/v1/workflows/wf-1/versions/v1.0/metrics")
        assert r.status_code == 200
        assert r.json()["data"]["metrics"] == {"executions": 10}

        v_sys.get_version_metrics.return_value = None
        r2 = self._c(MagicMock()).get("/api/v1/workflows/wf-1/versions/v1.0/metrics")
        assert r2.status_code == 200
        assert r2.json()["data"]["metrics"] == {}

    def test_requires_auth(self):
        from api.workflow_versioning_endpoints import router

        app = _app(router)
        client = TestClient(app, raise_server_exceptions=False)
        r = client.get("/api/v1/workflows/wf-1/versions")
        assert r.status_code == 401


# =========================================================================== #
# meeting_routes (real DB CRUD)
# =========================================================================== #
class TestMeetingRoutes:
    @pytest.fixture
    def db(self, worker_database):
        from core.models import MeetingAttendanceStatus

        session = worker_database()
        session.query(MeetingAttendanceStatus).delete()
        session.commit()
        yield session
        session.close()

    def _c(self, db):
        from api.meeting_routes import router

        return _client(router, db)

    def test_crud_cycle(self, db):
        client = self._c(db)
        # create
        r = client.post("/api/meetings/attendance", json={
            "task_id": "task-1", "platform": "zoom", "meeting_identifier": "m-1",
            "current_status_message": "joined",
        })
        assert r.status_code == 201
        body = r.json()
        assert body["task_id"] == "task-1"
        assert body["user_id"] == "u-1"

        # duplicate create -> conflict
        r2 = client.post("/api/meetings/attendance", json={"task_id": "task-1"})
        assert r2.status_code == 409

        # get by id
        r3 = client.get("/api/meetings/attendance/task-1")
        assert r3.status_code == 200
        assert r3.json()["platform"] == "zoom"

        # missing -> 404
        assert client.get("/api/meetings/attendance/nope").status_code == 404

        # list
        r4 = client.get("/api/meetings/attendance")
        assert r4.status_code == 200
        assert len(r4.json()) == 1

        # update partial
        r5 = client.patch("/api/meetings/attendance/task-1", json={
            "current_status_message": "left", "final_notion_page_url": "https://n",
        })
        assert r5.status_code == 200
        assert r5.json()["current_status_message"] == "left"
        assert r5.json()["final_notion_page_url"] == "https://n"
        assert r5.json()["platform"] == "zoom"

        assert client.patch("/api/meetings/attendance/nope", json={}).status_code == 404

        # delete
        r6 = client.delete("/api/meetings/attendance/task-1")
        assert r6.status_code == 200
        assert client.get("/api/meetings/attendance/task-1").status_code == 404
        assert client.delete("/api/meetings/attendance/task-1").status_code == 404

    def test_requires_auth(self, db):
        from api.meeting_routes import router

        app = _app(router)
        app.dependency_overrides[get_db] = lambda: db
        client = TestClient(app, raise_server_exceptions=False)
        assert client.get("/api/meetings/attendance").status_code == 401


# =========================================================================== #
# memory_routes
# =========================================================================== #
class TestMemoryRoutes:
    @pytest.fixture(autouse=True)
    def _clean(self):
        import api.memory_routes as mr

        mr._memory_store.clear()
        mr._context_store.clear()
        yield
        mr._memory_store.clear()
        mr._context_store.clear()

    def _c(self, db=None):
        from api.memory_routes import router

        return _client(router, db or MagicMock())

    def test_stats_from_lancedb(self):
        from core.lancedb_handler import get_lancedb_handler

        handler = MagicMock()
        handler.list_documents.return_value = [
            {"metadata": {"integration_id": "outlook"}},
            {"metadata": {"integration_id": "outlook"}},
            {"metadata": {"integration_id": "gmail"}},
        ]
        with patch("core.lancedb_handler.get_lancedb_handler", return_value=handler):
            r = self._c().get("/api/memory/stats?workspace_id=ws-1")
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["total_entities"] == 3
        assert data["by_integration"] == {"outlook": 2, "gmail": 1}

    def test_stats_lancedb_unavailable(self):
        import api.memory_routes as mr

        with patch("core.lancedb_handler.get_lancedb_handler",
                   side_effect=ImportError("no lancedb")):
            r = self._c().get("/api/memory/stats")
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["total_entities"] == 0
        assert data["by_integration"] == {}

    def test_stats_lancedb_error_generic_no_leak(self):
        """WE1: the except-path must not leak str(e) into the payload."""
        import api.memory_routes as mr

        with patch(
            "core.lancedb_handler.get_lancedb_handler",
            side_effect=RuntimeError("secret /var/lib/memory.db exploded"),
        ):
            r = self._c().get("/api/memory/stats")
        assert r.status_code == 200
        payload = r.json()["data"]
        assert "secret" not in str(payload)
        assert "memory.db" not in str(payload)
        assert "error" in payload

    def test_store_and_retrieve(self):
        client = self._c()
        r = client.post("/api/memory", json={"key": "k1", "value": {"a": 1}, "metadata": {"m": 2}})
        assert r.status_code == 200
        body = r.json()
        assert body["key"] == "k1"
        assert body["value"] == {"a": 1}
        assert body["metadata"] == {"m": 2}

        r2 = client.get("/api/memory/k1")
        assert r2.status_code == 200
        assert r2.json()["value"] == {"a": 1}

        assert client.get("/api/memory/ghost").status_code == 404

    def test_delete_memory(self):
        client = self._c()
        client.post("/api/memory", json={"key": "k2", "value": "v"})
        r = client.delete("/api/memory/k2")
        assert r.status_code == 200
        assert client.get("/api/memory/k2").status_code == 404
        assert client.delete("/api/memory/k2").status_code == 404

    def test_search(self):
        client = self._c()
        client.post("/api/memory", json={"key": "alpha", "value": "Hello World"})
        client.post("/api/memory", json={"key": "beta", "value": "Goodbye Moon"})
        r = client.get("/api/memory/search?q=hello")
        assert r.status_code == 200
        body = r.json()
        assert body["metadata"]["count"] == 1
        assert body["data"][0]["key"] == "alpha"
        r2 = client.get("/api/memory/search?q=zzz")
        assert r2.json()["metadata"]["count"] == 0

    def test_context_crud(self):
        client = self._c()
        r = client.get("/api/memory/context/sess-1")
        assert r.status_code == 200
        assert r.json()["context"] == {}

        r2 = client.post("/api/memory/context/sess-1", json={"topic": "math"})
        assert r2.status_code == 200

        r3 = client.get("/api/memory/context/sess-1")
        assert r3.json()["context"]["topic"] == "math"

        # merge semantics
        client.post("/api/memory/context/sess-1", json={"difficulty": "hard"})
        r4 = client.get("/api/memory/context/sess-1")
        ctx = r4.json()["context"]
        assert ctx["topic"] == "math"
        assert ctx["difficulty"] == "hard"
        assert "_updated_at" in ctx

    def test_requires_auth(self):
        from api.memory_routes import router

        client = TestClient(_app(router), raise_server_exceptions=False)
        assert client.get("/api/memory/stats").status_code == 401
        assert client.get("/api/memory/search?q=x").status_code == 401


# =========================================================================== #
# reconciliation_routes
# =========================================================================== #
class TestReconciliationRoutes:
    def _c(self, db=None):
        from api.reconciliation_routes import router

        return _client(router, db or MagicMock())

    def _patch_engine(self, **attrs):
        import core.reconciliation_engine as re_mod

        engine = MagicMock()
        for k, v in attrs.items():
            setattr(engine, k, v)
        return patch.object(re_mod, "reconciliation_engine", engine), engine

    def test_add_bank_entry(self):
        p, engine = self._patch_engine()
        with p:
            r = self._c().post("/reconciliation/bank-entries", json={
                "id": "b-1", "source": "bank", "date": "2026-01-01T00:00:00",
                "amount": 100.5, "description": "deposit",
            })
        assert r.status_code == 200
        assert r.json()["status"] == "added"
        engine.add_bank_entry.assert_called_once()

    def test_add_ledger_entry_invalid_date(self):
        p, engine = self._patch_engine()
        with p:
            r = self._c().post("/reconciliation/ledger-entries", json={
                "id": "l-1", "source": "ledger", "date": "not-a-date",
                "amount": 1.0, "description": "x",
            })
        assert r.status_code == 422  # router.validation_error -> 422
        engine.add_ledger_entry.assert_not_called()

    def test_agent_governance_denied(self):
        from core.agent_context_resolver import AgentContextResolver
        from core.agent_governance_service import AgentGovernanceService

        resolver = AsyncMock()
        resolver.resolve_agent_for_request.return_value = (SimpleNamespace(id="a-1"), {})
        governance = MagicMock()
        governance.can_perform_action.return_value = {
            "allowed": False, "reason": "maturity too low"
        }
        with patch("core.agent_context_resolver.AgentContextResolver", return_value=resolver), \
             patch("core.agent_governance_service.AgentGovernanceService", return_value=governance):
            r = self._c().post("/reconciliation/bank-entries", json={
                "id": "b-2", "source": "bank", "date": "2026-01-01",
                "amount": 1.0, "description": "x", "agent_id": "a-1",
            })
        assert r.status_code == 403

    def test_agent_governance_allows(self):
        from core.agent_context_resolver import AgentContextResolver
        from core.agent_governance_service import AgentGovernanceService

        resolver = AsyncMock()
        resolver.resolve_agent_for_request.return_value = (SimpleNamespace(id="a-1"), {})
        governance = MagicMock()
        governance.can_perform_action.return_value = {"allowed": True, "reason": None}
        p, engine = self._patch_engine()
        with patch("core.agent_context_resolver.AgentContextResolver", return_value=resolver), \
             patch("core.agent_governance_service.AgentGovernanceService", return_value=governance), \
             p:
            r = self._c().post("/reconciliation/bank-entries", json={
                "id": "b-3", "source": "bank", "date": "2026-01-01",
                "amount": 1.0, "description": "x", "agent_id": "a-1",
            })
        assert r.status_code == 200

    def test_run_reconciliation(self):
        p, engine = self._patch_engine()
        engine.reconcile.return_value = {"matched": 2, "unmatched": 1}
        with p:
            r = self._c().post("/reconciliation/reconcile")
        assert r.status_code == 200
        assert r.json() == {"matched": 2, "unmatched": 1}

    def test_get_anomalies(self):
        anomaly = SimpleNamespace(
            id="an-1", anomaly_type=SimpleNamespace(value="amount_mismatch"),
            severity="high", description="desc", confidence=0.75, suggested_action="review",
        )
        p, engine = self._patch_engine()
        engine.get_anomalies.return_value = [anomaly]
        with p:
            r = self._c().get("/reconciliation/anomalies?unresolved_only=true")
        assert r.status_code == 200
        body = r.json()
        assert body["count"] == 1
        assert body["anomalies"][0]["type"] == "amount_mismatch"
        assert body["anomalies"][0]["confidence"] == 75.0
        engine.get_anomalies.assert_called_once_with(True)

    def test_detect_and_resolve_anomalies(self):
        p, engine = self._patch_engine()
        engine.detect_anomalies.return_value = [1, 2, 3]
        with p:
            r = self._c().post("/reconciliation/detect-anomalies")
        assert r.status_code == 200
        assert r.json() == {"detected": 3}

        p2, engine2 = self._patch_engine()
        engine2.resolve_anomaly.return_value = True
        with p2:
            r2 = self._c().post("/reconciliation/anomalies/an-1/resolve")
        assert r2.status_code == 200
        assert r2.json()["status"] == "resolved"

        p3, engine3 = self._patch_engine()
        engine3.resolve_anomaly.return_value = False
        with p3:
            r3 = self._c().post("/reconciliation/anomalies/ghost/resolve")
        assert r3.status_code == 404

    def test_requires_auth(self):
        from api.reconciliation_routes import router

        client = TestClient(_app(router), raise_server_exceptions=False)
        assert client.get("/reconciliation/anomalies").status_code == 401


# =========================================================================== #
# health_monitoring_routes
# =========================================================================== #
class TestHealthMonitoringRoutes:
    def _c(self, db=None):
        from api.health_monitoring_routes import router

        return _client(router, db or MagicMock())

    def test_agent_health(self):
        svc = AsyncMock()
        svc.get_agent_health.return_value = {
            "agent_id": "a-1", "agent_name": "Helper", "status": "active",
            "current_operation": None, "operations_completed": 10, "success_rate": 0.9,
            "confidence_score": 0.8, "last_active": "2026-01-01T00:00:00Z",
            "health_trend": "stable", "metrics": {},
        }
        with patch("api.health_monitoring_routes.get_health_monitoring_service", return_value=svc):
            r = self._c().get("/api/health/agent/a-1")
        assert r.status_code == 200
        body = r.json()
        assert body["agent_name"] == "Helper"
        assert body["health_trend"] == "stable"

    def test_agent_health_not_found(self):
        svc = AsyncMock()
        svc.get_agent_health.return_value = {"status": "error", "error": "Agent not found"}
        with patch("api.health_monitoring_routes.get_health_monitoring_service", return_value=svc):
            r = self._c().get("/api/health/agent/ghost")
        assert r.status_code == 404

    def test_integrations_health(self):
        svc = AsyncMock()
        svc.get_all_integrations_health.return_value = [{
            "integration_id": "i-1", "integration_name": "Slack", "status": "healthy",
            "last_used": "2026-01-01", "latency_ms": 12.5, "error_rate": 0.0,
            "health_trend": "stable", "connection_status": "connected",
        }]
        with patch("api.health_monitoring_routes.get_health_monitoring_service", return_value=svc):
            r = self._c().get("/api/health/integrations")
        assert r.status_code == 200
        assert r.json()[0]["integration_name"] == "Slack"
        svc.get_all_integrations_health.assert_awaited_once_with("u-1")

    def test_system_metrics(self):
        svc = AsyncMock()
        svc.get_system_metrics.return_value = {
            "cpu_usage": 0.3, "memory_usage": 0.5, "active_operations": 2,
            "queue_depth": 0, "total_agents": 3, "active_agents": 1,
            "total_integrations": 2, "healthy_integrations": 2, "alerts": {},
        }
        with patch("api.health_monitoring_routes.get_health_monitoring_service", return_value=svc):
            r = self._c().get("/api/health/system")
        assert r.status_code == 200
        assert r.json()["cpu_usage"] == 0.3

    def test_alerts_filter_and_sort(self):
        svc = AsyncMock()
        svc.get_active_alerts.return_value = [
            {"alert_id": "a2", "severity": "info", "message": "m2", "source_type": "s",
             "source_id": "1", "timestamp": "t", "action_required": False, "acknowledged": False},
            {"alert_id": "a1", "severity": "critical", "message": "m1", "source_type": "s",
             "source_id": "1", "timestamp": "t", "action_required": True, "acknowledged": False},
            {"alert_id": "a3", "severity": "warning", "message": "m3", "source_type": "s",
             "source_id": "1", "timestamp": "t", "action_required": False, "acknowledged": False},
        ]
        with patch("api.health_monitoring_routes.get_health_monitoring_service", return_value=svc):
            r = self._c().get("/api/health/alerts")
        assert r.status_code == 200
        ids = [a["alert_id"] for a in r.json()]
        assert ids == ["a1", "a3", "a2"]  # critical, warning, info

        with patch("api.health_monitoring_routes.get_health_monitoring_service", return_value=svc):
            r2 = self._c().get("/api/health/alerts?severity=critical")
        assert [a["alert_id"] for a in r2.json()] == ["a1"]

        with patch("api.health_monitoring_routes.get_health_monitoring_service", return_value=svc):
            r3 = self._c().get("/api/health/alerts?severity=unknown")
        assert r3.json() == []

    def test_requires_auth(self):
        from api.health_monitoring_routes import router

        client = TestClient(_app(router), raise_server_exceptions=False)
        assert client.get("/api/health/agent/a-1").status_code == 401


# =========================================================================== #
# project_health_routes
# =========================================================================== #
class TestProjectHealthRoutes:
    def _c(self, db=None):
        from api.project_health_routes import router

        return _client(router, db or MagicMock())

    def _metric(self, name, score=80, status="good"):
        from api.project_health_routes import HealthMetric

        return HealthMetric(
            name=name, score=score, max_score=100, status=status,
            details={}, trend="stable",
        )

    def test_full_check_all_integrations(self):
        with patch("api.project_health_routes.calculate_notion_health",
                   AsyncMock(return_value=self._metric("notion", 90, "excellent"))), \
             patch("api.project_health_routes.calculate_github_health",
                   AsyncMock(return_value=self._metric("github", 70, "good"))), \
             patch("api.project_health_routes.calculate_slack_health",
                   AsyncMock(return_value=self._metric("slack", 60, "warning"))), \
             patch("api.project_health_routes.calculate_meeting_health",
                   AsyncMock(return_value=self._metric("meetings", 80, "good"))):
            r = self._c().post("/api/v1/projects/health", json={
                "notion_api_key": "k", "notion_database_id": "db",
                "github_owner": "o", "github_repo": "r", "slack_channel_id": "c",
                "time_range_days": 14,
            })
        assert r.status_code == 200
        body = r.json()
        assert set(body["metrics"].keys()) == {"notion", "github", "slack", "meetings"}
        assert body["time_range_days"] == 14
        assert body["check_id"]
        assert 0 <= body["overall_score"] <= 100

    def test_partial_integrations_only(self):
        with patch("api.project_health_routes.calculate_notion_health",
                   AsyncMock(return_value=self._metric("notion"))), \
             patch("api.project_health_routes.calculate_meeting_health",
                   AsyncMock(return_value=self._metric("meetings"))):
            r = self._c().post("/api/v1/projects/health", json={
                "notion_api_key": "k", "notion_database_id": "db",
            })
        assert r.status_code == 200
        assert set(r.json()["metrics"].keys()) == {"notion", "meetings"}

    def test_no_credentials_still_reports_meetings(self):
        with patch("api.project_health_routes.calculate_meeting_health",
                   AsyncMock(return_value=self._metric("meetings"))):
            r = self._c().post("/api/v1/projects/health", json={})
        assert r.status_code == 200
        assert list(r.json()["metrics"].keys()) == ["meetings"]

    def test_integration_failure_doesnt_kill_check(self):
        with patch("api.project_health_routes.calculate_notion_health",
                   AsyncMock(side_effect=RuntimeError("notion down"))), \
             patch("api.project_health_routes.calculate_meeting_health",
                   AsyncMock(return_value=self._metric("meetings"))):
            r = self._c().post("/api/v1/projects/health", json={
                "notion_api_key": "k", "notion_database_id": "db",
            })
        assert r.status_code == 200
        assert list(r.json()["metrics"].keys()) == ["meetings"]

    def test_all_calculators_failing_400(self):
        with patch("api.project_health_routes.calculate_meeting_health",
                   AsyncMock(side_effect=RuntimeError("calendar down"))), \
             patch("api.project_health_routes.calculate_notion_health",
                   AsyncMock(side_effect=RuntimeError("notion down"))):
            r = self._c().post("/api/v1/projects/health", json={
                "notion_api_key": "k", "notion_database_id": "db",
            })
        assert r.status_code == 400  # no metrics calculated at all

    def test_time_range_bounds(self):
        assert self._c().post("/api/v1/projects/health", json={"time_range_days": 0}).status_code == 422
        assert self._c().post("/api/v1/projects/health", json={"time_range_days": 91}).status_code == 422

    def test_templates_endpoint(self):
        r = self._c().get("/api/v1/projects/health/templates")
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 4
        assert "software_development" in body["templates"]

    def test_pure_helpers(self):
        from api.project_health_routes import (
            calculate_overall_score,
            generate_overall_recommendations,
        )

        score, status = calculate_overall_score({})
        assert score == 0.0
        assert status == "unknown"

        metrics = {
            "a": self._metric("a", 90, "excellent"),
            "b": self._metric("b", 40, "warning"),
        }
        score2, status2 = calculate_overall_score(metrics)
        assert 0 < score2 <= 100
        recs = generate_overall_recommendations(metrics)
        assert isinstance(recs, list)

    def test_requires_auth(self):
        from api.project_health_routes import router

        client = TestClient(_app(router), raise_server_exceptions=False)
        assert client.post("/api/v1/projects/health", json={}).status_code == 401
