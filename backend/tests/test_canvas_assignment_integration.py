"""Typed canvas receipt -> assignment -> guarded registered action -> teaching.

The canvas is the authoring surface; the assignment executor remains the only
job engine. These controls use a scratch SQLite store and a fake Outlook
service behind the production registered action.
"""
from __future__ import annotations

import asyncio
import json
import uuid
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.assignment_executor import AssignmentExecutor
from core.auth import get_current_user
from core.canvas_capability_service import (
    bind_dataset,
    current_revision,
    edit_operation,
    get_manifest,
    set_manifest,
)
from core.database import Base, get_db
from core.deployment_audience import require_pilot_user
from core.goals.goal_run_service import GoalRunService
from core.goals.goal_service import GoalService
from core.models import (
    AgentRegistry,
    Canvas,
    HITLAction,
    HITLActionStatus,
    User,
)
from core.task_lifecycle import TaskLifecycle


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("TESTING", "1")
    monkeypatch.setenv(
        "ATOM_ASSIGNMENT_OUTBOX", str(tmp_path / "outbox.jsonl"))
    monkeypatch.setenv("ATOM_OFFICE_DIR", str(tmp_path))
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    db = factory()
    user = User(
        id="canvas-user", email="canvas@example.invalid",
        hashed_password="x", first_name="C", last_name="U",
        role="workspace_admin", status="active",
        workspace_id="ws-canvas", tenant_id="tenant-canvas",
        is_active=True,
    )
    db.add(user)
    agent = AgentRegistry(
        id="canvas-agent", name="Canvas Employee", category="operations",
        module_path="core.generic_agent", class_name="GenericAgent",
        status="intern", confidence_score=0.5, configuration={},
        capabilities=[], workspace_id="ws-canvas",
        tenant_id="tenant-canvas",
    )
    db.add(agent)
    db.commit()
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
    drafts = []

    class FakeOutlook:
        async def _get_access_token(self, user_id):
            return "controlled-token"

        async def create_draft_email(self, **kwargs):
            drafts.append(dict(kwargs))
            return {
                "id": f"draft-{len(drafts)}",
                "subject": kwargs.get("subject"),
                "body": kwargs.get("body"),
                "to": kwargs.get("to_recipients"),
            }

    monkeypatch.setattr(
        "integrations.outlook_service.OutlookService",
        lambda *args, **kwargs: FakeOutlook())
    import core.connected_actions  # noqa: F401 - registers connected actions

    from api.canvas_capability_routes import router

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[require_pilot_user] = lambda: user
    client = TestClient(app)
    try:
        yield {
            "db": db, "factory": factory, "user": user, "client": client,
            "drafts": drafts, "agent_id": agent.id,
        }
    finally:
        db.close()
        engine.dispose()


def _manifest(actions=True):
    manifest = {
        "schema_version": 2,
        "base_component": "table",
        "operations": ["read", "derive", "edit", "bind"],
        "data_binding": {"subject_field": "Item"},
        "teaching_binding": {"agent_id": "canvas-agent",
                             "scope_id": "canvas-task"},
        "fields": [
            {"id": "item_id", "label": "Item", "type": "string",
             "column": "Item", "required": True},
            {"id": "quantity", "label": "Quantity", "type": "decimal",
             "column": "Qty", "unit": "each", "required": True,
             "editable": True},
            {"id": "unit_price", "label": "Unit price", "type": "currency",
             "column": "Price", "currency": "USD", "required": True,
             "editable": True},
            {"id": "line_total", "label": "Line total", "type": "currency",
             "column": "Line Total", "currency": "USD",
             "derived": "quantity * unit_price", "aggregate": "sum",
             "group_by": "item_id"},
        ],
        "outputs": ["xlsx"],
    }
    if actions:
        manifest["actions"] = [{
            "id": "notify",
            "operation": "connected.outlook.create_draft",
            "allowed_fields": [
                "item_id", "quantity", "unit_price", "line_total"],
            "target": "buyer@example.invalid",
            "authority": "grant-canvas-draft-1",
            "arguments": {
                "to": ["buyer@example.invalid"],
                "subject": "Canvas quote ${objective}",
                "body": "Total ${total} ${currency} (${row_count} rows)",
                "authority_reference": "grant-canvas-draft-1",
                "operation_id": "canvas-${receipt_digest}",
            },
        }]
    return manifest


