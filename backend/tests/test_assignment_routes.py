"""Public assignment-route approval authority controls.

These exercise the real FastAPI assignment routes with a scratch database,
not the executor helper directly.
"""
from __future__ import annotations

import asyncio
import copy
import json
import os
import shutil
import uuid
from pathlib import Path
from datetime import datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("TESTING", "1")

from core.assignment_executor import (
    AssignmentExecutor,
    NeedsContext,
    WaitingForExternal,
    default_adapter_registry,
)
from core.assignment_plan import new_assignment, new_step, new_teaching_snapshot
from core.auth import get_current_user
from core.base_routes import BaseAPIRouter
from core.database import get_db
import core.assignment_controlled_transport  # noqa: F401,E402
from core.goals.goal_run_service import GoalRunService
from core.goals.goal_service import GoalService
from core.models import (
    Base, DatasetEntry, GoalRun, HITLAction, HITLActionStatus,
    IngestedDocument, IntegrationToken, User,
)
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


def _scotch_catalog(route_env, tmp_path, monkeypatch):
    """A real scoped catalog entry backed by a real Parquet frame.

    No reader or catalog function is mocked. The only controlled substitution
    is the non-secret active integration token, which stands in for an owner
    grant during an isolated acceptance run.
    """
    import pandas as pd

    monkeypatch.setenv("ATOM_DATA_DIR", str(tmp_path))
    root = tmp_path / "sheet_datasets"
    root.mkdir(parents=True, exist_ok=True)
    parquet = root / "scotch-parts.parquet"
    frame = pd.DataFrame({
        "Item Number": ["SC-1", "SC-2", "SC-3"],
        "Description": ["Scotch A", "Scotch B", "Scotch C"],
        "Quantity": [2, 3, 1],
        "Unit Price": [10.0, 20.0, 5.0],
        "Total": [20.0, 60.0, 5.0],
        "Currency": ["USD", "USD", "USD"],
        "__sheet_row": [2, 3, 4],
    })
    frame.to_parquet(parquet, index=False)
    columns = [
        {"name": column,
         "samples": [value.item() if hasattr(value, "item") else value
                     for value in frame[column].head(2).tolist()]}
        for column in frame.columns
    ]
    coverage = {
        "known": True, "source_row_count": len(frame),
        "materialized_row_count": len(frame), "truncated": False,
    }
    entry = DatasetEntry(
        id="scotch-entry",
        workspace_id="ws-1", tenant_id="tenant-1", created_by="lead-1",
        source_kind="file", source="onedrive", external_id="scotch-drive-1",
        file_name="scotch-parts.xlsx", content_hash="a" * 40,
        entity_name="US$ SCOTCH PARTS",
        dataset_name="scotch_parts_price_list",
        parquet_path=str(parquet), row_count=len(frame),
        column_count=len(frame.columns),
        columns_json={"columns": columns, "coverage": coverage},
        ingested_at=datetime.now() + timedelta(minutes=5),
        status="active",
    )
    route_env["db"].add(entry)
    existing = route_env["db"].query(IntegrationToken).filter(
        IntegrationToken.user_id == "lead-1",
        IntegrationToken.provider == "onedrive",
    ).first()
    if existing is None:
        route_env["db"].add(IntegrationToken(
            id="token-scotch", tenant_id="tenant-1", user_id="lead-1",
            workspace_id="ws-1", provider="onedrive",
            access_token="controlled-acceptance-not-a-secret",
            status="active"))
    route_env["db"].commit()
    return entry


def _add_distractor(route_env, tmp_path):
    import pandas as pd

    root = tmp_path / "sheet_datasets"
    root.mkdir(parents=True, exist_ok=True)
    parquet = root / "unrelated.parquet"
    frame = pd.DataFrame({
        "Label": ["X"],
        "Price": [1.0],
        "__sheet_row": [2],
    })
    frame.to_parquet(parquet, index=False)
    route_env["db"].add(DatasetEntry(
        id="distractor-entry",
        workspace_id="ws-1", tenant_id="tenant-1", created_by="lead-1",
        source_kind="file", source="onedrive", external_id="other-drive-1",
        file_name="unrelated-notes.xlsx", content_hash="b" * 40,
        entity_name="Notes", dataset_name="unrelated_notes",
        parquet_path=str(parquet), row_count=1, column_count=3,
        columns_json={
            "columns": [{"name": column} for column in frame.columns],
            "coverage": {"known": True, "source_row_count": 1,
                         "materialized_row_count": 1, "truncated": False},
        },
        ingested_at=datetime.now() + timedelta(minutes=30),
        status="active",
    ))
    route_env["db"].commit()


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
    assert response.status_code == 409, response.text
    detail = response.json()["detail"]
    assert detail["error"] == "artifact_content_required"
    assert "generic" in detail["message"].lower()


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


def test_guided_connected_aggregate_is_grounded_and_survives_restart(
        route_env, tmp_path, monkeypatch):
    _scotch_catalog(route_env, tmp_path, monkeypatch)
    _add_distractor(route_env, tmp_path)
    agent_id = _teaching_agent(
        route_env, "Connected document employee", "Times New Roman",
        "procurement")
    response = route_env["client"].post("/api/assignments", json={
        "objective": "Sum the total for the scotch parts price list",
        "agent_id": agent_id,
        "discover": True,
        "source_scope": {"query": "scotch parts price list"},
        "deliverables": [{
            "kind": "document",
            "description": "Scotch parts total",
        }],
        "outbound": {
            "to": ["acceptance@example.invalid"],
            "subject": "Scotch parts total",
        },
        "task_context": {"audience": "procurement"},
        "transport": "controlled",
    })
    assert response.status_code == 200, response.text
    body = response.json()
    assignment = body["assignment"]["assignment"]
    assert assignment["status"] == "waiting", body
    internal = route_env["lifecycle"].get_assignment(body["run_id"])
    source_step = next(
        step for step in internal["steps"]
        if step["step_id"] == "source-1")
    assert source_step["adapter"] == "dataset.aggregate", source_step
    binding = source_step["inputs"]["resource_binding"]
    assert binding["representation"] == "parquet_frame"
    assert binding["dataset_name"] == "scotch_parts_price_list"
    assert binding["sheet"] == "US$ SCOTCH PARTS"
    assert "path" not in binding
    assert "path" not in source_step["inputs"]
    doc = next(item for item in assignment["deliverables"]
               if item["kind"] == "document")
    assert doc["artifact_path"], doc

    import docx

    document = docx.Document(doc["artifact_path"])
    text = " | ".join(paragraph.text for paragraph in document.paragraphs)
    for table in document.tables:
        for row in table.rows:
            text += " | " + " | ".join(cell.text for cell in row.cells)
    assert "85.00" in text, text
    assert "scotch-parts.xlsx" in text
    assert "US$ SCOTCH PARTS" in text
    assert "SC-1" in text and "20.00" in text
    assert document.styles["Normal"].font.name == "Times New Roman"

    action = route_env["db"].query(HITLAction).filter(
        HITLAction.action_type == "assignment_approval"
    ).order_by(HITLAction.created_at.desc()).first()
    assert action is not None
    approved = route_env["client"].post(
        f"/api/assignments/{body['run_id']}/approve/send", json={})
    assert approved.status_code == 200, approved.text
    assert approved.json()["assignment"]["assignment"]["status"] == "completed"
    outbox = (tmp_path / "controlled-outbox.jsonl").read_text()
    assert "85.00" in outbox
    assert "scotch-parts.xlsx" in outbox

    # Rebuild the executor from durable state; no in-memory handoff.
    runs = GoalRunService(
        workspace_id="ws-1", tenant_id="tenant-1",
        session_factory=route_env["factory"])
    reopened = AssignmentExecutor(TaskLifecycle(
        runs, GoalService(
            workspace_id="ws-1", tenant_id="tenant-1",
            session_factory=route_env["factory"])))
    status = reopened.status(body["run_id"])
    assert status["assignment"]["status"] == "completed"
    reopened_doc = next(
        item for item in status["assignment"]["deliverables"]
        if item["kind"] == "document")
    assert reopened_doc["artifact_path"] == doc["artifact_path"]
    assert os.path.isfile(reopened_doc["artifact_path"])


def test_guided_connected_count_presentation(route_env, tmp_path, monkeypatch):
    _scotch_catalog(route_env, tmp_path, monkeypatch)
    _add_distractor(route_env, tmp_path)
    response = route_env["client"].post("/api/assignments", json={
        "objective": "Count the records in the scotch parts price list",
        "discover": True,
        "source_scope": {"query": "scotch parts price list"},
        "deliverables": [{
            "kind": "presentation",
            "description": "Scotch record count",
        }],
    })
    assert response.status_code == 200, response.text
    assignment = response.json()["assignment"]["assignment"]
    assert assignment["status"] == "completed", assignment
    internal = route_env["lifecycle"].get_assignment(
        response.json()["run_id"])
    source_step = next(
        step for step in internal["steps"]
        if step["step_id"] == "source-1")
    assert source_step["adapter"] == "dataset.aggregate", source_step
    assert source_step["inputs"]["operation"] == "count"
    deck = next(item for item in assignment["deliverables"]
                if item["kind"] == "presentation")
    assert deck["artifact_path"], deck
    import pptx

    presentation = pptx.Presentation(deck["artifact_path"])
    text = " | ".join(
        shape.text for slide in presentation.slides
        for shape in slide.shapes if getattr(shape, "text", "")
    )
    assert "3" in text, text
    assert "scotch-parts.xlsx" in text


def test_supervisor_assignment_rechecks_requester_source_grant(
        route_env, tmp_path, monkeypatch):
    _scotch_catalog(route_env, tmp_path, monkeypatch)
    response = route_env["client"].post("/api/assignments", json={
        "objective": "Sum the total for the scotch parts price list",
        "employee_id": "member-1",
        "discover": True,
        "source_scope": {"query": "scotch parts price list"},
        "deliverables": [{"kind": "document", "description": "Total"}],
    })
    assert response.status_code == 200, response.text
    assignment = response.json()["assignment"]["assignment"]
    assert assignment["employee_id"] == "member-1", assignment
    assert assignment["status"] == "completed", assignment
    internal = route_env["lifecycle"].get_assignment(
        response.json()["run_id"])
    source_step = next(
        step for step in internal["steps"]
        if step["step_id"] == "source-1")
    assert source_step["status"] == "applied", source_step
    assert source_step["inputs"]["resource_binding"]["access_scope"][
        "user_id"] == "lead-1"


def test_bounded_taught_method_job_with_wait_and_draft(
        route_env, tmp_path, monkeypatch):
    import docx
    from core.student_learning_service import (
        deliver_teacher_lesson, list_agent_lessons,
    )

    _scotch_catalog(route_env, tmp_path, monkeypatch)
    note = tmp_path / "email-note.docx"
    document = docx.Document()
    document.add_paragraph("Customer: Acme")
    document.add_paragraph("Approval reference: REF-9")
    document.add_paragraph("Message: please review the corrected line total.")
    document.save(note)

    agent_id = _teaching_agent(
        route_env, "Taught method employee", "Arial", "reviewer")
    deliver_teacher_lesson(
        route_env["db"], agent_id,
        "Use the taught line-total method",
        topic="calculation method", applies_to=["document"],
        format_spec={
            "calculation_expression": "line_total * correction_factor",
            "calculation_fields": ["line_total=Total"],
            "calculation_wait_variable": "correction_factor",
            "calculation_unit": "USD",
        },
        context={"audience": "reviewer"}, workspace_id="ws-1")
    deliver_teacher_lesson(
        route_env["db"], agent_id,
        "Use the reviewer email protocol",
        topic="email standard", applies_to=["email"],
        format_spec={
            "greeting": "Dear reviewer,",
            "signature": "Regards,\nOperations",
            "subject_prefix": "[Review]",
        },
        context={"audience": "reviewer"}, workspace_id="ws-1")
    lessons = list_agent_lessons(route_env["db"], agent_id)
    assert any(
        (lesson.get("format_spec") or {}).get("calculation_expression")
        for lesson in lessons), lessons

    response = route_env["client"].post("/api/assignments", json={
        "objective": "Prepare the bounded review package using the taught method",
        "agent_id": agent_id,
        "sources": [
            {
                "kind": "workbook",
                "dataset_name": "scotch_parts_price_list",
                "sheet": "US$ SCOTCH PARTS",
                "columns": ["Total"],
            },
            {"kind": "document", "path": str(note)},
        ],
        "deliverables": [
            {"kind": "document", "description": "Bounded review"},
            {"kind": "email_draft", "description": "Reviewer note"},
        ],
        "wait": {
            "correlation_id": "bounded-correction",
            "party": "reviewer",
            "detail": "correction factor",
        },
        "task_context": {"audience": "reviewer"},
    })
    assert response.status_code == 200, response.text
    body = response.json()
    assignment = body["assignment"]["assignment"]
    assert assignment["status"] == "waiting", assignment
    internal = route_env["lifecycle"].get_assignment(body["run_id"])
    calc_step = next(
        step for step in internal["steps"]
        if step["step_id"] == "calculate")
    assert calc_step["inputs"]["expression"] == (
        "line_total * correction_factor")
    assert calc_step["inputs"]["bindings"]["line_total"] == {
        "$ref": "source-1.rows.0.Total"}
    assert calc_step["inputs"]["bindings"]["correction_factor"] == {
        "$ref": "wait.value"}

    responded = route_env["client"].post(
        "/api/assignments/" + body["run_id"]
        + "/responses/bounded-correction",
        json={"response": "1.2", "source": "reviewer",
              "evidence": "corrected factor"},
    )
    assert responded.status_code == 200, responded.text
    completed = responded.json()["assignment"]
    assert completed["status"] == "completed", completed
    internal = route_env["lifecycle"].get_assignment(body["run_id"])
    calc_step = next(
        step for step in internal["steps"]
        if step["step_id"] == "calculate")
    assert str(calc_step["result"]["value"]) in ("24", "24.0", "24.00")
    doc = next(item for item in completed["deliverables"]
               if item["kind"] == "document")
    assert doc["artifact_path"], doc
    text = "\n".join(
        paragraph.text for paragraph in docx.Document(
            doc["artifact_path"]).paragraphs)
    for table in docx.Document(doc["artifact_path"]).tables:
        for row in table.rows:
            text += "\n" + " | ".join(cell.text for cell in row.cells)
    assert "24" in text, text
    assert "scotch-parts.xlsx" in text, text
    assert "email-note.docx" in text, text
    assert "REF-9" in text, text
    draft_step = next(
        step for step in internal["steps"]
        if step["adapter"] == "email.draft")
    draft = draft_step["result"]["draft"]
    assert "Dear reviewer," in draft["body"]
    assert "Regards" in draft["body"]
    assert "24" in draft["body"]
    assert draft["subject"].startswith("[Review]")

    # Rebuild the executor from durable state only.
    rebuilt = AssignmentExecutor(TaskLifecycle(
        GoalRunService(
            workspace_id="ws-1", tenant_id="tenant-1",
            session_factory=route_env["factory"]),
        GoalService(
            workspace_id="ws-1", tenant_id="tenant-1",
            session_factory=route_env["factory"])))
    reopened = rebuilt.status(body["run_id"])
    assert reopened["assignment"]["status"] == "completed"
    reopened_doc = next(
        item for item in reopened["assignment"]["deliverables"]
        if item["kind"] == "document")
    assert reopened_doc["artifact_path"] == doc["artifact_path"]
    assert os.path.isfile(reopened_doc["artifact_path"])

    evidence_dir = os.getenv("ATOM_ASSIGNMENT_BOUNDED_EVIDENCE_DIR")
    if evidence_dir:
        os.makedirs(evidence_dir, exist_ok=True)
        stored_doc = os.path.join(evidence_dir, "bounded-review.docx")
        shutil.copy2(doc["artifact_path"], stored_doc)
        payload = {
            "slice": "bounded-taught-method-job",
            "controlled": True,
            "live_connected": False,
            "objective": (
                "Prepare the bounded review package using the taught method"),
            "plan_revision": completed["plan_revision"],
            "teaching_revision": completed["teaching_revision"],
            "sources": internal.get("sources") or [],
            "calculation": {
                "expression": calc_step["inputs"]["expression"],
                "bindings": calc_step["inputs"]["bindings"],
                "value": calc_step["result"]["value"],
                "unit": calc_step["result"]["unit"],
            },
            "wait_response": "1.2",
            "artifact_path": doc["artifact_path"],
            "stored_artifact": stored_doc,
            "artifact_sha256": doc.get("sha256"),
            "artifact_text": text,
            "draft": draft,
            "draft_revision": draft.get("draft_revision"),
            "reopened_status": reopened["assignment"]["status"],
        }
        with open(os.path.join(
                evidence_dir, "bounded_taught_job.json"), "w") as handle:
            json.dump(payload, handle, indent=2, default=str)



def test_taught_method_missing_wait_is_a_clarification(
        route_env, tmp_path, monkeypatch):
    from core.student_learning_service import deliver_teacher_lesson

    _scotch_catalog(route_env, tmp_path, monkeypatch)
    agent_id = _teaching_agent(
        route_env, "Taught wait employee", "Arial", "reviewer")
    deliver_teacher_lesson(
        route_env["db"], agent_id,
        "Use the taught line-total method",
        topic="calculation method", applies_to=["document"],
        format_spec={
            "calculation_expression": "line_total * correction_factor",
            "calculation_fields": ["line_total=Total"],
            "calculation_wait_variable": "correction_factor",
            "calculation_unit": "USD",
        },
        context={"audience": "reviewer"}, workspace_id="ws-1")
    response = route_env["client"].post("/api/assignments", json={
        "objective": "Prepare the bounded review package using the taught method",
        "agent_id": agent_id,
        "sources": [{
            "kind": "workbook",
            "dataset_name": "scotch_parts_price_list",
            "sheet": "US$ SCOTCH PARTS",
        }],
        "deliverables": [{"kind": "document", "description": "Bounded review"}],
        "task_context": {"audience": "reviewer"},
    })
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["error"] == (
        "calculation_method_unresolved")


def test_unsupported_taught_method_is_a_clarification(
        route_env, tmp_path, monkeypatch):
    from core.student_learning_service import deliver_teacher_lesson

    _scotch_catalog(route_env, tmp_path, monkeypatch)
    agent_id = _teaching_agent(
        route_env, "Taught invalid employee", "Arial", "reviewer")
    deliver_teacher_lesson(
        route_env["db"], agent_id,
        "Use the taught line-total method",
        topic="calculation method", applies_to=["document"],
        format_spec={
            "calculation_expression": "line_total *",
            "calculation_fields": ["line_total=Total"],
            "calculation_unit": "USD",
        },
        context={"audience": "reviewer"}, workspace_id="ws-1")
    response = route_env["client"].post("/api/assignments", json={
        "objective": "Prepare the bounded review package using the taught method",
        "agent_id": agent_id,
        "sources": [{
            "kind": "workbook",
            "dataset_name": "scotch_parts_price_list",
            "sheet": "US$ SCOTCH PARTS",
        }],
        "deliverables": [{"kind": "document", "description": "Bounded review"}],
        "task_context": {"audience": "reviewer"},
    })
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["error"] in (
        "calculation_method_unresolved", "calculation_method_unsupported")


