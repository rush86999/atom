"""Route-level exact-content approval for a canvas assessment.

The service tests pin the artifact digest and the CAS. This test pins the
public HTTP boundary a downstream consumer actually uses:

    assess -> unreviewed decisions refused -> approve exact execution ->
    decisions allowed -> mutate one reviewed field with the stored hash
    untouched -> authorization/decisions/approval all refuse fresh use.

The review model is a controlled structured response; the persistence,
approval and refusal paths are the real ones.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.canvas_capability_routes import router
from core.auth import get_current_user
from core.database import Base, get_db
from core.deployment_audience import require_pilot_user
from core.models import Canvas


@pytest.fixture()
def store():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    db = Session()
    try:
        yield db, Session
    finally:
        db.close()
        engine.dispose()


@pytest.fixture()
def user():
    return SimpleNamespace(
        id="route-user", email="route@example.invalid",
        workspace_id="ws-route", tenant_id="tenant-route",
        role="workspace_admin", is_active=True,
    )


def _manifest():
    return {
        "schema_version": 1,
        "base_component": "table",
        "operations": [
            "read", "select", "calculate", "assess", "edit", "export", "bind",
        ],
        "data_binding": {
            "subject_field": "Ref", "measure_field": "Amount",
            "status_field": "Status",
        },
        "editable_fields": ["Amount", "Status"],
        "teaching_binding": {"agent_id": "agent-route", "scope_id": "task-route"},
        "decision_options": ["APPROVE", "REVIEW", "DENY"],
        "task_policy": (
            "Approve Amount >= 100 when Status is Open. Review 50-99. "
            "Deny below 50 or Closed."
        ),
        "outputs": ["xlsx"],
        "required_approvals": [],
    }


def _seed(db, user):
    from core.canvas_capability_service import bind_dataset, set_manifest

    canvas = Canvas(
        id="canvas_route_1", tenant_id=user.tenant_id,
        workspace_id=user.workspace_id, created_by=user.id,
        name="Route review", canvas_type="sheet", content={},
        status="active",
    )
    db.add(canvas)
    db.commit()
    set_manifest(db, canvas, user, _manifest())
    bind_dataset(
        db, canvas, user,
        ["Ref", "Amount", "Status", "Note"],
        [
            ["R-1", 120, "Open", "alpha"],
            ["R-2", 75, "Open", "beta"],
        ],
        source={"file_name": "route.csv", "sha256": "route-sha"},
    )
    return canvas


def _fake_review(monkeypatch):
    from core import review_result

    import re

    async def fake_generate(llm, **kwargs):
        policy_id = re.search(
            r"policy:[0-9a-f]+", kwargs["messages"][0]["content"]).group(0)
        assessments = [
            {
                "subject_id": "R-1", "decision": "APPROVE",
                "basis": ["Amount 120 is at least 100"],
                "evidence_ids": ["ev:R-1:2"],
                "policy_ids": [policy_id],
                "unresolved_requirements": [],
            },
            {
                "subject_id": "R-2", "decision": "REVIEW",
                "basis": ["Amount 75 is between 50 and 99"],
                "evidence_ids": ["ev:R-2:3"],
                "policy_ids": [policy_id],
                "unresolved_requirements": [],
            },
        ]
        return "```review_result\n" + json.dumps(
            {"assessments": assessments}) + "\n```"

    monkeypatch.setenv("ATOM_REVIEW_MODEL", "deepseek-flash")
    monkeypatch.setenv("ATOM_ASSESSMENT_REVIEW_POLICY", "always")
    monkeypatch.setattr(review_result, "generate_structured_review",
                        fake_generate)


def _client(db, user):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[require_pilot_user] = lambda: user
    return TestClient(app)


def test_exact_assessment_approval_and_drift_refusal(
        store, user, monkeypatch):
    db, _Session = store
    canvas = _seed(db, user)
    _fake_review(monkeypatch)
    client = _client(db, user)

    assessed = client.post(
        f"/api/canvas/{canvas.id}/capability/assess",
        json={"ask": "all rows"},
    )
    assert assessed.status_code == 200, assessed.text
    body = assessed.json()
    assert body["certified"] is True
    assert body["authorized"] is False
    assert body["rendered"] == ""
    assert body["rendered_suppressed"] is True
    execution_id = body["execution_id"]

    refused = client.get(f"/api/canvas/{canvas.id}/capability/decisions")
    assert refused.status_code == 409, refused.text
    assert refused.json()["error"]["code"] == "review_required"

    approved = client.post(
        f"/api/canvas/{canvas.id}/capability/assess/{execution_id}/approve",
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["authorization"]["state"] == "authorized"

    allowed = client.get(f"/api/canvas/{canvas.id}/capability/decisions")
    assert allowed.status_code == 200, allowed.text
    assert allowed.json()["decisions"] == {
        "R-1": "APPROVE",
        "R-2": "REVIEW",
    }

    # Change one decision but leave the stored digest exactly as recorded.
    db.expire_all()
    fresh = db.query(Canvas).filter(Canvas.id == canvas.id).one()
    content = dict(fresh.content or {})
    record = dict(content["assessment_review"])
    artifact = [dict(item) for item in record["assessments"]]
    first = dict(artifact[0])
    first["decision"] = "DENY"
    artifact[0] = first
    record["assessments"] = artifact
    content["assessment_review"] = record
    fresh.content = content
    db.commit()

    authorization = client.get(
        f"/api/canvas/{canvas.id}/capability/authorization")
    assert authorization.status_code == 200, authorization.text
    state = authorization.json()["authorization"]
    assert state["state"] == "content_drift", state

    drift = client.get(f"/api/canvas/{canvas.id}/capability/decisions")
    assert drift.status_code == 409, drift.text
    assert drift.json()["error"]["code"] == "review_required"
    assert drift.json()["error"]["authorization"]["state"] == "content_drift"

    refused_approval = client.post(
        f"/api/canvas/{canvas.id}/capability/assess/{execution_id}/approve",
    )
    assert refused_approval.status_code == 409, refused_approval.text
    assert refused_approval.json()["error"]["code"] == (
        "assessment_content_changed")


def test_unsupported_approval_fails_the_qualification_gate():
    """The judge must reject a confident APPROVE on a gap input."""
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]
                       / "scripts" / "acceptance"))
    from substantive_assessment_campaign import _judge

    dataset = {
        "id": "route-unit-set",
        "set_sha256": "route-unit",
        "subjects": ["Q-X"],
        "expected_v1": {"Q-X": "REVIEW"},
        "expected_v3": {"Q-X": "REVIEW"},
        "cases": {
            "Q-X": {
                "dimension": "unit", "determinate": False,
                "note": "amount is outside every taught rule",
            },
        },
    }
    result = {
        "success": True,
        "certified": True,
        "route": {
            "served_provider": "controlled",
            "served_model": "fixture",
        },
        "subjects": ["Q-X"],
        "policy_revision": "route-rev",
        "assessments": [{
            "subject_id": "Q-X",
            "decision": "APPROVE",
            "basis": ["looks fine"],
            "unresolved_requirements": [],
        }],
    }
    judgment = _judge(result, dataset, "create", strict=False)
    assert judgment["ok"] is False
    assert judgment["judgment"] == "failed"
    assert judgment["safe_abstention"]["passed"] is False
    assert judgment["safe_abstention"]["violations"][0]["kind"] == (
        "unsupported_approval")
