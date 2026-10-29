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
import core.assignment_controlled_transport  # noqa: F401,E402
from core.goals.goal_run_service import GoalRunService
from core.goals.goal_service import GoalService
from core.models import Base, HITLAction, HITLActionStatus, User
from core.task_lifecycle import TaskLifecycle


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture()
def route_env(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "ATOM_ASSIGNMENT_OUTBOX", str(tmp_path / "controlled-outbox.jsonl"))
    monkeypatch.setenv("ATOM_OFFICE_DIR", str(tmp_path))
    monkeypatch.setenv("ATOM_ASSIGNMENT_ALLOW_INTERNAL_PATHS", "1")
    monkeypatch.setenv("ATOM_ASSIGNMENT_INTERNAL_FIXTURE_ROOT", str(tmp_path))
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


def _teaching_agent(route_env, name: str, font: str, audience: str) -> str:
    from core.models import AgentRegistry
    from core.student_learning_service import deliver_teacher_lesson

    db = route_env["db"]
    agent = AgentRegistry(
        id=f"agent-{uuid.uuid4().hex[:8]}", name=name,
        category="operations", description="planner test",
        module_path="core.generic_agent", class_name="GenericAgent",
        status="intern", confidence_score=0.5, configuration={},
        capabilities=[], workspace_id="ws-1", tenant_id="tenant-1",
    )
    db.add(agent)
    db.commit()
    deliver_teacher_lesson(
        db, agent.id, "Use the approved document standard",
        topic="document standard", applies_to=["document"],
        format_spec={"font_name": font, "font_size": 11},
        context={"audience": audience},
        workspace_id="ws-1",
    )
    deliver_teacher_lesson(
        db, agent.id, "Use the approved presentation standard",
        topic="presentation standard", applies_to=["presentation"],
        format_spec={"font_name": font, "font_size": 18},
        context={"audience": audience},
        workspace_id="ws-1",
    )
    return agent.id


def test_start_from_chat_objective_uses_registered_plan_and_teaching(
        route_env, tmp_path):
    import openpyxl

    source = tmp_path / "connected-records.xlsx"
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Records"
    sheet.append(["Item", "Quantity", "Unit Price"])
    sheet.append(["A-1", 2, 10])
    sheet.append(["B-2", 3, 20])
    workbook.save(source)

    agent_id = _teaching_agent(
        route_env, "Document employee", "Times New Roman", "customer")
    from core.student_learning_service import list_agent_lessons

    lessons = list_agent_lessons(route_env["db"], agent_id)
    assert lessons and lessons[0].get("format_spec"), lessons[0]
    from core.artifact_teaching import resolve_artifact_teaching

    resolved = resolve_artifact_teaching(
        route_env["db"], agent_id, "document",
        task_context={"audience": "customer"}, workspace_id="ws-1")
    assert resolved["status"] == "applicable", resolved
    response = route_env["client"].post("/api/assignments", json={
        "objective": "Prepare a commercial response from the connected records",
        "agent_id": agent_id,
        "sources": [{
            "kind": "workbook", "path": str(source), "sheet": "Records",
            "columns": ["Item", "Quantity", "Unit Price"],
        }],
        "deliverables": [{
            "kind": "document",
            "description": "Commercial response",
            "path": str(tmp_path / "commercial.docx"),
            "content": (
                "## Summary\n\nTotal ${calculate.value}\n\n"
                "## Sources\n\n- Connected records"),
        }],
        "calculation": {"expression": "2*10 + 3*20", "output_unit": "USD"},
        "wait": {"correlation_id": "corr-A",
                 "party": "external source"},
        "outbound": {
            "to": ["test-recipient@example.invalid"],
            "subject": "Commercial response",
            "body": "Please see the prepared result.",
        },
        "task_context": {"audience": "customer"},
        "transport": "controlled",
    })
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["assignment"]["assignment"]["status"] == "waiting", body
    assert body["teaching_revision"].startswith("")
    assignment = body["assignment"]["assignment"]
    assert assignment["plan_revision"] == 1
    assert any(step["adapter"] == "workbook.read"
               for step in assignment["steps"])
    assert any(step["adapter"] == "formula.calculate"
               for step in assignment["steps"])
    assert any(step["adapter"] == "artifact.document"
               for step in assignment["steps"])

    responded = route_env["client"].post(
        "/api/assignments/" + body["run_id"] + "/responses/corr-A",
        json={"response": "REF-9", "source": "controlled reply",
              "evidence": "authorized message"},
    )
    assert responded.status_code == 200, responded.text
    assert responded.json()["assignment"]["status"] == "waiting"
    assignment = responded.json()["assignment"]

    # The teaching format reaches the saved document.
    doc_step = next(step for step in assignment["steps"]
                    if step["step_id"] == "deliverable-1")
    assert doc_step["status"] == "applied"
    doc_deliverable = next(
        item for item in assignment["deliverables"]
        if item.get("kind") == "document")
    doc_path = doc_deliverable.get("artifact_path")
    assert doc_path, doc_deliverable
    import docx

    document = docx.Document(str(doc_path))
    assert document.styles["Normal"].font.name == "Times New Roman"

    run_id = body["run_id"]
    action = route_env["db"].query(HITLAction).filter(
        HITLAction.action_type == "assignment_approval"
    ).order_by(HITLAction.created_at.desc()).first()
    assert action is not None
    assert action.params.get("run_id") == run_id
    approved = route_env["client"].post(
        f"/api/assignments/{run_id}/approve/send", json={"note": "ok"})
    assert approved.status_code == 200, approved.text
    assert approved.json()["assignment"]["assignment"]["status"] == "completed"


