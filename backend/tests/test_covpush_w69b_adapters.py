"""Coverage wave W69b — Meta Business + Universal OAuth routes + Slack adapters + Node bridge.

Targets (>=95% statement coverage, standalone):
- integrations/meta_business_service.py       (was 34% — import-only from other suites)
- integrations/universal/routes.py            (was 0% — never imported by any test)
- integrations/adapters/slack_adapter.py      (was 36% — init-only)
- integrations/bridge/node_bridge_service.py  (was 0% — sys.modules-mocked everywhere, never tested)
- core/communication/adapters/slack.py        (was 33% — init-only smoke)

Pattern: pure unit tests, mocked deps, ZERO LLM spend, no network (httpx/slack_sdk
mocked), no DB. FastAPI routes tested via TestClient with get_current_user
dependency-overridden. Patches target the REAL module names (no `backend.`
prefix).

Bugs found + fixed in the assigned modules (regression tests below):
1. meta_business_service.py:15-19 — `atom_ingestion_pipeline` and the phantom
   top-level `ai_enhanced_service` import shared ONE try/except. ai_enhanced_service
   does not exist anywhere in the repo, so the except branch ALWAYS fired,
   logging a false "Core services not available" warning on every import, and
   `ingest_communications`'s pipeline dependency was coupled to an unrelated
   phantom module (NameError if the pipeline import ever failed). Split into two
   independent guarded imports — test_import_binds_pipeline_without_warning /
   test_ingest_communications_reaches_pipeline.
"""
import asyncio
import hashlib
import hmac
import logging
import sys
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from core.integration_service import IntegrationErrorCode, OperationResult
from integrations.meta_business_service import MetaBusinessService, MetaPlatform
from integrations.universal.auth_handler import OAuthState
from integrations.adapters.slack_adapter import SlackAdapter as UpstreamSlackAdapter
from integrations.bridge.node_bridge_service import NodeBridgeService
from core.communication.adapters.slack import SlackAdapter as CommunicationSlackAdapter

# ---------------------------------------------------------------------------
# integrations/meta_business_service.py
# ---------------------------------------------------------------------------


class TestMetaBusinessServiceInit:
    def test_init_defaults(self):
        svc = MetaBusinessService()
        assert svc.tenant_id == "default"
        assert svc.access_token is None
        assert svc.app_id is None
        assert svc.config == {}

    def test_init_with_config(self):
        svc = MetaBusinessService(tenant_id="t1", config={"meta_access_token": "tok", "meta_app_id": "app"})
        assert svc.tenant_id == "t1"
        assert svc.access_token == "tok"
        assert svc.app_id == "app"

    def test_init_preserves_passed_config(self):
        cfg = {"meta_access_token": "tok"}
        svc = MetaBusinessService(config=cfg)
        assert svc.config is cfg

    def test_import_binds_pipeline_without_warning(self):
        """Regression: the phantom ai_enhanced_service import must not poison
        the atom_ingestion_pipeline import (was: same try block -> every import
        logged a false 'Core services not available' warning)."""
        import integrations.meta_business_service as mod
        records = []
        handler = logging.StreamHandler()
        handler.emit = lambda rec: records.append(rec)
        root = logging.getLogger()
        root.addHandler(handler)
        try:
            import importlib
            reloaded = importlib.reload(mod)
        finally:
            root.removeHandler(handler)
        assert hasattr(reloaded, "atom_ingestion_pipeline")
        assert not any("not available for Meta Business" in r.getMessage() for r in records)


    def test_pipeline_import_failure_logs_warning(self, monkeypatch):
        """Cover the pipeline ImportError branch: a missing pipeline module must
        log the fallback warning instead of silently importing."""
        import importlib.util
        import types
        import integrations.meta_business_service as mod
        stub = types.ModuleType("integrations.atom_ingestion_pipeline")
        monkeypatch.setitem(sys.modules, "integrations.atom_ingestion_pipeline", stub)
        spec = importlib.util.spec_from_file_location("meta_business_fresh", mod.__file__)
        fresh = importlib.util.module_from_spec(spec)
        records = []
        handler = logging.StreamHandler()
        handler.emit = lambda rec: records.append(rec)
        root = logging.getLogger()
        root.addHandler(handler)
        try:
            spec.loader.exec_module(fresh)
        finally:
            root.removeHandler(handler)
        assert not hasattr(fresh, "atom_ingestion_pipeline")
        assert any("not available for Meta Business" in r.getMessage() for r in records)


class TestMetaBusinessServiceCapabilities:
    def test_get_capabilities(self):
        caps = MetaBusinessService().get_capabilities()
        assert caps["required_params"] == ["meta_access_token", "meta_app_id"]
        assert caps["supports_webhooks"] is True
        assert {op["id"] for op in caps["operations"]} == {
            "send_message", "get_ad_insights", "ingest_communications",
            "sync_to_postgres_cache", "full_sync",
        }

    def test_health_check_healthy(self):
        svc = MetaBusinessService(config={"meta_access_token": "t", "meta_app_id": "a"})
        health = svc.health_check()
        assert health["ok"] is True
        assert health["status"] == "healthy"
        assert "initialized" in health["message"]
        assert health["timestamp"]

    def test_health_check_unhealthy(self):
        health = MetaBusinessService().health_check()
        assert health["ok"] is False
        assert health["status"] == "unhealthy"
        assert "Missing credentials" in health["message"]


