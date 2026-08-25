"""Coverage-push wave 32 — api/learning_routes.py + api/graphrag_routes.py.

TDD bug-hunt (RED -> GREEN, all fixes local to these two route modules):

  * graphrag POST /ingest: async ``graphrag_engine.ingest_document()`` was
    never awaited -> silent no-op: HTTP 200 "Document ingested successfully"
    with nothing stored.
  * graphrag POST /query: async ``graphrag_engine.query()`` was never awaited
    -> a coroutine landed in the response body -> 500 on every query.
  * graphrag GET /context: imported ``get_graphrag_context`` which no longer
    exists in core.graphrag_engine (replaced by ``get_context_for_ai``) ->
    ImportError -> 500 on every call.
  * graphrag GET /canonical-search: positional call
    ``canonical_search(workspace_id, type, q)`` mapped q onto ``entity_type``
    and left ``query=""`` (signature: workspace_id, tenant_id, entity_type,
    query) -> search always returned empty results.
  * learning GET /tenant/summary: called ``get_learning_progress(tenant_id=...)``
    without the required ``agent_id`` positional -> TypeError -> 500 on every
    call.
"""
from __future__ import annotations

import contextlib
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.auth import get_current_user
from core.database import get_db


# ---------------------------------------------------------------------------
# Shared harness
# ---------------------------------------------------------------------------
def _make_app(router):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id="u-1", tenant_id="t-1", role="user"
    )
    return app


@contextlib.contextmanager
def _yield_session(session):
    yield session


def _patch_db_session(mock_session):
    """Patch the get_db_session context manager used by graphrag handlers."""
    return patch("core.database.get_db_session", lambda: _yield_session(mock_session))


def _node(nid, name, type="org", description="d", properties=None):
    return SimpleNamespace(
        id=nid, name=name, type=type,
        description=description,
        properties=properties if properties is not None else {},
    )


def _edge(eid, src, dst, rel_type="owns", properties=None):
    return SimpleNamespace(
        id=eid, source_node_id=src, target_node_id=dst,
        relationship_type=rel_type,
        properties=properties if properties is not None else {},
    )


