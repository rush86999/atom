"""Tests for decision-plane admin routes (Gap 2).

Hermetic FastAPI TestClient with overridden auth/DB deps:
- anon/member → 403 on mutating endpoints (parity with stage-router tests)
- admin approve/reject/run-now/status behave against an in-memory DB
"""

import os
os.environ["TESTING"] = "1"

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


def _app(db_session, role="admin"):
    from api.decision_automation_routes import router
    from core.auth import get_current_user
    from core.database import get_db

    app = FastAPI()
    app.include_router(router)

    from types import SimpleNamespace
    user = SimpleNamespace(role=role, id="u1")

    async def _user():
        return user

    def _db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_current_user] = _user
    app.dependency_overrides[get_db] = _db
    return TestClient(app)


def _session():
    from core.models import Base
    engine = create_engine("sqlite:///:memory:", poolclass=StaticPool,
                           connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


class TestAuth:
    def test_member_forbidden(self):
        c = _app(_session(), role="member")
        assert c.post("/api/v1/decision-automation/automation/run-now").status_code == 403
        assert c.post("/api/v1/decision-automation/automation/approve",
                      json={"action_id": 1}).status_code == 403
        assert c.post("/api/v1/decision-automation/automation/reject",
                      json={"action_id": 1}).status_code == 403
        assert c.get("/api/v1/decision-automation/automation").status_code == 403

    def test_status_open(self):
        c = _app(_session(), role="member")
        r = c.get("/api/v1/decision-automation/status")
        assert r.status_code == 200
        assert "phase" in r.json()


class TestAdminFlow:
    def test_run_now_empty(self):
        c = _app(_session())
        r = c.post("/api/v1/decision-automation/automation/run-now")
        assert r.status_code == 200
        assert r.json()["actions"] == []

    def test_approve_reject_roundtrip(self):
        from core import decision_automation as da
        session = _session()
        c = _app(session)
        planted = da._write_action(session, "intent", "certify", "approve", {"n": 1})
        aid = planted["id"]

        r = c.post("/api/v1/decision-automation/automation/approve",
                   json={"action_id": aid})
        assert r.status_code == 200
        assert r.json()["applied"] is True

        r = c.post("/api/v1/decision-automation/automation/approve",
                   json={"action_id": aid})
        assert r.status_code == 404  # already applied

        planted2 = da._write_action(session, "turn", "certify", "approve", {"n": 1})
        r = c.post("/api/v1/decision-automation/automation/reject",
                   json={"action_id": planted2["id"]})
        assert r.status_code == 200
        assert r.json()["applied"] is False

    def test_approve_missing_id(self):
        c = _app(_session())
        assert c.post("/api/v1/decision-automation/automation/approve",
                      json={"action_id": 999}).status_code == 404
        assert c.post("/api/v1/decision-automation/automation/approve",
                      json={}).status_code == 422

    def test_automation_view(self, monkeypatch):
        monkeypatch.setenv("ATOM_DECISION_AUTO_ENFORCE", "off")
        from core import decision_automation as da
        session = _session()
        c = _app(session)
        da._write_action(session, "intent", "certify", "approve", {"n": 1})
        r = c.get("/api/v1/decision-automation/automation")
        assert r.status_code == 200
        body = r.json()
        assert body["mode"] == "off"
        assert len(body["pending"]) == 1