class TestMetaBusinessServiceExecute:
    def test_execute_tenant_mismatch(self):
        svc = MetaBusinessService()
        result = asyncio.run(svc.execute_operation("send_message", {}, context={"tenant_id": "other"}))
        assert result == {"success": False, "error": "Tenant ID mismatch"}

    def test_execute_send_message(self):
        svc = MetaBusinessService()
        result = asyncio.run(svc.execute_operation(
            "send_message", {"platform": "instagram", "recipient_id": "u1", "text": "hi"},
            context={"tenant_id": "default"},
        ))
        assert result == {"success": True, "result": {"message_sent": True}}

    def test_execute_send_message_default_platform(self):
        svc = MetaBusinessService()
        result = asyncio.run(svc.execute_operation("send_message", {"recipient_id": "u1", "text": "hi"}))
        assert result["success"] is True

    def test_execute_get_ad_insights(self):
        svc = MetaBusinessService()
        result = asyncio.run(svc.execute_operation("get_ad_insights", {}))
        assert result["success"] is True
        assert result["result"]["spend"] == 1250.0

    def test_execute_ingest_communications(self):
        svc = MetaBusinessService()
        with patch.object(svc, "ingest_communications", AsyncMock()) as ingest:
            result = asyncio.run(svc.execute_operation("ingest_communications", {"page_id": "p1"}))
        ingest.assert_awaited_once_with("p1")
        assert result == {"success": True, "result": {"ingested": True}}

    def test_execute_sync_to_postgres_cache(self):
        svc = MetaBusinessService()
        with patch.object(svc, "sync_to_postgres_cache", AsyncMock(return_value={"success": True, "metrics_synced": 5})) as sync:
            result = asyncio.run(svc.execute_operation("sync_to_postgres_cache", {"workspace_id": "w1"}))
        sync.assert_awaited_once_with("w1")
        assert result == {"success": True, "result": {"success": True, "metrics_synced": 5}}

    def test_execute_full_sync(self):
        svc = MetaBusinessService()
        with patch.object(svc, "full_sync", AsyncMock(return_value={"success": True})) as fs:
            result = asyncio.run(svc.execute_operation("full_sync", {"workspace_id": "w1"}))
        fs.assert_awaited_once_with("w1")
        assert result["success"] is True

    def test_execute_unknown_operation(self):
        svc = MetaBusinessService()
        result = asyncio.run(svc.execute_operation("nope", {}))
        assert result == {"success": False, "error": "Unknown operation: nope"}

    def test_execute_exception_caught(self):
        svc = MetaBusinessService()
        with patch.object(svc, "send_message", AsyncMock(side_effect=RuntimeError("boom"))):
            result = asyncio.run(svc.execute_operation("send_message", {"recipient_id": "u1", "text": "hi"}))
        assert result == {"success": False, "error": "boom"}

    def test_execute_invalid_platform_value(self):
        svc = MetaBusinessService()
        result = asyncio.run(svc.execute_operation("send_message", {"platform": "tiktok", "recipient_id": "u1", "text": "hi"}))
        assert result["success"] is False
        assert "tiktok" in result["error"]

    def test_execute_missing_required_param(self):
        svc = MetaBusinessService()
        result = asyncio.run(svc.execute_operation("send_message", {"platform": "facebook"}))
        assert result["success"] is False
        assert "'recipient_id'" in result["error"]


class TestMetaBusinessServiceDirect:
    def test_send_message_returns_true(self):
        result = asyncio.run(MetaBusinessService().send_message(MetaPlatform.MESSENGER, "u1", "hi"))
        assert result is True

    def test_get_ad_insights_returns_metrics(self):
        insights = asyncio.run(MetaBusinessService().get_ad_insights("acct", "last_7d"))
        assert insights["roas"] == 3.8
        assert insights["impressions"] == 50000

    def test_ingest_communications_reaches_pipeline(self):
        """Regression: ingest_communications must invoke the ingestion pipeline
        (was coupled to the phantom ai_enhanced_service import)."""
        import integrations.meta_business_service as mod
        svc = MetaBusinessService()
        with patch.object(mod, "atom_ingestion_pipeline", MagicMock()) as pipeline:
            asyncio.run(svc.ingest_communications("page_42"))
        pipeline.ingest_record.assert_called_once()
        kwargs = pipeline.ingest_record.call_args.kwargs
        assert kwargs["app_type"] == "meta_business"
        assert kwargs["record_type"] == "communication"
        assert kwargs["data"]["from"]["id"] == "user_123"


class _FakeQuery:
    def __init__(self, existing):
        self._existing = existing

    def filter_by(self, **_kw):
        return self

    def first(self):
        return self._existing


class _FakeDB:
    def __init__(self, existing=None, commit_error=None):
        self.existing = existing
        self.commit_error = commit_error
        self.added = []
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def query(self, _model):
        return _FakeQuery(self.existing)

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        if self.commit_error:
            raise self.commit_error
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


