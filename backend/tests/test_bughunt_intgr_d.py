"""
Bug-hunt tests (TDD RED->GREEN) for integrations modules:
workflow_approval_routes, google_calendar_service, xero_service,
sync_to_postgres_cache (github/gitlab/notion/outlook_calendar/google_calendar/
google_drive/onedrive/plaid), ecommerce_unified_service, document_logic_service,
chat_routes, webhook_renewal_routes, workflow_automation_routes, ai_routes,
universal_webhook_bridge, and str(e) leak sweep across service modules.
"""

import asyncio
import json
from datetime import datetime, timezone
from unittest import mock

import pytest

# ---------------------------------------------------------------------------
# 1. workflow_approval_routes: PAUSED executions can never be approved
# ---------------------------------------------------------------------------


def _make_approval_test_env():
    import importlib

    # The module imports advanced_workflow_orchestrator at import time.
    wf_mod = importlib.import_module("integrations.workflow_approval_routes")
    return wf_mod


class TestWorkflowApprovalRoutes:
    def test_respond_accepts_paused_status(self):
        """The pending list filters on WorkflowExecutionStatus.PAUSED; the
        respond handler must accept that same status instead of comparing
        against the orchestrator's 'waiting_approval' enum."""
        wf_mod = _make_approval_test_env()

        class FakeExec:
            execution_id = "exec-1"
            workflow_id = "wf-1"
            status = "PAUSED"  # WorkflowExecutionStatus.PAUSED.value
            context = json.dumps({"results": {"step1": {"status": "waiting_approval"}}})
            input_data = json.dumps({"x": 1})
            created_at = datetime.now(timezone.utc)
            error = None

        fake_db = mock.MagicMock()
        fake_db.query.return_value.filter.return_value.first.return_value = FakeExec()

        with mock.patch.object(
            wf_mod.AdvancedWorkflowOrchestrator, "resume_workflow"
        ) as mock_resume:
            mock_resume = mock.AsyncMock()

            async def run():
                resp = await wf_mod.respond_to_approval(
                    "exec-1",
                    wf_mod.ApprovalResponse(decision="approve", step_id="step1"),
                    db=fake_db,
                    user=None,
                )
                return resp

            resp = asyncio.run(run())
        assert resp["status"] == "success"
        fake_db.commit.assert_not_called()

    def test_reject_path_fails_execution(self):
        wf_mod = _make_approval_test_env()

        class FakeExec:
            execution_id = "exec-1"
            workflow_id = "wf-1"
            status = "PAUSED"
            context = None
            input_data = None
            created_at = datetime.now(timezone.utc)
            error = None

        fake_db = mock.MagicMock()
        fake_db.query.return_value.filter.return_value.first.return_value = FakeExec()

        resp = asyncio.run(
            wf_mod.respond_to_approval(
                "exec-1",
                wf_mod.ApprovalResponse(
                    decision="reject", step_id="step1", comments="nope"
                ),
                db=fake_db,
                user=None,
            )
        )
        assert resp["status"] == "cancelled"
        assert FakeExec.status == "FAILED"
        assert "nope" in FakeExec.error
        fake_db.commit.assert_called_once()


# ---------------------------------------------------------------------------
# 2. google_calendar_service.execute_operation: wrong kwargs
# ---------------------------------------------------------------------------


