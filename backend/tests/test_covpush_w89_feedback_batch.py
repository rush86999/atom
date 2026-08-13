# -*- coding: utf-8 -*-
"""Coverage wave 89 — api/feedback_batch.py (Batch feedback adjudication).

Real in-memory SQLite (no network, no LLM). Covers every endpoint
(approve/reject/update-status/pending/stats) x {success, missing feedback,
empty ids, invalid status, 401 unauth, 403 non-moderator role, 422 body
validation, service-failure paths}.

Security regression surface checked this wave:
  * every endpoint rejects anonymous callers with 401 (Round 37 fix),
  * every endpoint rejects non-supervisor roles (team_lead+) with 403
    (Bughunt 2026-08-09 fix) — members/viewers/guests cannot read or
    adjudicate other users' feedback.
"""
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.feedback_batch import router as feedback_batch_router
from core.auth import get_current_user
from core.database import Base, get_db
from core.models import AgentFeedback, AgentRegistry, User

AUTH_HEADERS = {"Authorization": "Bearer test-token"}


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


def _make_user(db, user_id="user-1", role="admin", email=None):
    existing = db.query(User).filter(User.id == user_id).first()
    if existing:
        return existing
    user = User(
        id=user_id,
        email=email or f"{user_id}@example.com",
        first_name="T",
        last_name="U",
        role=role,
        status="active",
        tenant_id="t1",
    )
    db.add(user)
    db.commit()
    return user


def _make_agent(db, agent_id="agent-1"):
    existing = db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).first()
    if existing:
        return existing
    agent = AgentRegistry(
        id=agent_id,
        name=f"Agent {agent_id}",
        workspace_id="ws-1",
        tenant_id="t1",
        category="Test",
        module_path="test",
        class_name="Test",
    )
    db.add(agent)
    db.commit()
    return agent


def _make_feedback(db, feedback_id, agent_id="agent-1", user_id="user-1",
                   feedback_type="correction", status="pending",
                   original_output="out", user_correction="fix",
                   rating=None, thumbs_up_down=None, created_days=1,
                   with_agent=True):
    if with_agent:
        _make_agent(db, agent_id)
    fb = AgentFeedback(
        id=feedback_id,
        agent_id=agent_id,
        user_id=user_id,
        original_output=original_output,
        user_correction=user_correction,
        feedback_type=feedback_type,
        thumbs_up_down=thumbs_up_down,
        rating=rating,
        status=status,
        created_at=datetime.now() - timedelta(days=created_days),
    )
    db.add(fb)
    db.commit()
    return fb


@pytest.fixture()
def client(db):
    app = FastAPI()
    app.include_router(feedback_batch_router)
    admin = _make_user(db, role="admin")

    def _override_db():
        yield db

    def _override_user():
        return admin

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = _override_user
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture()
def anon_client(db):
    app = FastAPI()
    app.include_router(feedback_batch_router)

    def _override_db():
        yield db

    app.dependency_overrides[get_db] = _override_db
    return TestClient(app)


VALID_BODIES = {
    "post": {"feedback_ids": ["fb-1"], "user_id": "user-1"},
    "get": None,
}