class _Metric:
    """Real stand-in for core.models.IntegrationMetric (records kwargs)."""

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class TestMetaBusinessServicePostgresSync:
    def test_sync_success_creates_metrics(self):
        db = _FakeDB(existing=None)
        with patch("core.database.SessionLocal", return_value=db):
            with patch("core.models.IntegrationMetric", _Metric):
                result = asyncio.run(MetaBusinessService().sync_to_postgres_cache("w9"))
        assert result == {"success": True, "metrics_synced": 5}
        assert db.committed is True
        assert len(db.added) == 5
        assert db.added[0].metric_key == "meta_ad_spend"
        assert db.added[0].value == 1250.0
        assert db.added[0].unit == "currency"
        assert db.added[0].tenant_id == "w9"
        assert db.added[0].integration_type == "meta_business"
        assert db.added[4].unit == "ratio"

    def test_sync_updates_existing_metrics(self):
        existing = MagicMock()
        db = _FakeDB(existing=existing)
        with patch("core.database.SessionLocal", return_value=db):
            with patch("core.models.IntegrationMetric", _Metric):
                result = asyncio.run(MetaBusinessService().sync_to_postgres_cache("w9"))
        assert result["success"] is True
        assert db.added == []
        assert existing.last_synced_at is not None

    def test_sync_commit_error_rolls_back(self):
        db = _FakeDB(existing=None, commit_error=RuntimeError("commit fail"))
        with patch("core.database.SessionLocal", return_value=db):
            with patch("core.models.IntegrationMetric", MagicMock()):
                result = asyncio.run(MetaBusinessService().sync_to_postgres_cache("w9"))
        assert result == {"success": False, "error": "commit fail"}
        assert db.rolled_back is True

    def test_sync_session_factory_error(self):
        with patch("core.database.SessionLocal", side_effect=RuntimeError("no db")):
            result = asyncio.run(MetaBusinessService().sync_to_postgres_cache("w9"))
        assert result == {"success": False, "error": "no db"}

    def test_full_sync_envelope(self):
        svc = MetaBusinessService()
        with patch.object(svc, "sync_to_postgres_cache", AsyncMock(return_value={"success": True, "metrics_synced": 5})):
            result = asyncio.run(svc.full_sync("w9"))
        assert result["success"] is True
        assert result["workspace_id"] == "w9"
        assert result["postgres_cache"]["metrics_synced"] == 5
        assert result["timestamp"]


# ---------------------------------------------------------------------------
# integrations/universal/routes.py
# ---------------------------------------------------------------------------

def _make_app():
    from integrations.universal import routes
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[routes.get_current_user] = lambda: SimpleNamespace(id="user-9")
    return app, routes


def _make_state(service_id="@activepieces/piece-slack", user_id="user-9"):
    return OAuthState(integration_type="activepieces", service_id=service_id, user_id=user_id)


class TestUniversalRoutesAuthorize:
    def test_authorize_success(self):
        app, routes = _make_app()
        config = {"auth_url": "https://provider/auth", "client_id": "cid", "scopes": ["a", "b"]}
        with patch.object(routes, "get_oauth_config", return_value=config):
            with patch.object(routes.universal_auth, "generate_oauth_url", return_value="https://provider/auth?x=1") as gen:
                resp = TestClient(app).get("/api/v1/integrations/universal/authorize",
                                           params={"service_id": "s1", "integration_type": "activepieces", "redirect_path": "/home"})
        assert resp.status_code == 200
        assert resp.json() == {"url": "https://provider/auth?x=1"}
        assert gen.call_args.kwargs["auth_url"] == "https://provider/auth"
        state = gen.call_args.kwargs["state_payload"]
        assert state.user_id == "user-9"
        assert state.redirect_path == "/home"
        assert state.integration_type == "activepieces"

    def test_authorize_default_integration_type(self):
        app, routes = _make_app()
        with patch.object(routes, "get_oauth_config", return_value={"auth_url": "u", "client_id": "c", "scopes": []}):
            with patch.object(routes.universal_auth, "generate_oauth_url", return_value="u"):
                resp = TestClient(app).get("/api/v1/integrations/universal/authorize", params={"service_id": "s1"})
        assert resp.status_code == 200

    def test_authorize_no_config(self):
        app, routes = _make_app()
        with patch.object(routes, "get_oauth_config", return_value=None):
            resp = TestClient(app).get("/api/v1/integrations/universal/authorize", params={"service_id": "unknown"})
        assert resp.status_code == 400


