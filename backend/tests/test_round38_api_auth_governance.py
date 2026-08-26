"""
Round 38 — Remaining API surface: auth + governance wiring + impersonation + leak sweep.

Regression tests (Red-Green-Refactor) for bugs found in the July 31 sweep:

  A. Unauthenticated endpoints — anonymous callers could:
     - execute business interventions, simulate decisions, read financial forensics
       (api/operational_routes.py  /api/business-health/*)
     - create tasks on connected platforms via MCP, read tasks as any user
       (api/project_routes.py  /api/projects/unified-tasks)
     - burn LLM credits + read provider config (api/ai_workflows_routes.py)
     - adjudicate feedback + read pending feedback content (api/feedback_batch.py)
     - read/ingest any user's Zoho WorkDrive files (api/zoho_workdrive_routes.py)
     - create/import/execute workflow templates (api/workflow_template_routes.py)
     - register/start/stop background agents (api/background_agent_routes.py)
     - enable auto data sync (api/data_ingestion_routes.py)

  B. Governance wiring — @require_governance silently skips its check when the
     decorated function's Request parameter is named http_request (or missing),
     because the wrapper looks up kwargs['request']. Renaming restores gating.

  C. Impersonation — client-supplied user_id was trusted instead of the
     authenticated user's identity (deeplinks execute, zoho-workdrive).

  D. str(e) leaks — internal exception text returned to clients
     (forensics_api, project_routes, ai_workflows_routes, canvas_recording_routes,
     workflow_template_routes, document_ingestion_routes).
"""

import inspect
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.auth import get_current_user as auth_get_current_user
from core.database import get_db

SENTINEL = "SENTINEL_LEAK_round37"


def make_client(router, current_user=None, db=None, base_url=None):
    """Build an isolated TestClient for a router (per-file app pattern)."""
    app = FastAPI()
    if base_url:
        app.include_router(router)
        # Caller may pass a router that already declares its own prefix.
    else:
        app.include_router(router)

    def _override_user():
        return current_user if current_user is not None else MagicMock(id="round37-user")

    def _override_db():
        return db if db is not None else MagicMock()

    app.dependency_overrides[auth_get_current_user] = _override_user
    app.dependency_overrides[get_db] = _override_db
    return TestClient(app, raise_server_exceptions=False)


def make_anon_client(router):
    """Build a TestClient WITHOUT overriding auth — requests must 401."""
    app = FastAPI()
    app.include_router(router)
    return TestClient(app, raise_server_exceptions=False)


# ============================================================================
# A. Unauthenticated endpoints must now return 401
# ============================================================================

class TestProjectRoutesAuth:
    def test_get_unified_tasks_requires_auth(self):
        from api.project_routes import router
        client = make_anon_client(router)
        assert client.get("/api/projects/unified-tasks").status_code == 401

    def test_create_unified_task_requires_auth(self):
        from api.project_routes import router
        client = make_anon_client(router)
        resp = client.post("/api/projects/unified-tasks", json={"name": "x"})
        assert resp.status_code == 401

    def test_authenticated_get_works(self):
        from api.project_routes import router
        with patch("api.project_routes.mcp_service") as mock_mcp:
            mock_mcp.execute_tool = AsyncMock(return_value={"tasks": []})
            client = make_client(router, current_user=MagicMock(id="u-1"))
            resp = client.get("/api/projects/unified-tasks")
        assert resp.status_code == 200


class TestOperationalRoutesAuth:
    def _client(self):
        from api.operational_routes import router
        return make_anon_client(router)

    def test_priorities_requires_auth(self):
        assert self._client().get("/api/business-health/priorities").status_code == 401

    def test_simulate_requires_auth(self):
        resp = self._client().post(
            "/api/business-health/simulate",
            json={"decision_type": "hiring", "data": {}},
        )
        assert resp.status_code == 401

    def test_price_drift_requires_auth(self):
        assert self._client().get("/api/business-health/forensics/price-drift").status_code == 401

    def test_pricing_advisor_requires_auth(self):
        assert self._client().get("/api/business-health/forensics/pricing-advisor").status_code == 401

    def test_subscription_waste_requires_auth(self):
        assert self._client().get("/api/business-health/forensics/waste").status_code == 401

    def test_generate_interventions_requires_auth(self):
        assert self._client().post("/api/business-health/interventions/generate").status_code == 401

    def test_execute_intervention_requires_auth(self):
        resp = self._client().post(
            "/api/business-health/interventions/abc/execute",
            json={"action": "cancel", "payload": {}},
        )
        assert resp.status_code == 401