def test_guided_no_match_is_explicit_pending_work(
        route_env, tmp_path, monkeypatch):
    _scotch_catalog(route_env, tmp_path, monkeypatch)
    response = route_env["client"].post("/api/assignments", json={
        "objective": "Summarize the quarterly tax filings",
        "discover": True,
        "source_scope": {"query": "quarterly tax filings"},
        "deliverables": [{"kind": "document", "description": "Tax summary"}],
    })
    assert response.status_code == 409, response.text
    detail = response.json()["detail"]
    assert detail["error"] == "resource_discovery_empty"


def test_guided_wrong_workspace_scope_is_refused(route_env, tmp_path, monkeypatch):
    _scotch_catalog(route_env, tmp_path, monkeypatch)
    response = route_env["client"].post("/api/assignments", json={
        "objective": "Sum the total for the scotch parts price list",
        "discover": True,
        "source_scope": {"query": "scotch parts price list",
                         "workspace_id": "ws-2"},
        "deliverables": [{"kind": "document", "description": "Total"}],
    })
    assert response.status_code == 403, response.text
    assert response.json()["detail"]["error"] == "resource_workspace_mismatch"


def test_real_catalog_resource_from_another_workspace_is_refused(
        route_env, tmp_path, monkeypatch):
    _scotch_catalog(route_env, tmp_path, monkeypatch)
    route_env["current"]["user"] = route_env["users"]["other"]
    response = route_env["client"].post("/api/assignments", json={
        "objective": "Sum the total for the scotch parts price list",
        "sources": [{
            "dataset_name": "scotch_parts_price_list",
            "sheet": "US$ SCOTCH PARTS",
        }],
        "deliverables": [{"kind": "document", "description": "Total"}],
    })
    assert response.status_code == 403, response.text
    assert response.json()["detail"]["error"] == "resource_workspace_mismatch"


def test_client_cannot_choose_an_output_path(route_env, tmp_path, monkeypatch):
    _scotch_catalog(route_env, tmp_path, monkeypatch)
    foreign = tmp_path / "other-user" / "owned-by-other.docx"
    response = route_env["client"].post("/api/assignments", json={
        "objective": "Sum the total for the scotch parts price list",
        "discover": True,
        "source_scope": {"query": "scotch parts price list"},
        "deliverables": [{
            "kind": "document",
            "description": "Total",
            "path": str(foreign),
        }],
    })
    assert response.status_code == 200, response.text
    doc = next(item for item in response.json()["assignment"]["assignment"][
        "deliverables"] if item["kind"] == "document")
    assert doc["artifact_path"] != str(foreign)
    assert not foreign.exists()
    assert str(route_env["users"]["lead"].id) in doc["artifact_path"]



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
                "Slide 1: Overview\n- Record record-2\n\n"
                "Slide 2: Findings\n- Subject: record-2\n- Status: active\n\n"
                "Slide 3: Sources\n- qualification.txt"),
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




def _mapping_correction_plan(
    route_env,
    tmp_path,
    *,
    mappings=None,
    execute=False,
):
    """A real aggregate plan with one confirmed Price mapping.

    The source is an allowed controlled fixture, so the route still exercises
    the real source resolver (monkeypatched to the same typed binding) and the
    real dataset aggregate adapter.
    """
    import pandas as pd

    parquet = tmp_path / "correction-source.parquet"
    pd.DataFrame({
        "Item": ["R-1", "R-2"],
        "List Price": [60.0, 40.0],
        "Contract Price": [45.0, 35.0],
        "Renewal Price": [40.0, 30.0],
        "Tax": [5.0, 3.0],
        "Currency": ["USD", "USD"],
        "__sheet_row": [2, 3],
    }).to_parquet(parquet, index=False)
    binding = {
        "resource_id": "fixture:correction-source.parquet",
        "dataset_name": "correction_source",
        "source": "outlook",
        "external_id": "correction-source",
        "original_file_name": "correction-source.xlsx",
        "representation": "parquet_frame",
        "source_version": "v1",
        "sheet": "Sheet1",
        "columns": [
            "Item", "List Price", "Contract Price", "Renewal Price",
            "Tax", "Currency", "__sheet_row",
        ],
        "numeric_columns": [
            "List Price", "Contract Price", "Renewal Price", "Tax",
        ],
        "workspace_id": "ws-1",
        "tenant_id": "tenant-1",
        "access_scope": {
            "user_id": "lead-1", "workspace_id": "ws-1",
            "tenant_id": "tenant-1",
        },
        "internal_fixture": True,
        "path": str(parquet),
    }
    confirmed = [{
        "concept": "Price", "sheet": "Sheet1", "column": "List Price",
        "unit": "USD", "unit_authority": "source_evidence",
        "required_unit": "USD", "source_unit": "USD",
        "source_unit_column": "Currency", "source_version": "v1",
        "revision": 2,
    }, {
        "concept": "Tax", "sheet": "Sheet1", "column": "Tax",
        "unit": "USD", "unit_authority": "source_evidence",
        "required_unit": "USD", "source_unit": "USD",
        "source_unit_column": "Currency", "source_version": "v1",
        "revision": 1,
    }]
    if mappings is not None:
        confirmed = mappings
    plan = new_assignment(
        objective="Correct the price mapping",
        employee_id="lead-1",
        workspace_id="ws-1",
        tenant_id="tenant-1",
        teaching_snapshot=new_teaching_snapshot(
            revision="corr-r1", field_mappings=confirmed),
        steps=[new_step(
            step_id="source-1", title="Aggregate the mapped price",
            operation_type="calculate", adapter="dataset.aggregate",
            inputs={
                "resource_binding": binding,
                "operation": "sum",
                "value_column": "List Price",
            },
            effect="local")],
        sources=[{"kind": "workbook", "binding": binding}],
        authorized_actions=["retrieve", "calculate"],
        completion_criteria=[{"kind": "required_work_complete"}],
        provenance={"agent_id": "correction-agent"},
    )
    record = route_env["executor"].create_assignment(
        "conv-correction", "Correct the price mapping", assignment=plan,
        employee_id="lead-1", workspace_id="ws-1", tenant_id="tenant-1")
    if execute:
        _run(route_env["executor"].execute(record["run_id"]))
    return record["run_id"], binding


def _source_resolver(binding):
    def resolve(db, user, reference, allow_internal=False):
        return dict(binding)

    return resolve


def _durable_assignment_route(route_env, run_id):
    record = route_env["lifecycle"].get_task(run_id) or {}
    return copy.deepcopy(record.get("assignment") or {})


def _correction_payload(**overrides):
    payload = {
        "concept": "Price",
        "expected_revision": 2,
        "column": "Contract Price",
        "unit": "USD",
        "evidence": "route acceptance correction",
        "sheet": "Sheet1",
        "source_version": "v1",
    }
    payload.update(overrides)
    return payload


def test_mapping_correction_route_applies_and_resumes(route_env, tmp_path,
                                                      monkeypatch):
    run_id, binding = _mapping_correction_plan(
        route_env, tmp_path, execute=True)
    before = _durable_assignment_route(route_env, run_id)
    assert before["steps"][0]["result"]["value"] == "100.00"
    monkeypatch.setattr(
        "api.assignment_routes.resolve_assignment_source",
        _source_resolver(binding))
    response = route_env["client"].post(
        f"/api/assignments/{run_id}/mappings/correct",
        json=_correction_payload())
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["assignment"]["status"] == "completed", body
    mapping = next(
        item for item in body["assignment"]["mappings"]
        if item["concept"] == "Price")
    assert mapping["column"] == "Contract Price"
    assert mapping["revision"] == 3
    assert mapping["source_version"] == "v1"
    assert mapping["unit_authority"] == "source_evidence"
    step = next(
        item for item in body["assignment"]["steps"]
        if item["step_id"] == "source-1")
    assert step["result_value"] == "80.00"
    assert step["prior_result_count"] == 1
    durable = _durable_assignment_route(route_env, run_id)
    assert durable["steps"][0]["prior_results"][0]["result"]["value"] == (
        "100.00")
    assert durable["mapping_history"][0]["column"] == "List Price"
    assert durable["mapping_history"][0]["revision"] == 2
    assert next(
        item for item in durable["teaching_snapshot"]["field_mappings"]
        if item["concept"] == "Tax") == next(
            item for item in before["teaching_snapshot"]["field_mappings"]
            if item["concept"] == "Tax")


def test_stale_mapping_correction_is_refused_before_source_resolution(
        route_env, tmp_path, monkeypatch):
    run_id, _binding = _mapping_correction_plan(route_env, tmp_path)
    before = _durable_assignment_route(route_env, run_id)
    called = {"resolve": 0}

    def unexpected_resolve(*args, **kwargs):
        called["resolve"] += 1
        raise AssertionError("stale correction must not resolve the source")

    monkeypatch.setattr(
        "api.assignment_routes.resolve_assignment_source",
        unexpected_resolve)
    response = route_env["client"].post(
        f"/api/assignments/{run_id}/mappings/correct",
        json=_correction_payload(expected_revision=1))
    assert response.status_code == 409, response.text
    assert "stale mapping revision" in response.json()["detail"]
    assert called["resolve"] == 0
    assert _durable_assignment_route(route_env, run_id) == before


def test_wrong_workspace_mapping_correction_is_refused(route_env, tmp_path,
                                                       monkeypatch):
    run_id, binding = _mapping_correction_plan(route_env, tmp_path)
    before = _durable_assignment_route(route_env, run_id)
    monkeypatch.setattr(
        "api.assignment_routes.resolve_assignment_source",
        _source_resolver(binding))
    route_env["current"]["user"] = route_env["users"]["other"]
    response = route_env["client"].post(
        f"/api/assignments/{run_id}/mappings/correct",
        json=_correction_payload())
    assert response.status_code == 404, response.text
    assert _durable_assignment_route(route_env, run_id) == before


def test_ambiguous_mapping_correction_requires_source_identity(
        route_env, tmp_path, monkeypatch):
    first = {
        "concept": "Price", "sheet": "Sheet1", "column": "List Price",
        "unit": "USD", "unit_authority": "source_evidence",
        "required_unit": "USD", "source_unit": "USD",
        "source_unit_column": "Currency", "source_version": "v1",
        "revision": 2,
    }
    second = {
        **first, "sheet": "Sheet2", "column": "Renewal Price",
        "revision": 1,
    }
    run_id, binding = _mapping_correction_plan(
        route_env, tmp_path, mappings=[first, second])
    before = _durable_assignment_route(route_env, run_id)
    called = {"resolve": 0}

    def unexpected_resolve(*args, **kwargs):
        called["resolve"] += 1
        raise AssertionError("ambiguous correction must not resolve a source")

    monkeypatch.setattr(
        "api.assignment_routes.resolve_assignment_source",
        unexpected_resolve)
    response = route_env["client"].post(
        f"/api/assignments/{run_id}/mappings/correct",
        json=_correction_payload(sheet="", source_version=""))
    assert response.status_code == 409, response.text
    assert "more than one confirmed mapping" in response.json()["detail"]
    assert called["resolve"] == 0
    assert _durable_assignment_route(route_env, run_id) == before


def _mapping_gap_assignment(route_env, tmp_path):
    """Execute a real aggregate against a frame missing the taught measure."""
    import pandas as pd
    from core.models import AgentRegistry
    from core.student_learning_service import journal_standing_lesson_entry

    parquet = tmp_path / "gap-source.parquet"
    pd.DataFrame({
        "Item": ["B-1", "B-2"],
        "Amount": [15.0, 20.0],
        "Discount": [1.0, 2.0],
        "Currency": ["USD", "USD"],
        "__sheet_row": [2, 3],
    }).to_parquet(parquet, index=False)
    binding = {
        "resource_id": "fixture:gap-source.parquet",
        "dataset_name": "gap_source",
        "source": "outlook",
        "external_id": "gap-source",
        "original_file_name": "gap-source.xlsx",
        "representation": "parquet_frame",
        "source_version": "v1",
        "sheet": "Sheet1",
        "columns": [
            "Item", "Amount", "Discount", "Currency", "__sheet_row"],
        "numeric_columns": ["Amount", "Discount"],
        "workspace_id": "ws-1",
        "tenant_id": "tenant-1",
        "access_scope": {
            "user_id": "lead-1", "workspace_id": "ws-1",
            "tenant_id": "tenant-1",
        },
        "internal_fixture": True,
        "path": str(parquet),
    }
    agent_id = f"gap-agent-{uuid.uuid4().hex[:8]}"
    agent = AgentRegistry(
        id=agent_id, name="Gap Agent", category="operations",
        description="mapping gap authority control",
        module_path="core.generic_agent", class_name="GenericAgent",
        status="intern", confidence_score=0.5, configuration={},
        capabilities=[], workspace_id="ws-1", tenant_id="tenant-1")
    route_env["db"].add(agent)
    route_env["db"].commit()
    lesson = journal_standing_lesson_entry(
        route_env["db"], agent_id,
        "Price is a monetary amount and must be mapped explicitly.",
        source="teacher", topic="price gap mapping",
        applies_to=["document"],
        context={"field_mappings": [{
            "concept": "Price", "sheet": "Sheet1", "column": "Price",
            "unit": "USD", "source_version": "a" * 40, "revision": 1,
        }]}, workspace_id="ws-1")
    assert lesson and lesson.get("id"), lesson
    plan = new_assignment(
        objective="Map the missing price measure",
        employee_id="lead-1",
        workspace_id="ws-1",
        tenant_id="tenant-1",
        teaching_snapshot=new_teaching_snapshot(
            revision="gap-r1",
            field_mappings=[{
                "concept": "Price", "sheet": "Sheet1", "column": "Price",
                "unit": "USD", "source_version": "a" * 40,
                "revision": 1, "lesson_id": lesson["id"],
            }]),
        steps=[new_step(
            step_id="source-1", title="Aggregate the missing price",
            operation_type="calculate", adapter="dataset.aggregate",
            inputs={
                "resource_binding": binding,
                "operation": "sum",
                "value_column": "Price",
            },
            effect="local")],
        sources=[{"kind": "workbook", "binding": binding}],
        authorized_actions=["retrieve", "calculate"],
        completion_criteria=[{"kind": "required_work_complete"}],
        provenance={"agent_id": agent_id},
    )
    record = route_env["executor"].create_assignment(
        "conv-gap", "Map the missing price measure", assignment=plan,
        employee_id="lead-1", workspace_id="ws-1", tenant_id="tenant-1")
    _run(route_env["executor"].execute(record["run_id"]))
    status = route_env["executor"].status(record["run_id"])
    gap = next(
        item for item in status["open_gaps"]
        if (item.get("inputs") or {}).get("mapping"))
    return record["run_id"], plan["assignment_id"], gap, binding, agent_id


def _agent_configuration(route_env, agent_id):
    from core.models import AgentRegistry

    route_env["db"].expire_all()
    agent = route_env["db"].query(AgentRegistry).filter(
        AgentRegistry.id == agent_id).first()
    assert agent is not None
    return copy.deepcopy(agent.configuration)


def _gap_resolution(gap, assignment_id, column, *, unit=None,
                    source_version="v1", teaching_revision="gap-r1",
                    request_id=None, target_assignment_id=None):
    payload = {
        "request_id": request_id or gap["question_id"],
        "assignment_id": target_assignment_id or assignment_id,
        "column": column,
        "source_version": source_version,
        "teaching_revision": teaching_revision,
    }
    if unit is not None:
        payload["unit"] = unit
    return json.dumps(payload)