class TestUniversalRoutesCallback:
    def test_callback_success(self):
        app, routes = _make_app()
        state = _make_state()
        config = {
            "token_url": "https://provider/token",
            "client_id": "cid",
            "client_secret": "sec",
            "auth_url": "u",
            "scopes": [],
        }
        exchange_resp = MagicMock()
        exchange_resp.status_code = 200
        exchange_resp.json.return_value = {"access_token": "tok", "expires_in": 3600}
        client = MagicMock()
        client.post = AsyncMock(return_value=exchange_resp)
        async_client = MagicMock()
        async_client.__aenter__.return_value = client
        connection = SimpleNamespace(connection_name="slack Connection")
        with patch.object(routes.universal_auth, "handle_callback", AsyncMock(return_value={"state": state, "callback_url": "http://cb"})):
            with patch.object(routes, "get_oauth_config", return_value=config):
                with patch("httpx.AsyncClient", return_value=async_client):
                    with patch.object(routes, "connection_service") as conn_svc:
                        conn_svc.save_connection.return_value = connection
                        with patch("core.agent_world_model.WorldModelService") as wm_cls:
                            wm = MagicMock()
                            wm.record_experience = AsyncMock()
                            wm_cls.return_value = wm
                            resp = TestClient(app).get("/api/v1/integrations/universal/callback",
                                                       params={"code": "code1", "state": "enc"})
        assert resp.status_code == 200
        assert "AUTH_SUCCESS" in resp.text
        conn_svc.save_connection.assert_called_once()
        assert conn_svc.save_connection.call_args.kwargs["user_id"] == "user-9"
        assert conn_svc.save_connection.call_args.kwargs["credentials"]["access_token"] == "tok"
        client.post.assert_awaited_once()
        wm.record_experience.assert_awaited_once()
        assert wm_cls.call_args.kwargs == {"workspace_id": "default"}

    def test_callback_world_model_failure_ignored(self):
        app, routes = _make_app()
        state = _make_state()
        config = {"token_url": "u", "client_id": "c", "client_secret": "s"}
        exchange_resp = MagicMock()
        exchange_resp.status_code = 200
        exchange_resp.json.return_value = {"access_token": "tok"}
        client = MagicMock()
        client.post = AsyncMock(return_value=exchange_resp)
        async_client = MagicMock()
        async_client.__aenter__.return_value = client
        with patch.object(routes.universal_auth, "handle_callback", AsyncMock(return_value={"state": state, "callback_url": "u"})):
            with patch.object(routes, "get_oauth_config", return_value=config):
                with patch("httpx.AsyncClient", return_value=async_client):
                    with patch.object(routes, "connection_service") as conn_svc:
                        conn_svc.save_connection.return_value = SimpleNamespace(connection_name="c1")
                        with patch("core.agent_world_model.WorldModelService") as wm_cls:
                            wm = MagicMock()
                            wm.record_experience = AsyncMock(side_effect=RuntimeError("wm down"))
                            wm_cls.return_value = wm
                            resp = TestClient(app).get("/api/v1/integrations/universal/callback",
                                                       params={"code": "code1", "state": "enc"})
        assert resp.status_code == 200
        assert "AUTH_SUCCESS" in resp.text

    def test_callback_token_exchange_failure(self):
        app, routes = _make_app()
        state = _make_state()
        config = {"token_url": "u", "client_id": "c", "client_secret": "s"}
        exchange_resp = MagicMock()
        exchange_resp.status_code = 400
        exchange_resp.text = "bad request"
        client = MagicMock()
        client.post = AsyncMock(return_value=exchange_resp)
        async_client = MagicMock()
        async_client.__aenter__.return_value = client
        with patch.object(routes.universal_auth, "handle_callback", AsyncMock(return_value={"state": state, "callback_url": "u"})):
            with patch.object(routes, "get_oauth_config", return_value=config):
                with patch("httpx.AsyncClient", return_value=async_client):
                    resp = TestClient(app, raise_server_exceptions=False).get(
                        "/api/v1/integrations/universal/callback", params={"code": "c", "state": "e"})
        assert resp.status_code == 500
        assert "Authentication failed" in resp.text

    def test_callback_config_lost(self):
        app, routes = _make_app()
        state = _make_state()
        with patch.object(routes.universal_auth, "handle_callback", AsyncMock(return_value={"state": state, "callback_url": "u"})):
            with patch.object(routes, "get_oauth_config", return_value=None):
                resp = TestClient(app, raise_server_exceptions=False).get(
                    "/api/v1/integrations/universal/callback", params={"code": "c", "state": "e"})
        assert resp.status_code == 500
        assert "Authentication failed" in resp.text

    def test_callback_invalid_state(self):
        app, routes = _make_app()
        with patch.object(routes.universal_auth, "handle_callback", AsyncMock(side_effect=ValueError("bad state"))):
            resp = TestClient(app, raise_server_exceptions=False).get(
                "/api/v1/integrations/universal/callback", params={"code": "c", "state": "e"})
        assert resp.status_code == 500
        assert "Authentication failed" in resp.text


class TestUniversalRoutesInit:
    def test_init_redirects_to_authorize(self):
        app, routes = _make_app()
        resp = TestClient(app).get("/api/v1/integrations/universal/init", params={"service_id": "s1"})
        assert resp.status_code == 200
        assert resp.json() == {"message": "Use /api/v1/integrations/universal/authorize"}

    def test_init_default_integration_type(self):
        app, routes = _make_app()
        resp = TestClient(app).get("/api/v1/integrations/universal/init", params={"service_id": "s1", "integration_type": "activepieces"})
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# integrations/adapters/slack_adapter.py (upstream orchestrator adapter)
# ---------------------------------------------------------------------------


def _make_upstream_adapter(**kwargs):
    with patch("integrations.adapters.slack_adapter.SlackUnifiedService") as svc_cls:
        adapter = UpstreamSlackAdapter(config=kwargs)
    service = svc_cls.return_value
    return adapter, service


class TestUpstreamSlackAdapterBasics:
    def test_init_defaults(self):
        with patch("integrations.adapters.slack_adapter.SlackUnifiedService"):
            adapter = UpstreamSlackAdapter()
        assert adapter.tenant_id == "default"
        assert adapter.workspace_id == "default"

    def test_init_tenant(self):
        with patch("integrations.adapters.slack_adapter.SlackUnifiedService"):
            adapter = UpstreamSlackAdapter(tenant_id="t1")
        assert adapter.tenant_id == "t1"
        assert adapter.workspace_id == "t1"

    def test_get_capabilities(self):
        adapter, _ = _make_upstream_adapter()
        caps = adapter.get_capabilities()
        assert caps["required_params"] == ["bot_token"]
        assert caps["operations"] == ["post_message", "list_channels", "get_channel_history", "add_reaction", "update_message"]

    def test_health_check(self):
        adapter, _ = _make_upstream_adapter()
        health = adapter.health_check()
        assert health == {"healthy": True, "message": "SlackAdapter ready", "last_check": None}

    def test_get_supported_operations(self):
        adapter, _ = _make_upstream_adapter()
        assert "update_message" in adapter.get_supported_operations()


