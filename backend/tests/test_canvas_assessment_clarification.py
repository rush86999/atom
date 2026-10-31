"""Durable assessment clarification: persist, answer, resume, survive restart."""
from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from core.database import Base
from core.models import Canvas


@pytest.fixture()
def store(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'atom.db'}",
        connect_args={"check_same_thread": False},
        poolclass=NullPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    setup = Session()
    canvas = Canvas(
        id="canvas_clarify_1", tenant_id="default", workspace_id="ws-1",
        created_by="user-1", name="Clarify", canvas_type="sheet",
        content={}, status="active",
    )
    setup.add(canvas)
    setup.commit()
    yield Session, canvas
    setup.close()
    engine.dispose()


@pytest.fixture()
def user():
    return SimpleNamespace(
        id="user-1", workspace_id="ws-1", tenant_id="default",
        role="workspace_admin",
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
        "teaching_binding": {"agent_id": "agent-1", "scope_id": "task-1"},
        "decision_options": ["APPROVE", "REVIEW", "DENY"],
        "task_policy": (
            "Approve Amount >= 100 when Status is Open. Review 50-99. "
            "Deny below 50 or Closed."
        ),
        "outputs": ["xlsx"],
        "required_approvals": [],
    }


def _prepare(db, canvas, user):
    from core.canvas_capability_service import bind_dataset, set_manifest

    set_manifest(db, canvas, user, _manifest())
    bind_dataset(
        db, canvas, user,
        ["Ref", "Amount", "Status", "Note"],
        [
            ["R-1", 120, "Open", "alpha"],
            ["R-2", 75, "Open", "beta"],
            ["R-3", 20, "Closed", "gamma"],
            ["R-4", 95, "Open", "delta"],
        ],
        source={"file_name": "clarify.csv", "sha256": "fixture-sha"},
    )


_FAKE = {"unresolved": {}, "revision": None}


def _fake_review(monkeypatch):
    from core import review_result

    async def fake_generate(llm, **kwargs):
        rev = _FAKE["revision"]
        assessments = []
        for subject, decision, row in (
            ("R-1", "APPROVE", 2), ("R-2", "REVIEW", 3),
            ("R-3", "DENY", 4), ("R-4", "REVIEW", 5),
        ):
            assessments.append({
                "subject_id": subject,
                "decision": decision,
                "basis": ["fixture"],
                "evidence_ids": [f"ev:{subject}:{row}"],
                "policy_ids": [f"policy:{rev}"],
                "unresolved_requirements": list(
                    _FAKE["unresolved"].get(subject, [])),
            })
        return "```review_result\n" + json.dumps(
            {"assessments": assessments}) + "\n```"

    monkeypatch.setenv("ATOM_REVIEW_MODEL", "deepseek-flash")
    monkeypatch.setattr(review_result, "generate_structured_review", fake_generate)
    review_result.LAST_STRUCTURED_REVIEW.update(
        ok=True, dispatched=True, failure_kind=None, failure_stage=None,
        served_provider="ollama", served_model="llama3.1:8b")


def _assess(db, canvas, user, ask="all rows"):
    from core.canvas_capability_service import (
        assess_operation, get_manifest, policy_revision,
    )

    _FAKE["revision"] = policy_revision(get_manifest(canvas))
    return asyncio.run(assess_operation(
        db, canvas, user, ask, llm_service=object()))


def test_assessment_persists_the_clarification_obligation(
        store, user, monkeypatch):
    from core.canvas_capability_service import assessment_clarification

    Session, _ = store
    db = Session()
    try:
        canvas = db.query(Canvas).first()
        _prepare(db, canvas, user)
        _fake_review(monkeypatch)
        _FAKE["unresolved"] = {"R-4": ["Confirm the amount for R-4."]}
        result = _assess(db, canvas, user, ask="Assess every row.")

        clarification = result["clarification"]
        assert clarification["state"] == "open"
        assert clarification["open_count"] == 1
        requirement = clarification["requirements"][0]
        assert requirement["subject"] == "R-4"
        assert requirement["requirement"] == "Confirm the amount for R-4."
        assert clarification["request"]["ask"] == "Assess every row."
        assert clarification["request"]["execution_id"] == result["execution_id"]
        assert clarification["source_revision"]
        assert clarification["policy_revision"]
        assert assessment_clarification(canvas)["state"] == "open"
    finally:
        db.close()


