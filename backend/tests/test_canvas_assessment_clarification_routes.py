"""The clarification route must consume the saved answers into generation.

Sets up: assessment with an unresolved requirement -> public clarify route ->
capture what the resumed generation actually received.
"""
from __future__ import annotations

import json
import re

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
        yield db
    finally:
        db.close()
        engine.dispose()


@pytest.fixture()
def user():
    return type("U", (), {
        "id": "route-user", "email": "route@example.invalid",
        "workspace_id": "ws-route", "tenant_id": "tenant-route",
        "role": "workspace_admin", "is_active": True,
    })()


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
        id="canvas_clarify_route_1", tenant_id=user.tenant_id,
        workspace_id=user.workspace_id, created_by=user.id,
        name="Clarify route", canvas_type="sheet", content={},
        status="active",
    )
    db.add(canvas)
    db.commit()
    set_manifest(db, canvas, user, _manifest())
    bind_dataset(
        db, canvas, user,
        ["Ref", "Amount", "Status", "Note"],
        [["R-1", 120, "Open", "alpha"], ["R-2", 75, "Open", "beta"]],
        source={"file_name": "clarify_route.csv", "sha256": "route-sha"},
    )
    return canvas


CAPTURED = {"call": 0, "system": None}


def _fake_review(monkeypatch):
    from core import review_result

    async def fake_generate(llm, **kwargs):
        CAPTURED["call"] += 1
        system = "\n".join(
            str(message.get("content") or "")
            for message in kwargs["messages"])
        policy_id = re.search(r"policy:[0-9a-f]+", system).group(0)
        unresolved = (
            ["Confirm the amount for R-1."] if CAPTURED["call"] == 1 else [])
        assessments = [
            {
                "subject_id": "R-1", "decision": "APPROVE",
                "basis": ["Amount 120 is at least 100"],
                "evidence_ids": ["ev:R-1:2"],
                "policy_ids": [policy_id],
                "unresolved_requirements": list(unresolved),
            },
            {
                "subject_id": "R-2", "decision": "REVIEW",
                "basis": ["Amount 75 is between 50 and 99"],
                "evidence_ids": ["ev:R-2:3"],
                "policy_ids": [policy_id],
                "unresolved_requirements": [],
            },
        ]
        if CAPTURED["call"] > 1:
            CAPTURED["system"] = system
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


def test_clarify_route_consumes_saved_answers_into_generation(
        store, user, monkeypatch):
    db = store
    canvas = _seed(db, user)
    _fake_review(monkeypatch)
    CAPTURED.update(call=0, system=None)
    client = _client(db, user)

    assessed = client.post(
        f"/api/canvas/{canvas.id}/capability/assess",
        json={"ask": "Assess every row for the grant review."},
    ).json()
    execution_id = assessed["execution_id"]
    requirement = assessed["clarification"]["requirements"][0]
    requirement_id = requirement["requirement_id"]
    assert requirement["subject"] == "R-1"

    clarified = client.post(
        f"/api/canvas/{canvas.id}/capability/assess/{execution_id}/clarify",
        json={"answers": [
            {"requirement_id": requirement_id, "answer": "120.00 USD"}]},
    ).json()

    assert clarified.get("clarification_resumed") is True
    assert clarified["execution_id"] != execution_id
    system = CAPTURED["system"]
    assert system is not None, "the resumed generation was not dispatched"
    # Original objective survives into the resumed prompt.
    assert "Assess every row for the grant review." in system
    # The exact obligation and its answer reach generation.
    assert requirement_id in system
    assert "subject=R-1" in system
    assert "Confirm the amount for R-1." in system
    assert "120.00 USD" in system
    # The accepted revisions (source, policy, manifest) reach generation.
    assert "ACCEPTED REVISIONS" in system
    assert assessed["source_revision"] in system
    assert assessed["policy_revision"] in system
    assert assessed["manifest_revision"] in system
    # The resumed assessment used the same accepted policy revision.
    assert clarified["policy_revision"] == assessed["policy_revision"]
    # The old approval cannot authorize the resumed execution.
    assert clarified["authorization"]["state"] != "authorized"
