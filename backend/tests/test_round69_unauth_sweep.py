"""
Round 69 — Theme B: unauthenticated route sweep (Red-Green-Refactor).

Routes that mutate state / send messages / trigger LLM calls / expose
orchestrator state with no auth get ``get_current_user`` (or an internal
constant-time shared-secret dependency for scheduler internals).
"""

import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.auth import get_current_user as auth_get_current_user
from core.database import get_db


def user(role="member"):
    return MagicMock(id="u-69", email="u@example.com", role=role, tenant_id="tenant-69")


def make_client(router_obj, role=None):
    app = FastAPI()
    app.include_router(router_obj)
    app.dependency_overrides[get_db] = lambda: MagicMock()
    if role:
        app.dependency_overrides[auth_get_current_user] = lambda: user(role)
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# B1 — sales router
# ---------------------------------------------------------------------------


class TestSalesRoutesAuth:
    def test_dashboard_summary_anon_401(self):
        from sales.routes import router

        client = make_client(router)
        resp = client.get("/api/sales/dashboard/summary?workspace_id=ws-1")
        assert resp.status_code == 401

    def test_dashboard_summary_authed_200(self):
        from sales.routes import router

        client = make_client(router, role="member")
        with patch("sales.routes.SalesDashboardService") as m_svc:
            m_svc.return_value.get_sales_summary = MagicMock(return_value={})
            resp = client.get("/api/sales/dashboard/summary?workspace_id=ws-1")
        assert resp.status_code == 200

    def test_ingest_lead_anon_401(self):
        from sales.routes import router

        client = make_client(router)
        resp = client.post("/api/sales/leads/ingest?workspace_id=ws-1", json={"email": "a@b.c"})
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# B2 — messaging routes
# ---------------------------------------------------------------------------


class TestMessagingProactiveAuth:
    def test_schedule_anon_401(self):
        from api.messaging_routes import router

        client = make_client(router)
        resp = client.post(
            "/api/v1/messaging/proactive/schedule",
            json={
                "agent_id": "a1",
                "platform": "slack",
                "recipient_id": "r1",
                "content": "hi",
                "scheduled_for": "2026-09-01T00:00:00Z",
            },
        )
        assert resp.status_code == 401

    def test_schedule_authed_200(self):
        from api.messaging_routes import router

        client = make_client(router, role="member")
        with patch("api.messaging_routes.ProactiveMessagingService") as m_svc:
            m_svc.return_value.create_proactive_message = MagicMock(
                return_value=MagicMock(id="m1", agent_id="a1", agent_name="", agent_maturity_level="", platform="slack", recipient_id="r1", content="hi", scheduled_for=None, send_now=False, status="pending", approved_by=None, approved_at=None, rejection_reason=None, sent_at=None, error_message=None, platform_message_id=None, created_at=datetime.now(timezone.utc), updated_at=None)
            )
            resp = client.post(
                "/api/v1/messaging/proactive/schedule",
                json={
                    "agent_id": "a1",
                    "platform": "slack",
                    "recipient_id": "r1",
                    "content": "hi",
                    "scheduled_for": "2026-09-01T00:00:00Z",
                },
            )
        assert resp.status_code == 200

    def test_get_message_anon_401(self):
        from api.messaging_routes import router

        client = make_client(router)
        resp = client.get("/api/v1/messaging/proactive/m-1")
        assert resp.status_code == 401

    def test_send_scheduled_anon_401(self):
        from api.messaging_routes import router

        client = make_client(router)
        resp = client.post("/api/v1/messaging/proactive/_send_scheduled")
        assert resp.status_code == 401

    def test_send_scheduled_with_secret_200(self):
        from api.messaging_routes import router

        secret = "scheduler-secret-69"
        client = make_client(router)
        with patch.dict(os.environ, {"ATOM_SCHEDULER_SECRET": secret}), patch(
            "api.messaging_routes.ProactiveMessagingService"
        ) as m_svc:
            m_svc.return_value.send_scheduled_messages = AsyncMock(
                return_value={"sent": 0, "failed": 0}
            )
            resp = client.post(
                "/api/v1/messaging/proactive/_send_scheduled",
                headers={"X-Scheduler-Secret": secret},
            )
        assert resp.status_code == 200

    def test_send_scheduled_wrong_secret_401(self):
        from api.messaging_routes import router

        client = make_client(router)
        with patch.dict(os.environ, {"ATOM_SCHEDULER_SECRET": "real-secret"}):
            resp = client.post(
                "/api/v1/messaging/proactive/_send_scheduled",
                headers={"X-Scheduler-Secret": "wrong"},
            )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# B3 — workflow UI read endpoints