def test_mapping_gap_authority_controls_and_idempotent_replay(
        route_env, tmp_path, monkeypatch):
    run_id, assignment_id, gap, binding, agent_id = _mapping_gap_assignment(
        route_env, tmp_path)
    monkeypatch.setattr(
        "api.assignment_routes.resolve_assignment_source",
        _source_resolver(binding))
    params_before = route_env["lifecycle"].get_task(run_id)
    params_before = copy.deepcopy(params_before)
    lesson_before = _agent_configuration(route_env, agent_id)
    mapping = gap["inputs"]["mapping"]
    assert mapping["source_version"] == "v1"
    assert mapping["teaching_revision"] == "gap-r1"
    assert "Amount" in [
        item["column"] for item in mapping["candidates"]]
    assert mapping["source_unit"] == "USD"

    rejected = route_env["client"].post(
        f"/api/assignments/{run_id}/gaps/{gap['question_id']}/resolve",
        json={"resolution": json.dumps({
            "rejected": True,
            "request_id": gap["question_id"],
            "assignment_id": assignment_id,
        })})
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["status"] == "rejected_candidates"
    assert copy.deepcopy(
        route_env["lifecycle"].get_task(run_id)) == params_before
    assert _agent_configuration(route_env, agent_id) == lesson_before

    def assert_refused(payload, *, expected_status=409, contains=""):
        response = route_env["client"].post(
            f"/api/assignments/{run_id}/gaps/{gap['question_id']}/resolve",
            json={"resolution": payload})
        assert response.status_code == expected_status, response.text
        if contains:
            assert contains in response.text.lower(), response.text
        assert copy.deepcopy(
            route_env["lifecycle"].get_task(run_id)) == params_before
        assert _agent_configuration(route_env, agent_id) == lesson_before
        durable = _durable_assignment_route(route_env, run_id)
        assert durable["objective"] == "Map the missing price measure"
        assert durable["status"] != "completed"
        assert not any(step.get("result") for step in durable["steps"])
        return response

    assert_refused(
        _gap_resolution(gap, assignment_id, "Amount",
                        request_id="wrong-request"),
        contains="outstanding mapping request")
    assert_refused(
        _gap_resolution(gap, assignment_id, "Amount",
                        target_assignment_id="wrong-assignment"),
        contains="different assignment")
    assert_refused(
        _gap_resolution(gap, assignment_id, "Forged"),
        contains="current schema candidates")
    assert_refused(
        _gap_resolution(gap, assignment_id, "Amount",
                        source_version="v0"),
        contains="stale source version")
    monkeypatch.setattr(
        "api.assignment_routes.resolve_assignment_source",
        _source_resolver({**binding, "source_version": "v2"}))
    assert_refused(
        _gap_resolution(gap, assignment_id, "Amount"),
        contains="stale source version")
    monkeypatch.setattr(
        "api.assignment_routes.resolve_assignment_source",
        _source_resolver(binding))
    assert_refused(
        _gap_resolution(gap, assignment_id, "Amount",
                        teaching_revision="gap-r0"),
        contains="stale teaching revision")
    assert_refused(
        _gap_resolution(gap, assignment_id, "Amount", unit="EUR"),
        contains="conflict")
    route_env["current"]["user"] = route_env["users"]["other"]
    assert_refused(
        _gap_resolution(gap, assignment_id, "Amount"),
        expected_status=404)
    route_env["current"]["user"] = route_env["users"]["lead"]

    accepted = _gap_resolution(
        gap, assignment_id, "Amount", unit="USD")
    response = route_env["client"].post(
        f"/api/assignments/{run_id}/gaps/{gap['question_id']}/resolve",
        json={"resolution": accepted})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["assignment"]["status"] == "completed", body
    assert body["assignment"]["assignment_id"] == assignment_id
    durable_after = copy.deepcopy(
        route_env["lifecycle"].get_task(run_id))
    assignment = durable_after["assignment"]
    source_step = next(
        step for step in assignment["steps"]
        if step["step_id"] == "source-1")
    assert source_step["result"]["value"] == "35.00"
    assert source_step["result"]["unit"] == "USD"
    mappings = [
        item for item in assignment["teaching_snapshot"]["field_mappings"]
        if item["concept"] == "Price"
    ]
    assert len(mappings) == 1
    assert mappings[0]["column"] == "Amount"
    assert mappings[0]["revision"] == 2
    assert mappings[0]["unit_authority"] == "source_evidence"
    applied_operations = [
        op for op in durable_after["operations"]
        if op.get("status") == "applied"]
    assert len(applied_operations) == 1
    lesson_after = _agent_configuration(route_env, agent_id)
    lesson_mappings = [
        item for item in (
            (lesson_after.get("learning") or {}).get("log") or [{}]
        )[0].get("context", {}).get("field_mappings") or []
        if item.get("concept") == "Price"
    ]
    assert len(lesson_mappings) == 1
    assert lesson_mappings[0]["column"] == "Amount"
    assert lesson_mappings[0]["revision"] == 2

    # An identical replay is idempotent: no new operation, result or teaching
    # revision. A conflicting replay is refused with no mutation.
    replay = route_env["client"].post(
        f"/api/assignments/{run_id}/gaps/{gap['question_id']}/resolve",
        json={"resolution": accepted})
    assert replay.status_code == 200, replay.text
    assert replay.json()["status"] == "already_resolved"
    assert copy.deepcopy(
        route_env["lifecycle"].get_task(run_id)) == durable_after
    assert _agent_configuration(route_env, agent_id) == lesson_after

    conflict = route_env["client"].post(
        f"/api/assignments/{run_id}/gaps/{gap['question_id']}/resolve",
        json={"resolution": _gap_resolution(
            gap, assignment_id, "Discount", unit="USD")})
    assert conflict.status_code == 409, conflict.text
    assert copy.deepcopy(
        route_env["lifecycle"].get_task(run_id)) == durable_after
    assert _agent_configuration(route_env, agent_id) == lesson_after


