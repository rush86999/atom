"""Authority/current-scope and material controls for public goal writes.

Scope: ``POST /api/goals``, ``PUT /api/goals/{goal_id}/utility`` and
``DELETE /api/goals/{goal_id}/utility``.

The request-entry ``User`` object is a snapshot. The routes' role gates read
that snapshot, and the legacy service mutated the goal without re-binding the
actor or the reviewed target material. These contracts are failure-first:
before the verified write service existed, an allowed actor whose row was
demoted/deactivated/moved after the gate still committed the goal write, and a
concurrent metadata change was overwritten by the whole-dict utility update.

Only interleaving is instrumented here — the router, role gates, service
transaction, conditional UPDATE and audit receipt are the real ones, on real
fresh SQLite sessions.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text, update
from sqlalchemy.orm import sessionmaker

import api.goal_routes as goal_routes
from api.goal_routes import router as goal_router
from core.auth import get_current_user
from core.database import Base, get_db
from core.models import AuditLog, GoalObjective, Tenant, User, Workspace


_UTILITY = {
    "metric": "steps_executed",
    "direction": "minimize",
    "source": "goal_run",
    "description": "fewer steps",
}


@pytest.fixture()
def env(tmp_path):
    db_path = tmp_path / "goal-write-contract.db"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )

    @event.listens_for(engine, "connect")
    def _wal_pragmas(dbapi_connection, _record):
        # Match the production SQLite contract (core/database.py): WAL lets a
        # peer commit while a request holds a read snapshot, which is the
        # interleaving these contracts exercise.
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA busy_timeout=5000")
        finally:
            cursor.close()

    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    seed = Session()
    seed.add_all([
        Tenant(id="default", name="Personal", subdomain="personal"),
        Workspace(id="ws-test", name="Test", tenant_id="default"),
        Workspace(id="ws-other", name="Other", tenant_id="default"),
    ])
    users = [
        User(
            id="lead-1", tenant_id="default", workspace_id="ws-test",
            email="lead@example.com", first_name="Lead", last_name="One",
            role="team_lead", status="active", is_active=True),
        User(
            id="lead-2", tenant_id="default", workspace_id="ws-test",
            email="lead2@example.com", first_name="Lead", last_name="Two",
            role="team_lead", status="active", is_active=True),
        User(
            id="member-1", tenant_id="default", workspace_id="ws-test",
            email="member@example.com", first_name="Member", last_name="One",
            role="member", status="active", is_active=True),
        User(
            id="member-2", tenant_id="default", workspace_id="ws-test",
            email="member2@example.com", first_name="Member", last_name="Two",
            role="member", status="active", is_active=True),
        User(
            id="viewer-1", tenant_id="default", workspace_id="ws-test",
            email="viewer@example.com", first_name="Viewer", last_name="One",
            role="viewer", status="active", is_active=True),
        User(
            id="lead-other", tenant_id="default", workspace_id="ws-other",
            email="other@example.com", first_name="Other", last_name="Lead",
            role="team_lead", status="active", is_active=True),
    ]
    goals = [
        GoalObjective(
            id="goal-1", tenant_id="default", workspace_id="ws-test",
            title="Quote follow-up", status="active", progress=10.0,
            criteria=[{"type": "entity_exists", "name": "quote"}],
            metadata_json={
                "utility_target": dict(_UTILITY),
                "peer_note": "original",
            }),
        GoalObjective(
            id="goal-null", tenant_id="default", workspace_id="ws-test",
            title="Null metadata goal", status="active"),
        GoalObjective(
            id="goal-empty", tenant_id="default", workspace_id="ws-test",
            title="Empty metadata goal", status="active", metadata_json={}),
        GoalObjective(
            id="goal-json-null", tenant_id="default", workspace_id="ws-test",
            title="JSON null metadata goal", status="active",
            metadata_json={}),
        GoalObjective(
            id="goal-transition", tenant_id="default", workspace_id="ws-test",
            title="Nullable transition goal", status="active",
            metadata_json={}),
        GoalObjective(
            id="goal-other", tenant_id="default", workspace_id="ws-other",
            title="Other workspace goal", status="active",
            metadata_json={}),
    ]
    seed.add_all(users + goals)
    seed.commit()
    # Explicit physical SQL NULL: the column's Python default would otherwise
    # turn an explicit None into ``{}`` on INSERT. Null and empty-object
    # metadata are different material for the CAS.
    seed.execute(text(
        "UPDATE goal_objectives SET metadata_json = NULL "
        "WHERE id = 'goal-null'"))
    # A stored JSON null ('null'), physically distinct from both SQL NULL and
    # the empty object. ORM deserialization maps it to Python None, so the
    # write service must read the physical IS NULL flag in the same snapshot.
    seed.execute(text(
        "UPDATE goal_objectives SET metadata_json = 'null' "
        "WHERE id = 'goal-json-null'"))
    seed.commit()
    seed.close()

    app = FastAPI()
    app.include_router(goal_router)

    def db_override():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = db_override

    def client(user: User):
        # Per-actor app keeps the dependency override scoped to one actor, so
        # the tests never race on a global override.
        scoped = FastAPI()
        scoped.include_router(goal_router)
        scoped.dependency_overrides[get_db] = db_override
        scoped.dependency_overrides[get_current_user] = lambda: user
        return TestClient(scoped, raise_server_exceptions=False)

    actors = {}
    for user_id in (
            "lead-1", "lead-2", "member-1", "member-2", "viewer-1",
            "lead-other"):
        session = Session()
        actors[user_id] = session.query(User).filter(
            User.id == user_id).one()
        session.close()

    yield SimpleNamespace(
        engine=engine, db_path=db_path, Session=Session, app=app,
        client=client, actors=actors,
    )


# ------------------------------------------------------------------ helpers

def _change_user(env, user_id, **values):
    """A peer request/session commits an authority change."""
    db = env.Session()
    try:
        db.execute(update(User).where(User.id == user_id).values(**values))
        db.commit()
    finally:
        db.close()


def _actor_workspace(env, user_id):
    db = env.Session()
    try:
        return db.query(User).filter(User.id == user_id).one().workspace_id
    finally:
        db.close()


def _peer_goal_change(env, goal_id, **values):
    """A peer commits a change to the reviewed goal row."""
    db = env.Session()
    try:
        db.execute(
            update(GoalObjective)
            .where(GoalObjective.id == goal_id)
            .values(**values))
        db.commit()
    finally:
        db.close()


_NULLABLE_METADATA_KINDS = ("sql_null", "json_null", "object")
_NULLABLE_GOALS = {
    "sql_null": "goal-null",
    "json_null": "goal-json-null",
    "object": "goal-empty",
}


def _physical_metadata(env, goal_id):
    """Read the physically stored metadata kind without ORM normalization.

    SQLite stores JSON null as the JSON text ``'null'``; ``IS NULL`` is only
    true for a physical SQL NULL. This helper deliberately does not reuse the
    service's snapshot helper so the assertions are independent of it.
    """
    db = env.Session()
    try:
        row = db.execute(text(
            "SELECT metadata_json, (metadata_json IS NULL) "
            "FROM goal_objectives WHERE id = :id"), {"id": goal_id}).one()
    finally:
        db.close()
    raw, is_sql_null = row
    if is_sql_null:
        return "sql_null", None
    if raw == "null":
        return "json_null", None
    return "object", json.loads(raw)


def _set_physical_metadata(env, goal_id, kind):
    """Commit an arbitrary physical nullable state for the transition matrix."""
    values = {"sql_null": None, "json_null": "null", "object": "{}"}
    db = env.Session()
    try:
        db.execute(
            text("UPDATE goal_objectives SET metadata_json = :value "
                 "WHERE id = :id"),
            {"value": values[kind], "id": goal_id})
        db.commit()
    finally:
        db.close()
    assert _physical_metadata(env, goal_id)[0] == kind


def _arm_after_gate(monkeypatch, change):
    """Commit ``change`` immediately after the last real route role gate.

    This is the reachable public interleaving: the request-entry actor is
    authorized, a peer commits a demotion/deactivation/workspace change, and
    only then does the write path run. Both real gates still run and return
    their real verdicts; the peer change fires once, after the gate that the
    request actually uses (supervisor gate, or member runner gate).
    """
    original_supervisor = goal_routes._is_supervisor
    original_runner = goal_routes._require_runner
    state = {"armed": True}

    def fire():
        if state["armed"]:
            state["armed"] = False
            change()

    def gate_then_peer(db, current_user):
        verdict = original_supervisor(db, current_user)
        if verdict:
            fire()
        return verdict

    def runner_then_peer(db, current_user):
        original_runner(db, current_user)
        fire()

    monkeypatch.setattr(goal_routes, "_is_supervisor", gate_then_peer)
    monkeypatch.setattr(goal_routes, "_require_runner", runner_then_peer)
    return state


def _arm_after_goal_read(env, change):
    """Commit ``change`` between the service's goal read and its write.

    The SQL statement has executed (so the ORM snapshot is fixed) but no write
    transaction is held yet — the exact lost-update/TOCTOU window.
    """
    state = {"armed": True}

    def after_cursor_execute(
            conn, cursor, statement, parameters, context, executemany):
        if (
            state["armed"]
            and "select" in statement.lower()
            and "goal_objectives" in statement.lower()
        ):
            state["armed"] = False
            change()

    event.listen(env.engine, "after_cursor_execute", after_cursor_execute)
    return state


def _goal(env, goal_id="goal-1"):
    db = env.Session()
    try:
        return db.query(GoalObjective).filter(
            GoalObjective.id == goal_id).first()
    finally:
        db.close()


def _audits(env, resource=None):
    db = env.Session()
    try:
        query = db.query(AuditLog)
        if resource is not None:
            query = query.filter(AuditLog.resource == resource)
        return query.all()
    finally:
        db.close()


def _goal_titled(env, title):
    db = env.Session()
    try:
        return db.query(GoalObjective).filter(
            GoalObjective.title == title).all()
    finally:
        db.close()


# ------------------------------------------------------------ positive twins

def test_create_member_plain_goal_verified_and_audited(env):
    response = env.client(env.actors["member-1"]).post(
        "/api/goals?operation_id=create-member",
        json={"title": "Call the supplier", "description": "ask for a quote"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True
    assert body["goal"]["title"] == "Call the supplier"
    assert body["verification"]["status"] == "verified"
    assert body["verification"]["effect"] == "committed"
    assert body["operation_id"] == "goal:create:create-member"
    assert body["audit_id"] == body["operation_id"]

    rows = _goal_titled(env, "Call the supplier")
    assert len(rows) == 1
    assert rows[0].workspace_id == "ws-test"
    assert rows[0].owner_id == "member-1"
    assert rows[0].criteria == []

    audits = _audits(env, f"goal:{rows[0].id}")
    assert len(audits) == 1
    assert audits[0].id == body["operation_id"]
    assert audits[0].action == "goal_created"
    assert audits[0].user_id == "member-1"
    assert audits[0].workspace_id == "ws-test"
    metadata = json.loads(audits[0].metadata_json)
    assert metadata["target_id"] == rows[0].id
    assert "title" not in audits[0].metadata_json
    assert "quote" not in audits[0].metadata_json


def test_create_supervisor_enrichment_and_role_contract(env):
    supervisor = env.client(env.actors["lead-1"])
    enriched = supervisor.post("/api/goals", json={
        "title": "Close the deal",
        "description": "negotiate",
        "criteria": [{"type": "state_equals", "key": "deal", "value": "won"}],
        "target_date": "2026-12-31",
        "utility_target": dict(_UTILITY),
    })
    assert enriched.status_code == 200, enriched.text
    assert enriched.json()["goal"]["utility_target"]["metric"] == (
        "steps_executed")

    member_enriched = env.client(env.actors["member-1"]).post(
        "/api/goals", json={
            "title": "Member cannot enrich",
            "criteria": [{"type": "entity_exists", "name": "quote"}],
        })
    assert member_enriched.status_code == 403, member_enriched.text

    viewer = env.client(env.actors["viewer-1"]).post(
        "/api/goals", json={"title": "Viewer cannot create"})
    assert viewer.status_code == 403, viewer.text
    assert _goal_titled(env, "Viewer cannot create") == []


def test_utility_roles_and_same_workspace_twins(env):
    member = env.client(env.actors["member-1"])
    viewer = env.client(env.actors["viewer-1"])
    supervisor = env.client(env.actors["lead-2"])

    assert member.put(
        "/api/goals/goal-1/utility", json=dict(_UTILITY)).status_code == 403
    assert viewer.put(
        "/api/goals/goal-1/utility", json=dict(_UTILITY)).status_code == 403
    assert viewer.delete("/api/goals/goal-1/utility").status_code == 403

    set_response = supervisor.put(
        "/api/goals/goal-1/utility?operation_id=utility-set-twin",
        json={"metric": "steps_executed", "direction": "maximize",
              "source": "goal_run"})
    assert set_response.status_code == 200, set_response.text
    body = set_response.json()
    assert body["utility_target"]["direction"] == "maximize"
    assert body["verification"]["status"] == "verified"

    # The peer metadata key written by another request/session survives the
    # utility write; the target write must not own the whole metadata blob.
    goal = _goal(env)
    assert goal.metadata_json["peer_note"] == "original"
    assert goal.criteria == [{"type": "entity_exists", "name": "quote"}]
    assert goal.progress == 10.0

    clear_response = supervisor.delete(
        "/api/goals/goal-1/utility?operation_id=utility-clear-twin")
    assert clear_response.status_code == 200, clear_response.text
    assert clear_response.json()["utility_target"] is None
    assert _goal(env).metadata_json.get("peer_note") == "original"

    # A supervisor of another workspace cannot see or mutate this goal.
    other = env.client(env.actors["lead-other"])
    assert other.put(
        "/api/goals/goal-1/utility", json=dict(_UTILITY)).status_code == 404
    assert other.delete("/api/goals/goal-1/utility").status_code == 404


def test_read_paths_stay_open_to_signed_in_viewer(env):
    viewer = env.client(env.actors["viewer-1"])
    listed = viewer.get("/api/goals")
    assert listed.status_code == 200, listed.text
    assert any(goal["id"] == "goal-1" for goal in listed.json()["goals"])
    assert viewer.get("/api/goals/goal-1").status_code == 200
    assert viewer.get("/api/goals/goal-1/utility").status_code == 200


# ------------------------------------------------- authority race negatives

def test_utility_set_refuses_demotion_committed_after_goal_read(
        env, monkeypatch):
    _arm_after_goal_read(
        env, lambda: _change_user(env, "lead-1", role="member"))
    response = env.client(env.actors["lead-1"]).put(
        "/api/goals/goal-1/utility?operation_id=race-demote",
        json={"metric": "replan_count", "direction": "minimize",
              "source": "goal_run"})
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["error"]["code"] == "AUTHORITY_CHANGED"
    assert response.json()["detail"]["verification"]["effect"] == "none"
    assert _goal(env).metadata_json["utility_target"] == _UTILITY
    assert _audits(env) == []

    # Positive twin: a supervisor who still has authority succeeds.
    twin = env.client(env.actors["lead-2"]).put(
        "/api/goals/goal-1/utility",
        json={"metric": "replan_count", "direction": "minimize",
              "source": "goal_run"})
    assert twin.status_code == 200, twin.text
    assert _goal(env).metadata_json["utility_target"]["metric"] == (
        "replan_count")


def test_utility_clear_refuses_deactivation_committed_after_goal_read(
        env, monkeypatch):
    _arm_after_goal_read(
        env, lambda: _change_user(
            env, "lead-1", status="inactive", is_active=False))
    response = env.client(env.actors["lead-1"]).delete(
        "/api/goals/goal-1/utility?operation_id=race-deactivate")
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["error"]["code"] == "AUTHORITY_CHANGED"
    assert _goal(env).metadata_json["utility_target"] == _UTILITY
    assert _audits(env) == []

    twin = env.client(env.actors["lead-2"]).delete(
        "/api/goals/goal-1/utility")
    assert twin.status_code == 200, twin.text
    assert _goal(env).metadata_json.get("utility_target") is None


def test_utility_set_refuses_workspace_move_after_goal_read(
        env, monkeypatch):
    _arm_after_goal_read(
        env, lambda: _change_user(env, "lead-1", workspace_id="ws-other"))
    response = env.client(env.actors["lead-1"]).put(
        "/api/goals/goal-1/utility?operation_id=race-workspace",
        json={"metric": "steps_executed", "direction": "minimize",
              "source": "goal_run"})
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["error"]["code"] == "AUTHORITY_CHANGED"
    assert _goal(env).metadata_json == {
        "utility_target": dict(_UTILITY), "peer_note": "original"}
    assert _audits(env) == []


def test_utility_set_refuses_workspace_move_committed_after_role_gate(
        env, monkeypatch):
    _arm_after_gate(
        monkeypatch,
        lambda: _change_user(env, "lead-1", workspace_id="ws-other"))
    response = env.client(env.actors["lead-1"]).put(
        "/api/goals/goal-1/utility?operation_id=race-workspace-gate",
        json={"metric": "steps_executed", "direction": "minimize",
              "source": "goal_run"})
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["error"]["code"] == "AUTHORITY_CHANGED"
    assert _goal(env).metadata_json["utility_target"] == _UTILITY
    assert _audits(env) == []

    # A fresh supervisor request in the same workspace still succeeds.
    twin = env.client(env.actors["lead-2"]).put(
        "/api/goals/goal-1/utility",
        json={"metric": "steps_executed", "direction": "maximize",
              "source": "goal_run"})
    assert twin.status_code == 200, twin.text


def test_create_refuses_demotion_committed_after_role_gate(env, monkeypatch):
    _arm_after_gate(
        monkeypatch,
        lambda: _change_user(env, "member-1", role="viewer"))
    response = env.client(env.actors["member-1"]).post(
        "/api/goals?operation_id=race-create-demote",
        json={"title": "Race demoted create"})
    assert response.status_code in (403, 409), response.text
    assert _goal_titled(env, "Race demoted create") == []
    assert _audits(env) == []


def test_create_refuses_deactivation_committed_after_role_gate(
        env, monkeypatch):
    _arm_after_gate(
        monkeypatch,
        lambda: _change_user(
            env, "member-1", status="inactive", is_active=False))
    response = env.client(env.actors["member-1"]).post(
        "/api/goals?operation_id=race-create-deactivate",
        json={"title": "Race deactivated create"})
    assert response.status_code in (403, 409), response.text
    assert _goal_titled(env, "Race deactivated create") == []
    assert _audits(env) == []

    twin = env.client(env.actors["member-2"]).post(
        "/api/goals", json={"title": "Legitimate member create"})
    assert twin.status_code == 200, twin.text


def test_create_refuses_workspace_move_committed_after_role_gate(
        env, monkeypatch):
    _arm_after_gate(
        monkeypatch,
        lambda: _change_user(env, "member-1", workspace_id="ws-other"))
    response = env.client(env.actors["member-1"]).post(
        "/api/goals?operation_id=race-create-workspace",
        json={"title": "Moved actor create"})
    # An already-reviewed request must not be retargeted to the actor's new
    # workspace: the write refuses with effect none in every workspace, and
    # the peer's move stands.
    assert response.status_code in (403, 409), response.text
    assert _goal_titled(env, "Moved actor create") == []
    assert _goal(env, "goal-1").workspace_id == "ws-test"
    assert _actor_workspace(env, "member-1") == "ws-other"
    assert _audits(env) == []


def test_new_request_already_in_current_workspace_can_create(env):
    # Valid twin: a NEW request whose authenticated actor already belongs to
    # ws-other writes there. This is not a mid-request retarget.
    response = env.client(env.actors["lead-other"]).post(
        "/api/goals?operation_id=new-scope-create",
        json={"title": "Other workspace request"})
    assert response.status_code == 200, response.text
    created = _goal_titled(env, "Other workspace request")
    assert len(created) == 1
    assert created[0].workspace_id == "ws-other"
    assert created[0].owner_id == "lead-other"


# -------------------------------------------------- stale material controls

def test_utility_set_refuses_stale_metadata_and_preserves_peer(env, monkeypatch):
    def peer_writes():
        _peer_goal_change(
            env, "goal-1",
            metadata_json={
                "utility_target": dict(_UTILITY),
                "peer_note": "peer-kept",
            },
            criteria=[{"type": "entity_exists", "name": "peer-quote"}],
            progress=55.0)

    _arm_after_goal_read(env, peer_writes)
    response = env.client(env.actors["lead-1"]).put(
        "/api/goals/goal-1/utility?operation_id=stale-metadata",
        json={"metric": "replan_count", "direction": "minimize",
              "source": "goal_run"})
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["error"]["code"] == "STALE_TARGET"
    assert response.json()["detail"]["verification"]["effect"] == "none"

    goal = _goal(env)
    # The peer's metadata material and the independent criteria/progress are
    # all preserved; the stale target write applied nothing.
    assert goal.metadata_json["peer_note"] == "peer-kept"
    assert goal.metadata_json["utility_target"] == _UTILITY
    assert goal.criteria == [{"type": "entity_exists", "name": "peer-quote"}]
    assert goal.progress == 55.0
    assert _audits(env) == []


def test_utility_handles_null_and_empty_metadata_distinctly(env):
    client = env.client(env.actors["lead-1"])
    null_goal = _goal(env, "goal-null")
    empty_goal = _goal(env, "goal-empty")
    assert null_goal.metadata_json is None
    assert empty_goal.metadata_json == {}

    set_null = client.put(
        "/api/goals/goal-null/utility?operation_id=null-material",
        json={"metric": "steps_executed", "direction": "minimize",
              "source": "goal_run"})
    assert set_null.status_code == 200, set_null.text
    assert set_null.json()["verification"]["status"] == "verified"
    assert _goal(env, "goal-null").metadata_json == {
        "utility_target": {"metric": "steps_executed",
                           "direction": "minimize",
                           "source": "goal_run", "description": ""}}

    set_empty = client.put(
        "/api/goals/goal-empty/utility?operation_id=empty-material",
        json={"metric": "human_interventions", "direction": "minimize",
              "source": "goal_run"})
    assert set_empty.status_code == 200, set_empty.text
    assert set_empty.json()["verification"]["status"] == "verified"

    cleared = client.delete(
        "/api/goals/goal-empty/utility?operation_id=empty-material-clear")
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["verification"]["status"] == "verified"
    assert _goal(env, "goal-empty").metadata_json == {}


def test_utility_set_refuses_stale_null_metadata(env, monkeypatch):
    def peer_writes():
        _peer_goal_change(
            env, "goal-null",
            metadata_json={"peer_note": "kept-null"},
            progress=42.0)

    _arm_after_goal_read(env, peer_writes)
    response = env.client(env.actors["lead-1"]).put(
        "/api/goals/goal-null/utility?operation_id=stale-null",
        json={"metric": "steps_executed", "direction": "minimize",
              "source": "goal_run"})
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["error"]["code"] == "STALE_TARGET"
    goal = _goal(env, "goal-null")
    assert goal.metadata_json == {"peer_note": "kept-null"}
    assert goal.progress == 42.0
    assert _audits(env) == []


# -------------------------------------------- nullable metadata material

@pytest.mark.parametrize("kind", _NULLABLE_METADATA_KINDS)
def test_utility_accepts_each_nullable_metadata_kind(env, kind):
    """SQL NULL, JSON null and {} each accept an explicit new target.

    The supplied root probe reproduced a 409 STALE_TARGET only for a physical
    JSON null because the CAS mapped both null kinds to ``IS NULL``. All three
    physical kinds are valid unchanged prior material.
    """
    goal_id = _NULLABLE_GOALS[kind]
    assert _physical_metadata(env, goal_id)[0] == kind
    client = env.client(env.actors["lead-1"])
    operation_id = f"nullable-positive-{kind}"

    response = client.put(
        f"/api/goals/{goal_id}/utility?operation_id={operation_id}",
        json={"metric": "steps_executed", "direction": "minimize",
              "source": "goal_run"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["verification"]["status"] == "verified"
    assert body["verification"]["effect"] == "committed"

    stored_kind, stored_value = _physical_metadata(env, goal_id)
    assert stored_kind == "object"
    assert stored_value["utility_target"]["metric"] == "steps_executed"

    replay = client.put(
        f"/api/goals/{goal_id}/utility?operation_id={operation_id}",
        json={"metric": "steps_executed", "direction": "minimize",
              "source": "goal_run"})
    assert replay.status_code == 200, replay.text
    assert replay.json()["verification"]["status"] == "already_applied"
    assert len(_audits(env)) == 1


def test_nullable_metadata_kinds_have_distinct_prior_digests(env):
    """The exact physical kind is part of the comparison material/digest."""
    client = env.client(env.actors["lead-1"])
    prior_digests = {}
    for kind in _NULLABLE_METADATA_KINDS:
        goal_id = _NULLABLE_GOALS[kind]
        response = client.put(
            f"/api/goals/{goal_id}/utility?operation_id=nullable-digest-{kind}",
            json={"metric": "steps_executed", "direction": "minimize",
                  "source": "goal_run"})
        assert response.status_code == 200, response.text
        audits = _audits(env, f"goal:{goal_id}")
        assert len(audits) == 1
        metadata = json.loads(audits[0].metadata_json)
        prior_digests[kind] = metadata["prior_digest"]
        assert metadata["prior_digest"] != metadata["result_digest"]
    assert len(set(prior_digests.values())) == len(_NULLABLE_METADATA_KINDS)


@pytest.mark.parametrize("peer_kind", _NULLABLE_METADATA_KINDS)
@pytest.mark.parametrize("prior_kind", _NULLABLE_METADATA_KINDS)
def test_utility_refuses_nullable_metadata_transition_after_read(
        env, prior_kind, peer_kind):
    """A peer transition between null/empty kinds refuses with no effect.

    This includes both directions between SQL NULL and JSON null, which share
    a Python ``None`` value but not a physical identity. The peer's exact kind
    is preserved and a fresh request then succeeds against it.
    """
    if prior_kind == peer_kind:
        pytest.skip("same-kind prior material is the positive matrix")

    goal_id = "goal-transition"
    _set_physical_metadata(env, goal_id, prior_kind)
    _arm_after_goal_read(
        env, lambda: _set_physical_metadata(env, goal_id, peer_kind))

    client = env.client(env.actors["lead-1"])
    response = client.put(
        f"/api/goals/{goal_id}/utility"
        f"?operation_id=nullable-transition-{prior_kind}-{peer_kind}",
        json={"metric": "replan_count", "direction": "minimize",
              "source": "goal_run"})
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["error"]["code"] == "STALE_TARGET"
    assert response.json()["detail"]["verification"]["effect"] == "none"
    assert _physical_metadata(env, goal_id)[0] == peer_kind
    assert _audits(env) == []

    # Fresh read: the peer's exact material is the new prior state.
    twin = client.put(
        f"/api/goals/{goal_id}/utility"
        f"?operation_id=nullable-transition-twin-{prior_kind}-{peer_kind}",
        json={"metric": "replan_count", "direction": "minimize",
              "source": "goal_run"})
    assert twin.status_code == 200, twin.text
    assert twin.json()["verification"]["status"] == "verified"
    assert _physical_metadata(env, goal_id)[0] == "object"
    assert len(_audits(env)) == 1


@pytest.mark.parametrize("kind", ("sql_null", "json_null"))
def test_utility_clear_preserves_null_metadata_kind(env, kind):
    """Clearing with no target is a no-change; it never coerces null to {}."""
    goal_id = _NULLABLE_GOALS[kind]
    response = env.client(env.actors["lead-1"]).delete(
        f"/api/goals/{goal_id}/utility?operation_id=nullable-clear-{kind}")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["verification"]["status"] == "no_change"
    assert body["verification"]["effect"] == "none"
    assert body["utility_target"] is None
    assert _physical_metadata(env, goal_id)[0] == kind
    assert _audits(env) == []


# ------------------------------------------------------- idempotent replay

def test_utility_set_replay_same_and_changed_material(env):
    client = env.client(env.actors["lead-1"])
    first = client.put(
        "/api/goals/goal-1/utility?operation_id=replay-util",
        json={"metric": "steps_executed", "direction": "maximize",
              "source": "goal_run"})
    assert first.status_code == 200, first.text
    assert first.json()["verification"]["status"] == "verified"

    replay = client.put(
        "/api/goals/goal-1/utility?operation_id=replay-util",
        json={"metric": "steps_executed", "direction": "maximize",
              "source": "goal_run"})
    assert replay.status_code == 200, replay.text
    assert replay.json()["verification"]["status"] == "already_applied"
    assert replay.json()["verification"]["replay"] == "do_not_repeat"
    assert len(_audits(env)) == 1

    changed = client.put(
        "/api/goals/goal-1/utility?operation_id=replay-util",
        json={"metric": "replan_count", "direction": "minimize",
              "source": "goal_run"})
    assert changed.status_code == 409, changed.text
    assert changed.json()["detail"]["error"]["code"] == "OPERATION_CONFLICT"
    assert _goal(env).metadata_json["utility_target"]["metric"] == (
        "steps_executed")
    assert len(_audits(env)) == 1


def test_utility_clear_replay_same_operation(env):
    client = env.client(env.actors["lead-1"])
    first = client.delete(
        "/api/goals/goal-1/utility?operation_id=replay-clear")
    assert first.status_code == 200, first.text
    replay = client.delete(
        "/api/goals/goal-1/utility?operation_id=replay-clear")
    assert replay.status_code == 200, replay.text
    assert replay.json()["verification"]["status"] == "already_applied"
    assert len(_audits(env)) == 1


def test_create_replay_same_and_changed_material(env):
    client = env.client(env.actors["member-1"])
    first = client.post(
        "/api/goals?operation_id=replay-create",
        json={"title": "Replay goal", "description": "first"})
    assert first.status_code == 200, first.text
    goal_id = first.json()["goal"]["id"]

    replay = client.post(
        "/api/goals?operation_id=replay-create",
        json={"title": "Replay goal", "description": "first"})
    assert replay.status_code == 200, replay.text
    assert replay.json()["verification"]["status"] == "already_applied"
    assert replay.json()["goal"]["id"] == goal_id
    assert len(_goal_titled(env, "Replay goal")) == 1
    assert len(_audits(env)) == 1

    changed = client.post(
        "/api/goals?operation_id=replay-create",
        json={"title": "Replay goal", "description": "different"})
    assert changed.status_code == 409, changed.text
    assert changed.json()["detail"]["error"]["code"] == "OPERATION_CONFLICT"
    assert len(_goal_titled(env, "Replay goal")) == 1
    assert len(_audits(env)) == 1


def test_receipt_and_target_read_back_after_fresh_engine(env):
    client = env.client(env.actors["lead-1"])
    response = client.put(
        "/api/goals/goal-1/utility?operation_id=restart-receipt",
        json={"metric": "human_interventions", "direction": "minimize",
              "source": "goal_run"})
    assert response.status_code == 200, response.text

    # A new engine/sessionmaker over the same file is the restart readback.
    fresh_engine = create_engine(
        f"sqlite:///{env.db_path}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    Fresh = sessionmaker(bind=fresh_engine, expire_on_commit=False)
    fresh = Fresh()
    try:
        goal = fresh.query(GoalObjective).filter(
            GoalObjective.id == "goal-1").one()
        assert goal.metadata_json["utility_target"]["metric"] == (
            "human_interventions")
        receipt = fresh.query(AuditLog).filter(
            AuditLog.id == "goal:utility:set:restart-receipt").one()
        assert receipt.success is True
        assert receipt.action == "goal_utility_set"
        metadata = json.loads(receipt.metadata_json)
        assert metadata["result_digest"]
        assert metadata["actor_id"] == "lead-1"
        assert "human_interventions" not in receipt.metadata_json
    finally:
        fresh.close()
        fresh_engine.dispose()

    # Fresh app over the fresh engine: the public readback agrees.
    fresh_app = FastAPI()
    fresh_app.include_router(goal_router)

    def fresh_db():
        db = Fresh()
        try:
            yield db
        finally:
            db.close()

    fresh_app.dependency_overrides[get_db] = fresh_db
    fresh_app.dependency_overrides[get_current_user] = (
        lambda: env.actors["viewer-1"])
    fresh_client = TestClient(fresh_app, raise_server_exceptions=False)
    readback = fresh_client.get("/api/goals/goal-1/utility")
    assert readback.status_code == 200, readback.text
    assert readback.json()["target"]["metric"] == "human_interventions"