class TestAIWorkflowsAuth:
    def _client(self):
        from api.ai_workflows_routes import router
        return make_anon_client(router)

    def test_parse_nlu_requires_auth(self):
        resp = self._client().post("/api/ai-workflows/nlu/parse", json={"text": "hello"})
        assert resp.status_code == 401

    def test_providers_requires_auth(self):
        assert self._client().get("/api/ai-workflows/providers").status_code == 401

    def test_complete_requires_auth(self):
        resp = self._client().post("/api/ai-workflows/complete", json={"prompt": "hi"})
        assert resp.status_code == 401


class TestFeedbackBatchAuth:
    def _client(self):
        from api.feedback_batch import router
        return make_anon_client(router)

    def test_approve_requires_auth(self):
        resp = self._client().post("/api/feedback/batch/approve", json={"feedback_ids": ["f1"]})
        assert resp.status_code == 401

    def test_reject_requires_auth(self):
        resp = self._client().post("/api/feedback/batch/reject", json={"feedback_ids": ["f1"]})
        assert resp.status_code == 401

    def test_update_status_requires_auth(self):
        resp = self._client().post(
            "/api/feedback/batch/update-status",
            json={"feedback_ids": ["f1"], "new_status": "approved"},
        )
        assert resp.status_code == 401

    def test_pending_requires_auth(self):
        assert self._client().get("/api/feedback/batch/pending").status_code == 401

    def test_stats_requires_auth(self):
        assert self._client().get("/api/feedback/batch/stats").status_code == 401


class TestZohoWorkDriveAuth:
    def _client(self):
        from api.zoho_workdrive_routes import router
        return make_anon_client(router)

    def test_teams_requires_auth(self):
        assert self._client().get("/api/zoho-workdrive/teams?user_id=x").status_code == 401

    def test_list_files_requires_auth(self):
        resp = self._client().post("/api/zoho-workdrive/files/list", json={"user_id": "x"})
        assert resp.status_code == 401

    def test_ingest_requires_auth(self):
        resp = self._client().post("/api/zoho-workdrive/ingest", json={"user_id": "x", "file_id": "f"})
        assert resp.status_code == 401


class TestWorkflowTemplateAuth:
    def _client(self):
        from api.workflow_template_routes import router
        return make_anon_client(router)

    def test_create_template_requires_auth(self):
        resp = self._client().post("/api/workflow-templates/", json={"name": "t", "description": "d"})
        assert resp.status_code == 401

    def test_import_template_requires_auth(self):
        resp = self._client().post("/api/workflow-templates/tpl_1/import")
        assert resp.status_code == 401

    def test_execute_template_requires_auth(self):
        resp = self._client().post("/api/workflow-templates/tpl_1/execute", json={})
        assert resp.status_code == 401


class TestBackgroundAgentAuth:
    def _client(self):
        from api.background_agent_routes import router
        return make_anon_client(router)

    def test_register_requires_auth(self):
        resp = self._client().post("/api/background-agents/ag-1/register", json={"interval_seconds": 3600})
        assert resp.status_code == 401

    def test_start_requires_auth(self):
        assert self._client().post("/api/background-agents/ag-1/start").status_code == 401

    def test_stop_requires_auth(self):
        assert self._client().post("/api/background-agents/ag-1/stop").status_code == 401

    def test_all_status_requires_auth(self):
        assert self._client().get("/api/background-agents/status").status_code == 401

    def test_agent_status_requires_auth(self):
        assert self._client().get("/api/background-agents/ag-1/status").status_code == 401


class TestDataIngestionAuth:
    def test_enable_auto_sync_requires_auth(self):
        from api.data_ingestion_routes import router
        client = make_anon_client(router)
        resp = client.post(
            "/api/data-ingestion/enable-sync",
            json={"integration_id": "salesforce"},
        )
        assert resp.status_code == 401


# ============================================================================
# B. Governance wiring — request/http_request param-name mismatch
# ============================================================================

