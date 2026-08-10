"""Coverage wave 12 — api/ route bug-hunt + never-covered modules (TDD).

Targets modules surfaced by the recurring-bug sweep:
- graphrag_routes.py            (return HTTPException → 200-body; 4 sites)
- agent_governance_routes.py    (bare except swallows not_found/permission → 500; 8 sites)
- learning_routes.py            (phantom not_found_response → AttributeError)
- deeplinks.py                  (bare except swallows validation_error → 500; 2 sites)
- dynamic_options_routes.py     (response_model vs envelope → 500 on every request)
- integrations_catalog_routes.py, zoho_workdrive_routes.py, gatekeeper_routes.py,
  mcp_client_routes.py, mcp_server_routes.py (never-covered → coverage)

Methodology: each RED test reproduces the documented bug against the public
route contract (status code / body shape), then the source fix turns it GREEN.
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.auth import get_current_user
from core.database import get_db


# --------------------------------------------------------------------------- #
# Shared harness
# --------------------------------------------------------------------------- #
def _app(router):
    app = FastAPI()
    app.include_router(router)
    return app


def _client(router, db=None, user=None):
    app = _app(router)
    app.dependency_overrides[get_current_user] = lambda: user or SimpleNamespace(
        id="u-1", tenant_id="t-1", role="user"
    )
    if db is not None:
        app.dependency_overrides[get_db] = lambda: db
    return TestClient(app, raise_server_exceptions=False)


# =========================================================================== #
# GraphRAG routes — return router.error_response(...) must RAISE not return
# =========================================================================== #
class TestGraphRAGRoutes:
    @pytest.fixture(autouse=True)
    def _engine(self):
        with patch("core.graphrag_engine.graphrag_engine") as eng:
            yield eng

    def _client(self):
        from api.graphrag_routes import router
        return _client(router)

    def test_add_entity_success(self, _engine):
        _engine.add_entity.return_value = "node-1"
        c = self._client()
        r = c.post("/api/graphrag/entities", params={"workspace_id": "ws"},
                   json={"name": "Acme", "type": "org"})
        assert r.status_code == 200
        assert r.json()["data"]["id"] == "node-1"

    def test_add_entity_ingestion_failure_returns_500_not_200(self, _engine):
        """RED before fix: ``return router.error_response(...)`` serialized the
        HTTPException object as a 200 body; the intended 500 was lost."""
        _engine.add_entity.return_value = None
        c = self._client()
        r = c.post("/api/graphrag/entities", params={"workspace_id": "ws"},
                   json={"name": "Acme", "type": "org"})
        assert r.status_code == 500
        body = r.json()
        # error_response body nests under detail.error.code (FastAPI serializes
        # the raised HTTPException). A 200 with a raw exception object would
        # not carry this shape.
        assert body["detail"]["error"]["code"] == "INGESTION_FAILED"

    def test_add_relationship_missing_entity_returns_404_not_200(self, _engine):
        """The not-found branch must surface a 404, not a 200 with an
        HTTPException body."""
        from contextlib import contextmanager

        sess = MagicMock()
        sess.query.return_value.filter_by.return_value.first.return_value = None

        @contextmanager
        def _sess():
            yield sess

        with patch("core.database.get_db_session", _sess):
            c = self._client()
            r = c.post(
                "/api/graphrag/relationships", params={"workspace_id": "ws"},
                json={"from_entity": "x", "to_entity": "y", "relationship_type": "rel"},
            )
        assert r.status_code == 404

    def test_get_neighbors_missing_entity_returns_404_not_200(self, _engine):
        from contextlib import contextmanager

        sess = MagicMock()
        sess.query.return_value.filter_by.return_value.first.return_value = None

        @contextmanager
        def _sess():
            yield sess

        with patch("core.database.get_db_session", _sess):
            c = self._client()
            r = c.get("/api/graphrag/entities/nope/neighbors",
                      params={"workspace_id": "ws"})
        assert r.status_code == 404

    def test_list_entities(self, _engine):
        from contextlib import contextmanager

        node = SimpleNamespace(id="n1", name="Acme", type="org",
                               description="d", properties={})
        sess = MagicMock()
        sess.query.return_value.filter_by.return_value.limit.return_value.all.return_value = [node]

        @contextmanager
        def _sess():
            yield sess

        with patch("core.database.get_db_session", _sess):
            c = self._client()
            r = c.get("/api/graphrag/entities", params={"workspace_id": "ws"})
        assert r.status_code == 200
        assert r.json()["data"]["entities"][0]["id"] == "n1"

    def test_canonical_search_too_long_returns_422(self, _engine):
        c = self._client()
        r = c.get("/api/graphrag/canonical-search",
                  params={"workspace_id": "ws", "type": "org", "q": "x" * 501})
        assert r.status_code == 422


# =========================================================================== #
# Agent governance routes — bare except must not swallow not_found/permission
# =========================================================================== #
class TestAgentGovernanceRoutes:
    def _client(self):
        from api.agent_governance_routes import router
        return _client(router)

    def test_list_agents_with_maturity(self):
        r = self._client().get("/api/agent-governance/agents")
        assert r.status_code == 200
        ids = {a["agent_id"] for a in r.json()}
        assert "sales-agent" in ids

    def test_list_agents_category_filter(self):
        r = self._client().get("/api/agent-governance/agents", params={"category": "marketing"})
        assert r.status_code == 200
        assert all(a["category"] == "marketing" for a in r.json())

    def test_get_maturity_unknown_agent_returns_404_not_500(self):
        """RED before fix: not_found_error (404) was swallowed by the bare
        ``except Exception`` → surfaced as 500."""
        r = self._client().get("/api/agent-governance/agents/nope-agent")
        assert r.status_code == 404

    def test_get_maturity_known_agent(self):
        r = self._client().get("/api/agent-governance/agents/sales-agent")
        assert r.status_code == 200
        assert r.json()["agent_id"] == "sales-agent"

    def test_check_deployment_unknown_agent_returns_404(self):
        r = self._client().post(
            "/api/agent-governance/check-deployment",
            json={
                "agent_id": "nope", "workflow_name": "w",
                "workflow_definition": {}, "trigger_type": "manual",
                "actions": [], "requested_by": "u-1",
            },
        )
        assert r.status_code == 404

    def test_submit_for_approval_unknown_agent_returns_404(self):
        r = self._client().post(
            "/api/agent-governance/submit-for-approval",
            json={
                "agent_id": "nope", "workflow_name": "w",
                "workflow_definition": {}, "trigger_type": "manual",
                "actions": [], "requested_by": "u-1",
            },
        )
        assert r.status_code == 404

    def test_submit_feedback_unknown_agent_returns_404(self):
        r = self._client().post(
            "/api/agent-governance/feedback",
            json={
                "agent_id": "nope", "original_output": "x",
                "user_correction": "y", "input_context": "ctx",
            },
        )
        assert r.status_code == 404

    def test_get_capabilities_unknown_agent_returns_404(self):
        r = self._client().get("/api/agent-governance/agents/nope/capabilities")
        assert r.status_code == 404

    def test_get_capabilities_known_agent(self):
        r = self._client().get("/api/agent-governance/agents/sales-agent/capabilities")
        assert r.status_code == 200
        assert "allowed_actions" in r.json()

    def test_approve_workflow_unknown_user_returns_404(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        from api.agent_governance_routes import router
        c = _client(router, db=db)
        r = c.post("/api/agent-governance/approve/apr_1")
        assert r.status_code == 404

    def test_approve_workflow_wrong_role_returns_403(self):
        user = SimpleNamespace(id="u-1", role="user")
        db = MagicMock()
        dbu = SimpleNamespace(id="u-1", role="user")
        db.query.return_value.filter.return_value.first.return_value = dbu
        from api.agent_governance_routes import router
        c = _client(router, db=db, user=user)
        r = c.post("/api/agent-governance/approve/apr_1")
        assert r.status_code == 403

    def test_enforce_action_unknown_agent_blocked(self):
        r = self._client().post(
            "/api/agent-governance/enforce-action",
            json={"agent_id": "nope", "action_type": "read"},
        )
        assert r.status_code == 200
        assert r.json()["status"] == "BLOCKED"


# =========================================================================== #
# Learning routes — phantom not_found_response → AttributeError (now raises)
# =========================================================================== #
class TestLearningRoutes:
    def _client(self, db):
        from api.learning_routes import router
        return _client(router, db=db)

    def test_progress_found(self):
        db = MagicMock()
        with patch("api.learning_routes.ContinuousLearningService") as Svc:
            Svc.return_value.get_learning_progress.return_value = {"rate": 0.9}
            r = self._client(db).get("/api/learning/progress/ag-1")
        assert r.status_code == 200
        assert r.json()["data"]["rate"] == 0.9

    def test_progress_not_found_returns_404_not_500(self):
        """RED before fix: called ``router.not_found_response`` which does not
        exist → AttributeError → 500."""
        db = MagicMock()
        with patch("api.learning_routes.ContinuousLearningService") as Svc:
            Svc.return_value.get_learning_progress.return_value = None
            r = self._client(db).get("/api/learning/progress/ag-1")
        assert r.status_code == 404


# =========================================================================== #
# Deeplinks — bare except must not swallow validation_error (422)
# =========================================================================== #
class TestDeeplinksRoutes:
    def _client(self):
        from api.deeplinks import router
        return _client(router)

    def test_generate_invalid_resource_type_returns_422_not_500(self):
        """RED before fix: validation_error (422) raised inside try was caught
        by the bare ``except Exception`` → 500."""
        r = self._client().post(
            "/api/deeplinks/generate",
            json={"resource_type": "bogus", "resource_id": "x", "parameters": {}},
        )
        assert r.status_code == 422

    def test_generate_valid(self):
        r = self._client().post(
            "/api/deeplinks/generate",
            json={"resource_type": "agent", "resource_id": "ag-1", "parameters": {}},
        )
        assert r.status_code == 200
        assert r.json()["deeplink_url"].startswith("atom://")

    def test_execute_failed_execution_returns_422_not_500(self):
        """The inner validation_error must reach the client as 422, not be
        masked into 500 by the outer bare except."""
        with patch("api.deeplinks.execute_deep_link", new_callable=AsyncMock) as ex:
            ex.return_value = {"success": False, "error": "bad"}
            r = self._client().post(
                "/api/deeplinks/execute",
                json={"deeplink_url": "atom://agent/ag-1", "source": "test"},
            )
        assert r.status_code == 422

    def test_execute_success(self):
        with patch("api.deeplinks.execute_deep_link", new_callable=AsyncMock) as ex:
            ex.return_value = {
                "success": True, "agent_id": "ag-1", "agent_name": "Sales",
                "execution_id": "e-1", "resource_type": "agent",
                "resource_id": "ag-1", "action": "open", "source": "test",
            }
            r = self._client().post(
                "/api/deeplinks/execute",
                json={"deeplink_url": "atom://agent/ag-1", "source": "test"},
            )
        assert r.status_code == 200
        assert r.json()["agent_id"] == "ag-1"


# =========================================================================== #
# Dynamic options — response_model/envelope mismatch (was 500 on every request)
# =========================================================================== #
class TestDynamicOptionsRoutes:
    def _client(self):
        from api.dynamic_options_routes import router
        return _client(router)

    def test_fallback_no_connection_returns_200_not_500(self):
        """RED before fix: handler declared response_model=DynamicOptionsResponse
        but returned the success envelope → ResponseValidationError → 500."""
        r = self._client().post(
            "/api/v1/integrations/dynamic-options",
            json={"pieceId": "slack", "propertyName": "channels"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        assert body["data"]["options"] == []

    def test_credential_failure_returns_200_with_empty_options(self):
        with patch("core.connection_service.connection_service") as cs:
            cs.get_connection_credentials = AsyncMock(side_effect=RuntimeError("boom"))
            r = self._client().post(
                "/api/v1/integrations/dynamic-options",
                json={
                    "pieceId": "slack", "propertyName": "channels",
                    "connectionId": "c-1",
                },
            )
        assert r.status_code == 200
        assert r.json()["data"]["options"] == []

    def test_node_bridge_returns_options(self):
        with patch("integrations.bridge.node_bridge_service.node_bridge") as nb:
            nb.get_dynamic_options = AsyncMock(return_value={
                "options": [{"value": "general", "label": "#general"}],
                "placeholder": "pick",
            })
            r = self._client().post(
                "/api/v1/integrations/dynamic-options",
                json={"pieceId": "slack", "propertyName": "channels"},
            )
        assert r.status_code == 200
        assert len(r.json()["data"]["options"]) == 1


# =========================================================================== #
# Integrations catalog — never covered
# =========================================================================== #
class TestIntegrationsCatalogRoutes:
    def _client(self, db):
        from api.integrations_catalog_routes import router
        return _client(router, db=db)

    def _piece(self, **kw):
        base = dict(
            id="slack", name="Slack", description="chat", category="comms",
            icon="slack", color="#000", auth_type="oauth2",
            triggers=[], actions=[], popular=True, native_id=None,
        )
        base.update(kw)
        return SimpleNamespace(**base)

    def test_catalog_list(self):
        db = MagicMock()
        q = MagicMock()
        q.all.return_value = [self._piece()]
        db.query.return_value = q
        # chainable filters
        q.filter.return_value = q
        q.filter.return_value.filter.return_value = q
        r = self._client(db).get("/api/v1/integrations/catalog")
        assert r.status_code == 200
        assert r.json()[0]["id"] == "slack"

    def test_catalog_search(self):
        db = MagicMock()
        q = MagicMock()
        q.all.return_value = [self._piece(name="Slack")]
        db.query.return_value = q
        q.filter.return_value = q
        r = self._client(db).get("/api/v1/integrations/catalog", params={"search": "slack"})
        assert r.status_code == 200

    def test_catalog_details_found(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = self._piece()
        r = self._client(db).get("/api/v1/integrations/catalog/slack")
        assert r.status_code == 200
        assert r.json()["id"] == "slack"

    def test_catalog_details_not_found_returns_404(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        r = self._client(db).get("/api/v1/integrations/catalog/nope")
        assert r.status_code == 404


# =========================================================================== #
# Zoho WorkDrive routes — never covered
# =========================================================================== #
class TestZohoWorkDriveRoutes:
    def _client(self):
        from api.zoho_workdrive_routes import router
        return _client(router)

    def test_teams(self):
        with patch("api.zoho_workdrive_routes.zoho_service") as svc:
            svc.get_teams = AsyncMock(return_value=[{"id": "t1"}])
            r = self._client().get("/api/zoho-workdrive/teams")
        assert r.status_code == 200
        assert r.json()["data"] == [{"id": "t1"}]

    def test_teams_error_returns_500(self):
        with patch("api.zoho_workdrive_routes.zoho_service") as svc:
            svc.get_teams = AsyncMock(side_effect=RuntimeError("boom"))
            r = self._client().get("/api/zoho-workdrive/teams")
        assert r.status_code == 500

    def test_list_files(self):
        with patch("api.zoho_workdrive_routes.zoho_service") as svc:
            svc.list_files = AsyncMock(return_value=[{"id": "f1"}])
            r = self._client().post(
                "/api/zoho-workdrive/files/list",
                json={"user_id": "u-1", "parent_id": "root"},
            )
        assert r.status_code == 200

    def test_ingest(self):
        with patch("api.zoho_workdrive_routes.zoho_service") as svc:
            svc.ingest_file_to_memory = AsyncMock(return_value={"ok": True})
            r = self._client().post(
                "/api/zoho-workdrive/ingest",
                json={"user_id": "u-1", "file_id": "f1"},
            )
        assert r.status_code == 200

    def test_health_configured(self):
        with patch("api.zoho_workdrive_routes.zoho_service") as svc:
            svc.client_id = "cid"
            svc.client_secret = "secret"
            svc.redirect_uri = "uri"
            r = self._client().get("/api/zoho-workdrive/health")
        assert r.status_code == 200
        assert r.json()["data"]["status"] == "configured"

    def test_health_unconfigured(self):
        with patch("api.zoho_workdrive_routes.zoho_service") as svc:
            svc.client_id = None
            svc.client_secret = None
            svc.redirect_uri = None
            r = self._client().get("/api/zoho-workdrive/health")
        assert r.status_code == 200
        assert r.json()["data"]["status"] == "unconfigured"


# =========================================================================== #
# Gatekeeper routes — never covered
# =========================================================================== #
class TestGatekeeperRoutes:
    def _client(self):
        from api.gatekeeper_routes import router
        app = _app(router)
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
            id="admin-1", role="super_admin")
        return TestClient(app, raise_server_exceptions=False)

    def test_get_config(self):
        with patch("core.rbac_service.RBACService.check_permission", return_value=True), \
             patch("middleware.governance_middleware.governance_middleware") as gm:
            gm._config = {"slack": {"rate_limit": 100}}
            r = self._client().get("/api/gatekeeper/config")
        assert r.status_code == 200
        assert r.json()["data"]["slack"]["rate_limit"] == 100

    def test_update_config(self):
        with patch("core.rbac_service.RBACService.check_permission", return_value=True), \
             patch("middleware.governance_middleware.governance_middleware") as gm:
            gm.configure = MagicMock()
            r = self._client().put(
                "/api/gatekeeper/config/slack",
                json={"rate_limit": 200, "masked_fields": ["token"]},
            )
        assert r.status_code == 200
        gm.configure.assert_called_once()
        args = gm.configure.call_args
        assert args[0][0] == "slack"
        assert args[0][1]["rate_limit"] == 200


# =========================================================================== #
# MCP client routes — never covered
# =========================================================================== #
class TestMCPClientRoutes:
    def _client(self):
        from api.mcp_client_routes import router
        app = _app(router)
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
            id="admin-1", role="super_admin")
        return TestClient(app, raise_server_exceptions=False)

    def test_list_servers(self):
        from core.mcp_service import mcp_service
        with patch("core.rbac_service.RBACService.check_permission", return_value=True), \
             patch.object(mcp_service, "tools_cache", {"ext-1": ["t1"], "google-search": []}), \
             patch.object(mcp_service, "external_clients", {"ext-1": object()}):
            r = self._client().get("/api/mcp/servers")
        assert r.status_code == 200
        # built-in servers are filtered out
        ids = [s["server_id"] for s in r.json()["data"]]
        assert ids == ["ext-1"]

    def test_register_server(self):
        from core.mcp_service import mcp_service
        with patch("core.rbac_service.RBACService.check_permission", return_value=True), \
             patch.object(mcp_service, "register_server", new_callable=AsyncMock) as reg, \
             patch.object(mcp_service, "tools_cache", {"new": ["t1", "t2"]}), \
             patch.object(mcp_service, "external_clients", {"new": object()}):
            r = self._client().post(
                "/api/mcp/servers",
                json={"name": "new", "transport": "http", "url": "http://x"},
            )
        assert r.status_code == 200
        assert r.json()["data"]["tool_count"] == 2
        reg.assert_awaited_once()

    def test_register_server_failure_returns_502(self):
        from core.mcp_service import mcp_service
        with patch("core.rbac_service.RBACService.check_permission", return_value=True), \
             patch.object(mcp_service, "register_server", new_callable=AsyncMock) as reg:
            reg.side_effect = RuntimeError("connect failed")
            r = self._client().post(
                "/api/mcp/servers",
                json={"name": "bad", "transport": "http", "url": "http://x"},
            )
        assert r.status_code == 502

    def test_unregister_server(self):
        from core.mcp_service import mcp_service
        client = MagicMock()
        client.close = AsyncMock()
        with patch("core.rbac_service.RBACService.check_permission", return_value=True), \
             patch.object(mcp_service, "external_clients", {"ext-1": client}), \
             patch.object(mcp_service, "tools_cache", {"ext-1": []}), \
             patch.object(mcp_service, "servers", {"ext-1": {}}):
            r = self._client().delete("/api/mcp/servers/ext-1")
        assert r.status_code == 200
        client.close.assert_awaited_once()
