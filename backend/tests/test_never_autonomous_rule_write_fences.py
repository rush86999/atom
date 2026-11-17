"""Durable write fences for never-autonomous rule UPDATE persistence.

Run against an isolated scratch DB (never the live dev DB):

    TESTING=1 PYTEST_VERSION=ci PYTHON_DOTENV_DISABLED=1 \
    DATABASE_URL=sqlite:////tmp/atom_never_rule_fence_test.db \
    /private/tmp/atom-macos-quickstart.U2N2Wn/backend/venv/bin/python -m pytest \
      tests/test_never_autonomous_rule_write_fences.py -q

The regression being pinned: ``update_never_rule`` used to load a rule
(revision 1), a DIFFERENT Session committed a newer revision of the same
owned rule, and the update then wrote the caller's stale body unconditionally
(revision 2) — so a stale "disable" overwrote a peer's "enable". The loaded
Python object is not a concurrency fence; the UPDATE itself must claim
id + owner + the persisted revision.

These tests use a real file-backed SQLite engine with independent Sessions
(separate connections) and intercept the actual UPDATE statement so the peer
commits AFTER the row was loaded but BEFORE the claim executes. That is the
real interleaving, not merely a sequential expected-revision mismatch.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from core import autonomy_policy as ap
from core.auth import get_current_user
from core.database import get_db
from core.models import ActionAutonomyRule, Base

PEER_MATCH = {"difficulty": ["advanced"], "domain": ["finance"]}
STALE_MATCH = {"domain": ["finance"]}


@pytest.fixture()
def race_store(tmp_path):
    """File-backed engine whose Sessions use genuinely separate connections."""
    engine = create_engine(
        f"sqlite:///{tmp_path / 'atom_never_fence.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    db = Session()
    try:
        yield Session, db, engine
    finally:
        db.close()
        engine.dispose()


def _commit_peer_once(engine, Session, *, rule_id, name, enabled, match,
                      revision):
    """Commit a peer revision at the moment the claim UPDATE is issued.

    The listener fires on the real UPDATE statement, i.e. after the service
    loaded its rule row and before the statement runs. The flag is set before
    opening the peer Session so the peer's own UPDATE does not recurse.
    """
    state = {"fired": 0}

    def _hook(conn, cursor, statement, parameters, context, executemany):
        if state["fired"]:
            return
        if not statement.lstrip().upper().startswith(
                "UPDATE ACTION_AUTONOMY_RULES"):
            return
        state["fired"] = 1
        peer = Session()
        try:
            row = peer.query(ActionAutonomyRule).filter_by(id=rule_id).one()
            row.name = name
            row.enabled = enabled
            row.match_json = match
            row.revision = revision
            peer.commit()
            # Durable timestamp written by the peer itself; the stale writer
            # must not touch it afterwards.
            state["updated_at"] = (
                peer.query(ActionAutonomyRule)
                .filter_by(id=rule_id)
                .one()
                .updated_at
            )
        finally:
            peer.close()

    event.listen(engine, "before_cursor_execute", _hook)
    return state


def _naive(value):
    """SQLite returns naive datetimes; ORM onupdate values can be tz-aware."""
    return value.replace(tzinfo=None) if value is not None else None


def _fresh(Session):
    return Session()


def _durable(Session, rule_id):
    fresh = _fresh(Session)
    try:
        return fresh.query(ActionAutonomyRule).filter_by(id=rule_id).one()
    finally:
        fresh.close()


def test_stale_disable_cannot_remove_peer_enabled_policy(race_store):
    """ROOT regression: stale disable must not overwrite a peer's enable."""
    Session, db, engine = race_store
    rule = ap.create_never_rule(
        db, "u1", name="finance policy", match=PEER_MATCH, enabled=True)
    unrelated = ap.create_never_rule(
        db, "u1", name="unrelated prose rule", match={"category": ["prose"]})
    before_unrelated = _durable(Session, unrelated["id"])

    fired = _commit_peer_once(
        engine, Session, rule_id=rule["id"],
        name="PEER newest finance policy", enabled=True, match=PEER_MATCH,
        revision=2)

    with pytest.raises(ap.NeverRuleConflict) as excinfo:
        ap.update_never_rule(
            db, "u1", rule["id"],
            name="STALE disabled policy", match=STALE_MATCH, enabled=False,
            expected_revision=1)

    assert fired["fired"] == 1
    assert excinfo.value.current_revision == 2

    after = _durable(Session, rule["id"])
    assert after.name == "PEER newest finance policy"
    assert after.enabled is True
    assert after.revision == 2
    assert after.match_json == PEER_MATCH
    # The rejected stale body performed no write after the peer's commit.
    assert "updated_at" in fired
    assert _naive(after.updated_at) == _naive(fired["updated_at"])

    # No duplicate/unrelated effects.
    after_unrelated = _durable(Session, unrelated["id"])
    assert after_unrelated.name == before_unrelated.name
    assert after_unrelated.revision == 1
    assert after_unrelated.updated_at == before_unrelated.updated_at
    assert len(ap.list_never_rules(db, "u1")) == 2