class TestGovernanceWiring:
    async def test_wrapper_resolves_http_request_fallback(self, monkeypatch):
        """The governance wrapper must find the starlette Request even when the
        endpoint names it http_request (body param already uses `request`).
        Previously the check was silently skipped for those endpoints."""
        from fastapi import Request
        from core import api_governance as gov

        seen = {}

        async def fake_check(**kwargs):
            seen["agent_id"] = kwargs.get("agent_id")

        monkeypatch.setattr(gov, "perform_governance_check", fake_check)

        http_request = Request({
            "type": "http", "method": "POST", "path": "/api/test",
            "query_string": b"agent_id=ag-42", "headers": [],
            "server": ("test", 80), "client": ("test", 123), "scheme": "http",
        })

        @gov.require_governance(action_complexity=2, action_name="t", feature="f")
        async def handler(http_request=None, db=None, **kwargs):
            return "ok"

        result = await handler(http_request=http_request, db=MagicMock())
        assert result == "ok"
        assert seen.get("agent_id") == "ag-42", (
            "governance check was skipped: http_request not resolved"
        )

    async def test_wrapper_still_uses_request_param(self, monkeypatch):
        """Endpoints with a properly-named request param keep working."""
        from fastapi import Request
        from core import api_governance as gov

        seen = {}

        async def fake_check(**kwargs):
            seen["agent_id"] = kwargs.get("agent_id")

        monkeypatch.setattr(gov, "perform_governance_check", fake_check)

        http_request = Request({
            "type": "http", "method": "POST", "path": "/api/test",
            "query_string": b"agent_id=ag-7", "headers": [],
            "server": ("test", 80), "client": ("test", 123), "scheme": "http",
        })

        @gov.require_governance(action_complexity=2, action_name="t", feature="f")
        async def handler(request=None, db=None, **kwargs):
            return "ok"

        result = await handler(request=http_request, db=MagicMock())
        assert result == "ok"
        assert seen.get("agent_id") == "ag-7"

    @pytest.mark.parametrize("func_name", ["list_conflicts", "get_conflict"])
    def test_admin_conflict_endpoints_have_request_param(self, func_name):
        """These two endpoints had no Request param at all — governance was
        skipped unconditionally. They must now declare it."""
        import api.admin_routes as mod
        func = getattr(mod, func_name)
        assert "request" in set(inspect.signature(func).parameters)

    def test_governance_decorated_endpoints_have_auth_dependency(self):
        """All require_governance endpoints must also carry Depends(get_current_user)."""
        import api.project_routes as project_mod
        import api.workflow_template_routes as wt_mod
        import api.background_agent_routes as bg_mod
        import api.data_ingestion_routes as di_mod

        def params_of(func):
            return set(inspect.signature(func).parameters)

        for mod, func_names in [
            (project_mod, ["create_unified_task"]),
            (wt_mod, ["create_template", "import_template", "execute_template"]),
            (bg_mod, ["register_background_agent", "start_background_agent"]),
            (di_mod, ["enable_auto_sync"]),
        ]:
            for name in func_names:
                params = params_of(getattr(mod, name))
                assert any(
                    p in params for p in ("current_user", "current_admin", "user")
                ), f"{mod.__name__}.{name} missing authenticated-user dependency"


# ============================================================================
# C. Impersonation — client-supplied user_id must not be trusted
# ============================================================================

class TestImpersonation:
    def test_deeplink_execute_uses_authenticated_user(self):
        from api import deeplinks as deeplinks_mod

        authed_user = MagicMock(id="real-user-42")
        client = make_client(deeplinks_mod.router, current_user=authed_user)

        captured = {}
        async def fake_execute(**kwargs):
            captured.update(kwargs)
            return {"success": True, "agent_id": "a1", "agent_name": "A",
                    "execution_id": "e1", "resource_type": "agent",
                    "resource_id": "r1", "action": "run", "source": "external"}

        with patch.object(deeplinks_mod, "execute_deep_link", side_effect=fake_execute):
            resp = client.post("/api/deeplinks/execute", json={
                "deeplink_url": "atom://agent/a1",
                "user_id": "attacker-claimed-user",  # must be ignored
                "source": "external",
            })
        assert resp.status_code == 200
        assert captured.get("user_id") == "real-user-42", (
            "deeplink executed as client-supplied user_id (cross-user impersonation)"
        )

    def test_zoho_workdrive_list_uses_authenticated_user(self):
        from api import zoho_workdrive_routes as zoho_mod

        authed_user = MagicMock(id="real-user-42")
        client = make_client(zoho_mod.router, current_user=authed_user)

        captured = {}
        async def fake_list(user_id, parent_id, team_id=None, workspace_id=None, recursive=False):
            captured["user_id"] = user_id
            return []

        with patch.object(zoho_mod.zoho_service, "list_files", side_effect=fake_list):
            resp = client.post("/api/zoho-workdrive/files/list", json={
                "user_id": "attacker-claimed-user",
                "parent_id": "root",
            })
        assert resp.status_code == 200
        assert captured.get("user_id") == "real-user-42", (
            "zoho files listed for client-supplied user_id (cross-user file access)"
        )

    def test_deeplink_audit_scoped_to_current_user(self):
        from api import deeplinks as deeplinks_mod

        authed_user = MagicMock(id="real-user-42")
        mock_db = MagicMock()
        mock_db.query.return_value.offset.return_value.limit.return_value.all.return_value = []
        client = make_client(deeplinks_mod.router, current_user=authed_user, db=mock_db)

        resp = client.get("/api/deeplinks/audit?user_id=someone-else")
        assert resp.status_code == 200
        # The client-supplied user_id must be ignored — the filter must reference
        # the authenticated user, never "someone-else".
        assert len(mock_db.query.return_value.filter.call_args_list) == 1
        expr = mock_db.query.return_value.filter.call_args_list[0].args[0]
        right = getattr(expr, "right", None)
        value = getattr(right, "value", right)
        assert value == "real-user-42", f"audit filtered by {value!r}, expected current_user"


