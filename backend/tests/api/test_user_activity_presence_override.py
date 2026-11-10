"""Public-API and service controls for verified presence overrides.

Scratch SQLite + real JWT only. No live DB, provider or browser.
"""
from __future__ import annotations

import datetime
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.user_activity_routes import router
from core.auth import create_access_token
from core.database import Base, get_db
from core.models import (
    Tenant, User, UserActivity, UserActivitySession, UserState, Workspace,
)
from core.presence_override_write_service import (
    _audit_expected,
    _claim_actor,
    _commit_set,
    _resolve_actor,
    verified_clear_override,
    verified_set_override,
)
from core.user_activity_service import UserActivityService


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
                    id=f"ua-{uid}", user_id=uid, state=UserState.offline,
                    last_activity_at=now, manual_override=False,
                    created_at=now, updated_at=now))
            db.commit()

    def token(self, uid):
        with self.Session() as db:
            user = db.query(User).filter(User.id == uid).one()
            return create_access_token({"sub": user.id}, user=user)

    def actor(self, uid):
        with self.Session() as db:
            return db.query(User).filter(User.id == uid).one()

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
        return getattr(client, method)(
            path, headers={"Authorization": f"Bearer {token}"}, **kwargs)

    def activity(self, uid):
        with self.Session() as db:
            return db.query(UserActivity).filter(
                UserActivity.user_id == uid).one()


def _future(seconds=3600):
    return (datetime.datetime.now(datetime.timezone.utc)
            + datetime.timedelta(seconds=seconds)).isoformat()


def test_valid_future_aware_expiry_and_fresh_readback(world):
    token = world.token(world.self_user)
    with world.client() as c:
        response = world.call(
            c, "post", f"/api/users/{world.self_user}/activity/override",
            token, json={"state": "away", "expires_at": _future()})
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["manual_override"] is True
        assert body["state"] == "away"
        assert body["success"] is True
        assert body["verification"]["status"] == "verified"
        assert body["operation_id"].startswith("presence:")
        assert body["manual_override_expires_at"].endswith("+00:00")
        fresh = TestClient(c.app, base_url="http://testserver")
        state = world.call(
            fresh, "get", f"/api/users/{world.self_user}/activity/state", token)
        assert state.status_code == 200, state.text
        assert state.json()["manual_override"] is True
        assert state.json()["state"] == "away"


def test_naive_expiry_is_normalized_utc_not_500(world):
    token = world.token(world.self_user)
    with world.client() as c:
        response = world.call(
            c, "post", f"/api/users/{world.self_user}/activity/override",
            token, json={"state": "away",
                         "expires_at": "2030-01-01T00:00:00"})
        assert response.status_code == 200, response.text
        assert response.json()["manual_override_expires_at"] == \
            "2030-01-01T00:00:00+00:00"
        state = world.call(
            c, "get", f"/api/users/{world.self_user}/activity/state", token)
        assert state.status_code == 200, state.text
        assert state.json()["manual_override"] is True
        assert state.json()["manual_override_expires_at"] == \
            "2030-01-01T00:00:00+00:00"


def test_expired_override_clears_on_read(world):
    token = world.token(world.self_user)
    past = (datetime.datetime.now(datetime.timezone.utc)
            - datetime.timedelta(hours=1)).isoformat()
    with world.client() as c:
        response = world.call(
            c, "post", f"/api/users/{world.self_user}/activity/override",
            token, json={"state": "away", "expires_at": past})
        assert response.status_code == 200, response.text
        state = world.call(
            c, "get", f"/api/users/{world.self_user}/activity/state", token)
        assert state.status_code == 200, state.text
        assert state.json()["manual_override"] is False
        assert state.json()["manual_override_expires_at"] is None
        assert state.json()["state"] == "offline"


def test_invalid_state_and_expiry_are_typed_400(world):
    token = world.token(world.self_user)
    with world.client() as c:
        bad_state = world.call(
            c, "post", f"/api/users/{world.self_user}/activity/override",
            token, json={"state": "bogus"})
        assert bad_state.status_code == 400, bad_state.text
        bad_expiry = world.call(
            c, "post", f"/api/users/{world.self_user}/activity/override",
            token, json={"state": "away", "expires_at": "not-a-date"})
        assert bad_expiry.status_code == 400, bad_expiry.text


