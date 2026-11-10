"""Real scratch SQLite + JWT controls for the maturity-guide read scope.

No production mocks, no live DB, no model/provider/browser.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.agent_onboarding_routes import router
from core.auth import create_access_token
from core.database import Base, get_db
from core.models import AgentRegistry, Tenant, User, Workspace


class World:
    def __init__(self, tmp_path):
        self.engine = create_engine(
            f"sqlite:///{tmp_path}/maturity_scope.db",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)
        s = uuid.uuid4().hex[:8]
        self.tenant_a = f"tenant-a-{s}"
        self.ws_a = f"ws-a-{s}"
        self.user_a = f"user-a-{s}"
        self.peer_a = f"user-a-peer-{s}"
        self.tenant_b = f"tenant-b-{s}"
        self.ws_b = f"ws-b-{s}"
        self.user_b = f"user-b-{s}"
        self.agent_a = f"agent-a-{s}"
        self.agent_b = f"agent-b-{s}"
        self.shared_agent = f"agent-shared-{s}"
        with self.Session() as db:
            db.add_all([
                Tenant(id=self.tenant_a, name="A", subdomain=f"a-{s}",
                       edition="personal", is_active=True),
                Tenant(id=self.tenant_b, name="B", subdomain=f"b-{s}",
                       edition="personal", is_active=True),
            ])
            db.add_all([
                Workspace(id=self.ws_a, name="WA", tenant_id=self.tenant_a),
                Workspace(id=self.ws_b, name="WB", tenant_id=self.tenant_b),
            ])
            db.add_all([
                User(id=self.user_a, tenant_id=self.tenant_a,
                     email=f"a-{s}@example.com", first_name="A", last_name="User",
                     role="member", status="active", workspace_id=self.ws_a,
                     is_active=True),
                User(id=self.peer_a, tenant_id=self.tenant_a,
                     email=f"peer-{s}@example.com", first_name="P", last_name="User",
                     role="member", status="active", workspace_id=self.ws_a,
                     is_active=True),
                User(id=self.user_b, tenant_id=self.tenant_b,
                     email=f"b-{s}@example.com", first_name="B", last_name="User",
                     role="member", status="active", workspace_id=self.ws_b,
                     is_active=True),
            ])
            for aid, name, user, tenant, workspace, confidence in (
                (self.agent_a, "Private A Agent", self.user_a,
                 self.tenant_a, self.ws_a, 0.62),
                (self.agent_b, "B Agent", self.user_b,
                 self.tenant_b, self.ws_b, 0.30),
                (self.shared_agent, "Legacy Shared Agent", None, None, None, 0.20),
            ):
                db.add(AgentRegistry(
                    id=aid, name=name, category="Operations", role="agent",
                    type="personal", capabilities=[], module_path="core.generic_agent",
                    class_name="GenericAgent", user_id=user, workspace_id=workspace,
                    tenant_id=tenant, status="student", enabled=True,
                    confidence_score=confidence,
                    configuration={"learning": {
                        "role": "sales_assistant",
                        "log": [
                            {"id": "l1", "source": "teacher",
                             "lesson": f"private {aid}", "learned_at": "2026-01-01"},
                            {"id": "l2", "source": "observation",
                             "lesson": f"obs {aid}", "learned_at": "2026-01-02"},
                        ],
                    }},
                ))
            db.commit()

    def token(self, uid):
        with self.Session() as db:
            user = db.query(User).filter(User.id == uid).one()
            return create_access_token({"sub": user.id}, user=user)

    def client(self):
        app = FastAPI()
        app.include_router(router)
        def override():
            session = self.Session()
            try:
                yield session
            finally:
                session.close()
        app.dependency_overrides[get_db] = override
        return TestClient(app, base_url="http://testserver")

    def guide(self, client, token, agent_id):
        return client.get(
            f"/api/agents/{agent_id}/maturity-guide",
            headers={"Authorization": f"Bearer {token}"})

    def snapshot_agent(self, agent_id):
        with self.Session() as db:
            agent = db.query(AgentRegistry).filter(
                AgentRegistry.id == agent_id).one()
            return {
                "name": agent.name,
                "confidence": agent.confidence_score,
                "configuration": agent.configuration,
                "workspace_id": agent.workspace_id,
                "tenant_id": agent.tenant_id,
            }


@pytest.fixture
def world(tmp_path):
    return World(tmp_path)


def test_owner_and_same_scope_member_get_guide_with_fresh_readback(world):
    for token in (world.token(world.user_a), world.token(world.peer_a)):
        with world.client() as c:
            response = world.guide(c, token, world.agent_a)
        assert response.status_code == 200, response.text
        data = response.json()["data"]
        assert data["agent_name"] == "Private A Agent"
        assert data["readiness"]["confidence"] == 0.62
        assert data["learning_progress"]["lessons_from_teacher"] == 1
        assert data["mastery"]
    with world.client() as fresh:
        response = world.guide(
            fresh, world.token(world.user_a), world.agent_a)
    assert response.status_code == 200
    assert response.json()["data"]["agent_name"] == "Private A Agent"


def test_foreign_tenant_workspace_and_unknown_are_indistinguishable_404(world):
    token = world.token(world.user_b)
    with world.client() as c:
        foreign = world.guide(c, token, world.agent_a)
        unknown = world.guide(c, token, "does-not-exist")
    assert foreign.status_code == 404
    assert unknown.status_code == 404
    for response in (foreign, unknown):
        body = response.json()
        payload = body.get("detail", body) if isinstance(body, dict) else {}
        assert payload.get("success") is False
        assert payload.get("error", {}).get("code") == "AGENT_NOT_FOUND"
        assert "Private A Agent" not in response.text
        assert "confidence" not in response.text
        assert "lessons" not in response.text


def test_legacy_shared_agent_remains_readable(world):
    with world.client() as c:
        response = world.guide(
            c, world.token(world.user_a), world.shared_agent)
    assert response.status_code == 200, response.text
    assert response.json()["data"]["agent_name"] == "Legacy Shared Agent"


def test_deactivated_principal_is_refused_without_data(world):
    token = world.token(world.user_b)
    with world.Session() as db:
        user = db.query(User).filter(User.id == world.user_b).one()
        user.is_active = False
        user.status = "inactive"
        db.commit()
    with world.client() as c:
        response = world.guide(c, token, world.agent_b)
    assert response.status_code in (401, 403), response.text
    assert "B Agent" not in response.text
    assert "confidence" not in response.text


def test_moved_principal_uses_current_workspace_not_token_claim(world):
    token = world.token(world.user_a)
    with world.Session() as db:
        user = db.query(User).filter(User.id == world.user_a).one()
        user.workspace_id = world.ws_b
        user.tenant_id = world.tenant_b
        db.commit()
    with world.client() as c:
        old_agent = world.guide(c, token, world.agent_a)
        new_agent = world.guide(c, token, world.agent_b)
    assert old_agent.status_code == 404, old_agent.text
    assert new_agent.status_code == 200, new_agent.text
    assert new_agent.json()["data"]["agent_name"] == "B Agent"


def test_read_does_not_mutate_agent_or_learning(world):
    before = world.snapshot_agent(world.agent_a)
    with world.client() as c:
        response = world.guide(
            c, world.token(world.user_a), world.agent_a)
    assert response.status_code == 200
    assert world.snapshot_agent(world.agent_a) == before