# ---------------------------------------------------------------------------


class TestWorkflowUiReadAuth:
    def test_executions_anon_401(self):
        from core.workflow_ui_endpoints import router

        client = make_client(router)
        resp = client.get("/executions")
        assert resp.status_code == 401

    def test_executions_authed_200(self):
        from core.workflow_ui_endpoints import router

        client = make_client(router, role="member")
        with patch(
            "advanced_workflow_orchestrator.get_orchestrator",
            return_value=MagicMock(active_contexts={}),
        ):
            resp = client.get("/executions")
        assert resp.status_code == 200

    def test_debug_state_anon_401(self):
        from core.workflow_ui_endpoints import router

        client = make_client(router)
        resp = client.get("/debug/state")
        assert resp.status_code == 401

    def test_debug_state_authed_200(self):
        from core.workflow_ui_endpoints import router

        client = make_client(router, role="member")
        with patch(
            "advanced_workflow_orchestrator.get_orchestrator",
            return_value=MagicMock(active_contexts={}, memory_snapshots={}),
        ):
            resp = client.get("/debug/state")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# B4 — canvas docs read endpoints
# ---------------------------------------------------------------------------


class TestCanvasDocsReadAuth:
    def test_versions_anon_401(self):
        from api.canvas_docs_routes import router

        client = make_client(router)
        resp = client.get("/api/canvas/docs/c-1/versions")
        assert resp.status_code == 401

    def test_toc_anon_401(self):
        from api.canvas_docs_routes import router

        client = make_client(router)
        resp = client.get("/api/canvas/docs/c-1/toc")
        assert resp.status_code == 401

    def test_versions_authed_200(self):
        from api.canvas_docs_routes import router

        client = make_client(router, role="member")
        with patch("api.canvas_docs_routes.DocumentationCanvasService") as m_svc:
            m_svc.return_value.get_document_versions = MagicMock(return_value={"success": True})
            resp = client.get("/api/canvas/docs/c-1/versions")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# B5 — marketing LLM read endpoints
# ---------------------------------------------------------------------------


class TestMarketingLLMReadAuth:
    def test_reputation_analyze_anon_401(self):
        from api.marketing_routes import router

        client = make_client(router)
        resp = client.get("/api/marketing/reputation/analyze?interaction=hello")
        assert resp.status_code == 401

    def test_reputation_analyze_authed_200(self):
        from api.marketing_routes import router

        client = make_client(router, role="member")
        with patch("api.marketing_routes.reputation_manager") as m_rep:
            m_rep.determine_feedback_strategy = AsyncMock(return_value={"strategy": "public"})
            resp = client.get("/api/marketing/reputation/analyze?interaction=hello")
        assert resp.status_code == 200

    def test_gmb_weekly_post_anon_401(self):
        from api.marketing_routes import router

        client = make_client(router)
        resp = client.get("/api/marketing/gmb/weekly-post/suggest?business_name=B&location=L")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# B6 — oauth config-status
# ---------------------------------------------------------------------------


class TestOAuthConfigStatusAuth:
    def test_config_status_anon_401(self):
        from api.oauth_routes import router

        client = make_client(router)
        resp = client.get("/api/v1/auth/oauth/config-status")
        assert resp.status_code == 401

    def test_config_status_authed_200(self):
        from api import oauth_routes
        from api.oauth_routes import router

        client = make_client(router, role="member")
        # oauth_routes defines a local get_current_user wrapper (delegating to
        # core.auth) that shadows the imported one; override THAT callable so
        # the dependency resolves in tests.
        client.app.dependency_overrides[oauth_routes.get_current_user] = lambda: user("member")
        with patch("api.oauth_routes.GOOGLE_OAUTH_CONFIG", MagicMock(is_configured=MagicMock(return_value=True))):
            resp = client.get("/api/v1/auth/oauth/config-status")
        assert resp.status_code == 200

    def test_initiate_stays_public(self):
        from api.oauth_routes import router

        client = make_client(router)
        # /initiate redirects when provider is misconfigured; any non-401 is fine
        resp = client.get("/api/v1/auth/oauth/initiate?provider=google&redirect_uri=http://x")
        assert resp.status_code != 401
