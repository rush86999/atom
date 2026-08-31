# -*- coding: utf-8 -*-
"""Coverage wave 77c — 8 API route modules (each >=95% standalone).

Targets:
- api/graphrag_routes.py       (GraphRAG ingestion/query/entities/relationships)
- api/feedback_enhanced.py     (submit / agent summary / analytics / trends)
- api/feedback_analytics.py    (dashboard / per-agent dashboard / trends)
- api/onboarding_routes.py     (update / status / probe-ollama)
- api/marketing_routes.py      (summary / lead scoring / reputation / GMB post)
- api/reasoning_routes.py      (reasoning chain / step feedback)
- api/risk_routes.py           (customer protection / early warning / fraud)
- api/project_health_routes.py (health check / templates)

No LLM, no network, no real DB: FastAPI TestClient + dependency_overrides +
service/mock patches on REAL module names (no `backend.` prefix).
"""
from __future__ import annotations

import contextlib
import importlib
import os
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import api.marketing_routes as marketing_mod
import api.onboarding_routes as onboarding_mod
import api.risk_routes as risk_mod
from core.auth import get_current_user
from core.database import get_db


# ============================================================================
# Shared helpers
# ============================================================================

def _app_with(router, user=None, db=None, prefix=""):
    """Build a hermetic app with optional auth/db overrides."""
    app = FastAPI()
    app.include_router(router, prefix=prefix)
    if user is not None:
        app.dependency_overrides[get_current_user] = lambda: user
    if db is not None:
        app.dependency_overrides[get_db] = lambda: db
    return app


class FakeUser:
    id = "u-token-1"
    tenant_id = "t-1"
    role = "member"
    status = "active"
    email = "user@test.com"
    onboarding_step = "welcome"
    onboarding_completed = False


def _auth_app(router, user=None, db=None, prefix="", raise_exc=False):
    app = _app_with(router, user=user or FakeUser(), db=db, prefix=prefix)
    return TestClient(app, raise_server_exceptions=raise_exc)


def _anon_client(router, prefix=""):
    return TestClient(_app_with(router, prefix=prefix))


@contextlib.contextmanager
def _yield_session(session):
    yield session


def _patch_db_session(mock_session):
    return patch("core.database.get_db_session", lambda: _yield_session(mock_session))


# ============================================================================
# api/graphrag_routes.py
# ============================================================================