def test_foreign_mutations_refused_and_existing_read_visibility(world):
    token = world.token(world.self_user)
    with world.client() as c:
        set_response = world.call(
            c, "post", f"/api/users/{world.peer}/activity/override",
            token, json={"state": "online"})
        assert set_response.status_code == 403, set_response.text
        clear_response = world.call(
            c, "delete", f"/api/users/{world.peer}/activity/override", token)
        assert clear_response.status_code == 403, clear_response.text
        # The existing authenticated read route was not narrowed by this
        # repair; it must be truthful rather than 500.
        read_response = world.call(
            c, "get", f"/api/users/{world.self_user}/activity/state",
            world.token(world.peer))
        assert read_response.status_code == 200, read_response.text


def test_operation_replay_change_conflict_and_no_change(world):
    token = world.token(world.self_user)
    operation_id = f"presence:test-{uuid.uuid4().hex}"
    expiry = _future()
    with world.client() as c:
        first = world.call(
            c, "post", f"/api/users/{world.self_user}/activity/override",
            token, json={"state": "away", "expires_at": expiry,
                         "operation_id": operation_id})
        assert first.status_code == 200, first.text
        assert first.json()["verification"]["status"] == "verified"
        replay = world.call(
            c, "post", f"/api/users/{world.self_user}/activity/override",
            token, json={"state": "away", "expires_at": expiry,
                         "operation_id": operation_id})
        assert replay.status_code == 200, replay.text
        assert replay.json()["verification"]["status"] == "already_applied"
        assert replay.json()["verification"]["replay"] == "do_not_repeat"
        changed = world.call(
            c, "post", f"/api/users/{world.self_user}/activity/override",
            token, json={"state": "online", "expires_at": expiry,
                         "operation_id": operation_id})
        assert changed.status_code == 409, changed.text

        no_change = world.call(
            c, "post", f"/api/users/{world.self_user}/activity/override",
            token, json={"state": "away", "expires_at": expiry,
                         "operation_id": f"presence:nochange-{uuid.uuid4().hex}"})
        assert no_change.status_code == 200, no_change.text
        assert no_change.json()["verification"]["status"] == "no_change"
        assert no_change.json()["verification"]["effect"] == "none"

        clear_op = f"presence:clear-{uuid.uuid4().hex}"
        clear_first = world.call(
            c, "delete", f"/api/users/{world.self_user}/activity/override",
            token, params={"operation_id": clear_op})
        assert clear_first.status_code == 200, clear_first.text
        clear_replay = world.call(
            c, "delete", f"/api/users/{world.self_user}/activity/override",
            token, params={"operation_id": clear_op})
        assert clear_replay.status_code == 200, clear_replay.text
        assert clear_replay.json()["verification"]["status"] == "already_applied"


def test_heartbeat_does_not_overwrite_manual_override(world):
    with world.Session() as db:
        service = UserActivityService(db)
        import asyncio
        asyncio.run(service.set_manual_override(
            world.self_user, UserState.away))
        asyncio.run(service.record_heartbeat(
            world.self_user, "presence-heartbeat-token"))
        db.expire_all()
        activity = db.query(UserActivity).filter(
            UserActivity.user_id == world.self_user).one()
        assert activity.manual_override is True
        assert activity.state == UserState.away


def test_transition_batch_expires_manual_override(world):
    token = world.token(world.self_user)
    past = (datetime.datetime.now(datetime.timezone.utc)
            - datetime.timedelta(hours=1)).isoformat()
    with world.client() as c:
        response = world.call(
            c, "post", f"/api/users/{world.self_user}/activity/override",
            token, json={"state": "away", "expires_at": past})
        assert response.status_code == 200, response.text
    with world.Session() as db:
        import asyncio
        service = UserActivityService(db)
        asyncio.run(service.transition_state_batch())
        db.expire_all()
        activity = db.query(UserActivity).filter(
            UserActivity.user_id == world.self_user).one()
        assert activity.manual_override is False
        assert activity.manual_override_expires_at is None


def test_service_set_and_clear_verified_results(world):
    with world.Session() as db:
        import asyncio
        actor = world.actor(world.self_user)
        set_result = asyncio.run(verified_set_override(
            db, actor=actor, target_user_id=world.self_user,
            state=UserState.away, expires_at=None,
            operation_id=f"presence:service-{uuid.uuid4().hex}"))
        assert set_result["status"] == "verified"
        assert set_result["verification"]["status"] == "verified"
        clear_result = asyncio.run(verified_clear_override(
            db, actor=actor, target_user_id=world.self_user,
            operation_id=f"presence:clear-{uuid.uuid4().hex}"))
        assert clear_result["status"] == "verified"
        assert clear_result["data"]["manual_override"] is False


