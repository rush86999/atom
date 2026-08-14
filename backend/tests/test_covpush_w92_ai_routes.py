"""Coverage wave 92 — integrations/ai_routes.py (47% → 95%+).

Closes the never-wave-tested gaps: NLP parse (success/500), data ingest
(valid platform, unsupported-platform 400, 500), unified search (with/
without entity types, invalid type 400, serialization, 500), entity
details (found/404/500), workflow create (success/500), workflow execute
(success, ValueError 404, 500), workflow list (updated_at set/unset, 500),
execution history (success/500), AI health (healthy/unhealthy), root.

Security: the router had NO auth dependency — every endpoint asserts 401
anonymous (RED) and the router is wired with Depends(get_current_user)
(GREEN).
"""
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.security_dependencies import get_current_user
from integrations import ai_routes as ar

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")


# --- tiny stand-ins for engine-owned objects ---------------------------------

class V:
    """Hashable enum-like stand-in (SimpleNamespace is unhashable)."""

    def __init__(self, value):
        self.value = value


class FakeEntity:
    def __init__(self, eid="e1", etype="person", name="Alice"):
        self.entity_id = eid
        self.entity_type = V(etype)
        self.canonical_name = name
        self.platform_mappings = {V("slack"): "U1"}
        self.attributes = {"title": "Engineer"}
        self.relationships = []
        self.confidence_score = 0.9
        self.source_platforms = [V("slack"), V("email")]
        self.created_at = datetime(2026, 1, 1, 10)
        self.updated_at = datetime(2026, 1, 1, 11)


class FakeRelationship:
    def __init__(self):
        self.relationship_id = "r1"
        self.relationship_type = "works_with"
        self.target_entity_id = "e2"
        self.strength = 0.8
        self.created_at = datetime(2026, 1, 1, 9)


class FakeTrigger:
    def __init__(self):
        self.trigger_id = "tr1"
        self.trigger_type = V("webhook")
        self.platform = V("slack")
        self.event_name = "message.new"


class FakeAction:
    def __init__(self):
        self.action_id = "a1"
        self.action_type = V("send_message")
        self.platform = V("slack")
        self.description = "Post a message"


class FakeWorkflow:
    def __init__(self, updated=True):
        self.workflow_id = "wf1"
        self.name = "W"
        self.description = "D"
        self.trigger = FakeTrigger()
        self.actions = [FakeAction()]
        self.is_active = True
        self.created_at = datetime(2026, 1, 1, 10)
        self.updated_at = datetime(2026, 1, 1, 11) if updated else None


class FakeExecution:
    def __init__(self):
        self.execution_id = "ex1"
        self.status = "completed"
        self.actions_executed = ["a1"]
        self.errors = []
        self.results = {"ok": True}
        self.start_time = datetime(2026, 1, 1, 10)
        self.end_time = datetime(2026, 1, 1, 10, 1)


@pytest.fixture
def app():
    application = FastAPI()
    application.include_router(ar.router)
    return application


@pytest.fixture
def anon_client(app):
    return TestClient(app)


@pytest.fixture
def client(app):
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id="user_1", tenant_id="t1")
    return TestClient(app)


@pytest.fixture
def engines():
    with patch.object(ar, "nlp_engine") as nlp, \
         patch.object(ar, "data_engine") as data, \
         patch.object(ar, "automation_engine") as auto:
        yield SimpleNamespace(nlp=nlp, data=data, auto=auto)


class TestRouteAuth:
    """Security: every /ai endpoint rejects anonymous callers."""

    @pytest.mark.parametrize("method,path", [
        ("post", "/ai/nlp/parse"),
        ("post", "/ai/data/ingest"),
        ("post", "/ai/data/search"),
        ("get", "/ai/data/entities/e1"),
        ("post", "/ai/automation/workflows"),
        ("post", "/ai/automation/workflows/wf1/execute"),
        ("get", "/ai/automation/workflows"),
        ("get", "/ai/automation/workflows/wf1/executions"),
        ("get", "/ai/health"),
        ("get", "/ai/"),
    ])
    def test_anonymous_rejected(self, anon_client, method, path):
        resp = getattr(anon_client, method)(path)
        assert resp.status_code == 401, f"{method} {path} -> {resp.status_code}"