class TestGoogleCalendarExecuteOperation:
    @pytest.fixture()
    def svc(self):
        from integrations.google_calendar_service import GoogleCalendarService

        return GoogleCalendarService()

    def test_get_events_uses_time_min_time_max(self, svc):
        """execute_operation('get_events') previously forwarded phantom
        start_date/end_date kwargs -> TypeError -> always failed."""
        with mock.patch.object(
            svc, "get_events", new=mock.AsyncMock(return_value=[{"id": "e1"}])
        ) as m:
            result = asyncio.run(
                svc.execute_operation("get_events", {"time_min": "2026-01-01T00:00:00Z"})
            )
        assert result["success"] is True
        assert result["data"] == [{"id": "e1"}]
        call_kwargs = m.call_args.kwargs
        assert "time_min" in call_kwargs and "time_max" in call_kwargs
        assert "start_date" not in call_kwargs

    def test_update_event_passes_updates_not_event_data(self, svc):
        with mock.patch.object(
            svc, "update_event", new=mock.AsyncMock(return_value={"id": "e1"})
        ) as m:
            result = asyncio.run(
                svc.execute_operation(
                    "update_event",
                    {"event_id": "evt-1", "updates": {"title": "New"}},
                )
            )
        assert result["success"] is True
        assert m.call_args.kwargs["updates"] == {"title": "New"}
        assert "event_data" not in m.call_args.kwargs

    def test_check_conflicts_no_attendee_kwarg(self, svc):
        with mock.patch.object(
            svc,
            "check_conflicts",
            new=mock.AsyncMock(
                return_value={"success": True, "has_conflicts": False, "conflicts": []}
            ),
        ) as m:
            result = asyncio.run(
                svc.execute_operation(
                    "check_conflicts",
                    {"start_time": datetime.now(timezone.utc), "end_time": datetime.now(timezone.utc)},
                )
            )
        assert result["success"] is True
        assert "attendee_emails" not in m.call_args.kwargs

    def test_execute_operation_accepts_context_param(self, svc):
        """Other services accept (operation, parameters, context); the old
        signature (operation, params) blew up when the registry passed context."""
        with mock.patch.object(svc, "get_events", new=mock.AsyncMock(return_value=[])):
            result = asyncio.run(
                svc.execute_operation(
                    "get_events", {}, context={"tenant_id": svc.tenant_id}
                )
            )
        assert "success" in result

    def test_execute_operation_unknown_operation(self, svc):
        result = asyncio.run(svc.execute_operation("nope", {}))
        assert result["success"] is False


# ---------------------------------------------------------------------------
# 3. xero_service.execute_operation 'full_sync' wrong kwarg
# ---------------------------------------------------------------------------


class TestXeroExecuteOperation:
    def test_full_sync_passes_xero_tenant_id(self):
        from integrations.xero_service import XeroService

        svc = XeroService()
        with mock.patch.object(
            svc, "full_sync", new=mock.AsyncMock(return_value={"success": True})
        ) as m:
            result = asyncio.run(
                svc.execute_operation(
                    "full_sync",
                    {
                        "user_id": "u1",
                        "access_token": "tok",
                        "xero_tenant_id": "tenant-x",
                    },
                )
            )
        assert result["success"] is True
        assert m.call_args.kwargs.get("xero_tenant_id") == "tenant-x"
        assert "tenant_id" not in m.call_args.kwargs


# ---------------------------------------------------------------------------
# 4. sync_to_postgres_cache: IntegrationMetric has workspace_id, not tenant_id
# ---------------------------------------------------------------------------


def _in_memory_metric_db():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine("sqlite:///:memory:")
    from core.database import Base

    # Import models so the metadata is registered
    import core.models  # noqa: F401

    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal


class TestSyncToPostgresCacheWorkspaceId:
    @pytest.mark.parametrize(
        "module,op",
        [
            ("integrations.github_service", "sync_to_postgres_cache"),
            ("integrations.gitlab_service", "sync_to_postgres_cache"),
            ("integrations.notion_service", "sync_to_postgres_cache"),
            ("integrations.outlook_calendar_service", "sync_to_postgres_cache"),
            ("integrations.google_calendar_service", "sync_to_postgres_cache"),
            ("integrations.google_drive_service", "sync_to_postgres_cache"),
            ("integrations.onedrive_service", "sync_to_postgres_cache"),
            ("integrations.plaid_service", "sync_to_postgres_cache"),
        ],
    )
    def test_sync_writes_workspace_id_metric(self, module, op):
        """filter_by(tenant_id=...) on IntegrationMetric (which only has
        workspace_id) raised InvalidRequestError -> sync always failed."""
        import importlib

        mod = importlib.import_module(module)
        svc = mod.__dict__["GitHubService"]() if "github" in module else None
        if svc is None:
            # construct service generically from the module's service class
            svc_name = next(
                n
                for n in mod.__dict__
                if n.endswith("Service")
                and not n.startswith("_")
                and isinstance(mod.__dict__[n], type)
            )
            svc = mod.__dict__[svc_name]()

        SessionLocal = _in_memory_metric_db()
        with mock.patch.object(
            mod, "SessionLocal", SessionLocal, create=True
        ), mock.patch.object(
            mod, "get_db_session", create=True
        ) if hasattr(mod, "get_db_session") else mock.patch.object(
            mod, "SessionLocal", SessionLocal, create=True
        ):
            # Stub out the data-fetching pieces
            if module == "integrations.github_service":
                svc.get_user_repositories = lambda **kw: []
                result = asyncio.run(svc.sync_to_postgres_cache("ws-1"))
            elif module == "integrations.gitlab_service":
                svc.get_projects = mock.AsyncMock(return_value=[])
                result = asyncio.run(
                    svc.sync_to_postgres_cache("ws-1", access_token="tok")
                )
            elif module == "integrations.notion_service":
                svc.search_pages_in_workspace = mock.Mock(return_value=[])
                svc.search_databases_in_workspace = mock.Mock(return_value=[])
                result = asyncio.run(svc.sync_to_postgres_cache())
            elif module == "integrations.outlook_calendar_service":
                svc.get_events = mock.AsyncMock(return_value=[])
                result = asyncio.run(svc.sync_to_postgres_cache("ws-1"))
            elif module == "integrations.google_calendar_service":
                svc.get_events = mock.AsyncMock(return_value=[])
                result = asyncio.run(svc.sync_to_postgres_cache("ws-1"))
            elif module == "integrations.google_drive_service":
                svc.list_files = mock.AsyncMock(
                    return_value={"status": "success", "data": {"files": []}}
                )
                result = asyncio.run(
                    svc.sync_to_postgres_cache("ws-1", access_token="tok")
                )
            elif module == "integrations.onedrive_service":
                svc.list_files = mock.AsyncMock(
                    return_value={"status": "success", "data": {"value": []}}
                )
                result = asyncio.run(
                    svc.sync_to_postgres_cache("ws-1", access_token="tok")
                )
            elif module == "integrations.plaid_service":
                svc.get_accounts = mock.AsyncMock(return_value=[])
                result = asyncio.run(
                    svc.sync_to_postgres_cache("ws-1", access_token="tok")
                )

        assert result.get("success") is True, result
        db = SessionLocal()
        rows = db.query(
            __import__("core.models", fromlist=["IntegrationMetric"]).IntegrationMetric
        ).all()
        assert rows, "no metrics written"
        assert all(r.workspace_id == "ws-1" for r in rows)


# ---------------------------------------------------------------------------
# 5. ecommerce_unified_service singleton: dict passed as tenant_id
# ---------------------------------------------------------------------------


