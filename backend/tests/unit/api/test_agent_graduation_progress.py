"""
P3.1 regression tests — GET /api/agents/{id}/graduation-progress.

Verifies the endpoint returns the tier + next-tier threshold shape that the
AgentCard badge + dashboard progress bar consume.
"""
from unittest.mock import MagicMock

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture
def app_with_deps(monkeypatch):
    """Mount the agents router with permissions + db stubbed."""
    # Import after the pytest.importorskip so we skip cleanly if fastapi missing.
    from core import rbac_service as rbac  # noqa: F401  (ensures import works)
    from api import agent_routes as ar

    # Bypass RBAC for the test — every user is allowed every permission.
    monkeypatch.setattr(rbac.RBACService, "check_permission", lambda *a, **kw: True)

    fake_user = MagicMock()
    fake_user.id = "u-1"

    db = MagicMock()

    app = FastAPI()
    app.include_router(ar.router)
    app.dependency_overrides[ar.get_current_user] = lambda: fake_user
    app.dependency_overrides[ar.get_db] = lambda: db
    return app, db


def _make_agent(*, id="a-1", status="student"):
    a = MagicMock()
    a.id = id
    a.name = "Demo Assistant"
    a.status = status
    a.confidence_score = 0.5
    return a


def test_graduation_progress_returns_tier_and_threshold(app_with_deps):
    app, db = app_with_deps
    db.query.return_value.filter.return_value.first.return_value = _make_agent(status="student")

    client = TestClient(app)
    r = client.get("/api/agents/a-1/graduation-progress")
    assert r.status_code == 200, r.text
    body = r.json()
    data = body.get("data", body)

    assert data["agent_id"] == "a-1"
    assert data["current_tier"] == "student"
    # Student → next tier is intern, threshold = 10 episodes.
    assert data["next_tier"] == "intern"
    assert data["next_threshold_episodes"] == 10
    assert data["episodes_to_next"] == 10


def test_graduation_progress_404_for_missing_agent(app_with_deps):
    app, db = app_with_deps
    db.query.return_value.filter.return_value.first.return_value = None

    client = TestClient(app)
    r = client.get("/api/agents/does-not-exist/graduation-progress")
    assert r.status_code == 404


def test_graduation_progress_autonomous_has_no_next_tier(app_with_deps):
    app, db = app_with_deps
    db.query.return_value.filter.return_value.first.return_value = _make_agent(status="autonomous")

    client = TestClient(app)
    r = client.get("/api/agents/a-1/graduation-progress")
    assert r.status_code == 200
    body = r.json()
    data = body.get("data", body)
    assert data["current_tier"] == "autonomous"
    assert data["next_tier"] is None
    assert data["next_threshold_episodes"] is None


def test_graduation_progress_normalizes_unknown_status_to_student(app_with_deps):
    app, db = app_with_deps
    db.query.return_value.filter.return_value.first.return_value = _make_agent(status="bogus_tier")

    client = TestClient(app)
    r = client.get("/api/agents/a-1/graduation-progress")
    assert r.status_code == 200
    body = r.json()
    data = body.get("data", body)
    # Bogus tier falls back to student so the UI still renders something sane.
    assert data["current_tier"] == "student"
    assert data["next_tier"] == "intern"