class TestNLP:
    def test_parse_success(self, client, engines):
        engines.nlp.parse_command.return_value = MagicMock()
        engines.nlp.generate_response.return_value = {
            "success": True, "confidence": 0.8, "command_type": "send_message",
            "platforms": ["slack"], "entities": ["bob"],
            "parameters": {"to": "bob"}, "message": "Sending...",
            "suggested_actions": ["a1"]}
        resp = client.post("/ai/nlp/parse", json={"command": "send bob a hi",
                                                  "user_id": "u1"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["command_type"] == "send_message"
        assert body["parameters"] == {"to": "bob"}

    def test_parse_error_500(self, client, engines):
        engines.nlp.parse_command.side_effect = RuntimeError("boom")
        resp = client.post("/ai/nlp/parse", json={"command": "hi", "user_id": "u1"})
        assert resp.status_code == 500


class TestDataIngest:
    def test_ingest_success(self, client, engines):
        multi = FakeEntity()
        multi.source_platforms = [V("slack"), V("email")]  # multi-platform -> updated
        single = FakeEntity(eid="e2")
        single.source_platforms = [V("slack")]
        engines.data.ingest_platform_data.return_value = [multi, single]
        engines.data.relationship_registry = {"r1": {}}
        resp = client.post("/ai/data/ingest", json={
            "platform": "Slack", "data": [{"id": "1"}]})
        assert resp.status_code == 200
        body = resp.json()
        assert body["entities_created"] == 2
        assert body["entities_updated"] == 1
        assert body["relationships_created"] == 1

    def test_ingest_unsupported_platform_400(self, client, engines):
        resp = client.post("/ai/data/ingest", json={
            "platform": "carrier_pigeon", "data": []})
        assert resp.status_code == 400

    def test_ingest_error_500(self, client, engines):
        engines.data.ingest_platform_data.side_effect = RuntimeError("boom")
        resp = client.post("/ai/data/ingest", json={"platform": "slack", "data": []})
        assert resp.status_code == 500


class TestDataSearch:
    def test_search_no_filters(self, client, engines):
        engines.data.search_unified_entities.return_value = [FakeEntity()]
        resp = client.post("/ai/data/search", json={"query": "alice"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_count"] == 1
        assert body["results"][0]["entity_type"] == "person"
        assert body["results"][0]["platforms"] == ["slack", "email"]

    def test_search_with_entity_types(self, client, engines):
        engines.data.search_unified_entities.return_value = []
        resp = client.post("/ai/data/search",
                           json={"query": "q", "entity_types": ["Deal", "company"]})
        assert resp.status_code == 200
        call_types = engines.data.search_unified_entities.call_args[0][1]
        assert [t.value for t in call_types] == ["deal", "company"]

    def test_search_invalid_entity_type_400(self, client, engines):
        resp = client.post("/ai/data/search",
                           json={"query": "q", "entity_types": ["dragon"]})
        assert resp.status_code == 400

    def test_search_error_500(self, client, engines):
        engines.data.search_unified_entities.side_effect = RuntimeError("boom")
        resp = client.post("/ai/data/search", json={"query": "q"})
        assert resp.status_code == 500


class TestEntityDetails:
    def test_success(self, client, engines):
        engines.data.entity_registry.get.return_value = FakeEntity()
        engines.data.get_entity_relationships.return_value = [FakeRelationship()]
        engines.data.get_entity_timeline.return_value = [{"ts": "2026-01-01"}]
        resp = client.get("/ai/data/entities/e1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["entity"]["entity_id"] == "e1"
        assert body["entity"]["platform_mappings"] == {"slack": "U1"}
        assert body["relationships"][0]["relationship_type"] == "works_with"
        assert body["timeline"] == [{"ts": "2026-01-01"}]

    def test_not_found_404(self, client, engines):
        engines.data.entity_registry.get.return_value = None
        resp = client.get("/ai/data/entities/missing")
        assert resp.status_code == 404

    def test_error_500(self, client, engines):
        engines.data.entity_registry.get.side_effect = RuntimeError("boom")
        resp = client.get("/ai/data/entities/e1")
        assert resp.status_code == 500


class TestWorkflowCreate:
    def test_success(self, client, engines):
        engines.auto.create_workflow.return_value = FakeWorkflow()
        resp = client.post("/ai/automation/workflows", json={
            "name": "W", "description": "D", "trigger": {"type": "webhook"},
            "actions": [{"type": "send_message"}], "conditions": [{"c": 1}]})
        assert resp.status_code == 200
        body = resp.json()
        assert body["workflow_id"] == "wf1"
        assert body["trigger"]["type"] == "webhook"
        assert body["actions"][0]["type"] == "send_message"
        assert body["is_active"] is True

    def test_error_500(self, client, engines):
        engines.auto.create_workflow.side_effect = RuntimeError("boom")
        resp = client.post("/ai/automation/workflows", json={
            "name": "W", "description": "D", "trigger": {}, "actions": []})
        assert resp.status_code == 500


class TestWorkflowExecute:
    def test_success(self, client, engines):
        engines.auto.execute_workflow = AsyncMock(return_value=FakeExecution())
        resp = client.post("/ai/automation/workflows/wf1/execute",
                           json={"workflow_id": "wf1", "trigger_data": {"a": 1}})
        assert resp.status_code == 200
        body = resp.json()
        assert body["execution_id"] == "ex1"
        assert body["status"] == "completed"
        assert body["results"] == {"ok": True}

    def test_workflow_not_found_404(self, client, engines):
        engines.auto.execute_workflow = AsyncMock(side_effect=ValueError("no such"))
        resp = client.post("/ai/automation/workflows/wf1/execute",
                           json={"workflow_id": "wf1", "trigger_data": {}})
        assert resp.status_code == 404

    def test_error_500(self, client, engines):
        engines.auto.execute_workflow = AsyncMock(side_effect=RuntimeError("boom"))
        resp = client.post("/ai/automation/workflows/wf1/execute",
                           json={"workflow_id": "wf1", "trigger_data": {}})
        assert resp.status_code == 500


class TestWorkflowList:
    def test_success(self, client, engines):
        engines.auto.list_workflows.return_value = [FakeWorkflow(updated=True),
                                                    FakeWorkflow(updated=False)]
        resp = client.get("/ai/automation/workflows")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 2
        assert body[0]["updated_at"] is not None
        assert body[1]["updated_at"] is None
        assert body[0]["action_count"] == 1
        engines.auto.list_workflows.assert_called_once_with(True)

    def test_inactive_only_param(self, client, engines):
        engines.auto.list_workflows.return_value = []
        client.get("/ai/automation/workflows", params={"active_only": "false"})
        assert engines.auto.list_workflows.call_args[0][0] is False

    def test_error_500(self, client, engines):
        engines.auto.list_workflows.side_effect = RuntimeError("boom")
        resp = client.get("/ai/automation/workflows")
        assert resp.status_code == 500


class TestWorkflowExecutions:
    def test_success(self, client, engines):
        engines.auto.get_execution_history.return_value = [FakeExecution()]
        resp = client.get("/ai/automation/workflows/wf1/executions")
        assert resp.status_code == 200
        body = resp.json()
        assert body[0]["execution_id"] == "ex1"
        assert body[0]["error_count"] == 0
        engines.auto.get_execution_history.assert_called_once_with("wf1", 10)

    def test_error_500(self, client, engines):
        engines.auto.get_execution_history.side_effect = RuntimeError("boom")
        resp = client.get("/ai/automation/workflows/wf1/executions")
        assert resp.status_code == 500


class TestHealthAndRoot:
    def test_health_healthy(self, client, engines):
        engines.nlp.parse_command.return_value = SimpleNamespace(confidence=0.5)
        engines.data.entity_registry = {"e1": {}}
        engines.data.relationship_registry = {}
        engines.auto.workflows = {"wf1": SimpleNamespace(is_active=True)}
        engines.auto.executions = ["ex1"]
        resp = client.get("/ai/health")
        body = resp.json()
        assert body["status"] == "healthy"
        assert body["components"]["nlp_engine"] == "healthy"
        assert body["metrics"]["unified_entities"] == 1
        assert body["metrics"]["active_workflows"] == 1
        assert body["metrics"]["total_executions"] == 1

    def test_health_unhealthy(self, client, engines):
        engines.nlp.parse_command.side_effect = RuntimeError("boom")
        resp = client.get("/ai/health")
        body = resp.json()
        assert body["status"] == "unhealthy"
        assert body["metrics"] == {}

    def test_root(self, client):
        resp = client.get("/ai/")
        assert resp.json()["service"] == "ai_integration"