def test_start_rejects_unregistered_proposed_adapter(route_env, tmp_path, monkeypatch):
    monkeypatch.setenv("ATOM_ASSIGNMENT_ALLOW_PROPOSED_STEPS", "1")
    source = tmp_path / "a.txt"
    source.write_text("source")
    response = route_env["client"].post("/api/assignments", json={
        "objective": "Unsafe plan",
        "sources": [{"kind": "document", "path": str(source)}],
        "deliverables": [{
            "kind": "document", "path": str(tmp_path / "out.docx"),
            "content": "body",
        }],
        "proposed_steps": [{
            "step_id": "bad", "title": "Bad", "operation_type": "retrieve",
            "adapter": "invented.adapter", "depends_on": [],
            "inputs": {}, "instruction": "", "required": True,
            "effect": "read_only",
            "approval": {"required": False, "purpose": ""},
            "standing_authorization": None, "max_attempts": 3,
            "invalidate_on_revision_change": True, "status": "pending",
            "operation_id": None, "attempts": 0, "result": None,
            "evidence_refs": [], "gap_ids": [], "artifact_revision": None,
            "prior_results": [], "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
        }],
    })
    assert response.status_code == 422
    assert "unregistered adapter" in response.text


def test_guided_discovery_mode_needs_no_paths(route_env, tmp_path, monkeypatch):
    source = tmp_path / "discovered.txt"
    source.write_text("Subject: discovered\nStatus: active\n")
    monkeypatch.setattr(
        "core.sheet_dataset_service.find_entries_sync",
        lambda **kwargs: [{
            "dataset_name": "discovered-doc",
            "file_name": "discovered.txt",
            "entity_name": "Sheet1",
            "content_hash": "v1",
        }],
    )
    monkeypatch.setattr(
        "api.assignment_routes.resolve_assignment_source",
        lambda db, user, ref, allow_internal=False: {
            "kind": "document", "path": str(source),
            "resource_id": "discovered-doc", "dataset_name": "discovered-doc",
            "source_version": "v1",
            "coverage": {"known": True, "truncated": False},
        },
    )
    response = route_env["client"].post("/api/assignments", json={
        "objective": "Prepare a narrative for the permitted source",
        "discover": True,
        "source_scope": {"query": "discovered"},
        "deliverables": [{"kind": "document",
                          "description": "Narrative"}],
    })
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["assignment"]["assignment"]["status"] == "completed"
    assert body["assignment"]["assignment"]["deliverables"][0][
        "artifact_path"]


def test_public_proposed_steps_are_gated(route_env, tmp_path):
    source = tmp_path / "gate.txt"
    source.write_text("source")
    response = route_env["client"].post("/api/assignments", json={
        "objective": "Public proposed plan",
        "sources": [{"kind": "document", "path": str(source)}],
        "deliverables": [{
            "kind": "document", "path": str(tmp_path / "out.docx"),
            "content": "body",
        }],
        "proposed_steps": [],
    })
    assert response.status_code == 422
    assert "cannot submit executable steps" in response.text


def test_start_second_domain_presentation_completes(route_env, tmp_path):
    source = tmp_path / "qualification.txt"
    source.write_text("Subject: record-2\nStatus: active\n")
    agent_id = _teaching_agent(
        route_env, "Presentation employee", "Georgia", "reviewer")
    response = route_env["client"].post("/api/assignments", json={
        "objective": "Prepare an eligibility presentation for the reviewer",
        "agent_id": agent_id,
        "sources": [{"kind": "document", "path": str(source)}],
        "deliverables": [{
            "kind": "presentation",
            "description": "Eligibility deck",
            "path": str(tmp_path / "eligibility.pptx"),
            "content": (
                "Slide 1: Overview\n- Prepared from the authorized record\n\n"
                "Slide 2: Sources\n- Qualification record"),
        }],
        "task_context": {"audience": "reviewer"},
    })
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["assignment"]["assignment"]["status"] == "completed", body
    presentation_deliverable = next(
        item for item in body["assignment"]["assignment"]["deliverables"]
        if item.get("kind") == "presentation")
    presentation_path = presentation_deliverable.get("artifact_path")
    assert presentation_path, presentation_deliverable
    import pptx

    presentation = pptx.Presentation(str(presentation_path))
    assert presentation.slides[0].shapes.title.text == "Overview"