# ===========================================================================
# api/graphrag_routes.py
# ===========================================================================
class TestGraphRAGRoutes:
    @pytest.fixture(autouse=True)
    def _engine(self):
        with patch("core.graphrag_engine.graphrag_engine") as eng:
            yield eng

    @pytest.fixture
    def client(self):
        from api.graphrag_routes import router
        return TestClient(_make_app(router), raise_server_exceptions=False)

    # ---- POST /api/graphrag/ingest ---------------------------------------
    def test_ingest_awaits_async_engine(self, client, _engine):
        """RED before fix: ingest_document is async but was called without
        await -> coroutine discarded, nothing ingested."""
        _engine.ingest_document = AsyncMock(return_value=None)
        r = client.post("/api/graphrag/ingest", json={
            "doc_id": "d1", "text": "John works at Acme", "source": "api",
        })
        assert r.status_code == 200
        assert r.json()["success"] is True
        # R83: routes partition by the caller's workspace (mock user has none
        # → "default"), not by user id.
        _engine.ingest_document.assert_awaited_once_with(
            workspace_id="default", doc_id="d1",
            text="John works at Acme", source="api",
        )

    # ---- GET /api/graphrag/entities --------------------------------------
    def test_list_entities_success(self, client, _engine):
        sess = MagicMock()
        sess.query.return_value.filter_by.return_value.limit.return_value.all.return_value = [
            _node("n1", "Acme", type="organization", properties={"industry": "Tech"}),
            _node("n2", "John"),
        ]
        with _patch_db_session(sess):
            r = client.get("/api/graphrag/entities", params={"workspace_id": "ws1"})
        assert r.status_code == 200
        entities = r.json()["data"]["entities"]
        assert len(entities) == 2
        assert entities[0] == {
            "id": "n1", "name": "Acme", "type": "organization",
            "description": "d", "properties": {"industry": "Tech"},
        }

    def test_list_entities_empty(self, client, _engine):
        sess = MagicMock()
        sess.query.return_value.filter_by.return_value.limit.return_value.all.return_value = []
        with _patch_db_session(sess):
            r = client.get("/api/graphrag/entities", params={"workspace_id": "ws1"})
        assert r.status_code == 200
        assert r.json()["data"]["entities"] == []

    # ---- POST /api/graphrag/entities -------------------------------------
    def test_add_entity_success(self, client, _engine):
        _engine.add_entity.return_value = "node-1"
        r = client.post(
            "/api/graphrag/entities", params={"workspace_id": "ws1"},
            json={"name": "Acme", "type": "organization", "description": "d",
                  "properties": {"industry": "Tech"}},
        )
        assert r.status_code == 200
        assert r.json()["data"]["id"] == "node-1"
        assert _engine.add_entity.call_args.args[0].name == "Acme"

    def test_add_entity_failure_raises_500(self, client, _engine):
        """RED before Aug-10 fix: `return router.error_response(...)` serialized
        the HTTPException as a 200 body; must raise -> 500."""
        _engine.add_entity.return_value = None
        r = client.post(
            "/api/graphrag/entities", params={"workspace_id": "ws1"},
            json={"name": "Acme", "type": "organization"},
        )
        assert r.status_code == 500
        assert r.json()["detail"]["error"]["code"] == "INGESTION_FAILED"

    # ---- GET /api/graphrag/canonical-search ------------------------------
    def test_canonical_search_success(self, client, _engine):
        """RED before fix: positional call mapped q onto entity_type and left
        query='' -> search always empty."""
        _engine.canonical_search.return_value = [{"id": "c1"}]
        r = client.get(
            "/api/graphrag/canonical-search",
            params={"workspace_id": "ws1", "type": "company", "q": "Acme"},
        )
        assert r.status_code == 200
        assert r.json()["data"]["results"] == [{"id": "c1"}]
        _engine.canonical_search.assert_called_once_with(
            workspace_id="ws1", entity_type="company", query="Acme"
        )

    def test_canonical_search_query_too_long_422(self, client, _engine):
        r = client.get(
            "/api/graphrag/canonical-search",
            params={"workspace_id": "ws1", "type": "company", "q": "x" * 501},
        )
        assert r.status_code == 422
        _engine.canonical_search.assert_not_called()

    # ---- GET /api/graphrag/relationships ---------------------------------
    def test_list_relationships_maps_node_names(self, client, _engine):
        sess = MagicMock()
        sess.query.return_value.filter_by.return_value.limit.return_value.all.return_value = [
            _edge("e1", "n1", "n2"),
        ]
        sess.query.return_value.filter.return_value.all.return_value = [
            _node("n1", "Acme"), _node("n2", "Box"),
        ]
        with _patch_db_session(sess):
            r = client.get("/api/graphrag/relationships", params={"workspace_id": "ws1"})
        assert r.status_code == 200
        rels = r.json()["data"]["relationships"]
        assert len(rels) == 1
        assert rels[0]["from_entity"] == "Acme"
        assert rels[0]["to_entity"] == "Box"
        assert rels[0]["type"] == "owns"

    def test_list_relationships_falls_back_to_ids(self, client, _engine):
        sess = MagicMock()
        sess.query.return_value.filter_by.return_value.limit.return_value.all.return_value = [
            _edge("e1", "n1", "n2"),
        ]
        sess.query.return_value.filter.return_value.all.return_value = []
        with _patch_db_session(sess):
            r = client.get("/api/graphrag/relationships", params={"workspace_id": "ws1"})
        assert r.status_code == 200
        rel = r.json()["data"]["relationships"][0]
        assert rel["from_entity"] == "n1"
        assert rel["to_entity"] == "n2"

    def test_list_relationships_empty(self, client, _engine):
        sess = MagicMock()
        sess.query.return_value.filter_by.return_value.limit.return_value.all.return_value = []
        with _patch_db_session(sess):
            r = client.get("/api/graphrag/relationships", params={"workspace_id": "ws1"})
        assert r.status_code == 200
        assert r.json()["data"]["relationships"] == []

    # ---- POST /api/graphrag/relationships --------------------------------
    def _add_rel_body(self, src="Acme", dst="Box"):
        return {
            "from_entity": src, "to_entity": dst,
            "relationship_type": "owns", "description": "d", "properties": {},
        }

    def test_add_relationship_success_by_name(self, client, _engine):
        sess = MagicMock()
        src, dst = _node("n1", "Acme"), _node("n2", "Box")
        sess.query.return_value.filter_by.return_value.first.side_effect = [src, dst]
        _engine.add_relationship.return_value = "rel-1"
        with _patch_db_session(sess):
            r = client.post(
                "/api/graphrag/relationships", params={"workspace_id": "ws1"},
                json=self._add_rel_body(),
            )
        assert r.status_code == 200
        assert r.json()["data"]["id"] == "rel-1"
        assert _engine.add_relationship.call_args.args[0].from_entity == "n1"
        assert _engine.add_relationship.call_args.args[0].to_entity == "n2"

    def test_add_relationship_src_resolved_by_id(self, client, _engine):
        sess = MagicMock()
        src, dst = _node("n1", "Acme"), _node("n2", "Box")
        # name lookups miss for src, hit for dst; id fallback hits for src
        sess.query.return_value.filter_by.return_value.first.side_effect = [None, dst, src]
        _engine.add_relationship.return_value = "rel-1"
        with _patch_db_session(sess):
            r = client.post(
                "/api/graphrag/relationships", params={"workspace_id": "ws1"},
                json=self._add_rel_body(src="n1"),
            )
        assert r.status_code == 200
        assert r.json()["data"]["id"] == "rel-1"

    def test_add_relationship_dst_resolved_by_id(self, client, _engine):
        sess = MagicMock()
        src, dst = _node("n1", "Acme"), _node("n2", "Box")
        sess.query.return_value.filter_by.return_value.first.side_effect = [src, None, dst]
        _engine.add_relationship.return_value = "rel-1"
        with _patch_db_session(sess):
            r = client.post(
                "/api/graphrag/relationships", params={"workspace_id": "ws1"},
                json=self._add_rel_body(dst="n2"),
            )
        assert r.status_code == 200
        assert r.json()["data"]["id"] == "rel-1"

    def test_add_relationship_missing_entities_404(self, client, _engine):
        sess = MagicMock()
        sess.query.return_value.filter_by.return_value.first.side_effect = [None, None, None, None]
        with _patch_db_session(sess):
            r = client.post(
                "/api/graphrag/relationships", params={"workspace_id": "ws1"},
                json=self._add_rel_body(),
            )
        assert r.status_code == 404
        assert r.json()["detail"]["error"]["code"] == "NOT_FOUND"

    def test_add_relationship_failure_raises_500(self, client, _engine):
        sess = MagicMock()
        src, dst = _node("n1", "Acme"), _node("n2", "Box")
        sess.query.return_value.filter_by.return_value.first.side_effect = [src, dst]
        _engine.add_relationship.return_value = None
        with _patch_db_session(sess):
            r = client.post(
                "/api/graphrag/relationships", params={"workspace_id": "ws1"},
                json=self._add_rel_body(),
            )
        assert r.status_code == 500
        assert r.json()["detail"]["error"]["code"] == "INGESTION_FAILED"

    # ---- POST /api/graphrag/build-communities ----------------------------
    def test_build_communities(self, client, _engine):
        _engine.build_communities.return_value = {"communities": 2}
        r = client.post("/api/graphrag/build-communities", params={"user_id": "u-1"})
        assert r.status_code == 200
        assert r.json()["data"]["user_id"] == "u-1"
        # R83: workspace partition — mock user has no workspace → "default".
        _engine.build_communities.assert_called_once_with("default")

    # ---- POST /api/graphrag/query ----------------------------------------
    def test_query_awaits_async_engine(self, client, _engine):
        """RED before fix: query is async but was called without await ->
        coroutine in response body -> 500 on every query."""
        _engine.query = AsyncMock(return_value={"mode": "local", "answer": "ok"})
        r = client.post("/api/graphrag/query", json={
            "query": "who is john", "workspace_id": "ws1", "mode": "auto",
        })
        assert r.status_code == 200
        assert r.json()["data"]["answer"] == "ok"
        _engine.query.assert_awaited_once_with("ws1", "who is john", "auto")

    def test_query_missing_query_422(self, client, _engine):
        r = client.post("/api/graphrag/query", json={"workspace_id": "ws1"})
        assert r.status_code == 422

    # ---- GET /api/graphrag/entities/{id}/neighbors ------------------------
    def test_neighbors_entity_not_found_404(self, client, _engine):
        sess = MagicMock()
        sess.query.return_value.filter_by.return_value.first.return_value = None
        with _patch_db_session(sess):
            r = client.get(
                "/api/graphrag/entities/ghost/neighbors",
                params={"workspace_id": "ws1"},
            )
        assert r.status_code == 404
        assert r.json()["detail"]["error"]["code"] == "NOT_FOUND"

    def test_neighbors_success(self, client, _engine):
        sess = MagicMock()
        sess.query.return_value.filter_by.return_value.first.return_value = _node("n1", "Acme")
        _engine.local_search.return_value = {"entities": []}
        with _patch_db_session(sess):
            r = client.get(
                "/api/graphrag/entities/n1/neighbors",
                params={"workspace_id": "ws1", "depth": 2},
            )
        assert r.status_code == 200
        assert r.json()["data"]["entities"] == []
        _engine.local_search.assert_called_once_with("ws1", "Acme", depth=2)

    # ---- GET /api/graphrag/context ---------------------------------------
    def test_context_success(self, client, _engine):
        """RED before fix: imported get_graphrag_context which no longer exists
        -> ImportError -> 500 on every call."""
        _engine.get_context_for_ai = AsyncMock(return_value="context text")
        r = client.get("/api/graphrag/context", params={"user_id": "ws1", "query": "hello"})
        assert r.status_code == 200
        assert r.json()["data"]["user_id"] == "ws1"
        assert r.json()["data"]["context"] == "context text"
        # R83: workspace partition — mock user has no workspace → "default"
        # (the user_id param is echoed in the response, not used for routing).
        _engine.get_context_for_ai.assert_awaited_once_with(
            workspace_id="default", query="hello"
        )

    # ---- GET /api/graphrag/stats -----------------------------------------
    def test_stats_with_user_id(self, client, _engine):
        _engine.get_stats.return_value = {"nodes": 3}
        r = client.get("/api/graphrag/stats", params={"user_id": "u-1"})
        assert r.status_code == 200
        assert r.json()["data"]["nodes"] == 3
        _engine.get_stats.assert_called_once_with("u-1")

    def test_stats_without_user_id(self, client, _engine):
        _engine.get_stats.return_value = {"nodes": 0}
        r = client.get("/api/graphrag/stats")
        assert r.status_code == 200
        _engine.get_stats.assert_called_once_with(None)