class TestUpstreamSlackAdapterExecute:
    def test_missing_token(self):
        adapter, _ = _make_upstream_adapter()
        result = asyncio.run(adapter.execute_operation("post_message", {"channel_id": "c", "text": "hi"}))
        assert isinstance(result, OperationResult)
        assert result.success is False
        assert result.error == IntegrationErrorCode.AUTH_EXPIRED

    def test_post_message_missing_params(self):
        adapter, _ = _make_upstream_adapter(access_token="tok")
        result = asyncio.run(adapter.execute_operation("post_message", {"channel_id": "c"}))
        assert result.success is False
        assert result.error == IntegrationErrorCode.INVALID_PARAMETERS

    def test_post_message_success(self):
        adapter, service = _make_upstream_adapter(access_token="tok")
        service.post_message = AsyncMock(return_value={"ok": True})
        result = asyncio.run(adapter.execute_operation(
            "post_message", {"channel_id": "c", "text": "hi", "thread_ts": "1.2", "blocks": [{"type": "section"}]}))
        assert result.success is True
        assert result.data == {"ok": True}
        service.post_message.assert_awaited_once_with("tok", "c", "hi", thread_ts="1.2", blocks=[{"type": "section"}])

    def test_list_channels_success(self):
        adapter, service = _make_upstream_adapter(access_token="tok")
        service.list_channels = AsyncMock(return_value=[{"id": "c1"}])
        result = asyncio.run(adapter.execute_operation("list_channels", {"types": "public_channel"}))
        assert result.success is True
        assert result.data == {"channels": [{"id": "c1"}]}
        service.list_channels.assert_awaited_once_with("tok", types="public_channel")

    def test_list_channels_default_types(self):
        adapter, service = _make_upstream_adapter(access_token="tok")
        service.list_channels = AsyncMock(return_value=[])
        result = asyncio.run(adapter.execute_operation("list_channels", {}))
        assert result.success is True
        service.list_channels.assert_awaited_once_with("tok", types="public_channel,private_channel")

    def test_get_channel_history_success(self):
        adapter, service = _make_upstream_adapter(access_token="tok")
        service.get_channel_history = AsyncMock(return_value={"messages": []})
        result = asyncio.run(adapter.execute_operation("get_channel_history", {"channel_id": "c", "limit": 50}))
        assert result.success is True
        service.get_channel_history.assert_awaited_once_with("tok", "c", limit=50)

    def test_get_channel_history_default_limit(self):
        adapter, service = _make_upstream_adapter(access_token="tok")
        service.get_channel_history = AsyncMock(return_value={})
        result = asyncio.run(adapter.execute_operation("get_channel_history", {"channel_id": "c"}))
        assert result.success is True
        service.get_channel_history.assert_awaited_once_with("tok", "c", limit=100)

    def test_add_reaction_success(self):
        adapter, service = _make_upstream_adapter(access_token="tok")
        service.add_reaction = AsyncMock(return_value={"ok": True})
        result = asyncio.run(adapter.execute_operation(
            "add_reaction", {"channel_id": "c", "timestamp": "1.0", "reaction": "thumbsup"}))
        assert result.success is True
        service.add_reaction.assert_awaited_once_with("tok", "c", "1.0", "thumbsup")

    def test_unknown_operation(self):
        adapter, _ = _make_upstream_adapter(access_token="tok")
        result = asyncio.run(adapter.execute_operation("explode", {}))
        assert result.success is False
        assert result.error == IntegrationErrorCode.NOT_FOUND

    def test_slack_error_maps_to_api_error(self):
        from integrations.slack_service_unified import SlackError
        adapter, service = _make_upstream_adapter(access_token="tok")
        service.post_message = AsyncMock(side_effect=SlackError("slack down"))
        result = asyncio.run(adapter.execute_operation("post_message", {"channel_id": "c", "text": "hi"}))
        assert result.success is False
        assert result.error == IntegrationErrorCode.API_ERROR
        assert result.message == "slack down"

    def test_generic_exception_maps_to_execution_exception(self):
        adapter, service = _make_upstream_adapter(access_token="tok")
        service.post_message = AsyncMock(side_effect=RuntimeError("bad"))
        result = asyncio.run(adapter.execute_operation("post_message", {"channel_id": "c", "text": "hi"}))
        assert result.success is False
        assert result.error == IntegrationErrorCode.EXECUTION_EXCEPTION

    def test_token_from_parameters(self):
        adapter, service = _make_upstream_adapter()
        service.list_channels = AsyncMock(return_value=[])
        result = asyncio.run(adapter.execute_operation("list_channels", {"access_token": "paramtok"}))
        assert result.success is True
        service.list_channels.assert_awaited_once_with("paramtok", types="public_channel,private_channel")


# ---------------------------------------------------------------------------
# integrations/bridge/node_bridge_service.py
# ---------------------------------------------------------------------------

def _make_node_bridge():
    client = AsyncMock()
    async_client = MagicMock(return_value=client)
    with patch("integrations.bridge.node_bridge_service.httpx.AsyncClient", async_client):
        service = NodeBridgeService()
    return service, async_client, client