def test_clarification_survives_a_restart(store, user, monkeypatch):
    from core.canvas_capability_service import assessment_clarification

    Session, _ = store
    first = Session()
    try:
        canvas = first.query(Canvas).first()
        _prepare(first, canvas, user)
        _fake_review(monkeypatch)
        _FAKE["unresolved"] = {"R-4": ["Confirm the amount."]}
        result = _assess(first, canvas, user)
        execution_id = result["execution_id"]
    finally:
        first.close()

    second = Session()
    try:
        canvas = second.query(Canvas).first()
        clarification = assessment_clarification(canvas)
        assert clarification["state"] == "open"
        assert clarification["execution_id"] == execution_id
        assert clarification["requirements"][0]["subject"] == "R-4"
    finally:
        second.close()


def test_partial_answer_stays_open_and_clears_approval(
        store, user, monkeypatch):
    from core.canvas_capability_service import (
        answer_assessment_clarification, approve_assessment,
    )

    Session, _ = store
    db = Session()
    try:
        canvas = db.query(Canvas).first()
        _prepare(db, canvas, user)
        _fake_review(monkeypatch)
        _FAKE["unresolved"] = {
            "R-2": ["Confirm the band."], "R-4": ["Confirm the amount."]}
        result = _assess(db, canvas, user)
        approve_assessment(db, canvas, user, result["execution_id"])

        answered = answer_assessment_clarification(
            db, canvas, user, result["execution_id"],
            [{"subject": "R-4", "answer": "95.00"}],
        )
        assert answered["ready_to_resume"] is False
        assert answered["clarification"]["open_count"] == 1
        assert answered["clarification"]["requirements"][0]["answer"] is None
        assert answered["clarification"]["requirements"][1]["answer"] == "95.00"
        # New inputs invalidate the earlier approval.
        assert answered["clarification"]["state"] == "open"
    finally:
        db.close()


def test_full_answer_resumes_the_same_work(store, user, monkeypatch):
    from core.canvas_capability_service import (
        answer_assessment_clarification, assessment_clarification,
    )

    Session, _ = store
    db = Session()
    try:
        canvas = db.query(Canvas).first()
        _prepare(db, canvas, user)
        _fake_review(monkeypatch)
        _FAKE["unresolved"] = {"R-4": ["Confirm the amount."]}
        first = _assess(db, canvas, user, ask="Assess every row.")

        answered = answer_assessment_clarification(
            db, canvas, user, first["execution_id"],
            [{"subject": "R-4", "answer": "95.00"}],
        )
        assert answered["ready_to_resume"] is True
        assert answered["clarification"]["state"] == "answered"

        # Resume re-dispatches the same canvas/policy (model mocked).
        _FAKE["unresolved"] = {}
        resumed = _assess(db, canvas, user, ask="Reassess with the answers.")
        assert resumed["execution_id"] != first["execution_id"]
        assert resumed["certified"] is True
        assert assessment_clarification(canvas)["state"] == "none"
    finally:
        db.close()


def test_answer_for_an_unknown_subject_is_refused(store, user, monkeypatch):
    from core.canvas_capability_service import (
        CapabilityError, answer_assessment_clarification,
    )

    Session, _ = store
    db = Session()
    try:
        canvas = db.query(Canvas).first()
        _prepare(db, canvas, user)
        _fake_review(monkeypatch)
        _FAKE["unresolved"] = {"R-4": ["Confirm the amount."]}
        result = _assess(db, canvas, user)
        with pytest.raises(CapabilityError) as exc:
            answer_assessment_clarification(
                db, canvas, user, result["execution_id"],
                [{"subject": "R-1", "answer": "120"}],
            )
        assert exc.value.code == "unknown_subject"
    finally:
        db.close()


def test_answer_after_reassessment_is_stale(store, user, monkeypatch):
    from core.canvas_capability_service import (
        CapabilityError, answer_assessment_clarification,
    )

    Session, _ = store
    db = Session()
    try:
        canvas = db.query(Canvas).first()
        _prepare(db, canvas, user)
        _fake_review(monkeypatch)
        _FAKE["unresolved"] = {"R-4": ["Confirm the amount."]}
        first = _assess(db, canvas, user)
        _fake_review(monkeypatch)
        second = _assess(db, canvas, user)

        with pytest.raises(CapabilityError) as exc:
            answer_assessment_clarification(
                db, canvas, user, first["execution_id"],
                [{"subject": "R-4", "answer": "95"}],
            )
        assert exc.value.code == "stale_assessment"
        assert exc.value.extra["current_execution_id"] == second["execution_id"]
    finally:
        db.close()
