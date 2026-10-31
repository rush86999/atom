"""Downstream use of an assessment requires an authorized review.

The verifier's boundary: an assessment that needs review must not become an
authorized decision by being handed to a caller, and a human approval must be
bound to the exact assessment, source revision and policy revision.
"""
from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.database import Base
from core.models import Canvas


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def canvas(db):
    row = Canvas(
        id="canvas_review_1", tenant_id="default", workspace_id="ws-1",
        created_by="user-1", name="Review", canvas_type="sheet",
        content={}, status="active",
    )
    db.add(row)
    db.commit()
    return row


@pytest.fixture()
def user():
    return SimpleNamespace(
        id="user-1", workspace_id="ws-1", tenant_id="default",
        role="workspace_admin",
    )


def _manifest(policy=None):
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
        "teaching_binding": {"agent_id": "agent-1", "scope_id": "task-1"},
        "decision_options": ["APPROVE", "REVIEW", "DENY"],
        "task_policy": policy or (
            "Approve Amount >= 100 when Status is Open. Review 50-99. "
            "Deny below 50 or Closed."
        ),
        "outputs": ["xlsx"],
        "required_approvals": [],
    }


def _bind(db, canvas, user):
    from core.canvas_capability_service import bind_dataset, set_manifest

    set_manifest(db, canvas, user, _manifest())
    return bind_dataset(
        db, canvas, user,
        ["Ref", "Amount", "Status", "Note"],
        [
            ["R-1", 120, "Open", "alpha"],
            ["R-2", 75, "Open", "beta"],
            ["R-3", 20, "Closed", "gamma"],
            ["R-4", 95, "Open", "delta"],
        ],
        source={"file_name": "review.csv", "sha256": "fixture-sha"},
    )


def _fake_review(monkeypatch, unresolved=None):
    from core import review_result

    unresolved = unresolved or {}

    async def fake_generate(llm, **kwargs):
        rev = _FAKE_REV["revision"]
        assessments = []
        for subject, decision in (
            ("R-1", "APPROVE"), ("R-2", "REVIEW"),
            ("R-3", "DENY"), ("R-4", "REVIEW"),
        ):
            assessments.append({
                "subject_id": subject,
                "decision": decision,
                "basis": ["fixture"],
                "evidence_ids": [
                    f"ev:{subject}:{_FAKE_REV['rows'][subject]}"],
                "policy_ids": [f"policy:{rev}"],
                "unresolved_requirements": list(unresolved.get(subject, [])),
            })
        return "```review_result\n" + json.dumps(
            {"assessments": assessments}) + "\n```"

    monkeypatch.setenv("ATOM_REVIEW_MODEL", "deepseek-flash")
    monkeypatch.setattr(review_result, "generate_structured_review", fake_generate)


_FAKE_REV = {}


def _assess(db, canvas, user):
    from core.canvas_capability_service import (
        assess_operation, get_manifest, policy_revision,
    )

    _FAKE_REV["revision"] = policy_revision(get_manifest(canvas))
    _FAKE_REV["rows"] = {"R-1": 2, "R-2": 3, "R-3": 4, "R-4": 5}
    return asyncio.run(assess_operation(
        db, canvas, user, "all rows", llm_service=object()))


def test_unreviewed_recommendation_blocks_downstream_decisions(
        db, canvas, user, monkeypatch):
    from core.canvas_capability_service import (
        CapabilityError, decisions_operation,
    )

    _bind(db, canvas, user)
    _fake_review(monkeypatch, unresolved={"R-4": ["Amount 95 is below the band; confirm."]})
    result = _assess(db, canvas, user)

    assert result["certified"] is True
    assert result["review_required"] is True
    assert result["authorization"]["state"] == "review_required"

    with pytest.raises(CapabilityError) as exc:
        decisions_operation(canvas)
    assert exc.value.code == "review_required"
    assert exc.value.extra["authorization"]["unresolved_subjects"] == ["R-4"]