class TestAuthEnforcement:
    @pytest.mark.parametrize("method,path", [
        ("post", "/api/feedback/batch/approve"),
        ("post", "/api/feedback/batch/reject"),
        ("post", "/api/feedback/batch/update-status"),
        ("get", "/api/feedback/batch/pending"),
        ("get", "/api/feedback/batch/stats"),
    ])
    def test_anonymous_requests_rejected(self, anon_client, method, path):
        body = VALID_BODIES[method]
        resp = getattr(anon_client, method)(path, json=body) if body is not None \
            else getattr(anon_client, method)(path)
        assert resp.status_code == 401

    @pytest.mark.parametrize("method,path", [
        ("post", "/api/feedback/batch/approve"),
        ("post", "/api/feedback/batch/reject"),
        ("post", "/api/feedback/batch/update-status"),
        ("get", "/api/feedback/batch/pending"),
        ("get", "/api/feedback/batch/stats"),
    ])
    def test_non_moderator_role_forbidden(self, db, method, path):
        app = FastAPI()
        app.include_router(feedback_batch_router)

        def _override_db():
            yield db

        def _override_user():
            return _make_user(db, user_id="member-1", role="member")

        app.dependency_overrides[get_db] = _override_db
        app.dependency_overrides[get_current_user] = _override_user
        member_client = TestClient(app)
        body = VALID_BODIES[method]
        resp = getattr(member_client, method)(path, json=body) if body is not None \
            else getattr(member_client, method)(path)
        assert resp.status_code == 403

    def test_moderator_dep_accepts_userrole_enum_role(self, db):
        """require_feedback_moderator normalizes UserRole enum roles before
        comparing (line: isinstance(role, UserRole) -> role.value)."""
        from core.models import UserRole
        from types import SimpleNamespace
        app = FastAPI()
        app.include_router(feedback_batch_router)

        def _override_db():
            yield db

        enum_user = SimpleNamespace(
            id="enum-admin", email="enum@example.com", role=UserRole.ADMIN,
        )

        def _override_user():
            return enum_user

        app.dependency_overrides[get_db] = _override_db
        app.dependency_overrides[get_current_user] = _override_user
        resp = TestClient(app).get("/api/feedback/batch/pending")
        assert resp.status_code == 200

    def test_moderator_dep_enum_guest_role_forbidden(self, db):
        from core.models import UserRole
        app = FastAPI()
        app.include_router(feedback_batch_router)

        def _override_db():
            yield db

        enum_user = User(
            id="enum-guest", email="g@example.com", first_name="G",
            last_name="G", role=UserRole.GUEST, status="active", tenant_id="t1",
        )
        db.add(enum_user)
        db.commit()

        def _override_user():
            return enum_user

        app.dependency_overrides[get_db] = _override_db
        app.dependency_overrides[get_current_user] = _override_user
        resp = TestClient(app).get("/api/feedback/batch/pending")
        assert resp.status_code == 403


