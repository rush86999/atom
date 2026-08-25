"""R82 trajectory-feed endpoint — GET /api/episodes/trajectories.

The memory-recall UI (components/Agents/MemoryRecallFeed.tsx) fetched
/api/governance/analytics/trajectories which NO backend route served — the
feed was dead (always empty, console error). This endpoint is the real,
episodic-memory-backed surface for that UI.
"""
from unittest.mock import MagicMock

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture
def app_with_deps(monkeypatch):
    from api import episode_routes as er

    fake_user = MagicMock()
    fake_user.id = "u-1"

    db = MagicMock()

    app = FastAPI()
    app.include_router(er.router)
    app.dependency_overrides[er.get_current_user] = lambda: fake_user
    app.dependency_overrides[er.get_db] = lambda: db
    return app, db


def _make_episode(*, id="e-1", agent_id="a-1", outcome="success", task="Build report"):
    ep = MagicMock()
    ep.id = id
    ep.agent_id = agent_id
    ep.task_description = task
    ep.outcome = outcome
    ep.success = outcome == "success"
    ep.step_efficiency = 0.93 if outcome == "success" else 0.41
    ep.confidence_score = 0.8
    ep.metadata_json = {"learnings": ["do X first"]}
    ep.started_at = MagicMock()
    ep.started_at.isoformat.return_value = "2026-01-01T10:00:00+00:00"
    return ep


def test_trajectories_lists_episodes_mapped(app_with_deps):
    app, db = app_with_deps
    db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [
        _make_episode(),
    ]

    client = TestClient(app)
    r = client.get("/api/episodes/trajectories?agent_id=a-1")
    assert r.status_code == 200, r.text
    data = r.json().get("data") if isinstance(r.json(), dict) else r.json()
    traj = data[0]
    assert traj["id"] == "e-1"
    assert traj["agent_id"] == "a-1"
    assert traj["outcome"] == "success"
    assert traj["summary"] == "Build report"
    assert traj["learnings"] == ["do X first"]
    assert traj["timestamp"] == "2026-01-01T10:00:00+00:00"


def test_trajectories_requires_auth(app_with_deps):
    from api.episode_routes import router, get_current_user
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()
    app.include_router(router)

    # No user override: real get_current_user runs → 401 without a token.
    client = TestClient(app)
    r = client.get("/api/episodes/trajectories")
    assert r.status_code == 401