class TestGraphRAGRoutes:
    """Coverage: api/graphrag_routes.py"""

    @pytest.fixture(autouse=True)
    def _engine(self):
        with patch("core.graphrag_engine.graphrag_engine") as eng:
            yield eng

    @pytest.fixture
    def client(self):
        from api.graphrag_routes import router
        return _auth_app(router)

    @staticmethod
    def _node(nid, name, type="org", description="d", properties=None):
        return SimpleNamespace(
            id=nid, name=name, type=type,
            description=description,
            properties=properties if properties is not None else {},
        )

    @staticmethod
    def _edge(eid, src, dst, rel_type="owns", properties=None):
        return SimpleNamespace(
            id=eid, source_node_id=src, target_node_id=dst,
            relationship_type=rel_type,
            properties=properties if properties is not None else {},
        )

    def test_all_endpoints_require_auth(self, _engine):
        from api.graphrag_routes import router
        client = _anon_client(router)
        checks = [
            (client.post, "/api/graphrag/ingest", {"json": {"doc_id": "d", "text": "t"}}),
            (client.get, "/api/graphrag/entities", {"params": {"workspace_id": "w"}}),
            (client.post, "/api/graphrag/entities", {"params": {"workspace_id": "w"}, "json": {"name": "n", "type": "org"}}),
            (client.get, "/api/graphrag/canonical-search", {"params": {"workspace_id": "w", "type": "org", "q": "x"}}),
            (client.get, "/api/graphrag/relationships", {"params": {"workspace_id": "w"}}),
            (client.post, "/api/graphrag/relationships", {"params": {"workspace_id": "w"}, "json": {"from_entity": "a", "to_entity": "b", "relationship_type": "r"}}),
            (client.post, "/api/graphrag/build-communities", {"params": {"user_id": "u"}}),
            (client.post, "/api/graphrag/query", {"json": {"query": "q"}}),
            (client.get, "/api/graphrag/entities/n1/neighbors", {"params": {"workspace_id": "w"}}),
            (client.get, "/api/graphrag/context", {"params": {"user_id": "u", "query": "q"}}),
            (client.get, "/api/graphrag/stats", {}),
        ]
        for call, url, kwargs in checks:
            assert call(url, **kwargs).status_code == 401

    def test_ingest_awaits_async_engine(self, client, _engine):
        _engine.ingest_document = AsyncMock(return_value=None)
        r = client.post("/api/graphrag/ingest", json={
            "doc_id": "d1", "text": "John works at Acme", "source": "api",
        })
        assert r.status_code == 200
        assert r.json()["success"] is True
        _engine.ingest_document.assert_awaited_once_with(
            workspace_id="default_user", doc_id="d1",
            text="John works at Acme", source="api",
        )

    def test_ingest_custom_user_id(self, client, _engine):
        _engine.ingest_document = AsyncMock(return_value=None)
        r = client.post("/api/graphrag/ingest", json={
            "doc_id": "d2", "text": "t", "user_id": "ws-custom",
        })
        assert r.status_code == 200
        _engine.ingest_document.assert_awaited_once()
        assert _engine.ingest_document.await_args.kwargs["workspace_id"] == "ws-custom"

    def test_ingest_missing_fields_422(self, client, _engine):
        assert client.post("/api/graphrag/ingest", json={"doc_id": "d"}).status_code == 422

    def test_list_entities_success(self, client, _engine):
        sess = MagicMock()
        sess.query.return_value.filter_by.return_value.limit.return_value.all.return_value = [
            self._node("n1", "Acme", type="organization", properties={"industry": "Tech"}),
            self._node("n2", "John"),
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
        _engine.add_entity.return_value = None
        r = client.post(
            "/api/graphrag/entities", params={"workspace_id": "ws1"},
            json={"name": "Acme", "type": "organization"},
        )
        assert r.status_code == 500
        assert r.json()["detail"]["error"]["code"] == "INGESTION_FAILED"

    def test_canonical_search_success(self, client, _engine):
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

    def test_list_relationships_maps_node_names(self, client, _engine):
        sess = MagicMock()
        sess.query.return_value.filter_by.return_value.limit.return_value.all.return_value = [
            self._edge("e1", "n1", "n2"),
        ]
        sess.query.return_value.filter.return_value.all.return_value = [
            self._node("n1", "Acme"), self._node("n2", "Box"),
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
            self._edge("e1", "n1", "n2"),
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

    @staticmethod
    def _add_rel_body(src="Acme", dst="Box"):
        return {
            "from_entity": src, "to_entity": dst,
            "relationship_type": "owns", "description": "d", "properties": {},
        }

    def test_add_relationship_success_by_name(self, client, _engine):
        sess = MagicMock()
        src, dst = self._node("n1", "Acme"), self._node("n2", "Box")
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
        src, dst = self._node("n1", "Acme"), self._node("n2", "Box")
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
        src, dst = self._node("n1", "Acme"), self._node("n2", "Box")
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
        src, dst = self._node("n1", "Acme"), self._node("n2", "Box")
        sess.query.return_value.filter_by.return_value.first.side_effect = [src, dst]
        _engine.add_relationship.return_value = None
        with _patch_db_session(sess):
            r = client.post(
                "/api/graphrag/relationships", params={"workspace_id": "ws1"},
                json=self._add_rel_body(),
            )
        assert r.status_code == 500
        assert r.json()["detail"]["error"]["code"] == "INGESTION_FAILED"

    def test_build_communities(self, client, _engine):
        _engine.build_communities.return_value = {"communities": 2}
        r = client.post("/api/graphrag/build-communities", params={"user_id": "u-1"})
        assert r.status_code == 200
        assert r.json()["data"]["user_id"] == "u-1"
        _engine.build_communities.assert_called_once_with("u-1")

    def test_query_awaits_async_engine(self, client, _engine):
        _engine.query = AsyncMock(return_value={"mode": "local", "answer": "ok"})
        r = client.post("/api/graphrag/query", json={
            "query": "who is john", "workspace_id": "ws1", "mode": "auto",
        })
        assert r.status_code == 200
        assert r.json()["data"]["answer"] == "ok"
        _engine.query.assert_awaited_once_with("ws1", "who is john", "auto")

    def test_query_missing_query_422(self, client, _engine):
        assert client.post("/api/graphrag/query", json={"workspace_id": "ws1"}).status_code == 422

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
        sess.query.return_value.filter_by.return_value.first.return_value = self._node("n1", "Acme")
        _engine.local_search.return_value = {"entities": []}
        with _patch_db_session(sess):
            r = client.get(
                "/api/graphrag/entities/n1/neighbors",
                params={"workspace_id": "ws1", "depth": 2},
            )
        assert r.status_code == 200
        assert r.json()["data"]["entities"] == []
        _engine.local_search.assert_called_once_with("ws1", "Acme", depth=2)

    def test_context_success(self, client, _engine):
        _engine.get_context_for_ai = AsyncMock(return_value="context text")
        r = client.get("/api/graphrag/context", params={"user_id": "ws1", "query": "hello"})
        assert r.status_code == 200
        assert r.json()["data"]["user_id"] == "ws1"
        assert r.json()["data"]["context"] == "context text"
        _engine.get_context_for_ai.assert_awaited_once_with(
            workspace_id="ws1", query="hello"
        )

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


# ============================================================================
# api/feedback_enhanced.py
# ============================================================================

class TestFeedbackEnhancedRoutes:
    """Coverage: api/feedback_enhanced.py — real in-memory SQLite."""

    @pytest.fixture
    def db(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy.pool import StaticPool
        from core.models_registration import Base

        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()
        yield session
        session.close()
        engine.dispose()

    @pytest.fixture
    def user(self, db):
        from core.models import User
        u = User(
            id="u-token-1", email="fb@test.com",
            first_name="Fb", last_name="T", role="member", status="active",
        )
        db.add(u)
        db.commit()
        return u

    @pytest.fixture
    def client(self, db, user):
        from api.feedback_enhanced import router
        app = FastAPI()
        app.include_router(router)

        def _get_db():
            yield db

        def _get_current_user():
            return user

        app.dependency_overrides[get_db] = _get_db
        app.dependency_overrides[get_current_user] = _get_current_user
        return TestClient(app)

    @pytest.fixture
    def anon_client(self):
        from api.feedback_enhanced import router
        return _anon_client(router)

    def _add_agent(self, db, name="TestAgent"):
        from core.models import AgentRegistry
        agent = AgentRegistry(
            name=name, status="autonomous", category="testing",
            role="agent", type="personal", capabilities=[],
            module_path="test.module", class_name="TestClass",
        )
        db.add(agent)
        db.commit()
        return agent

    def _add_feedback(self, db, agent_id, **kwargs):
        from core.models import AgentFeedback
        fb = AgentFeedback(
            agent_id=agent_id,
            user_id="u-token-1",
            input_context=kwargs.get("input_context"),
            original_output=kwargs.get("original_output", "out"),
            user_correction=kwargs.get("user_correction", ""),
            feedback_type=kwargs.get("feedback_type"),
            thumbs_up_down=kwargs.get("thumbs_up_down"),
            rating=kwargs.get("rating"),
            created_at=kwargs.get("created_at", datetime.now()),
        )
        db.add(fb)
        db.commit()
        return fb

    def test_all_endpoints_require_auth(self, anon_client):
        assert anon_client.post("/api/feedback/submit", json={
            "agent_id": "a", "user_id": "u", "thumbs_up_down": True,
        }).status_code == 401
        assert anon_client.get("/api/feedback/agent/a").status_code == 401
        assert anon_client.get("/api/feedback/analytics").status_code == 401
        assert anon_client.get("/api/feedback/trends").status_code == 401

    def test_submit_thumbs_up_approval(self, client, db, user):
        agent = self._add_agent(db)
        r = client.post("/api/feedback/submit", json={
            "agent_id": agent.id, "user_id": "spoofed-user", "thumbs_up_down": True,
        })
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["feedback_type"] == "approval"
        assert data["agent_id"] == agent.id
        from core.models import AgentFeedback
        row = db.query(AgentFeedback).filter(AgentFeedback.id == data["feedback_id"]).first()
        assert row.user_id == "u-token-1"  # token identity, never body user_id
        assert row.thumbs_up_down is True
        assert row.status == "pending"

    def test_submit_thumbs_down_comment(self, client, db):
        agent = self._add_agent(db)
        r = client.post("/api/feedback/submit", json={
            "agent_id": agent.id, "user_id": "u", "thumbs_up_down": False,
        })
        assert r.status_code == 200
        assert r.json()["data"]["feedback_type"] == "comment"

    def test_submit_rating_detects_type(self, client, db):
        agent = self._add_agent(db)
        r = client.post("/api/feedback/submit", json={
            "agent_id": agent.id, "user_id": "u", "rating": 4,
        })
        assert r.status_code == 200
        assert r.json()["data"]["feedback_type"] == "rating"

    def test_submit_correction_detects_type(self, client, db):
        agent = self._add_agent(db)
        r = client.post("/api/feedback/submit", json={
            "agent_id": agent.id, "user_id": "u", "user_correction": "should be X",
        })
        assert r.status_code == 200
        assert r.json()["data"]["feedback_type"] == "correction"

    def test_submit_explicit_feedback_type_passthrough(self, client, db):
        agent = self._add_agent(db)
        r = client.post("/api/feedback/submit", json={
            "agent_id": agent.id, "user_id": "u",
            "thumbs_up_down": True, "feedback_type": "custom-vote",
        })
        assert r.status_code == 200
        assert r.json()["data"]["feedback_type"] == "custom-vote"

    def test_submit_stores_execution_context(self, client, db):
        agent = self._add_agent(db)
        r = client.post("/api/feedback/submit", json={
            "agent_id": agent.id, "user_id": "u",
            "agent_execution_id": "exec-1",
            "input_context": "input text",
            "original_output": "output text",
            "rating": 5,
        })
        assert r.status_code == 200
        from core.models import AgentFeedback
        row = db.query(AgentFeedback).filter(AgentFeedback.id == r.json()["data"]["feedback_id"]).first()
        assert row.agent_execution_id == "exec-1"
        assert row.input_context == "input text"
        assert row.original_output == "output text"

    def test_submit_missing_agent_404(self, client):
        r = client.post("/api/feedback/submit", json={
            "agent_id": "ghost", "user_id": "u", "thumbs_up_down": True,
        })
        assert r.status_code == 404
        assert r.json()["detail"]["error"]["code"] == "NOT_FOUND"

    def test_submit_no_feedback_422(self, client, db):
        agent = self._add_agent(db)
        r = client.post("/api/feedback/submit", json={
            "agent_id": agent.id, "user_id": "u",
        })
        assert r.status_code == 422
        body = r.json()["detail"]["error"]
        assert body["code"] == "VALIDATION_ERROR"
        assert "At least one feedback type" in body["message"]

    def test_submit_rating_out_of_range_422(self, client, db):
        agent = self._add_agent(db)
        for bad in (0, 6):
            r = client.post("/api/feedback/submit", json={
                "agent_id": agent.id, "user_id": "u", "rating": bad,
            })
            assert r.status_code == 422

    def test_agent_feedback_missing_agent_404(self, client):
        r = client.get("/api/feedback/agent/ghost")
        assert r.status_code == 404

    def test_agent_feedback_summary_with_ratings(self, client, db):
        agent = self._add_agent(db, name="RatedAgent")
        for rating in (5, 4, 3, 2, 1):
            self._add_feedback(db, agent.id, rating=rating, feedback_type="rating")
        self._add_feedback(db, agent.id, thumbs_up_down=True, feedback_type="approval")
        self._add_feedback(db, agent.id, thumbs_up_down=False, feedback_type="comment")
        r = client.get(f"/api/feedback/agent/{agent.id}")
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["agent_name"] == "RatedAgent"
        assert data["total_feedback"] == 7
        assert data["rating_distribution"] == {"1": 1, "2": 1, "3": 1, "4": 1, "5": 1}
        assert data["average_rating"] == 3.0
        assert data["thumbs_up_count"] == 1
        assert data["thumbs_down_count"] == 1
        assert data["positive_count"] == 3  # ratings 5,4 + thumbs up
        assert data["negative_count"] == 3  # ratings 2,1 + thumbs down
        assert data["feedback_types"] == {"rating": 5, "approval": 1, "comment": 1}

    def test_agent_feedback_days_filter(self, client, db):
        agent = self._add_agent(db)
        self._add_feedback(db, agent.id, thumbs_up_down=True,
                           created_at=datetime.now() - timedelta(days=10))
        self._add_feedback(db, agent.id, thumbs_up_down=True,
                           created_at=datetime.now() - timedelta(days=45))
        r = client.get(f"/api/feedback/agent/{agent.id}", params={"days": 30})
        assert r.status_code == 200
        assert r.json()["data"]["total_feedback"] == 1

    def test_analytics_empty(self, client):
        r = client.get("/api/feedback/analytics")
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["total_feedback"] == 0
        assert data["total_agents_with_feedback"] == 0
        assert data["overall_positive_ratio"] == 0
        assert data["overall_average_rating"] is None
        assert data["top_performing_agents"] == []
        assert data["most_corrected_agents"] == []
        assert data["feedback_by_type"] == {}

    def test_analytics_full(self, client, db):
        a = self._add_agent(db, name="Agent A")
        b = self._add_agent(db, name="Agent B")
        self._add_feedback(db, a.id, thumbs_up_down=True, rating=5)
        self._add_feedback(db, a.id, thumbs_up_down=False, rating=2)
        self._add_feedback(db, b.id, rating=1, feedback_type="correction")
        self._add_feedback(db, "ghost", rating=3, feedback_type=None)
        self._add_feedback(db, "ghost2", thumbs_up_down=True, rating=1,
                           feedback_type="correction")
        r = client.get("/api/feedback/analytics", params={"days": 30, "limit": 5})
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["total_feedback"] == 5
        assert data["total_agents_with_feedback"] == 4
        assert data["overall_positive_ratio"] == 0.4  # 2 of 5
        assert data["overall_average_rating"] == 2.4  # (5+2+1+3+1)/5
        top = data["top_performing_agents"]
        assert [t["agent_id"] for t in top] == [a.id, b.id]  # ghosts not in registry
        assert top[0]["agent_name"] == "Agent A"
        assert top[0]["positive_ratio"] == 0.5
        corrected = data["most_corrected_agents"]
        assert corrected[0]["agent_id"] == b.id
        assert corrected[0]["correction_count"] == 1
        assert data["feedback_by_type"] == {"correction": 2}

    def test_trends_groups_by_date(self, client, db):
        agent = self._add_agent(db)
        now = datetime.now()
        self._add_feedback(db, agent.id, thumbs_up_down=True, rating=5, created_at=now)
        self._add_feedback(db, agent.id, thumbs_up_down=False, rating=1, created_at=now)
        self._add_feedback(db, agent.id, rating=3, created_at=now - timedelta(days=1))
        r = client.get("/api/feedback/trends", params={"days": 7})
        assert r.status_code == 200
        items = r.json()["data"]
        assert len(items) == 2
        today = items[-1]
        assert today["total"] == 2
        assert today["positive"] == 1
        assert today["negative"] == 1
        assert today["average_rating"] == 3.0
        yesterday = items[0]
        assert yesterday["total"] == 1
        assert yesterday["average_rating"] == 3.0
        assert yesterday["positive"] == 0

    def test_trends_empty(self, client):
        r = client.get("/api/feedback/trends")
        assert r.status_code == 200
        assert r.json()["data"] == []


# ============================================================================
# api/feedback_analytics.py
# ============================================================================

class TestFeedbackAnalyticsRoutes:
    """Coverage: api/feedback_analytics.py — service classes mocked."""

    @pytest.fixture
    def analytics_instance(self):
        inst = MagicMock()
        inst.get_feedback_statistics.return_value = {"total": 3, "positive_ratio": 0.5}
        inst.get_top_performing_agents.return_value = [{"agent_id": "a1"}]
        inst.get_most_corrected_agents.return_value = [{"agent_id": "b1"}]
        inst.get_feedback_breakdown_by_type.return_value = {"approval": 2}
        inst.get_feedback_trends.return_value = [{"date": "2026-08-13", "total": 3}]
        inst.get_agent_feedback_summary.return_value = {"total": 1}
        return inst

    @pytest.fixture
    def learning_instance(self):
        inst = MagicMock()
        inst.get_learning_signals.return_value = [{"signal": "x"}]
        return inst

    @contextlib.contextmanager
    def _client(self, analytics_instance, learning_instance, raise_exc=False):
        from api.feedback_analytics import router
        app = FastAPI()
        app.include_router(router, prefix="/api/feedback/analytics")
        app.dependency_overrides[get_current_user] = lambda: FakeUser()
        app.dependency_overrides[get_db] = lambda: MagicMock()
        with patch("api.feedback_analytics.FeedbackAnalytics", return_value=analytics_instance), \
                patch("core.agent_learning_enhanced.AgentLearningEnhanced", return_value=learning_instance):
            yield TestClient(app, raise_server_exceptions=raise_exc)

    def test_all_endpoints_require_auth(self):
        from api.feedback_analytics import router
        client = _anon_client(router, prefix="/api/feedback/analytics")
        assert client.get("/api/feedback/analytics/").status_code == 401
        assert client.get("/api/feedback/analytics/agent/a1").status_code == 401
        assert client.get("/api/feedback/analytics/trends").status_code == 401

    def test_dashboard_success(self, analytics_instance, learning_instance):
        with self._client(analytics_instance, learning_instance) as client:
            r = client.get("/api/feedback/analytics/")
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["period_days"] == 30
        assert data["summary"] == {"total": 3, "positive_ratio": 0.5}
        assert data["top_performing_agents"] == [{"agent_id": "a1"}]
        assert data["feedback_by_type"] == {"approval": 2}
        assert data["trends"] == [{"date": "2026-08-13", "total": 3}]

    def test_dashboard_custom_days_limit(self, analytics_instance, learning_instance):
        with self._client(analytics_instance, learning_instance) as client:
            r = client.get("/api/feedback/analytics/?days=7&limit=3")
        assert r.status_code == 200
        assert r.json()["data"]["period_days"] == 7
        analytics_instance.get_feedback_statistics.assert_called_once_with(days=7)
        analytics_instance.get_top_performing_agents.assert_called_once_with(days=7, limit=3)
        analytics_instance.get_most_corrected_agents.assert_called_once_with(days=7, limit=3)
        analytics_instance.get_feedback_breakdown_by_type.assert_called_once_with(days=7)
        analytics_instance.get_feedback_trends.assert_called_once_with(days=7)

    def test_dashboard_invalid_days_422(self, analytics_instance, learning_instance):
        with self._client(analytics_instance, learning_instance) as client:
            assert client.get("/api/feedback/analytics/?days=0").status_code == 422
            assert client.get("/api/feedback/analytics/?days=400").status_code == 422

    def test_dashboard_service_failure_500(self, learning_instance):
        inst = MagicMock()
        inst.get_feedback_statistics.side_effect = RuntimeError("boom")
        with self._client(inst, learning_instance, raise_exc=True) as client:
            r = client.get("/api/feedback/analytics/")
        assert r.status_code == 500
        assert "boom" not in r.text

    def test_agent_dashboard_success(self, analytics_instance, learning_instance):
        with self._client(analytics_instance, learning_instance) as client:
            r = client.get("/api/feedback/analytics/agent/ag-1")
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["agent_id"] == "ag-1"
        assert data["feedback_summary"] == {"total": 1}
        assert data["learning_signals"] == [{"signal": "x"}]
        analytics_instance.get_agent_feedback_summary.assert_called_once_with(
            agent_id="ag-1", days=30
        )
        learning_instance.get_learning_signals.assert_called_once_with(
            agent_id="ag-1", days=30
        )

    def test_agent_dashboard_service_failure_500(self, learning_instance):
        inst = MagicMock()
        inst.get_agent_feedback_summary.side_effect = RuntimeError("boom")
        with self._client(inst, learning_instance, raise_exc=True) as client:
            r = client.get("/api/feedback/analytics/agent/ag-1")
        assert r.status_code == 500
        assert "boom" not in r.text

    def test_trends_success(self, analytics_instance, learning_instance):
        with self._client(analytics_instance, learning_instance) as client:
            r = client.get("/api/feedback/analytics/trends", params={"days": 7})
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["period_days"] == 7
        assert data["trends"] == [{"date": "2026-08-13", "total": 3}]
        analytics_instance.get_feedback_trends.assert_called_once_with(days=7)

    def test_trends_service_failure_500(self, learning_instance):
        inst = MagicMock()
        inst.get_feedback_trends.side_effect = RuntimeError("boom")
        with self._client(inst, learning_instance, raise_exc=True) as client:
            r = client.get("/api/feedback/analytics/trends")
        assert r.status_code == 500
        assert "boom" not in r.text


# ============================================================================
# api/onboarding_routes.py
# ============================================================================

class TestOnboardingRoutes:
    """Coverage: api/onboarding_routes.py"""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def client(self, mock_db):
        app = FastAPI()
        app.include_router(onboarding_mod.router)
        app.dependency_overrides[get_current_user] = lambda: FakeUser()
        app.dependency_overrides[onboarding_mod.get_db] = lambda: mock_db
        return TestClient(app)

    def test_all_endpoints_require_auth(self):
        client = _anon_client(onboarding_mod.router)
        assert client.post("/api/onboarding/update", json={}).status_code == 401
        assert client.get("/api/onboarding/status").status_code == 401
        assert client.get("/api/onboarding/probe-ollama").status_code == 401

    def test_update_step(self, client, mock_db):
        r = client.post("/api/onboarding/update", json={"step": "models"})
        assert r.status_code == 200
        assert r.json()["data"]["onboarding_step"] == "models"
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()

    def test_update_completed(self, client):
        r = client.post("/api/onboarding/update", json={"completed": True})
        assert r.status_code == 200
        assert r.json()["data"]["onboarding_completed"] is True

    def test_update_both(self, client):
        r = client.post("/api/onboarding/update", json={"step": "done", "completed": True})
        assert r.status_code == 200
        assert r.json()["data"] == {"onboarding_step": "done", "onboarding_completed": True}

    def test_update_neither_commits(self, client, mock_db):
        r = client.post("/api/onboarding/update", json={})
        assert r.status_code == 200
        mock_db.commit.assert_called_once()

    def test_update_invalid_body_422(self, client):
        assert client.post("/api/onboarding/update", json={"step": 123}).status_code == 422

    def test_status(self, client):
        r = client.get("/api/onboarding/status")
        assert r.status_code == 200
        assert r.json()["data"]["onboarding_step"] == "welcome"
        assert r.json()["data"]["onboarding_completed"] is False

    def test_probe_reachable_default(self, client):
        with patch.object(onboarding_mod, "_probe_ollama", return_value=True) as p:
            r = client.get("/api/onboarding/probe-ollama")
        assert r.status_code == 200
        assert r.json()["data"]["reachable"] is True
        assert r.json()["data"]["host"] == "localhost"
        assert r.json()["data"]["port"] == 11434
        p.assert_called_once_with("localhost", 11434)

    def test_probe_unreachable(self, client):
        with patch.object(onboarding_mod, "_probe_ollama", return_value=False):
            r = client.get("/api/onboarding/probe-ollama")
        assert r.json()["data"]["reachable"] is False
        assert r.json()["message"] == "Ollama not detected"

    def test_probe_custom_host_port(self, client):
        with patch.dict(os.environ, {"OLLAMA_BASE_URL": "http://10.0.0.5:1234"}), \
                patch.object(onboarding_mod, "_probe_ollama", return_value=True) as p:
            r = client.get("/api/onboarding/probe-ollama")
        assert r.json()["data"]["host"] == "10.0.0.5"
        assert r.json()["data"]["port"] == 1234
        p.assert_called_once_with("10.0.0.5", 1234)

    def test_probe_http_default_port(self, client):
        with patch.dict(os.environ, {"OLLAMA_BASE_URL": "http://ollama.local"}), \
                patch.object(onboarding_mod, "_probe_ollama", return_value=True) as p:
            r = client.get("/api/onboarding/probe-ollama")
        assert r.json()["data"]["port"] == 80
        p.assert_called_once_with("ollama.local", 80)

    def test_probe_https_default_port(self, client):
        with patch.dict(os.environ, {"OLLAMA_BASE_URL": "https://ollama.local"}), \
                patch.object(onboarding_mod, "_probe_ollama", return_value=True) as p:
            r = client.get("/api/onboarding/probe-ollama")
        assert r.json()["data"]["port"] == 443
        p.assert_called_once_with("ollama.local", 443)

    def test_probe_unparseable_env_falls_back(self, client):
        with patch.dict(os.environ, {"OLLAMA_BASE_URL": "not a url://%%"}), \
                patch.object(onboarding_mod, "_probe_ollama", return_value=True) as p:
            r = client.get("/api/onboarding/probe-ollama")
        assert r.status_code == 200
        p.assert_called_once_with("localhost", 11434)

    def test_probe_urlparse_exception_tolerated(self, client):
        with patch.dict(os.environ, {"OLLAMA_BASE_URL": "http://evil:99"}), \
                patch("urllib.parse.urlparse", side_effect=ValueError("boom")), \
                patch.object(onboarding_mod, "_probe_ollama", return_value=True) as p:
            r = client.get("/api/onboarding/probe-ollama")
        assert r.status_code == 200
        assert r.json()["data"]["host"] == "localhost"
        p.assert_called_once_with("localhost", 11434)

    def test_probe_socket_success(self):
        with patch("api.onboarding_routes.socket.create_connection") as conn:
            assert onboarding_mod._probe_ollama("localhost", 11434) is True
        conn.assert_called_once_with(("localhost", 11434), timeout=1.5)

    def test_probe_socket_oserror(self):
        with patch(
            "api.onboarding_routes.socket.create_connection",
            side_effect=OSError("refused"),
        ):
            assert onboarding_mod._probe_ollama("localhost", 11434) is False


# ============================================================================
# api/marketing_routes.py
# ============================================================================

class TestMarketingRoutes:
    """Coverage: api/marketing_routes.py"""

    @pytest.fixture
    def mock_db(self):
        db = Mock()
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        db.commit = Mock()
        return db

    @pytest.fixture
    def client(self, mock_db):
        app = FastAPI()
        app.include_router(marketing_mod.router)
        app.dependency_overrides[get_current_user] = lambda: FakeUser()
        app.dependency_overrides[marketing_mod.get_db] = lambda: mock_db
        return TestClient(app, raise_server_exceptions=False)

    def test_all_endpoints_require_auth(self):
        client = _anon_client(marketing_mod.router)
        assert client.get("/api/marketing/dashboard/summary").status_code == 401
        assert client.post("/api/marketing/leads/l1/score").status_code == 401
        assert client.get("/api/marketing/reputation/analyze", params={"interaction": "x"}).status_code == 401
        assert client.get("/api/marketing/gmb/weekly-post/suggest", params={"business_name": "b", "location": "l"}).status_code == 401

    @staticmethod
    def _channel(name, leads=10, spend=100.0, conversions=3, cr=0.3):
        return {
            "channel_name": name, "leads": leads, "spend": spend,
            "conversions": conversions, "conversion_rate": cr,
        }

    @staticmethod
    def _lead(lid="lead-1", first="John", last="Doe", email="j@x.com", score=85.0, summary="s"):
        return SimpleNamespace(
            id=lid, first_name=first, last_name=last, email=email, source="website",
            ai_score=score, ai_qualification_summary=summary,
        )

    def test_summary_success_with_channels_and_leads(self, client, mock_db):
        leads = [self._lead()]
        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = leads
        with patch("marketing.intelligence_service.MarketingIntelligenceService") as Svc:
            Svc.return_value.get_channel_performance.return_value = [
                self._channel("google_ads", leads=50, conversions=10, cr=0.2),
                self._channel("facebook", leads=30, spend=300.0, conversions=5, cr=0.167),
            ]
            with patch.object(marketing_mod.reporter, "generate_narrative_report",
                              new=AsyncMock(return_value="narrative")) as rep:
                with patch.dict(os.environ, {"MOCK_MODE_ENABLED": "true"}):
                    r = client.get("/api/marketing/dashboard/summary")
        assert r.status_code == 200
        data = r.json()
        assert data["narrative_report"] == "narrative"
        assert data["performance_metrics"]["google_ads"]["leads"] == 50
        assert data["performance_metrics"]["facebook"]["cost"] == 300.0
        assert data["high_intent_leads"][0]["name"] == "John Doe"
        assert data["high_intent_leads"][0]["score"] == 85.0
        assert data["gmb_status"] == "mock"
        assert data["pending_reviews"] == 12
        assert data["data_source"] == "mock"
        rep.assert_awaited_once()

    def test_summary_lead_without_first_name_uses_email(self, client, mock_db):
        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [
            self._lead(first=None, email="anon@x.com"),
        ]
        with patch("marketing.intelligence_service.MarketingIntelligenceService") as Svc:
            Svc.return_value.get_channel_performance.return_value = [self._channel("google_ads")]
            with patch.object(marketing_mod.reporter, "generate_narrative_report",
                              new=AsyncMock(return_value="n")):
                with patch.dict(os.environ, {}):
                    r = client.get("/api/marketing/dashboard/summary")
        assert r.status_code == 200
        assert r.json()["high_intent_leads"][0]["name"] == "anon@x.com"

    def test_summary_no_channels_falls_back_to_no_data(self, client, mock_db):
        with patch("marketing.intelligence_service.MarketingIntelligenceService") as Svc:
            Svc.return_value.get_channel_performance.return_value = []
            with patch.object(marketing_mod.reporter, "generate_narrative_report",
                              new=AsyncMock(return_value="n")):
                with patch.dict(os.environ, {}):
                    r = client.get("/api/marketing/dashboard/summary")
        assert r.status_code == 200
        assert r.json()["performance_metrics"] == {"no_data": {"leads": 0, "cost": 0, "conversions": 0}}

    def test_summary_gmb_configured_active(self, client, mock_db):
        with patch("marketing.intelligence_service.MarketingIntelligenceService") as Svc:
            Svc.return_value.get_channel_performance.return_value = []
            with patch.object(marketing_mod.reporter, "generate_narrative_report",
                              new=AsyncMock(return_value="n")):
                with patch.dict(os.environ, {"GOOGLE_BUSINESS_API_KEY": "key", "MOCK_MODE_ENABLED": "false"}):
                    r = client.get("/api/marketing/dashboard/summary")
        assert r.status_code == 200
        assert r.json()["gmb_status"] == "active"
        assert r.json()["pending_reviews"] is None
        assert r.json()["data_source"] == "live"

    def test_summary_gmb_not_configured(self, client, mock_db):
        with patch("marketing.intelligence_service.MarketingIntelligenceService") as Svc:
            Svc.return_value.get_channel_performance.return_value = []
            with patch.object(marketing_mod.reporter, "generate_narrative_report",
                              new=AsyncMock(return_value="n")):
                with patch.dict(os.environ, {}):
                    r = client.get("/api/marketing/dashboard/summary")
        assert r.status_code == 200
        assert r.json()["gmb_status"] == "not_configured"
        assert r.json()["pending_reviews"] == "integration_required"
        assert r.json()["data_source"] == "live"

    def test_summary_service_error_500(self, client, mock_db):
        with patch("marketing.intelligence_service.MarketingIntelligenceService",
                   side_effect=RuntimeError("boom")):
            r = client.get("/api/marketing/dashboard/summary")
        assert r.status_code == 500
        assert "boom" not in r.text

    def test_score_lead_success(self, client, mock_db):
        lead = self._lead()
        mock_db.query.return_value.filter.return_value.first.return_value = lead
        with patch.object(marketing_mod.marketing_manager.lead_scoring, "calculate_score",
                          new=AsyncMock(return_value={"score": 88, "rationale": "good lead"})) as calc:
            r = client.post("/api/marketing/leads/lead-1/score")
        assert r.status_code == 200
        assert r.json() == {"score": 88, "rationale": "good lead"}
        assert lead.ai_score == 88.0
        assert lead.ai_qualification_summary == "good lead"
        calc.assert_awaited_once_with({"email": "j@x.com", "name": "John"}, ["Lead source: website"])

    def test_score_lead_not_found_404(self, client, mock_db):
        mock_db.query.return_value.filter.return_value.first.return_value = None
        r = client.post("/api/marketing/leads/ghost/score")
        assert r.status_code == 404
        assert r.json()["detail"]["error"]["code"] == "NOT_FOUND"

    def test_analyze_reputation(self, client):
        with patch.object(marketing_mod.reputation_manager, "determine_feedback_strategy",
                          new=AsyncMock(return_value={"strategy": "private"})) as strat:
            r = client.get("/api/marketing/reputation/analyze", params={"interaction": "rude customer"})
        assert r.status_code == 200
        assert r.json() == {"strategy": "private"}
        strat.assert_awaited_once_with("rude customer")

    def test_suggest_gmb_post_with_events(self, client):
        with patch.object(marketing_mod.marketing_manager.gmb, "generate_weekly_update",
                          new=AsyncMock(return_value="post text")) as gen:
            r = client.get(
                "/api/marketing/gmb/weekly-post/suggest",
                params={"business_name": "Acme", "location": "NY", "events": ["Sale"]},
            )
        assert r.status_code == 200
        assert r.json() == {"suggested_post": "post text"}
        gen.assert_awaited_once_with({"name": "Acme", "location": "NY"}, ["Sale"])

    def test_suggest_gmb_post_default_events(self, client):
        with patch.object(marketing_mod.marketing_manager.gmb, "generate_weekly_update",
                          new=AsyncMock(return_value="post text")) as gen:
            r = client.get(
                "/api/marketing/gmb/weekly-post/suggest",
                params={"business_name": "Acme", "location": "NY"},
            )
        assert r.status_code == 200
        assert r.json() == {"suggested_post": "post text"}
        gen.assert_awaited_once_with(
            {"name": "Acme", "location": "NY"}, ["Open for business", "New services available"]
        )

    def test_stub_ai_enhanced_service_generate_insights(self):
        """Line 26: the module falls back to StubAIEnhancedService (no
        integrations.ai_enhanced_service in this repo); exercise it."""
        import asyncio
        result = asyncio.run(marketing_mod.ai_enhanced_service.generate_insights())
        assert result == {"status": "stub", "message": "AI Enhanced service not available"}


# ============================================================================
# api/reasoning_routes.py
# ============================================================================

class TestReasoningRoutes:
    """Coverage: api/reasoning_routes.py"""

    @pytest.fixture
    def client(self):
        from api.reasoning_routes import router
        db = MagicMock()
        # The /feedback idempotency guard queries AgentFeedback.first() —
        # a truthy MagicMock reads as "duplicate" and short-circuits every
        # submission before governance is ever called.
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
        return _auth_app(router, db=db, raise_exc=True)

    def test_all_endpoints_require_auth(self):
        from api.reasoning_routes import router
        client = _anon_client(router)
        assert client.get("/api/reasoning/chain/c1").status_code == 401
        assert client.post("/api/reasoning/feedback", json={
            "agent_id": "a", "run_id": "r", "step_index": 0,
            "step_content": {"thought": "t"}, "feedback_type": "thumbs_up",
        }).status_code == 401

    def test_get_chain_success_with_dict_method(self, client):
        from api.reasoning_routes import router
        chain = SimpleNamespace(
            id="c1", dict=lambda: {"id": "c1", "steps": []},
        )
        tracker = Mock()
        tracker.get_chain.return_value = chain
        with patch("core.reasoning_chain.get_reasoning_tracker", return_value=tracker):
            r = client.get("/api/reasoning/chain/c1")
        assert r.status_code == 200
        assert r.json()["data"] == {"id": "c1", "steps": []}
        tracker.get_chain.assert_called_once_with("c1")

    def test_get_chain_success_with_dunder_dict(self, client):
        chain = SimpleNamespace(id="c2", steps=[1])
        tracker = Mock()
        tracker.get_chain.return_value = chain
        with patch("core.reasoning_chain.get_reasoning_tracker", return_value=tracker):
            r = client.get("/api/reasoning/chain/c2")
        assert r.status_code == 200
        assert r.json()["data"] == {"id": "c2", "steps": [1]}

    def test_get_chain_not_found_404(self, client):
        tracker = Mock()
        tracker.get_chain.return_value = None
        with patch("core.reasoning_chain.get_reasoning_tracker", return_value=tracker):
            r = client.get("/api/reasoning/chain/ghost")
        assert r.status_code == 404
        assert r.json()["detail"]["error"]["code"] == "NOT_FOUND"

    def test_submit_step_feedback_success(self, client):
        from api.reasoning_routes import AgentGovernanceService
        svc = MagicMock()
        svc.submit_feedback = AsyncMock(return_value=SimpleNamespace(id="fb-1"))
        with patch("api.reasoning_routes.AgentGovernanceService", return_value=svc):
            r = client.post("/api/reasoning/feedback", json={
                "agent_id": "ag-1", "run_id": "run-1", "step_index": 2,
                "step_content": {"thought": "think about X"},
                "feedback_type": "thumbs_down", "comment": "wrong step",
            })
        assert r.status_code == 200
        assert r.json()["data"] == {"id": "fb-1"}
        call_kwargs = svc.submit_feedback.await_args.kwargs
        assert call_kwargs["agent_id"] == "ag-1"
        assert call_kwargs["user_id"] == "u-token-1"
        assert call_kwargs["original_output"] == '"think about X"'
        assert call_kwargs["user_correction"] == "wrong step"

    def test_submit_step_feedback_comment_fallback(self, client):
        from api.reasoning_routes import AgentGovernanceService
        svc = MagicMock()
        svc.submit_feedback = AsyncMock(return_value=SimpleNamespace(id="fb-2"))
        with patch("api.reasoning_routes.AgentGovernanceService", return_value=svc):
            r = client.post("/api/reasoning/feedback", json={
                "agent_id": "ag-1", "run_id": "run-1", "step_index": 0,
                "step_content": {"thought": "t"}, "feedback_type": "thumbs_up",
            })
        assert r.status_code == 200
        assert svc.submit_feedback.await_args.kwargs["user_correction"] == "thumbs_up"
        assert "run-1" in svc.submit_feedback.await_args.kwargs["input_context"]

    def test_submit_step_feedback_missing_thought(self, client):
        from api.reasoning_routes import AgentGovernanceService
        svc = MagicMock()
        svc.submit_feedback = AsyncMock(return_value=SimpleNamespace(id="fb-3"))
        with patch("api.reasoning_routes.AgentGovernanceService", return_value=svc):
            r = client.post("/api/reasoning/feedback", json={
                "agent_id": "ag-1", "run_id": "run-1", "step_index": 0,
                "step_content": {"action": "act"}, "feedback_type": "thumbs_up",
            })
        assert r.status_code == 200
        assert svc.submit_feedback.await_args.kwargs["original_output"] == '""'

    def test_submit_step_feedback_governance_failure_500(self, client):
        from api.reasoning_routes import AgentGovernanceService
        svc = MagicMock()
        svc.submit_feedback = AsyncMock(side_effect=RuntimeError("boom"))
        with patch("api.reasoning_routes.AgentGovernanceService", return_value=svc):
            r = client.post("/api/reasoning/feedback", json={
                "agent_id": "ag-1", "run_id": "run-1", "step_index": 0,
                "step_content": {"thought": "t"}, "feedback_type": "thumbs_up",
            })
        assert r.status_code == 500
        assert "boom" not in r.text


# ============================================================================
# api/risk_routes.py
# ============================================================================

class TestRiskRoutes:
    """Coverage: api/risk_routes.py — both mock and live modes."""

    @pytest.fixture
    def client(self):
        app = FastAPI()
        app.include_router(risk_mod.router)
        app.dependency_overrides[get_current_user] = lambda: FakeUser()
        return TestClient(app, raise_server_exceptions=False)

    @pytest.fixture
    def anon_client(self):
        app = FastAPI()
        app.include_router(risk_mod.router)
        return TestClient(app)

    @pytest.fixture
    def mock_mode_client(self):
        with patch.dict(os.environ, {"FINANCIAL_FORENSICS_MOCK": "true"}):
            importlib.reload(risk_mod)
        try:
            app = FastAPI()
            app.include_router(risk_mod.router)
            app.dependency_overrides[get_current_user] = lambda: FakeUser()
            yield TestClient(app, raise_server_exceptions=False)
        finally:
            with patch.dict(os.environ, {"FINANCIAL_FORENSICS_MOCK": "false"}):
                importlib.reload(risk_mod)

    def test_all_endpoints_require_auth(self, anon_client):
        assert anon_client.get("/api/risk/customer-protection").status_code == 401
        assert anon_client.get("/api/risk/early-warning").status_code == 401
        assert anon_client.get("/api/risk/fraud").status_code == 401

    def test_customer_protection_mock(self, mock_mode_client):
        r = mock_mode_client.get("/api/risk/customer-protection")
        assert r.status_code == 200
        data = r.json()
        assert data["is_mock"] is True
        assert len(data["churn_risk"]) == 2
        assert data["churn_risk"][0]["risk_level"] == "HIGH"
        assert data["vip_opportunities"][1]["ai_score"] == 89

    def test_early_warning_mock(self, mock_mode_client):
        r = mock_mode_client.get("/api/risk/early-warning")
        assert r.status_code == 200
        data = r.json()
        assert data["is_mock"] is True
        assert data["ar_alerts"][0]["days_overdue"] == 52

    def test_fraud_mock(self, mock_mode_client):
        r = mock_mode_client.get("/api/risk/fraud")
        assert r.status_code == 200
        assert r.json()["anomalies"][0]["type"] == "LARGE_OUTFLOW"

    def test_customer_protection_live(self, client):
        svc = AsyncMock()
        svc.predict_churn_risk.return_value = [{"deal_id": "d1", "risk_level": "MEDIUM"}]
        with patch.object(risk_mod, "CustomerProtectionService", return_value=svc):
            r = client.get("/api/risk/customer-protection")
        assert r.status_code == 200
        data = r.json()
        assert data["is_mock"] is False
        assert data["churn_risk"] == [{"deal_id": "d1", "risk_level": "MEDIUM"}]
        assert data["vip_opportunities"] == []
        svc.predict_churn_risk.assert_awaited_once_with("default")

    def test_customer_protection_live_service_failure(self, client):
        svc = AsyncMock()
        svc.predict_churn_risk.side_effect = RuntimeError("boom")
        with patch.object(risk_mod, "CustomerProtectionService", return_value=svc):
            r = client.get("/api/risk/customer-protection")
        assert r.status_code == 500
        assert "boom" not in r.text

    def test_early_warning_live(self, client):
        svc = AsyncMock()
        svc.detect_ar_delays.return_value = [{"id": "inv-1", "amount": 500}]
        with patch.object(risk_mod, "EarlyWarningService", return_value=svc):
            r = client.get("/api/risk/early-warning")
        assert r.status_code == 200
        assert r.json()["ar_alerts"] == [{"id": "inv-1", "amount": 500}]
        svc.detect_ar_delays.assert_awaited_once_with("default")

    def test_early_warning_live_service_failure(self, client):
        svc = AsyncMock()
        svc.detect_ar_delays.side_effect = RuntimeError("boom")
        with patch.object(risk_mod, "EarlyWarningService", return_value=svc):
            r = client.get("/api/risk/early-warning")
        assert r.status_code == 500

    def test_fraud_live(self, client):
        svc = AsyncMock()
        svc.detect_anomalies.return_value = [{"id": "tx-1", "severity": "HIGH"}]
        with patch.object(risk_mod, "FraudDetectionService", return_value=svc):
            r = client.get("/api/risk/fraud")
        assert r.status_code == 200
        assert r.json()["anomalies"] == [{"id": "tx-1", "severity": "HIGH"}]
        svc.detect_anomalies.assert_awaited_once_with("default")

    def test_fraud_live_service_failure(self, client):
        svc = AsyncMock()
        svc.detect_anomalies.side_effect = RuntimeError("boom")
        with patch.object(risk_mod, "FraudDetectionService", return_value=svc):
            r = client.get("/api/risk/fraud")
        assert r.status_code == 500


# ============================================================================
# api/project_health_routes.py
# ============================================================================

class TestProjectHealthRoutes:
    """Coverage: api/project_health_routes.py"""

    @pytest.fixture
    def client(self):
        from api.project_health_routes import router
        from core.security_dependencies import get_current_user as ph_user
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[ph_user] = lambda: SimpleNamespace(id="u1")
        app.dependency_overrides[get_db] = lambda: SimpleNamespace()
        return TestClient(app, raise_server_exceptions=False)

    @pytest.fixture
    def anon_client(self):
        from api.project_health_routes import router
        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    FULL_PAYLOAD = {
        "notion_api_key": "k",
        "notion_database_id": "db",
        "github_owner": "owner",
        "github_repo": "repo",
        "slack_channel_id": "chan",
        "time_range_days": 7,
    }

    def test_all_endpoints_require_auth(self, anon_client):
        assert anon_client.post("/api/v1/projects/health", json={}).status_code == 401
        # /health/templates carries no auth dependency (public list) -> 200 anon
        assert anon_client.get("/api/v1/projects/health/templates").status_code == 200

    def test_full_payload_all_metrics(self, client):
        r = client.post("/api/v1/projects/health", json=self.FULL_PAYLOAD)
        assert r.status_code == 200
        data = r.json()
        assert set(data["metrics"]) == {"notion", "github", "slack", "meetings"}
        assert data["metrics"]["notion"]["name"] == "Task Management"
        assert data["metrics"]["github"]["name"] == "Code Health"
        assert data["metrics"]["slack"]["name"] == "Communication"
        assert data["metrics"]["meetings"]["name"] == "Meeting Balance"
        assert data["time_range_days"] == 7
        assert len(data["check_id"]) == 36
        assert "checked_at" in data
        assert data["recommendations"]

    def test_notion_only(self, client):
        r = client.post("/api/v1/projects/health", json={
            "notion_api_key": "k", "notion_database_id": "db"})
        assert r.status_code == 200
        assert set(r.json()["metrics"]) == {"notion", "meetings"}

    def test_github_only(self, client):
        r = client.post("/api/v1/projects/health", json={
            "github_owner": "o", "github_repo": "r"})
        assert r.status_code == 200
        assert set(r.json()["metrics"]) == {"github", "meetings"}

    def test_slack_only(self, client):
        r = client.post("/api/v1/projects/health", json={"slack_channel_id": "c"})
        assert r.status_code == 200
        assert set(r.json()["metrics"]) == {"slack", "meetings"}

    def test_no_credentials_meetings_only(self, client):
        r = client.post("/api/v1/projects/health", json={})
        assert r.status_code == 200
        assert set(r.json()["metrics"]) == {"meetings"}

    def test_notion_calculation_failure_skipped(self, client):
        with patch("api.project_health_routes.calculate_notion_health",
                   new=AsyncMock(side_effect=RuntimeError("boom"))):
            r = client.post("/api/v1/projects/health", json=self.FULL_PAYLOAD)
        assert r.status_code == 200
        assert "notion" not in r.json()["metrics"]

    def test_github_calculation_failure_skipped(self, client):
        with patch("api.project_health_routes.calculate_github_health",
                   new=AsyncMock(side_effect=RuntimeError("boom"))):
            r = client.post("/api/v1/projects/health", json=self.FULL_PAYLOAD)
        assert r.status_code == 200
        assert "github" not in r.json()["metrics"]

    def test_slack_calculation_failure_skipped(self, client):
        with patch("api.project_health_routes.calculate_slack_health",
                   new=AsyncMock(side_effect=RuntimeError("boom"))):
            r = client.post("/api/v1/projects/health", json=self.FULL_PAYLOAD)
        assert r.status_code == 200
        assert "slack" not in r.json()["metrics"]

    def test_meeting_calculation_failure_skipped(self, client):
        with patch("api.project_health_routes.calculate_meeting_health",
                   new=AsyncMock(side_effect=RuntimeError("boom"))):
            r = client.post("/api/v1/projects/health", json=self.FULL_PAYLOAD)
        assert r.status_code == 200
        assert "meetings" not in r.json()["metrics"]

    def test_all_calculations_fail_returns_400(self, client):
        patchers = [
            patch("api.project_health_routes.calculate_notion_health",
                  new=AsyncMock(side_effect=RuntimeError("n"))),
            patch("api.project_health_routes.calculate_github_health",
                  new=AsyncMock(side_effect=RuntimeError("g"))),
            patch("api.project_health_routes.calculate_slack_health",
                  new=AsyncMock(side_effect=RuntimeError("s"))),
            patch("api.project_health_routes.calculate_meeting_health",
                  new=AsyncMock(side_effect=RuntimeError("m"))),
        ]
        for p in patchers:
            p.start()
        try:
            r = client.post("/api/v1/projects/health", json=self.FULL_PAYLOAD)
        finally:
            for p in patchers:
                p.stop()
        assert r.status_code == 400

    def test_time_range_validation_422(self, client):
        r = client.post("/api/v1/projects/health", json={
            "notion_api_key": "k", "notion_database_id": "db",
            "time_range_days": 0})
        assert r.status_code == 422

    def test_unexpected_error_returns_500(self, client):
        with patch("api.project_health_routes.calculate_overall_score",
                   side_effect=RuntimeError("boom")):
            r = client.post("/api/v1/projects/health", json=self.FULL_PAYLOAD)
        assert r.status_code == 500
        assert r.json()["detail"] == "Internal error"

    def test_list_templates(self, client):
        r = client.get("/api/v1/projects/health/templates")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 4
        assert set(data["templates"]) == {
            "software_development", "product_team", "research", "startup"}
        assert data["templates"]["software_development"]["metrics"] == [
            "notion", "github", "slack", "meetings"]

    def test_recommendation_each_name_warning(self):
        from api.project_health_routes import HealthMetric, generate_overall_recommendations

        def metric(name, status):
            return HealthMetric(
                name=name, score=50, max_score=100, status=status,
                details={}, trend="stable",
            )

        recs = generate_overall_recommendations({
            "a": metric("Task Management", status="warning"),
            "b": metric("Code Health", status="warning"),
            "c": metric("Communication", status="warning"),
            "d": metric("Meeting Balance", status="critical"),
        })
        joined = " ".join(recs)
        assert "overdue tasks" in joined
        assert "open PRs" in joined
        assert "response times" in joined
        assert "meeting load" in joined

    def test_recommendation_good_fallback(self):
        from api.project_health_routes import HealthMetric, generate_overall_recommendations
        recs = generate_overall_recommendations({
            "a": HealthMetric(
                name="Task Management", score=90, max_score=100, status="good",
                details={}, trend="stable"),
        })
        assert recs == ["Project health is good! Maintain current practices."]

    def test_overall_score_empty_unknown(self):
        from api.project_health_routes import calculate_overall_score
        score, status = calculate_overall_score({})
        assert score == 0.0 and status == "unknown"

    def test_overall_score_statuses(self):
        from api.project_health_routes import HealthMetric, calculate_overall_score

        def metric(score, max_score=100):
            return HealthMetric(
                name="x", score=score, max_score=max_score, status="good",
                details={}, trend="stable")

        assert calculate_overall_score({"a": metric(90)})[1] == "excellent"
        assert calculate_overall_score({"a": metric(70)})[1] == "good"
        assert calculate_overall_score({"a": metric(50)})[1] == "warning"
        assert calculate_overall_score({"a": metric(30)})[1] == "critical"
        assert calculate_overall_score({"a": metric(80)})[0] == 80.0