def test_human_approval_binds_to_the_exact_assessment(
        db, canvas, user, monkeypatch):
    from core.canvas_capability_service import (
        approve_assessment, decisions_operation,
    )

    _bind(db, canvas, user)
    _fake_review(monkeypatch, unresolved={"R-4": ["Confirm the amount."]})
    result = _assess(db, canvas, user)

    approved = approve_assessment(db, canvas, user, result["execution_id"])
    assert approved["authorization"]["state"] == "authorized"
    approval = approved["authorization"]["approval"]
    assert approval["execution_fingerprint"] == result["execution_fingerprint"]
    assert approval["policy_revision"] == result["policy_revision"]
    assert approval["source_revision"] == result["source_revision"]
    assert approval["approved_by"] == "user-1"

    decisions = decisions_operation(canvas)
    assert decisions["decisions"] == {
        "R-1": "APPROVE", "R-2": "REVIEW", "R-3": "DENY", "R-4": "REVIEW"}
    assert decisions["authorization"]["state"] == "authorized"


def test_changed_assessment_after_approval_requires_fresh_review(
        db, canvas, user, monkeypatch):
    from core.canvas_capability_service import (
        CapabilityError, approve_assessment, decisions_operation,
    )

    _bind(db, canvas, user)
    _fake_review(monkeypatch, unresolved={"R-4": ["Confirm the amount."]})
    first = _assess(db, canvas, user)
    approve_assessment(db, canvas, user, first["execution_id"])
    assert decisions_operation(canvas)["success"] is True

    # A new assessment is a new execution: the earlier approval must not carry.
    second = _assess(db, canvas, user)
    assert second["execution_id"] != first["execution_id"]
    with pytest.raises(CapabilityError) as exc:
        decisions_operation(canvas)
    assert exc.value.code == "review_required"
    assert exc.value.extra["authorization"]["state"] == "review_required"


def test_a_stale_approval_cannot_authorize_a_new_execution(
        db, canvas, user, monkeypatch):
    from core.canvas_capability_service import (
        CapabilityError, approve_assessment, get_manifest, policy_revision,
    )

    _bind(db, canvas, user)
    _fake_review(monkeypatch, unresolved={"R-4": ["Confirm the amount."]})
    result = _assess(db, canvas, user)
    approve_assessment(db, canvas, user, result["execution_id"])

    # APPROVING a different execution id is refused: the approval is bound to
    # the one that was actually reviewed.
    with pytest.raises(CapabilityError) as exc:
        approve_assessment(db, canvas, user, "some-other-execution")
    assert exc.value.code == "stale_assessment"


def test_policy_change_after_approval_requires_fresh_review(
        db, canvas, user, monkeypatch):
    from core.canvas_capability_service import (
        CapabilityError, approve_assessment, decisions_operation, set_manifest,
    )

    _bind(db, canvas, user)
    _fake_review(monkeypatch, unresolved={"R-4": ["Confirm the amount."]})
    result = _assess(db, canvas, user)
    approve_assessment(db, canvas, user, result["execution_id"])
    assert decisions_operation(canvas)["success"] is True

    set_manifest(db, canvas, user, _manifest(
        policy="Approve Amount >= 200 when Status is Open. Review otherwise."))
    with pytest.raises(CapabilityError) as exc:
        decisions_operation(canvas)
    assert exc.value.code == "review_required"
    assert exc.value.extra["authorization"]["state"] == "stale_assessment"


def test_certified_assessment_without_unresolved_requirements_needs_no_approval(
        db, canvas, user, monkeypatch):
    from core.canvas_capability_service import decisions_operation

    _bind(db, canvas, user)
    _fake_review(monkeypatch)
    result = _assess(db, canvas, user)

    assert result["review_required"] is False
    assert result["authorization"]["state"] == "authorized"
    assert decisions_operation(canvas)["decisions"]["R-1"] == "APPROVE"
