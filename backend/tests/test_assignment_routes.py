"""Public assignment-route approval authority controls.

These exercise the real FastAPI assignment routes with a scratch database,
not the executor helper directly.
"""
from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("TESTING", "1")

from core.assignment_executor import AssignmentExecutor, default_adapter_registry
from core.assignment_plan import new_assignment, new_step, new_teaching_snapshot
from core.auth import get_current_user
from core.base_routes import BaseAPIRouter
from core.database import get_db
from core.goals.goal_run_service import GoalRunService
from core.goals.goal_service import GoalService
from core.models import Base, HITLAction, HITLActionStatus, User
from core.task_lifecycle import TaskLifecycle


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture()
def route_env(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path}/routes.db")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    db = factory()
    users = {
        "member": User(
            id="member-1", email="member@example.com", hashed_password="x",
            first_name="M", last_name="One", role="member", status="active",
            workspace_id="ws-1", tenant_id="tenant-1", is_active=True),
        "lead": User(
            id="lead-1", email="lead@example.com", hashed_password="x",
            first_name="L", last_name="One", role="team_lead",
            status="active", workspace_id="ws-1", tenant_id="tenant-1",
            is_active=True),
        "other": User(
            id="lead-2", email="other@example.com", hashed_password="x",
            first_name="O", last_name="Two", role="team_lead",
            status="active", workspace_id="ws-2", tenant_id="tenant-2",
            is_active=True),
    }
    for user in users.values():
        db.add(user)
    db.commit()

    runs = GoalRunService(
        workspace_id="ws-1", tenant_id="tenant-1",
        session_factory=factory)
    goals = GoalService(
        workspace_id="ws-1", tenant_id="tenant-1",
        session_factory=factory)
    lifecycle = TaskLifecycle(runs, goals)
    registry = default_adapter_registry.clone()
    executor = AssignmentExecutor(lifecycle, adapters=registry)

    # Route-created services use the application session factory.
    monkeypatch.setattr("core.database.get_db_session", factory)

    async def fake_request_intervention(**kwargs):
        action = HITLAction(
            id=f"hitl-{uuid.uuid4().hex[:8]}",
            workspace_id=kwargs.get("workspace_id"),
            tenant_id=kwargs.get("tenant_id"),
            action_type=kwargs.get("action_type"),
            platform=kwargs.get("platform"),
            params=kwargs.get("params") or {},
            reason=kwargs.get("reason"),
            status=HITLActionStatus.PENDING.value,
            user_id=kwargs.get("user_id"),
        )
        db.add(action)
        db.commit()
        db.refresh(action)
        return {"status": "PAUSED", "action_id": action.id}

    monkeypatch.setattr(
        "core.intervention_service.intervention_service.request_intervention",
        fake_request_intervention)

    from api.assignment_routes import router

    app = FastAPI()
    app.include_router(router)
    current = {"user": users["lead"]}
    app.dependency_overrides[get_current_user] = lambda: current["user"]
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)

    calls = {"send": 0}

    async def send(inputs, context):
        calls["send"] += 1
        return {
            "status": "applied", "summary": "route provider accepted",
            "provider_state": "sent", "provider_ref": "provider-1",
        }

    def prepare(inputs, context):
        return {
            "payload": {
                "to": inputs.get("to"),
                "subject": inputs.get("subject"),
                "body": inputs.get("body"),
            },
            "artifact_revision": inputs.get("draft_revision"),
            "requested_by": "owner-1",
        }

    registry.register("test.route.send", send, prepare=prepare)
    default_adapter_registry.register(
        "test.route.send", send, prepare=prepare)

    yield {
        "db": db,
        "factory": factory,
        "users": users,
        "current": current,
        "client": client,
        "runs": runs,
        "lifecycle": lifecycle,
        "executor": executor,
        "calls": calls,
    }
    db.close()


def _awaiting_assignment(env):
    plan = new_assignment(
        objective="Route approval",
        employee_id="owner-1",
        workspace_id="ws-1",
        tenant_id="tenant-1",
        teaching_snapshot=new_teaching_snapshot(revision="route-r1"),
        steps=[new_step(
            step_id="send", title="Send the prepared effect",
            operation_type="outbound", adapter="test.route.send",
            inputs={"to": ["test@example.invalid"], "subject": "S",
                    "body": "B", "draft_revision": "draft-r1"},
            effect="external", approval_required=True,
            approval_purpose="Send the route-controlled effect")],
    )
    record = env["executor"].create_assignment(
        "conv-route", "Route approval", assignment=plan)
    _run(env["executor"].execute(record["run_id"]))
    action = env["db"].query(HITLAction).filter(
        HITLAction.action_type == "assignment_approval").order_by(
            HITLAction.created_at.desc()).first()
    return record["run_id"], action.id


def test_authorized_team_lead_approves_once(route_env):
    run_id, action_id = _awaiting_assignment(route_env)
    response = route_env["client"].post(
        f"/api/assignments/{run_id}/approve/send", json={"note": "ok"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "approved"
    assert body["assignment"]["assignment"]["status"] == "completed"
    assert route_env["calls"]["send"] == 1
    route_env["db"].refresh(route_env["db"].query(HITLAction).filter(
        HITLAction.id == action_id).first())
    assert route_env["db"].query(HITLAction).filter(
        HITLAction.id == action_id).first().status == (
            HITLActionStatus.APPROVED.value)

    # A duplicate decision cannot run the effect twice.
    again = route_env["client"].post(
        f"/api/assignments/{run_id}/approve/send", json={})
    assert again.status_code in (404, 409)
    assert route_env["calls"]["send"] == 1


def test_same_workspace_member_cannot_approve(route_env):
    run_id, _ = _awaiting_assignment(route_env)
    route_env["current"]["user"] = route_env["users"]["member"]
    response = route_env["client"].post(
        f"/api/assignments/{run_id}/approve/send", json={})
    assert response.status_code == 403
    assert route_env["calls"]["send"] == 0


def test_wrong_workspace_approver_is_refused(route_env):
    run_id, _ = _awaiting_assignment(route_env)
    route_env["current"]["user"] = route_env["users"]["other"]
    response = route_env["client"].post(
        f"/api/assignments/{run_id}/approve/send", json={})
    assert response.status_code == 404
    assert route_env["calls"]["send"] == 0


def test_changed_payload_is_not_approved_under_old_request(route_env):
    run_id, _ = _awaiting_assignment(route_env)

    def compute(record, assignment):
        step = next(item for item in assignment["steps"]
                    if item["step_id"] == "send")
        step["inputs"]["body"] = "Changed after request"
        return assignment, {}

    route_env["lifecycle"].mutate_assignment(
        run_id, compute, rationale="changed payload")
    response = route_env["client"].post(
        f"/api/assignments/{run_id}/approve/send", json={})
    assert response.status_code == 409
    assert route_env["calls"]["send"] == 0


def test_cancelled_assignment_cannot_be_approved(route_env):
    run_id, _ = _awaiting_assignment(route_env)
    route_env["executor"].cancel(
        run_id, reason="cancelled", cancelled_by="owner-1")
    response = route_env["client"].post(
        f"/api/assignments/{run_id}/approve/send", json={})
    assert response.status_code == 409
    assert route_env["calls"]["send"] == 0