class TestEcommerceUnifiedService:
    def test_singleton_config_and_tenant_id(self):
        from integrations.ecommerce_unified_service import ecommerce_service

        assert ecommerce_service.config == {}
        assert ecommerce_service.tenant_id == "default"

    def test_sync_orders_with_pipeline(self):
        from integrations import ecommerce_unified_service as mod

        with mock.patch.object(mod, "atom_ingestion_pipeline") as m_pipe:
            svc = mod.EcommerceUnifiedService()
            result = asyncio.run(svc.sync_orders(mod.EcommercePlatform.SHOPIFY))
        assert result and result[0]["id"] == "shopify_ord_999"
        m_pipe.ingest_record.assert_called_once()

    def test_sync_orders_no_pipeline_graceful(self):
        """If the ingestion pipeline import failed (module attr None), sync
        must not blow up with NameError."""
        from integrations import ecommerce_unified_service as mod

        svc = mod.EcommerceUnifiedService()
        with mock.patch.object(mod, "atom_ingestion_pipeline", None):
            result = asyncio.run(svc.sync_orders(mod.EcommercePlatform.ETSY))
        assert isinstance(result, dict)
        assert result.get("success") is False

    def test_update_inventory_all_platforms(self):
        from integrations.ecommerce_unified_service import (
            EcommercePlatform,
            EcommerceUnifiedService,
        )

        svc = EcommerceUnifiedService()
        asyncio.run(svc.update_inventory("SKU-1", 5))
        asyncio.run(
            svc.update_inventory("SKU-1", 5, platform=EcommercePlatform.AMAZON)
        )


# ---------------------------------------------------------------------------
# 6. document_logic_service: NameError when pipeline import failed
# ---------------------------------------------------------------------------


class TestDocumentLogicService:
    def test_ingest_document_no_pipeline(self):
        """atom_ingestion_pipeline may be None after a failed import; the
        ingest must return a clean error instead of raising NameError."""
        from integrations import document_logic_service as mod

        svc = mod.DocumentLogicService()
        with mock.patch.object(mod, "atom_ingestion_pipeline", None):
            try:
                result = asyncio.run(
                    svc.ingest_document(
                        "/tmp/x.pdf", mod.DocumentType.PDF, workspace_id="ws-1"
                    )
                )
            except NameError:
                pytest.fail("NameError raised when pipeline missing")
        assert result["snippets_extracted"] == 1

    def test_execute_operation_tenant_mismatch(self):
        from integrations.document_logic_service import DocumentLogicService

        svc = DocumentLogicService(tenant_id="tenant-a")
        result = asyncio.run(
            svc.execute_operation(
                "parse_document", {}, context={"tenant_id": "tenant-b"}
            )
        )
        assert result["success"] is False

    def test_classify_document_keywords(self):
        from integrations.document_logic_service import DocumentLogicService

        svc = DocumentLogicService()
        res = asyncio.run(
            svc.execute_operation("classify_document", {"content": "This invoice is due"})
        )
        assert res["result"]["classification"] == "financial"

    def test_merge_documents_requires_paths(self):
        from integrations.document_logic_service import DocumentLogicService

        svc = DocumentLogicService()
        res = asyncio.run(svc.execute_operation("merge_documents", {}))
        assert res["success"] is False


# ---------------------------------------------------------------------------
# 7. str(e) leak sweep — client-visible response bodies
# ---------------------------------------------------------------------------


