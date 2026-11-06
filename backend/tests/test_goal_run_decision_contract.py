"""Failure-first contracts for verified goal-run mode/cancel decisions."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, update
from sqlalchemy.orm import sessionmaker

import core.goal_run_decision_service as service
from api.goal_run_routes import router as goal_router
from core.auth import get_current_user
from core.database import Base, get_db
from core.models import (
    AuditLog,
    GoalObjective,
    GoalRun,
    Tenant,
    User,
    Workspace,
)


@pytest.fixture()
def env(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path}/goal-decision.db",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
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
            id="member-1", tenant_id="default", workspace_id="ws-test",
            email="member@example.com", first_name="Member", last_name="One",
            role="member", status="active", is_active=True),
        User(
            id="member-2", tenant_id="default", workspace_id="ws-test",
            email="member2@example.com", first_name="Member", last_name="Two",
            role="member", status="active", is_active=True),
        User(
            id="lead-other", tenant_id="default", workspace_id="ws-other",
            email="other@example.com", first_name="Other", last_name="Lead",
            role="team_lead", status="active", is_active=True),
    ]
    goal = GoalObjective(
        id="goal-1", workspace_id="ws-test", tenant_id="default",
        title="Prepare a quote", status="active")
    runs = [
        GoalRun(
            id="run-1", tenant_id="default", workspace_id="ws-test",
            goal_id="goal-1", created_by="lead-1", status="active",
            supervision_mode="shadow", material_revision=3,
            decision_log=[], plan=[]),
        GoalRun(
            id="run-owner", tenant_id="default", workspace_id="ws-test",
            goal_id="goal-1", created_by="member-1", status="active",
            supervision_mode="shadow", material_revision=1,
            decision_log=[], plan=[]),
        GoalRun(
            id="run-cancelled", tenant_id="default", workspace_id="ws-test",
            goal_id="goal-1", created_by="lead-1", status="cancelled",
            supervision_mode="shadow", material_revision=1,
            decision_log=[], plan=[]),
        GoalRun(
            id="run-other", tenant_id="default", workspace_id="ws-other",
            goal_id="goal-1", created_by="lead-other", status="active",
            supervision_mode="shadow", material_revision=1,
            decision_log=[], plan=[]),
    ]
    seed.add_all(users + [goal] + runs)
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
        scoped = FastAPI()
        scoped.include_router(goal_router)
        scoped.dependency_overrides[get_db] = db_override
        scoped.dependency_overrides[get_current_user] = lambda: user
        return TestClient(scoped, raise_server_exceptions=False)

    actors = {
        "lead-1": Session().query(User).filter(User.id == "lead-1").one(),
        "member-1": Session().query(User).filter(User.id == "member-1").one(),
        "member-2": Session().query(User).filter(User.id == "member-2").one(),
        "lead-other": Session().query(User).filter(
            User.id == "lead-other").one(),
    }
    yield SimpleNamespace(
        engine=engine, Session=Session, app=app, client=client,
        actors=actors,
    )


def _run(env, run_id):
    db = env.Session()
    try:
        return db.query(GoalRun).filter(GoalRun.id == run_id).first()
    finally:
        db.close()


def _audits(env, operation_id=None):
    db = env.Session()
    try:
        query = db.query(AuditLog)
        if operation_id is not None:
            query = query.filter(AuditLog.id == operation_id)
        return query.all()
    finally:
        db.close()


def _peer_bump(env, run_id, **values):
    db = env.Session()
    try:
        row = db.query(GoalRun).filter(GoalRun.id == run_id).one()
        values.setdefault(
            "material_revision", int(row.material_revision or 0) + 1)
        db.execute(update(GoalRun).where(
            GoalRun.id == run_id).values(**values))
        db.commit()
    finally:
        db.close()


def test_supervisor_mode_change_audits_and_bumps_revision(env):
    response = env.client(env.actors["lead-1"]).post(
        "/api/goal-runs/run-1/mode?operation_id=mode-one",
        json={"supervision_mode": "training"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["run"]["supervision_mode"] == "training"
    assert body["run"]["material_revision"] == 4
    assert body["verification"]["status"] == "verified"
    assert body["operation_id"] == "goal-run:mode:mode-one"

    audits = _audits(env, "goal-run:mode:mode-one")
    assert len(audits) == 1
    audit = audits[0]
    assert audit.action == "goal_run_mode_changed"
    assert audit.user_id == "lead-1"
    assert audit.workspace_id == "ws-test"
    metadata = json.loads(audit.metadata_json)
    assert metadata["target_id"] == "run-1"
    assert metadata["prior_mode"] == "shadow"
    assert metadata["result_mode"] == "training"
    assert metadata["prior_revision"] == 3
    assert metadata["result_revision"] == 4
    assert "plan" not in audit.metadata_json
    assert "parameters" not in audit.metadata_json


def test_member_mode_change_refused_and_cross_workspace_404(env):
    member = env.client(env.actors["member-1"])
    assert member.post(
        "/api/goal-runs/run-1/mode",
        json={"supervision_mode": "shadow"}).status_code == 403
    other = env.client(env.actors["lead-other"])
    assert other.post(
        "/api/goal-runs/run-1/mode",
        json={"supervision_mode": "shadow"}).status_code == 404
    assert _run(env, "run-1").supervision_mode == "shadow"


def test_invalid_mode_and_no_change(env):
    client = env.client(env.actors["lead-1"])
    assert client.post(
        "/api/goal-runs/run-1/mode",
        json={"supervision_mode": "solo"}).status_code == 422
    nochange = client.post(
        "/api/goal-runs/run-1/mode",
        json={"supervision_mode": "shadow"})
    assert nochange.status_code == 200, nochange.text
    assert nochange.json()["verification"]["status"] == "no_change"
    assert nochange.json()["verification"]["effect"] == "none"
    assert _audits(env) == []


def test_stale_mode_revision_refuses(env, monkeypatch):
    original = service._load_run
    changed = {"done": False}

    def load_then_bump(db, workspace_id, run_id):
        row = original(db, workspace_id, run_id)
        if not changed["done"] and run_id == "run-1":
            changed["done"] = True
            _peer_bump(env, run_id, supervision_mode="autonomous")
        return row

    monkeypatch.setattr(service, "_load_run", load_then_bump)
    response = env.client(env.actors["lead-1"]).post(
        "/api/goal-runs/run-1/mode?operation_id=stale-mode",
        json={"supervision_mode": "training"})
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["error"]["code"] == "STALE_TARGET"
    assert _run(env, "run-1").supervision_mode == "autonomous"
    assert _audits(env) == []


def test_mode_replay_changed_material_and_later_revision(env):
    client = env.client(env.actors["lead-1"])
    first = client.post(
        "/api/goal-runs/run-1/mode?operation_id=replay-mode",
        json={"supervision_mode": "training"})
    assert first.status_code == 200, first.text
    replay = client.post(
        "/api/goal-runs/run-1/mode?operation_id=replay-mode",
        json={"supervision_mode": "training"})
    assert replay.status_code == 200, replay.text
    assert replay.json()["verification"]["status"] == "already_applied"
    assert len(_audits(env)) == 1

    changed = client.post(
        "/api/goal-runs/run-1/mode?operation_id=replay-mode",
        json={"supervision_mode": "autonomous"})
    assert changed.status_code == 409, changed.text
    assert changed.json()["detail"]["error"]["code"] == "OPERATION_CONFLICT"

    _peer_bump(env, "run-1", supervision_mode="shadow")
    later = client.post(
        "/api/goal-runs/run-1/mode?operation_id=replay-mode",
        json={"supervision_mode": "training"})
    assert later.status_code == 503, later.text
    assert later.json()["detail"]["error"]["code"] == (
        "GOAL_RUN_COMMITTED_UNVERIFIED")


def test_owner_member_can_cancel_and_replay(env):
    client = env.client(env.actors["member-1"])
    first = client.post(
        "/api/goal-runs/run-owner/cancel?operation_id=cancel-owner")
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["run"]["status"] == "cancelled"
    assert body["run"]["material_revision"] == 2
    assert body["run"]["waiting_on"] is None
    assert any(entry.get("kind") == "cancelled"
               for entry in body["run"]["decision_log"])

    replay = client.post(
        "/api/goal-runs/run-owner/cancel?operation_id=cancel-owner")
    assert replay.status_code == 200, replay.text
    assert replay.json()["verification"]["status"] == "already_applied"
    assert len(_audits(env)) == 1

    other = env.client(env.actors["member-2"])
    assert other.post(
        "/api/goal-runs/run-1/cancel",
        json={}).status_code == 403
    supervisor = env.client(env.actors["lead-1"])
    assert supervisor.post(
        "/api/goal-runs/run-1/cancel").status_code == 200


def test_cancel_cross_workspace_and_already_terminal(env):
    other = env.client(env.actors["lead-other"])
    assert other.post(
        "/api/goal-runs/run-1/cancel").status_code == 404
    client = env.client(env.actors["lead-1"])
    assert client.post(
        "/api/goal-runs/run-cancelled/cancel").status_code == 409
    assert _run(env, "run-cancelled").status == "cancelled"


def test_stale_cancel_revision_refuses(env, monkeypatch):
    original = service._load_run
    changed = {"done": False}

    def load_then_bump(db, workspace_id, run_id):
        row = original(db, workspace_id, run_id)
        if not changed["done"] and run_id == "run-1":
            changed["done"] = True
            _peer_bump(env, run_id, status="waiting")
        return row

    monkeypatch.setattr(service, "_load_run", load_then_bump)
    response = env.client(env.actors["lead-1"]).post(
        "/api/goal-runs/run-1/cancel?operation_id=stale-cancel")
    assert response.status_code == 409, response.text
    assert _run(env, "run-1").status == "waiting"
    assert _audits(env) == []


@pytest.mark.parametrize("kind", ["mode", "cancel"])
def test_confirmed_audit_rollback_reports_effect_none(env, monkeypatch, kind):
    original = service._audit_row

    def invalid_audit(**kwargs):
        row = original(**kwargs)
        row.action = None
        return row

    monkeypatch.setattr(service, "_audit_row", invalid_audit)
    client = env.client(env.actors["lead-1"])
    if kind == "mode":
        response = client.post(
            "/api/goal-runs/run-1/mode?operation_id=rollback-mode",
            json={"supervision_mode": "training"})
    else:
        response = client.post(
            "/api/goal-runs/run-1/cancel?operation_id=rollback-cancel")
    assert response.status_code == 409, response.text
    detail = response.json()["detail"]
    assert detail["error"]["code"] == "GOAL_RUN_TRANSACTION_ROLLED_BACK"
    assert detail["verification"]["effect"] == "none"
    run = _run(env, "run-1")
    assert run.status == "active" and run.supervision_mode == "shadow"
    assert _audits(env) == []


def test_post_commit_readback_is_committed_unverified(env, monkeypatch):
    def unavailable(_db, expected):
        return {
            "status": "unavailable",
            "audit_id": expected["operation_id"],
        }

    monkeypatch.setattr(service, "_verify_audit", unavailable)
    response = env.client(env.actors["lead-1"]).post(
        "/api/goal-runs/run-1/mode?operation_id=readback",
        json={"supervision_mode": "training"})
    assert response.status_code == 503, response.text
    detail = response.json()["detail"]
    assert detail["error"]["code"] == "GOAL_RUN_COMMITTED_UNVERIFIED"
    assert detail["verification"]["effect"] == "committed"
    assert _run(env, "run-1").supervision_mode == "training"
    assert len(_audits(env, "goal-run:mode:readback")) == 1


def test_lost_confirmation_is_effect_unknown_with_identity(env, caplog):
    db = env.Session()
    try:
        def lost_commit():
            raise RuntimeError("lost confirmation SYNTHETIC-GOAL-SECRET")

        db.commit = lost_commit
        result = service.set_supervision_mode(
            db, actor=env.actors["lead-1"], workspace_id="ws-test",
            run_id="run-1", mode="training",
            operation_id="lost-confirmation")
    finally:
        db.rollback()
        db.close()

    assert result["status"] == "effect_unknown"
    assert result["verification"]["effect"] == "unknown"
    assert result["verification"]["replay"] == "do_not_repeat"
    assert result["operation_id"] == "goal-run:mode:lost-confirmation"
    assert "SYNTHETIC-GOAL-SECRET" not in json.dumps(result)
    assert "SYNTHETIC-GOAL-SECRET" not in caplog.text
    assert _run(env, "run-1").supervision_mode == "shadow"
    assert _audits(env) == []


@pytest.mark.parametrize("field", [
    "action",
    "user_id",
    "workspace_id",
    "success",
    "security_level",
    "resource",
    "metadata_target_id",
    "metadata_target_workspace_id",
    "metadata_prior_mode",
    "metadata_result_mode",
    "metadata_prior_revision",
    "metadata_result_revision",
    "metadata_request_digest",
    "metadata_result_digest",
])
def test_wrong_audit_receipt_is_never_verified(env, monkeypatch, field):
    original = service._audit_row

    def wrong_audit(**kwargs):
        row = original(**kwargs)
        metadata = json.loads(row.metadata_json or "{}")
        if field == "action":
            row.action = "wrong-action"
        elif field == "user_id":
            row.user_id = "member-1"
        elif field == "workspace_id":
            row.workspace_id = "ws-other"
        elif field == "success":
            row.success = False
        elif field == "security_level":
            row.security_level = "low"
        elif field == "resource":
            row.resource = "goal_run:other"
        elif field == "metadata_target_id":
            metadata["target_id"] = "other"
        elif field == "metadata_target_workspace_id":
            metadata["target_workspace_id"] = "ws-other"
        elif field == "metadata_prior_mode":
            metadata["prior_mode"] = "training"
        elif field == "metadata_result_mode":
            metadata["result_mode"] = "autonomous"
        elif field == "metadata_prior_revision":
            metadata["prior_revision"] = 99
        elif field == "metadata_result_revision":
            metadata["result_revision"] = 99
        elif field == "metadata_request_digest":
            metadata["request_digest"] = "wrong-request"
        elif field == "metadata_result_digest":
            metadata["result_digest"] = "wrong-result"
        row.metadata_json = json.dumps(metadata)
        return row

    monkeypatch.setattr(service, "_audit_row", wrong_audit)
    response = env.client(env.actors["lead-1"]).post(
        f"/api/goal-runs/run-1/mode?operation_id=audit-{field}",
        json={"supervision_mode": "training"})
    assert response.status_code == 503, response.text
    detail = response.json()["detail"]
    assert detail["error"]["code"] == "GOAL_RUN_COMMITTED_UNVERIFIED"
    assert detail["verification"]["status"] in ("refuted", "unavailable")
    assert detail["verification"]["effect"] == "committed"


def test_authority_change_before_claim_refuses(env, monkeypatch):
    original = service._load_run
    changed = {"done": False}

    def load_then_change(db, workspace_id, run_id):
        row = original(db, workspace_id, run_id)
        if not changed["done"] and run_id == "run-1":
            changed["done"] = True
            peer = env.Session()
            try:
                peer.execute(update(User).where(
                    User.id == "lead-1").values(
                        status="inactive", is_active=False))
                peer.commit()
            finally:
                peer.close()
        return row

    monkeypatch.setattr(service, "_load_run", load_then_change)
    response = env.client(env.actors["lead-1"]).post(
        "/api/goal-runs/run-1/mode?operation_id=authority",
        json={"supervision_mode": "training"})
    assert response.status_code in (403, 409), response.text
    assert response.json()["detail"]["verification"]["effect"] == "none"
    assert _run(env, "run-1").supervision_mode == "shadow"
    assert _audits(env) == []
