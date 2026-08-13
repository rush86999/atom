"""Coverage wave 81 — core/unified_search_endpoints.py (52% → ~100%).

Covers the hybrid-search body (workspace resolution from the authenticated
user — BUG-098 semantics, LanceDB unavailability, doc_type post-filtering,
semantic/keyword/hybrid scoring, min_score filter, limit cap, 500 and
HTTPException re-raise), suggestions (empty-DB, exception tolerance) and
health (disabled/happy/unavailable/error). Deps fully mocked: get_current_user
override + patched get_lancedb_handler.
"""
import os
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

import core.unified_search_endpoints as use
from core.auth import get_current_user


def make_handler(db_available=True, results=None):
    handler = Mock()
    handler.db = object() if db_available else None
    handler.db_path = "/data/lancedb" if db_available else None
    handler._ensure_db = Mock()
    handler._ensure_embedder = Mock()
    handler.search = Mock(return_value=results if results is not None else [])
    return handler


def make_row(row_id="d1", text="quarterly report", score=0.9,
             metadata=None, source="s3://x"):
    return {
        "id": row_id,
        "text": text,
        "score": score,
        "source": source,
        "metadata": metadata if metadata is not None else {
            "doc_type": "report", "title": "Q3",
        },
    }


@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(use.router)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id="u1", tenant_id="t1",
        workspaces=[SimpleNamespace(id="ws-u1")])
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