class TestStrELeaks:
    def test_workday_execute_operation_no_leak(self):
        from integrations.workday_service import WorkdayService

        svc = WorkdayService()
        with mock.patch.object(
            svc, "get_worker_profile", new=mock.AsyncMock(side_effect=ValueError("secret-token-xyz"))
        ):
            result = asyncio.run(
                svc.execute_operation("get_worker_profile", {"worker_id": "w1"})
            )
        assert result["success"] is False
        assert "secret-token-xyz" not in json.dumps(result)

    def test_webex_execute_operation_no_leak(self):
        from integrations.webex_service import WebexService

        svc = WebexService()
        with mock.patch.object(
            svc, "list_rooms", new=mock.AsyncMock(side_effect=ValueError("boom-secret"))
        ):
            result = asyncio.run(svc.execute_operation("list_rooms", {}))
        assert "boom-secret" not in json.dumps(result)

    def test_tableau_execute_operation_no_leak(self):
        from integrations.tableau_service import TableauService

        svc = TableauService()
        with mock.patch.object(
            svc, "get_workbooks", new=mock.AsyncMock(side_effect=ValueError("t-secret"))
        ):
            result = asyncio.run(
                svc.execute_operation("get_workbooks", {"access_token": "tok"})
            )
        assert "t-secret" not in json.dumps(result)

    def test_twilio_execute_operation_no_leak(self):
        from integrations.twilio_service import TwilioService

        svc = TwilioService()
        with mock.patch.object(
            svc, "send_sms", new=mock.AsyncMock(side_effect=ValueError("tw-secret"))
        ):
            result = asyncio.run(
                svc.execute_operation(
                    "send_sms", {"to": "+1", "body": "hi"}
                )
            )
        assert "tw-secret" not in json.dumps(result)

    def test_zoom_execute_operation_no_leak(self):
        from integrations.zoom_service import ZoomService

        svc = ZoomService()
        with mock.patch.object(
            svc, "list_meetings", new=mock.AsyncMock(side_effect=ValueError("z-secret"))
        ):
            result = asyncio.run(svc.execute_operation("list_meetings", {}))
        assert "z-secret" not in json.dumps(result)

    def test_github_health_no_leak(self):
        from integrations.github_service import GitHubService

        svc = GitHubService()
        with mock.patch.object(
            svc.session, "get", side_effect=ValueError("gh-secret")
        ):
            result = svc.health_check()
        assert "gh-secret" not in json.dumps(result)

    def test_github_sync_no_leak(self):
        from integrations.github_service import GitHubService

        svc = GitHubService()
        with mock.patch.object(
            svc, "get_user_repositories", side_effect=ValueError("gh-sync-secret")
        ):
            result = svc.sync_to_postgres_cache("ws-1")
        assert "gh-sync-secret" not in json.dumps(result)

    def test_gitlab_execute_operation_no_leak(self):
        from integrations.gitlab_service import GitLabService

        svc = GitLabService()
        with mock.patch.object(
            svc, "get_user", new=mock.AsyncMock(side_effect=ValueError("gl-secret"))
        ):
            result = asyncio.run(
                svc.execute_operation("get_user", {"access_token": "tok"})
            )
        assert "gl-secret" not in json.dumps(result)

    def test_notion_execute_operation_no_leak(self):
        from integrations.notion_service import NotionService

        svc = NotionService()
        with mock.patch.object(svc, "search", side_effect=ValueError("n-secret")):
            result = asyncio.run(
                svc.execute_operation("search", {"query": "q"})
            )
        assert "n-secret" not in json.dumps(result)

    def test_plaid_execute_operation_no_leak(self):
        from integrations.plaid_service import PlaidService

        svc = PlaidService()
        with mock.patch.object(
            svc, "get_accounts", new=mock.AsyncMock(side_effect=ValueError("p-secret"))
        ):
            result = asyncio.run(
                svc.execute_operation("get_accounts", {"access_token": "tok"})
            )
        assert "p-secret" not in json.dumps(result)

    def test_google_calendar_execute_operation_no_leak(self):
        from integrations.google_calendar_service import GoogleCalendarService

        svc = GoogleCalendarService()
        with mock.patch.object(
            svc, "get_events", new=mock.AsyncMock(side_effect=ValueError("gc-secret"))
        ):
            result = asyncio.run(
                svc.execute_operation("get_events", {"time_min": None})
            )
        assert "gc-secret" not in json.dumps(result)

    def test_outlook_calendar_execute_operation_no_leak(self):
        from integrations.outlook_calendar_service import OutlookCalendarService

        svc = OutlookCalendarService()
        with mock.patch.object(
            svc, "get_events", new=mock.AsyncMock(side_effect=ValueError("oc-secret"))
        ):
            result = asyncio.run(
                svc.execute_operation("get_events", {})
            )
        assert "oc-secret" not in json.dumps(result)

    def test_discord_health_no_leak(self):
        from integrations.discord_service import DiscordService

        svc = DiscordService()
        # force exception path
        with mock.patch.object(
            svc, "health_check", wraps=svc.health_check
        ):
            pass
        result = asyncio.run(svc.health_check())
        assert "secret" not in json.dumps(result)

    def test_document_logic_execute_operation_no_leak(self):
        from integrations.document_logic_service import DocumentLogicService

        svc = DocumentLogicService()
        with mock.patch.object(
            svc, "_parse_document",
            new=mock.AsyncMock(side_effect=ValueError("dl-secret")),
        ):
            result = asyncio.run(
                svc.execute_operation(
                    "parse_document",
                    {"file_path": "a.pdf", "doc_type": "pdf", "workspace_id": "w"},
                )
            )
        assert "dl-secret" not in json.dumps(result)

    def test_google_drive_list_files_no_leak(self):
        from integrations.google_drive_service import GoogleDriveService

        svc = GoogleDriveService()
        with mock.patch.object(
            svc, "_drive_get",
            new=mock.AsyncMock(side_effect=ValueError("gd-secret")),
        ):
            result = asyncio.run(
                svc.list_files("tok")
            )
        assert "gd-secret" not in json.dumps(result)

    def test_onedrive_search_no_leak(self):
        from integrations.onedrive_service import OneDriveService

        svc = OneDriveService()
        with mock.patch.object(
            svc, "_graph_get",
            new=mock.AsyncMock(side_effect=ValueError("od-secret")),
        ):
            result = asyncio.run(svc.search_files("tok", "query"))
        assert "od-secret" not in json.dumps(result)

    def test_universal_webhook_bridge_error_no_leak(self):
        from integrations.universal_webhook_bridge import UniversalWebhookBridge

        bridge = UniversalWebhookBridge()
        with mock.patch.object(
            bridge, "_standardize_message",
            side_effect=ValueError("ub-secret"),
        ):
            result = asyncio.run(
                bridge.process_incoming_message("slack", {"type": "message"})
            )
        assert "ub-secret" not in json.dumps(result)

    def test_chat_routes_health_no_leak(self):
        from integrations.chat_routes import chat_health_check

        with mock.patch(
            "integrations.chat_routes.chat_orchestrator",
            mock.MagicMock(side_effect=ValueError("chat-secret")),
        ):
            import asyncio as _a

            result = _a.run(chat_health_check())
        assert "chat-secret" not in json.dumps(result)