def test_incomplete_inline_evidence_cannot_resume_route(route_env, monkeypatch):
    """A public response cannot complete a wait when inline rows do not
    cover the accepted identities exactly."""
    async def source(inputs, context):
        return {
            "status": "applied",
            "summary": "inline accepted rows 2 and 3",
            "rows": [{"__sheet_row": 2, "Currency": "USD"}],
            "selected_count": 2,
            "evidence": [{
                "sheet_rows": [2, 3],
                "selected_count": 2,
                "coverage": {"known": True, "source_row_count": 2,
                             "truncated": False},
            }],
        }

    async def wait_fact(inputs, context):
        raise WaitingForExternal({
            "event": "email",
            "state": "waiting_for_external",
            "party": "owner",
            "correlation_id": "inline-corr",
            "resume_on": "response",
            "detail": "currency",
            "fact": "currency",
        })

    route_env["executor"].adapters.register("test.inline.source", source)
    route_env["executor"].adapters.register("test.inline.wait", wait_fact)
    monkeypatch.setattr(
        "api.assignment_routes._executor",
        lambda run: route_env["executor"])
    plan = new_assignment(
        objective="Incomplete inline evidence",
        employee_id="owner-1",
        workspace_id="ws-1",
        tenant_id="tenant-1",
        teaching_snapshot=new_teaching_snapshot(revision="inline-r1"),
        steps=[
            new_step(
                step_id="source", title="Read inline rows",
                operation_type="retrieve", adapter="test.inline.source",
                inputs={"resource_binding": {
                    "columns": ["Currency", "__sheet_row"]}},
                effect="read_only"),
            new_step(
                step_id="wait", title="Wait for currency",
                operation_type="retrieve", adapter="test.inline.wait",
                depends_on=["source"], effect="read_only"),
        ],
    )
    record = route_env["executor"].create_assignment(
        "conv-inline", "Incomplete inline evidence", assignment=plan)
    run_id = record["run_id"]
    _run(route_env["executor"].execute(run_id))
    response = route_env["client"].post(
        f"/api/assignments/{run_id}/responses/inline-corr",
        json={"response": "USD", "source": "owner"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "incomplete", body
    detail = route_env["executor"].status(run_id)
    assert detail["assignment"]["status"] == "waiting"
    wait_step = next(step for step in detail["assignment"]["steps"]
                     if step["step_id"] == "wait")
    assert wait_step["status"] == "waiting"
    assert wait_step["waiting"]["conflicts"][-1]["reason"] == (
        "source_fact_incomplete")


def test_assignment_consumes_contextual_conversation_method(
        route_env, tmp_path, monkeypatch):
    """Normal assignment start consumes a promoted method, not /apply."""
    from decimal import Decimal

    from core.conversation_learning import MethodInput, MethodSpec
    from core.models import AgentRegistry
    from core.student_learning_service import journal_standing_lesson_entry

    _scotch_catalog(route_env, tmp_path, monkeypatch)
    db = route_env["db"]
    agent = AgentRegistry(
        id="agent-context-method", name="Context Method Employee",
        category="operations", module_path="core.generic_agent",
        class_name="GenericAgent", status="supervised",
        confidence_score=0.6, configuration={}, capabilities=[],
        workspace_id="ws-1", tenant_id="tenant-1",
    )
    db.add(agent)
    db.commit()
    method = MethodSpec(
        intended_outcome="Price the order",
        operation="multiply_sum",
        inputs=[
            MethodInput(concept="quantity", column="Quantity", unit="units"),
            MethodInput(concept="unit_price", column="Unit Price", unit="USD"),
        ],
        output_unit="USD",
        transformation="quantity * unit_price",
        rounding={"places": 2, "stage": "final"},
    )
    lesson = journal_standing_lesson_entry(
        db, agent.id, "Use the licensed customer pricing method",
        source="teacher", topic="pricing",
        context={"audience": "customer"},
        details={"conversation_learning": {
            "candidate_id": "lc-assignment-test",
            "method": method.model_dump(mode="json"),
        }},
        workspace_id="ws-1",
    )
    assert lesson is not None

    base_payload = {
        "objective": "Use the pricing method for the customer order",
        "agent_id": agent.id,
        "sources": [{
            "kind": "workbook",
            "dataset_name": "scotch_parts_price_list",
            "sheet": "US$ SCOTCH PARTS",
            "columns": ["Quantity", "Unit Price"],
        }],
        "deliverables": [{
            "kind": "document",
            "description": "Priced order",
        }],
    }

    wrong = route_env["client"].post(
        "/api/assignments",
        json={**base_payload, "task_context": {"audience": "other"}})
    assert wrong.status_code == 409, wrong.text
    assert wrong.json()["detail"]["error"] == "teaching_context_mismatch"

    missing = route_env["client"].post(
        "/api/assignments",
        json={**base_payload, "task_context": {}})
    assert missing.status_code == 409, missing.text
    assert missing.json()["detail"]["error"] == "teaching_context_unresolved"
    assert "audience" in missing.json()["detail"]["missing"]

    matching = route_env["client"].post(
        "/api/assignments",
        json={**base_payload, "task_context": {"audience": "customer"}})
    assert matching.status_code == 200, matching.text
    assignment = matching.json()["assignment"]["assignment"]
    assert assignment["status"] == "completed", {
        "status": assignment.get("status"),
        "steps": [
            {"id": step.get("step_id"), "status": step.get("status"),
             "adapter": step.get("adapter"),
             "failure": step.get("failure"),
             "waiting": step.get("waiting"),
             "gap_ids": step.get("gap_ids"),
             "result": step.get("result")}
            for step in assignment.get("steps") or []
        ],
        "open_gaps": matching.json().get("open_gaps"),
    }
    formula = next(step for step in assignment["steps"]
                   if step["adapter"] == "formula.calculate")
    assert Decimal(str(formula["result_value"])) == Decimal("20")
    effective = assignment.get("effective_lesson_ids") or []
    assert any(item.get("id") == lesson["id"] and item.get("revision") == 1
               for item in effective), effective
    status = route_env["client"].get(
        f"/api/assignments/{matching.json()['run_id']}")
    assert status.status_code == 200, status.text
    persisted = status.json()["assignment"].get("effective_lesson_ids") or []
    assert any(item.get("id") == lesson["id"] and item.get("revision") == 1
               for item in persisted), persisted


def _uncertain_assignment(env):
    from core.assignment_executor import ExternalOutcomeUnknown

    calls = {"count": 0, "effects": 0}

    async def uncertain(inputs, context):
        calls["count"] += 1
        if calls["count"] == 1:
            calls["effects"] += 1
            raise ExternalOutcomeUnknown(
                "provider may have accepted the effect",
                evidence="outbox: row-1")
        return {
            "status": "applied", "summary": "provider accepted",
            "provider_state": "sent", "provider_ref": "provider-2",
        }

    def prepare(inputs, context):
        return {
            "payload": {"to": inputs.get("to"),
                        "subject": inputs.get("subject"),
                        "body": inputs.get("body")},
            "requested_by": "owner-1",
        }

    registry = default_adapter_registry
    registry.register("test.route.uncertain", uncertain, prepare=prepare)
    env["executor"].adapters.register(
        "test.route.uncertain", uncertain, prepare=prepare)
    plan = new_assignment(
        objective="Route uncertain effect",
        employee_id="owner-1", workspace_id="ws-1", tenant_id="tenant-1",
        teaching_snapshot=new_teaching_snapshot(revision="route-r1"),
        steps=[new_step(
            step_id="send", title="Uncertain send",
            operation_type="outbound", adapter="test.route.uncertain",
            inputs={"to": ["test@example.invalid"], "subject": "S",
                    "body": "B"},
            effect="external", approval_required=True,
            approval_purpose="Send the uncertain effect")],
    )
    record = env["executor"].create_assignment(
        "conv-route", "Route uncertain effect", assignment=plan)
    run_id = record["run_id"]
    _run(env["executor"].execute(run_id))
    env["executor"].approve_step(run_id, "send", approved_by="lead-1")
    _run(env["executor"].execute(run_id))
    return run_id, calls


def test_route_reconcile_applied_never_resends(route_env):
    run_id, calls = _uncertain_assignment(route_env)
    record = route_env["lifecycle"].get_assignment(run_id)
    step = next(item for item in record["steps"]
                if item["step_id"] == "send")
    assert step["status"] == "uncertain"

    response = route_env["client"].post(
        f"/api/assignments/{run_id}/reconcile/send",
        json={"verdict": "applied",
              "evidence": "the outbox row proves provider acceptance",
              "evidence_ref": "outbox: row-1"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["verdict"] == "applied"
    assert body["assignment"]["assignment"]["status"] == "completed"
    assert calls["count"] == 1
    assert calls["effects"] == 1


def test_route_reconcile_insufficient_keeps_uncertain_and_never_resends(
        route_env):
    run_id, calls = _uncertain_assignment(route_env)
    response = route_env["client"].post(
        f"/api/assignments/{run_id}/reconcile/send",
        json={"verdict": "insufficient",
              "evidence": "the provider audit returned no row"})
    assert response.status_code == 200, response.text
    assert response.json()["verdict"] == "insufficient"
    record = route_env["lifecycle"].get_assignment(run_id)
    step = next(item for item in record["steps"]
                if item["step_id"] == "send")
    assert step["status"] == "uncertain"
    assert calls["count"] == 1


def test_route_reconcile_not_applied_allows_one_new_operation(route_env):
    run_id, calls = _uncertain_assignment(route_env)
    response = route_env["client"].post(
        f"/api/assignments/{run_id}/reconcile/send",
        json={"verdict": "not_applied",
              "evidence": "the provider audit proves no row was created"})
    assert response.status_code == 200, response.text
    assert response.json()["verdict"] == "not_applied"
    # The retry is a NEW operation and still needs approval; the failed
    # evidence is preserved.
    assert calls["count"] == 1
    record = route_env["lifecycle"].get_assignment(run_id)
    send = next(item for item in record["steps"]
                if item["step_id"] == "send")
    assert send["status"] == "awaiting_approval"
    assert send["attempts"] == 1
    operations = [
        item for item in route_env["lifecycle"].get_task(run_id)["operations"]
        if item.get("step_id") == "send"]
    assert len(operations) == 2

    approved = route_env["client"].post(
        f"/api/assignments/{run_id}/approve/send", json={})
    assert approved.status_code == 200, approved.text
    assert calls["count"] == 2
    record = route_env["lifecycle"].get_assignment(run_id)
    assert record["status"] == "completed"
    send = next(item for item in record["steps"]
                if item["step_id"] == "send")
    assert send["status"] == "applied"


def test_route_reconcile_requires_evidence_and_authority(route_env):
    run_id, _ = _uncertain_assignment(route_env)
    missing = route_env["client"].post(
        f"/api/assignments/{run_id}/reconcile/send",
        json={"verdict": "applied", "evidence": ""})
    assert missing.status_code == 409, missing.text

    route_env["current"]["user"] = route_env["users"]["member"]
    denied = route_env["client"].post(
        f"/api/assignments/{run_id}/reconcile/send",
        json={"verdict": "applied", "evidence": "outbox row"})
    assert denied.status_code == 403, denied.text


def test_standing_authority_requires_a_real_bound():
    from core.assignment_plan import normalize_standing_authority
    from core.task_lifecycle import TaskLifecycleError

    with pytest.raises(TaskLifecycleError):
        normalize_standing_authority(
            {"actions": ["outbound"], "max_effects": 0,
             "recipients": ["a@example.invalid"]}, granted_by="owner-1")
    with pytest.raises(TaskLifecycleError):
        normalize_standing_authority(
            {"actions": ["outbound"], "max_effects": 1},
            granted_by="owner-1")
    with pytest.raises(TaskLifecycleError):
        normalize_standing_authority(
            {"actions": ["crm_write"], "max_effects": 1,
             "recipients": ["a@example.invalid"]}, granted_by="owner-1")
    grant = normalize_standing_authority(
        {"actions": ["outbound"], "max_effects": 2,
         "recipients": ["A@Example.invalid"]}, granted_by="owner-1")
    assert grant["recipients"] == ["a@example.invalid"]
    assert grant["used_effects"] == 0
    assert grant["status"] == "active"


def test_over_limit_outbound_body_is_rejected_before_run_creation(
        route_env, tmp_path, monkeypatch):
    """A 20,001-byte executable body is a 422, not a truncated 20,000 body."""
    monkeypatch.setenv("ATOM_ASSIGNMENT_ALLOW_LIVE_SEND", "1")
    source = tmp_path / "records.csv"
    source.write_text("Item,Price\nA-1,10\nA-2,20\n", encoding="utf-8")
    response = route_env["client"].post("/api/assignments", json={
        "objective": "Oversized outbound payload must be refused",
        "sources": [{
            "kind": "workbook", "path": str(source),
            "sheet": "records", "columns": ["Item", "Price"],
        }],
        "outbound": {
            "to": ["owner@example.invalid"],
            "subject": "Oversized body",
            "body": "x" * 20_001,
            "canvas_id": "canvas-oversized",
        },
    })
    assert response.status_code == 422
    assert "20000 UTF-8 bytes" in response.text


def _waiting_route_assignment(env, *, adapter: str, waiting: dict) -> str:
    async def wait_step(inputs, context):
        raise WaitingForExternal(waiting)

    env["executor"].adapters.register(adapter, wait_step)
    default_adapter_registry.register(adapter, wait_step)
    plan = new_assignment(
        objective=f"Route cancel {uuid.uuid4().hex[:8]}",
        employee_id="owner-1",
        workspace_id="ws-1",
        tenant_id="tenant-1",
        teaching_snapshot=new_teaching_snapshot(revision="route-cancel-r1"),
        steps=[new_step(
            step_id="wait", title="Wait for an authorized reply",
            operation_type="retrieve", adapter=adapter, effect="read_only")],
    )
    record = env["executor"].create_assignment(
        "conv-cancel-route", plan["objective"], assignment=plan)
    _run(env["executor"].execute(record["run_id"]))
    return record["run_id"]


def _outbox_empty() -> bool:
    outbox = Path(os.environ["ATOM_ASSIGNMENT_OUTBOX"])
    return not outbox.exists() or not outbox.read_text().strip()


def test_budget_extension_raises_limits_without_restarting_the_job(route_env):
    env = route_env
    run_id = _waiting_route_assignment(
        env, adapter="test.route.cancel.correlated",
        waiting={
            "event": "email", "state": "waiting_for_external",
            "party": "supplier", "correlation_id": "corr-budget-route",
            "resume_on": "response", "detail": "reply on thread-budget",
        })
    before = env["lifecycle"].get_assignment(run_id)
    response = env["client"].post(
        f"/api/assignments/{run_id}/budget",
        json={"max_wall_seconds": 1800, "max_steps": 12,
              "reason": "held-out continuation recovery"})
    assert response.status_code == 200, response.text
    budget = response.json()["budget"]
    assert budget["max_wall_seconds"] >= 1800
    assert budget["max_steps"] >= 12
    assert budget["budget_extended_by"]
    assert budget["budget_extension_reason"] == (
        "held-out continuation recovery")
    after = env["lifecycle"].get_assignment(run_id)
    assert after["objective"] == before["objective"]
    assert [step["step_id"] for step in after["steps"]] == [
        step["step_id"] for step in before["steps"]]
    assert after["status"] == before["status"]

    # An increase-only route never lowers the owner's existing budget.
    lowered = env["client"].post(
        f"/api/assignments/{run_id}/budget",
        json={"max_wall_seconds": 1, "max_steps": 1})
    assert lowered.status_code == 200, lowered.text
    assert lowered.json()["budget"]["max_wall_seconds"] >= 1800
    assert lowered.json()["budget"]["max_steps"] >= 12


def test_cancel_clears_correlated_wait_and_refuses_late_reply(route_env):
    env = route_env
    run_id = _waiting_route_assignment(
        env, adapter="test.route.cancel.correlated",
        waiting={
            "event": "email", "state": "waiting_for_external",
            "party": "supplier", "correlation_id": "corr-cancel-route",
            "resume_on": "response", "detail": "reply on thread-route",
        })
    run = env["runs"].get_run(run_id)
    assert run["status"] == "waiting" and run["waiting_on"], run

    cancelled = env["client"].post(
        f"/api/assignments/{run_id}/cancel",
        json={"reason": "owner cancel"})
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["assignment"]["status"] == "cancelled"

    run = env["runs"].get_run(run_id)
    assert run["status"] == "cancelled", run
    assert run["waiting_on"] is None, run
    detail = env["executor"].status(run_id)
    assert detail["assignment"]["status"] == "cancelled"
    wait_step = next(step for step in detail["assignment"]["steps"]
                     if step["step_id"] == "wait")
    assert wait_step["status"] == "cancelled"
    # Historical wait record is preserved; only the live projection is cleared.
    assert (wait_step.get("waiting") or {}).get("correlation_id") == (
        "corr-cancel-route")

    # Fresh session, not the route dependency session.
    with env["factory"]() as fresh:
        row = fresh.query(GoalRun).filter(GoalRun.id == run_id).first()
        assert row is not None and row.status == "cancelled"
        assert row.waiting_on is None

    late = env["client"].post(
        f"/api/assignments/{run_id}/responses/corr-cancel-route",
        json={"response": "late reply after cancellation"})
    assert late.status_code == 409, late.text
    assert "cancelled" in late.json()["detail"].lower()
    run = env["runs"].get_run(run_id)
    assert run["status"] == "cancelled" and run["waiting_on"] is None
    assert _outbox_empty()

    again = env["client"].post(
        f"/api/assignments/{run_id}/cancel", json={"reason": "again"})
    assert again.status_code == 200
    assert again.json()["assignment"]["status"] == "cancelled"
    decisions = env["runs"].get_run(run_id)["decision_log"]
    assert sum(1 for item in decisions
               if item.get("kind") == "external_response_refused") == 1
    assert sum(1 for item in decisions
               if item.get("rationale") == "assignment cancelled: owner cancel"
               ) == 1
    assert all(item["id"] != run_id for item in
               env["runs"].list_runs(include_terminal=False))
    # The active-task consumer must not find cancelled work.
    assert env["lifecycle"].find_active_task("conv-cancel-route") is None

    read = env["client"].get(f"/api/assignments/{run_id}")
    assert read.status_code == 200, read.text
    assert read.json()["assignment"]["status"] == "cancelled"

    resumed = env["client"].post(f"/api/assignments/{run_id}/resume")
    assert resumed.status_code in (200, 409), resumed.text
    if resumed.status_code == 200:
        assert resumed.json()["assignment"]["status"] == "cancelled"
    assert _outbox_empty()


def test_cancel_clears_mapping_wait_and_refuses_gap_and_reply(route_env):
    env = route_env

    async def mapping_gap(inputs, context):
        raise NeedsContext({
            "concept": "column",
            "reason": "required column not found: Price",
            "question": "Which column should supply Price?",
            "checked_evidence": ["columns=['Item', 'Quantity', 'Unit Price']"],
            "next_retrieval": "confirm the column mapping",
            "kind": "missing_evidence",
            "inputs": {"mapping": {
                "concept": "Price", "sheet": "Records",
                "source_version": "v1",
                "candidates": [{"column": "Unit Price"}],
            }},
            "waiting": {
                "state": "waiting_for_person", "party": "owner",
                "resume_on": "answer", "correlation_id": "corr-map-cancel",
                "detail": "which column supplies Price",
            },
        })

    env["executor"].adapters.register("test.route.cancel.mapping", mapping_gap)
    default_adapter_registry.register(
        "test.route.cancel.mapping", mapping_gap)
    plan = new_assignment(
        objective="Route mapping cancel",
        employee_id="owner-1",
        workspace_id="ws-1",
        tenant_id="tenant-1",
        teaching_snapshot=new_teaching_snapshot(revision="route-cancel-r2"),
        steps=[new_step(
            step_id="read", title="Read the sheet",
            operation_type="retrieve",
            adapter="test.route.cancel.mapping", effect="read_only")],
    )
    record = env["executor"].create_assignment(
        "conv-cancel-route-map", plan["objective"], assignment=plan)
    run_id = record["run_id"]
    _run(env["executor"].execute(run_id))
    detail = env["executor"].status(run_id)
    assert detail["assignment"]["status"] == "waiting"
    gap = detail["open_gaps"][0]
    assert gap["kind"] == "missing_evidence"
    run = env["runs"].get_run(run_id)
    assert run["status"] == "waiting" and run["waiting_on"], run

    cancelled = env["client"].post(
        f"/api/assignments/{run_id}/cancel",
        json={"reason": "mapping run cancelled"})
    assert cancelled.status_code == 200, cancelled.text
    run = env["runs"].get_run(run_id)
    assert run["status"] == "cancelled" and run["waiting_on"] is None, run
    with env["factory"]() as fresh:
        row = fresh.query(GoalRun).filter(GoalRun.id == run_id).first()
        assert row.status == "cancelled" and row.waiting_on is None

    revived = env["client"].post(
        f"/api/assignments/{run_id}/gaps/{gap['question_id']}/resolve",
        json={"resolution": "Unit Price"})
    assert revived.status_code == 409, revived.text
    assert "cancelled" in revived.json()["detail"].lower()

    late = env["client"].post(
        f"/api/assignments/{run_id}/responses/corr-map-cancel",
        json={"response": "late mapping reply"})
    assert late.status_code == 409, late.text
    assert _outbox_empty()
    assert env["executor"].status(run_id)["assignment"]["status"] == (
        "cancelled")


def test_quote_journey_uses_sources_and_taught_line_discount(
        route_env, tmp_path, monkeypatch):
    """Multi-source quote with a taught exception yields the 362.50 fixture.

    Independent expected arithmetic:
      A 2 x 100.00            = 200.00
      B 3 x 50.00, 5% on B    = 142.50
      freight                 =  20.00
      explicit no tax         =   0.00
      total                   = 362.50
    """
    import docx
    from core.student_learning_service import deliver_teacher_lesson

    _scotch_catalog(route_env, tmp_path, monkeypatch)
    agreement = tmp_path / "brennan-customer-agreement.docx"
    document = docx.Document()
    document.add_paragraph("Customer: Acme Fabrication")
    document.add_paragraph("Agreement: AF-2026")
    document.add_paragraph(
        "Taught exception: category B lines carry a 5% contract discount.")
    document.save(agreement)

    agent_id = _teaching_agent(
        route_env, "Quote employee", "Arial", "quote-reviewer")
    deliver_teacher_lesson(
        route_env["db"], agent_id,
        "Apply the customer agreement discount exception",
        topic="quote discount", applies_to=["document"],
        format_spec={
            "font_name": "Arial",
            "line_discount_rules": [{
                "lesson_id": "quote-category-b",
                "revision": 1,
                "name": "category B contract discount",
                "when": {"category": "B"},
                "rate": "0.05",
            }],
        },
        context={"audience": "quote-reviewer"}, workspace_id="ws-1")

    response = route_env["client"].post("/api/assignments", json={
        "objective": "Prepare the Acme quote using the governing agreement",
        "agent_id": agent_id,
        "sources": [
            {
                "kind": "workbook",
                "dataset_name": "scotch_parts_price_list",
                "sheet": "US$ SCOTCH PARTS",
            },
            {"kind": "document", "path": str(agreement)},
        ],
        "calculation": {
            "line_items": [
                {"item_id": "A", "category": "A", "quantity": "2",
                 "unit": "each", "pack_size": "1",
                 "unit_price": "100.00", "price_basis": "contract",
                 "currency": "USD"},
                {"item_id": "B", "category": "B", "quantity": "3",
                 "unit": "each", "pack_size": "1",
                 "unit_price": "50.00", "price_basis": "contract",
                 "currency": "USD"},
            ],
            "currency": "USD",
            "freight": "20.00",
            "tax": {"basis": "none"},
            "rounding": "half_up",
            "scale": 2,
            "rounding_authority": "customer agreement AF-2026",
        },
        "deliverables": [{"kind": "document", "description": "Acme quote"}],
        "task_context": {"audience": "quote-reviewer"},
    })
    assert response.status_code == 200, response.text
    body = response.json()
    assignment = body["assignment"]["assignment"]
    assert assignment["status"] == "completed", assignment
    internal = route_env["lifecycle"].get_assignment(body["run_id"])
    calc = next(step for step in internal["steps"]
                if step["step_id"] == "calculate")
    assert calc["result"]["value"] == "362.50"
    receipt = calc["result"]["calculation_receipt"]
    assert receipt["subtotal"] == "342.50"
    assert receipt["total"] == "362.50"
    assert receipt["tax"]["basis"] == "none"
    assert receipt["rounding_authority"] == "customer agreement AF-2026"
    assert receipt["discount_rules"][0]["lesson_id"] == "quote-category-b"
    assert [row["discount_rate"] for row in calc["result"]["rows"]] == [
        "0", "0.05"]

    deliverable = next(item for item in assignment["deliverables"]
                       if item["kind"] == "document")
    text = "\n".join(
        paragraph.text for paragraph in docx.Document(
            deliverable["artifact_path"]).paragraphs)
    for table in docx.Document(deliverable["artifact_path"]).tables:
        for row in table.rows:
            text += "\n" + " | ".join(cell.text for cell in row.cells)
    assert "362.50" in text, text
    assert "scotch-parts.xlsx" in text, text
    assert "brennan-customer-agreement.docx" in text, text

    evidence_dir = os.getenv("ATOM_BRENNAN_EVIDENCE_DIR")
    if evidence_dir:
        os.makedirs(evidence_dir, exist_ok=True)
        stored = os.path.join(evidence_dir, "acme-quote.docx")
        shutil.copy2(deliverable["artifact_path"], stored)
        payload = {
            "slice": "controlled-quote-journey",
            "controlled": True,
            "live_connected": False,
            "objective": "Prepare the Acme quote using the governing agreement",
            "run_id": body["run_id"],
            "assignment_id": assignment["assignment_id"],
            "plan_revision": assignment["plan_revision"],
            "teaching_revision": body.get("teaching_revision"),
            "teaching_fingerprint": assignment.get("teaching_fingerprint"),
            "sources": internal.get("sources") or [],
            "calculation_receipt": receipt,
            "calculation_rows": calc["result"]["rows"],
            "expected_total_independent": "362.50",
            "artifact_path": deliverable["artifact_path"],
            "stored_artifact": stored,
            "artifact_sha256": deliverable.get("sha256"),
            "artifact_text": text,
            "status_after_build": assignment["status"],
        }
        with open(os.path.join(
                evidence_dir, "quote_journey.json"), "w") as handle:
            json.dump(payload, handle, indent=2, default=str)


def test_service_proposal_route_uses_the_same_assignment_api(
        route_env, tmp_path, monkeypatch):
    """Portability: hours/rates/CAD through the public route, no quote lesson.

    Independent arithmetic: 4 x 120.00 + 2 x 75.00 = 630.00 CAD.
    """
    import docx

    scope = tmp_path / "service-scope.txt"
    scope.write_text(
        "Service scope: four consulting hours and two site trips.\n")
    response = route_env["client"].post("/api/assignments", json={
        "objective": "Prepare a service proposal for the site visit",
        "sources": [{"kind": "document", "path": str(scope)}],
        "calculation": {
            "line_items": [
                {"item_id": "consulting-hours", "quantity": "4",
                 "unit": "hour", "pack_size": "1", "unit_price": "120.00",
                 "price_basis": "rate", "currency": "CAD"},
                {"item_id": "site-trips", "quantity": "2", "unit": "trip",
                 "pack_size": "1", "unit_price": "75.00",
                 "price_basis": "rate", "currency": "CAD"},
            ],
            "currency": "CAD", "freight": "0", "tax": {"basis": "none"},
            "rounding": "half_up", "scale": 2,
            "rounding_authority": "service rate card",
        },
        "deliverables": [{"kind": "document",
                          "description": "Service proposal"}],
    })
    assert response.status_code == 200, response.text
    body = response.json()
    assignment = body["assignment"]["assignment"]
    assert assignment["status"] == "completed", assignment
    internal = route_env["lifecycle"].get_assignment(body["run_id"])
    calc = next(step for step in internal["steps"]
                if step["step_id"] == "calculate")
    assert calc["result"]["value"] == "630.00"
    assert calc["result"]["calculation_receipt"]["currency"] == "CAD"
    deliverable = next(item for item in assignment["deliverables"]
                       if item["kind"] == "document")
    text = "\n".join(
        paragraph.text for paragraph in docx.Document(
            deliverable["artifact_path"]).paragraphs)
    for table in docx.Document(deliverable["artifact_path"]).tables:
        for row in table.rows:
            text += "\n" + " | ".join(cell.text for cell in row.cells)
    assert "630.00" in text, text
    assert "consulting-hours" in text or "Service" in text


def _start_quote(route_env, tmp_path, monkeypatch, agent_id, *, customer="Acme",
                 actions=None, email_draft=False):
    import docx

    if route_env["db"].query(DatasetEntry).filter(
            DatasetEntry.id == "scotch-entry").first() is None:
        _scotch_catalog(route_env, tmp_path, monkeypatch)
    agreement = tmp_path / f"{customer.lower()}-agreement.docx"
    document = docx.Document()
    document.add_paragraph(f"Customer: {customer}")
    document.add_paragraph("Agreement: AF-2026")
    document.save(agreement)
    return route_env["client"].post("/api/assignments", json={
        "objective": f"Prepare the {customer} quote",
        "agent_id": agent_id,
        "sources": [
            {"kind": "workbook",
             "dataset_name": "scotch_parts_price_list",
             "sheet": "US$ SCOTCH PARTS"},
            {"kind": "document", "path": str(agreement)},
        ],
        "calculation": {
            "line_items": [
                {"item_id": "A", "category": "A", "quantity": "2",
                 "unit": "each", "pack_size": "1",
                 "unit_price": "100.00", "price_basis": "contract",
                 "currency": "USD"},
                {"item_id": "B", "category": "B", "quantity": "3",
                 "unit": "each", "pack_size": "1",
                 "unit_price": "50.00", "price_basis": "contract",
                 "currency": "USD"},
            ],
            "currency": "USD", "freight": "20.00",
            "tax": {"basis": "none"}, "rounding": "half_up", "scale": 2,
            "rounding_authority": "agreement AF-2026",
        },
        "actions": list(actions or []),
        "deliverables": (
            [{"kind": "document", "description": "Quote"}]
            + ([{"kind": "email_draft", "step_id": "email-draft",
                 "description": "Quote email",
                 "to": ["buyer@example.invalid"],
                 "subject": "Acme quote"}] if email_draft else [])),
        "task_context": {"audience": "quote-reviewer"},
    })


def _quote_lesson(route_env, agent_id, rate, name):
    from core.student_learning_service import deliver_teacher_lesson

    deliver_teacher_lesson(
        route_env["db"], agent_id, name,
        topic="quote discount", applies_to=["document"],
        format_spec={
            "font_name": "Arial",
            "line_discount_rules": [{
                "lesson_id": "quote-category-b",
                "revision": 1,
                "name": name,
                "when": {"category": "B"},
                "rate": rate,
            }],
        },
        context={"audience": "quote-reviewer"}, workspace_id="ws-1")


def test_teaching_correction_preserves_snapshot_and_reassessment_invalidates(
        route_env, tmp_path, monkeypatch):
    from core.student_learning_service import (
        list_agent_lessons, update_teaching_point,
    )

    agent_id = _teaching_agent(
        route_env, "Correctable quote employee", "Arial", "quote-reviewer")
    _quote_lesson(route_env, agent_id, "0.05", "5% category B")
    first = _start_quote(route_env, tmp_path, monkeypatch, agent_id)
    assert first.status_code == 200, first.text
    first_body = first.json()
    assert first_body["assignment"]["assignment"]["status"] == "completed"
    run_id = first_body["run_id"]
    before = route_env["lifecycle"].get_assignment(run_id)
    before_calc = next(step for step in before["steps"]
                       if step["step_id"] == "calculate")
    assert before_calc["result"]["value"] == "362.50"
    before_revision = before["teaching_snapshot"]["revision"]

    point = next(
        item for item in list_agent_lessons(route_env["db"], agent_id)
        if item.get("topic") == "quote discount")
    corrected = update_teaching_point(
        route_env["db"], agent_id, point["id"],
        text="Use the corrected 10% category B exception",
        format_spec={"line_discount_rules": [{
            "lesson_id": "quote-category-b", "revision": 2,
            "name": "10% category B", "when": {"category": "B"},
            "rate": "0.10"}]})
    assert corrected["status"] == "ok", corrected

    # Active/completed work keeps its accepted snapshot.
    retained = route_env["lifecycle"].get_assignment(run_id)
    assert retained["teaching_snapshot"]["revision"] == before_revision
    assert retained["steps"][-1]["status"] in ("applied", "pending")
    assert next(step for step in retained["steps"]
                if step["step_id"] == "calculate"
                )["result"]["value"] == "362.50"

    # New work adopts the correction.
    second = _start_quote(
        route_env, tmp_path, monkeypatch, agent_id, customer="Acme Two")
    assert second.status_code == 200, second.text
    second_body = second.json()
    assert second_body["assignment"]["assignment"]["status"] == "completed"
    second_calc = next(
        step for step in route_env["lifecycle"].get_assignment(
            second_body["run_id"])["steps"]
        if step["step_id"] == "calculate")
    assert second_calc["result"]["value"] == "355.00", second_calc["result"]

    # Explicit reassessment adopts the correction for the old job and
    # invalidates its derived calculation/deliverable, preserving prior work.
    reassessed = route_env["client"].post(
        f"/api/assignments/{run_id}/reassess",
        json={"reason": "pricing owner corrected the exception"})
    assert reassessed.status_code == 200, reassessed.text
    body = reassessed.json()
    assert body["status"] == "reassessed"
    assert "calculate" in body["affected_steps"]
    assert "source-1" in body["preserved_steps"]
    after = route_env["lifecycle"].get_assignment(run_id)
    assert after["plan_revision"] == retained["plan_revision"] + 1
    calc = next(step for step in after["steps"]
                if step["step_id"] == "calculate")
    assert calc["status"] == "applied"
    assert calc["result"]["value"] == "355.00"
    assert calc["prior_results"], calc
    assert calc["prior_results"][-1]["result"]["value"] == "362.50"
    assert after["teaching_snapshot"]["revision"] != before_revision
    assert after["teaching_history"], after
    assert after["teaching_history"][-1]["revision"] == before_revision
    deliverable = next(item for item in after["deliverables"]
                       if item["kind"] == "document")
    assert deliverable["artifact_path"].endswith(".docx")
    assert deliverable["status"] == "applied"

    evidence_dir = os.getenv("ATOM_BRENNAN_EVIDENCE_DIR")
    if evidence_dir:
        os.makedirs(evidence_dir, exist_ok=True)
        stored = os.path.join(evidence_dir, "acme-quote-corrected.docx")
        shutil.copy2(deliverable["artifact_path"], stored)
        payload = {
            "slice": "teaching-correction-reassessment",
            "controlled": True,
            "before_teaching_revision": before_revision,
            "after_teaching_revision": after["teaching_snapshot"]["revision"],
            "old_plan_revision": retained["plan_revision"],
            "new_plan_revision": after["plan_revision"],
            "teaching_history": after.get("teaching_history") or [],
            "affected_steps": body["affected_steps"],
            "preserved_steps": body["preserved_steps"],
            "before_total": calc["prior_results"][-1]["result"]["value"],
            "after_total": calc["result"]["value"],
            "new_work_total": second_calc["result"]["value"],
            "stored_artifact": stored,
            "artifact_revision": deliverable.get("artifact_revision"),
        }
        with open(os.path.join(
                evidence_dir, "teaching_correction.json"), "w") as handle:
            json.dump(payload, handle, indent=2, default=str)


def test_quote_controlled_commercial_update_duplicate_and_uncertain(
        route_env, tmp_path, monkeypatch):
    """Document -> registered commercial update -> email draft.

    The controlled action stands in for Agent 2's Zoho write; the executor
    operation id is the idempotency identity. A lost provider response is
    uncertain and must reconcile without a second call.
    """
    from core.action_registry import action_registry
    from core.assignment_executor import ExternalOutcomeUnknown

    action_name = f"test.quote.update.{uuid.uuid4().hex[:8]}"
    calls = []

    async def controlled_update(args, context):
        calls.append({"args": dict(args), "run_id": context.get("run_id"),
                      "operation": context.get("assignment_id")})
        if args.get("mode") == "uncertain":
            raise ExternalOutcomeUnknown(
                "provider accepted the update then lost the response",
                "controlled-readback:deal-1:v2")
        return {
            "status": "applied",
            "record_id": "deal-1",
            "version": "v2",
            "readback": {
                "record_id": "deal-1",
                "quote_total": args.get("quote_total"),
                "version": "v2",
            },
        }

    action_registry.register(
        action_name, controlled_update,
        description="Controlled commercial record update",
        effects=[{"effect": "record_created", "object": "deal"}])

    async def verify_update(ctx):
        from core.oracle import OracleResult

        return OracleResult(
            action_name,
            ctx.get("status") == "applied"
            and ctx.get("record_id") == "deal-1"
            and (ctx.get("readback") or {}).get("version") == "v2",
            "controlled readback version v2 for deal-1",
        )

    from core.oracle import register_postcondition

    register_postcondition(action_name)(verify_update)

    agent_id = _teaching_agent(
        route_env, "Commercial quote employee", "Arial", "quote-reviewer")
    _quote_lesson(route_env, agent_id, "0.05", "5% category B")

    def update_spec(**overrides):
        spec = {
            "step_id": "commercial-update",
            "action": action_name,
            "title": "Create the Zoho commercial record",
            "arguments": {"quote_total": "362.50", "deal": "deal-1"},
            "target": {"record_id": "deal-1"},
            "permitted_fields": ["quote_total", "validity"],
            "expected_version": "v1",
            "approval_purpose": "Create the quote in Zoho",
        }
        spec.update(overrides)
        return spec

    started = _start_quote(
        route_env, tmp_path, monkeypatch, agent_id,
        actions=[update_spec()], email_draft=True)
    assert started.status_code == 200, started.text
    body = started.json()
    run_id = body["run_id"]
    assignment = body["assignment"]["assignment"]
    assert assignment["status"] == "waiting", assignment
    action_step = next(step for step in assignment["steps"]
                       if step["step_id"] == "commercial-update")
    assert action_step["status"] == "awaiting_approval", action_step
    assert action_step["depends_on"] == ["source-1", "source-2",
                                         "calculate", "deliverable-1"]
    draft_step = next(step for step in assignment["steps"]
                      if step["step_id"] == "email-draft")
    assert "commercial-update" in draft_step["depends_on"]
    assert calls == []

    approved = route_env["client"].post(
        f"/api/assignments/{run_id}/approve/commercial-update",
        json={"note": "bounded commercial update"})
    assert approved.status_code == 200, approved.text
    completed = approved.json()["assignment"]
    assert completed["assignment"]["status"] == "completed", completed
    assert len(calls) == 1, calls
    internal_completed = route_env["lifecycle"].get_assignment(run_id)
    updated = next(step for step in internal_completed["steps"]
                   if step["step_id"] == "commercial-update")
    assert updated["result"]["data"]["readback"]["record_id"] == "deal-1"
    draft = next(step for step in internal_completed["steps"]
                 if step["step_id"] == "email-draft")
    assert draft["status"] == "applied"
    assert "362.50" in str(draft["result"].get("draft") or
                           draft["result"].get("body") or "")

    # Duplicate resume/approval replay must not repeat the effect.
    again = route_env["client"].post(
        f"/api/assignments/{run_id}/resume", json={})
    assert again.status_code == 200, again.text
    assert len(calls) == 1, calls

    # Uncertain provider outcome: one call, marked uncertain, reconciled
    # against the existing operation without a resend.
    uncertain = _start_quote(
        route_env, tmp_path, monkeypatch, agent_id, customer="Acme Uncertain",
        actions=[update_spec(arguments={"quote_total": "362.50",
                                        "deal": "deal-1",
                                        "mode": "uncertain"})])
    assert uncertain.status_code == 200, uncertain.text
    uncertain_run = uncertain.json()["run_id"]
    approved = route_env["client"].post(
        f"/api/assignments/{uncertain_run}/approve/commercial-update",
        json={"note": "bounded commercial update"})
    assert approved.status_code == 200, approved.text
    status = route_env["client"].get(
        f"/api/assignments/{uncertain_run}").json()
    assert status["assignment"]["status"] == "blocked", status
    uncertain_step = next(step for step in status["assignment"]["steps"]
                          if step["step_id"] == "commercial-update")
    assert uncertain_step["status"] == "uncertain"
    assert len(calls) == 2, calls

    reconciled = route_env["client"].post(
        f"/api/assignments/{uncertain_run}/reconcile/commercial-update",
        json={"verdict": "applied",
              "evidence": "provider readback shows deal-1 at v2",
              "evidence_ref": "controlled-readback:deal-1:v2"})
    assert reconciled.status_code == 200, reconciled.text
    assert len(calls) == 2, calls

    # Cancellation before approval: no late event revives the commercial
    # effect, and no provider call occurs.
    cancelled = _start_quote(
        route_env, tmp_path, monkeypatch, agent_id, customer="Acme Cancel",
        actions=[update_spec(step_id="commercial-update")])
    assert cancelled.status_code == 200, cancelled.text
    cancelled_run = cancelled.json()["run_id"]
    before_cancel_calls = len(calls)
    stopped = route_env["client"].post(
        f"/api/assignments/{cancelled_run}/cancel",
        json={"reason": "customer withdrew the RFQ"})
    assert stopped.status_code == 200, stopped.text
    assert stopped.json()["assignment"]["status"] == "cancelled"
    late = route_env["client"].post(
        f"/api/assignments/{cancelled_run}/approve/commercial-update",
        json={"note": "late approval"})
    assert late.status_code in (404, 409), late.text
    assert len(calls) == before_cancel_calls


def test_quote_missing_tax_is_a_typed_clarification_not_zero(
        route_env, tmp_path, monkeypatch):
    _scotch_catalog(route_env, tmp_path, monkeypatch)
    agent_id = _teaching_agent(
        route_env, "Clarifying quote employee", "Arial", "quote-reviewer")
    _quote_lesson(route_env, agent_id, "0.05", "5% category B")
    response = route_env["client"].post("/api/assignments", json={
        "objective": "Prepare a quote with an unstated tax treatment",
        "agent_id": agent_id,
        "sources": [
            {"kind": "workbook",
             "dataset_name": "scotch_parts_price_list",
             "sheet": "US$ SCOTCH PARTS"},
        ],
        "calculation": {
            "line_items": [{
                "item_id": "A", "category": "A", "quantity": "1",
                "unit": "each", "pack_size": "1", "unit_price": "10.00",
                "price_basis": "contract", "currency": "USD"}],
            "currency": "USD", "freight": "0",
            "rounding": "half_up", "scale": 2,
            "rounding_authority": "agreement",
        },
        "deliverables": [{"kind": "document", "description": "Quote"}],
        "task_context": {"audience": "quote-reviewer"},
    })
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["assignment"]["assignment"]["status"] == "waiting", body
    gaps = body["assignment"]["open_gaps"]
    assert any(gap.get("concept") == "quote_input" for gap in gaps), gaps
    tax_question = next(
        gap for gap in gaps if gap.get("concept") == "quote_input")
    assert "tax" in tax_question["question"].lower()
    calc = next(step for step in body["assignment"]["assignment"]["steps"]
                if step["step_id"] == "calculate")
    assert calc["status"] == "waiting"
    assert calc["result_value"] is None


def test_source_revision_change_invalidates_dependent_artifact(
        route_env, tmp_path, monkeypatch):
    import pandas as pd

    agent_id = _teaching_agent(
        route_env, "Source change employee", "Arial", "quote-reviewer")
    _quote_lesson(route_env, agent_id, "0.05", "5% category B")
    started = _start_quote(route_env, tmp_path, monkeypatch, agent_id)
    assert started.status_code == 200, started.text
    body = started.json()
    run_id = body["run_id"]
    before = route_env["lifecycle"].get_assignment(run_id)
    before_doc = next(item for item in before["deliverables"]
                      if item["kind"] == "document")
    assert before_doc["status"] == "applied"
    before_revision = before_doc["artifact_revision"]

    # The authorized source is revised while the job is retained.
    parquet = tmp_path / "sheet_datasets" / "scotch-parts.parquet"
    frame = pd.read_parquet(parquet)
    frame.loc[0, "Description"] = "Changed Scotch A"
    frame.to_parquet(parquet, index=False)

    invalidated = route_env["client"].post(
        f"/api/assignments/{run_id}/invalidate/source-1",
        json={"reason": "authorized source revision changed"})
    assert invalidated.status_code == 200, invalidated.text
    result = invalidated.json()
    assert "source-1" in result["affected_steps"]
    status = result["assignment"]
    assert status["assignment"]["status"] == "completed", status
    after = route_env["lifecycle"].get_assignment(run_id)
    assert after["plan_revision"] == before["plan_revision"] + 1
    source_step = next(step for step in after["steps"]
                       if step["step_id"] == "source-1")
    assert source_step["status"] == "applied"
    before_rows = next(step for step in before["steps"]
                       if step["step_id"] == "source-1")["result"]["rows"]
    assert source_step["result"]["rows"] != before_rows
    after_doc = next(item for item in after["deliverables"]
                     if item["kind"] == "document")
    assert after_doc["status"] == "applied"
    assert after_doc["artifact_revision"] != before_revision
    calc = next(step for step in after["steps"]
                if step["step_id"] == "calculate")
    assert calc["result"]["value"] == "362.50"
    assert calc["prior_results"], calc
    deliverable_step = next(step for step in after["steps"]
                            if step["step_id"] == "deliverable-1")
    assert deliverable_step["prior_results"], deliverable_step
    text = "\n".join(
        paragraph.text for paragraph in __import__("docx").Document(
            after_doc["artifact_path"]).paragraphs)
    for table in __import__("docx").Document(
            after_doc["artifact_path"]).tables:
        for row in table.rows:
            text += "\n" + " | ".join(cell.text for cell in row.cells)
    assert "Changed Scotch A" in text, text


def test_quote_same_sku_different_pack_asks_before_arithmetic(
        route_env, tmp_path, monkeypatch):
    _scotch_catalog(route_env, tmp_path, monkeypatch)
    agent_id = _teaching_agent(
        route_env, "Ambiguity quote employee", "Arial", "quote-reviewer")
    response = route_env["client"].post("/api/assignments", json={
        "objective": "Quote the ambiguous SKU",
        "agent_id": agent_id,
        "sources": [
            {"kind": "workbook",
             "dataset_name": "scotch_parts_price_list",
             "sheet": "US$ SCOTCH PARTS"},
        ],
        "calculation": {
            "line_items": [
                {"item_id": "SKU-1", "category": "A", "quantity": "1",
                 "unit": "each", "pack_size": "10", "unit_price": "10.00",
                 "price_basis": "contract", "currency": "USD"},
                {"item_id": "SKU-1", "category": "A", "quantity": "1",
                 "unit": "case", "pack_size": "25", "unit_price": "20.00",
                 "price_basis": "contract", "currency": "USD"},
            ],
            "currency": "USD", "freight": "0", "tax": {"basis": "none"},
            "rounding": "half_up", "scale": 2,
            "rounding_authority": "agreement",
        },
        "deliverables": [{"kind": "document", "description": "Quote"}],
        "task_context": {"audience": "quote-reviewer"},
    })
    assert response.status_code == 200, response.text
    body = response.json()
    assignment = body["assignment"]["assignment"]
    assert assignment["status"] == "waiting", assignment
    gap = next(item for item in body["assignment"]["open_gaps"]
               if item.get("concept") == "packaging_identity")
    assert "SKU-1" in gap["question"]
    calc = next(step for step in assignment["steps"]
                if step["step_id"] == "calculate")
    assert calc["status"] == "waiting"
    assert calc["result_value"] is None
    deliverable = next(step for step in assignment["steps"]
                       if step["step_id"] == "deliverable-1")
    assert deliverable["status"] == "pending"


def test_unsupported_pricing_rule_refuses_public_plan_and_effect(
        route_env, tmp_path):
    """A cap/fixed rule cannot produce a completed quote or action call."""
    from core.action_registry import action_registry
    import uuid

    calls = []

    async def commercial_update(args, context):
        calls.append(dict(args))
        return {"status": "applied", "remote_id": "should-not-run"}

    action_name = f"test.pricing.unsupported.{uuid.uuid4().hex[:8]}"
    action_registry.register(
        action_name, commercial_update,
        effects=[{"effect": "create", "object": "estimate"}])
    agent_id = _teaching_agent(
        route_env, "Pricing rejection employee", "Arial", "quote-reviewer")
    agreement = tmp_path / "agreement.txt"
    agreement.write_text("Customer: Acme\n", encoding="utf-8")

    response = route_env["client"].post("/api/assignments", json={
        "objective": "Prepare a quote with an unsupported capped discount",
        "agent_id": agent_id,
        "sources": [{
            "kind": "document", "representation": "file",
            "internal_fixture": True, "path": str(agreement),
            "resource_id": "agreement-1",
        }],
        "calculation": {
            "line_items": [{
                "item_id": "B", "category": "B", "quantity": "2",
                "unit": "each", "pack_size": "1",
                "unit_price": "100.00", "price_basis": "contract",
                "currency": "USD",
            }],
            "currency": "USD", "freight": "0",
            "tax": {"basis": "none"},
            "discount_rules": [{
                "name": "capped", "when": {"category": "B"},
                "rate": "0.10", "cap": "5.00",
            }],
        },
        "actions": [{
            "action": action_name,
            "arguments": {"quote_total": "190.00"},
            "approval_purpose": "Create the quote",
        }],
        "deliverables": [{"kind": "document", "description": "Quote"}],
        "task_context": {"audience": "quote-reviewer"},
    })

    assert response.status_code in (400, 422), response.text
    assert "unsupported" in response.text.lower()
    assert calls == []


def test_onedrive_xlsx_public_route_uses_production_parser(
        route_env, tmp_path, monkeypatch):
    import io
    import openpyxl
    from core import connected_actions

    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.append(["sku", "category", "quantity", "unit", "pack",
                  "unit_price", "currency", "discount_percent"])
    sheet.append(["A", "A", 2, "each", 1, "10.00", "USD", 0])
    sheet.append(["B", "B", 3, "each", 1, "20.00", "USD", 0])
    buffer = io.BytesIO()
    workbook.save(buffer)
    content = buffer.getvalue()

    class FakeOneDrive:
        async def get_access_token_resolution(self, user_id):
            return "token", {"state": "ok"}

        async def get_file_metadata(self, token, file_id):
            return {"status": "success",
                    "data": {"id": file_id, "name": "price-list.xlsx",
                             "version": "v1"}}

        async def download_file_bytes(self, token, file_id):
            return content

    async def fake_service(ids):
        return FakeOneDrive()

    monkeypatch.setattr(connected_actions, "_onedrive_service", fake_service)
    monkeypatch.setenv("ATOM_ASSIGNMENT_ALLOW_PROPOSED_STEPS", "1")
    source = tmp_path / "agreement.txt"
    source.write_text("Customer: Acme\n", encoding="utf-8")

    read = new_step(
        step_id="read", title="Read the OneDrive price workbook",
        operation_type="retrieve", adapter="action.registry",
        effect="read_only",
        inputs={"action": "connected.onedrive.read_file",
                "arguments": {"file_id": "xlsx-1",
                              "evidence_kind": "price_rows"}})
    map_rows = new_step(
        step_id="map", title="Map workbook rows",
        operation_type="calculate", adapter="quote.lines_from_rows",
        depends_on=["read"], effect="local",
        inputs={
            "rows": {"$ref": "read.data.rows"},
            "columns": {
                "item_id": "sku", "quantity": "quantity", "unit": "unit",
                "pack_size": "pack", "unit_price": "unit_price",
                "currency": "currency", "description": "sku",
                "category": "category", "discount": "discount_percent",
            },
            "defaults": {"price_basis": "contract"},
            "discount_mode": "percent",
            "discount_authority": "price-list:v1",
            "source_identity": {
                "resource_id": {"$ref": "read.data.read_receipt.resource_id"},
                "version": {"$ref": "read.data.read_receipt.version"},
                "sha256": {"$ref": "read.data.read_receipt.fields.sha256"},
            },
        })
    calculate = new_step(
        step_id="calculate", title="Calculate the workbook quote",
        operation_type="calculate", adapter="quote.calculate",
        depends_on=["map"], effect="local",
        inputs={"line_items": {"$ref": "map.line_items"},
                "currency": "USD", "freight": "0",
                "tax": {"basis": "none"}, "discount_rules": []})
    email = new_step(
        step_id="email-draft", title="Prepare the quote email",
        operation_type="present", adapter="email.draft",
        depends_on=["calculate"], effect="local",
        inputs={"to": ["buyer@example.invalid"], "subject": "Quote",
                "body": "Total ${calculate.value} USD"})

    response = route_env["client"].post("/api/assignments", json={
        "objective": "Quote from a OneDrive workbook",
        "agent_id": _teaching_agent(
            route_env, "OneDrive employee", "Arial", "quote-reviewer"),
        "sources": [{
            "kind": "document", "representation": "file",
            "internal_fixture": True, "path": str(source),
            "resource_id": "agreement-1",
        }],
        "proposed_steps": [read, map_rows, calculate, email],
        "authorized_actions": ["retrieve", "calculate", "edit"],
        "deliverables": [{
            "kind": "email_draft", "step_id": "email-draft",
            "description": "Quote email", "to": ["buyer@example.invalid"],
            "subject": "Quote", "body": "Total ${calculate.value} USD",
        }],
        "task_context": {"audience": "quote-reviewer"},
    })
    assert response.status_code == 200, response.text
    run_id = response.json()["run_id"]
    assignment = route_env["lifecycle"].get_assignment(run_id)
    read_step = next(step for step in assignment["steps"]
                     if step["step_id"] == "read")
    returned = read_step["result"]["data"]
    assert returned["read_receipt"]["version"] == "v1"
    assert returned["read_receipt"]["coverage"] == "complete"
    assert returned["read_receipt"]["fields"]["sha256"]
    assert len(returned["rows"]) == 2
    calc = next(step for step in assignment["steps"]
                if step["step_id"] == "calculate")
    assert calc["result"]["value"] == "80.00"
    assert all(row["source_ref"]["version"] == "v1"
               for row in calc["result"]["rows"])


def _qualified_discount_quote(route_env, tmp_path, *, label, rules):
    scope = tmp_path / f"{label}.txt"
    scope.write_text("Customer: Acme\\nQualification: pending\\n")
    return route_env["client"].post("/api/assignments", json={
        "objective": f"Qualify the {label} line",
        "sources": [{"kind": "document", "path": str(scope)}],
        "calculation": {
            "line_items": [{
                "item_id": "B", "category": "B", "quantity": "1",
                "unit": "each", "pack_size": "1", "unit_price": "100.00",
                "price_basis": "contract", "currency": "USD"}],
            "currency": "USD", "freight": "0", "tax": {"basis": "none"},
            "discount_rules": rules,
            "rounding": "half_up", "scale": 2,
            "rounding_authority": "agreement AF-2026",
        },
        "deliverables": [{"kind": "document",
                          "description": "Qualified quote"}],
        "task_context": {"audience": "quote-reviewer"},
    })


def test_quote_missing_qualification_waits_and_resolves_through_route(
        route_env, tmp_path):
    """Missing qualification is a public-route gap, not an assumed answer.

    Independent arithmetic: 1 x 100.00 less the licensed 10% = 90.00.
    """
    rules = [
        {"lesson_id": "general-b", "revision": 1, "name": "general B",
         "when": {"category": "B"}, "rate": "0.05"},
        {"lesson_id": "licensed-b", "revision": 1, "name": "licensed B",
         "when": {"category": "B", "qualification": "licensed"},
         "rate": "0.10"},
    ]
    response = _qualified_discount_quote(
        route_env, tmp_path, label="licensed", rules=rules)
    assert response.status_code == 200, response.text
    body = response.json()
    run_id = body["run_id"]
    assignment = body["assignment"]["assignment"]
    assert assignment["status"] == "waiting", assignment
    gap = next(item for item in body["assignment"]["open_gaps"]
               if item.get("concept") == "discount_scope")
    assert "qualification" in gap["question"].lower(), gap
    calc = next(step for step in assignment["steps"]
                if step["step_id"] == "calculate")
    assert calc["status"] == "waiting"
    assert calc["result_value"] is None

    resolved = route_env["client"].post(
        f"/api/assignments/{run_id}/gaps/{gap['question_id']}/resolve",
        json={"resolution": "licensed",
              "resolved_by": "pricing owner",
              "evidence": "accepted customer qualification: licensed"})
    assert resolved.status_code == 200, resolved.text
    completed = resolved.json()["assignment"]
    assert completed["status"] == "completed", completed
    internal = route_env["lifecycle"].get_assignment(run_id)
    calc = next(step for step in internal["steps"]
                if step["step_id"] == "calculate")
    assert calc["result"]["value"] == "90.00"
    assert calc["result"]["rows"][0]["discount_rate"] == "0.10"
    assert calc["result"]["rows"][0]["discount_rule"]["lesson_id"] == (
        "licensed-b")
    assert calc["result"]["calculation_receipt"]["rounding_authority"] == (
        "agreement AF-2026")

    replay = route_env["client"].post(
        f"/api/assignments/{run_id}/gaps/{gap['question_id']}/resolve",
        json={"resolution": "licensed"})
    assert replay.status_code == 200, replay.text
    assert replay.json()["status"] == "already_resolved"
    conflict = route_env["client"].post(
        f"/api/assignments/{run_id}/gaps/{gap['question_id']}/resolve",
        json={"resolution": "unlicensed"})
    assert conflict.status_code == 409, conflict.text
    assert "different answer" in conflict.text.lower()
    durable = route_env["lifecycle"].get_assignment(run_id)
    assert next(step for step in durable["steps"]
                if step["step_id"] == "calculate"
                )["result"]["value"] == "90.00"


def test_quote_ambiguous_discount_refuses_unrecognized_resolution(
        route_env, tmp_path):
    """Equally specific rules conflict; an unknown answer buys no arithmetic."""
    rules = [
        {"lesson_id": "five", "revision": 1, "name": "five percent",
         "when": {"category": "B"}, "rate": "0.05"},
        {"lesson_id": "ten", "revision": 1, "name": "ten percent",
         "when": {"category": "B"}, "rate": "0.10"},
    ]
    response = _qualified_discount_quote(
        route_env, tmp_path, label="conflict", rules=rules)
    assert response.status_code == 200, response.text
    body = response.json()
    run_id = body["run_id"]
    gap = next(item for item in body["assignment"]["open_gaps"]
               if item.get("concept") == "discount_rule_conflict")
    calc = next(step for step in body["assignment"]["assignment"]["steps"]
                if step["step_id"] == "calculate")
    assert calc["result_value"] is None

    refused = route_env["client"].post(
        f"/api/assignments/{run_id}/gaps/{gap['question_id']}/resolve",
        json={"resolution": "the cheaper one"})
    assert refused.status_code == 200, refused.text
    after = route_env["lifecycle"].get_assignment(run_id)
    calc = next(step for step in after["steps"]
                if step["step_id"] == "calculate")
    assert calc["status"] == "waiting"
    assert calc["result"] is None
    # A refused candidate answer returns the rejection record, not a run
    # projection; read the durable gap state from the assignment route.
    durable_state = route_env["client"].get(
        f"/api/assignments/{run_id}")
    assert durable_state.status_code == 200, durable_state.text
    open_gaps = durable_state.json()["open_gaps"]
    replacement = next(item for item in open_gaps
                       if item.get("concept") == "discount_rule_conflict")
    assert replacement["question_id"] != gap["question_id"]

    accepted = route_env["client"].post(
        f"/api/assignments/{run_id}/gaps/{replacement['question_id']}/resolve",
        json={"resolution": "ten percent"})
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["assignment"]["status"] == "completed"
    calc = next(step for step in route_env["lifecycle"].get_assignment(
        run_id)["steps"] if step["step_id"] == "calculate")
    assert calc["result"]["value"] == "90.00"


def test_expense_reconciliation_uses_the_same_assignment_route(
        route_env, tmp_path):
    """Non-sales portability: miles/nights, no quote lesson or discount.

    Independent arithmetic: 120 x 0.67 + 1 x 180.00 = 260.40 USD.
    """
    import docx

    policy = tmp_path / "travel-policy.txt"
    policy.write_text(
        "Travel policy 2026: mileage 0.67 USD per mile; lodging 180.00 "
        "USD per night.\n")
    response = route_env["client"].post("/api/assignments", json={
        "objective": "Reconcile the submitted travel expenses",
        "sources": [{"kind": "document", "path": str(policy)}],
        "calculation": {
            "line_items": [
                {"item_id": "mileage", "quantity": "120", "unit": "mile",
                 "pack_size": "1", "unit_price": "0.67",
                 "price_basis": "rate", "currency": "USD"},
                {"item_id": "lodging", "quantity": "1", "unit": "night",
                 "pack_size": "1", "unit_price": "180.00",
                 "price_basis": "rate", "currency": "USD"},
            ],
            "currency": "USD", "freight": "0", "tax": {"basis": "none"},
            "rounding": "half_up", "scale": 2,
            "rounding_authority": "travel policy 2026",
            "discount_rules": [],
        },
        "deliverables": [{"kind": "document",
                          "description": "Expense reconciliation"}],
        "task_context": {"audience": "finance reviewer"},
    })
    assert response.status_code == 200, response.text
    body = response.json()
    assignment = body["assignment"]["assignment"]
    assert assignment["status"] == "completed", assignment
    internal = route_env["lifecycle"].get_assignment(body["run_id"])
    calc = next(step for step in internal["steps"]
                if step["step_id"] == "calculate")
    assert calc["result"]["value"] == "260.40"
    assert calc["result"]["measure"] == "quote_total"
    receipt = calc["result"]["calculation_receipt"]
    assert receipt["currency"] == "USD"
    assert receipt["total"] == "260.40"
    assert len(receipt["line_evidence"]) == 2
    assert {row["item_id"] for row in calc["result"]["rows"]} == {
        "mileage", "lodging"}
    deliverable = next(item for item in assignment["deliverables"]
                       if item["kind"] == "document")
    text = "\n".join(
        paragraph.text for paragraph in docx.Document(
            deliverable["artifact_path"]).paragraphs)
    for table in docx.Document(deliverable["artifact_path"]).tables:
        for row in table.rows:
            text += "\n" + " | ".join(cell.text for cell in row.cells)
    assert "260.40" in text, text
    assert "mileage" in text and "lodging" in text, text


def test_objective_only_reads_authorized_evidence(route_env, tmp_path, monkeypatch):
    """An ordinary objective can start useful read-only work without a DAG."""
    note = tmp_path / "commercial-notes.txt"
    note.write_text("Approved commercial note: delivery within ten days.\n")

    async def proposal(context, **_kwargs):
        source_id = context["sources"][0]["source_id"]
        return {
            "proposal": {
                "proposal_kind": "evidence_read",
                "reason": "Read the authorized commercial note first.",
                "evidence_reads": [{
                    "step_id": "evidence-1",
                    "title": "Read the commercial note",
                    "source_id": source_id,
                }],
            },
            "source": "model",
            "technical_fallback": False,
            "errors": [],
        }

    monkeypatch.setattr(
        "api.assignment_routes.propose_employee_work", proposal)
    response = route_env["client"].post(
        "/api/assignments/from-objective",
        json={
            "objective": "Prepare a delivery answer for the customer",
            "sources": [{"path": str(note), "kind": "document"}],
            "use_model": False,
        })
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["proposal_source"] == "model"
    assert body["plan_revision"] == 1
    steps = body["assignment"]["assignment"]["steps"]
    assert steps[0]["status"] == "applied"
    assert body["employee_job"]["identity"]["execution_owner"] == "assignment"
    assert body["employee_job"]["objective"] == (
        "Prepare a delivery answer for the customer")
    assert body["employee_job"]["business_outcome"]["state"] == "unresolved"

    # G1: the same root job/criteria/identity survives a fresh session.
    fresh_runs = GoalRunService(
        workspace_id="ws-1", tenant_id="tenant-1",
        session_factory=route_env["factory"])
    fresh_goals = GoalService(
        workspace_id="ws-1", tenant_id="tenant-1",
        session_factory=route_env["factory"])
    fresh_lifecycle = TaskLifecycle(fresh_runs, fresh_goals)
    fresh_record = fresh_lifecycle.get_task(body["run_id"])
    assert fresh_record["assignment"]["objective"] == (
        "Prepare a delivery answer for the customer")
    assert fresh_record["assignment"]["employee_id"]
    assert fresh_record["assignment"]["completion_criteria"]
    assert fresh_record["assignment"]["sources"]


def test_objective_uploaded_document_is_selectable_and_readable(
        route_env, tmp_path, monkeypatch):
    payload = tmp_path / "purchase-order.json"
    payload.write_text(
        '{"po_id": "PO-9", "vendor_id": "V-2", "quantity": "2", '
        '"unit_price": "10.00", "currency": "USD"}')
    doc = IngestedDocument(
        id="doc-upload-1", workspace_id="ws-1", tenant_id="tenant-1",
        file_name="purchase-order.json", file_path=str(payload),
        file_type="json", integration_id="upload", external_id="upload-1",
        source_content_hash="v1", freshness_status="fresh")
    route_env["db"].add(doc)
    route_env["db"].commit()

    sources = route_env["client"].get("/api/assignments/sources")
    assert sources.status_code == 200, sources.text
    uploaded = next(
        item for item in sources.json()
        if item.get("document_id") == "doc-upload-1")
    assert uploaded["kind"] == "document"

    async def proposal(context, **_kwargs):
        return {
            "proposal": {
                "proposal_kind": "evidence_read",
                "reason": "Read the uploaded purchase order.",
                "evidence_reads": [{
                    "step_id": "evidence-1",
                    "title": "Read purchase order",
                    "source_id": context["sources"][0]["source_id"],
                }],
            },
            "source": "model",
            "technical_fallback": False,
            "errors": [],
        }

    monkeypatch.setattr(
        "api.assignment_routes.propose_employee_work", proposal)
    response = route_env["client"].post(
        "/api/assignments/from-objective",
        json={
            "objective": "Read the uploaded purchase order",
            "sources": [{"document_id": "doc-upload-1"}],
            "authorized_actions": ["retrieve"],
            "use_model": False,
        })
    assert response.status_code == 200, response.text
    body = response.json()
    internal = route_env["lifecycle"].get_assignment(body["run_id"])
    step = internal["steps"][0]
    assert step["status"] == "applied", step
    assert step["result"]["data"]["po_id"] == "PO-9"


def test_objective_only_returns_one_targeted_business_question(
        route_env, tmp_path, monkeypatch):
    async def proposal(_context, **_kwargs):
        return {
            "proposal": {
                "proposal_kind": "clarification",
                "reason": "The delivery requirement changes the answer.",
                "clarification": {
                    "question": "What delivery date has the customer accepted?",
                    "concept": "delivery_deadline",
                    "unblocks": "Selecting an eligible delivery option.",
                    "expected_answer_type": "date",
                },
            },
            "source": "model",
            "technical_fallback": False,
            "errors": [],
        }

    monkeypatch.setattr(
        "api.assignment_routes.propose_employee_work", proposal)
    note = tmp_path / "notes.txt"
    note.write_text("source\n")
    response = route_env["client"].post(
        "/api/assignments/from-objective",
        json={
            "objective": "Prepare a delivery answer",
            "sources": [{"path": str(note), "kind": "document"}],
            "use_model": False,
        })
    assert response.status_code == 409, response.text
    detail = response.json()["detail"]
    assert detail["error"] == "employee_clarification_required"
    assert detail["clarification"]["question"] == (
        "What delivery date has the customer accepted?")


def test_objective_only_unknown_qualification_blocks_dependent_read(
        route_env, tmp_path, monkeypatch):
    note = tmp_path / "eligibility-notes.txt"
    note.write_text("Eligibility is not stated in this note.\n")

    async def proposal(context, **_kwargs):
        return {
            "proposal": {
                "proposal_kind": "evidence_read",
                "reason": "The price answer depends on eligibility.",
                "evidence_reads": [{
                    "step_id": "evidence-1",
                    "title": "Read the pricing note",
                    "source_id": context["sources"][0]["source_id"],
                    "requires": [{
                        "kind": "fact", "fact_id": "agreement_eligible",
                        "equals": True,
                    }],
                }],
            },
            "source": "model",
            "technical_fallback": False,
            "errors": [],
        }

    monkeypatch.setattr(
        "api.assignment_routes.propose_employee_work", proposal)
    response = route_env["client"].post(
        "/api/assignments/from-objective",
        json={
            "objective": "Prepare the agreement price",
            "sources": [{"path": str(note), "kind": "document"}],
            "use_model": False,
        })
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["employee_job"]["business_outcome"]["state"] in (
        "unresolved", "unsatisfied")
    assert body["employee_job"]["business_outcome"]["state"] != "satisfied"
    step = body["employee_job"]["steps"][0]
    assert step["status"] == "pending"
    assert step["requires"] == [{
        "kind": "fact", "fact_id": "agreement_eligible", "equals": True}]
    assert body["assignment"]["assignment"]["status"] in (
        "blocked", "planned", "partial")


def test_plan_patch_route_adopts_fact_and_refuses_stale_proposal(
        route_env, tmp_path):
    step = new_step(
        step_id="read", title="Read the source",
        operation_type="retrieve", adapter="document.read",
        inputs={"path": str(tmp_path / "patch.txt")},
        effect="read_only")
    step["status"] = "applied"
    step["operation_id"] = "op-patch-read"
    step["result"] = {"value": "evidence", "summary": "read"}
    plan = new_assignment(
        objective="Apply a bounded plan patch",
        employee_id="lead-1", workspace_id="ws-1", tenant_id="tenant-1",
        teaching_snapshot=new_teaching_snapshot(revision="patch-r1"),
        steps=[step], authorized_actions=["retrieve"],
        completion_criteria=[{"kind": "required_work_complete"}])
    record = route_env["executor"].create_assignment(
        "conv-patch-route", "Apply a bounded plan patch", assignment=plan)
    run_id = record["run_id"]
    task = route_env["lifecycle"].get_task(run_id)
    payload = {
        "patch_id": "route-patch-1",
        "base_task_version": int(task.get("task_version") or 0),
        "base_plan_revision": task["assignment"]["plan_revision"],
        "reason": "qualification evidence arrived",
        "observations": [{"kind": "qualification", "id": "eligible"}],
        "add_facts": [{
            "fact_id": "eligible", "value": True,
            "evidence_state": "established",
            "subject": {"kind": "customer", "id": "cust-1"},
            "source_refs": [{"resource_id": "agreement-1",
                             "version": "v3"}],
            "authority_ref": "agreement:eligibility",
        }],
    }
    response = route_env["client"].post(
        f"/api/assignments/{run_id}/patch", json=payload)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "applied"
    fresh = route_env["lifecycle"].get_assignment(run_id)
    assert fresh["plan_revision"] == 2
    assert fresh["facts"][0]["fact_id"] == "eligible"

    stale = dict(payload)
    stale["patch_id"] = "route-patch-stale"
    stale["base_task_version"] = 0
    refused = route_env["client"].post(
        f"/api/assignments/{run_id}/patch", json=stale)
    assert refused.status_code == 409, refused.text


def test_objective_only_runs_typed_adaptive_follow_up(
        route_env, tmp_path, monkeypatch):
    import openpyxl

    prices = tmp_path / "heldout-prices.xlsx"
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Prices"
    sheet.append(["Item", "Qty", "Price", "Currency"])
    sheet.append(["A", 2, 100.00, "USD"])
    sheet.append(["B", 3, 50.00, "USD"])
    workbook.save(prices)

    async def initial(context, **_kwargs):
        return {
            "proposal": {
                "proposal_kind": "evidence_read",
                "reason": "Read the authorized price rows.",
                "evidence_reads": [{
                    "step_id": "evidence-1",
                    "title": "Read held-out prices",
                    "source_id": context["sources"][0]["source_id"],
                }],
            },
            "source": "model",
            "technical_fallback": False,
            "errors": [],
        }

    from core.employee_adaptation import WorkAdaptationProposal
    from core.employee_work_requests import (
        MoneyTerm, QuoteCalculationRequest, QuoteColumns, TaxTerm,
    )

    async def adaptation(context, observations, **_kwargs):
        assert context["work_request_schemas"]
        assert observations
        request = QuoteCalculationRequest(
            operation="quote_calculation",
            source_step_id="source-1",
            columns=QuoteColumns(
                item_id="Item", quantity="Qty", unit_price="Price",
                currency="Currency"),
            currency="USD",
            freight=MoneyTerm(value="20.00", authority_ref="freight"),
            tax=TaxTerm(basis="none", authority_ref="tax_basis"),
            reason="calculate the held-out quote")
        return {
            "proposal": WorkAdaptationProposal(
                decision="replan", reason="accepted rows support the quote",
                observation_ids=[observations[0]["observation_id"]],
                work_request=request).model_dump(),
            "source": "model",
            "technical_fallback": False,
            "errors": [],
            "attempt_id": "route-adaptive-1",
        }

    monkeypatch.setattr(
        "api.assignment_routes.propose_employee_work", initial)
    monkeypatch.setattr(
        "api.assignment_routes.propose_adaptation", adaptation)
    monkeypatch.setattr(
        "api.assignment_routes._employee_llm",
        lambda *_args, **_kwargs: object())

    response = route_env["client"].post(
        "/api/assignments/from-objective",
        json={
            "objective": "Quote the held-out customer request",
            "sources": [{
                "kind": "workbook", "path": str(prices),
                "sheet": "Prices",
            }],
            "authorized_actions": ["retrieve", "calculate"],
            "teaching_terms": {
                "currency": "USD", "freight": "20.00",
                "tax_basis": "none",
            },
            "use_model": True,
        })
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["adaptive_rounds"], (
        body["assignment"]["assignment"]["status"],
        [s.get("status") for s in body["assignment"]["assignment"]["steps"]],
        body["employee_job"]["business_outcome"],
        body.get("proposal_source"),
    )
    round_zero = body["adaptive_rounds"][0]
    assert round_zero["source"] == "model"
    assert round_zero.get("work_request_operation") == "quote_calculation", round_zero
    assert round_zero["adoption_status"] == "applied"
    assert body["assignment"]["assignment"]["status"] == "completed", body
    internal = route_env["lifecycle"].get_assignment(body["run_id"])
    calc = next(step for step in internal["steps"]
                if step.get("adapter") == "quote.calculate")
    assert calc["status"] == "applied"
    assert calc["result"]["value"] == "370.00"


def test_advance_route_adopts_typed_work_from_applied_evidence(
        route_env, monkeypatch):
    from core.employee_adaptation import WorkAdaptationProposal
    from tests.test_employee_work_requests import (
        _quote_request, _verified_quote_evidence,
    )

    teaching = new_teaching_snapshot(revision="route-advance-1")
    teaching["terms"] = {
        "currency": "USD", "freight": "20.00", "tax_basis": "none",
    }
    plan = new_assignment(
        objective="Quote the accepted customer request",
        employee_id="owner-1", workspace_id="ws-1", tenant_id="tenant-1",
        teaching_snapshot=teaching, steps=[_verified_quote_evidence()],
        authorized_actions=["retrieve", "calculate"],
        completion_criteria=[
            {"kind": "required_work_complete", "required": True},
            {"criterion_id": "employee_result:objective",
             "kind": "employee_result", "required": True,
             "verifier": "employee_result"},
        ])
    record = route_env["executor"].create_assignment(
        "conv-route-advance", plan["objective"], assignment=plan)
    run_id = record["run_id"]

    async def proposal(
        _context, observations, *, assignment, **_kwargs,
    ):
        return {
            "proposal": WorkAdaptationProposal(
                decision="replan",
                reason="the accepted rows support an exact quote",
                observation_ids=[observations[0]["observation_id"]],
                work_request=_quote_request()).model_dump(),
            "source": "model",
            "technical_fallback": False,
            "errors": [],
        }

    monkeypatch.setattr(
        "api.assignment_routes.propose_adaptation", proposal)
    response = route_env["client"].post(
        f"/api/assignments/{run_id}/advance",
        json={"use_model": False, "deadline_seconds": 30})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["rounds"][0]["source"] == "model"
    internal = route_env["lifecycle"].get_assignment(run_id)
    calculate = next(
        step for step in internal["steps"]
        if step["adapter"] == "quote.calculate")
    assert calculate["status"] == "applied"
    assert calculate["result"]["value"] == "370.00"


def test_advance_route_accepts_model_wait_choice_source(
        route_env, monkeypatch):
    from core.employee_adaptation import WorkAdaptationProposal
    from tests.test_employee_work_requests import (
        _quote_request, _verified_quote_evidence,
    )

    teaching = new_teaching_snapshot(revision="route-wait-choice-1")
    teaching["terms"] = {
        "currency": "USD", "freight": "20.00", "tax_basis": "none",
    }
    plan = new_assignment(
        objective="Quote the accepted customer request",
        employee_id="owner-1", workspace_id="ws-1", tenant_id="tenant-1",
        teaching_snapshot=teaching, steps=[_verified_quote_evidence()],
        authorized_actions=["retrieve", "calculate"],
        completion_criteria=[
            {"kind": "required_work_complete", "required": True},
            {"criterion_id": "employee_result:objective",
             "kind": "employee_result", "required": True,
             "verifier": "employee_result"},
        ])
    record = route_env["executor"].create_assignment(
        "conv-route-wait-choice", plan["objective"], assignment=plan)
    run_id = record["run_id"]

    async def proposal(
        _context, observations, *, assignment, **_kwargs,
    ):
        return {
            "proposal": WorkAdaptationProposal(
                decision="replan",
                reason="the accepted rows support an exact quote",
                observation_ids=[observations[0]["observation_id"]],
                work_request=_quote_request()).model_dump(),
            "source": "model_wait_choice",
            "technical_fallback": False,
            "errors": [],
        }

    monkeypatch.setattr(
        "api.assignment_routes.propose_adaptation", proposal)
    response = route_env["client"].post(
        f"/api/assignments/{run_id}/advance",
        json={"use_model": False, "deadline_seconds": 30})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["rounds"][0]["source"] == "model_wait_choice"
    internal = route_env["lifecycle"].get_assignment(run_id)
    calculate = next(
        step for step in internal["steps"]
        if step["adapter"] == "quote.calculate")
    assert calculate["status"] == "applied"
    assert calculate["result"]["value"] == "370.00"


def test_advance_route_does_not_adopt_a_policy_forbidden_wait(
        route_env, tmp_path, monkeypatch):
    from core.employee_adaptation import propose_adaptation as real_propose
    from core.task_lifecycle import open_unresolved_questions

    monkeypatch.setenv("ATOM_ASSIGNMENT_ALLOW_INTERNAL_PATHS", "1")
    monkeypatch.setenv(
        "ATOM_ASSIGNMENT_INTERNAL_FIXTURE_ROOT", str(tmp_path))

    def applied(step_id, data):
        step = new_step(
            step_id=step_id, title=step_id, operation_type="retrieve",
            adapter="document.read", inputs={}, effect="read_only")
        payload = tmp_path / f"{step_id}.json"
        payload.write_text(json.dumps(data))
        step.update(
            status="applied", operation_id=f"op-{step_id}",
            inputs={
                "path": str(payload),
                "resource_binding": {
                    "resource_id": f"resource-{step_id}",
                    "source_version": "v1",
                },
            },
            result={
                "data": data, "resource_id": step_id,
                "source_version": "v1",
                "coverage": {"complete": True, "known": True,
                             "truncated": False},
                "verification": {
                    "status": "verified", "resource_id": step_id,
                    "version": "v1"},
            })
        return step

    plan = new_assignment(
        objective="Reconcile the supplier invoice for PO-ROUTE-77",
        employee_id="owner-1", workspace_id="ws-1", tenant_id="tenant-1",
        teaching_snapshot=new_teaching_snapshot(revision="route-guard-1"),
        steps=[
            applied("purchase-order", {
                "po_id": "PO-ROUTE-77", "vendor_id": "V-9"}),
            applied("receiving", {
                "po_id": "PO-ROUTE-77", "received_quantity": "2"}),
            # Two accepted invoices make the role ambiguous, matching the
            # captured replay's trusted state: no missing role, no ready
            # operation, and only clarify/retain allowed.
            applied("invoice-a", {
                "invoice_id": "INV-ROUTE-A", "po_id": "PO-ROUTE-77",
                "quantity": "2", "unit_price": "10.00"}),
            applied("invoice-b", {
                "invoice_id": "INV-ROUTE-B", "po_id": "PO-ROUTE-77",
                "quantity": "2", "unit_price": "11.00"}),
        ],
        authorized_actions=["retrieve", "calculate"],
        completion_criteria=[
            {"kind": "required_work_complete", "required": True},
            {"criterion_id": "employee_result:objective",
             "kind": "employee_result", "required": True,
             "verifier": "employee_result"},
        ])
    record = route_env["executor"].create_assignment(
        "conv-route-guard", plan["objective"], assignment=plan)
    run_id = record["run_id"]

    async def fake_pinned(_llm, *, response_model, **_kwargs):
        if response_model.__name__ == "AdaptationProposal":
            return response_model.model_validate({
                "decision": "replan",
                "reason": "await the missing invoice",
                "observation_ids": [],
                "work_request": {
                    "operation": "await_evidence",
                    "fact": "the supplier invoice for PO-ROUTE-77",
                    "subject": "purchase order PO-ROUTE-77",
                    "expected_from": "authorized procurement source",
                    "expected_answer_type": "text",
                    "blocks": "invoice reconciliation",
                    "blocks_operation": "invoice_reconciliation",
                },
            })
        return response_model.model_validate({
            "decision": "replan",
            "reason": "await the missing invoice",
            "fact": "the supplier invoice for PO-ROUTE-77",
            "subject": "purchase order PO-ROUTE-77",
            "expected_from": "authorized procurement source",
            "expected_answer_type": "text",
            "blocks_operation": "invoice_reconciliation",
        })

    monkeypatch.setattr(
        "core.llm.pinned_planning.pinned_structured_call", fake_pinned)

    async def guarded_propose(
        context, observations, *, assignment, **kwargs,
    ):
        kwargs.pop("llm_service", None)
        return await real_propose(
            context, observations, assignment=assignment,
            llm_service=object(), **kwargs)

    monkeypatch.setattr(
        "api.assignment_routes.propose_adaptation", guarded_propose)
    response = route_env["client"].post(
        f"/api/assignments/{run_id}/advance",
        json={"use_model": True, "deadline_seconds": 30})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body.get("rounds"), body
    round_record = body["rounds"][0]
    assert round_record["source"] == "deterministic", round_record
    assert round_record["failure_stage"] == "wait_choice_policy", round_record
    assert round_record["decision"] in ("clarify", "retain"), round_record
    assert any(
        "replan_not_allowed" in item
        for item in round_record["errors"]), round_record
    assert round_record["decision"] == "clarify", round_record

    internal = route_env["lifecycle"].get_assignment(run_id)
    steps = {step["step_id"]: step for step in internal["steps"]}
    assert "assignment.wait" not in {
        step.get("adapter") for step in internal["steps"]}
    assert steps["purchase-order"]["status"] == "applied"
    assert steps["purchase-order"]["result"]["data"]["po_id"] == (
        "PO-ROUTE-77")
    assert steps["receiving"]["status"] == "applied"
    assert internal["status"] != "waiting"
    questions = open_unresolved_questions(
        route_env["lifecycle"].get_task(run_id))
    assert questions, "the rejected wait must leave a targeted question"
    assert "invoice" in str(questions[0]).lower()


def test_source_addition_settles_missing_prerequisite_without_duplicates(
        route_env, tmp_path, monkeypatch):
    from core.task_lifecycle import (
        add_unresolved_questions, open_unresolved_questions,
    )

    monkeypatch.setenv("ATOM_ASSIGNMENT_ALLOW_INTERNAL_PATHS", "1")
    monkeypatch.setenv(
        "ATOM_ASSIGNMENT_INTERNAL_FIXTURE_ROOT", str(tmp_path))

    def applied(step_id, data):
        step = new_step(
            step_id=step_id, title=step_id, operation_type="retrieve",
            adapter="document.read", inputs={}, effect="read_only")
        payload = tmp_path / f"{step_id}.json"
        payload.write_text(json.dumps(data))
        step.update(
            status="applied", operation_id=f"op-{step_id}",
            inputs={"path": str(payload)},
            result={
                "data": data, "resource_id": step_id,
                "source_version": "v1",
                "coverage": {"complete": True, "known": True,
                             "truncated": False},
                "verification": {
                    "status": "verified", "resource_id": step_id,
                    "version": "v1"},
            })
        return step

    plan = new_assignment(
        objective="Reconcile the supplier invoice for PO-7",
        employee_id="owner-1", workspace_id="ws-1", tenant_id="tenant-1",
        teaching_snapshot=new_teaching_snapshot(revision="source-settle-1"),
        steps=[
            applied("purchase-order", {
                "po_id": "PO-7", "vendor_id": "V-9"}),
            applied("receiving", {
                "po_id": "PO-7", "received_quantity": "2"}),
        ],
        authorized_actions=["retrieve", "calculate"])
    record = route_env["executor"].create_assignment(
        "conv-source-settle", plan["objective"], assignment=plan)
    run_id = record["run_id"]
    add_unresolved_questions(route_env["lifecycle"], run_id, [{
        "kind": "missing_evidence",
        "item": "invoice reconciliation",
        "question": "Which authorized source contains the invoice for PO-7?",
        "concept": "invoice_reconciliation",
        "next_action": "Authorize the invoice source.",
        "inputs": {"operation": "invoice_reconciliation",
                   "missing": ["invoice"]},
    }])
    invoice = tmp_path / "invoice.json"
    invoice.write_text(json.dumps({
        "invoice_id": "INV-7", "po_id": "PO-7", "quantity": "2",
        "unit_price": "120.00", "freight": "30.00", "currency": "USD"}))
    response = route_env["client"].post(
        f"/api/assignments/{run_id}/sources",
        json={"source": {"kind": "document", "path": str(invoice)},
              "reason": "the user supplied the invoice"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["resolved_question_ids"]
    assert open_unresolved_questions(
        route_env["lifecycle"].get_task(run_id)) == []
    steps_before = len(
        route_env["lifecycle"].get_assignment(run_id)["steps"])

    duplicate = route_env["client"].post(
        f"/api/assignments/{run_id}/sources",
        json={"source": {"kind": "document", "path": str(invoice)},
              "reason": "same invoice again"})
    assert duplicate.status_code == 200, duplicate.text
    assert duplicate.json()["status"] == "already_present"
    assert len(route_env["lifecycle"].get_assignment(
        run_id)["steps"]) == steps_before


def test_retained_authorized_scope_supports_later_evidence_reads(
        route_env, tmp_path, monkeypatch):
    from core.employee_adaptation import WorkAdaptationProposal
    from core.employee_work_requests import (
        InvoiceReconciliationRequest,
    )

    monkeypatch.setenv("ATOM_ASSIGNMENT_ALLOW_INTERNAL_PATHS", "1")
    monkeypatch.setenv("ATOM_ASSIGNMENT_INTERNAL_FIXTURE_ROOT", str(tmp_path))
    po = tmp_path / "purchase-order.json"
    po.write_text(json.dumps({
        "po_id": "PO-7", "vendor_id": "V-9", "quantity": "2",
        "unit_price": "120.00", "freight": "30.00", "currency": "USD"}))
    invoice = tmp_path / "invoice.json"
    invoice.write_text(json.dumps({
        "invoice_id": "INV-7", "po_id": "PO-7", "quantity": "2",
        "unit_price": "120.00", "freight": "30.00", "currency": "USD"}))
    receiving = tmp_path / "receiving.json"
    receiving.write_text(json.dumps({
        "po_id": "PO-7", "received_quantity": "2"}))
    source_paths = [str(receiving), str(po), str(invoice)]

    async def fake_work(context, **_kwargs):
        if context.get("stage") == "discovery":
            chosen = list(context["sources"][1:])
        else:
            chosen = [context["sources"][0]]
        return {
            "proposal": {
                "proposal_kind": "evidence_read",
                "reason": "read the next authorized evidence",
                "evidence_reads": [{
                    "step_id": f"evidence-{index}",
                    "title": "Read authorized evidence",
                    "source_id": source["source_id"],
                } for index, source in enumerate(chosen, start=1)],
            },
            "source": "model",
            "technical_fallback": False,
            "errors": [],
        }

    async def fake_adaptation(context, observations, **_kwargs):
        assert context["work_request_schemas"]
        return {
            "proposal": WorkAdaptationProposal(
                decision="replan",
                reason="all authorized evidence is now read",
                observation_ids=[
                    item["observation_id"] for item in observations],
                work_request=InvoiceReconciliationRequest(
                    operation="invoice_reconciliation",
                    invoice_step_id="source-3",
                    purchase_order_step_id="source-2",
                    receiving_step_id="source-1",
                )).model_dump(),
            "source": "model",
            "technical_fallback": False,
            "errors": [],
        }

    # The context does not expose step IDs directly; the compiler derives them
    # in assignment order: receiving first, then PO and invoice from discovery.
    monkeypatch.setattr(
        "api.assignment_routes.propose_employee_work", fake_work)
    monkeypatch.setattr(
        "api.assignment_routes.propose_adaptation", fake_adaptation)
    monkeypatch.setattr(
        "api.assignment_routes._employee_llm",
        lambda *_args, **_kwargs: object())

    response = route_env["client"].post(
        "/api/assignments/from-objective",
        json={
            "objective": "Reconcile the invoice from authorized sources",
            "sources": [{"path": path} for path in source_paths],
            "authorized_actions": ["retrieve", "calculate"],
            "use_model": True,
        })
    assert response.status_code == 200, response.text
    body = response.json()
    internal = route_env["lifecycle"].get_assignment(body["run_id"])
    assert len(internal["sources"]) == 3
    steps = {step["step_id"]: step for step in internal["steps"]}
    assert [step["step_id"] for step in internal["steps"]] == [
        "source-1", "source-2", "source-3", "invoice-reconcile"]
    assert steps["source-2"]["adapter"] == "document.read"
    assert steps["source-3"]["adapter"] == "document.read"
    assert internal["status"] == "completed", internal["status"]
    assert next(
        step for step in internal["steps"]
        if step["adapter"] == "invoice.reconcile")["result"]["value"] == (
            "270.00")


def test_discovery_outside_scope_asks_one_actionable_question(
        route_env, tmp_path, monkeypatch):
    from core.task_lifecycle import open_unresolved_questions

    monkeypatch.setenv("ATOM_ASSIGNMENT_ALLOW_INTERNAL_PATHS", "1")
    monkeypatch.setenv("ATOM_ASSIGNMENT_INTERNAL_FIXTURE_ROOT", str(tmp_path))
    note = tmp_path / "commercial-notes.txt"
    note.write_text("No invoice, purchase order or receiving data is here.\n")

    async def fake_work(context, **_kwargs):
        return {
            "proposal": {
                "proposal_kind": "evidence_read",
                "reason": "read the only authorized note",
                "evidence_reads": [{
                    "step_id": "evidence-1",
                    "title": "Read the authorized note",
                    "source_id": context["sources"][0]["source_id"],
                }],
            },
            "source": "model", "technical_fallback": False,
            "errors": [],
        }

    async def fake_adaptation(context, observations, **_kwargs):
        from core.employee_adaptation import AdaptationProposal

        assert not context.get("work_request_schemas")
        return {
            "proposal": AdaptationProposal(
                decision="clarify",
                reason="the corrected invoice is outside the authorized scope",
                observation_ids=[
                    item["observation_id"] for item in observations],
                clarification={
                    "question": (
                        "Which authorized source contains the corrected "
                        "invoice for purchase order PO-7?"),
                    "concept": "invoice_reconciliation",
                    "unblocks": "invoice reconciliation",
                }).model_dump(),
            "source": "model", "technical_fallback": False,
            "errors": [],
        }

    monkeypatch.setattr(
        "api.assignment_routes.propose_employee_work", fake_work)
    monkeypatch.setattr(
        "api.assignment_routes.propose_adaptation", fake_adaptation)
    monkeypatch.setattr(
        "api.assignment_routes._employee_llm",
        lambda *_args, **_kwargs: object())
    response = route_env["client"].post(
        "/api/assignments/from-objective",
        json={
            "objective": "Reconcile the supplier invoice",
            "sources": [{"path": str(note)}],
            "authorized_actions": ["retrieve", "calculate"],
            "use_model": True,
        })
    assert response.status_code == 200, response.text
    body = response.json()
    questions = open_unresolved_questions(
        route_env["lifecycle"].get_task(body["run_id"]))
    assert questions
    assert questions[0]["kind"] == "missing_evidence"
    assert "invoice" in questions[0]["question"].lower()
    internal = route_env["lifecycle"].get_assignment(body["run_id"])
    assert [step["step_id"] for step in internal["steps"]] == ["source-1"]
    assert internal["steps"][0]["status"] == "applied"


def test_discovery_repeated_read_falls_back_to_unread_authorized_scope(
        route_env, tmp_path, monkeypatch):
    from core.employee_adaptation import WorkAdaptationProposal
    from core.employee_work_requests import InvoiceReconciliationRequest

    monkeypatch.setenv("ATOM_ASSIGNMENT_ALLOW_INTERNAL_PATHS", "1")
    monkeypatch.setenv("ATOM_ASSIGNMENT_INTERNAL_FIXTURE_ROOT", str(tmp_path))
    payloads = {
        "purchase-order.json": {
            "po_id": "PO-7", "vendor_id": "V-9", "quantity": "2",
            "unit_price": "120.00", "freight": "30.00", "currency": "USD"},
        "invoice.json": {
            "invoice_id": "INV-7", "po_id": "PO-7", "quantity": "2",
            "unit_price": "120.00", "freight": "30.00", "currency": "USD"},
        "receiving.json": {
            "po_id": "PO-7", "received_quantity": "2"},
    }
    for name, payload in payloads.items():
        (tmp_path / name).write_text(json.dumps(payload))
    order = ["receiving.json", "invoice.json", "purchase-order.json"]

    async def fake_work(context, **_kwargs):
        if context.get("stage") == "discovery":
            # The consumer contract exposes the already-authorized unread
            # handles explicitly; the fallback then reads them instead of
            # asking the user to upload them again.
            assert context["unread_sources"]
            assert context["unread_source_count"] == len(
                context["unread_sources"])
            assert all(
                source.get("read") is False
                for source in context["unread_sources"])
            chosen = [context["sources"][0]]
        else:
            chosen = [context["sources"][0]]
        return {
            "proposal": {
                "proposal_kind": "evidence_read",
                "reason": "read the next authorized evidence",
                "evidence_reads": [{
                    "step_id": f"evidence-{index}",
                    "title": "Read authorized evidence",
                    "source_id": source["source_id"],
                } for index, source in enumerate(chosen, start=1)],
            },
            "source": "model", "technical_fallback": False,
            "errors": [],
        }

    async def fake_adaptation(context, observations, **_kwargs):
        assert context["work_request_schemas"]
        return {
            "proposal": WorkAdaptationProposal(
                decision="replan",
                reason="all authorized evidence is applied",
                observation_ids=[
                    item["observation_id"] for item in observations],
                work_request=InvoiceReconciliationRequest(
                    operation="invoice_reconciliation",
                    invoice_step_id="source-2",
                    purchase_order_step_id="source-3",
                    receiving_step_id="source-1")).model_dump(),
            "source": "model", "technical_fallback": False,
            "errors": [],
        }

    monkeypatch.setattr(
        "api.assignment_routes.propose_employee_work", fake_work)
    monkeypatch.setattr(
        "api.assignment_routes.propose_adaptation", fake_adaptation)
    monkeypatch.setattr(
        "api.assignment_routes._employee_llm",
        lambda *_args, **_kwargs: object())
    response = route_env["client"].post(
        "/api/assignments/from-objective",
        json={
            "objective": "Reconcile the supplier invoice from authorized scope",
            "sources": [
                {"path": str(tmp_path / name)} for name in order],
            "authorized_actions": ["retrieve", "calculate"],
            "use_model": True,
        })
    assert response.status_code == 200, response.text
    body = response.json()
    rounds = body.get("adaptive_rounds") or []
    assert any(
        round_item.get("repair") == "unread_scope"
        for round_item in rounds), rounds
    internal = route_env["lifecycle"].get_assignment(body["run_id"])
    steps = {step["step_id"]: step for step in internal["steps"]}
    assert steps["source-1"]["status"] == "applied"
    assert steps["source-2"]["status"] == "applied"
    assert steps["source-3"]["status"] == "applied"
    assert internal["status"] == "completed", internal["status"]
    assert next(
        step for step in internal["steps"]
        if step["adapter"] == "invoice.reconcile")["result"]["value"] == (
            "270.00")


def test_requested_document_compiles_after_verified_evidence_quote(
        route_env, tmp_path, monkeypatch):
    import docx

    from core.employee_adaptation import WorkAdaptationProposal
    from core.employee_work_requests import (
        MoneyTerm, QuoteCalculationRequest, QuoteColumns, TaxTerm,
    )

    _scotch_catalog(route_env, tmp_path, monkeypatch)

    async def fake_work(context, **_kwargs):
        return {
            "proposal": {
                "proposal_kind": "evidence_read",
                "reason": "read the authorized price list",
                "evidence_reads": [{
                    "step_id": "evidence-1",
                    "title": "Read the price list",
                    "source_id": context["sources"][0]["source_id"],
                }],
            },
            "source": "model", "technical_fallback": False, "errors": [],
        }

    async def fake_adaptation(context, observations, **_kwargs):
        assert context["work_request_schemas"]
        return {
            "proposal": WorkAdaptationProposal(
                decision="replan",
                reason="derive the quote from the accepted price rows",
                observation_ids=[
                    item["observation_id"] for item in observations],
                work_request=QuoteCalculationRequest(
                    operation="quote_calculation",
                    source_step_id="source-1",
                    columns=QuoteColumns(
                        item_id="Item Number",
                        description="Description",
                        quantity="Quantity",
                        unit_price="Unit Price",
                        currency="Currency"),
                    currency="USD",
                    freight=MoneyTerm(
                        value="20.00", authority_ref="freight"),
                    tax=TaxTerm(
                        basis="none", authority_ref="tax_basis"),
                )).model_dump(),
            "source": "model", "technical_fallback": False, "errors": [],
        }

    monkeypatch.setattr(
        "api.assignment_routes.propose_employee_work", fake_work)
    monkeypatch.setattr(
        "api.assignment_routes.propose_adaptation", fake_adaptation)
    monkeypatch.setattr(
        "api.assignment_routes._employee_llm",
        lambda *_args, **_kwargs: object())
    response = route_env["client"].post(
        "/api/assignments/from-objective",
        json={
            "objective": (
                "Prepare the customer quote document from the authorized "
                "price list"),
            "sources": [{
                "kind": "workbook",
                "dataset_name": "scotch_parts_price_list",
                "sheet": "US$ SCOTCH PARTS",
            }],
            "authorized_actions": ["retrieve", "calculate"],
            "teaching_terms": {
                "currency": "USD", "freight": "20.00",
                "tax_basis": "none"},
            "requested_output": "document",
            "use_model": True,
        })
    assert response.status_code == 200, response.text
    body = response.json()
    internal = route_env["lifecycle"].get_assignment(body["run_id"])
    assert internal["status"] == "completed", internal["status"]
    steps = {step["step_id"]: step for step in internal["steps"]}
    assert "requested-artifact" in steps, steps
    artifact_step = steps["requested-artifact"]
    assert artifact_step["status"] == "applied"
    assert artifact_step["depends_on"] == ["quote-total"]
    assert artifact_step["inputs"]["compose_from_results"] is True
    deliverable = internal["deliverables"][0]
    assert deliverable["kind"] == "document"
    assert deliverable["status"] == "applied"
    artifact_path = Path(deliverable["artifact_path"])
    assert artifact_path.is_file()
    text = "\n".join(
        paragraph.text for paragraph in docx.Document(
            str(artifact_path)).paragraphs)
    for table in docx.Document(str(artifact_path)).tables:
        for row in table.rows:
            text += "\n" + " | ".join(cell.text for cell in row.cells)
    assert "105.00" in text, text
    assert "scotch-parts.xlsx" in text, text
    criteria = (body.get("employee_job") or {}).get("criteria") or []
    assert any(
        item.get("kind") == "artifact_verified"
        and item.get("deliverable_id") == deliverable["deliverable_id"]
        for item in criteria), criteria


def test_requested_document_compiles_after_verified_invoice_reconciliation(
        route_env, tmp_path, monkeypatch):
    """The same compiler renders the requested output for procurement.

    The artifact must follow the verified reconciliation receipt and draw its
    content from that durable result, not from an explicit body supplied by
    the caller.
    """
    import docx

    from core.employee_adaptation import WorkAdaptationProposal
    from core.employee_work_requests import InvoiceReconciliationRequest

    monkeypatch.setenv("ATOM_ASSIGNMENT_ALLOW_INTERNAL_PATHS", "1")
    monkeypatch.setenv("ATOM_ASSIGNMENT_INTERNAL_FIXTURE_ROOT", str(tmp_path))
    po = tmp_path / "purchase-order.json"
    po.write_text(json.dumps({
        "po_id": "PO-7", "vendor_id": "V-9", "quantity": "2",
        "unit_price": "120.00", "freight": "30.00", "currency": "USD"}))
    invoice = tmp_path / "invoice.json"
    invoice.write_text(json.dumps({
        "invoice_id": "INV-7", "po_id": "PO-7", "quantity": "2",
        "unit_price": "120.00", "freight": "30.00", "currency": "USD"}))
    receiving = tmp_path / "receiving.json"
    receiving.write_text(json.dumps({
        "po_id": "PO-7", "received_quantity": "2"}))
    source_paths = [str(receiving), str(po), str(invoice)]

    async def fake_work(context, **_kwargs):
        if context.get("stage") == "discovery":
            chosen = list(context["sources"][0:])
        else:
            chosen = [context["sources"][0]]
        return {
            "proposal": {
                "proposal_kind": "evidence_read",
                "reason": "read the authorized procurement evidence",
                "evidence_reads": [{
                    "step_id": f"evidence-{index}",
                    "title": "Read authorized evidence",
                    "source_id": source["source_id"],
                } for index, source in enumerate(chosen, start=1)],
            },
            "source": "model",
            "technical_fallback": False,
            "errors": [],
        }

    async def fake_adaptation(context, observations, **_kwargs):
        assert context["work_request_schemas"]
        return {
            "proposal": WorkAdaptationProposal(
                decision="replan",
                reason="reconcile the invoice then render the review",
                observation_ids=[
                    item["observation_id"] for item in observations],
                work_request=InvoiceReconciliationRequest(
                    operation="invoice_reconciliation",
                    invoice_step_id="source-3",
                    purchase_order_step_id="source-2",
                    receiving_step_id="source-1")).model_dump(),
            "source": "model",
            "technical_fallback": False,
            "errors": [],
        }

    monkeypatch.setattr(
        "api.assignment_routes.propose_employee_work", fake_work)
    monkeypatch.setattr(
        "api.assignment_routes.propose_adaptation", fake_adaptation)
    monkeypatch.setattr(
        "api.assignment_routes._employee_llm",
        lambda *_args, **_kwargs: object())

    response = route_env["client"].post(
        "/api/assignments/from-objective",
        json={
            "objective": "Reconcile the invoice and issue the review document",
            "sources": [{"path": path} for path in source_paths],
            "authorized_actions": ["retrieve", "calculate"],
            "requested_output": "document",
            "use_model": True,
        })
    assert response.status_code == 200, response.text
    body = response.json()
    internal = route_env["lifecycle"].get_assignment(body["run_id"])
    assert internal["status"] == "completed", internal["status"]
    steps = {step["step_id"]: step for step in internal["steps"]}
    artifact_step = steps["requested-artifact"]
    assert artifact_step["status"] == "applied"
    assert artifact_step["depends_on"] == ["invoice-reconcile"]
    assert artifact_step["inputs"]["compose_from_results"] is True
    assert steps["invoice-reconcile"]["result"]["value"] == "270.00"
    deliverable = internal["deliverables"][0]
    assert deliverable["status"] == "applied"
    artifact_path = Path(deliverable["artifact_path"])
    assert artifact_path.is_file()
    document = docx.Document(str(artifact_path))
    text = "\n".join(paragraph.text for paragraph in document.paragraphs)
    for table in document.tables:
        for row in table.rows:
            text += "\n" + " | ".join(cell.text for cell in row.cells)
    assert "270.00" in text, text
    assert "purchase-order.json" in text, text
    criteria = (body.get("employee_job") or {}).get("criteria") or []
    assert any(
        item.get("kind") == "artifact_verified"
        and item.get("deliverable_id") == deliverable["deliverable_id"]
        for item in criteria), criteria


def test_no_suitable_reasoning_route_is_durable_and_business_safe(
        route_env, tmp_path, monkeypatch):
    note = tmp_path / "commercial-notes.txt"
    note.write_text("Approved commercial note: delivery within ten days.\n")

    async def proposal(context, **_kwargs):
        return {
            "proposal": {
                "proposal_kind": "evidence_read",
                "reason": "read the authorized note",
                "evidence_reads": [{
                    "step_id": "evidence-1",
                    "title": "Read the commercial note",
                    "source_id": context["sources"][0]["source_id"],
                }],
            },
            "source": "deterministic",
            "technical_fallback": True,
            "errors": ["no configured model was eligible"],
            "routing": {
                "mode": "pinned",
                "requested_route": {
                    "provider": "local", "model": "weak-candidate"},
                "served_route": None,
                "resolved_model": None,
                "profile": {
                    "name": "employee_evidence_selection",
                    "version": "2026-11-04.1",
                },
                "error": {
                    "code": "no_suitable_configured_model",
                    "detail": "raw provider exception must not surface",
                },
            },
        }

    monkeypatch.setattr(
        "api.assignment_routes.propose_employee_work", proposal)
    response = route_env["client"].post(
        "/api/assignments/from-objective",
        json={
            "objective": "Prepare a delivery answer for the customer",
            "sources": [{"path": str(note), "kind": "document"}],
            "use_model": False,
        })
    assert response.status_code == 200, response.text
    body = response.json()
    run_id = body["run_id"]
    notice = body["employee_job"]["routing_notice"]
    assert notice["state"] == "configuration_required"
    assert notice["code"] == "no_suitable_configured_model"
    assert "settings" in notice["next_action"].lower()
    rendered = json.dumps(body)
    assert "raw provider exception" not in rendered
    assert "weak-candidate" not in json.dumps(notice)

    # The route outcome belongs to this assignment and survives a fresh read.
    detail = route_env["client"].get(
        f"/api/assignments/{run_id}").json()
    assert detail["employee_routing"]["error"]["code"] == (
        "no_suitable_configured_model")
    assert detail["employee_routing"]["requested_route"] == {
        "provider": "local", "model": "weak-candidate"}
    assert detail["employee_routing"]["served_route"] is None
    assert detail["employee_job"]["routing_notice"] == notice
    decisions = route_env["lifecycle"].runs.get_decisions(run_id)
    routes = [
        item for item in decisions if item.get("kind") == "employee_route"]
    assert routes and routes[-1]["stage"] == "employee_proposal"
    assert routes[-1]["error_code"] == "no_suitable_configured_model"
    assert routes[-1]["served_route"] is None
    assert route_env["lifecycle"].get_assignment(run_id)["status"] != (
        "cancelled")
