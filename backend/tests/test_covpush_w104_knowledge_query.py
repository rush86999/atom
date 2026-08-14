# -*- coding: utf-8 -*-
"""Coverage wave 104 — core/knowledge_query_endpoints.py.

TestClient-based coverage of the /api/knowledge/query surface:
- anonymous -> 401 (auth verified), authenticated success in both
  GraphRAG modes (local: entities + relationships; global: summaries),
  GraphRAG-returned error surfaced as a graceful answer, missing-answer
  default, engine exception -> generic 500, workspace_id passthrough,
  factory helper.

No LLM spend, no network; ServiceFactory.get_graphrag_engine is mocked.
"""
from unittest.mock import AsyncMock, MagicMock

import asyncio
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.auth import get_current_user
from core.database import get_db
from core.knowledge_query_endpoints import (
    KnowledgeQueryManager,
    get_knowledge_query_manager,
    router,
)


@pytest.fixture()
def user():
    u = MagicMock()
    u.id = "user-1"
    return u


@pytest.fixture()
def app(user):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: MagicMock()
    app.dependency_overrides[get_current_user] = lambda: user
    yield app
    app.dependency_overrides.clear()


@pytest.fixture()
def client(app):
    return TestClient(app)


@pytest.fixture()
def anon_app():
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: MagicMock()
    yield app
    app.dependency_overrides.clear()


@pytest.fixture()
def anon_client(anon_app):
    return TestClient(anon_app)


@pytest.fixture()
def engine():
    engine = MagicMock()
    engine.query = AsyncMock()
    return engine


@pytest.fixture(autouse=True)
def _patch_factory(engine, monkeypatch):
    monkeypatch.setattr(
        "core.knowledge_query_endpoints.ServiceFactory.get_graphrag_engine",
        MagicMock(return_value=engine),
    )


def _local_result():
    return {
        "answer": "Project Alpha is on track.",
        "mode": "local",
        "entities": [
            {"name": "Alpha", "type": "project", "description": "Flagship"},
            {"name": "Beta", "type": "initiative", "description": "Second"},
        ],
        "relationships": [{"from": "Alpha", "to": "Beta", "type": "depends_on"}],
    }


def _global_result():
    return {
        "answer": "Three communities cover the topic.",
        "mode": "global",
        "summaries": ["Community one summary", "Community two summary"],
    }


class TestKnowledgeQueryEndpoint:
    def test_anonymous_401(self, anon_client):
        resp = anon_client.post(
            "/api/knowledge/query", json={"query": "hi", "user_id": "u1"}
        )
        assert resp.status_code == 401

    def test_local_mode_success(self, client, engine):
        engine.query.return_value = _local_result()
        resp = client.post(
            "/api/knowledge/query",
            json={"query": "what is Project Alpha?", "user_id": "u1"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["answer"] == "Project Alpha is on track."
        assert body["mode"] == "local"
        assert "Entity: Alpha (project) - Flagship" in body["relevant_facts"]
        assert "Relationship: Alpha -> depends_on -> Beta" in body["relevant_facts"]
        engine.query.assert_awaited_once()

    def test_global_mode_success(self, client, engine):
        engine.query.return_value = _global_result()
        resp = client.post(
            "/api/knowledge/query",
            json={"query": "summarize everything", "user_id": "u1"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["mode"] == "global"
        assert "Community Summary: Community one summary" in body["relevant_facts"][0]
        assert body["relevant_facts"][0].endswith("...")

    def test_graphrag_error_graceful_answer(self, client, engine):
        engine.query.return_value = {"error": "vector store unavailable"}
        resp = client.post(
            "/api/knowledge/query",
            json={"query": "q", "user_id": "u1"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "error while searching" in body["answer"]
        assert body["relevant_facts"] == []

    def test_missing_answer_default(self, client, engine):
        engine.query.return_value = {"mode": "global", "summaries": []}
        resp = client.post(
            "/api/knowledge/query",
            json={"query": "q", "user_id": "u1"},
        )
        assert resp.json()["answer"] == "No answer could be synthesized."

    def test_workspace_id_passthrough(self, client, engine):
        engine.query.return_value = _local_result()
        resp = client.post(
            "/api/knowledge/query",
            json={"query": "q", "user_id": "u1", "workspace_id": "ws-9"},
        )
        assert resp.status_code == 200
        assert engine.query.await_args[0][0] == "ws-9"

    def test_engine_exception_generic_500(self, client, engine):
        engine.query.side_effect = RuntimeError("graph broken")
        resp = client.post(
            "/api/knowledge/query",
            json={"query": "q", "user_id": "u1"},
        )
        assert resp.status_code == 500
        assert resp.json()["detail"] == "Internal error"

    def test_facts_truncated_to_ten(self, client, engine):
        result = _local_result()
        result["entities"] = [
            {"name": f"E{i}", "type": "t", "description": "d"}
            for i in range(12)
        ]
        result["relationships"] = [
            {"from": f"a{i}", "to": "b", "type": "x"} for i in range(12)
        ]
        engine.query.return_value = result
        resp = client.post(
            "/api/knowledge/query",
            json={"query": "q", "user_id": "u1"},
        )
        facts = resp.json()["relevant_facts"]
        assert len(facts) == 20  # 10 entities + 10 relationships

    def test_entity_missing_description(self, client, engine):
        result = _local_result()
        result["entities"] = [{"name": "X", "type": "thing"}]
        engine.query.return_value = result
        resp = client.post(
            "/api/knowledge/query",
            json={"query": "q", "user_id": "u1"},
        )
        assert "Entity: X (thing) - " in resp.json()["relevant_facts"][0]


class TestKnowledgeQueryManager:
    def test_default_workspace(self, engine):
        manager = KnowledgeQueryManager()
        assert manager.workspace_id == "default"

    def test_explicit_workspace(self, engine):
        manager = KnowledgeQueryManager(workspace_id="ws-1")
        assert manager.workspace_id == "ws-1"

    def test_answer_query_default_workspace(self, engine):
        engine.query.return_value = _local_result()
        manager = KnowledgeQueryManager(workspace_id="ws-1")
        result = asyncio.run(manager.answer_query("q", user_id="u1"))
        assert result["answer"] == "Project Alpha is on track."
        assert engine.query.await_args[0][0] == "ws-1"

    def test_answer_query_explicit_workspace_override(self, engine):
        engine.query.return_value = _local_result()
        manager = KnowledgeQueryManager(workspace_id="ws-1")
        result = asyncio.run(manager.answer_query("q", user_id="u1", workspace_id="ws-2"))
        assert engine.query.await_args[0][0] == "ws-2"

    def test_answer_query_error_branch(self, engine):
        engine.query.return_value = {"error": "boom"}
        manager = KnowledgeQueryManager()
        result = asyncio.run(manager.answer_query("q"))
        assert result["answer"].startswith("I encountered an error")
        assert result["relevant_facts"] == []

    def test_factory(self, engine):
        manager = get_knowledge_query_manager(workspace_id="ws-3")
        assert isinstance(manager, KnowledgeQueryManager)
        assert manager.workspace_id == "ws-3"