# ---------------------------------------------------------------------------
# 8. webhook_renewal_routes health leak
# ---------------------------------------------------------------------------


class TestWebhookRenewalRoutes:
    def test_health_no_str_leak(self):
        from integrations import webhook_renewal_routes as mod

        class Boom:
            def health_check(self):
                raise ValueError("renewal-secret-42")

        with mock.patch.object(mod, "_get_service", return_value=Boom()):
            result = asyncio.run(mod.health())
        assert result["healthy"] is False
        assert "renewal-secret-42" not in json.dumps(result)


# ---------------------------------------------------------------------------
# 9. workflow_automation_routes: leaks + whatsapp automation
# ---------------------------------------------------------------------------


class TestWorkflowAutomationRoutes:
    def test_whatsapp_unsupported_type_no_leak(self):
        from integrations import workflow_automation_routes as mod

        result = asyncio.run(
            mod.whatsapp_workflow_automation({"type": "bogus_type", "parameters": {}})
        )
        assert result["success"] is False
        assert "bogus_type" not in json.dumps(result).replace(
            result.get("error", ""), ""
        )

    def test_whatsapp_customer_support(self):
        from integrations import workflow_automation_routes as mod

        result = asyncio.run(
            mod.whatsapp_workflow_automation(
                {"type": "customer_support", "parameters": {}}
            )
        )
        assert result["success"] is True
        assert result["result"]["status"] == "configured"

    def test_test_step_analytics_path(self):
        from integrations import workflow_automation_routes as mod

        result = asyncio.run(
            mod.test_workflow_step(
                mod.TestStepRequest(
                    service="Slack",
                    action="send",
                    workflow_id="wf-1",
                    step_id="step-1",
                )
            )
        )
        assert result.success is True

    def test_test_step_error_no_leak(self):
        from integrations import workflow_automation_routes as mod

        with mock.patch(
            "analytics.collector.AsyncAnalyticsCollector.get_instance",
            side_effect=ValueError("analytics-secret"),
        ):
            result = asyncio.run(
                mod.test_workflow_step(
                    mod.TestStepRequest(
                        service="Slack",
                        action="send",
                        workflow_id="wf-1",
                        step_id="step-1",
                    )
                )
            )
        assert "analytics-secret" not in json.dumps(result.model_dump())


