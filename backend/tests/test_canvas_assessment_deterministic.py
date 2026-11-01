"""Deterministic taught-rule assessment, separate from model judgment."""
from __future__ import annotations

import asyncio
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
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def user():
    return SimpleNamespace(
        id="user-det", workspace_id="ws-det", tenant_id="tenant-det",
        role="workspace_admin",
    )


def _manifest(*, with_review=True):
    decisions = ["APPROVE", "REVIEW", "DENY"] if with_review else [
        "APPROVE", "DENY"]
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
        "teaching_binding": {"agent_id": "agent-det", "scope_id": "task-det"},
        "decision_options": decisions,
        "task_policy": (
            "Deny Closed. Approve Open with Amount >= 100. "
            "Review Open with Amount 50-99. Otherwise review."),
        "assessment_mode": "deterministic",
        "decision_rules": [
            {"decision": "DENY",
             "when": [{"field": "Status", "op": "eq", "value": "Closed"}],
             "basis": "Closed records are denied."},
            {"decision": "APPROVE",
             "when": [
                 {"field": "Status", "op": "eq", "value": "Open"},
                 {"field": "Amount", "op": "gte", "value": 100},
             ],
             "basis": "Open and Amount at least 100."},
            {"decision": "REVIEW",
             "when": [
                 {"field": "Status", "op": "eq", "value": "Open"},
                 {"field": "Amount", "op": "gte", "value": 50},
                 {"field": "Amount", "op": "lt", "value": 100},
             ],
             "basis": "Open and Amount in the 50-99 band."},
        ],
        "outputs": ["xlsx"],
        "required_approvals": [],
    }


def _prepare(db, user, *, with_review=True):
    from core.canvas_capability_service import bind_dataset, set_manifest

    canvas = Canvas(
        id="canvas_det_1", tenant_id=user.tenant_id,
        workspace_id=user.workspace_id, created_by=user.id,
        name="Deterministic review", canvas_type="sheet", content={},
        status="active",
    )
    db.add(canvas)
    db.commit()
    set_manifest(db, canvas, user, _manifest(with_review=with_review))
    bind_dataset(
        db, canvas, user,
        ["Ref", "Amount", "Status", "Note"],
        [
            ["R-1", 120, "Open", "alpha"],
            ["R-2", 75, "Open", "beta"],
            ["R-3", 20, "Closed", "gamma"],
            ["R-4", "", "Open", "missing amount"],
            ["R-5", 0, "Open", "below the taught band"],
        ],
        source={"file_name": "deterministic.csv", "sha256": "det-sha"},
    )
    return canvas


def _assess(db, canvas, user):
    from core.canvas_capability_service import assess_operation

    return asyncio.run(assess_operation(
        db, canvas, user, "all rows", llm_service=object()))


def test_deterministic_rules_certify_without_a_model(db, user, monkeypatch):
    from core.canvas_capability_service import approve_assessment

    monkeypatch.delenv("ATOM_REVIEW_MODEL", raising=False)
    canvas = _prepare(db, user)
    result = _assess(db, canvas, user)

    assert result["certified"] is True
    assert result["route"]["served_provider"] == "deterministic"
    assert result["route"]["served_model"] == "taught_rules"
    assert result["qualification"]["status"] == "deterministic_rules"
    by_subject = {item["subject_id"]: item for item in result["assessments"]}
    assert by_subject["R-1"]["decision"] == "APPROVE"
    assert by_subject["R-2"]["decision"] == "REVIEW"
    assert by_subject["R-3"]["decision"] == "DENY"
    assert by_subject["R-4"]["decision"] == "REVIEW"
    assert by_subject["R-4"]["unresolved_requirements"]
    assert by_subject["R-5"]["decision"] == "REVIEW"
    assert by_subject["R-5"]["unresolved_requirements"]

    # Human review is still the default: the deterministic method does not
    # authorize its own output.
    assert result["authorized"] is False
    assert result["review_required"] is True
    assert "review_policy_always" in result["review_reasons"]
    approve_assessment(db, canvas, user, result["execution_id"])
    from core.canvas_capability_service import decisions_operation

    decisions = decisions_operation(canvas, db=db)
    assert decisions["decisions"]["R-1"] == "APPROVE"
    assert decisions["decisions"]["R-3"] == "DENY"


def test_deterministic_manifest_requires_review_fallback(db, user):
    from core.canvas_capability_service import CapabilityError, set_manifest

    canvas = _prepare(db, user)
    with pytest.raises(CapabilityError) as exc:
        set_manifest(db, canvas, user, _manifest(with_review=False))
    assert exc.value.code == "invalid_manifest"
    assert "REVIEW fallback" in exc.value.message


def test_deterministic_rule_change_invalidates_the_assessment(db, user):
    from core.canvas_capability_service import (
        CapabilityError, assess_operation, set_manifest,
    )

    canvas = _prepare(db, user)
    first = _assess(db, canvas, user)
    changed = _manifest()
    changed["decision_rules"][1]["when"][1]["value"] = 200
    set_manifest(db, canvas, user, changed)

    with pytest.raises(CapabilityError) as exc:
        from core.canvas_capability_service import decisions_operation

        decisions_operation(canvas, db=db)
    assert exc.value.code in ("review_required", "stale_assessment")
    second = _assess(db, canvas, user)
    assert second["execution_id"] != first["execution_id"]
    by_subject = {item["subject_id"]: item for item in second["assessments"]}
    assert by_subject["R-1"]["decision"] == "REVIEW"
    assert by_subject["R-1"]["unresolved_requirements"]