class TestHybridSearch:
    def test_anon_401(self):
        app = FastAPI()
        app.include_router(use.router)
        resp = TestClient(app).post("/api/lancedb-search/hybrid",
                                    json={"query": "report"})
        assert resp.status_code == 401

    def test_success_hybrid_scoring(self, app, client):
        handler = make_handler(results=[make_row(text="quarterly review", score=0.8)])
        with patch.object(use, "get_lancedb_handler", return_value=handler):
            resp = client.post("/api/lancedb-search/hybrid", json={
                "query": "report", "search_type": "hybrid", "limit": 20})
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["total_count"] == 1
        assert body["query"] == "report"
        assert body["search_type"] == "hybrid"
        result = body["results"][0]
        assert result["id"] == "d1"
        assert result["title"] == "Q3"
        assert result["doc_type"] == "report"
        assert result["similarity_score"] == 0.8
        assert result["keyword_score"] == 0.0
        assert result["combined_score"] == 0.8 * 0.7
        handler._ensure_db.assert_called_once()
        handler._ensure_embedder.assert_called_once()
        # BUG-098: workspace resolved from the authenticated user
        handler.search.assert_called_once_with(
            "documents", "report", limit=20, filter_str=None, user_id=None)

    def test_keyword_score_boost(self, app, client):
        handler = make_handler(results=[make_row(
            text="report report report", score=0.5)])
        with patch.object(use, "get_lancedb_handler", return_value=handler):
            resp = client.post("/api/lancedb-search/hybrid", json={
                "query": "report", "search_type": "keyword"})
        result = resp.json()["results"][0]
        assert result["keyword_score"] == 0.8
        assert result["combined_score"] == 0.8

    def test_semantic_score_only(self, app, client):
        handler = make_handler(results=[make_row(score=0.7)])
        with patch.object(use, "get_lancedb_handler", return_value=handler):
            resp = client.post("/api/lancedb-search/hybrid", json={
                "query": "report", "search_type": "semantic"})
        result = resp.json()["results"][0]
        assert result["combined_score"] == 0.7

    def test_keyword_capped_at_one(self, app, client):
        handler = make_handler(results=[make_row(
            text="a" + " report" * 50, score=0.1)])
        with patch.object(use, "get_lancedb_handler", return_value=handler):
            resp = client.post("/api/lancedb-search/hybrid", json={
                "query": "report", "search_type": "keyword"})
        assert resp.json()["results"][0]["keyword_score"] == 1.0

    def test_workspace_id_from_request_wins(self, app, client):
        handler = make_handler(results=[make_row()])
        with patch.object(use, "get_lancedb_handler", return_value=handler):
            client.post("/api/lancedb-search/hybrid", json={
                "query": "report", "workspace_id": "ws-explicit"})
            assert use.get_lancedb_handler.call_args[0][0] == "ws-explicit"
            assert handler.search.call_args[1]["limit"] == 20

    def test_default_shared_when_no_workspaces(self, app, client):
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
            id="u1", tenant_id="t1", workspaces=[])
        handler = make_handler(results=[])
        with patch.object(use, "get_lancedb_handler", return_value=handler):
            client.post("/api/lancedb-search/hybrid", json={"query": "q"})
            assert use.get_lancedb_handler.call_args[0][0] == "default_shared"

    def test_lancedb_unavailable_returns_empty(self, app, client):
        handler = make_handler(db_available=False)
        with patch.object(use, "get_lancedb_handler", return_value=handler):
            resp = client.post("/api/lancedb-search/hybrid", json={"query": "q"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["results"] == []
        assert body["total_count"] == 0

    def test_doc_type_post_filter_skips_mismatches(self, app, client):
        handler = make_handler(results=[
            make_row("d1", metadata={"doc_type": "report", "title": "A"}),
            make_row("d2", metadata={"doc_type": "meeting", "title": "B"}),
        ])
        with patch.object(use, "get_lancedb_handler", return_value=handler):
            resp = client.post("/api/lancedb-search/hybrid", json={
                "query": "q", "filters": {"doc_type": ["report"]}})
        results = resp.json()["results"]
        assert [r["id"] for r in results] == ["d1"]
        # search limit doubled for post-filtering headroom
        assert handler.search.call_args[1]["limit"] == 40

    def test_min_score_filter_skips_low(self, app, client):
        handler = make_handler(results=[
            make_row("d1", score=0.9),
            make_row("d2", score=0.1),
        ])
        with patch.object(use, "get_lancedb_handler", return_value=handler):
            resp = client.post("/api/lancedb-search/hybrid", json={
                "query": "q", "search_type": "semantic",
                "filters": {"min_score": 0.5}})
        assert [r["id"] for r in resp.json()["results"]] == ["d1"]

    def test_limit_caps_results(self, app, client):
        handler = make_handler(results=[make_row(f"d{i}") for i in range(5)])
        with patch.object(use, "get_lancedb_handler", return_value=handler):
            resp = client.post("/api/lancedb-search/hybrid", json={
                "query": "q", "limit": 2})
        assert len(resp.json()["results"]) == 2

    def test_results_sorted_by_combined_score(self, app, client):
        handler = make_handler(results=[
            make_row("low", score=0.3),
            make_row("high", score=0.9),
        ])
        with patch.object(use, "get_lancedb_handler", return_value=handler):
            resp = client.post("/api/lancedb-search/hybrid", json={
                "query": "q", "search_type": "hybrid"})
        ids = [r["id"] for r in resp.json()["results"]]
        assert ids == ["high", "low"]

    def test_missing_metadata_defaults(self, app, client):
        handler = make_handler(results=[{"id": "x", "text": "t", "score": 0.5,
                                         "source": "s", "metadata": {}}])
        with patch.object(use, "get_lancedb_handler", return_value=handler):
            resp = client.post("/api/lancedb-search/hybrid", json={"query": "q"})
        result = resp.json()["results"][0]
        assert result["title"] == "Untitled"
        assert result["doc_type"] == "unknown"
        assert result["metadata"] == {}

    def test_internal_error_500(self, app, client):
        handler = make_handler()
        handler.search = Mock(side_effect=RuntimeError("lancedb down"))
        with patch.object(use, "get_lancedb_handler", return_value=handler):
            resp = client.post("/api/lancedb-search/hybrid", json={"query": "q"})
        assert resp.status_code == 500

    def test_http_exception_reraised(self, app, client):
        handler = make_handler()
        handler.search = Mock(side_effect=HTTPException(status_code=418))
        with patch.object(use, "get_lancedb_handler", return_value=handler):
            resp = client.post("/api/lancedb-search/hybrid", json={"query": "q"})
        assert resp.status_code == 418

    @pytest.mark.parametrize("payload", [
        {"query": "q", "limit": 0},
        {"query": "q", "limit": 101},
        {"query": "q", "search_type": "fuzzy"},
    ])
    def test_request_validation_422(self, app, client, payload):
        with patch.object(use, "get_lancedb_handler", return_value=make_handler()):
            resp = client.post("/api/lancedb-search/hybrid", json=payload)
        assert resp.status_code == 422


class TestSuggestions:
    def test_anon_401(self):
        app = FastAPI()
        app.include_router(use.router)
        resp = TestClient(app).get("/api/lancedb-search/suggestions?query=rep")
        assert resp.status_code == 401

    def test_empty_query_422(self, app, client):
        with patch.object(use, "get_lancedb_handler",
                          return_value=make_handler(db_available=False)):
            resp = client.get("/api/lancedb-search/suggestions?query=")
        assert resp.status_code == 422

    def test_no_db_empty_suggestions(self, app, client):
        with patch.object(use, "get_lancedb_handler",
                          return_value=make_handler(db_available=False)):
            resp = client.get("/api/lancedb-search/suggestions?query=rep")
        assert resp.status_code == 200
        assert resp.json() == {"success": True, "suggestions": []}

    def test_db_present_empty_suggestions(self, app, client):
        with patch.object(use, "get_lancedb_handler",
                          return_value=make_handler(db_available=True)):
            resp = client.get("/api/lancedb-search/suggestions?query=rep&limit=3")
        assert resp.status_code == 200
        assert resp.json()["suggestions"] == []

    def test_exception_tolerated(self, app, client):
        with patch.object(use, "get_lancedb_handler",
                          side_effect=RuntimeError("boom")):
            resp = client.get("/api/lancedb-search/suggestions?query=rep")
        assert resp.status_code == 200
        assert resp.json()["suggestions"] == []


class TestHealth:
    def test_disabled_via_env(self, client, app):
        with patch.dict(os.environ, {"ATOM_DISABLE_LANCEDB": "true"}):
            resp = client.get("/api/lancedb-search/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "disabled"
        assert body["lancedb_available"] is False
        assert body["db_path"] is None

    def test_healthy(self, client, app):
        with patch.object(use, "get_lancedb_handler",
                          return_value=make_handler(db_available=True)):
            resp = client.get("/api/lancedb-search/health")
        body = resp.json()
        assert body["status"] == "healthy"
        assert body["lancedb_available"] is True
        assert body["db_path"] == "/data/lancedb"

    def test_unavailable(self, client, app):
        with patch.object(use, "get_lancedb_handler",
                          return_value=make_handler(db_available=False)):
            resp = client.get("/api/lancedb-search/health")
        body = resp.json()
        assert body["status"] == "unavailable"
        assert body["lancedb_available"] is False

    def test_error(self, client, app):
        with patch.object(use, "get_lancedb_handler",
                          side_effect=RuntimeError("boom")):
            resp = client.get("/api/lancedb-search/health")
        body = resp.json()
        assert body["status"] == "error"
        assert body["lancedb_available"] is False