# ===========================================================================
# api/learning_routes.py
# ===========================================================================
class TestLearningRoutes:
    @pytest.fixture(autouse=True)
    def _shared_db(self):
        self.db_mock = MagicMock()
        yield
        self.db_mock = None

    @pytest.fixture
    def client(self):
        from api.learning_routes import router
        app = _make_app(router)
        app.dependency_overrides[get_db] = lambda: self.db_mock
        return TestClient(app, raise_server_exceptions=False)

    # ---- GET /api/learning/progress/{agent_id} ---------------------------
    def test_progress_found(self, client):
        with patch("api.learning_routes.ContinuousLearningService") as Svc:
            Svc.return_value.get_learning_progress.return_value = {
                "agent_id": "ag-1", "status": "learning", "positive_rate": 0.8,
            }
            r = client.get("/api/learning/progress/ag-1")
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["agent_id"] == "ag-1"
        assert data["positive_rate"] == 0.8
        Svc.return_value.get_learning_progress.assert_called_once_with(
            tenant_id="t-1", agent_id="ag-1"
        )

    def test_progress_not_found_404(self, client):
        with patch("api.learning_routes.ContinuousLearningService") as Svc:
            Svc.return_value.get_learning_progress.return_value = None
            r = client.get("/api/learning/progress/ag-1")
        assert r.status_code == 404
        assert r.json()["detail"]["error"]["code"] == "NOT_FOUND"

    # ---- GET /api/learning/adaptations/{agent_id} ------------------------
    def test_adaptations(self, client):
        adaptations = [{"type": "parameter_adjustment", "priority": "high"}]
        with patch("api.learning_routes.ContinuousLearningService") as Svc:
            Svc.return_value.generate_adaptations.return_value = adaptations
            r = client.get("/api/learning/adaptations/ag-1")
        assert r.status_code == 200
        assert r.json()["data"]["adaptations"] == adaptations
        Svc.return_value.generate_adaptations.assert_called_once_with(
            tenant_id="t-1", agent_id="ag-1"
        )

    # ---- GET /api/learning/tenant/summary --------------------------------
    def test_tenant_summary_empty(self, client):
        """RED before fix: get_learning_progress requires agent_id but the
        route called it with tenant_id only -> TypeError -> 500. Real service
        is used here so the signature error surfaces."""
        self.db_mock.query.return_value.filter.return_value.distinct.return_value.all.return_value = []
        r = client.get("/api/learning/tenant/summary")
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["count"] == 0
        assert data["agents"] == []

    def test_tenant_summary_aggregates_per_agent(self, client):
        self.db_mock.query.return_value.filter.return_value.distinct.return_value.all.return_value = [
            ("ag-1",), ("ag-2",),
        ]
        with patch("api.learning_routes.ContinuousLearningService") as Svc:
            Svc.return_value.get_learning_progress.side_effect = (
                lambda tenant_id, agent_id: {"agent_id": agent_id, "status": "learning"}
            )
            r = client.get("/api/learning/tenant/summary")
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["count"] == 2
        assert [a["agent_id"] for a in data["agents"]] == ["ag-1", "ag-2"]
        assert Svc.return_value.get_learning_progress.call_args_list[0].kwargs == {
            "tenant_id": "t-1", "agent_id": "ag-1"
        }
        assert Svc.return_value.get_learning_progress.call_args_list[1].kwargs == {
            "tenant_id": "t-1", "agent_id": "ag-2"
        }
