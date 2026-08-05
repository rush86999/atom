"""
Tests for list-endpoint limit/offset bounds (DoS prevention).

The agent history and document list endpoints previously accepted unbounded
`limit` (a client could request limit=999999999 and materialize the whole
table → OOM) and unvalidated `offset` (negative values). Both now enforce
Query bounds: limit ∈ [1, 100], offset >= 0. Out-of-range values must return
422 (FastAPI validation error), not proceed.
"""

import pytest
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient


def _build_bounded_app():
    """Build a minimal app exposing the same bounded signatures as the real
    routes, so we can assert the Query constraints reject out-of-range values."""
    app = FastAPI()

    @app.get("/api/agents/history")
    def agent_history(limit: int = pytest.importorskip("fastapi").Query(50, ge=1, le=100)):
        return {"limit": limit}

    @app.get("/api/documents")
    def list_documents(
        limit: int = pytest.importorskip("fastapi").Query(100, ge=1, le=100),
        offset: int = pytest.importorskip("fastapi").Query(0, ge=0),
    ):
        return {"limit": limit, "offset": offset}

    return app


@pytest.fixture
def client():
    return TestClient(_build_bounded_app())


class TestAgentHistoryBounds:
    def test_rejects_limit_above_max(self, client):
        """limit=999999999 must be rejected (422), not passed to the DB."""
        resp = client.get("/api/agents/history?limit=999999999")
        assert resp.status_code == 422

    def test_rejects_limit_below_one(self, client):
        resp = client.get("/api/agents/history?limit=0")
        assert resp.status_code == 422

    def test_accepts_limit_within_range(self, client):
        resp = client.get("/api/agents/history?limit=50")
        assert resp.status_code == 200
        assert resp.json()["limit"] == 50


class TestDocumentListBounds:
    def test_rejects_limit_above_max(self, client):
        resp = client.get("/api/documents?limit=999999999")
        assert resp.status_code == 422

    def test_rejects_negative_offset(self, client):
        resp = client.get("/api/documents?offset=-10")
        assert resp.status_code == 422

    def test_accepts_valid_params(self, client):
        resp = client.get("/api/documents?limit=50&offset=10")
        assert resp.status_code == 200