@pytest.fixture
def world(tmp_path):
    return World(tmp_path)


def test_stale_cas_writer_is_refused(world):
    import asyncio
    from core.presence_override_write_service import _audit_expected, _commit_set
    from core.user_activity_service import UserActivityService

    with world.Session() as stale_db, world.Session() as winner_db:
        stale_activity = stale_db.query(UserActivity).filter(
            UserActivity.user_id == world.self_user).one()
        actor = _resolve_actor(stale_db, world.actor(world.self_user))
        expected = _audit_expected(
            operation_id=f"presence:stale-{uuid.uuid4().hex}",
            action="presence_override_set",
            target=world.self_user,
            request_digest="stale-request",
            prior_digest="", result_digest="", actor=actor)
        asyncio.run(UserActivityService(winner_db).set_manual_override(
            world.self_user, UserState.away))
        result = asyncio.run(_commit_set(
            stale_db, target=world.self_user, state=UserState.online,
            expiry=None, operation_id=expected["operation_id"],
            expected=expected, actor=actor, activity=stale_activity))
        assert result["status"] == "conflict", result
        assert result["verification"]["effect"] == "none"


def test_committed_unverified_is_distinct_from_rollback(world, monkeypatch):
    import core.presence_override_write_service as presence

    monkeypatch.setattr(
        presence, "_verify_activity",
        lambda db, target, digest: {"status": "unavailable", "data": None})
    token = world.token(world.self_user)
    with world.client() as c:
        response = world.call(
            c, "post", f"/api/users/{world.self_user}/activity/override",
            token, json={"state": "away", "expires_at": _future()})
        assert response.status_code == 503, response.text
        body = response.json()
        assert body["success"] is False
        assert body["verification"]["status"] == "unavailable"
        assert body["verification"]["effect"] == "committed"


def test_malformed_operation_id_is_typed_refusal(world):
    token = world.token(world.self_user)
    with world.client() as c:
        response = world.call(
            c, "post", f"/api/users/{world.self_user}/activity/override",
            token, json={"state": "away", "operation_id": "bad id!"})
        assert response.status_code == 422, response.text


def test_actor_claim_pins_current_raw_snapshot(world):
    import asyncio
    with world.Session() as db:
        snapshot = _resolve_actor(db, world.actor(world.self_user))
        assert _claim_actor(db, snapshot) is True
        db.rollback()
        with world.Session() as other:
            other.query(User).filter(User.id == world.self_user).update(
                {User.role: "team_lead"})
            other.commit()
        assert _claim_actor(db, snapshot) is False


def test_replay_refuses_changed_actor_authority(world):
    token = world.token(world.self_user)
    operation_id = f"presence:authority-{uuid.uuid4().hex}"
    with world.client() as c:
        first = world.call(
            c, "post", f"/api/users/{world.self_user}/activity/override",
            token, json={"state": "away", "operation_id": operation_id})
        assert first.status_code == 200, first.text
        with world.Session() as db:
            db.query(User).filter(User.id == world.self_user).update(
                {User.role: "team_lead"})
            db.commit()
        replay = world.call(
            c, "post", f"/api/users/{world.self_user}/activity/override",
            token, json={"state": "away", "operation_id": operation_id})
        assert replay.status_code == 403, replay.text
        assert "authority changed" in replay.text.lower()


def test_no_change_commit_uncertainty_is_effect_unknown(world, monkeypatch):
    import asyncio
    with world.Session() as db:
        actor = world.actor(world.self_user)
        first = asyncio.run(verified_set_override(
            db, actor=actor, target_user_id=world.self_user,
            state=UserState.away, expires_at=None,
            operation_id=f"presence:base-{uuid.uuid4().hex}"))
        assert first["status"] == "verified"
        def boom():
            raise RuntimeError("confirmation lost after commit")
        monkeypatch.setattr(db, "commit", boom)
        result = asyncio.run(verified_set_override(
            db, actor=actor, target_user_id=world.self_user,
            state=UserState.away, expires_at=None,
            operation_id=f"presence:nochange-lost-{uuid.uuid4().hex}"))
        assert result["status"] == "effect_unknown", result
        assert result["verification"]["effect"] == "unknown"
