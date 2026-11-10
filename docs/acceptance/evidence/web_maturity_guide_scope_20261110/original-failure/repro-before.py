"""Actual public-API maturity-guide scope repro on scratch SQLite + JWT."""
from __future__ import annotations

import json
import uuid

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
            f"sqlite:///{tmp_path}/scope.db",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)
        s = uuid.uuid4().hex[:8]
        self.tenant_a = f"tenant-a-{s}"
        self.ws_a = f"ws-a-{s}"
        self.user_a = f"user-a-{s}"
        self.tenant_b = f"tenant-b-{s}"
        self.ws_b = f"ws-b-{s}"
        self.user_b = f"user-b-{s}"
        self.agent_a = f"agent-a-{s}"
        self.agent_b = f"agent-b-{s}"
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
                User(id=self.user_b, tenant_id=self.tenant_b,
                     email=f"b-{s}@example.com", first_name="B", last_name="User",
                     role="member", status="active", workspace_id=self.ws_b,
                     is_active=True),
            ])
            for aid, name, user, tenant, ws, conf in (
                (self.agent_a, "Private A Agent", self.user_a,
                 self.tenant_a, self.ws_a, 0.62),
                (self.agent_b, "B Agent", self.user_b,
                 self.tenant_b, self.ws_b, 0.30),
            ):
                db.add(AgentRegistry(
                    id=aid, name=name, category="Operations", role="agent",
                    type="personal", capabilities=[], module_path="core.generic_agent",
                    class_name="GenericAgent", user_id=user, workspace_id=ws,
                    tenant_id=tenant, status="student", enabled=True,
                    confidence_score=conf,
                    configuration={"learning": {
                        "role": "sales_assistant",
                        "log": [
                            {"id": "l1", "source": "teacher",
                             "lesson": "private lesson A", "learned_at": "2026-01-01"},
                            {"id": "l2", "source": "observation",
                             "lesson": "private obs A", "learned_at": "2026-01-02"},
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


def main():
    import tempfile
    from pathlib import Path
    world = World(Path(tempfile.mkdtemp(prefix="maturity-scope-repro-")))
    out = {}
    with world.client() as c:
        for label, token, agent in (
            ("owner_same_scope", world.token(world.user_a), world.agent_a),
            ("foreign_tenant_workspace", world.token(world.user_b), world.agent_a),
            ("foreign_own_agent", world.token(world.user_b), world.agent_b),
            ("unknown", world.token(world.user_b), "does-not-exist"),
        ):
            r = c.get(f"/api/agents/{agent}/maturity-guide",
                      headers={"Authorization": f"Bearer {token}"})
            try:
                body = r.json()
            except Exception:
                body = None
            out[label] = {
                "status": r.status_code,
                "agent_name": (body or {}).get("data", {}).get("agent_name"),
                "confidence": (body or {}).get("data", {}).get("readiness", {}).get("confidence"),
                "lessons": (body or {}).get("data", {}).get("learning_progress", {}).get("lessons_from_teacher"),
                "mastery_present": "mastery" in ((body or {}).get("data") or {}),
                "error": (body or {}).get("detail") or (body or {}).get("message"),
            }
    print(json.dumps(out, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