class TestNodeBridgeInit:
    def test_default_url(self):
        service, async_client, _ = _make_node_bridge()
        assert service.node_url == "http://localhost:3003"
        assert async_client.call_count == 1

    def test_env_url(self, monkeypatch):
        monkeypatch.setenv("NODE_ENGINE_URL", "http://engine:9999")
        service, async_client, _ = _make_node_bridge()
        assert service.node_url == "http://engine:9999"
        async_client.assert_called_once_with(base_url="http://engine:9999", timeout=30.0)

    def test_initial_cache_state(self):
        service, _, _ = _make_node_bridge()
        assert service._catalog_cache == []
        assert service._cache_ttl.total_seconds() == 300


class TestNodeBridgeHealth:
    def test_health_ok(self):
        service, _, client = _make_node_bridge()
        resp = MagicMock()
        client.get = AsyncMock(return_value=resp)
        assert asyncio.run(service.get_health()) is True
        client.get.assert_awaited_once_with("/health")
        resp.raise_for_status.assert_called_once()

    def test_health_error(self):
        service, _, client = _make_node_bridge()
        client.get = AsyncMock(side_effect=RuntimeError("conn refused"))
        assert asyncio.run(service.get_health()) is False


class TestNodeBridgeCatalog:
    def test_fetch_success_caches(self):
        service, _, client = _make_node_bridge()
        resp = MagicMock()
        resp.json.return_value = [{"name": "slack"}]
        client.get = AsyncMock(return_value=resp)
        pieces = asyncio.run(service.get_catalog())
        assert pieces == [{"name": "slack"}]
        assert service._catalog_cache == [{"name": "slack"}]
        assert service._catalog_last_updated is not None
        client.get.assert_awaited_once_with("/pieces")

    def test_cache_hit_skips_fetch(self):
        from datetime import datetime, timezone
        service, _, client = _make_node_bridge()
        service._catalog_cache = [{"name": "cached"}]
        service._catalog_last_updated = datetime.now(timezone.utc)
        client.get = AsyncMock()
        pieces = asyncio.run(service.get_catalog())
        assert pieces == [{"name": "cached"}]
        client.get.assert_not_called()

    def test_force_refresh_bypasses_cache(self):
        from datetime import datetime, timezone
        service, _, client = _make_node_bridge()
        service._catalog_cache = [{"name": "cached"}]
        service._catalog_last_updated = datetime.now(timezone.utc)
        resp = MagicMock()
        resp.json.return_value = [{"name": "fresh"}]
        client.get = AsyncMock(return_value=resp)
        pieces = asyncio.run(service.get_catalog(force_refresh=True))
        assert pieces == [{"name": "fresh"}]
        client.get.assert_awaited_once_with("/pieces")

    def test_stale_cache_refetches(self):
        from datetime import datetime, timedelta, timezone
        service, _, client = _make_node_bridge()
        service._catalog_cache = [{"name": "stale"}]
        service._catalog_last_updated = datetime.now(timezone.utc) - timedelta(minutes=10)
        resp = MagicMock()
        resp.json.return_value = [{"name": "fresh"}]
        client.get = AsyncMock(return_value=resp)
        pieces = asyncio.run(service.get_catalog())
        assert pieces == [{"name": "fresh"}]

    def test_fetch_error_returns_empty(self):
        service, _, client = _make_node_bridge()
        client.get = AsyncMock(side_effect=RuntimeError("down"))
        assert asyncio.run(service.get_catalog()) == []
        assert service._catalog_cache == []


class TestNodeBridgePieceDetails:
    def test_details_success(self):
        service, _, client = _make_node_bridge()
        resp = MagicMock()
        resp.json.return_value = {"name": "slack", "version": "1.0"}
        client.get = AsyncMock(return_value=resp)
        details = asyncio.run(service.get_piece_details("slack"))
        assert details == {"name": "slack", "version": "1.0"}
        client.get.assert_awaited_once_with("/pieces/slack")

    def test_details_404_returns_none(self):
        import httpx
        service, _, client = _make_node_bridge()
        resp = MagicMock()
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404", request=httpx.Request("GET", "/pieces/nope"), response=httpx.Response(404))
        client.get = AsyncMock(return_value=resp)
        assert asyncio.run(service.get_piece_details("nope")) is None

    def test_details_5xx_returns_none(self):
        import httpx
        service, _, client = _make_node_bridge()
        resp = MagicMock()
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500", request=httpx.Request("GET", "/pieces/x"), response=httpx.Response(500))
        client.get = AsyncMock(return_value=resp)
        assert asyncio.run(service.get_piece_details("x")) is None

    def test_details_generic_error_returns_none(self):
        service, _, client = _make_node_bridge()
        resp = MagicMock()
        resp.raise_for_status.side_effect = ValueError("garbage")
        client.get = AsyncMock(return_value=resp)
        assert asyncio.run(service.get_piece_details("x")) is None


