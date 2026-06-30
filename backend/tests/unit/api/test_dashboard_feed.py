"""
P3.2 regression tests — GET /api/dashboard/feed aggregate endpoint.

Verifies the endpoint returns the four sections the landing page expects and
fails open (returns empty lists / null) when the underlying tables are empty
or raise.
"""
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture
def app_with_deps():
    from api import dashboard_routes as dr

    fake_user = MagicMock()
    fake_user.id = "u-1"
    fake_user.workspace_id = "default"

    db = MagicMock()
    app = FastAPI()
    app.include_router(dr.router)
    app.dependency_overrides[dr.get_current_user] = lambda: fake_user
    app.dependency_overrides[dr.get_db] = lambda: db
    return app, db


def test_feed_returns_all_four_sections_even_when_empty(app_with_deps):
    """An empty workspace should still get all 4 keys, just with empty values."""
    app, db = app_with_deps
    # Every chained query returns nothing.
    chain = MagicMock()
    chain.filter.return_value = chain
    chain.outerjoin.return_value = chain
    chain.order_by.return_value = chain
    chain.limit.return_value = chain
    chain.all.return_value = []
    chain.first.return_value = None
    db.query.return_value = chain

    client = TestClient(app)
    r = client.get("/api/dashboard/feed")
    assert r.status_code == 200, r.text
    data = r.json().get("data", {})
    assert set(data.keys()) == {"recent_executions", "recent_canvases", "last_chat_session", "agents_progress"}
    assert data["recent_executions"] == []
    assert data["recent_canvases"] == []
    assert data["last_chat_session"] is None
    assert data["agents_progress"] == []


def test_feed_includes_recent_execution_with_agent_name(app_with_deps):
    app, db = app_with_deps
    exec_row = MagicMock()
    exec_row.id = "ex-1"
    exec_row.agent_id = "a-1"
    exec_row.status = "completed"
    exec_row.input_summary = "Summarize X"
    exec_row.started_at = datetime.now(timezone.utc)
    exec_row.duration_seconds = 1.5

    chain = MagicMock()
    chain.outerjoin.return_value = chain
    chain.filter.return_value = chain
    chain.order_by.return_value = chain
    chain.limit.return_value = chain
    chain.all.return_value = [(exec_row, "Demo Assistant")]
    chain.first.return_value = None
    db.query.return_value = chain

    client = TestClient(app)
    r = client.get("/api/dashboard/feed")
    assert r.status_code == 200
    data = r.json()["data"]
    assert len(data["recent_executions"]) == 1
    ex = data["recent_executions"][0]
    assert ex["agent_name"] == "Demo Assistant"
    assert ex["status"] == "completed"
    assert ex["input_summary"] == "Summarize X"


def test_feed_last_chat_session_shape(app_with_deps):
    app, db = app_with_deps
    session = MagicMock()
    session.id = "s-1"
    session.title = "Draft welcome email"
    session.updated_at = datetime.now(timezone.utc)

    # First three queries (executions, canvases, agents) return empty/None;
    # the chat-session query returns our session via .first().
    empty_chain = MagicMock()
    empty_chain.filter.return_value = empty_chain
    empty_chain.outerjoin.return_value = empty_chain
    empty_chain.order_by.return_value = empty_chain
    empty_chain.limit.return_value = empty_chain
    empty_chain.all.return_value = []
    empty_chain.first.return_value = None

    session_chain = MagicMock()
    session_chain.filter.return_value = session_chain
    session_chain.order_by.return_value = session_chain
    session_chain.first.return_value = session

    db.query.side_effect = [empty_chain, empty_chain, session_chain, empty_chain]

    client = TestClient(app)
    r = client.get("/api/dashboard/feed")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["last_chat_session"] is not None
    assert data["last_chat_session"]["id"] == "s-1"
    assert data["last_chat_session"]["title"] == "Draft welcome email"