def test_peer_race_without_expected_revision_is_also_fenced(race_store):
    """No precondition still must not clobber a revision committed mid-flight."""
    Session, db, engine = race_store
    rule = ap.create_never_rule(
        db, "u1", name="finance policy", match=PEER_MATCH, enabled=True)

    _commit_peer_once(
        engine, Session, rule_id=rule["id"],
        name="PEER newest finance policy", enabled=True, match=PEER_MATCH,
        revision=2)

    with pytest.raises(ap.NeverRuleConflict) as excinfo:
        ap.update_never_rule(
            db, "u1", rule["id"], name="late unconditional body",
            match=STALE_MATCH, enabled=False)

    assert excinfo.value.current_revision == 2
    durable = _durable(Session, rule["id"])
    assert durable.name == "PEER newest finance policy"
    assert durable.enabled is True
    assert durable.revision == 2


def test_mounted_put_returns_409_with_durable_current_revision(race_store):
    """The existing HTTP route propagates the typed conflict unchanged."""
    Session, _db, engine = race_store
    setup = Session()
    try:
        rule = ap.create_never_rule(
            setup, "u1", name="finance policy", match=PEER_MATCH,
            enabled=True)
    finally:
        setup.close()

    _commit_peer_once(
        engine, Session, rule_id=rule["id"],
        name="PEER newest finance policy", enabled=True, match=PEER_MATCH,
        revision=2)

    from api.autonomy_routes import router

    app = FastAPI()
    app.include_router(router)
    request_db = Session()
    app.dependency_overrides[get_db] = lambda: request_db
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id="u1", workspace_id=None, tenant_id=None)
    try:
        response = TestClient(app).put(
            f"/api/autonomy/never-rules/{rule['id']}",
            json={
                "name": "STALE disabled policy",
                "enabled": False,
                "match": STALE_MATCH,
                "expected_revision": 1,
            },
        )
    finally:
        request_db.close()

    assert response.status_code == 409
    body = response.json()
    assert body["detail"] == "rule_revision_conflict"
    assert body["current_revision"] == 2

    durable = _durable(Session, rule["id"])
    assert durable.name == "PEER newest finance policy"
    assert durable.enabled is True
    assert durable.revision == 2


def test_nonstale_update_increments_once_and_reads_back(race_store):
    Session, db, _engine = race_store
    rule = ap.create_never_rule(
        db, "u1", name="finance policy", match=PEER_MATCH, enabled=True)

    updated = ap.update_never_rule(
        db, "u1", rule["id"], name="finance policy v2",
        match={"domain": ["finance"]}, enabled=False, expected_revision=1)

    assert updated["name"] == "finance policy v2"
    assert updated["enabled"] is False
    assert updated["revision"] == 2

    durable = _durable(Session, rule["id"])
    assert durable.name == "finance policy v2"
    assert durable.enabled is False
    assert durable.revision == 2
    assert durable.match_json == {"domain": ["finance"]}

    # Optional expected_revision remains supported: a second valid write
    # claims revision 2 and increments exactly once more.
    third = ap.update_never_rule(
        db, "u1", rule["id"], name="finance policy v3",
        match=PEER_MATCH, enabled=True, expected_revision=2)
    assert third["revision"] == 3
    assert _durable(Session, rule["id"]).revision == 3


def test_update_without_expected_revision_still_succeeds(race_store):
    Session, db, _engine = race_store
    rule = ap.create_never_rule(
        db, "u1", name="finance policy", match=PEER_MATCH, enabled=True)

    updated = ap.update_never_rule(
        db, "u1", rule["id"], name="no precondition",
        match={"domain": ["finance"]}, enabled=False)

    assert updated["revision"] == 2
    assert updated["enabled"] is False
    assert len(ap.list_never_rules(db, "u1")) == 1


def test_invalid_payload_never_mutates_authoritative_state(race_store):
    Session, db, _engine = race_store
    rule = ap.create_never_rule(
        db, "u1", name="finance policy", match=PEER_MATCH, enabled=True)
    before = _durable(Session, rule["id"])

    with pytest.raises(ap.NeverRuleValidationError):
        ap.update_never_rule(
            db, "u1", rule["id"], name="bad",
            match={"difficulty": ["impossible"]}, expected_revision=1)
    with pytest.raises(ap.NeverRuleValidationError):
        ap.update_never_rule(
            db, "u1", rule["id"], name="", match=PEER_MATCH,
            expected_revision=1)

    after = _durable(Session, rule["id"])
    assert after.name == before.name
    assert after.enabled is before.enabled
    assert after.revision == before.revision
    assert after.match_json == before.match_json
    assert after.updated_at == before.updated_at


def test_owner_nonowner_and_missing_ids_stay_404(race_store):
    Session, db, _engine = race_store
    rule = ap.create_never_rule(
        db, "u1", name="finance policy", match=PEER_MATCH, enabled=True)
    before = _durable(Session, rule["id"])

    with pytest.raises(ap.NeverRuleNotFound):
        ap.update_never_rule(
            db, "u2", rule["id"], name="hijack", match=STALE_MATCH)
    with pytest.raises(ap.NeverRuleNotFound):
        ap.update_never_rule(
            db, "u1", "does-not-exist", name="missing", match=STALE_MATCH)

    after = _durable(Session, rule["id"])
    assert after.name == before.name
    assert after.enabled is True
    assert after.revision == 1

    # Same contract through the mounted PUT.
    from api.autonomy_routes import router

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id="u2", workspace_id=None, tenant_id=None)
    client = TestClient(app)
    assert client.put(
        f"/api/autonomy/never-rules/{rule['id']}",
        json={"name": "hijack", "match": STALE_MATCH},
    ).status_code == 404
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id="u1", workspace_id=None, tenant_id=None)
    assert client.put(
        "/api/autonomy/never-rules/does-not-exist",
        json={"name": "missing", "match": STALE_MATCH},
    ).status_code == 404