def _canvas(env, *, canvas_id="canvas_assignment", actions=True):
    db = env["db"]
    canvas = Canvas(
        id=canvas_id, tenant_id=env["user"].tenant_id,
        workspace_id=env["user"].workspace_id,
        created_by=env["user"].id, name="Assignment canvas",
        canvas_type="table", content={}, status="active",
    )
    db.add(canvas)
    db.commit()
    set_manifest(db, canvas, env["user"], _manifest(actions=actions))
    bound = bind_dataset(
        db, canvas, env["user"], ["Item", "Qty", "Price"],
        [["A", "2", "100.00"], ["B", "3", "50.00"]],
        source={"file_name": "canvas-assignment.csv"},
    )
    return canvas, bound


def _assign(env, canvas, bound):
    response = env["client"].post(
        f"/api/canvas/{canvas.id}/capability/assign",
        json={
            "objective": "Quote assignment",
            "agent_id": env["agent_id"],
            "expected_revision": bound["revision"],
            "manifest_revision": bound["manifest"]["manifest_revision"],
            "source_version": bound["source"]["source_version"],
            "action_ids": ["notify"],
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def _executor(env):
    runs = GoalRunService(
        workspace_id=env["user"].workspace_id,
        tenant_id=env["user"].tenant_id,
        session_factory=env["factory"],
    )
    goals = GoalService(
        workspace_id=env["user"].workspace_id,
        tenant_id=env["user"].tenant_id,
        session_factory=env["factory"],
    )
    return AssignmentExecutor(TaskLifecycle(runs, goals))


def _step(assignment, step_id):
    data = (
        assignment.get("assignment")
        if isinstance(assignment, dict)
        and isinstance(assignment.get("assignment"), dict)
        else assignment
    )
    return next(
        item for item in data["steps"]
        if item["step_id"] == step_id)


def test_receipt_assignment_executes_one_approved_draft(env):
    canvas, bound = _canvas(env)
    created = _assign(env, canvas, bound)
    assert created["receipt_digest"]
    assignment = created["assignment"]
    assert _step(assignment, "receipt")["status"] == "applied"
    assert _step(assignment, "guard-notify")["status"] == "applied"
    action = _step(assignment, "action-notify")
    assert action["status"] == "awaiting_approval"
    assert env["drafts"] == []

    executor = _executor(env)
    executor.approve_step(
        created["run_id"], "action-notify",
        approved_by=env["user"].id, note="approved canvas action")
    final = asyncio.run(executor.execute(created["run_id"]))["assignment"]
    assert final["status"] == "completed", final
    assert _step(final, "action-notify")["status"] == "applied"
    assert len(env["drafts"]) == 1
    assert "350.00 USD" in env["drafts"][0]["body"]
    assert env["drafts"][0]["subject"] == "Canvas quote Quote assignment"

    # Duplicate continuation and a fresh executor must not dispatch again.
    asyncio.run(executor.execute(created["run_id"]))
    AssignmentExecutor(
        TaskLifecycle(
            GoalRunService(
                workspace_id=env["user"].workspace_id,
                tenant_id=env["user"].tenant_id,
                session_factory=env["factory"],
            ),
            GoalService(
                workspace_id=env["user"].workspace_id,
                tenant_id=env["user"].tenant_id,
                session_factory=env["factory"],
            ),
        )
    ).approve_step(
        created["run_id"], "action-notify",
        approved_by=env["user"].id, note="duplicate approval")
    assert len(env["drafts"]) == 1


def test_canvas_edit_during_approval_blocks_action(env):
    canvas, bound = _canvas(env, canvas_id="canvas_corrected")
    created = _assign(env, canvas, bound)
    edit_operation(
        env["db"], canvas, env["user"],
        [{"row": 2, "column": "Price", "value": "110.00"}],
        expected_revision=bound["revision"],
    )
    executor = _executor(env)
    executor.approve_step(
        created["run_id"], "action-notify",
        approved_by=env["user"].id, note="approve stale action")
    final = asyncio.run(executor.execute(created["run_id"]))["assignment"]
    action = _step(final, "action-notify")
    assert action["status"] == "failed", action
    assert "canvas revision changed" in str(action)
    assert env["drafts"] == []


def test_action_revocation_during_approval_blocks_dispatch(env):
    canvas, bound = _canvas(env, canvas_id="canvas_revoked")
    created = _assign(env, canvas, bound)
    set_manifest(
        env["db"], canvas, env["user"], _manifest(actions=False))
    executor = _executor(env)
    executor.approve_step(
        created["run_id"], "action-notify",
        approved_by=env["user"].id, note="approve revoked action")
    final = asyncio.run(executor.execute(created["run_id"]))["assignment"]
    action = _step(final, "action-notify")
    assert action["status"] == "failed", action
    assert "canvas manifest changed" in str(action)
    assert env["drafts"] == []


def test_foreign_or_moved_employee_cannot_receive_canvas_teaching(env):
    from core.student_learning_service import list_agent_lessons

    foreign = AgentRegistry(
        id="foreign-agent", name="Foreign", category="operations",
        module_path="core.generic_agent", class_name="GenericAgent",
        status="intern", confidence_score=0.5, configuration={},
        capabilities=[], workspace_id="foreign-ws",
        tenant_id="foreign-tenant",
    )
    env["db"].add(foreign)
    env["db"].commit()
    canvas, bound = _canvas(env, canvas_id="canvas_foreign")
    proposal = env["client"].post(
        f"/api/canvas/{canvas.id}/capability/teaching/propose",
        json={
            "lesson": "Foreign lesson",
            "agent_id": "foreign-agent",
            "expected_revision": bound["revision"],
            "manifest_revision": bound["manifest"]["manifest_revision"],
            "source_version": bound["source"]["source_version"],
        })
    assert proposal.status_code in (403, 404), proposal.text
    assert list_agent_lessons(env["db"], "foreign-agent") == []

    owned = env["client"].post(
        f"/api/canvas/{canvas.id}/capability/teaching/propose",
        json={
            "lesson": "Moved target lesson",
            "agent_id": env["agent_id"],
            "expected_revision": bound["revision"],
            "manifest_revision": bound["manifest"]["manifest_revision"],
            "source_version": bound["source"]["source_version"],
        })
    assert owned.status_code == 200, owned.text
    proposal_id = owned.json()["proposal"]["id"]
    agent = env["db"].query(AgentRegistry).filter(
        AgentRegistry.id == env["agent_id"]).one()
    agent.workspace_id = "foreign-ws"
    agent.tenant_id = "foreign-tenant"
    env["db"].commit()
    promoted = env["client"].post(
        f"/api/canvas/{canvas.id}/capability/teaching/{proposal_id}/promote",
        json={
            "approved": True,
            "expected_revision": bound["revision"],
            "manifest_revision": bound["manifest"]["manifest_revision"],
            "source_version": bound["source"]["source_version"],
        })
    assert promoted.status_code in (403, 404), promoted.text
    lessons = list_agent_lessons(env["db"], env["agent_id"])
    assert not any("Moved target lesson" in json.dumps(item)
                   for item in lessons)


def test_non_supervisor_and_journal_failure_do_not_promote(env, monkeypatch):
    from core.student_learning_service import list_agent_lessons

    canvas, bound = _canvas(env, canvas_id="canvas_role")
    proposal = env["client"].post(
        f"/api/canvas/{canvas.id}/capability/teaching/propose",
        json={
            "lesson": "Role-gated lesson",
            "agent_id": env["agent_id"],
            "expected_revision": bound["revision"],
            "manifest_revision": bound["manifest"]["manifest_revision"],
            "source_version": bound["source"]["source_version"],
        }).json()["proposal"]
    original_role = env["user"].role
    env["user"].role = "member"
    try:
        refused = env["client"].post(
            f"/api/canvas/{canvas.id}/capability/teaching/"
            f"{proposal['id']}/promote",
            json={
                "approved": True,
                "expected_revision": bound["revision"],
                "manifest_revision": bound["manifest"]["manifest_revision"],
                "source_version": bound["source"]["source_version"],
            })
        assert refused.status_code == 403, refused.text
    finally:
        env["user"].role = original_role
    assert not any("Role-gated lesson" in json.dumps(item)
                   for item in list_agent_lessons(env["db"], env["agent_id"]))

    def failed_journal(*args, **kwargs):
        return {"status": "journal_failed", "entry": None}

    monkeypatch.setattr(
        "core.student_learning_service.deliver_teacher_lesson",
        failed_journal)
    failed = env["client"].post(
        f"/api/canvas/{canvas.id}/capability/teaching/{proposal['id']}/promote",
        json={
            "approved": True,
            "expected_revision": bound["revision"],
            "manifest_revision": bound["manifest"]["manifest_revision"],
            "source_version": bound["source"]["source_version"],
        })
    assert failed.status_code == 409, failed.text
    durable = env["db"].query(Canvas).filter(
        Canvas.id == canvas.id).one()
    stored = next(
        item for item in durable.content[
            "capability_teaching_proposals"]
        if item["id"] == proposal["id"])
    assert stored["status"] == "proposed"


def test_promoted_global_lesson_is_consumed_with_full_provenance(env):
    from core.student_learning_service import get_agent_lessons

    canvas, bound = _canvas(env, canvas_id="canvas_global")
    receipt = env["client"].post(
        f"/api/canvas/{canvas.id}/capability/derive",
        json={
            "expected_revision": bound["revision"],
            "manifest_revision": bound["manifest"]["manifest_revision"],
            "source_version": bound["source"]["source_version"],
        }).json()
    proposal = env["client"].post(
        f"/api/canvas/{canvas.id}/capability/teaching/propose",
        json={
            "lesson": "Global provenance lesson",
            "agent_id": env["agent_id"],
            "expected_revision": bound["revision"],
            "manifest_revision": bound["manifest"]["manifest_revision"],
            "source_version": bound["source"]["source_version"],
        }).json()["proposal"]
    promoted = env["client"].post(
        f"/api/canvas/{canvas.id}/capability/teaching/"
        f"{proposal['id']}/promote",
        json={
            "approved": True,
            "expected_revision": bound["revision"],
            "manifest_revision": bound["manifest"]["manifest_revision"],
            "source_version": bound["source"]["source_version"],
        })
    assert promoted.status_code == 200, promoted.text
    lessons = get_agent_lessons(
        env["db"], env["agent_id"],
        workspace_id=env["user"].workspace_id, task_context={})
    matching = [
        item for item in lessons
        if "Global provenance lesson" in json.dumps(item)
    ]
    assert matching, lessons
    provenance = matching[0].get("provenance") or {}
    assert provenance.get("receipt_digest") == (
        receipt["input_receipt"]["digest"])
    assert provenance.get("manifest_revision") == (
        bound["manifest"]["manifest_revision"])
    assert isinstance(provenance.get("source"), dict)


def test_foreign_employee_cannot_start_canvas_assignment(env):
    foreign = AgentRegistry(
        id="foreign-assign-agent", name="Foreign Assign",
        category="operations", module_path="core.generic_agent",
        class_name="GenericAgent", status="intern",
        confidence_score=0.5, configuration={}, capabilities=[],
        workspace_id="foreign-ws", tenant_id="foreign-tenant",
    )
    env["db"].add(foreign)
    env["db"].commit()
    canvas, bound = _canvas(env, canvas_id="canvas_foreign_assign")
    response = env["client"].post(
        f"/api/canvas/{canvas.id}/capability/assign",
        json={
            "objective": "Foreign assignment",
            "agent_id": "foreign-assign-agent",
            "expected_revision": bound["revision"],
            "manifest_revision": bound["manifest"]["manifest_revision"],
            "source_version": bound["source"]["source_version"],
            "action_ids": ["notify"],
        })
    assert response.status_code in (403, 404), response.text


def test_canvas_consumers_reject_a_foreign_assignment_principal(env):
    from core.canvas_assignment import _canvas_receipt

    canvas, bound = _canvas(env, canvas_id="canvas_foreign_principal")
    receipt = env["client"].post(
        f"/api/canvas/{canvas.id}/capability/derive",
        json={
            "expected_revision": bound["revision"],
            "manifest_revision": bound["manifest"]["manifest_revision"],
            "source_version": bound["source"]["source_version"],
        }).json()
    failed = asyncio.run(_canvas_receipt(
        {
            "canvas_id": canvas.id,
            "receipt": receipt["input_receipt"],
            "expected_revision": bound["revision"],
            "manifest_revision": bound["manifest"]["manifest_revision"],
            "source_version": bound["source"]["source_version"],
        },
        {
            "workspace_id": "foreign-ws",
            "tenant_id": "foreign-tenant",
            "provenance": {"requester_id": "foreign-user"},
        },
    ))
    assert failed["status"] == "failed"
    assert (
        "refused" in failed["message"].lower()
        or "different tenant" in failed["message"].lower()
    )


def test_teaching_proposal_requires_explicit_promotion(env):
    from core.student_learning_service import list_agent_lessons

    canvas, bound = _canvas(env, canvas_id="canvas_teaching")
    receipt = env["client"].post(
        f"/api/canvas/{canvas.id}/capability/derive",
        json={
            "expected_revision": bound["revision"],
            "manifest_revision": bound["manifest"]["manifest_revision"],
            "source_version": bound["source"]["source_version"],
        }).json()
    stale_receipt = env["client"].post(
        f"/api/canvas/{canvas.id}/capability/teaching/propose",
        json={
            "lesson": "This proposal is bound to a different receipt",
            "agent_id": env["agent_id"],
            "receipt_digest": "0" * 64,
            "expected_revision": bound["revision"],
            "manifest_revision": bound["manifest"]["manifest_revision"],
            "source_version": bound["source"]["source_version"],
        })
    assert stale_receipt.status_code == 409, stale_receipt.text
    proposal_response = env["client"].post(
        f"/api/canvas/{canvas.id}/capability/teaching/propose",
        json={
            "lesson": "Use the customer agreement's currency for all quote lines",
            "topic": "quote currency",
            "applies_to": ["quote"],
            "format_spec": {"rounding": "half_up"},
            "context": {"audience": "quote-reviewer"},
            "agent_id": env["agent_id"],
            "receipt_digest": receipt["input_receipt"]["digest"],
            "expected_revision": bound["revision"],
            "manifest_revision": bound["manifest"]["manifest_revision"],
            "source_version": bound["source"]["source_version"],
        },
    )
    assert proposal_response.status_code == 200, proposal_response.text
    proposal = proposal_response.json()["proposal"]
    assert proposal["status"] == "proposed"
    assert list_agent_lessons(env["db"], env["agent_id"]) == []

    no_approval = env["client"].post(
        f"/api/canvas/{canvas.id}/capability/teaching/"
        f"{proposal['id']}/promote",
        json={
            "approved": False,
            "expected_revision": bound["revision"],
            "manifest_revision": bound["manifest"]["manifest_revision"],
            "source_version": bound["source"]["source_version"],
        })
    assert no_approval.status_code == 403, no_approval.text

    promoted = env["client"].post(
        f"/api/canvas/{canvas.id}/capability/teaching/"
        f"{proposal['id']}/promote",
        json={
            "approved": True,
            "reason": "owner reviewed the receipt and lesson",
            "expected_revision": bound["revision"],
            "manifest_revision": bound["manifest"]["manifest_revision"],
            "source_version": bound["source"]["source_version"],
        })
    assert promoted.status_code == 200, promoted.text
    assert promoted.json()["status"] == "promoted"
    lessons = list_agent_lessons(env["db"], env["agent_id"])
    assert (
        "Use the customer agreement's currency for all quote lines"
        in json.dumps(lessons))
    duplicate = env["client"].post(
        f"/api/canvas/{canvas.id}/capability/teaching/"
        f"{proposal['id']}/promote",
        json={
            "approved": True,
            "expected_revision": bound["revision"],
            "manifest_revision": bound["manifest"]["manifest_revision"],
            "source_version": bound["source"]["source_version"],
        })
    assert duplicate.status_code == 200, duplicate.text
    assert duplicate.json()["status"] == "already_promoted"
    lessons_after = list_agent_lessons(env["db"], env["agent_id"])
    assert sum(
        1 for item in lessons_after
        if "Use the customer agreement's currency for all quote lines"
        in json.dumps(item)
    ) == 1


def test_forged_self_consistent_receipt_is_not_accepted(env):
    """A client can recompute a digest but cannot mint the server receipt."""
    from core.canvas_assignment import _canvas_receipt, _receipt_digest

    canvas, bound = _canvas(env, canvas_id="canvas_forged_receipt")
    derived = env["client"].post(
        f"/api/canvas/{canvas.id}/capability/derive",
        json={
            "expected_revision": bound["revision"],
            "manifest_revision": bound["manifest"]["manifest_revision"],
            "source_version": bound["source"]["source_version"],
        },
    ).json()
    receipt = json.loads(json.dumps(derived["input_receipt"]))
    receipt["rows"][0]["values"]["line_total"] = "9999.00"
    receipt["digest"] = _receipt_digest(receipt)
    result = asyncio.run(_canvas_receipt(
        {
            "canvas_id": canvas.id,
            "receipt": receipt,
            "expected_revision": bound["revision"],
            "manifest_revision": bound["manifest"]["manifest_revision"],
            "source_version": bound["source"]["source_version"],
        },
        {
            "workspace_id": env["user"].workspace_id,
            "tenant_id": env["user"].tenant_id,
            "employee_id": env["agent_id"],
            "provenance": {"requester_id": env["user"].id},
        }))
    assert result["status"] == "failed"
    assert result.get("error_class") == "receipt_not_server_issued"
