"""Coverage wave 90 — api/dashboard_routes.py (76% → 95%+).

Closes the fail-open exception branches of the four helper queries, the
graduation-service import failure, and the tier-normalization paths
(unknown tier → student, terminal tier → no next tier, missing criteria
→ no threshold). Endpoint coverage: success aggregate + unauth 401.
"""
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import dashboard_routes as dr
from core.auth import get_current_user


class FakeUser:
    id = "u-1"
    tenant_id = "t1"
    workspace_id = "ws-1"


def _chained(all_result=None, first_result=None):
    """Query mock where every chained call returns itself and `.all()`/`.first()` land."""
    q = MagicMock()
    q.filter.return_value = q
    q.outerjoin.return_value = q
    q.order_by.return_value = q
    q.limit.return_value = q
    if all_result is not None:
        q.all.return_value = all_result
    q.first.return_value = first_result
    return q


def _agent(name="Bot", status="intern"):
    a = MagicMock()
    a.id = "a1"
    a.name = name
    a.status = status
    a.updated_at = None
    return a


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def client(mock_db):
    app = FastAPI()
    app.include_router(dr.router)
    app.dependency_overrides[get_current_user] = lambda: FakeUser()
    app.dependency_overrides[dr.get_db] = lambda: mock_db
    yield TestClient(app)
    app.dependency_overrides = {}


@pytest.fixture
def anon_client():
    app = FastAPI()
    app.include_router(dr.router)
    yield TestClient(app)
    app.dependency_overrides = {}


class TestFeedEndpoint:
    def test_feed_requires_auth(self, anon_client):
        assert anon_client.get("/api/dashboard/feed").status_code == 401

    def test_feed_success_populates_all_sections(self, client, mock_db):
        exec_row = MagicMock()
        exec_row.id = "e1"
        exec_row.agent_id = "a1"
        exec_row.status = "completed"
        exec_row.input_summary = "x" * 300
        exec_row.started_at = datetime(2026, 8, 1, 12, 0, 0)
        exec_row.duration_seconds = 3.5

        canvas = MagicMock()
        canvas.id = "c1"
        canvas.canvas_id = "cv-1"
        canvas.action_type = "present"
        canvas.created_at = datetime(2026, 8, 1, 11, 0, 0)

        chat = MagicMock()
        chat.id = "chat-1"
        chat.title = "My session"
        chat.updated_at = datetime(2026, 8, 1, 10, 0, 0)

        agent = _agent(status="intern")

        def side_effect(model, *a, **k):
            if model is dr.CanvasAudit:
                return _chained(all_result=[canvas])
            if model is dr.ChatSession:
                return _chained(first_result=chat)
            if model is dr.AgentRegistry:
                return _chained(all_result=[agent])
            return _chained(
                all_result=[(exec_row, "Agent Name"), (exec_row, None)]
            )
        mock_db.query.side_effect = side_effect

        with patch.object(dr, "AgentGraduationService", create=True) as ags:
            ags.CRITERIA = {"INTERN": {"min_episodes": 10}}
            resp = client.get("/api/dashboard/feed")

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data["recent_executions"]) == 2
        assert data["recent_executions"][0]["agent_name"] == "Agent Name"
        assert data["recent_executions"][1]["agent_name"] == "Unknown"
        assert data["recent_executions"][0]["input_summary"] == "x" * 200
        assert data["recent_executions"][0]["started_at"].startswith("2026-08-01")
        assert data["recent_executions"][0]["duration_seconds"] == 3.5
        assert len(data["recent_canvases"]) == 1
        assert data["recent_canvases"][0]["action"] == "present"
        assert data["last_chat_session"]["id"] == "chat-1"
        assert data["last_chat_session"]["title"] == "My session"
        assert len(data["agents_progress"]) == 1
        assert data["agents_progress"][0]["current_tier"] == "intern"
        assert data["agents_progress"][0]["next_tier"] == "supervised"

    def test_feed_empty_state(self, client, mock_db):
        def side_effect(model, *a, **k):
            if model is dr.ChatSession:
                return _chained(first_result=None)
            return _chained(all_result=[])
        mock_db.query.side_effect = side_effect

        with patch.object(dr, "AgentGraduationService", create=True):
            resp = client.get("/api/dashboard/feed")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["recent_executions"] == []
        assert data["recent_canvases"] == []
        assert data["last_chat_session"] is None
        assert data["agents_progress"] == []


class TestHelpers:
    def test_recent_executions_fails_open_on_exception(self):
        db = MagicMock()
        db.query.side_effect = Exception("schema drift")
        assert dr._recent_executions(db, "ws-1") == []

    def test_recent_canvases_fails_open_on_exception(self):
        db = MagicMock()
        db.query.side_effect = Exception("schema drift")
        assert dr._recent_canvases(db, "t1") == []

    def test_last_chat_session_fails_open_on_exception(self):
        db = MagicMock()
        db.query.side_effect = Exception("schema drift")
        assert dr._last_chat_session(db, "u1") is None

    def test_last_chat_session_untitled_default(self):
        row = MagicMock()
        row.id = "c2"
        row.title = None
        row.updated_at = None
        db = MagicMock()
        db.query.return_value = _chained(first_result=row)
        result = dr._last_chat_session(db, "u1")
        assert result["title"] == "Untitled session"
        assert result["updated_at"] is None

    def test_agents_progress_fails_open_on_exception(self):
        db = MagicMock()
        db.query.side_effect = Exception("schema drift")
        assert dr._agents_progress(db, "ws-1") == []

    def test_agents_progress_import_failure_skips_thresholds(self):
        """Graduation-service import failure → criteria={} → no thresholds."""
        db = MagicMock()
        db.query.return_value = _chained(all_result=[_agent(status="supervised")])
        with patch("builtins.__import__", side_effect=ImportError("no service")):
            result = dr._agents_progress(db, "ws-1")
        assert result[0]["next_threshold_episodes"] is None
        assert result[0]["next_tier"] == "autonomous"

    def test_agents_progress_unknown_tier_normalized_to_student(self):
        db = MagicMock()
        db.query.return_value = _chained(all_result=[_agent(status="weird-tier")])
        with patch.object(dr, "AgentGraduationService", create=True) as ags:
            ags.CRITERIA = {}
            result = dr._agents_progress(db, "ws-1")
        assert result[0]["current_tier"] == "student"
        assert result[0]["next_tier"] == "intern"

    def test_agents_progress_terminal_tier_has_no_next(self):
        db = MagicMock()
        db.query.return_value = _chained(all_result=[_agent(status="autonomous")])
        with patch.object(dr, "AgentGraduationService", create=True) as ags:
            ags.CRITERIA = {"SUPERVISED": {"min_episodes": 25}}
            result = dr._agents_progress(db, "ws-1")
        assert result[0]["next_tier"] is None
        assert result[0]["next_threshold_episodes"] is None

    def test_agents_progress_threshold_from_criteria(self):
        db = MagicMock()
        db.query.return_value = _chained(all_result=[_agent(status="student")])
        with patch.object(dr, "AgentGraduationService", create=True) as ags:
            ags.CRITERIA = {"INTERN": {"min_episodes": 10}}
            result = dr._agents_progress(db, "ws-1")
        assert result[0]["current_tier"] == "student"
        assert result[0]["next_tier"] == "intern"
        assert result[0]["next_threshold_episodes"] == 10
