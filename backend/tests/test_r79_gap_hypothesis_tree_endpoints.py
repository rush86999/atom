# -*- coding: utf-8 -*-
"""
Round 79 — gap coverage: core/hypothesis_tree_endpoints.py (Arbor HTR REST API;
zero test references before this file).

Uses a standalone FastAPI app so ``get_db`` (in-memory SQLite) and
``get_current_user`` (SUPER_ADMIN) can be overridden.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.auto_dev.models import HypothesisTreeRecord


@pytest.fixture()
def db_session():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from core.database import Base

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine, tables=[HypothesisTreeRecord.__table__])
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


@pytest.fixture()
def client(db_session, monkeypatch):
    from core.auth import get_current_user
    from core.database import get_db
    from core.hypothesis_tree_endpoints import _TREE_REGISTRY, router

    _TREE_REGISTRY.clear()
    monkeypatch.setattr("core.hypothesis_tree_endpoints._TREE_REGISTRY", _TREE_REGISTRY)

    app = FastAPI()
    app.include_router(router)

    def override_db():
        yield db_session

    def override_user():
        return SimpleNamespace(id="user-1", role="super_admin", tenant_id="t1")

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    with TestClient(app) as c:
        yield c


CREATE_BODY = {
    "task_description": "Improve API latency",
    "tier": "solo",
    "task_type": "coding",
    "complexity_level": "standard",
}


class TestCreate:
    def test_create_coding_tree(self, client):
        r = client.post("/create", json=CREATE_BODY)
        assert r.status_code == 201
        body = r.json()
        assert body["tree_id"]
        assert body["tier"] == "solo"
        assert body["task_type"] == "coding"
        assert body["max_nodes"] > 0

    def test_create_optimization_tree(self, client):
        body = dict(CREATE_BODY, task_type="workflow")
        r = client.post("/create", json=body)
        assert r.status_code == 201
        assert r.json()["task_type"] == "workflow"

    def test_create_invalid_task_type_422(self, client):
        r = client.post("/create", json=dict(CREATE_BODY, task_type="bogus"))
        assert r.status_code == 422

    def test_create_negative_constraints_roundtrip(self, client):
        body = dict(CREATE_BODY, negative_constraints=["never use pandas"])
        r = client.post("/create", json=body)
        assert r.status_code == 201


class TestAddNode:
    def test_add_node_to_tree(self, client):
        tree_id = client.post("/create", json=CREATE_BODY).json()["tree_id"]
        r = client.post(
            f"/{tree_id}/add-node",
            json={"hypothesis": "add index on users.email", "promise_score": 0.8},
        )
        assert r.status_code == 200
        assert r.json()["added"] is True
        assert r.json()["node_id"]

    def test_add_child_node(self, client):
        tree_id = client.post("/create", json=CREATE_BODY).json()["tree_id"]
        parent = client.post(
            f"/{tree_id}/add-node", json={"hypothesis": "root idea"}
        ).json()["node_id"]
        child = client.post(
            f"/{tree_id}/add-node",
            json={"hypothesis": "child idea", "parent_id": parent},
        )
        assert child.json()["added"] is True
        assert child.json()["tree_stats"]["total_nodes"] == 2

    def test_add_node_with_metrics(self, client):
        tree_id = client.post("/create", json=CREATE_BODY).json()["tree_id"]
        r = client.post(
            f"/{tree_id}/add-node",
            json={
                "hypothesis": "h",
                "metrics": {"tokens_used": 100, "test_pass_rate": 0.9, "lint_errors": 1},
            },
        )
        assert r.json()["added"] is True

    def test_add_node_unknown_tree_404(self, client):
        r = client.post("/missing/add-node", json={"hypothesis": "h"})
        assert r.status_code == 404

    def test_add_node_bad_parent_404(self, client):
        tree_id = client.post("/create", json=CREATE_BODY).json()["tree_id"]
        r = client.post(
            f"/{tree_id}/add-node", json={"hypothesis": "h", "parent_id": "nope"}
        )
        assert r.status_code == 404

    def test_add_node_constraint_violation_rejected(self, client):
        tree_id = client.post(
            "/create",
            json=dict(CREATE_BODY, negative_constraints=["pandas"]),
        ).json()["tree_id"]
        r = client.post(f"/{tree_id}/add-node", json={"hypothesis": "use pandas everywhere"})
        assert r.status_code == 200
        assert r.json()["added"] is False
        assert "constraint" in r.json()["reason"]


class TestLifecycle:
    def test_succeed_persists_to_db(self, client):
        tree_id = client.post("/create", json=CREATE_BODY).json()["tree_id"]
        node_id = client.post(
            f"/{tree_id}/add-node", json={"hypothesis": "winning idea"}
        ).json()["node_id"]
        r = client.post(f"/{tree_id}/nodes/{node_id}/succeed?tenant_id=t1")
        assert r.status_code == 200
        body = r.json()
        assert body["node_id"] == node_id
        assert body["persisted"] is True
        assert node_id in body["winning_path"]

    def test_succeed_missing_node_404(self, client):
        tree_id = client.post("/create", json=CREATE_BODY).json()["tree_id"]
        r = client.post(f"/{tree_id}/nodes/nope/succeed")
        assert r.status_code == 404

    def test_prune_branch(self, client):
        tree_id = client.post("/create", json=CREATE_BODY).json()["tree_id"]
        node_id = client.post(
            f"/{tree_id}/add-node", json={"hypothesis": "bad idea"}
        ).json()["node_id"]
        r = client.post(f"/{tree_id}/nodes/{node_id}/prune", json={"reason": "test_failed"})
        assert r.status_code == 200
        assert r.json()["pruned_count"] == 1

    def test_prune_invalid_reason_422(self, client):
        tree_id = client.post("/create", json=CREATE_BODY).json()["tree_id"]
        node_id = client.post(
            f"/{tree_id}/add-node", json={"hypothesis": "h"}
        ).json()["node_id"]
        r = client.post(f"/{tree_id}/nodes/{node_id}/prune", json={"reason": "nope"})
        assert r.status_code == 422

    def test_prune_missing_node_404(self, client):
        tree_id = client.post("/create", json=CREATE_BODY).json()["tree_id"]
        r = client.post(f"/{tree_id}/nodes/nope/prune", json={"reason": "manual"})
        assert r.status_code == 404

    def test_add_constraint(self, client):
        tree_id = client.post("/create", json=CREATE_BODY).json()["tree_id"]
        r = client.post(f"/{tree_id}/constraints", json={"constraint": "avoid X"})
        assert r.status_code == 200
        assert r.json()["total_constraints"] == 1

    def test_statistics_shape(self, client):
        tree_id = client.post("/create", json=CREATE_BODY).json()["tree_id"]
        r = client.get(f"/{tree_id}/statistics")
        assert r.status_code == 200
        stats = r.json()
        for key in ("total_nodes", "successful_nodes", "pruned_nodes"):
            assert key in stats

    def test_get_tree_serialization(self, client):
        tree_id = client.post("/create", json=CREATE_BODY).json()["tree_id"]
        client.post(f"/{tree_id}/add-node", json={"hypothesis": "h"})
        r = client.get(f"/{tree_id}")
        assert r.status_code == 200
        assert r.json()["task_description"] == "Improve API latency"
        assert len(r.json()["nodes"]) == 1

    def test_delete_tree_204_then_404(self, client):
        tree_id = client.post("/create", json=CREATE_BODY).json()["tree_id"]
        r = client.delete(f"/{tree_id}?tenant_id=t1")
        assert r.status_code == 204
        assert client.get(f"/{tree_id}").status_code == 404


class TestSearch:
    def test_best_first_selects_highest_promise(self, client):
        tree_id = client.post("/create", json=CREATE_BODY).json()["tree_id"]
        client.post(f"/{tree_id}/add-node", json={"hypothesis": "a", "promise_score": 0.4})
        client.post(f"/{tree_id}/add-node", json={"hypothesis": "b", "promise_score": 0.9})
        r = client.post(f"/{tree_id}/search", json={"algorithm": "best_first"})
        assert r.status_code == 200
        assert r.json()["next_node"]["hypothesis"] == "b"
        assert r.json()["next_node"]["status"] == "expanding"

    def test_mcts_algorithm(self, client):
        tree_id = client.post("/create", json=CREATE_BODY).json()["tree_id"]
        client.post(f"/{tree_id}/add-node", json={"hypothesis": "a", "promise_score": 0.5})
        r = client.post(f"/{tree_id}/search", json={"algorithm": "mcts"})
        assert r.status_code == 200
        assert r.json()["next_node"] is not None

    def test_beam_search_algorithm(self, client):
        tree_id = client.post("/create", json=CREATE_BODY).json()["tree_id"]
        client.post(f"/{tree_id}/add-node", json={"hypothesis": "a", "promise_score": 0.6})
        r = client.post(f"/{tree_id}/search", json={"algorithm": "beam_search", "beam_width": 1})
        assert r.status_code == 200
        assert r.json()["next_node"] is not None

    def test_beam_width_zero_is_rejected(self, client):
        """RED: beam_width=0 -> sorted_candidates[:0] -> IndexError -> 500."""
        tree_id = client.post("/create", json=CREATE_BODY).json()["tree_id"]
        client.post(f"/{tree_id}/add-node", json={"hypothesis": "a", "promise_score": 0.6})
        r = client.post(f"/{tree_id}/search", json={"algorithm": "beam_search", "beam_width": 0})
        assert r.status_code == 422

    def test_unknown_algorithm_422(self, client):
        tree_id = client.post("/create", json=CREATE_BODY).json()["tree_id"]
        client.post(f"/{tree_id}/add-node", json={"hypothesis": "a", "promise_score": 0.6})
        r = client.post(f"/{tree_id}/search", json={"algorithm": "random"})
        assert r.status_code == 422

    def test_no_pending_nodes(self, client):
        tree_id = client.post("/create", json=CREATE_BODY).json()["tree_id"]
        r = client.post(f"/{tree_id}/search", json={"algorithm": "best_first"})
        assert r.status_code == 200
        assert r.json()["next_node"] is None


class TestHistory:
    def test_list_trees(self, client):
        client.post("/create", json=CREATE_BODY)
        r = client.get("/")
        assert r.status_code == 200
        assert r.json()["total"] == 1

    def test_list_history_empty_for_tenant(self, client):
        r = client.get("/history?tenant_id=nobody")
        assert r.status_code == 200
        assert r.json()["total"] == 0

    def test_list_history_after_persist(self, client):
        tree_id = client.post("/create", json=CREATE_BODY).json()["tree_id"]
        node_id = client.post(
            f"/{tree_id}/add-node", json={"hypothesis": "winner"}
        ).json()["node_id"]
        client.post(f"/{tree_id}/nodes/{node_id}/succeed?tenant_id=t1")
        r = client.get("/history?tenant_id=t1")
        assert r.json()["total"] == 1
        assert r.json()["trees"][0]["successful_nodes"] == 1

    def test_history_task_type_filter(self, client):
        tree_id = client.post("/create", json=CREATE_BODY).json()["tree_id"]
        node_id = client.post(
            f"/{tree_id}/add-node", json={"hypothesis": "winner"}
        ).json()["node_id"]
        client.post(f"/{tree_id}/nodes/{node_id}/succeed?tenant_id=t1")
        r = client.get("/history?tenant_id=t1&task_type=routing")
        assert r.json()["total"] == 0

    def test_get_tree_history_missing_404(self, client):
        r = client.get("/history/missing-tree")
        assert r.status_code == 404

    def test_get_tree_history_returns_snapshot(self, client):
        tree_id = client.post("/create", json=CREATE_BODY).json()["tree_id"]
        node_id = client.post(
            f"/{tree_id}/add-node", json={"hypothesis": "winner"}
        ).json()["node_id"]
        client.post(f"/{tree_id}/nodes/{node_id}/succeed?tenant_id=t1")
        r = client.get(f"/history/{tree_id}")
        assert r.status_code == 200
        assert r.json()["tree_snapshot"] is not None
        assert r.json()["winning_path"] == [node_id]