class TestNodeBridgeExecute:
    def test_execute_success(self):
        service, _, client = _make_node_bridge()
        resp = MagicMock()
        resp.json.return_value = {"success": True, "output": {"rows": 3}}
        client.post = AsyncMock(return_value=resp)
        output = asyncio.run(service.execute_action("slack", "post", {"text": "hi"}, {"token": "t"}))
        assert output == {"rows": 3}
        client.post.assert_awaited_once()
        payload = client.post.call_args.kwargs["json"]
        assert payload == {"pieceName": "slack", "actionName": "post", "props": {"text": "hi"}, "auth": {"token": "t"}}

    def test_execute_failure_raises(self):
        service, _, client = _make_node_bridge()
        resp = MagicMock()
        resp.json.return_value = {"success": False, "error": "auth denied"}
        client.post = AsyncMock(return_value=resp)
        with pytest.raises(Exception, match="auth denied"):
            asyncio.run(service.execute_action("slack", "post", {}))

    def test_execute_failure_unknown_error(self):
        service, _, client = _make_node_bridge()
        resp = MagicMock()
        resp.json.return_value = {"success": False}
        client.post = AsyncMock(return_value=resp)
        with pytest.raises(Exception, match="Unknown error"):
            asyncio.run(service.execute_action("slack", "post", {}))

    def test_execute_network_error_reraises(self):
        service, _, client = _make_node_bridge()
        client.post = AsyncMock(side_effect=RuntimeError("timeout"))
        with pytest.raises(RuntimeError, match="timeout"):
            asyncio.run(service.execute_action("slack", "post", {}))

    def test_execute_auth_none(self):
        service, _, client = _make_node_bridge()
        resp = MagicMock()
        resp.json.return_value = {"success": True, "output": {}}
        client.post = AsyncMock(return_value=resp)
        asyncio.run(service.execute_action("slack", "post", {"a": 1}))
        assert client.post.call_args.kwargs["json"]["auth"] is None

    def test_close(self):
        service, _, client = _make_node_bridge()
        asyncio.run(service.close())
        client.aclose.assert_awaited_once()


# ---------------------------------------------------------------------------
# core/communication/adapters/slack.py (Events API adapter)
# ---------------------------------------------------------------------------

def _mock_request(headers=None):
    headers = headers or {}
    req = MagicMock(spec=Request)
    req.headers.get = headers.get
    req.headers = headers
    return req


def _valid_signature(secret: str, body: str, ts: str) -> str:
    sig_basestring = f"v0:{ts}:{body}".encode("utf-8")
    return "v0=" + hmac.new(secret.encode("utf-8"), sig_basestring, hashlib.sha256).hexdigest()


def _make_comm_adapter(**kwargs):
    with patch("slack_sdk.WebClient") as wc_cls:
        adapter = CommunicationSlackAdapter(**kwargs)
    return adapter, wc_cls


class TestCommunicationSlackAdapterInit:
    def test_init_from_args(self):
        adapter, wc_cls = _make_comm_adapter(bot_token="xoxb-1", signing_secret="sec")
        assert adapter.bot_token == "xoxb-1"
        assert adapter.signing_secret == "sec"
        wc_cls.assert_called_once_with(token="xoxb-1")

    def test_init_from_env(self, monkeypatch):
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-env")
        monkeypatch.setenv("SLACK_SIGNING_SECRET", "sec-env")
        adapter, wc_cls = _make_comm_adapter()
        assert adapter.bot_token == "xoxb-env"
        assert adapter.signing_secret == "sec-env"
        wc_cls.assert_called_once_with(token="xoxb-env")

    def test_init_without_token(self):
        adapter, wc_cls = _make_comm_adapter()
        assert adapter.client is None
        wc_cls.assert_not_called()

    def test_init_sdk_missing(self, monkeypatch):
        stub = sys.modules.get("slack_sdk")
        import types
        fake = types.ModuleType("slack_sdk")
        monkeypatch.setitem(sys.modules, "slack_sdk", fake)
        try:
            with patch("logging.Logger.warning") as warn:
                adapter = CommunicationSlackAdapter(bot_token="xoxb-1")
            assert adapter.client is None
            warn.assert_called_once()
        finally:
            if stub is not None:
                sys.modules["slack_sdk"] = stub


class TestCommunicationSlackVerify:
    def test_verify_without_secret_allows(self):
        adapter, _ = _make_comm_adapter()
        with patch("logging.Logger.warning") as warn:
            assert asyncio.run(adapter.verify_request(_mock_request(), b"{}")) is True
        warn.assert_called_once()

    def test_verify_missing_headers(self):
        adapter, _ = _make_comm_adapter(signing_secret="sec")
        assert asyncio.run(adapter.verify_request(_mock_request(), b"{}")) is False

    def test_verify_stale_timestamp(self):
        adapter, _ = _make_comm_adapter(signing_secret="sec")
        req = _mock_request(headers={
            "X-Slack-Request-Timestamp": str(int(time.time()) - 400),
            "X-Slack-Signature": "v0=abc",
        })
        assert asyncio.run(adapter.verify_request(req, b"{}")) is False

    def test_verify_valid_signature(self):
        adapter, _ = _make_comm_adapter(signing_secret="sec")
        body = "payload=1"
        ts = str(int(time.time()))
        req = _mock_request(headers={
            "X-Slack-Request-Timestamp": ts,
            "X-Slack-Signature": _valid_signature("sec", body, ts),
        })
        assert asyncio.run(adapter.verify_request(req, body.encode())) is True

    def test_verify_tampered_signature(self):
        adapter, _ = _make_comm_adapter(signing_secret="sec")
        body = "payload=1"
        ts = str(int(time.time()))
        req = _mock_request(headers={
            "X-Slack-Request-Timestamp": ts,
            "X-Slack-Signature": "v0=deadbeef",
        })
        assert asyncio.run(adapter.verify_request(req, body.encode())) is False

    def test_verify_future_timestamp_rejected(self):
        adapter, _ = _make_comm_adapter(signing_secret="sec")
        req = _mock_request(headers={
            "X-Slack-Request-Timestamp": str(int(time.time()) + 400),
            "X-Slack-Signature": "v0=abc",
        })
        assert asyncio.run(adapter.verify_request(req, b"{}")) is False


