"""Actual public-API presence override repro on scratch SQLite + real JWT."""
from __future__ import annotations

import datetime
import json
import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.user_activity_routes import router
from core.auth import create_access_token
from core.database import Base, get_db
from core.models import Tenant, User, UserActivity, UserState, Workspace


class World:
    def __init__(self, tmp_path):
        self.engine = create_engine(
            f"sqlite:///{tmp_path}/presence.db",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)
        s = uuid.uuid4().hex[:8]
        self.tenant = f"tenant-{s}"
        self.ws = f"ws-{s}"
        self.self_user = f"user-self-{s}"
        self.peer = f"user-peer-{s}"
        now = datetime.datetime.now(datetime.timezone.utc)
        with self.Session() as db:
            db.add(Tenant(id=self.tenant, name="T", subdomain=f"t-{s}",
                          edition="personal", is_active=True))
            db.add(Workspace(id=self.ws, name="W", tenant_id=self.tenant))
            for uid, email in ((self.self_user, f"self-{s}@example.com"),
                               (self.peer, f"peer-{s}@example.com")):
                db.add(User(id=uid, tenant_id=self.tenant, email=email,
                            first_name="U", last_name="Ser", role="member",
                            status="active", workspace_id=self.ws,
                            is_active=True))
            db.add(UserActivity(
                id=f"ua-self-{s}", user_id=self.self_user,
                state=UserState.offline, last_activity_at=now,
                manual_override=False,
                created_at=now, updated_at=now,
            ))
            db.add(UserActivity(
                id=f"ua-peer-{s}", user_id=self.peer,
                state=UserState.offline, last_activity_at=now,
                manual_override=False,
                created_at=now, updated_at=now,
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

    def call(self, client, method, path, token, **kwargs):
        headers = {"Authorization": f"Bearer {token}"}
        return getattr(client, method)(path, headers=headers, **kwargs)


def _state(world, client, token, uid):
    r = world.call(client, "get", f"/api/users/{uid}/activity/state", token)
    try:
        body = r.json()
    except Exception:
        body = None
    return r.status_code, body


def main():
    import tempfile
    from pathlib import Path
    world = World(Path(tempfile.mkdtemp(prefix="presence-repro-")))
    self_token = world.token(world.self_user)
    peer_token = world.token(world.peer)
    out = {}
    with world.client() as c:
        future = (datetime.datetime.now(datetime.timezone.utc)
                  + datetime.timedelta(hours=2)).isoformat()
        r = world.call(c, "post", f"/api/users/{world.self_user}/activity/override",
                       self_token, json={"state": "away", "expires_at": future})
        out["set_aware_future"] = {"status": r.status_code, "body": r.json()}
        out["get_after_set"] = _state(world, c, self_token, world.self_user)
        r = world.call(c, "delete", f"/api/users/{world.self_user}/activity/override",
                       self_token)
        out["clear"] = {"status": r.status_code, "body": r.json()}
        out["get_after_clear"] = _state(world, c, self_token, world.self_user)

        r = world.call(c, "post", f"/api/users/{world.self_user}/activity/override",
                       self_token, json={"state": "bogus"})
        out["invalid_state"] = {"status": r.status_code, "body": r.json()}
        r = world.call(c, "post", f"/api/users/{world.self_user}/activity/override",
                       self_token, json={"state": "away", "expires_at": "not-a-date"})
        out["invalid_expiry"] = {"status": r.status_code, "body": r.json()}
        r = world.call(c, "post", f"/api/users/{world.self_user}/activity/override",
                       self_token, json={"state": "away",
                                         "expires_at": "2030-01-01T00:00:00"})
        out["set_naive_future"] = {"status": r.status_code, "body": r.json()}
        out["get_after_naive"] = _state(world, c, self_token, world.self_user)

        past = (datetime.datetime.now(datetime.timezone.utc)
                - datetime.timedelta(hours=1)).isoformat()
        r = world.call(c, "post", f"/api/users/{world.self_user}/activity/override",
                       self_token, json={"state": "away", "expires_at": past})
        out["set_aware_past"] = {"status": r.status_code, "body": r.json()}
        out["get_after_expired"] = _state(world, c, self_token, world.self_user)

        r = world.call(c, "post", f"/api/users/{world.peer}/activity/override",
                       self_token, json={"state": "online"})
        out["foreign_set"] = {"status": r.status_code, "body": r.json()}
        r = world.call(c, "delete", f"/api/users/{world.peer}/activity/override",
                       self_token)
        out["foreign_clear"] = {"status": r.status_code, "body": r.json()}
        out["foreign_get"] = _state(world, c, peer_token, world.self_user)

        # Same operation/material replay: no operation id exists today; repeat
        # the same request and observe idempotent state.
        r1 = world.call(c, "post", f"/api/users/{world.self_user}/activity/override",
                        self_token, json={"state": "offline"})
        r2 = world.call(c, "post", f"/api/users/{world.self_user}/activity/override",
                        self_token, json={"state": "offline"})
        out["repeat_same"] = {"first": r1.status_code, "second": r2.status_code,
                              "second_body": r2.json()}
    print(json.dumps(out, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