# ============================================================================
# D. str(e) leaks
# ============================================================================

class TestStrELeaks:
    def test_forensics_api_does_not_leak_exception_text(self):
        from api import forensics_api as mod
        client = make_client(mod.router, current_user=MagicMock(id="u-1"))

        def boom(*args, **kwargs):
            raise Exception(f"{SENTINEL}_forensics")

        with patch.object(mod, "get_forensics_services", side_effect=boom):
            resp = client.get("/api/forensics/vendor-drift")
        assert resp.status_code == 500
        assert SENTINEL not in resp.text

    def test_project_routes_does_not_leak_exception_text(self):
        from api import project_routes as mod
        client = make_client(mod.router, current_user=MagicMock(id="u-1"))

        with patch.object(mod.mcp_service, "execute_tool", new=AsyncMock(
            side_effect=Exception(f"{SENTINEL}_project"))):
            resp = client.get("/api/projects/unified-tasks")
        assert SENTINEL not in resp.text

    def test_ai_workflows_complete_does_not_leak_exception_text(self):
        from api import ai_workflows_routes as mod
        client = make_client(mod.router, current_user=MagicMock(id="u-1"))

        with patch("enhanced_ai_workflow_endpoints.ai_service") as mock_svc:
            mock_svc.analyze_text = AsyncMock(side_effect=Exception(f"{SENTINEL}_aiworkflows"))
            resp = client.post("/api/ai-workflows/complete", json={"prompt": "hi"})
        assert SENTINEL not in resp.text

    def test_canvas_recording_flag_does_not_leak_exception_text(self):
        from api import canvas_recording_routes as mod
        from core.models import CanvasRecording

        user = MagicMock(id="u-1")
        recording = MagicMock(spec=CanvasRecording)
        recording.user_id = "u-1"
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = recording
        client = make_client(mod.router, current_user=user, db=mock_db)

        def boom(*args, **kwargs):
            raise Exception(f"{SENTINEL}_recording")

        with patch.object(mod, "get_canvas_recording_service", side_effect=boom):
            resp = client.post("/api/canvas/recording/rec-1/flag", json={"flag_reason": "test"})
        assert SENTINEL not in resp.text

    def test_workflow_template_create_does_not_leak_exception_text(self):
        from api import workflow_template_routes as mod
        client = make_client(mod.router, current_user=MagicMock(id="u-1"))

        with patch.object(mod, "get_template_manager", side_effect=Exception(f"{SENTINEL}_tpl")):
            resp = client.post("/api/workflow-templates/", json={"name": "t", "description": "d"})
        assert SENTINEL not in resp.text

    def test_document_ingestion_parse_does_not_leak_exception_text(self):
        from core.security_dependencies import get_current_user as sec_get_current_user
        from api import document_ingestion_routes as mod

        app = FastAPI()
        app.include_router(mod.router)
        app.dependency_overrides[sec_get_current_user] = lambda: MagicMock(id="u-1")
        client = TestClient(app, raise_server_exceptions=False)

        with patch("core.docling_processor.is_docling_available", return_value=False):
            with patch("core.auto_document_ingestion.DocumentParser.parse_document",
                       side_effect=Exception(f"{SENTINEL}_doc_ingest")):
                resp = client.post(
                    "/api/document-ingestion/parse",
                    files={"file": ("test.txt", b"hello world", "text/plain")},
                )
        assert SENTINEL not in resp.text


# ============================================================================
# E. Feedback batch must derive identity from the token, not the body
# ============================================================================

class TestFeedbackBatchIdentity:
    def test_approve_uses_authenticated_identity(self):
        from api import feedback_batch as mod
        from core.models import AgentFeedback

        feedback = MagicMock(spec=AgentFeedback)
        feedback.status = "pending"
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = feedback
        client = make_client(mod.router, current_user=MagicMock(id="real-user-42"), db=mock_db)

        resp = client.post("/api/feedback/batch/approve", json={
            "feedback_ids": ["f1"],
            "user_id": "attacker-claimed-user",  # must be ignored
        })
        assert resp.status_code == 200
        assert feedback.status == "approved"