# ---------------------------------------------------------------------------
# 10. ai_routes auth
# ---------------------------------------------------------------------------


class TestAIRoutesAuth:
    def _client(self, auth: bool):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from core.auth import get_current_user
        from integrations.ai_routes import router

        app = FastAPI()
        if auth:
            from core.auth import create_access_token
            from core.models import User

            # build a minimal fake user
            user = User(
                id="user-1", username="tester", email="t@t.com",
                status="active", role="admin",
            )
            # default override: allow access
            def fake_get_current_user():
                return user

            app.dependency_overrides[get_current_user] = fake_get_current_user
        app.include_router(router)
        return TestClient(app)

    def test_nlp_parse_requires_auth(self):
        client = self._client(auth=False)
        resp = client.post("/ai/nlp/parse", json={"command": "hello", "user_id": "u1"})
        assert resp.status_code == 401

    def test_data_ingest_requires_auth(self):
        client = self._client(auth=False)
        resp = client.post("/ai/data/ingest", json={"platform": "slack", "data": []})
        assert resp.status_code == 401

    def test_workflow_create_requires_auth(self):
        client = self._client(auth=False)
        resp = client.post(
            "/ai/automation/workflows",
            json={
                "name": "w",
                "description": "d",
                "trigger": {"type": "manual"},
                "actions": [],
            },
        )
        assert resp.status_code == 401

    def test_authenticated_nlp_parse_works(self):
        client = self._client(auth=True)
        with mock.patch(
            "integrations.ai_routes.nlp_engine.parse_command"
        ) as m_parse, mock.patch(
            "integrations.ai_routes.nlp_engine.generate_response"
        ) as m_gen:
            m_parse.return_value = mock.MagicMock()
            m_gen.return_value = {
                "success": True,
                "confidence": 0.9,
                "command_type": "query",
                "platforms": [],
                "entities": [],
                "parameters": {},
                "message": "ok",
                "suggested_actions": [],
            }
            resp = client.post(
                "/ai/nlp/parse", json={"command": "hello", "user_id": "u1"}
            )
        assert resp.status_code == 200
        assert resp.json()["success"] is True


# ---------------------------------------------------------------------------
# 11. workflow_automation_routes auth
# ---------------------------------------------------------------------------


class TestWorkflowAutomationRoutesAuth:
    def _client(self, auth: bool):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from core.auth import get_current_user
        from integrations.workflow_automation_routes import router

        app = FastAPI()
        if auth:
            def fake_get_current_user():
                return mock.MagicMock(id="user-1")

            app.dependency_overrides[get_current_user] = fake_get_current_user
        app.include_router(router)
        return TestClient(app)

    def test_test_step_requires_auth(self):
        client = self._client(auth=False)
        resp = client.post(
            "/workflows/test-step",
            json={"service": "slack", "action": "send"},
        )
        assert resp.status_code == 401

    def test_whatsapp_automate_requires_auth(self):
        client = self._client(auth=False)
        resp = client.post(
            "/workflows/whatsapp/automate", json={"type": "customer_support"}
        )
        assert resp.status_code == 401

    def test_enhanced_intelligence_requires_auth(self):
        client = self._client(auth=False)
        resp = client.post(
            "/workflows/enhanced/intelligence/analyze", json={"user_input": "x"}
        )
        assert resp.status_code == 401