class TestBatchApprove:
    def test_approve_success(self, client, db):
        _make_feedback(db, "fb-1")
        _make_feedback(db, "fb-2")
        resp = client.post("/api/feedback/batch/approve", json={
            "feedback_ids": ["fb-1", "fb-2"],
            "user_id": "user-1",
            "reason": "Looks correct",
        }, headers=AUTH_HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["processed"] == 2
        assert body["data"]["failed"] == 0
        fb = db.query(AgentFeedback).filter(AgentFeedback.id == "fb-1").first()
        assert fb.status == "approved"
        assert fb.ai_reasoning == "Looks correct"
        assert fb.adjudicated_at is not None

    def test_approve_missing_feedback_flagged_failed(self, client, db):
        _make_feedback(db, "fb-1")
        resp = client.post("/api/feedback/batch/approve", json={
            "feedback_ids": ["fb-1", "missing-id"],
            "user_id": "user-1",
        }, headers=AUTH_HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["processed"] == 1
        assert body["data"]["failed"] == 1
        assert body["data"]["failed_ids"] == ["missing-id"]

    def test_approve_empty_ids_validation_error(self, client):
        resp = client.post("/api/feedback/batch/approve", json={
            "feedback_ids": [],
            "user_id": "user-1",
        }, headers=AUTH_HEADERS)
        assert resp.status_code == 422
        assert resp.json()["detail"]["error"]["code"] == "VALIDATION_ERROR"

    def test_approve_missing_body_fields_422(self, client):
        resp = client.post("/api/feedback/batch/approve", json={}, headers=AUTH_HEADERS)
        assert resp.status_code == 422

    def test_approve_per_feedback_exception_flagged_failed(self, client, db):
        _make_feedback(db, "fb-1")
        with patch.object(db, "query", side_effect=Exception("db down")):
            resp = client.post("/api/feedback/batch/approve", json={
                "feedback_ids": ["fb-1"],
                "user_id": "user-1",
            }, headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["data"]["failed"] == 1

    def test_approve_commit_failure_raises_500(self, client, db):
        _make_feedback(db, "fb-1")
        with patch.object(db, "commit", side_effect=Exception("commit boom")):
            resp = client.post("/api/feedback/batch/approve", json={
                "feedback_ids": ["fb-1"],
                "user_id": "user-1",
            }, headers=AUTH_HEADERS)
        assert resp.status_code == 500


class TestBatchReject:
    def test_reject_success(self, client, db):
        _make_feedback(db, "fb-1")
        resp = client.post("/api/feedback/batch/reject", json={
            "feedback_ids": ["fb-1"],
            "user_id": "user-1",
            "reason": "Not a real issue",
        }, headers=AUTH_HEADERS)
        assert resp.status_code == 200
        fb = db.query(AgentFeedback).filter(AgentFeedback.id == "fb-1").first()
        assert fb.status == "rejected"
        assert fb.ai_reasoning == "Rejected: Not a real issue"

    def test_reject_without_reason(self, client, db):
        _make_feedback(db, "fb-1")
        resp = client.post("/api/feedback/batch/reject", json={
            "feedback_ids": ["fb-1", "missing-id"],
            "user_id": "user-1",
        }, headers=AUTH_HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert body["processed"] == 1
        assert body["failed"] == 1
        assert body["failed_ids"] == ["missing-id"]

    def test_reject_empty_ids_422(self, client):
        resp = client.post("/api/feedback/batch/reject", json={
            "feedback_ids": [],
            "user_id": "user-1",
        }, headers=AUTH_HEADERS)
        assert resp.status_code == 422

    def test_reject_per_feedback_exception(self, client, db):
        _make_feedback(db, "fb-1")
        with patch.object(db, "query", side_effect=Exception("db down")):
            resp = client.post("/api/feedback/batch/reject", json={
                "feedback_ids": ["fb-1"],
                "user_id": "user-1",
            }, headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["failed"] == 1


class TestBatchUpdateStatus:
    def test_update_status_success_pending(self, client, db):
        _make_feedback(db, "fb-1")
        resp = client.post("/api/feedback/batch/update-status", json={
            "feedback_ids": ["fb-1"],
            "new_status": "pending",
            "user_id": "user-1",
            "ai_reasoning": "Reopen for review",
        }, headers=AUTH_HEADERS)
        assert resp.status_code == 200
        fb = db.query(AgentFeedback).filter(AgentFeedback.id == "fb-1").first()
        assert fb.status == "pending"
        assert fb.ai_reasoning == "Reopen for review"
        assert fb.adjudicated_at is None

    def test_update_status_approved_sets_adjudicated_at(self, client, db):
        _make_feedback(db, "fb-1")
        resp = client.post("/api/feedback/batch/update-status", json={
            "feedback_ids": ["fb-1"],
            "new_status": "approved",
            "user_id": "user-1",
        }, headers=AUTH_HEADERS)
        assert resp.status_code == 200
        fb = db.query(AgentFeedback).filter(AgentFeedback.id == "fb-1").first()
        assert fb.status == "approved"
        assert fb.adjudicated_at is not None

    def test_update_status_expired(self, client, db):
        _make_feedback(db, "fb-1")
        resp = client.post("/api/feedback/batch/update-status", json={
            "feedback_ids": ["fb-1"],
            "new_status": "expired",
            "user_id": "user-1",
        }, headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["processed"] == 1

    def test_update_status_invalid_status_422(self, client):
        resp = client.post("/api/feedback/batch/update-status", json={
            "feedback_ids": ["fb-1"],
            "new_status": "bogus",
            "user_id": "user-1",
        }, headers=AUTH_HEADERS)
        assert resp.status_code == 422
        body = resp.json()["detail"]["error"]
        assert body["code"] == "VALIDATION_ERROR"
        assert "valid_options" in body["details"]

    def test_update_status_empty_ids_422(self, client):
        resp = client.post("/api/feedback/batch/update-status", json={
            "feedback_ids": [],
            "new_status": "approved",
            "user_id": "user-1",
        }, headers=AUTH_HEADERS)
        assert resp.status_code == 422

    def test_update_status_missing_feedback_flagged(self, client, db):
        _make_feedback(db, "fb-1")
        resp = client.post("/api/feedback/batch/update-status", json={
            "feedback_ids": ["fb-1", "nope"],
            "new_status": "approved",
            "user_id": "user-1",
        }, headers=AUTH_HEADERS)
        assert resp.json()["processed"] == 1
        assert resp.json()["failed_ids"] == ["nope"]

    def test_update_status_per_feedback_exception(self, client, db):
        _make_feedback(db, "fb-1")
        with patch.object(db, "query", side_effect=Exception("db down")):
            resp = client.post("/api/feedback/batch/update-status", json={
                "feedback_ids": ["fb-1"],
                "new_status": "approved",
                "user_id": "user-1",
            }, headers=AUTH_HEADERS)
        assert resp.json()["failed"] == 1


class TestGetPendingFeedback:
    def test_pending_no_filters(self, client, db):
        _make_feedback(db, "fb-1", feedback_type="correction")
        _make_feedback(db, "fb-2", feedback_type="rating", status="approved")
        resp = client.get("/api/feedback/batch/pending", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["total"] == 1
        assert body["data"]["items"][0]["id"] == "fb-1"
        assert body["data"]["items"][0]["agent_name"] == "Agent agent-1"

    def test_pending_agent_without_relationship_unknown_name(self, client, db):
        _make_feedback(db, "fb-1", with_agent=False)
        resp = client.get("/api/feedback/batch/pending", headers=AUTH_HEADERS)
        assert resp.json()["data"]["items"][0]["agent_name"] == "Unknown"

    def test_pending_filter_by_agent_and_type(self, client, db):
        _make_feedback(db, "fb-1", agent_id="agent-1", feedback_type="correction")
        _make_feedback(db, "fb-2", agent_id="agent-2", feedback_type="rating")
        _make_feedback(db, "fb-3", agent_id="agent-1", feedback_type="comment")
        resp = client.get(
            "/api/feedback/batch/pending",
            params={"agent_id": "agent-1", "feedback_type": "correction"},
            headers=AUTH_HEADERS,
        )
        assert resp.json()["data"]["total"] == 1
        assert resp.json()["data"]["items"][0]["id"] == "fb-1"

    def test_pending_pagination(self, client, db):
        for i in range(5):
            _make_feedback(db, f"fb-{i}")
        resp = client.get("/api/feedback/batch/pending",
                          params={"limit": 2, "offset": 1}, headers=AUTH_HEADERS)
        body = resp.json()["data"]
        assert body["total"] == 5
        assert len(body["items"]) == 2

    def test_pending_limit_out_of_range_422(self, client):
        resp = client.get("/api/feedback/batch/pending", params={"limit": 0},
                          headers=AUTH_HEADERS)
        assert resp.status_code == 422
        resp = client.get("/api/feedback/batch/pending", params={"limit": 1001},
                          headers=AUTH_HEADERS)
        assert resp.status_code == 422


class TestBatchStats:
    def test_stats_with_data(self, client, db):
        _make_feedback(db, "fb-1", feedback_type="correction")
        _make_feedback(db, "fb-2", feedback_type="correction")
        _make_feedback(db, "fb-3", feedback_type="rating", status="approved")
        resp = client.get("/api/feedback/batch/stats", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["status_counts"]["pending"] == 2
        assert data["status_counts"]["approved"] == 1
        assert data["type_counts"]["correction"] == 2
        assert data["total_pending"] == 2
        assert data["pending_by_agent"][0]["agent_id"] == "agent-1"
        assert data["pending_by_agent"][0]["pending_count"] == 2
        assert data["pending_by_agent"][0]["agent_name"] == "Agent agent-1"

    def test_stats_empty_db(self, client):
        resp = client.get("/api/feedback/batch/stats", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["status_counts"] == {
            "pending": 0, "approved": 0, "rejected": 0, "expired": 0}
        assert data["type_counts"] == {}
        assert data["pending_by_agent"] == []
        assert data["total_pending"] == 0
