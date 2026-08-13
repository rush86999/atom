"""Coverage wave 81 — core/missing_endpoints.py (0% → ~100%).

The module's 7 endpoints: task assignment, tracking setup, three demo
workflows, AI provider listing and generic AI execution. Wave's real-bug fix:
the router is auto-loaded at root in main_api_app (lazy integration registry
"missing_endpoints" → CORE_API_MODULES), yet every state-changing endpoint ran
UNauthenticated — anonymous users could assign tasks, set up tracking, and
trigger demo workflow "execution" against the production app. Auth added to
all six POST routes (GET /api/v1/ai/providers stays anon, matching the BYOK
`/api/ai/providers` convention).
"""
import uuid
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import core.missing_endpoints as me
from core.auth import get_current_user


@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(me.router)
    app.dependency_overrides[get_current_user] = lambda: {"id": "u1", "tenant_id": "t1"}
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


class TestAuthentication:
    """REAL BUG (wave fix): state-changing routes ran unauthenticated."""

    def test_anon_assign_tasks_401(self):
        app = FastAPI()
        app.include_router(me.router)
        resp = TestClient(app).post("/api/v1/tasks/assign",
                                    json={"tasks": ["a"], "team": "eng"})
        assert resp.status_code == 401

    def test_anon_tracking_setup_401(self):
        app = FastAPI()
        app.include_router(me.router)
        resp = TestClient(app).post("/api/v1/tracking/setup",
                                    json={"tracking_metric": "velocity",
                                          "interval": "weekly"})
        assert resp.status_code == 401

    @pytest.mark.parametrize("path", [
        "/api/v1/workflows/demo-project-management",
        "/api/v1/workflows/demo-customer-support",
        "/api/v1/workflows/demo-sales-lead",
    ])
    def test_anon_demo_workflow_401(self, path):
        app = FastAPI()
        app.include_router(me.router)
        resp = TestClient(app).post(path, json={"description": "demo"})
        assert resp.status_code == 401

    def test_anon_ai_execute_401(self):
        app = FastAPI()
        app.include_router(me.router)
        resp = TestClient(app).post("/api/v1/ai/execute",
                                    json={"description": "run"})
        assert resp.status_code == 401

    def test_ai_providers_stays_public(self, app):
        resp = TestClient(app).get("/api/v1/ai/providers")
        assert resp.status_code == 200


class TestAssignTasks:
    def test_assign_tasks_success(self, client):
        resp = client.post("/api/v1/tasks/assign",
                           json={"tasks": ["t1", "t2", "t3"], "team": "eng"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert len(body["assignments"]) == 3
        assert body["assignments"][0] == {
            "task_id": "t1", "assigned_to": "member_0", "team": "eng"}
        assert body["assignments"][2]["assigned_to"] == "member_2"
        assert body["notifications_sent"] is True
        assert body["message"] == "Assigned 3 tasks to eng"

    def test_assign_tasks_empty(self, client):
        resp = client.post("/api/v1/tasks/assign",
                           json={"tasks": [], "team": "eng"})
        assert resp.status_code == 200
        assert resp.json()["assignments"] == []

    def test_assign_tasks_missing_fields_422(self, client):
        resp = client.post("/api/v1/tasks/assign", json={"tasks": ["t1"]})
        assert resp.status_code == 422


class TestTrackingSetup:
    def test_tracking_setup_success(self, client):
        with patch.object(me.uuid, "uuid4", return_value=uuid.UUID(int=7)):
            resp = client.post("/api/v1/tracking/setup",
                               json={"tracking_metric": "velocity",
                                     "interval": "weekly"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["tracking_id"] == "00000000-0000-0000-0000-000000000007"
        assert body["metric"] == "velocity"
        assert body["interval"] == "weekly"
        assert body["tracking_enabled"] is True
        assert body["dashboard_created"] is True
        assert body["dashboard_url"] == "/analytics/dashboard/project-1"

    def test_tracking_setup_missing_interval_422(self, client):
        resp = client.post("/api/v1/tracking/setup",
                           json={"tracking_metric": "velocity"})
        assert resp.status_code == 422


class TestDemoWorkflows:
    def test_demo_project_management_success(self, client):
        resp = client.post("/api/v1/workflows/demo-project-management",
                           json={"description": "plan", "input": "x"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "completed"
        assert body["workflow_id"] == "demo-project-management"
        assert body["steps_executed"] == 5
        assert body["execution_time_ms"] == 1250
        assert len(body["execution_history"]) == 5
        assert body["validation_evidence"]["complexity_score"] == 7
        assert body["execution_id"]

    def test_demo_project_management_internal_error_500(self, client):
        with patch.object(me.uuid, "uuid4",
                          side_effect=RuntimeError("boom")):
            resp = client.post("/api/v1/workflows/demo-project-management",
                               json={})
        assert resp.status_code == 500

    def test_demo_customer_support_success(self, client):
        resp = client.post("/api/v1/workflows/demo-customer-support",
                           json={"description": "support"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["workflow_id"] == "demo-customer-support"
        assert body["steps_executed"] == 6
        assert len(body["execution_history"]) == 6
        assert body["validation_evidence"]["complexity_score"] == 8

    def test_demo_customer_support_internal_error_500(self, client):
        with patch.object(me.uuid, "uuid4",
                          side_effect=RuntimeError("boom")):
            resp = client.post("/api/v1/workflows/demo-customer-support",
                               json={})
        assert resp.status_code == 500

    def test_demo_sales_lead_success(self, client):
        resp = client.post("/api/v1/workflows/demo-sales-lead",
                           json={"description": "leads"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["workflow_id"] == "demo-sales-lead"
        assert body["steps_executed"] == 5
        assert len(body["execution_history"]) == 5
        assert body["validation_evidence"]["complexity_score"] == 7

    def test_demo_sales_lead_internal_error_500(self, client):
        with patch.object(me.uuid, "uuid4",
                          side_effect=RuntimeError("boom")):
            resp = client.post("/api/v1/workflows/demo-sales-lead", json={})
        assert resp.status_code == 500

    def test_demo_workflow_extra_fields_allowed(self, client):
        resp = client.post("/api/v1/workflows/demo-sales-lead",
                           json={"description": "d", "input": "i",
                                 "arbitrary": {"nested": 1}})
        assert resp.status_code == 200


class TestAIEndpoints:
    def test_get_ai_providers(self, client):
        resp = client.get("/api/v1/ai/providers")
        assert resp.status_code == 200
        body = resp.json()
        assert body["providers"] == ["openai", "anthropic", "deepseek"]
        assert body["active_providers"] == 3
        assert body["multi_provider_support"] is True
        assert body["default_provider"] == "openai"

    def test_execute_ai_workflow_success(self, client):
        resp = client.post("/api/v1/ai/execute",
                           json={"description": "create tasks"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["tasks_created"] == 2
        assert len(body["ai_generated_tasks"]) == 2
        assert body["confidence_score"] == 0.92
        assert body["intent"] == "task_creation"
        assert body["entities"] == ["financial report", "team meeting"]