class TestCommunicationSlackNormalize:
    def setup_method(self):
        self.adapter, _ = _make_comm_adapter()

    def test_challenge(self):
        result = self.adapter.normalize_payload({"challenge": "abc123", "type": "url_verification"})
        assert result == {"type": "challenge", "challenge": "abc123"}

    def test_message_bot_ignored(self):
        assert self.adapter.normalize_payload({"event": {"type": "message", "bot_id": "B1", "text": "hi"}}) is None

    def test_message_subtype_ignored(self):
        assert self.adapter.normalize_payload({"event": {"type": "message", "subtype": "message_changed", "text": "hi"}}) is None

    def test_message_normalized(self):
        payload = {"event": {"type": "message", "user": "U1", "text": "hello", "channel": "C1"}}
        result = self.adapter.normalize_payload(payload)
        assert result == {
            "sender_id": "U1",
            "content": "hello",
            "channel_id": "C1",
            "metadata": payload,
        }

    def test_block_actions_normalized(self):
        payload = {
            "type": "block_actions",
            "actions": [{"action_id": "approve_9", "value": "9"}],
            "user": {"id": "U2"},
            "channel": {"id": "C2"},
        }
        result = self.adapter.normalize_payload(payload)
        assert result["sender_id"] == "U2"
        assert result["content"] == "APPROVE_9 9"
        assert result["channel_id"] == "C2"
        assert result["is_interaction"] is True

    def test_block_actions_without_actions(self):
        payload = {"type": "block_actions", "actions": []}
        assert self.adapter.normalize_payload(payload) is None

    def test_unknown_event_returns_none(self):
        assert self.adapter.normalize_payload({"event": {"type": "reaction_added"}}) is None


class TestCommunicationSlackSend:
    def test_send_message_no_client(self):
        adapter, _ = _make_comm_adapter()
        assert asyncio.run(adapter.send_message("C1", "hi")) is False

    def test_send_message_success(self):
        adapter, wc_cls = _make_comm_adapter(bot_token="xoxb-1")
        client = wc_cls.return_value
        client.chat_postMessage = MagicMock()
        assert asyncio.run(adapter.send_message("C1", "hi")) is True
        client.chat_postMessage.assert_called_once_with(channel="C1", text="hi")

    def test_send_message_error(self):
        adapter, wc_cls = _make_comm_adapter(bot_token="xoxb-1")
        client = wc_cls.return_value
        client.chat_postMessage = MagicMock(side_effect=RuntimeError("api"))
        assert asyncio.run(adapter.send_message("C1", "hi")) is False

    def test_send_approval_no_client(self):
        adapter, _ = _make_comm_adapter()
        assert asyncio.run(adapter.send_approval_request("C1", "a1", {"action_type": "refund", "reason": "dup"}, "HIGH")) is False

    def test_send_approval_success(self):
        adapter, wc_cls = _make_comm_adapter(bot_token="xoxb-1")
        client = wc_cls.return_value
        client.chat_postMessage = MagicMock()
        result = asyncio.run(adapter.send_approval_request("C1", "a1", {"action_type": "refund", "reason": "dup"}, "HIGH"))
        assert result is True
        call = client.chat_postMessage.call_args
        assert call.kwargs["channel"] == "C1"
        assert call.kwargs["text"] == "HITL Approval Required: a1"
        blocks = call.kwargs["blocks"]
        assert blocks[1]["elements"][0]["action_id"] == "approve_a1"
        assert blocks[1]["elements"][1]["action_id"] == "reject_a1"
        assert blocks[2]["elements"][0]["text"] == "Action ID: `a1` | Priority: HIGH"

    def test_send_approval_error(self):
        adapter, wc_cls = _make_comm_adapter(bot_token="xoxb-1")
        client = wc_cls.return_value
        client.chat_postMessage = MagicMock(side_effect=RuntimeError("api"))
        assert asyncio.run(adapter.send_approval_request("C1", "a1", {}, "LOW")) is False

    def test_send_direct_no_client(self):
        adapter, _ = _make_comm_adapter()
        assert asyncio.run(adapter.send_direct_message("C1", "hi", "Agent")) is False

    def test_send_direct_with_agent_name(self):
        adapter, wc_cls = _make_comm_adapter(bot_token="xoxb-1")
        client = wc_cls.return_value
        client.chat_postMessage = MagicMock()
        assert asyncio.run(adapter.send_direct_message("C1", "hi", "Athena")) is True
        client.chat_postMessage.assert_called_once_with(channel="C1", text="*[Athena]* hi")

    def test_send_direct_without_agent_name(self):
        adapter, wc_cls = _make_comm_adapter(bot_token="xoxb-1")
        client = wc_cls.return_value
        client.chat_postMessage = MagicMock()
        assert asyncio.run(adapter.send_direct_message("C1", "hi")) is True
        client.chat_postMessage.assert_called_once_with(channel="C1", text="hi")

    def test_send_direct_error(self):
        adapter, wc_cls = _make_comm_adapter(bot_token="xoxb-1")
        client = wc_cls.return_value
        client.chat_postMessage = MagicMock(side_effect=RuntimeError("api"))
        assert asyncio.run(adapter.send_direct_message("C1", "hi")) is False
