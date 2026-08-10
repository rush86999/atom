"""Coverage wave 19 — workspace-context admin routes + enhanced feedback routes
(TDD)."""
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.feedback_enhanced import router as feedback_router
from api.workspace_context_routes import router as ctx_router
from core.admin_endpoints import get_super_admin
from core.auth import get_current_user
from core.database import get_db


def _user(role="member", uid="u-1"):
    u = SimpleNamespace(id=uid)
    if role:
        u.role = role
    return u


def _client(router, role="member", uid="u-1", db_provider=None):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = db_provider or (lambda: MagicMock())
    app.dependency_overrides[get_current_user] = lambda: _user(role, uid)
    return TestClient(app, raise_server_exceptions=False)


# =========================================================================== #
# workspace_context_routes
# =========================================================================== #
class TestWorkspaceContext:
    def _ctx_client(self, db):
        return _client(ctx_router, role="super_admin", db_provider=lambda: db)

    def _workspace(self, meta=None):
        ws = SimpleNamespace(id="ws-1", metadata_json=meta or {})
        return ws

    def test_get_context(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = self._workspace(
            {"curated_context": ["fact one", "fact two"]}
        )
        db.query.return_value.join.return_value.filter.return_value.all.return_value = [
            ("skill-a",), ("skill-b",),
        ]
        r = self._ctx_client(db).get("/api/workspaces/ws-1/context")
        assert r.status_code == 200
        body = r.json()["data"]
        assert body["curated_context"] == ["fact one", "fact two"]
        assert body["skill_names"] == ["skill-a", "skill-b"]

    def test_get_context_string_coerced(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = self._workspace(
            {"curated_context": "single blob"}
        )
        db.query.return_value.join.return_value.filter.return_value.all.return_value = []
        r = self._ctx_client(db).get("/api/workspaces/ws-1/context")
        assert r.json()["data"]["curated_context"] == ["single blob"]

    def test_get_context_404(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        r = self._ctx_client(db).get("/api/workspaces/missing/context")
        assert r.status_code == 404

    def test_update_context(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = self._workspace()
        r = self._ctx_client(db).put(
            "/api/workspaces/ws-1/context",
            json={"curated_context": ["new fact", "", "another"]},
        )
        assert r.status_code == 200
        assert r.json()["data"]["curated_context"] == ["new fact", "another"]
        assert db.commit.called

    def test_update_context_preserves_other_meta(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = self._workspace(
            {"other": "keep me", "curated_context": ["old"]}
        )
        r = self._ctx_client(db).put(
            "/api/workspaces/ws-1/context", json={"curated_context": ["new"]}
        )
        assert r.status_code == 200
        # fresh dict copy preserves unrelated keys
        updated_meta = db.query.return_value.filter.return_value.first.return_value.metadata_json
        assert updated_meta["other"] == "keep me"
        assert updated_meta["curated_context"] == ["new"]

    def test_assign_skill(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.side_effect = [
            self._workspace(),  # workspace
            SimpleNamespace(id="s1"),  # skill
            None,  # existing association
        ]
        r = self._ctx_client(db).post("/api/workspaces/ws-1/skills/s1")
        assert r.status_code == 200
        assert r.json()["data"]["assigned"] is True
        assert db.execute.called and db.commit.called

    def test_assign_skill_idempotent(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.side_effect = [
            self._workspace(),
            SimpleNamespace(id="s1"),
            ("s1",),  # already assigned
        ]
        r = self._ctx_client(db).post("/api/workspaces/ws-1/skills/s1")
        assert r.status_code == 200
        assert not db.execute.called  # no duplicate insert

    def test_assign_skill_missing_skill_404(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.side_effect = [
            self._workspace(), None,
        ]
        r = self._ctx_client(db).post("/api/workspaces/ws-1/skills/ghost")
        assert r.status_code == 404

    def test_unassign_skill(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = self._workspace()
        r = self._ctx_client(db).delete("/api/workspaces/ws-1/skills/s1")
        assert r.status_code == 200
        assert r.json()["data"]["assigned"] is False
        assert db.execute.called and db.commit.called


# =========================================================================== #
# feedback_enhanced routes
# =========================================================================== #
class TestEnhancedFeedback:
    def _fb_client(self, db):
        return _client(feedback_router, role="member", uid="u-1", db_provider=lambda: db)

    def _agent(self):
        return SimpleNamespace(id="ag-1", name="Agent One")

    def test_submit_thumbs_up(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = self._agent()
        fb = SimpleNamespace(id="fb-1")
        db.add = MagicMock()
        db.refresh = MagicMock(side_effect=lambda x: setattr(x, "id", "fb-1"))
        r = self._fb_client(db).post(
            "/api/feedback/submit",
            json={"agent_id": "ag-1", "user_id": "evil-user", "thumbs_up_down": True},
        )
        assert r.status_code == 200
        assert r.json()["data"]["feedback_type"] == "approval"
        # identity comes from the token, not the body user_id
        created = db.add.call_args.args[0]
        assert created.user_id == "u-1"

    def test_submit_rating(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = self._agent()
        db.refresh = MagicMock(side_effect=lambda x: setattr(x, "id", "fb-2"))
        r = self._fb_client(db).post(
            "/api/feedback/submit",
            json={"agent_id": "ag-1", "user_id": "u-1", "rating": 5},
        )
        assert r.status_code == 200
        assert r.json()["data"]["feedback_type"] == "rating"

    def test_submit_correction(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = self._agent()
        db.refresh = MagicMock(side_effect=lambda x: setattr(x, "id", "fb-3"))
        r = self._fb_client(db).post(
            "/api/feedback/submit",
            json={"agent_id": "ag-1", "user_id": "u-1", "user_correction": "should be X"},
        )
        assert r.json()["data"]["feedback_type"] == "correction"

    def test_submit_missing_agent_404(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        r = self._fb_client(db).post(
            "/api/feedback/submit",
            json={"agent_id": "ghost", "user_id": "u-1", "thumbs_up_down": True},
        )
        assert r.status_code == 404

    def test_submit_no_feedback_validation(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = self._agent()
        r = self._fb_client(db).post(
            "/api/feedback/submit",
            json={"agent_id": "ag-1", "user_id": "u-1"},
        )
        assert r.status_code == 400 or r.status_code == 422

    def test_get_agent_feedback_summary(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = self._agent()
        feedbacks = [
            SimpleNamespace(thumbs_up_down=True, rating=None, feedback_type="approval",
                            created_at=datetime.now()),
            SimpleNamespace(thumbs_up_down=False, rating=None, feedback_type="comment",
                            created_at=datetime.now()),
            SimpleNamespace(thumbs_up_down=None, rating=5, feedback_type="rating",
                            created_at=datetime.now()),
            SimpleNamespace(thumbs_up_down=None, rating=2, feedback_type="rating",
                            created_at=datetime.now()),
        ]
        db.query.return_value.filter.return_value.all.return_value = feedbacks
        r = self._fb_client(db).get("/api/feedback/agent/ag-1")
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["total_feedback"] == 4
        assert data["positive_count"] == 2  # thumbs up + rating 5
        assert data["negative_count"] == 2  # thumbs down + rating 2
        assert data["average_rating"] == 3.5
        assert data["rating_distribution"] == {"1": 0, "2": 1, "3": 0, "4": 0, "5": 1}
        assert data["feedback_types"] == {"approval": 1, "comment": 1, "rating": 2}

    def test_get_agent_feedback_missing_404(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        r = self._fb_client(db).get("/api/feedback/agent/ghost")
        assert r.status_code == 404

    def test_analytics(self):
        db = MagicMock()
        base = MagicMock()
        base.filter.return_value = base
        base.count.side_effect = lambda: 4
        base.distinct.return_value = MagicMock(count=MagicMock(return_value=2))
        base.all.return_value = [
            SimpleNamespace(agent_id="ag-1", thumbs_up_down=True, rating=None,
                            feedback_type="approval", created_at=datetime.now()),
            SimpleNamespace(agent_id="ag-1", thumbs_up_down=False, rating=None,
                            feedback_type="correction", created_at=datetime.now()),
            SimpleNamespace(agent_id="ag-2", thumbs_up_down=None, rating=5,
                            feedback_type="rating", created_at=datetime.now()),
            SimpleNamespace(agent_id="ag-2", thumbs_up_down=None, rating=4,
                            feedback_type="rating", created_at=datetime.now()),
        ]
        db.query.return_value = base
        # agent lookups for top/most-corrected lists
        db.query.return_value.filter.return_value.first.side_effect = [
            SimpleNamespace(id="ag-1", name="A1"),
            SimpleNamespace(id="ag-1", name="A1"),
            SimpleNamespace(id="ag-2", name="A2"),
        ]
        r = self._fb_client(db).get("/api/feedback/analytics")
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["total_feedback"] == 4
        assert data["overall_positive_ratio"] == 0.75  # 3 positive / 4 total
        assert data["top_performing_agents"][0]["agent_id"] == "ag-2"

    def test_trends(self):
        db = MagicMock()
        base = MagicMock()
        base.filter.return_value = base
        base.count.side_effect = [10, 30, 5, 20]
        base.all.return_value = []
        db.query.return_value = base
        r = self._fb_client(db).get("/api/feedback/trends")
        assert r.status_code == 200
        assert "data" in r.json()
